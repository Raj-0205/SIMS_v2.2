# modules/student/repository.py

from __future__ import annotations
from typing import Any, Optional, TypedDict, cast

from core.database.repository import BaseRepository

__all__ = ["StudentRepository", "StudentRow", "StudentSearchRow"]


class StudentSearchRow(TypedDict):
    """Strict typing for search results returned from the database."""
    id: int
    first_name: str
    last_name: str
    mobile_number: Optional[str]


class StudentRow(TypedDict):
    """Strict typing for full student record returned from the database."""
    id: int
    first_name: str
    last_name: str
    email: Optional[str]
    mobile_number: Optional[str]
    created_at: str


class StudentRepository(BaseRepository):
    """
    Handles all database interactions for the Student entity.
    STRICT RULE: Pure SQL execution. No business logic.
    """

    _STUDENT_SELECT_BASE = """
        SELECT
            s.id,
            s.first_name,
            s.last_name,
            s.email,
            s.mobile_number,
            s.created_at,
            (SELECT COUNT(*) FROM admissions a WHERE a.student_id = s.id) AS admissions_count,
            (
                SELECT c.name
                FROM admissions a
                JOIN admission_courses ac ON ac.admission_id = a.id
                JOIN courses c ON c.id = ac.course_id
                WHERE a.student_id = s.id
                ORDER BY a.id DESC
                LIMIT 1
            ) AS latest_course_name,
            (
                SELECT a.id
                FROM admissions a
                WHERE a.student_id = s.id
                ORDER BY a.id DESC
                LIMIT 1
            ) AS latest_admission_id,
            (
                SELECT a.status
                FROM admissions a
                WHERE a.student_id = s.id
                ORDER BY a.id DESC
                LIMIT 1
            ) AS latest_admission_status,
            (
                SELECT a.created_at
                FROM admissions a
                WHERE a.student_id = s.id
                ORDER BY a.id DESC
                LIMIT 1
            ) AS latest_admission_date
        FROM students s
    """

    def insert(self, data: dict[str, Any]) -> int:
        """Inserts a new student record and returns the generated ID."""
        sql = """
            INSERT INTO students (first_name, last_name, email, mobile_number)
            VALUES (?, ?, ?, ?);
        """
        params = (
            data["first_name"],
            data["last_name"],
            data.get("email"),
            data.get("mobile_number"),
        )
        return self.execute_insert(sql, params)

    def get_by_id(self, student_id: int) -> Optional[dict[str, Any]]:
        """Retrieves a single student record with admission summary by Primary Key."""
        sql = f"""
            {self._STUDENT_SELECT_BASE}
            WHERE s.id = ?;
        """
        return self.execute_fetchone(sql, (student_id,))

    def get_by_mobile(self, mobile_number: str) -> Optional[dict[str, Any]]:
        """Retrieves a student record matching the mobile number."""
        sql = """
            SELECT id, first_name, last_name, email, mobile_number, created_at
            FROM students
            WHERE mobile_number = ?
            LIMIT 1;
        """
        return self.execute_fetchone(sql, (mobile_number,))

    def get_by_email(self, email: str) -> Optional[dict[str, Any]]:
        """Retrieves a student record matching the email address."""
        sql = """
            SELECT id, first_name, last_name, email, mobile_number, created_at
            FROM students
            WHERE email = ?
            LIMIT 1;
        """
        return self.execute_fetchone(sql, (email,))

    def get_all_paged(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        """Fetches paginated student records ordered by newest first with latest admission summary."""
        sql = f"""
            {self._STUDENT_SELECT_BASE}
            ORDER BY s.id DESC
            LIMIT ? OFFSET ?;
        """
        return self.execute_fetchall(sql, (limit, offset))

    def count_all(self) -> int:
        """Returns the total number of students."""
        sql = "SELECT COUNT(*) as count FROM students;"
        row = self.execute_fetchone(sql)
        return int(row["count"]) if row else 0

    def search_paged(self, query: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        """
        Searches students across ID, first name, last name, mobile, and email with pagination.
        """
        search_pattern = f"%{query}%"
        sql = f"""
            {self._STUDENT_SELECT_BASE}
            WHERE
                CAST(s.id AS TEXT) LIKE ? OR
                s.first_name LIKE ? OR
                s.last_name LIKE ? OR
                s.mobile_number LIKE ? OR
                s.email LIKE ?
            ORDER BY s.id DESC
            LIMIT ? OFFSET ?;
        """
        params = (
            search_pattern,
            search_pattern,
            search_pattern,
            search_pattern,
            search_pattern,
            limit,
            offset,
        )
        return self.execute_fetchall(sql, params)

    def count_search(self, query: str) -> int:
        """Counts total matching records for a given search query."""
        search_pattern = f"%{query}%"
        sql = """
            SELECT COUNT(*) as count
            FROM students
            WHERE
                CAST(id AS TEXT) LIKE ? OR
                first_name LIKE ? OR
                last_name LIKE ? OR
                mobile_number LIKE ? OR
                email LIKE ?;
        """
        params = (
            search_pattern,
            search_pattern,
            search_pattern,
            search_pattern,
            search_pattern,
        )
        row = self.execute_fetchone(sql, params)
        return int(row["count"]) if row else 0

    def update(self, student_id: int, data: dict[str, Any]) -> int:
        """Updates an existing student record and returns affected rows count."""
        sql = """
            UPDATE students
            SET first_name = ?, last_name = ?, email = ?, mobile_number = ?
            WHERE id = ?;
        """
        params = (
            data["first_name"],
            data["last_name"],
            data.get("email"),
            data.get("mobile_number"),
            student_id,
        )
        return self.execute(sql, params)

    def has_admissions(self, student_id: int) -> bool:
        """Checks whether a student has any linked admission records."""
        sql = "SELECT 1 FROM admissions WHERE student_id = ? LIMIT 1;"
        return self.exists(sql, (student_id,))

    def delete(self, student_id: int) -> int:
        """Deletes a student record (only if no foreign key constraints violate)."""
        sql = "DELETE FROM students WHERE id = ?;"
        return self.execute(sql, (student_id,))

    def get_student_admissions(self, student_id: int) -> list[dict[str, Any]]:
        """
        Fetches all admissions linked to a student with course details.
        Demonstrates the Student != Admission rule (1 student, many admissions).
        """
        sql = """
            SELECT
                a.id AS admission_id,
                a.student_id,
                a.status,
                a.created_at AS admission_date,
                c.id AS course_id,
                c.code AS course_code,
                c.name AS course_name
            FROM admissions a
            LEFT JOIN admission_courses ac ON ac.admission_id = a.id
            LEFT JOIN courses c ON c.id = ac.course_id
            WHERE a.student_id = ?
            ORDER BY a.id DESC;
        """
        return self.execute_fetchall(sql, (student_id,))

    def search(self, query: str, limit: int = 25) -> list[StudentSearchRow]:
        """
        Legacy/search-helper query method for backward compatibility.
        Case-insensitive partial match.
        """
        search_pattern = f"%{query}%"
        sql = """
            SELECT
                id,
                first_name,
                last_name,
                mobile_number
            FROM students
            WHERE
                CAST(id AS TEXT) LIKE ? OR
                first_name LIKE ? OR
                last_name LIKE ? OR
                mobile_number LIKE ?
            ORDER BY first_name ASC, last_name ASC
            LIMIT ?;
        """
        params = (
            search_pattern,
            search_pattern,
            search_pattern,
            search_pattern,
            limit,
        )
        return cast(list[StudentSearchRow], self.execute_fetchall(sql, params))
