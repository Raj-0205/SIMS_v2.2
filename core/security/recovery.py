# core/security/recovery.py

from __future__ import annotations
import base64
import hashlib
import re
import secrets
import time
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from core.database.transaction import TransactionManager
from core.exceptions import AuthenticationError, RateLimitExceededError, ValidationError
from core.logger.service import LogService
from core.security.audit import SecurityAuditRepository
from infrastructure.notification.service import NotificationService
from modules.users.repository import UserRepository

__all__ = [
    "RecoveryKeyService",
    "BreakGlassService",
    "DUMMY_ARGON2_HASH",
]

# Precomputed static Argon2id hash for constant-time dummy verification (anti-enumeration)
_DUMMY_HASHER = PasswordHasher()
DUMMY_ARGON2_HASH = _DUMMY_HASHER.hash("SIMS-STATIC-DUMMY-RECOVERY-KEY-VALUE-PROTECT")

# Global in-memory attempt timestamp log for CPU exhaustion / rate limiting
_GLOBAL_BREAK_GLASS_ATTEMPTS: list[float] = []
_GLOBAL_MAX_ATTEMPTS = 10
_GLOBAL_WINDOW_SECONDS = 900  # 15 minutes


@contextmanager
def _transaction():
    """Context manager guaranteeing active database transaction."""
    if TransactionManager.in_transaction():
        yield
    else:
        TransactionManager.begin()
        try:
            yield
            if TransactionManager.in_transaction():
                TransactionManager.commit()
        except Exception:
            if TransactionManager.in_transaction():
                TransactionManager.rollback()
            raise


def _enforce_global_rate_limit() -> None:
    """Enforces global rate limit across all break-glass attempts."""
    now = time.time()
    cutoff = now - _GLOBAL_WINDOW_SECONDS
    global _GLOBAL_BREAK_GLASS_ATTEMPTS
    _GLOBAL_BREAK_GLASS_ATTEMPTS = [t for t in _GLOBAL_BREAK_GLASS_ATTEMPTS if t > cutoff]
    if len(_GLOBAL_BREAK_GLASS_ATTEMPTS) >= _GLOBAL_MAX_ATTEMPTS:
        LogService.warning("Global break-glass rate limit exceeded.", context="BREAK_GLASS")
        raise RateLimitExceededError(
            "Too many emergency recovery requests. Please wait 15 minutes before trying again."
        )
    _GLOBAL_BREAK_GLASS_ATTEMPTS.append(now)



