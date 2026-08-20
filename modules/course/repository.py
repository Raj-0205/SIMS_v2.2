# modules/course/repository.py

from __future__ import annotations
from typing import Any, Mapping, Optional, TypedDict, cast

from core.database.repository import BaseRepository

__all__ = ["CourseRepository", "CourseSearchRow"]


class CourseSearchRow(TypedDict):
    """Strict typing for search results returned from the database."""
    id: int
    code: str
    name: str
    status: str


class CourseRepository(BaseRepository):
    """
    Handles database interactions for the Course entity.
    STRICT RULE: Pure SQL execution. Parameterized queries only.
    """

    _SELECT_FIELDS = """
        id,
        code,
        name,
        status,
        base_fee,
        duration,
        category,
        description,
        created_at,
        updated_at
    """

    def create(self, data: Mapping[str, Any]) -> int:
        """Inserts a new course record and returns its generated ID."""
        sql = """
            INSERT INTO courses (
                code, name, status, base_fee, duration, category, description
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """
        params = (
            data["code"],
            data["name"],
            data.get("status", "ACTIVE"),
            data.get("base_fee", 0.0),
            data.get("duration"),
            data.get("category", "General"),
            data.get("description"),
        )
        return self.execute_insert(sql, params)

    def get_by_id(self, course_id: int) -> Optional[dict[str, Any]]:
        """Fetches a course by primary key."""
        sql = f"SELECT {self._SELECT_FIELDS} FROM courses WHERE id = ?;"
        return self.execute_fetchone(sql, (course_id,))

    def get_by_code(self, code: str) -> Optional[dict[str, Any]]:
        """Fetches a course by business unique code (case-insensitive in SQLite)."""
        sql = f"SELECT {self._SELECT_FIELDS} FROM courses WHERE code = ? COLLATE NOCASE;"
        return self.execute_fetchone(sql, (code,))

    def list(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
        category: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Fetches paged courses with optional status and category filters."""
        conditions: list[str] = []
        params: list[Any] = []

        if status:
            conditions.append("status = ?")
            params.append(status)

        if category:
            conditions.append("category = ? COLLATE NOCASE")
            params.append(category)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"""
            SELECT {self._SELECT_FIELDS}
            FROM courses
            {where_clause}
            ORDER BY name ASC, id ASC
            LIMIT ? OFFSET ?;
        """
        params.extend([limit, offset])
        return self.execute_fetchall(sql, params)

    def count(self, status: Optional[str] = None, category: Optional[str] = None) -> int:
        """Returns the total number of courses matching optional filters."""
        conditions: list[str] = []
        params: list[Any] = []

        if status:
            conditions.append("status = ?")
            params.append(status)

        if category:
            conditions.append("category = ? COLLATE NOCASE")
            params.append(category)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT COUNT(*) AS total FROM courses {where_clause};"
        row = self.execute_fetchone(sql, params)
        return int(row["total"]) if row else 0

    def update(self, course_id: int, data: Mapping[str, Any]) -> int:
        """Updates an existing course record."""
        sql = """
            UPDATE courses
            SET
                code = ?,
                name = ?,
                status = ?,
                base_fee = ?,
                duration = ?,
                category = ?,
                description = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?;
        """
        params = (
            data["code"],
            data["name"],
            data.get("status", "ACTIVE"),
            data.get("base_fee", 0.0),
            data.get("duration"),
            data.get("category", "General"),
            data.get("description"),
            course_id,
        )
        return self.execute(sql, params)

    def delete(self, course_id: int) -> int:
        """Deletes a course by ID. Returns affected rows."""
        sql = "DELETE FROM courses WHERE id = ?;"
        return self.execute(sql, (course_id,))

    def search(
        self, query: str, limit: int = 25, active_only: bool = False
    ) -> list[CourseSearchRow]:
        """
        Searches courses by Code or Name.
        Preserves backward compatibility for admission and search flows.
        """
        search_pattern = f"%{query}%"
        status_filter = "AND status = 'ACTIVE'" if active_only else ""

        sql = f"""
            SELECT 
                id, 
                code, 
                name, 
                status
            FROM courses
            WHERE 
                (code LIKE ? OR name LIKE ?)
                {status_filter}
            ORDER BY name ASC
            LIMIT ?;
        """
        params = (search_pattern, search_pattern, limit)
        return cast(list[CourseSearchRow], self.execute_fetchall(sql, params))

    def is_code_taken(self, code: str, exclude_id: Optional[int] = None) -> bool:
        """Checks if a course code is already registered, optionally excluding a course ID."""
        sql = """
            SELECT 1 FROM courses 
            WHERE code = ? COLLATE NOCASE 
              AND (? IS NULL OR id <> ?)
            LIMIT 1;
        """
        return self.exists(sql, (code, exclude_id, exclude_id))

    def has_linked_admissions(self, course_id: int) -> bool:
        """Checks if a course has associated admission records in the bridge table."""
        sql = "SELECT 1 FROM admission_courses WHERE course_id = ? LIMIT 1;"
        return self.exists(sql, (course_id,))

    def has_linked_batches(self, course_id: int) -> bool:
        """Checks if a course has associated batches."""
        sql = "SELECT 1 FROM batches WHERE course_id = ? LIMIT 1;"
        return self.exists(sql, (course_id,))

