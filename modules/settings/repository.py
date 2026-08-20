# modules/settings/repository.py

from __future__ import annotations
from typing import Any, Optional
from core.database.repository import BaseRepository

__all__ = ["SettingsRepository"]


class SettingsRepository(BaseRepository):
    """Handles persistence for institute_settings."""

    def get(self, key: str) -> Optional[str]:
        sql = "SELECT value FROM institute_settings WHERE key = ? LIMIT 1;"
        row = self.execute_fetchone(sql, (key,))
        return str(row["value"]) if row and row["value"] is not None else None

    def get_all(self, category: Optional[str] = None) -> dict[str, str]:
        if category:
            sql = "SELECT key, value FROM institute_settings WHERE category = ?;"
            rows = self.execute_fetchall(sql, (category,))
        else:
            sql = "SELECT key, value FROM institute_settings;"
            rows = self.execute_fetchall(sql)
        return {str(row["key"]): str(row["value"]) for row in rows}

    def set(self, key: str, value: str, category: str = "GENERAL", description: Optional[str] = None) -> None:
        sql = """
            INSERT INTO institute_settings (key, value, category, description, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP;
        """
        self.execute_insert(sql, (key, value, category, description))
