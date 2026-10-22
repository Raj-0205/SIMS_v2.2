# core/security/audit.py

from __future__ import annotations
from typing import Any, Optional
from contextlib import contextmanager
from core.database.repository import BaseRepository
from core.database.transaction import TransactionManager
from core.security.authorization import AuthorizationService
from core.security.permissions import SecurityPermission

__all__ = ["SecurityAuditRepository"]


@contextmanager
def _transaction():
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


class SecurityAuditRepository(BaseRepository):
    """
    Dedicated security audit repository utilizing the existing activity_logs infrastructure.
    Guarantees architectural independence of core security from domain modules.
    """

    def insert(
        self,
        entity_id: int = 0,
        action: str = "",
        actor_name: str = "SYSTEM",
        actor_id: Optional[int] = None,
        details: Optional[str] = None,
        entity_type: str = "SECURITY",
    ) -> int:
        """Record an immutable security event."""
        with _transaction():
            sql = """
                INSERT INTO activity_logs (entity_type, entity_id, action, actor_name, actor_id, details)
                VALUES (?, ?, ?, ?, ?, ?);
            """
            return self.execute_insert(
                sql,
                (entity_type.upper(), entity_id, action.upper(), actor_name, actor_id, details),
            )

    def get_recent_security_logs(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve recent security audit entries."""
        AuthorizationService.enforce(SecurityPermission.SECURITY_AUDIT_VIEW)
        with _transaction():
            sql = """
                SELECT * FROM activity_logs
                WHERE entity_type = 'SECURITY'
                ORDER BY created_at DESC
                LIMIT ?;
            """
            return self.execute_fetchall(sql, (limit,))
