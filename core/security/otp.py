# core/security/otp.py

from __future__ import annotations
import hashlib
import hmac
import secrets
from datetime import datetime, timezone, timedelta
from typing import Any, Tuple

from core.configuration.service import ConfigService
from core.exceptions import AuthenticationError
from core.logger.service import LogService
from modules.users.repository import UserRepository

__all__ = ["OTPService"]


class OTPService:
    """
    Cryptographic One-Time Password (OTP) Subsystem.

    Guarantees:
    1. Cryptographically secure 6-digit numeric generation.
    2. Zero plain OTP persistence: only salted cryptographic hashes are saved.
    3. Strict TTL enforcement.
    4. Single-use and attempt exhaustion protections.
    """

    def __init__(self, user_repo: UserRepository | None = None) -> None:
        self._user_repo = user_repo or UserRepository()

    @staticmethod
    def _generate_numeric_code() -> str:
        """Generate a cryptographically random 6-digit decimal code [000000..999999]."""
        return f"{secrets.randbelow(1_000_000):06d}"

    @staticmethod
    def _hash_otp(otp_code: str) -> str:
        """Hash the OTP using a secure random salt."""
        salt = secrets.token_hex(16)
        digest = hashlib.sha256(f"{salt}:{otp_code}".encode("utf-8")).hexdigest()
        return f"{salt}${digest}"

    @staticmethod
    def _verify_hash(otp_code: str, stored_hash: str) -> bool:
        """Verify the submitted OTP against the stored salted hash in constant time."""
        if not stored_hash or "$" not in stored_hash:
            return False
        salt, expected_digest = stored_hash.split("$", 1)
        actual_digest = hashlib.sha256(f"{salt}:{otp_code}".encode("utf-8")).hexdigest()
        return hmac.compare_digest(actual_digest, expected_digest)

    def create_challenge(self, user_id: int) -> Tuple[str, str]:
        """
        Creates and stores an OTP challenge for the given user.

        Invalidates any previous unconsumed challenges for this user.
        Returns:
            (challenge_token, plain_otp_code)
        The caller MUST transmit the plain_otp_code to the user and immediately discard it.
        """
        session_config = ConfigService.session()
        ttl_seconds = session_config.otp_ttl_seconds
        max_attempts = session_config.max_otp_attempts

        # Invalidate existing pending challenges for this user (Resend supersedes previous)
        self._user_repo.invalidate_pending_challenges_for_user(user_id)

        plain_otp = self._generate_numeric_code()
        otp_hash = self._hash_otp(plain_otp)
        challenge_token = secrets.token_urlsafe(32)

        now_utc = datetime.now(timezone.utc)
        expires_at_dt = now_utc + timedelta(seconds=ttl_seconds)
        expires_at_str = expires_at_dt.strftime("%Y-%m-%d %H:%M:%S")

        self._user_repo.create_otp_challenge(
            challenge_token=challenge_token,
            user_id=user_id,
            otp_hash=otp_hash,
            expires_at=expires_at_str,
            max_attempts=max_attempts,
        )

        LogService.info(
            f"Created OTP challenge for user_id={user_id} (token={challenge_token[:8]}...)",
            context="OTP",
        )
        return challenge_token, plain_otp

    def verify_challenge(self, challenge_token: str, submitted_otp: str) -> int:
        """
        Verifies an OTP challenge.

        Returns:
            user_id of the authenticated user upon success.

        Raises:
            AuthenticationError with safe, specific diagnostics if invalid, expired, or exhausted.
        """
        challenge = self._user_repo.get_otp_challenge(challenge_token)
        if not challenge:
            raise AuthenticationError("Invalid or nonexistent OTP verification challenge.")

        challenge_id = int(challenge["id"])
        user_id = int(challenge["user_id"])

        if bool(challenge.get("is_consumed")):
            raise AuthenticationError("This verification code has already been used.")

        # Check expiration
        expires_at_str = challenge["expires_at"]
        try:
            expires_at_dt = datetime.strptime(expires_at_str, "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            expires_at_dt = datetime.fromisoformat(expires_at_str).replace(tzinfo=timezone.utc)

        now_utc = datetime.now(timezone.utc)
        if now_utc > expires_at_dt:
            # Expired challenge
            self._user_repo.mark_otp_consumed(challenge_id)
            raise AuthenticationError("The verification code has expired. Please request a new one.")

        attempts_left = int(challenge.get("attempts_left") or 0)
        if attempts_left <= 0:
            self._user_repo.mark_otp_consumed(challenge_id)
            raise AuthenticationError("Maximum verification attempts exceeded. Please request a new code.")

        # Constant-time comparison
        is_valid = self._verify_hash(submitted_otp.strip(), challenge["otp_hash"])
        if not is_valid:
            remaining = self._user_repo.decrement_otp_attempts(challenge_id)
            if remaining <= 0:
                self._user_repo.mark_otp_consumed(challenge_id)
                raise AuthenticationError("Incorrect verification code. Maximum attempts reached.")
            raise AuthenticationError(
                f"Incorrect verification code. {remaining} attempt{'s' if remaining != 1 else ''} remaining."
            )

        # Mark challenge consumed
        self._user_repo.mark_otp_consumed(challenge_id)
        LogService.info(f"OTP challenge verified successfully for user_id={user_id}", context="OTP")
        return user_id
