# modules/users/repository.py

from typing import Any

from core.database.repository import BaseRepository

__all__ = ["UserRepository"]


class UserRepository(BaseRepository):
    """Data access layer for user entities."""

    def get_by_username(self, username: str) -> dict[str, Any] | None:
        """Fetch a user by exact username."""
        return self.execute_fetchone(
            """
            SELECT
                id,
                username,
                password_hash,
                role,
                is_active
            FROM users
            WHERE username = ?;
            """,
            (username,),
        )

    def create_user(
        self,
        username: str,
        password_hash: str,
        role: str = "OPERATOR",
    ) -> int:
        """Create a user and return its generated primary key."""
        return self.execute_insert(
            """
            INSERT INTO users (
                username,
                password_hash,
                role
            )
            VALUES (?, ?, ?);
            """,
            (username, password_hash, role),
        )
