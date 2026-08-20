# modules/admission/activity_log_repository.py

from __future__ import annotations
from typing import Any, Optional
from core.database.repository import BaseRepository

__all__ = ["ActivityLogRepository"]


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
        sql = """
            INSERT INTO activity_logs (entity_type, entity_id, action, actor_name, actor_id, details)
            VALUES (?, ?, ?, ?, ?, ?);
        """
        return self.execute_insert(sql, (entity_type.upper(), entity_id, action.upper(), actor_name, actor_id, details))

    def get_logs_for_entity(self, entity_type: str, entity_id: int, limit: int = 50) -> list[dict[str, Any]]:
        sql = """
            SELECT * FROM activity_logs
            WHERE entity_type = ? AND entity_id = ?
            ORDER BY created_at DESC
            LIMIT ?;
        """
        return self.execute_fetchall(sql, (entity_type.upper(), entity_id, limit))

    def get_recent_logs(self, limit: int = 50) -> list[dict[str, Any]]:
        sql = "SELECT * FROM activity_logs ORDER BY created_at DESC LIMIT ?;"
        return self.execute_fetchall(sql, (limit,))