class RecoveryKeyService:
    """
    Cryptographic Break-Glass Recovery Key Subsystem.

    Guarantees:
    1. 256 bits of true cryptographic entropy from secrets.token_bytes(32).
    2. RFC 4648 Base32 representation (52 uppercase characters, no padding).
    3. Standard human-readable chunking: SIMS-XXXX-XXXX-XXXX-...-XXXX (13 groups of 4).
    4. Plaintext is NEVER stored at rest; only Argon2id hashes are persisted.
    5. Single active key per user (revoking previous active keys upon generation).
    """

    _hasher = PasswordHasher()
    BASE32_REGEX = re.compile(r"^[A-Z2-7]{52}$")

    @classmethod
    def generate_recovery_key(cls) -> tuple[str, str, str]:
        """
        Generates a 256-bit recovery key, its canonical string, formatted representation,
        and an opaque key identifier.

        Returns:
            (formatted_key, canonical_key, key_identifier)
        """
        raw_bytes = secrets.token_bytes(32)  # 256 bits
        canonical = base64.b32encode(raw_bytes).decode("ascii").rstrip("=")
        if len(canonical) != 52:
            raise RuntimeError(f"Unexpected base32 length: {len(canonical)} (expected 52)")

        chunks = [canonical[i : i + 4] for i in range(0, 52, 4)]
        formatted = f"SIMS-{'-'.join(chunks)}"
        key_identifier = f"REC-{secrets.token_hex(4).upper()}"
        return formatted, canonical, key_identifier

    @classmethod
    def canonicalize_key(cls, submitted_key: str) -> str:
        """
        Normalizes and validates a submitted recovery key into its 52-char canonical Base32 representation.
        Accepts keys with or without 'SIMS-' prefix and with or without dashes or whitespace.
        """
        if not submitted_key:
            raise ValidationError("Recovery key cannot be empty.")
        clean = submitted_key.strip().upper()
        if clean.startswith("SIMS-"):
            clean = clean[5:]
        clean = clean.replace("-", "").replace(" ", "").replace("\t", "")

        if not cls.BASE32_REGEX.match(clean):
            raise ValidationError(
                "Invalid recovery key format. Must be a 52-character Base32 string (A-Z, 2-7)."
            )
        return clean

    @classmethod
    def validate_format(cls, key: str) -> bool:
        """Returns True if the key is a valid 52-char Base32 recovery key (formatted or raw)."""
        try:
            cls.canonicalize_key(key)
            return True
        except Exception:
            return False

    @classmethod
    def hash_key(cls, canonical_key: str) -> str:
        """Computes Argon2id hash of the canonical key."""
        return cls._hasher.hash(canonical_key)

    @classmethod
    def hash_recovery_key(cls, key: str) -> str:
        """Hashes the recovery key after canonicalizing."""
        canonical = cls.canonicalize_key(key)
        return cls.hash_key(canonical)

    @classmethod
    def verify_key(cls, hash_str: str, canonical_key: str) -> bool:
        """Constant-time verification of submitted canonical key against stored hash."""
        try:
            return cls._hasher.verify(hash_str, canonical_key)
        except (VerifyMismatchError, InvalidHashError, Exception):
            return False

    @classmethod
    def verify_recovery_key(cls, key: str, key_hash: str) -> bool:
        """Constant-time verification of submitted key against stored hash."""
        try:
            canonical = cls.canonicalize_key(key)
            return cls.verify_key(key_hash, canonical)
        except Exception:
            return False

    @classmethod
    def verify_dummy_key(cls, key: str) -> bool:
        """Runs constant-time dummy verification against DUMMY_ARGON2_HASH."""
        try:
            canonical = cls.canonicalize_key(key)
        except Exception:
            canonical = "A" * 52
        return cls.verify_key(DUMMY_ARGON2_HASH, canonical)

    @classmethod
    def provision_initial_key(cls, user_id: int) -> tuple[int, str, str]:
        """Provisions an initial key and returns (key_row_id, canonical_key, formatted_key)."""
        with _transaction():
            formatted, canonical, identifier = cls.generate_recovery_key()
            key_hash = cls.hash_key(canonical)
            repo = UserRepository()
            key_id = repo.create_recovery_key(
                user_id=user_id,
                key_hash=key_hash,
                key_identifier=identifier,
                delivery_email_status="NOT_CONFIGURED",
            )
            return key_id, canonical, formatted

    @classmethod
    def rotate_recovery_key(cls, user_id: int, reason: str = "ROTATION") -> dict[str, Any]:
        """Issues a new active recovery key and revokes old keys."""
        with _transaction():
            formatted_key, identifier, status = cls.issue_recovery_key(user_id, send_email=True)
            canonical = cls.canonicalize_key(formatted_key)
            return {
                "raw_recovery_key": canonical,
                "formatted_recovery_key": formatted_key,
                "key_identifier": identifier,
                "delivery_status": status,
            }

    @classmethod
    def record_delivery_status(cls, key_id: int, status: str, error: Optional[str] = None) -> None:
        """Records UI/delivery telemetry for a recovery key."""
        with _transaction():
            repo = UserRepository()
            repo.update_recovery_key_delivery_telemetry(key_id, status, error)

    @classmethod
    def issue_recovery_key(
        cls,
        user_id: int,
        user_repo: Optional[UserRepository] = None,
        send_email: bool = True,
    ) -> tuple[str, str, str]:
        """
        Generates and securely provisions a new active recovery key for the specified user.
        Dispatches email backup to user's registered email address if requested.
        Returns:
            (formatted_recovery_key, key_identifier, delivery_status)
        The formatted_recovery_key MUST be displayed to the user once and discarded from memory.
        """
        with _transaction():
            repo = user_repo or UserRepository()
            user = repo.get_by_id(user_id)
            if not user:
                raise ValidationError(f"User ID {user_id} not found.")

            formatted_key, canonical_key, key_identifier = cls.generate_recovery_key()
            key_hash = cls.hash_key(canonical_key)

            email = user.get("email")
            delivery_status = "PENDING"
            delivery_error = None

            if send_email and email and email.strip():
                try:
                    sent = NotificationService.send_recovery_key_delivery_email(
                        recipient_email=email.strip(),
                        username=user["username"],
                        recovery_key=formatted_key,
                        key_id=key_identifier,
                    )
                    delivery_status = "DELIVERED" if sent else "FAILED"
                except Exception as exc:
                    delivery_status = "FAILED"
                    delivery_error = str(exc)
                    LogService.warning(
                        f"Email delivery for recovery key {key_identifier} failed: {exc}",
                        context="RECOVERY_KEY",
                    )
            else:
                delivery_status = "NOT_CONFIGURED"

            key_id = repo.create_recovery_key(
                user_id=user_id,
                key_hash=key_hash,
                key_identifier=key_identifier,
                delivery_email_status=delivery_status,
                delivery_email_error=delivery_error,
            )

            LogService.info(
                f"Issued recovery key {key_identifier} (row_id={key_id}) for user_id={user_id}. Delivery: {delivery_status}",
                context="RECOVERY_KEY",
            )
            return formatted_key, key_identifier, delivery_status



