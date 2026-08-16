# core/security/auth.py

import flet as ft
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from core.database.transaction import TransactionManager
from core.logger.service import LogService
from modules.users.repository import UserRepository

__all__ = ["AuthService"]


class AuthService:
    """
    Authentication and password-security service.

    Responsibilities:
    - Argon2id password hashing and verification.
    - User credential authentication.
    - Transient per-session authentication state.

    Router protection and login UI wiring are intentionally deferred
    to the next batch.
    """

    _password_hasher = PasswordHasher()

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
        except VerifyMismatchError:
            return False

    @classmethod
    def authenticate(
        cls,
        username: str,
        password: str,
    ) -> dict[str, object] | None:
        """
        Authenticate a user.

        Returns:
            User dictionary on successful authentication.
            None when credentials are invalid.

        Infrastructure/database errors are deliberately propagated.
        """
        normalized_username = username.strip()

        if not normalized_username or not password:
            LogService.warning(
                "Authentication rejected because credentials were incomplete.",
                context="AUTH",
            )
            return None

        TransactionManager.begin()

        try:
            repository = UserRepository()
            user = repository.get_by_username(normalized_username)
            TransactionManager.commit()
        except Exception:
            if TransactionManager.in_transaction():
                TransactionManager.rollback()
            raise

        if not user:
            LogService.warning(
                f"Failed authentication attempt for username: '{normalized_username}'.",
                context="AUTH",
            )
            return None

        if not bool(user["is_active"]):
            LogService.warning(
                f"Authentication rejected for inactive user: '{normalized_username}'.",
                context="AUTH",
            )
            return None

        stored_hash = str(user["password_hash"])

        if not cls.verify_password(stored_hash, password):
            LogService.warning(
                f"Failed authentication attempt for username: '{normalized_username}'.",
                context="AUTH",
            )
            return None

        if cls._password_hasher.check_needs_rehash(stored_hash):
            LogService.warning(
                f"Password rehash recommended for user '{normalized_username}'.",
                context="AUTH",
            )

        LogService.info(
            f"User '{normalized_username}' authenticated successfully.",
            context="AUTH",
        )

        return user

    @classmethod
    def login(cls, page: ft.Page, user: dict[str, object]) -> None:
        """Store authenticated state in the current transient Flet session."""
        session = page.session.store

        session.set("authenticated", True)
        session.set("user_id", user["id"])
        session.set("username", user["username"])
        session.set("role", user["role"])

        LogService.info(
            f"Session started for user '{user['username']}'.",
            context="AUTH",
        )

    @classmethod
    def logout(cls, page: ft.Page) -> None:
        """Clear the current transient authentication session."""
        page.session.store.clear()

        LogService.info(
            "Authentication session cleared.",
            context="AUTH",
        )

    @classmethod
    def is_authenticated(cls, page: ft.Page) -> bool:
        """Return True when the current Flet session is authenticated."""
        return page.session.store.get("authenticated") is True
