# core/security/email_change.py

from __future__ import annotations
import re
import secrets
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from core.database.transaction import TransactionManager
from core.exceptions import AuthenticationError, ConflictError, ValidationError
from core.logger.service import LogService
from core.security.audit import SecurityAuditRepository
from core.security.otp import OTPService, OTPPurpose
from infrastructure.notification.service import NotificationService
from modules.users.repository import UserRepository

__all__ = ["EmailChangeService"]

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


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


class EmailChangeService:
    """
    Administrator Dual-Verification Email Change Subsystem.

    Enforces:
    1. Case-insensitive email normalization (lower(trim(email))).
    2. Zero duplicate emails across existing accounts.
    3. Mandatory dual OTP verification (OTP sent to current email AND new email).
    4. 15-minute TTL per request.
    5. Atomic finalization: updates user email, bumps security_version, and rotates security_stamp.
    """

    REQUEST_TTL_SECONDS = 900  # 15 minutes

    @staticmethod
    def normalize_email(email: str) -> str:
        """Strips whitespace and converts email to lowercase."""
        if not email:
            return ""
        return email.strip().lower()

    @classmethod
    def initiate_email_change(
        cls,
        user_id: int,
        new_email: str,
        user_repo: Optional[UserRepository] = None,
        otp_service: Optional[OTPService] = None,
        audit_repo: Optional[SecurityAuditRepository] = None,
    ) -> dict[str, Any]:
        """
        Initiates a dual-verification email change workflow.
        Dispatches two distinct OTP codes: one to current email, one to new email.
        """
        with _transaction():
            repo = user_repo or UserRepository()
            otp = otp_service or OTPService(repo)
            auditor = audit_repo or SecurityAuditRepository()

            user = repo.get_by_id(user_id)
            if not user:
                raise ValidationError(f"User ID {user_id} not found.")

            current_email = cls.normalize_email(user.get("email") or "")
            normalized_new_email = cls.normalize_email(new_email)

            if not normalized_new_email or not EMAIL_REGEX.match(normalized_new_email):
                raise ValidationError("Please provide a valid new email address.")

            if current_email == normalized_new_email:
                raise ValidationError("The new email address cannot be identical to the current email address.")

            # Check existing ownership
            existing_owner = repo.get_by_email(normalized_new_email)
            if existing_owner and int(existing_owner["id"]) != user_id:
                raise ConflictError("This email address is already in use by another account.")

            request_token = secrets.token_urlsafe(32)
            now_utc = datetime.now(timezone.utc)
            expires_at_dt = now_utc + timedelta(seconds=cls.REQUEST_TTL_SECONDS)
            expires_at_str = expires_at_dt.strftime("%Y-%m-%d %H:%M:%S")

            # Create OTP challenges
            curr_challenge_token, curr_plain_otp = otp.create_challenge(
                user_id=user_id,
                purpose=OTPPurpose.EMAIL_CHANGE_CURRENT,
            )
            new_challenge_token, new_plain_otp = otp.create_challenge(
                user_id=user_id,
                purpose=OTPPurpose.EMAIL_CHANGE_NEW,
            )

            repo.create_email_change_request(
                request_token=request_token,
                user_id=user_id,
                current_email=current_email,
                new_email=normalized_new_email,
                expires_at=expires_at_str,
            )

            # Dispatch notifications
            if current_email:
                NotificationService.send_email_change_current_notice(
                    recipient_email=current_email,
                    username=user["username"],
                    otp_code=curr_plain_otp,
                    new_email=normalized_new_email,
                    ttl_minutes=cls.REQUEST_TTL_SECONDS // 60,
                )

            NotificationService.send_email_change_new_verification(
                recipient_email=normalized_new_email,
                username=user["username"],
                otp_code=new_plain_otp,
                ttl_minutes=cls.REQUEST_TTL_SECONDS // 60,
            )

            auditor.insert(
                entity_type="SECURITY",
                entity_id=user_id,
                action="EMAIL_CHANGE_INITIATED",
                actor_name=user["username"],
                actor_id=user_id,
                details=f"Email change initiated: {current_email} -> {normalized_new_email}",
            )

            return {
                "request_token": request_token,
                "current_challenge_token": curr_challenge_token,
                "new_challenge_token": new_challenge_token,
                "current_email": current_email,
                "new_email": normalized_new_email,
                "expires_at": expires_at_str,
            }

    # Alias for API compatibility
    request_email_change = initiate_email_change

    @classmethod
    def verify_email_otp(
        cls,
        request_token: str,
        target: str,
        otp_code: str,
        challenge_token: Optional[str] = None,
        user_repo: Optional[UserRepository] = None,
        otp_service: Optional[OTPService] = None,
    ) -> dict[str, Any]:
        """
        Unified verification method for either 'current' or 'new' email OTP.
        Returns status dictionary: {'current_verified': bool, 'new_verified': bool, 'both_verified': bool}
        """
        with _transaction():
            repo = user_repo or UserRepository()
            otp = otp_service or OTPService(repo)

            req = repo.get_email_change_request(request_token)
            if not req or req["status"] != "PENDING":
                raise ValidationError("Invalid or expired email change session.")

            user_id = int(req["user_id"])
            purpose = OTPPurpose.EMAIL_CHANGE_CURRENT if target == "current" else OTPPurpose.EMAIL_CHANGE_NEW

            if not challenge_token:
                challenge = repo.get_latest_otp_challenge_by_purpose(user_id, purpose.value)
                if not challenge:
                    raise AuthenticationError(f"No active verification code found for {target} email.")
                challenge_token = challenge["challenge_token"]

            otp.verify_challenge(
                challenge_token=challenge_token,
                submitted_otp=otp_code,
                expected_purpose=purpose,
            )

            if target == "current":
                repo.mark_email_change_current_verified(request_token)
            else:
                repo.mark_email_change_new_verified(request_token)

            updated = repo.get_email_change_request(request_token)
            curr_v = bool(updated["current_verified"])
            new_v = bool(updated["new_verified"])
            return {
                "current_verified": curr_v,
                "new_verified": new_v,
                "both_verified": curr_v and new_v,
            }

    @classmethod
    def verify_current_email_otp(
        cls,
        request_token: str,
        challenge_token: str,
        submitted_otp: str,
        user_repo: Optional[UserRepository] = None,
        otp_service: Optional[OTPService] = None,
    ) -> bool:
        """Verifies the OTP dispatched to the current email address."""
        res = cls.verify_email_otp(
            request_token=request_token,
            target="current",
            otp_code=submitted_otp,
            challenge_token=challenge_token,
            user_repo=user_repo,
            otp_service=otp_service,
        )
        return res["current_verified"]

    @classmethod
    def verify_new_email_otp(
        cls,
        request_token: str,
        challenge_token: str,
        submitted_otp: str,
        user_repo: Optional[UserRepository] = None,
        otp_service: Optional[OTPService] = None,
    ) -> bool:
        """Verifies the OTP dispatched to the prospective new email address."""
        res = cls.verify_email_otp(
            request_token=request_token,
            target="new",
            otp_code=submitted_otp,
            challenge_token=challenge_token,
            user_repo=user_repo,
            otp_service=otp_service,
        )
        return res["new_verified"]

    @classmethod
    def cancel_email_change(
        cls,
        request_token: str,
        user_repo: Optional[UserRepository] = None,
        audit_repo: Optional[SecurityAuditRepository] = None,
    ) -> bool:
        """Cancels a pending email change request."""
        with _transaction():
            repo = user_repo or UserRepository()
            auditor = audit_repo or SecurityAuditRepository()
            req = repo.get_email_change_request(request_token)
            if req:
                repo.cancel_email_change_request(request_token)
                auditor.insert(
                    entity_type="SECURITY",
                    entity_id=req["user_id"],
                    action="EMAIL_CHANGE_CANCELLED",
                    actor_name="SYSTEM",
                    actor_id=req["user_id"],
                    details=f"Email change cancelled for request {request_token[:8]}",
                )
            return True

    @classmethod
    def finalize_email_change(
        cls,
        request_token: str,
        user_repo: Optional[UserRepository] = None,
        audit_repo: Optional[SecurityAuditRepository] = None,
    ) -> dict[str, Any]:
        """
        Finalizes the email change once both verification steps are complete.
        Rotates the security stamp, terminating any other active sessions.
        """
        with _transaction():
            repo = user_repo or UserRepository()
            auditor = audit_repo or SecurityAuditRepository()

            req = repo.get_email_change_request(request_token)
            if not req:
                raise ValidationError("Invalid email change request.")

            user_id = int(req["user_id"])
            user = repo.get_by_id(user_id)
            username = user["username"] if user else "Administrator"

            new_version, new_stamp = repo.finalize_email_change(request_token)

            auditor.insert(
                entity_type="SECURITY",
                entity_id=user_id,
                action="EMAIL_CHANGE_COMPLETED",
                actor_name=username,
                actor_id=user_id,
                details=f"Email updated to {req['new_email']}. Security version bumped to {new_version}.",
            )

            # Notify old and new email
            if req["current_email"]:
                try:
                    NotificationService.send_password_changed_alert(
                        recipient_email=req["current_email"],
                        username=username,
                        change_type=f"Email Address Changed to {req['new_email']}",
                    )
                except Exception:
                    pass

            try:
                NotificationService.send_password_changed_alert(
                    recipient_email=req["new_email"],
                    username=username,
                    change_type="Email Address Registration Confirmed",
                )
            except Exception:
                pass

            return {
                "success": True,
                "finalized": True,
                "new_email": req["new_email"],
                "security_version": new_version,
            }
