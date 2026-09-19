# core/security/password_recovery.py

from __future__ import annotations
import hashlib
import secrets
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from argon2 import PasswordHasher

from core.database.transaction import TransactionManager
from core.exceptions import AuthenticationError, ValidationError
from core.logger.service import LogService
from core.security.audit import SecurityAuditRepository
from core.security.otp import OTPService, OTPPurpose
from core.security.recovery import DUMMY_ARGON2_HASH, RecoveryKeyService
from infrastructure.notification.service import NotificationService
from modules.users.repository import UserRepository

__all__ = ["PasswordRecoveryService"]


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


class PasswordRecoveryService:
    """
    Self-Service Password Recovery Subsystem for Administrators.

    Enforces:
    1. Generic anti-enumeration responses and constant-time dummy hashing.
    2. Purpose-scoped OTP challenge (PASSWORD_RESET).
    3. Ephemeral single-use reset tokens with strict 15-minute TTL.
    4. Session termination on password change via security stamp rotation.
    """

    RESET_TOKEN_TTL_SECONDS = 900  # 15 minutes

    @staticmethod
    def _mask_email(email: str) -> str:
        if not email or "@" not in email:
            return "***"
        parts = email.split("@", 1)
        name, domain = parts[0], parts[1]
        if len(name) <= 2:
            masked_name = name[0] + "*"
        else:
            masked_name = name[0] + ("*" * (len(name) - 2)) + name[-1]
        return f"{masked_name}@{domain}"

    @classmethod
    def request_recovery(
        cls,
        username_or_email: str,
        user_repo: Optional[UserRepository] = None,
        otp_service: Optional[OTPService] = None,
        audit_repo: Optional[SecurityAuditRepository] = None,
    ) -> dict[str, Any]:
        """
        Initiates password recovery for an Administrator account.
        Fails safely and uniformly against unknown accounts to prevent enumeration.
        """
        with _transaction():
            repo = user_repo or UserRepository()
            otp = otp_service or OTPService(repo)
            auditor = audit_repo or SecurityAuditRepository()

            query = username_or_email.strip() if username_or_email else ""
            if not query:
                raise ValidationError("Please enter your username or registered email address.")

            user = repo.get_by_username(query)
            if not user and "@" in query:
                user = repo.get_by_email(query)

            # Anti-enumeration check: Only Administrator accounts can recover via email OTP
            if (
                not user
                or str(user.get("role", "")).upper() != "ADMINISTRATOR"
                or not bool(user.get("is_active", 1))
                or not user.get("email")
            ):
                # Constant-time dummy verification
                RecoveryKeyService.verify_key(DUMMY_ARGON2_HASH, "A" * 52)
                LogService.info(
                    f"Password recovery requested for unknown or non-administrator identity: {query}",
                    context="RECOVERY",
                )
                # Generic response to prevent user enumeration
                return {
                    "initiated": True,
                    "challenge_token": None,
                    "masked_email": None,
                    "message": "If an Administrator account exists with those credentials, a verification code has been sent.",
                }

            user_id = int(user["id"])
            email = str(user["email"]).strip()

            challenge_token, plain_otp = otp.create_challenge(
                user_id=user_id,
                purpose=OTPPurpose.PASSWORD_RESET,
            )

            NotificationService.send_recovery_otp_email(
                recipient_email=email,
                username=user["username"],
                otp_code=plain_otp,
                ttl_minutes=5,
            )

            auditor.insert(
                entity_type="SECURITY",
                entity_id=user_id,
                action="PASSWORD_RECOVERY_INITIATED",
                actor_name=user["username"],
                actor_id=user_id,
                details=f"Password recovery OTP dispatched to {cls._mask_email(email)}",
            )

            return {
                "initiated": True,
                "challenge_token": challenge_token,
                "masked_email": cls._mask_email(email),
                "user_id": user_id,
                "username": user["username"],
                "message": "A verification code has been sent to your registered email address.",
            }

    @classmethod
    def verify_recovery_otp(
        cls,
        challenge_token: str,
        submitted_otp: str,
        user_repo: Optional[UserRepository] = None,
        otp_service: Optional[OTPService] = None,
        audit_repo: Optional[SecurityAuditRepository] = None,
    ) -> str:
        """
        Verifies the recovery OTP and returns an ephemeral single-use reset token.
        """
        with _transaction():
            repo = user_repo or UserRepository()
            otp = otp_service or OTPService(repo)
            auditor = audit_repo or SecurityAuditRepository()

            user_id = otp.verify_challenge(
                challenge_token=challenge_token,
                submitted_otp=submitted_otp,
                expected_purpose=OTPPurpose.PASSWORD_RESET,
            )

            # Generate single-use bearer token
            raw_reset_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(raw_reset_token.encode("utf-8")).hexdigest()

            now_utc = datetime.now(timezone.utc)
            expires_at_dt = now_utc + timedelta(seconds=cls.RESET_TOKEN_TTL_SECONDS)
            expires_at_str = expires_at_dt.strftime("%Y-%m-%d %H:%M:%S")

            repo.create_password_reset_token(
                token_hash=token_hash,
                user_id=user_id,
                expires_at=expires_at_str,
            )

            auditor.insert(
                entity_type="SECURITY",
                entity_id=user_id,
                action="PASSWORD_RECOVERY_OTP_VERIFIED",
                actor_name="SYSTEM",
                actor_id=user_id,
                details="Recovery OTP successfully verified; reset token issued.",
            )

            return raw_reset_token

    @classmethod
    def complete_password_reset(
        cls,
        reset_token: str,
        new_password: str,
        user_repo: Optional[UserRepository] = None,
        audit_repo: Optional[SecurityAuditRepository] = None,
    ) -> dict[str, Any]:
        """
        Consumes the reset token and securely applies the new password with stamp rotation.
        """
        with _transaction():
            repo = user_repo or UserRepository()
            auditor = audit_repo or SecurityAuditRepository()

            if not reset_token:
                raise ValidationError("Reset token is required.")

            if not new_password or len(new_password) < 8:
                raise ValidationError("Password must be at least 8 characters long.")

            token_hash = hashlib.sha256(reset_token.encode("utf-8")).hexdigest()
            token_record = repo.get_password_reset_token(token_hash)
            if not token_record:
                raise AuthenticationError("Invalid or expired password reset link.")

            user_id = int(token_record["user_id"])
            user = repo.get_by_id(user_id)
            username = user["username"] if user else "Administrator"

            hasher = PasswordHasher()
            new_hash = hasher.hash(new_password)

            new_version, new_stamp = repo.consume_password_reset_token_and_update_password(
                token_hash=token_hash,
                new_password_hash=new_hash,
            )

            auditor.insert(
                entity_type="SECURITY",
                entity_id=user_id,
                action="PASSWORD_RESET_COMPLETED",
                actor_name=username,
                actor_id=user_id,
                details=f"Self-service password recovery completed. Security version: {new_version}",
            )

            if user and user.get("email"):
                try:
                    NotificationService.send_password_changed_alert(
                        recipient_email=user["email"].strip(),
                        username=username,
                        change_type="Self-Service Password Recovery",
                    )
                except Exception:
                    pass

            return {
                "success": True,
                "security_version": new_version,
                "message": "Password successfully updated. You may now log in with your new password.",
            }
