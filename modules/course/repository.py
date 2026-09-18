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
    Handles database interactions for the Course entity and fee history audit.
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
        search: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Fetches paged courses with optional status, category, and search filters."""
        conditions: list[str] = []
        params: list[Any] = []

        if status and status.upper() != "ALL":
            conditions.append("status = ?")
            params.append(status.upper())

        if category and category.upper() != "ALL":
            conditions.append("category = ? COLLATE NOCASE")
            params.append(category)

        if search and search.strip():
            p = f"%{search.strip()}%"
            conditions.append("(code LIKE ? OR name LIKE ?)")
            params.extend([p, p])

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

    def count(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
    ) -> int:
        """Returns the total number of courses matching optional filters."""
        conditions: list[str] = []
        params: list[Any] = []

        if status and status.upper() != "ALL":
            conditions.append("status = ?")
            params.append(status.upper())

        if category and category.upper() != "ALL":
            conditions.append("category = ? COLLATE NOCASE")
            params.append(category)

        if search and search.strip():
            p = f"%{search.strip()}%"
            conditions.append("(code LIKE ? OR name LIKE ?)")
            params.extend([p, p])

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

    def update_base_fee(self, course_id: int, new_fee: float) -> int:
        """Updates only the institute base fee for a course."""
        sql = """
            UPDATE courses
            SET
                base_fee = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?;
        """
        return self.execute(sql, (new_fee, course_id))

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

    def get_categories(self) -> list[str]:
        """Returns distinct non-empty category names sorted alphabetically."""
        sql = """
            SELECT DISTINCT category 
            FROM courses 
            WHERE category IS NOT NULL AND TRIM(category) <> ''
            ORDER BY category ASC;
        """
        rows = self.execute_fetchall(sql)
        return [str(r["category"]) for r in rows if r.get("category")]

    def get_operational_summary(self, course_id: int) -> dict[str, int]:
        """Returns operational summary metrics for a course."""
        sql = """
            SELECT
                (SELECT COUNT(*) FROM batches WHERE course_id = ?) AS batch_count,
                (SELECT COUNT(*) FROM batches WHERE course_id = ? AND status IN ('OPEN', 'FULL')) AS active_batch_count,
                (SELECT COUNT(*) FROM admission_courses WHERE course_id = ?) AS total_admissions_count;
        """
        row = self.execute_fetchone(sql, (course_id, course_id, course_id))
        if not row:
            return {"batch_count": 0, "active_batch_count": 0, "total_admissions_count": 0}
        return {
            "batch_count": int(row.get("batch_count") or 0),
            "active_batch_count": int(row.get("active_batch_count") or 0),
            "total_admissions_count": int(row.get("total_admissions_count") or 0),
        }

    def get_overall_summary(self) -> dict[str, int]:
        """Returns high-level KPI counts across all courses."""
        sql = """
            SELECT
                (SELECT COUNT(*) FROM courses) AS total_courses,
                (SELECT COUNT(*) FROM courses WHERE status = 'ACTIVE') AS active_courses,
                (SELECT COUNT(*) FROM courses WHERE status = 'INACTIVE') AS inactive_courses,
                (SELECT COUNT(*) FROM admission_courses) AS total_enrollments;
        """
        row = self.execute_fetchone(sql)
        if not row:
            return {
                "total_courses": 0,
                "active_courses": 0,
                "inactive_courses": 0,
                "total_enrollments": 0,
            }
        return {
            "total_courses": int(row.get("total_courses") or 0),
            "active_courses": int(row.get("active_courses") or 0),
            "inactive_courses": int(row.get("inactive_courses") or 0),
            "total_enrollments": int(row.get("total_enrollments") or 0),
        }

    def insert_fee_history(
        self,
        course_id: int,
        old_fee: float,
        new_fee: float,
        reason: str,
        changed_by_username: str,
        changed_by_user_id: Optional[int] = None,
    ) -> int:
        """Inserts an immutable record into course_fee_history."""
        sql = """
            INSERT INTO course_fee_history (
                course_id, old_fee, new_fee, reason, changed_by_username, changed_by_user_id
            ) VALUES (?, ?, ?, ?, ?, ?);
        """
        return self.execute_insert(
            sql,
            (course_id, old_fee, new_fee, reason, changed_by_username, changed_by_user_id),
        )

    def get_fee_history(self, course_id: int, limit: int = 50) -> list[dict[str, Any]]:
        """Fetches fee history records for a course ordered newest first."""
        sql = """
            SELECT id, course_id, old_fee, new_fee, changed_by_user_id, changed_by_username, reason, changed_at
            FROM course_fee_history
            WHERE course_id = ?
            ORDER BY changed_at DESC, id DESC
            LIMIT ?;
        """
        return self.execute_fetchall(sql, (course_id, limit))
