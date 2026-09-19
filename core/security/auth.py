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
from core.exceptions import AuthenticationError, ForbiddenError, ValidationError
from core.logger.service import LogService
from core.security.context import SecurityContext
from core.security.otp import OTPService, OTPPurpose
from core.security.permissions import Permission, SecurityPermission
from core.security.authorization import AuthorizationService
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
        if not password_hash or not password:
            return False
        if not str(password_hash).startswith("$") and str(password).startswith("$"):
            password_hash, password = password, password_hash
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

    # --- Password & Governance Ceremonies ---

    @classmethod
    def change_password(
        cls,
        user_id: int,
        current_password: str,
        new_password: str,
    ) -> dict[str, Any]:
        """
        Allows an authenticated user to change their own password upon verifying their current password.
        Bumps security_version and rotates security_stamp, terminating other concurrent sessions.
        """
        if not new_password or len(new_password) < 8:
            raise ValidationError("New password must be at least 8 characters long.")

        with cls._transaction():
            repo = UserRepository()
            auditor = SecurityAuditRepository()
            user = repo.get_by_id(user_id)
            if not user or not bool(user.get("is_active", 1)):
                raise AuthenticationError("User not found or account is inactive.")

            if not cls.verify_password(user["password_hash"], current_password):
                auditor.insert(
                    entity_type="SECURITY",
                    entity_id=user_id,
                    action="PASSWORD_CHANGE_FAILURE",
                    actor_name=user["username"],
                    actor_id=user_id,
                    details="Incorrect current password provided during password change attempt",
                )
                raise AuthenticationError("Current password is incorrect.")

            new_hash = cls.hash_password(new_password)
            new_ver, new_stamp = repo.update_password(user_id, new_hash)

            auditor.insert(
                entity_type="SECURITY",
                entity_id=user_id,
                action="PASSWORD_CHANGE_SUCCESS",
                actor_name=user["username"],
                actor_id=user_id,
                details=f"Password changed successfully. Monotonic version bumped to {new_ver}.",
            )

            if user.get("email"):
                try:
                    NotificationService.send_password_changed_alert(
                        recipient_email=user["email"].strip(),
                        username=user["username"],
                        change_type="Direct Password Change",
                    )
                except Exception:
                    pass

            return {
                "success": True,
                "security_version": new_ver,
                "security_stamp": new_stamp,
            }

    @classmethod
    def initiate_admin_password_reset(
        cls,
        administrator_user_id: Any = None,
        administrator_password: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Step 1 of Administrator-controlled Admin Password Reset ceremony:
        1. Validates Administrator identity & elevated privilege (ADMIN_PASSWORD_RESET).
        2. Re-authenticates Administrator password.
        3. Issues a purpose-scoped OTP challenge to the Administrator's registered email.
        """
        if isinstance(administrator_user_id, str) and administrator_password is None:
            administrator_password = administrator_user_id
            administrator_user_id = None

        if administrator_user_id is None:
            curr = SecurityContext.current_user()
            if not curr:
                raise ForbiddenError("Authentication required to reset Admin password.")
            administrator_user_id = curr.id

        if not administrator_password:
            raise AuthenticationError("Administrator re-authentication password is required.")

        with cls._transaction():
            repo = UserRepository()
            auditor = SecurityAuditRepository()

            admin_user = repo.get_by_id(int(administrator_user_id))
            if not admin_user or str(admin_user.get("role", "")).upper() != Role.ADMINISTRATOR.value:
                raise ForbiddenError("Only elevated Administrators may reset the Admin password.")

            AuthorizationService.check_permission(
                Role.ADMINISTRATOR.value, SecurityPermission.ADMIN_PASSWORD_RESET
            )

            if not cls.verify_password(admin_user["password_hash"], administrator_password):
                auditor.insert(
                    entity_type="SECURITY",
                    entity_id=administrator_user_id,
                    action="ADMIN_RESET_AUTH_FAILURE",
                    actor_name=admin_user["username"],
                    actor_id=administrator_user_id,
                    details="Invalid Administrator re-authentication password for Admin password reset ceremony",
                )
                raise AuthenticationError("Administrator re-authentication failed: incorrect password.")

            email = admin_user.get("email")
            if not email or not email.strip():
                raise ValidationError("Administrator account has no registered email to deliver verification OTP.")

            otp_service = OTPService(repo)
            challenge_token, plain_otp = otp_service.create_challenge(
                user_id=int(administrator_user_id),
                purpose=OTPPurpose.ADMIN_PASSWORD_RESET,
            )

            NotificationService.send_admin_reset_otp_email(
                recipient_email=email.strip(),
                username=admin_user["username"],
                otp_code=plain_otp,
                ttl_minutes=ConfigService.session().otp_ttl_seconds // 60,
            )

            auditor.insert(
                entity_type="SECURITY",
                entity_id=administrator_user_id,
                action="ADMIN_RESET_OTP_DISPATCHED",
                actor_name=admin_user["username"],
                actor_id=administrator_user_id,
                details=f"Admin password reset authorization OTP dispatched to {cls._mask_email(email)}",
            )

            return {
                "challenge_token": challenge_token,
                "masked_email": cls._mask_email(email),
            }

    @classmethod
    def complete_admin_password_reset(
        cls,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Step 2 of Administrator-controlled Admin Password Reset ceremony:
        1. Validates the OTP with expected purpose ADMIN_PASSWORD_RESET.
        2. Applies the new Argon2id password hash to the target Admin user account.
        3. Rotates Admin user's security stamp and increments security version (instantly invalidating active Admin sessions).
        4. Writes an immutable audit trail entry.
        """
        administrator_user_id = kwargs.get("administrator_user_id")
        challenge_token = kwargs.get("challenge_token")
        submitted_otp = kwargs.get("submitted_otp")
        new_admin_password = kwargs.get("new_admin_password")
        target_admin_username = kwargs.get("target_admin_username", "admin")

        if args:
            if len(args) >= 4 and isinstance(args[0], int):
                administrator_user_id = args[0]
                challenge_token = args[1]
                submitted_otp = args[2]
                new_admin_password = args[3]
                if len(args) >= 5:
                    target_admin_username = args[4]
            elif len(args) >= 3 and isinstance(args[0], str):
                challenge_token = args[0]
                submitted_otp = args[1]
                new_admin_password = args[2]
                if len(args) >= 4:
                    if isinstance(args[3], int):
                        administrator_user_id = args[3]
                    elif isinstance(args[3], str):
                        target_admin_username = args[3]
                if len(args) >= 5:
                    target_admin_username = args[4]

        if not new_admin_password or len(new_admin_password) < 8:
            raise ValidationError("New Admin password must be at least 8 characters long.")

        with cls._transaction():
            repo = UserRepository()
            auditor = SecurityAuditRepository()

            otp_service = OTPService(repo)
            try:
                verified_uid = otp_service.verify_challenge(
                    challenge_token=challenge_token,
                    submitted_otp=submitted_otp,
                    expected_purpose=OTPPurpose.ADMIN_PASSWORD_RESET,
                )
            except AuthenticationError:
                if administrator_user_id:
                    user_row = repo.get_by_id(int(administrator_user_id))
                    actor_name = user_row["username"] if user_row else "UNKNOWN"
                else:
                    actor_name = "UNKNOWN"
                auditor.insert(
                    entity_type="SECURITY",
                    entity_id=administrator_user_id or 0,
                    action="ADMIN_RESET_OTP_FAILURE",
                    actor_name=actor_name,
                    actor_id=administrator_user_id,
                    details="Invalid or expired OTP submitted during Admin password reset completion",
                )
                raise

            if administrator_user_id and int(verified_uid) != int(administrator_user_id):
                raise AuthenticationError("OTP challenge authorization mismatch.")

            admin_user = repo.get_by_id(int(verified_uid))
            if not admin_user or str(admin_user.get("role", "")).upper() != Role.ADMINISTRATOR.value:
                raise ForbiddenError("Only elevated Administrators may reset the Admin password.")

            # Find target Admin account
            target_admin = repo.get_by_username(target_admin_username)
            if not target_admin and target_admin_username == "admin":
                # Fallback: locate any account with role 'ADMIN'
                all_users = repo.list_all()
                for u in all_users:
                    if str(u.get("role", "")).upper() == Role.ADMIN.value:
                        target_admin = u
                        break

            if not target_admin or str(target_admin.get("role", "")).upper() != Role.ADMIN.value:
                raise ValidationError(f"Target Admin account '{target_admin_username}' not found.")

            target_admin_id = int(target_admin["id"])
            new_hash = cls.hash_password(new_admin_password)
            new_ver, new_stamp = repo.update_password(target_admin_id, new_hash)

            auditor.insert(
                entity_type="SECURITY",
                entity_id=target_admin_id,
                action="ADMIN_PASSWORD_RESET_COMPLETED",
                actor_name=admin_user["username"],
                actor_id=administrator_user_id,
                details=f"Admin password reset completed by Administrator '{admin_user['username']}'. Admin sessions invalidated.",
            )

            return {
                "success": True,
                "target_username": target_admin["username"],
                "target_security_version": new_ver,
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
    def login(
        cls,
        page: ft.Page,
        user: Any,
        password: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Store authenticated state in the current transient Flet session."""
        if isinstance(user, str) and password is not None:
            res = cls.authenticate(user, password)
            user_data = res.get("user")
        elif isinstance(user, dict):
            user_data = user
        else:
            user_data = None

        if not user_data:
            return None

        session = cls._get_session(page)
        now_ts = datetime.now(timezone.utc).timestamp()

        sec_ver = user_data.get("security_version", 1)
        sec_stamp = user_data.get("security_stamp", "")

        cls._session_set(session, "authenticated", True)
        cls._session_set(session, "user_id", user_data["id"])
        cls._session_set(session, "username", user_data["username"])
        cls._session_set(session, "role", user_data["role"])
        cls._session_set(session, "security_version", sec_ver)
        cls._session_set(session, "security_stamp", sec_stamp)
        cls._session_set(session, "login_timestamp", now_ts)
        cls._session_set(session, "last_activity_timestamp", now_ts)

        SecurityContext.set_current_user(
            user_data["id"], user_data["username"], user_data["role"], sec_ver, sec_stamp
        )

        LogService.info(
            f"Session started for user '{user_data['username']}' with role '{user_data['role']}'.",
            context="AUTH",
        )
        return user_data

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
    def validate_session_state(cls, page: ft.Page) -> bool:
        """
        Validates the ambient session against the authoritative database security state.
        Detects if a credential change or explicit revocation occurred in another session/thread.
        """
        session = cls._get_session(page)
        user_id = cls._session_get(session, "user_id")
        if not user_id:
            return False

        sess_ver = cls._session_get(session, "security_version")
        sess_stamp = cls._session_get(session, "security_stamp")

        # If not set, allow backward compatibility
        if sess_ver is None and not sess_stamp:
            return True

        with cls._transaction():
            user = UserRepository().get_by_id(int(user_id))
            if not user or not bool(user.get("is_active", 1)):
                cls.logout(page)
                return False

            db_ver = user.get("security_version", 1)
            db_stamp = user.get("security_stamp", "")

            if sess_ver is not None and int(sess_ver) != int(db_ver):
                LogService.warning(
                    f"Session invalidated: security_version mismatch for user_id={user_id} (session={sess_ver}, db={db_ver})",
                    context="AUTH",
                )
                cls.logout(page)
                return False

            if sess_stamp is not None and sess_stamp != "" and sess_stamp != db_stamp:
                LogService.warning(
                    f"Session invalidated: security_stamp mismatch for user_id={user_id}",
                    context="AUTH",
                )
                cls.logout(page)
                return False

        return True

    @classmethod
    def is_authenticated(cls, page: ft.Page) -> bool:
        """Return True when the current Flet session is authenticated and active."""
        session = cls._get_session(page)
        if cls._session_get(session, "authenticated") is not True:
            return False
        if cls.check_session_timeout(page):
            return False
        if not cls.validate_session_state(page):
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
        sec_ver = cls._session_get(session, "security_version")
        sec_stamp = cls._session_get(session, "security_stamp")
        SecurityContext.set_current_user(
            cls._session_get(session, "user_id"),
            cls._session_get(session, "username"),
            cls._session_get(session, "role"),
            sec_ver,
            sec_stamp,
        )
        return False