class BreakGlassService:
    """
    Break-Glass Emergency Authentication and Remediation Subsystem.

    Enforces:
    1. Per-account lockout after 3 consecutive failures (30 minutes).
    2. Global rate limiting (10 attempts / 15 minutes).
    3. Anti-enumeration / timing attack resistance via static dummy hash verification.
    4. Atomic 10-minute lease claiming (PENDING_REMEDIATION).
    5. 4-way validation before committing credential remediation.
    6. Automatic single-use consumption and key rotation.
    """

    LEASE_DURATION_SECONDS = 600  # 10 minutes

    @classmethod
    def reset_global_rate_limit(cls) -> None:
        """Resets the in-memory global rate limit counter (for testing and administrative reset)."""
        global _GLOBAL_BREAK_GLASS_ATTEMPTS
        _GLOBAL_BREAK_GLASS_ATTEMPTS.clear()

    @classmethod
    def claim_break_glass(
        cls,
        username: str,
        submitted_recovery_key: str,
        user_repo: Optional[UserRepository] = None,
        audit_repo: Optional[SecurityAuditRepository] = None,
    ) -> dict[str, Any]:
        """
        Validates the Break-Glass recovery key and claims an exclusive 10-minute remediation lease.
        """
        _enforce_global_rate_limit()

        with _transaction():
            repo = user_repo or UserRepository()
            auditor = audit_repo or SecurityAuditRepository()

            clean_username = username.strip() if username else ""
            if not clean_username:
                raise AuthenticationError("Username is required.")

            try:
                canonical_key = RecoveryKeyService.canonicalize_key(submitted_recovery_key)
            except ValidationError:
                # Still perform dummy verification to balance timing
                RecoveryKeyService.verify_key(DUMMY_ARGON2_HASH, "A" * 52)
                raise AuthenticationError("Invalid recovery key format.")

            user = repo.get_by_username(clean_username)

            # Anti-enumeration & non-existent user handling
            if not user or str(user.get("role", "")).upper() != "ADMINISTRATOR":
                RecoveryKeyService.verify_key(DUMMY_ARGON2_HASH, canonical_key)
                LogService.warning(
                    f"Break-glass attempted for non-existent or ineligible user: {clean_username}",
                    context="BREAK_GLASS",
                )
                raise AuthenticationError("Invalid recovery key or user does not exist.")

            user_id = int(user["id"])

            # Check Break-Glass lockout
            locked_until_str = user.get("break_glass_locked_until")
            if locked_until_str:
                try:
                    locked_dt = datetime.strptime(locked_until_str, "%Y-%m-%d %H:%M:%S").replace(
                        tzinfo=timezone.utc
                    )
                except ValueError:
                    locked_dt = datetime.fromisoformat(locked_until_str).replace(tzinfo=timezone.utc)

                if datetime.now(timezone.utc) < locked_dt:
                    auditor.insert(
                        entity_type="SECURITY",
                        entity_id=user_id,
                        action="BREAK_GLASS_LOCKED",
                        actor_name=user["username"],
                        actor_id=user_id,
                        details="Break-glass rejected due to active account lockout",
                    )
                    raise RateLimitExceededError(
                        "Emergency break-glass access is temporarily locked due to excessive failed attempts. "
                        "Please wait 30 minutes before trying again."
                    )

            active_key = repo.get_active_recovery_key(user_id)
            if not active_key:
                # No active key enrolled
                RecoveryKeyService.verify_key(DUMMY_ARGON2_HASH, canonical_key)
                LogService.warning(
                    f"No active recovery key found for Administrator: {clean_username}",
                    context="BREAK_GLASS",
                )
                raise AuthenticationError("No active emergency recovery key is registered for this account.")

            # Check if another session currently holds an unexpired lease
            if active_key.get("status") == "PENDING_REMEDIATION":
                pending_exp = active_key.get("pending_expires_at")
                is_expired = False
                if pending_exp:
                    try:
                        exp_dt = datetime.strptime(pending_exp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    except ValueError:
                        exp_dt = datetime.fromisoformat(pending_exp).replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) >= exp_dt:
                        is_expired = True
                if not is_expired:
                    auditor.insert(
                        entity_type="SECURITY",
                        entity_id=user_id,
                        action="BREAK_GLASS_CONFLICT",
                        actor_name=user["username"],
                        actor_id=user_id,
                        details="Concurrent break-glass attempt rejected; unexpired lease in progress",
                    )
                    TransactionManager.commit()
                    raise RateLimitExceededError(
                        "Another active emergency recovery session is currently in progress. "
                        "An active emergency lease is currently held. Please wait 10 minutes or use the existing active recovery session."
                    )

            # Verify key
            is_valid = RecoveryKeyService.verify_key(active_key["key_hash"], canonical_key)
            if not is_valid:
                failed_attempts = repo.record_failed_break_glass(user_id, max_attempts=3, lockout_minutes=30)
                auditor.insert(
                    entity_type="SECURITY",
                    entity_id=user_id,
                    action="BREAK_GLASS_FAILURE",
                    actor_name=user["username"],
                    actor_id=user_id,
                    details=f"Invalid recovery key attempt ({failed_attempts}/3)",
                )
                if failed_attempts >= 3:
                    auditor.insert(
                        entity_type="SECURITY",
                        entity_id=user_id,
                        action="BREAK_GLASS_ACCOUNT_LOCKED",
                        actor_name=user["username"],
                        actor_id=user_id,
                        details="Break-glass locked for 30 minutes",
                    )
                    TransactionManager.commit()
                    raise RateLimitExceededError(
                        "Emergency break-glass access is locked due to 3 failed attempts. Please wait 30 minutes."
                    )
                TransactionManager.commit()
                raise AuthenticationError(
                    f"Invalid recovery key. {3 - failed_attempts} attempt{'s' if 3 - failed_attempts != 1 else ''} remaining."
                )

            # Key is valid; reset failed counter
            repo.reset_failed_break_glass(user_id)

            # Generate unique lease tokens
            session_id = secrets.token_urlsafe(32)
            session_nonce = secrets.token_hex(32)
            nonce_hash = hashlib.sha256(session_nonce.encode("utf-8")).hexdigest()

            # Atomic claim
            claimed = repo.claim_break_glass_lease(
                key_id=int(active_key["id"]),
                session_id=session_id,
                session_nonce=nonce_hash,
                lease_seconds=cls.LEASE_DURATION_SECONDS,
            )

            if not claimed:
                LogService.warning(
                    f"Concurrent break-glass claim conflict on key_id={active_key['id']}",
                    context="BREAK_GLASS",
                )
                TransactionManager.commit()
                raise RateLimitExceededError(
                    "Another active emergency recovery session is currently in progress. "
                    "An active emergency lease is currently held. Please wait 10 minutes or use the existing active recovery session."
                )

            auditor.insert(
                entity_type="SECURITY",
                entity_id=user_id,
                action="BREAK_GLASS_LEASE_CLAIMED",
                actor_name=user["username"],
                actor_id=user_id,
                details=f"Exclusive remediation lease granted (session_id={session_id[:8]}...)",
            )

            now_utc = datetime.now(timezone.utc)
            expires_at_dt = now_utc + timedelta(seconds=cls.LEASE_DURATION_SECONDS)

            return {
                "lease_granted": True,
                "key_id": int(active_key["id"]),
                "key_identifier": active_key["key_identifier"],
                "session_id": session_id,
                "session_nonce": session_nonce,
                "user_id": user_id,
                "username": user["username"],
                "current_email": user.get("email"),
                "expires_at": expires_at_dt.strftime("%Y-%m-%d %H:%M:%S"),
            }

    @classmethod
    def cancel_lease(
        cls,
        key_id: int,
        session_id: str,
        user_repo: Optional[UserRepository] = None,
        audit_repo: Optional[SecurityAuditRepository] = None,
    ) -> bool:
        """Releases the remediation lease back to ACTIVE upon explicit cancellation."""
        with _transaction():
            repo = user_repo or UserRepository()
            auditor = audit_repo or SecurityAuditRepository()
            success = repo.cancel_break_glass_lease(key_id=key_id, session_id=session_id)
            if success:
                auditor.insert(
                    entity_type="SECURITY",
                    entity_id=key_id,
                    action="BREAK_GLASS_LEASE_CANCELLED",
                    actor_name="SYSTEM",
                    actor_id=None,
                    details=f"Break-glass lease cancelled for key_id={key_id}",
                )
            return success

    @classmethod
    def remediate(
        cls,
        key_id: int,
        session_id: str,
        session_nonce: str,
        user_id: int,
        new_password: str,
        new_email: Optional[str] = None,
        user_repo: Optional[UserRepository] = None,
        audit_repo: Optional[SecurityAuditRepository] = None,
    ) -> dict[str, Any]:
        """
        Executes the atomic Break-Glass remediation:
        1. 4-way validation of lease.
        2. Consumes active key.
        3. Updates password and optional new email.
        4. Bumps security_version and rotates security_stamp (invalidating all sessions).
        5. Automatically generates replacement recovery key and delivers backup.
        """
        with _transaction():
            repo = user_repo or UserRepository()
            auditor = audit_repo or SecurityAuditRepository()

            if not new_password or len(new_password) < 8:
                raise ValidationError("New password must be at least 8 characters long.")

            clean_email = new_email.strip() if new_email and new_email.strip() else None
            if clean_email:
                existing = repo.get_by_email(clean_email)
                if existing and int(existing["id"]) != user_id:
                    raise ValidationError("The specified email address is already registered to another user.")

            # Hash new password with Argon2id
            hasher = PasswordHasher()
            new_password_hash = hasher.hash(new_password)

            # Generate replacement recovery key
            new_formatted, new_canonical, new_identifier = RecoveryKeyService.generate_recovery_key()
            new_key_hash = RecoveryKeyService.hash_key(new_canonical)

            # Delivery ceremony for replacement key
            user = repo.get_by_id(user_id)
            effective_email = clean_email or (user.get("email") if user else None)
            delivery_status = "PENDING"
            delivery_error = None

            if effective_email and effective_email.strip():
                try:
                    sent = NotificationService.send_recovery_key_delivery_email(
                        recipient_email=effective_email.strip(),
                        username=user["username"] if user else "Administrator",
                        recovery_key=new_formatted,
                        key_id=new_identifier,
                    )
                    delivery_status = "DELIVERED" if sent else "FAILED"
                except Exception as exc:
                    delivery_status = "FAILED"
                    delivery_error = str(exc)
                    LogService.warning(f"Delivery email for replacement key failed: {exc}", context="BREAK_GLASS")
            else:
                delivery_status = "NOT_CONFIGURED"

            nonce_hash = hashlib.sha256(session_nonce.encode("utf-8")).hexdigest()

            # Atomic commit
            new_version, new_stamp, new_key_row_id = repo.commit_break_glass_remediation(
                key_id=key_id,
                session_id=session_id,
                session_nonce=nonce_hash,
                user_id=user_id,
                new_password_hash=new_password_hash,
                new_email=clean_email,
                new_key_identifier=new_identifier,
                new_key_hash=new_key_hash,
                delivery_email_status=delivery_status,
                delivery_email_error=delivery_error,
            )

            auditor.insert(
                entity_type="SECURITY",
                entity_id=user_id,
                action="BREAK_GLASS_REMEDIATION_COMPLETE",
                actor_name=user["username"] if user else "Administrator",
                actor_id=user_id,
                details=f"Break-Glass remediation successful. New recovery key: {new_identifier}, Security version: {new_version}",
            )

            if effective_email and effective_email.strip():
                try:
                    NotificationService.send_password_changed_alert(
                        recipient_email=effective_email.strip(),
                        username=user["username"] if user else "Administrator",
                        change_type="Break-Glass Emergency Remediation",
                    )
                except Exception:
                    pass

            return {
                "success": True,
                "remediation_completed": True,
                "security_version": new_version,
                "replacement_recovery_key": new_formatted,
                "replacement_key_identifier": new_identifier,
                "delivery_status": delivery_status,
            }
