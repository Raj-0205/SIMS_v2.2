# core/security/auth.py

from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Optional

import flet as ft
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from core.configuration.service import ConfigService
from core.database.transaction import TransactionManager
from core.exceptions import AuthenticationError
from core.logger.service import LogService
from core.security.context import SecurityContext
from core.security.otp import OTPService
from core.security.roles import Role
from core.security.audit import SecurityAuditRepository
from infrastructure.notification.service import NotificationService
from modules.users.repository import UserRepository

__all__ = ["AuthService"]


class AuthService:
    """
    Authentication and password-security service.

    Supports dual-tier authentication:
    - Admin: Username + Argon2id Password -> /dashboard
    - Administrator: Username + Argon2id Password + Mandatory Email OTP -> /control-center
    """

    _password_hasher = PasswordHasher()

    @classmethod
    @contextmanager
    def _transaction(cls):
        """Ensures operations participate in an active transaction."""
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

    @staticmethod
    def _mask_email(email: str) -> str:
        """Utility to mask an email address for safe display in UI."""
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
    def hash_password(cls, password: str) -> str:
        """Generate an Argon2id password hash."""
        if not password or not password.strip():
            raise ValueError("Password cannot be empty.")
        return cls._password_hasher.hash(password)

    @classmethod
    def verify_password(cls, password_hash: str, password: str) -> bool:
        """Return True when the supplied password matches the stored hash."""
        try:
            return cls._password_hasher.verify(password_hash, password)
        except (VerifyMismatchError, InvalidHashError, Exception):
            return False

    @classmethod
    def authenticate(
        cls,
        username: str,
        password: str,
        intended_role: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Authenticate a user against username and password with strict role verification.
        """
        normalized_username = username.strip() if username else ""

        if not normalized_username or not password:
            LogService.warning(
                "Authentication rejected because credentials were incomplete.",
                context="AUTH",
            )
            raise AuthenticationError("Please enter both username and password.")

        with cls._transaction():
            repository = UserRepository()
            activity_repo = SecurityAuditRepository()
            user = repository.get_by_username(normalized_username)

            if not user:
                LogService.warning(
                    f"Failed authentication attempt for unknown username: '{normalized_username}'.",
                    context="AUTH",
                )
                raise AuthenticationError("Invalid username or password.")

            user_id = int(user["id"])

            # Check account lockout status
            locked_until_str = user.get("locked_until")
            if locked_until_str:
                try:
                    locked_until_dt = datetime.strptime(
                        locked_until_str, "%Y-%m-%d %H:%M:%S"
                    ).replace(tzinfo=timezone.utc)
                except ValueError:
                    locked_until_dt = datetime.fromisoformat(locked_until_str).replace(
                        tzinfo=timezone.utc
                    )

                now_utc = datetime.now(timezone.utc)
                if now_utc < locked_until_dt:
                    activity_repo.insert(
                        entity_type="SECURITY",
                        entity_id=user_id,
                        action="LOGIN_BLOCKED_LOCKED",
                        actor_name=user["username"],
                        actor_id=user_id,
                        details="Login attempt blocked due to active account lockout",
                    )
                    TransactionManager.commit()
                    raise AuthenticationError(
                        "Account is temporarily locked due to multiple failed login attempts. Please try again later."
                    )

            if not bool(user.get("is_active", 1)):
                LogService.warning(
                    f"Authentication rejected for inactive user: '{normalized_username}'.",
                    context="AUTH",
                )
                raise AuthenticationError("Account is inactive. Please contact system administrator.")

            stored_hash = str(user["password_hash"])
            if not cls.verify_password(stored_hash, password):
                failed_count = repository.record_failed_login(
                    user_id=user_id,
                    max_attempts=ConfigService.session().max_login_attempts,
                    lockout_minutes=ConfigService.session().lockout_duration_minutes,
                )
                activity_repo.insert(
                    entity_type="SECURITY",
                    entity_id=user_id,
                    action="LOGIN_FAILURE",
                    actor_name=user["username"],
                    actor_id=user_id,
                    details=f"Invalid password attempt (consecutive failures: {failed_count})",
                )
                is_locked = failed_count >= ConfigService.session().max_login_attempts
                if is_locked:
                    activity_repo.insert(
                        entity_type="SECURITY",
                        entity_id=user_id,
                        action="ACCOUNT_LOCKED",
                        actor_name=user["username"],
                        actor_id=user_id,
                        details=f"Account locked for {ConfigService.session().lockout_duration_minutes} minutes",
                    )
                TransactionManager.commit()
                if is_locked:
                    raise AuthenticationError(
                        f"Account locked due to {failed_count} consecutive failed login attempts. "
                        f"Please try again in {ConfigService.session().lockout_duration_minutes} minutes."
                    )
                raise AuthenticationError("Invalid username or password.")

            # Password is valid; reset failed login counter
            repository.reset_failed_logins(user_id)

            # Authoritative Role Verification
            actual_role = str(user.get("role") or "").strip().upper()
            if actual_role == "OPERATOR":
                # Legacy normalization
                actual_role = Role.ADMIN.value

            if intended_role:
                clean_intended = str(intended_role).strip().upper()
                if clean_intended != actual_role:
                    activity_repo.insert(
                        entity_type="SECURITY",
                        entity_id=user_id,
                        action="LOGIN_ROLE_MISMATCH",
                        actor_name=user["username"],
                        actor_id=user_id,
                        details=f"Intended role '{clean_intended}' does not match authoritative role '{actual_role}'",
                    )
                    TransactionManager.commit()
                    raise AuthenticationError(
                        f"Account is not authorized for the selected role '{intended_role}'."
                    )

            # Rehash check
            if cls._password_hasher.check_needs_rehash(stored_hash):
                try:
                    new_hash = cls.hash_password(password)
                    repository.update_password(user_id, new_hash)
                except Exception as exc:
                    LogService.warning(f"Background password rehash failed: {exc}", context="AUTH")

            # Route by authoritative DB role
            if actual_role == Role.ADMIN.value:
                activity_repo.insert(
                    entity_type="SECURITY",
                    entity_id=user_id,
                    action="LOGIN_SUCCESS",
                    actor_name=user["username"],
                    actor_id=user_id,
                    details="Admin authenticated successfully",
                )
                return {
                    "requires_otp": False,
                    "user": user,
                    "redirect_route": "/dashboard",
                }

            elif actual_role == Role.ADMINISTRATOR.value:
                admin_email = user.get("email")
                if not admin_email or not admin_email.strip():
                    raise AuthenticationError(
                        "Administrator account has no configured email address for verification. Please contact support."
                    )

                otp_service = OTPService(repository)
                challenge_token, plain_otp = otp_service.create_challenge(user_id)

                NotificationService.send_otp_email(
                    recipient_email=admin_email.strip(),
                    username=user["username"],
                    otp_code=plain_otp,
                    ttl_minutes=ConfigService.session().otp_ttl_seconds // 60,
                )

                activity_repo.insert(
                    entity_type="SECURITY",
                    entity_id=user_id,
                    action="OTP_GENERATED",
                    actor_name=user["username"],
                    actor_id=user_id,
                    details=f"Email OTP dispatched to {cls._mask_email(admin_email)}",
                )

                return {
                    "requires_otp": True,
                    "challenge_token": challenge_token,
                    "masked_email": cls._mask_email(admin_email),
                    "user_id": user_id,
                    "username": user["username"],
                    "redirect_route": "/control-center",
                }

            else:
                raise AuthenticationError(f"Unrecognized role '{actual_role}' on account.")

    @classmethod
    def verify_otp(cls, challenge_token: str, submitted_otp: str) -> dict[str, Any]:
        """
        Validates OTP code for an active challenge and authenticates Administrator.
        """
        with cls._transaction():
            repository = UserRepository()
            activity_repo = SecurityAuditRepository()
            otp_service = OTPService(repository)

            try:
                user_id = otp_service.verify_challenge(challenge_token, submitted_otp)
            except AuthenticationError as exc:
                activity_repo.insert(
                    entity_type="SECURITY",
                    entity_id=0,
                    action="OTP_FAILURE",
                    actor_name="ANONYMOUS",
                    actor_id=None,
                    details=f"OTP verification failed: {str(exc)}",
                )
                TransactionManager.commit()
                raise

            user = repository.get_by_id(user_id)
            if not user or not bool(user.get("is_active", 1)):
                raise AuthenticationError("Account is inactive or does not exist.")

            activity_repo.insert(
                entity_type="SECURITY",
                entity_id=user_id,
                action="OTP_VERIFIED",
                actor_name=user["username"],
                actor_id=user_id,
                details="OTP code successfully verified",
            )
            activity_repo.insert(
                entity_type="SECURITY",
                entity_id=user_id,
                action="LOGIN_SUCCESS",
                actor_name=user["username"],
                actor_id=user_id,
                details="Administrator privileged login completed via OTP",
            )

            return {
                "user": user,
                "redirect_route": "/control-center",
            }

    @classmethod
    def resend_otp(cls, challenge_token: str) -> dict[str, Any]:
        """
        Issues a new OTP challenge, invalidating the previous one, and sends a new email.
        """
        with cls._transaction():
            repository = UserRepository()
            activity_repo = SecurityAuditRepository()
            challenge = repository.get_otp_challenge(challenge_token)

            if not challenge:
                raise AuthenticationError("Verification session not found or expired. Please log in again.")

            user_id = int(challenge["user_id"])
            user = repository.get_by_id(user_id)
            if not user or not bool(user.get("is_active", 1)):
                raise AuthenticationError("Account is inactive or does not exist.")

            admin_email = user.get("email")
            if not admin_email or not admin_email.strip():
                raise AuthenticationError("Administrator account has no configured email address.")

            otp_service = OTPService(repository)
            new_token, plain_otp = otp_service.create_challenge(user_id)

            NotificationService.send_otp_email(
                recipient_email=admin_email.strip(),
                username=user["username"],
                otp_code=plain_otp,
                ttl_minutes=ConfigService.session().otp_ttl_seconds // 60,
            )

            activity_repo.insert(
                entity_type="SECURITY",
                entity_id=user_id,
                action="OTP_RESENT",
                actor_name=user["username"],
                actor_id=user_id,
                details=f"New OTP code dispatched to {cls._mask_email(admin_email)}",
            )

            return {
                "challenge_token": new_token,
                "masked_email": cls._mask_email(admin_email),
            }

    # --- Session Management ---

    @classmethod
    def _get_session(cls, page: ft.Page) -> Any:
        sess = getattr(page, "session", None)
        if sess is not None and hasattr(sess, "store"):
            return sess.store
        return sess

    @classmethod
    def _session_set(cls, session: Any, key: str, value: Any) -> None:
        if hasattr(session, "set"):
            session.set(key, value)
        elif isinstance(session, dict):
            session[key] = value

    @classmethod
    def _session_get(cls, session: Any, key: str, default: Any = None) -> Any:
        if session is None:
            return default
        if isinstance(session, dict):
            return session.get(key, default)
        if hasattr(session, "contains_key") and callable(session.contains_key):
            if session.contains_key(key):
                val = session.get(key)
                return val if val is not None else default
            return default
        if hasattr(session, "get") and callable(session.get):
            try:
                val = session.get(key)
                return val if val is not None else default
            except TypeError:
                try:
                    return session.get(key, default)
                except Exception:
                    return default
            except Exception:
                return default
        return default

    @classmethod
    def get_current_role(cls, page: ft.Page) -> str | None:
        """Returns the current authenticated role or None."""
        if not cls.is_authenticated(page):
            return None
        session = cls._get_session(page)
        role = cls._session_get(session, "role")
        return str(role).strip().upper() if role else None

    @classmethod
    def _session_clear(cls, session: Any) -> None:
        if hasattr(session, "clear"):
            session.clear()

    @classmethod
    def login(cls, page: ft.Page, user: dict[str, Any]) -> None:
        """Store authenticated state in the current transient Flet session."""
        session = cls._get_session(page)
        now_ts = datetime.now(timezone.utc).timestamp()

        cls._session_set(session, "authenticated", True)
        cls._session_set(session, "user_id", user["id"])
        cls._session_set(session, "username", user["username"])
        cls._session_set(session, "role", user["role"])
        cls._session_set(session, "login_timestamp", now_ts)
        cls._session_set(session, "last_activity_timestamp", now_ts)

        SecurityContext.set_current_user(user["id"], user["username"], user["role"])

        LogService.info(
            f"Session started for user '{user['username']}' with role '{user['role']}'.",
            context="AUTH",
        )

    @classmethod
    def logout(cls, page: ft.Page) -> None:
        """Clear the current transient authentication session."""
        session = cls._get_session(page)
        username = cls._session_get(session, "username")
        cls._session_clear(session)
        SecurityContext.clear()

        LogService.info(
            f"Authentication session cleared for user '{username}'.",
            context="AUTH",
        )

    @classmethod
    def is_authenticated(cls, page: ft.Page) -> bool:
        """Return True when the current Flet session is authenticated and active."""
        session = cls._get_session(page)
        if cls._session_get(session, "authenticated") is not True:
            return False
        if cls.check_session_timeout(page):
            return False
        return True

    @classmethod
    def check_session_timeout(cls, page: ft.Page) -> bool:
        """
        Checks if the session has expired due to inactivity.

        Admin: 60 minutes default.
        Administrator: 15 minutes default.
        Returns True if timed out (and clears session), False otherwise.
        """
        session = cls._get_session(page)
        last_activity = cls._session_get(session, "last_activity_timestamp")
        role = cls._session_get(session, "role")

        if not last_activity or not role:
            return False

        now_ts = datetime.now(timezone.utc).timestamp()
        timeout_minutes = (
            ConfigService.session().administrator_timeout_minutes
            if str(role).upper() == Role.ADMINISTRATOR.value
            else ConfigService.session().admin_timeout_minutes
        )
        timeout_seconds = timeout_minutes * 60

        if (now_ts - float(last_activity)) > timeout_seconds:
            LogService.info(
                f"Session timed out for role '{role}' after {timeout_minutes} minutes of inactivity.",
                context="AUTH",
            )
            cls.logout(page)
            return True

        # Session active; touch activity timestamp and ensure SecurityContext
        cls._session_set(session, "last_activity_timestamp", now_ts)
        SecurityContext.set_current_user(
            cls._session_get(session, "user_id"),
            cls._session_get(session, "username"),
            cls._session_get(session, "role"),
        )
        return False
