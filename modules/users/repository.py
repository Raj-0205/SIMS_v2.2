# modules/users/repository.py

from __future__ import annotations
from typing import Any
from datetime import datetime, timezone, timedelta

from core.database.repository import BaseRepository

__all__ = ["UserRepository"]


class UserRepository(BaseRepository):
    """Data access layer for user and authentication entities."""

    def get_by_username(self, username: str) -> dict[str, Any] | None:
        """Fetch a user by exact username."""
        return self.execute_fetchone(
            """
            SELECT
                id,
                username,
                password_hash,
                role,
                email,
                is_active,
                failed_login_attempts,
                locked_until,
                created_at,
                updated_at
            FROM users
            WHERE username = ?;
            """,
            (username,),
        )

    def get_by_id(self, user_id: int) -> dict[str, Any] | None:
        """Fetch a user by primary key."""
        return self.execute_fetchone(
            """
            SELECT
                id,
                username,
                password_hash,
                role,
                email,
                is_active,
                failed_login_attempts,
                locked_until,
                created_at,
                updated_at
            FROM users
            WHERE id = ?;
            """,
            (user_id,),
        )

    def get_by_email(self, email: str) -> dict[str, Any] | None:
        """Fetch a user by exact email."""
        return self.execute_fetchone(
            """
            SELECT
                id,
                username,
                password_hash,
                role,
                email,
                is_active,
                failed_login_attempts,
                locked_until,
                created_at,
                updated_at
            FROM users
            WHERE email = ?;
            """,
            (email.strip(),),
        )

    def create_user(
        self,
        username: str,
        password_hash: str,
        role: str = "ADMIN",
        email: str | None = None,
    ) -> int:
        """Create a user and return its generated primary key."""
        return self.execute_insert(
            """
            INSERT INTO users (
                username,
                password_hash,
                role,
                email
            )
            VALUES (?, ?, ?, ?);
            """,
            (username.strip(), password_hash, role, email.strip() if email else None),
        )

    def record_failed_login(
        self,
        user_id: int,
        max_attempts: int = 5,
        lockout_minutes: int = 15,
    ) -> int:
        """
        Increments failed_login_attempts. If threshold is reached, locks the account.
        Returns the new failed attempt count.
        """
        user = self.get_by_id(user_id)
        if not user:
            return 0
        new_attempts = int(user.get("failed_login_attempts") or 0) + 1
        now_utc = datetime.now(timezone.utc)
        locked_until_str = None
        if new_attempts >= max_attempts:
            locked_until_dt = now_utc + timedelta(minutes=lockout_minutes)
            locked_until_str = locked_until_dt.strftime("%Y-%m-%d %H:%M:%S")

        self.execute(
            """
            UPDATE users
            SET failed_login_attempts = ?,
                locked_until = COALESCE(?, locked_until),
                updated_at = ?
            WHERE id = ?;
            """,
            (new_attempts, locked_until_str, now_utc.strftime("%Y-%m-%d %H:%M:%S"), user_id),
        )
        return new_attempts

    def reset_failed_logins(self, user_id: int) -> None:
        """Clears failed login attempts and unlocks the account."""
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        self.execute(
            """
            UPDATE users
            SET failed_login_attempts = 0,
                locked_until = NULL,
                updated_at = ?
            WHERE id = ?;
            """,
            (now_utc, user_id),
        )

    def update_email(self, user_id: int, email: str | None) -> None:
        """Update a user's email address."""
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        self.execute(
            """
            UPDATE users
            SET email = ?,
                updated_at = ?
            WHERE id = ?;
            """,
            (email.strip() if email else None, now_utc, user_id),
        )

    def update_role(self, user_id: int, role: str) -> None:
        """Update a user's role."""
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        self.execute(
            """
            UPDATE users
            SET role = ?,
                updated_at = ?
            WHERE id = ?;
            """,
            (role, now_utc, user_id),
        )

    def update_password(self, user_id: int, password_hash: str) -> None:
        """Update a user's password hash."""
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        self.execute(
            """
            UPDATE users
            SET password_hash = ?,
                updated_at = ?
            WHERE id = ?;
            """,
            (password_hash, now_utc, user_id),
        )

    # --- OTP Challenge Operations ---

    def create_otp_challenge(
        self,
        challenge_token: str,
        user_id: int,
        otp_hash: str,
        expires_at: str,
        max_attempts: int = 3,
    ) -> int:
        """Persist a new OTP challenge token."""
        return self.execute_insert(
            """
            INSERT INTO auth_otp_challenges (
                challenge_token,
                user_id,
                otp_hash,
                attempts_left,
                max_attempts,
                expires_at,
                is_consumed
            )
            VALUES (?, ?, ?, ?, ?, ?, 0);
            """,
            (challenge_token, user_id, otp_hash, max_attempts, max_attempts, expires_at),
        )

    def get_otp_challenge(self, challenge_token: str) -> dict[str, Any] | None:
        """Retrieve an OTP challenge by token."""
        return self.execute_fetchone(
            """
            SELECT
                id,
                challenge_token,
                user_id,
                otp_hash,
                attempts_left,
                max_attempts,
                expires_at,
                is_consumed,
                consumed_at,
                created_at
            FROM auth_otp_challenges
            WHERE challenge_token = ?;
            """,
            (challenge_token,),
        )

    def decrement_otp_attempts(self, challenge_id: int) -> int:
        """Decrement attempts_left by 1. Returns remaining attempts."""
        self.execute(
            """
            UPDATE auth_otp_challenges
            SET attempts_left = MAX(0, attempts_left - 1)
            WHERE id = ?;
            """,
            (challenge_id,),
        )
        row = self.execute_fetchone(
            "SELECT attempts_left FROM auth_otp_challenges WHERE id = ?;",
            (challenge_id,),
        )
        return int(row["attempts_left"]) if row else 0

    def mark_otp_consumed(self, challenge_id: int) -> None:
        """Mark an OTP challenge as consumed."""
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        self.execute(
            """
            UPDATE auth_otp_challenges
            SET is_consumed = 1,
                consumed_at = ?
            WHERE id = ?;
            """,
            (now_utc, challenge_id),
        )

    def invalidate_pending_challenges_for_user(self, user_id: int) -> None:
        """Invalidate all unconsumed OTP challenges for a user when resending."""
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        self.execute(
            """
            UPDATE auth_otp_challenges
            SET is_consumed = 1,
                consumed_at = ?
            WHERE user_id = ? AND is_consumed = 0;
            """,
            (now_utc, user_id),
        )
