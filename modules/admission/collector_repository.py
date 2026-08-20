# modules/admission/collector_repository.py

from __future__ import annotations
from typing import Any, Optional
from core.database.repository import BaseRepository

__all__ = ["PaymentCollectorRepository"]


class PaymentCollectorRepository(BaseRepository):
    """Persistence for payment collectors."""

    def get_active_collectors(self) -> list[dict[str, Any]]:
        sql = "SELECT * FROM payment_collectors WHERE is_active = 1 ORDER BY name ASC;"
        return self.execute_fetchall(sql)

    def get_all(self) -> list[dict[str, Any]]:
        sql = "SELECT * FROM payment_collectors ORDER BY name ASC;"
        return self.execute_fetchall(sql)

    def get_by_id(self, collector_id: int) -> Optional[dict[str, Any]]:
        sql = "SELECT * FROM payment_collectors WHERE id = ? LIMIT 1;"
        return self.execute_fetchone(sql, (collector_id,))

    def insert(self, name: str, role_title: Optional[str] = None) -> int:
        sql = "INSERT INTO payment_collectors (name, role_title, is_active) VALUES (?, ?, 1);"
        return self.execute_insert(sql, (name.strip(), role_title.strip() if role_title else None))

    def update(self, collector_id: int, name: str, role_title: Optional[str] = None, is_active: bool = True) -> int:
        sql = """
            UPDATE payment_collectors
            SET name = ?, role_title = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?;
        """
        return self.execute(sql, (name.strip(), role_title.strip() if role_title else None, 1 if is_active else 0, collector_id))
