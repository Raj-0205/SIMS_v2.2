# modules/admission/activity_log_repository.py

from __future__ import annotations
from typing import Any, Optional
from contextlib import contextmanager
from core.database.repository import BaseRepository
from core.database.transaction import TransactionManager

__all__ = ["ActivityLogRepository"]


@contextmanager
def _transaction():
    """Ensures repository calls succeed even if an external transaction is not already active."""
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


class ActivityLogRepository(BaseRepository):
    """Audit trail persistence for all ERP actions."""

    def insert(
        self,
        entity_type: str,
        entity_id: int,
        action: str,
        actor_name: str = "SYSTEM",
        actor_id: Optional[int] = None,
        details: Optional[str] = None,
    ) -> int:
        with _transaction():
            sql = """
                INSERT INTO activity_logs (entity_type, entity_id, action, actor_name, actor_id, details)
                VALUES (?, ?, ?, ?, ?, ?);
            """
            return self.execute_insert(sql, (entity_type.upper(), entity_id, action.upper(), actor_name, actor_id, details))

    def get_logs_for_entity(self, entity_type: str, entity_id: int, limit: int = 50) -> list[dict[str, Any]]:
        with _transaction():
            sql = """
                SELECT * FROM activity_logs
                WHERE entity_type = ? AND entity_id = ?
                ORDER BY created_at DESC
                LIMIT ?;
            """
            return self.execute_fetchall(sql, (entity_type.upper(), entity_id, limit))

    def get_recent_logs(self, limit: int = 50) -> list[dict[str, Any]]:
        with _transaction():
            sql = "SELECT * FROM activity_logs ORDER BY created_at DESC LIMIT ?;"
            return self.execute_fetchall(sql, (limit,))

    def get_today_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        """Retrieves actions performed during the current day."""
        with _transaction():
            sql = """
                SELECT * FROM activity_logs
                WHERE date(created_at, 'localtime') = date('now', 'localtime')
                   OR date(created_at) = date('now')
                ORDER BY created_at DESC
                LIMIT ?;
            """
            return self.execute_fetchall(sql, (limit,))

    def get_today_count(self) -> int:
        """Returns the number of actions performed today."""
        with _transaction():
            sql = """
                SELECT COUNT(*) as cnt FROM activity_logs
                WHERE date(created_at, 'localtime') = date('now', 'localtime')
                   OR date(created_at) = date('now');
            """
            row = self.execute_fetchone(sql, ())
            return row["cnt"] if row and "cnt" in row else 0

