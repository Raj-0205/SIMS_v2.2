# modules/batch/repository.py

from __future__ import annotations
from typing import Any, Mapping, Optional

from core.database.repository import BaseRepository

__all__ = ["BatchRepository"]


class BatchRepository(BaseRepository):
    """
    Data Access Layer for the Batch entity.
    STRICT RULE: Pure SQL execution. Parameterized queries only.
    """

    _SELECT_FIELDS = """
        b.id,
        b.course_id,
        b.batch_name,
        b.batch_code,
        b.timing,
        b.max_capacity,
        b.status,
        b.start_date,
        b.end_date,
        b.created_at,
        b.updated_at,
        c.code AS course_code,
        c.name AS course_name
    """

    def create(self, data: Mapping[str, Any]) -> int:
        """Inserts a new batch record and returns its generated ID."""
        sql = """
            INSERT INTO batches (
                course_id, batch_name, batch_code, timing, max_capacity,
                status, start_date, end_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """
        params = (
            data["course_id"],
            data["batch_name"],
            data.get("batch_code"),
            data["timing"],
            data.get("max_capacity", 0),
            data.get("status", "OPEN"),
            data.get("start_date"),
            data.get("end_date"),
        )
        return self.execute_insert(sql, params)

    def get_by_id(self, batch_id: int) -> Optional[dict[str, Any]]:
        """Fetches a batch by primary key with course details joined."""
        sql = f"""
            SELECT {self._SELECT_FIELDS}
            FROM batches b
            JOIN courses c ON c.id = b.course_id
            WHERE b.id = ?;
        """
        return self.execute_fetchone(sql, (batch_id,))

    def list(
        self,
        limit: int = 50,
        offset: int = 0,
        course_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Fetches paginated batches with optional course and status filters."""
        conditions: list[str] = []
        params: list[Any] = []

        if course_id is not None and int(course_id) > 0:
            conditions.append("b.course_id = ?")
            params.append(int(course_id))

        if status and status.strip() and status.strip().upper() != "ALL":
            conditions.append("b.status = ?")
            params.append(status.strip().upper())

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"""
            SELECT {self._SELECT_FIELDS}
            FROM batches b
            JOIN courses c ON c.id = b.course_id
            {where_clause}
            ORDER BY c.name ASC, b.batch_name ASC, b.id ASC
            LIMIT ? OFFSET ?;
        """
        params.extend([limit, offset])
        return self.execute_fetchall(sql, params)

    def count(
        self,
        course_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> int:
        """Returns total count of batches matching optional filters."""
        conditions: list[str] = []
        params: list[Any] = []

        if course_id is not None and int(course_id) > 0:
            conditions.append("course_id = ?")
            params.append(int(course_id))

        if status and status.strip() and status.strip().upper() != "ALL":
            conditions.append("status = ?")
            params.append(status.strip().upper())

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT COUNT(*) AS total FROM batches {where_clause};"
        row = self.execute_fetchone(sql, params)
        return int(row["total"]) if row else 0

    def list_by_course(
        self,
        course_id: int,
        status: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Fetches all batches for a specific course."""
        conditions: list[str] = ["b.course_id = ?"]
        params: list[Any] = [course_id]

        if status and status.strip() and status.strip().upper() != "ALL":
            conditions.append("b.status = ?")
            params.append(status.strip().upper())

        sql = f"""
            SELECT {self._SELECT_FIELDS}
            FROM batches b
            JOIN courses c ON c.id = b.course_id
            WHERE {' AND '.join(conditions)}
            ORDER BY b.batch_name ASC, b.id ASC;
        """
        return self.execute_fetchall(sql, params)

    def update(self, batch_id: int, data: Mapping[str, Any]) -> int:
        """Updates an existing batch record."""
        sql = """
            UPDATE batches
            SET
                course_id = ?,
                batch_name = ?,
                batch_code = ?,
                timing = ?,
                max_capacity = ?,
                status = ?,
                start_date = ?,
                end_date = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?;
        """
        params = (
            data["course_id"],
            data["batch_name"],
            data.get("batch_code"),
            data["timing"],
            data.get("max_capacity", 0),
            data.get("status", "OPEN"),
            data.get("start_date"),
            data.get("end_date"),
            batch_id,
        )
        return self.execute(sql, params)

    def delete(self, batch_id: int) -> int:
        """Deletes a batch by ID. Returns affected rows."""
        sql = "DELETE FROM batches WHERE id = ?;"
        return self.execute(sql, (batch_id,))

    def is_name_taken(
        self,
        course_id: int,
        batch_name: str,
        exclude_id: Optional[int] = None,
    ) -> bool:
        """Checks if a batch name is already taken within the same course."""
        sql = """
            SELECT 1 FROM batches
            WHERE course_id = ?
              AND batch_name = ? COLLATE NOCASE
              AND (? IS NULL OR id <> ?)
            LIMIT 1;
        """
        return self.exists(sql, (course_id, batch_name, exclude_id, exclude_id))

    def course_exists(self, course_id: int) -> bool:
        """Checks if the referenced course exists."""
        sql = "SELECT 1 FROM courses WHERE id = ? LIMIT 1;"
        return self.exists(sql, (course_id,))

    def has_linked_admissions(self, batch_id: int) -> bool:
        """
        Checks if admissions or bridge tables reference this batch.
        Guarded check: inspects schema dynamically to avoid runtime errors on missing column.
        """
        try:
            cols = self.execute_fetchall("PRAGMA table_info(admissions);")
            col_names = {c["name"] for c in cols} if cols else set()
            if "batch_id" in col_names:
                return self.exists("SELECT 1 FROM admissions WHERE batch_id = ? LIMIT 1;", (batch_id,))
            return False
        except Exception:
            return False
