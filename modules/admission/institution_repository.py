# modules/admission/institution_repository.py

from __future__ import annotations
from typing import Any, Optional
from core.database.repository import BaseRepository

__all__ = ["EducationalInstitutionRepository"]


class EducationalInstitutionRepository(BaseRepository):
    """Persistence for educational institutions (schools and colleges)."""

    def get_active_institutions(self) -> list[dict[str, Any]]:
        sql = "SELECT * FROM educational_institutions WHERE is_active = 1 ORDER BY name ASC;"
        return self.execute_fetchall(sql)

    def get_all(self) -> list[dict[str, Any]]:
        sql = "SELECT * FROM educational_institutions ORDER BY name ASC;"
        return self.execute_fetchall(sql)

    def get_by_id(self, inst_id: int) -> Optional[dict[str, Any]]:
        sql = "SELECT * FROM educational_institutions WHERE id = ? LIMIT 1;"
        return self.execute_fetchone(sql, (inst_id,))

    def get_by_name(self, name: str) -> Optional[dict[str, Any]]:
        sql = "SELECT * FROM educational_institutions WHERE LOWER(name) = LOWER(?) LIMIT 1;"
        return self.execute_fetchone(sql, (name.strip(),))

    def insert(self, name: str, institution_type: str = "COLLEGE", address: Optional[str] = None) -> int:
        sql = """
            INSERT INTO educational_institutions (name, institution_type, address, is_active)
            VALUES (?, ?, ?, 1);
        """
        return self.execute_insert(sql, (name.strip(), institution_type.upper(), address.strip() if address else None))

    def update(self, inst_id: int, name: str, institution_type: str, address: Optional[str] = None, is_active: bool = True) -> int:
        sql = """
            UPDATE educational_institutions
            SET name = ?, institution_type = ?, address = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?;
        """
        return self.execute(sql, (name.strip(), institution_type.upper(), address.strip() if address else None, 1 if is_active else 0, inst_id))
