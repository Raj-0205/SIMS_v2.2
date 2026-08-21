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
            s.middle_name,
            s.mother_name,
            s.dob,
            s.gender,
            s.aadhaar_number,
            s.parent_guardian_name,
            s.village,
            s.address,
            s.qualification,
            s.blood_group,
            s.photo_path,
            s.signature_path,
            s.email,
            s.mobile_number,
            s.created_at,
            s.updated_at,
            (SELECT COUNT(*) FROM admissions a WHERE a.student_id = s.id) AS admissions_count,
            (
                SELECT c.id
                FROM admissions a
                JOIN admission_courses ac ON ac.admission_id = a.id
                JOIN courses c ON c.id = ac.course_id
                WHERE a.student_id = s.id
                ORDER BY a.id DESC
                LIMIT 1
            ) AS latest_course_id,
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
                SELECT c.base_fee
                FROM admissions a
                JOIN admission_courses ac ON ac.admission_id = a.id
                JOIN courses c ON c.id = ac.course_id
                WHERE a.student_id = s.id
                ORDER BY a.id DESC
                LIMIT 1
            ) AS latest_course_base_fee,
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
        - Admission ID / Candidate Number (YYYY-NNN format or raw sequence)
        - Mobile Number (including normalized digits & international formats)
        - Email Address
        """
        clean = query.strip()
        if not clean:
            return "", []

        prefix = f"{table_alias}." if table_alias else ""
        student_id_ref = f"{prefix}id" if prefix else "id"

        # Check for Candidate Number format: YYYY-NNN (e.g. 2026-001 or 2026-1)
        cand_match = re.match(r"^(\d{4})-(\d{1,4})$", clean)
        if cand_match:
            year = int(cand_match.group(1))
            seq = int(cand_match.group(2))
            cand_pattern = f"%{clean}%"
            where = f"""(
                EXISTS (
                    SELECT 1 FROM admissions a_cand
                    WHERE a_cand.student_id = {student_id_ref}
                      AND (
                          (a_cand.candidate_year = ? AND a_cand.candidate_sequence = ?)
                          OR PRINTF('%04d-%03d', a_cand.candidate_year, a_cand.candidate_sequence) LIKE ?
                      )
                )
                OR CAST({prefix}id AS TEXT) LIKE ?
            )"""
            return where, [year, seq, cand_pattern, cand_pattern]

        # Check if entire query is primarily a phone candidate (only digits, spaces, plus, minus, parens, and length >= 8)
        clean_no_phone_chars = re.sub(r"[\s\+\-\(\)]", "", clean)
        if clean_no_phone_chars.isdigit() and len(clean_no_phone_chars) >= 8 and "-" not in clean:
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
                {prefix}email LIKE ? OR
                EXISTS (
                    SELECT 1 FROM admissions a_tok
                    WHERE a_tok.student_id = {student_id_ref}
                      AND (
                          PRINTF('%04d-%03d', a_tok.candidate_year, a_tok.candidate_sequence) LIKE ?
                          OR CAST(a_tok.candidate_year AS TEXT) LIKE ?
                          OR CAST(a_tok.id AS TEXT) LIKE ?
                      )
                )
            """
            token_params = [
                token_pattern,
                token_pattern,
                token_pattern,
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

    @classmethod
    def _build_filter_conditions(
        cls,
        query: Optional[str] = None,
        course_id: Optional[int] = None,
        status: Optional[str] = None,
        year: Optional[int] = None,
        month: Optional[int] = None,
        table_alias: str = "s",
    ) -> tuple[str, list[Any]]:
        """
        Builds dynamic parameterized WHERE clauses combining search, course, status, year, and month filters.
        """
        clauses: list[str] = []
        params: list[Any] = []

        # 1. Search Query
        if query and query.strip():
            search_clause, search_params = cls._build_search_conditions(query.strip(), table_alias=table_alias)
            if search_clause:
                clauses.append(f"({search_clause})")
                params.extend(search_params)

        # 2. Course Filter
        if course_id is not None and int(course_id) > 0:
            clauses.append(f"""EXISTS (
                SELECT 1 FROM admissions a_cf
                JOIN admission_courses ac_cf ON ac_cf.admission_id = a_cf.id
                WHERE a_cf.student_id = {table_alias}.id AND ac_cf.course_id = ?
            )""")
            params.append(int(course_id))

        # 3. Status Filter (DRAFT, REGISTERED, CONFIRMED, CANCELLED, COMPLETED)
        if status and status.strip() and status.strip().upper() != "ALL":
            clean_status = status.strip().upper()
            if clean_status == "REGISTERED":
                clauses.append(f"""(
                    EXISTS (
                        SELECT 1 FROM admissions a_sf
                        WHERE a_sf.student_id = {table_alias}.id AND a_sf.status = 'REGISTERED'
                    )
                    OR NOT EXISTS (
                        SELECT 1 FROM admissions a_any
                        WHERE a_any.student_id = {table_alias}.id
                    )
                )""")
            else:
                clauses.append(f"""EXISTS (
                    SELECT 1 FROM admissions a_sf
                    WHERE a_sf.student_id = {table_alias}.id AND a_sf.status = ?
                )""")
                params.append(clean_status)

        # 4. Year and Month Filters
        # For admitted students: filters against admission dates / candidate year.
        # For purely registered students (no admissions): filters against student registration date.
        if year is not None and int(year) > 0 and month is not None and 1 <= int(month) <= 12:
            year_int = int(year)
            month_int = int(month)
            clauses.append(f"""(
                EXISTS (
                    SELECT 1 FROM admissions a_ymf
                    WHERE a_ymf.student_id = {table_alias}.id 
                      AND (a_ymf.candidate_year = ? OR CAST(strftime('%Y', a_ymf.created_at) AS INTEGER) = ?)
                      AND CAST(strftime('%m', a_ymf.created_at) AS INTEGER) = ?
                )
                OR (
                    NOT EXISTS (SELECT 1 FROM admissions a_none WHERE a_none.student_id = {table_alias}.id)
                    AND CAST(strftime('%Y', {table_alias}.created_at) AS INTEGER) = ?
                    AND CAST(strftime('%m', {table_alias}.created_at) AS INTEGER) = ?
                )
            )""")
            params.extend([year_int, year_int, month_int, year_int, month_int])
        elif year is not None and int(year) > 0:
            year_int = int(year)
            clauses.append(f"""(
                EXISTS (
                    SELECT 1 FROM admissions a_yf
                    WHERE a_yf.student_id = {table_alias}.id 
                      AND (a_yf.candidate_year = ? OR CAST(strftime('%Y', a_yf.created_at) AS INTEGER) = ?)
                )
                OR (
                    NOT EXISTS (SELECT 1 FROM admissions a_none WHERE a_none.student_id = {table_alias}.id)
                    AND CAST(strftime('%Y', {table_alias}.created_at) AS INTEGER) = ?
                )
            )""")
            params.extend([year_int, year_int, year_int])
        elif month is not None and 1 <= int(month) <= 12:
            month_int = int(month)
            clauses.append(f"""(
                EXISTS (
                    SELECT 1 FROM admissions a_mf
                    WHERE a_mf.student_id = {table_alias}.id 
                      AND CAST(strftime('%m', a_mf.created_at) AS INTEGER) = ?
                )
                OR (
                    NOT EXISTS (SELECT 1 FROM admissions a_none WHERE a_none.student_id = {table_alias}.id)
                    AND CAST(strftime('%m', {table_alias}.created_at) AS INTEGER) = ?
                )
            )""")
            params.extend([month_int, month_int])

        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return where_clause, params

    # Whitelist of allowed sort fields → SQL expression fragments.
    # Strictly valid sorting criteria. Year and Month are filters, not sorts.
    _SORT_FIELD_MAP: dict[str, str | list[str]] = {
        "id": "s.id",
        "student_id": "s.id",
        "name": ["s.first_name", "s.last_name"],
        "student_name": ["s.first_name", "s.last_name"],
        "admission_id": ["latest_admission_year", "latest_admission_seq", "latest_admission_id"],
        "candidate_number": ["latest_admission_year", "latest_admission_seq", "latest_admission_id"],
        "mobile": "s.mobile_number",
        "mobile_number": "s.mobile_number",
        "course": "latest_course_name",
        "date": ["latest_admission_date", "s.created_at"],
        "admission_date": ["latest_admission_date", "s.created_at"],
        "registration_date": "s.created_at",
        "status": "latest_admission_status",
        "fee": "latest_course_base_fee",
    }

    @classmethod
    def _build_order_by(cls, sort_by: str = "id", sort_dir: str = "desc") -> str:
        """Constructs database-level ORDER BY clause from a single sort field."""
        return cls._build_multi_order_by([(sort_by, sort_dir)])

    @classmethod
    def _build_multi_order_by(cls, sort_keys: list[tuple[str, str]] | None = None) -> str:
        """
        Constructs database-level ORDER BY from one or more (field, direction) pairs.
        Every field is validated against the _SORT_FIELD_MAP whitelist.
        Adds a final stable tie-breaker ', s.id ASC' unless ID is already sorted.
        """
        if not sort_keys:
            return "ORDER BY s.id DESC"

        clauses: list[str] = []
        has_id_sort = False

        for field, direction in sort_keys:
            clean_field = str(field).lower().strip()
            dir_str = "ASC" if str(direction).lower() == "asc" else "DESC"

            if clean_field in ("id", "student_id"):
                has_id_sort = True

            mapping = cls._SORT_FIELD_MAP.get(clean_field)
            if mapping is None:
                continue  # Skip unknown fields silently

            if isinstance(mapping, list):
                for expr in mapping:
                    clauses.append(f"{expr} {dir_str}")
            else:
                clauses.append(f"{mapping} {dir_str}")

        if not clauses:
            return "ORDER BY s.id DESC"

        # Add deterministic stable tie-breaker if not already present
        if not has_id_sort:
            clauses.append("s.id ASC")

        return f"ORDER BY {', '.join(clauses)}"

    def filter_paged(
        self,
        query: Optional[str] = None,
        course_id: Optional[int] = None,
        status: Optional[str] = None,
        year: Optional[int] = None,
        month: Optional[int] = None,
        sort_by: str = "id",
        sort_dir: str = "desc",
        sort_keys: list[tuple[str, str]] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Executes an indexed, multi-criteria filtered search with database-level sorting and pagination.
        sort_keys takes precedence over sort_by/sort_dir when provided.
        """
        where_clause, params = self._build_filter_conditions(
            query=query,
            course_id=course_id,
            status=status,
            year=year,
            month=month,
            table_alias="s",
        )
        if sort_keys:
            order_by = self._build_multi_order_by(sort_keys)
        else:
            order_by = self._build_order_by(sort_by=sort_by, sort_dir=sort_dir)

        sql = f"""
            {self._STUDENT_SELECT_BASE}
            {where_clause}
            {order_by}
            LIMIT ? OFFSET ?;
        """
        params.extend([limit, offset])
        return self.execute_fetchall(sql, tuple(params))

    def count_filtered(
        self,
        query: Optional[str] = None,
        course_id: Optional[int] = None,
        status: Optional[str] = None,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> int:
        """Returns total matching records for the active filter set."""
        where_clause, params = self._build_filter_conditions(
            query=query,
            course_id=course_id,
            status=status,
            year=year,
            month=month,
            table_alias="s",
        )
        sql = f"SELECT COUNT(*) as count FROM students s {where_clause};"
        row = self.execute_fetchone(sql, tuple(params))
        return int(row["count"]) if row else 0

    def get_all_filtered(
        self,
        query: Optional[str] = None,
        course_id: Optional[int] = None,
        status: Optional[str] = None,
        year: Optional[int] = None,
        month: Optional[int] = None,
        sort_by: str = "id",
        sort_dir: str = "desc",
        sort_keys: list[tuple[str, str]] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Returns all matching filtered records without limit for full dataset exports (Excel/PDF).
        sort_keys takes precedence over sort_by/sort_dir when provided.
        """
        where_clause, params = self._build_filter_conditions(
            query=query,
            course_id=course_id,
            status=status,
            year=year,
            month=month,
            table_alias="s",
        )
        if sort_keys:
            order_by = self._build_multi_order_by(sort_keys)
        else:
            order_by = self._build_order_by(sort_by=sort_by, sort_dir=sort_dir)

        sql = f"""
            {self._STUDENT_SELECT_BASE}
            {where_clause}
            {order_by};
        """
        return self.execute_fetchall(sql, tuple(params))

    def get_all_paged(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        """Fetches paginated student records ordered by newest first with latest admission summary."""
        return self.filter_paged(limit=limit, offset=offset)

    def count_all(self) -> int:
        """Returns the total number of students."""
        sql = "SELECT COUNT(*) as count FROM students;"
        row = self.execute_fetchone(sql)
        return int(row["count"]) if row else 0

    def search_paged(self, query: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        """
        Universal tokenized search across ID, first name, last name, full name, mobile, and email with pagination.
        """
        return self.filter_paged(query=query, limit=limit, offset=offset)

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
                COALESCE(a.agreed_fee, 0.0) AS agreed_fee,
                COALESCE(a.discount, 0.0) AS discount,
                a.batch_id,
                b.batch_name,
                b.timing AS batch_timing,
                c.id AS course_id,
                c.code AS course_code,
                c.name AS course_name
            FROM admissions a
            LEFT JOIN admission_courses ac ON ac.admission_id = a.id
            LEFT JOIN courses c ON c.id = ac.course_id
            LEFT JOIN batches b ON b.id = a.batch_id
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
