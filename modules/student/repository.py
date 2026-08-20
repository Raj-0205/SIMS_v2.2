# modules/student/repository.py

from __future__ import annotations
import re
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
                SELECT a.candidate_year
                FROM admissions a
                WHERE a.student_id = s.id
                ORDER BY a.id DESC
                LIMIT 1
            ) AS latest_admission_year,
            (
                SELECT a.candidate_sequence
                FROM admissions a
                WHERE a.student_id = s.id
                ORDER BY a.id DESC
                LIMIT 1
            ) AS latest_admission_seq,
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

    @staticmethod
    def _build_search_conditions(query: str, table_alias: str = "s") -> tuple[str, list[Any]]:
        """
        Builds robust tokenized search conditions across multiple fields:
        - First Name, Last Name, Full Name (first_name || ' ' || last_name)
        - Student ID
        - Mobile Number (including normalized digits & international formats)
        - Email Address
        """
        clean = query.strip()
        if not clean:
            return "", []

        prefix = f"{table_alias}." if table_alias else ""

        # Check if entire query is primarily a phone candidate (digits and phone formatting chars)
        clean_no_phone_chars = re.sub(r"[\s\+\-\(\)]", "", clean)
        if clean_no_phone_chars.isdigit() and len(clean_no_phone_chars) >= 4:
            phone_digits = clean_no_phone_chars
            # Normalize Indian country code (+91 / 91)
            if phone_digits.startswith("91") and len(phone_digits) == 12:
                phone_digits = phone_digits[2:]

            pattern = f"%{phone_digits}%"
            where = f"""(
                REPLACE(REPLACE(REPLACE({prefix}mobile_number, ' ', ''), '-', ''), '+', '') LIKE ? OR
                CAST({prefix}id AS TEXT) LIKE ?
            )"""
            return where, [pattern, pattern]

        # Multi-token matching
        tokens = clean.split()
        token_clauses = []
        params: list[Any] = []

        for token in tokens:
            token_pattern = f"%{token}%"
            token_digits = re.sub(r"\D", "", token)
            has_token_digits = len(token_digits) >= 4

            clause = f"""(
                CAST({prefix}id AS TEXT) LIKE ? OR
                {prefix}first_name LIKE ? OR
                {prefix}last_name LIKE ? OR
                ({prefix}first_name || ' ' || {prefix}last_name) LIKE ? OR
                {prefix}mobile_number LIKE ? OR
                {prefix}email LIKE ?
            """
            token_params = [
                token_pattern,
                token_pattern,
                token_pattern,
                token_pattern,
                token_pattern,
                token_pattern,
            ]
            if has_token_digits:
                clause += f" OR REPLACE(REPLACE(REPLACE({prefix}mobile_number, ' ', ''), '-', ''), '+', '') LIKE ?"
                token_params.append(f"%{token_digits}%")

            clause += ")"
            token_clauses.append(clause)
            params.extend(token_params)

        where_clause = " AND ".join(token_clauses)
        return where_clause, params

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
        Universal tokenized search across ID, first name, last name, full name, mobile, and email with pagination.
        """
        where_clause, params = self._build_search_conditions(query, table_alias="s")
        if not where_clause:
            return self.get_all_paged(limit, offset)

        sql = f"""
            {self._STUDENT_SELECT_BASE}
            WHERE {where_clause}
            ORDER BY s.id DESC
            LIMIT ? OFFSET ?;
        """
        params.extend([limit, offset])
        return self.execute_fetchall(sql, tuple(params))

    def count_search(self, query: str) -> int:
        """Counts total matching records for a given universal search query."""
        where_clause, params = self._build_search_conditions(query, table_alias="")
        if not where_clause:
            return self.count_all()

        sql = f"""
            SELECT COUNT(*) as count
            FROM students
            WHERE {where_clause};
        """
        row = self.execute_fetchone(sql, tuple(params))
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
        Fetches all admissions linked to a student with course details and candidate sequence numbers.
        Demonstrates the Student != Admission rule (1 student, many admissions).
        """
        sql = """
            SELECT
                a.id AS admission_id,
                a.student_id,
                a.status,
                a.created_at AS admission_date,
                a.candidate_year,
                a.candidate_sequence,
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
        Universal search helper query method for backward compatibility.
        """
        where_clause, params = self._build_search_conditions(query, table_alias="")
        if not where_clause:
            sql = """
                SELECT id, first_name, last_name, mobile_number
                FROM students
                ORDER BY first_name ASC, last_name ASC
                LIMIT ?;
            """
            return cast(list[StudentSearchRow], self.execute_fetchall(sql, (limit,)))

        sql = f"""
            SELECT id, first_name, last_name, mobile_number
            FROM students
            WHERE {where_clause}
            ORDER BY first_name ASC, last_name ASC
            LIMIT ?;
        """
        params.append(limit)
        return cast(list[StudentSearchRow], self.execute_fetchall(sql, tuple(params)))
