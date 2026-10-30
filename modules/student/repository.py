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
            s.secondary_mobile,
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
                SELECT (COALESCE(a.agreed_fee, c.base_fee) - COALESCE(a.discount, 0.0))
                FROM admissions a
                LEFT JOIN admission_courses ac ON ac.admission_id = a.id
                LEFT JOIN courses c ON c.id = ac.course_id
                WHERE a.student_id = s.id
                ORDER BY a.id DESC
                LIMIT 1
            ) AS latest_agreed_fee,
            (
                SELECT COALESCE(SUM(p.amount), 0.0)
                FROM payments p
                WHERE p.admission_id = (
                    SELECT a.id FROM admissions a WHERE a.student_id = s.id ORDER BY a.id DESC LIMIT 1
                )
            ) AS latest_paid_amount,
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
        clean = query.strip()
        if not clean:
            return "", []

        prefix = f"{table_alias}." if table_alias else ""
        student_id_ref = f"{prefix}id" if prefix else "id"

        # Pattern 1: Formatted Candidate number (e.g. 2026-001, 2026-1, 26-1)
        cand_match = re.match(r"^(\d{2,4})[-\s/](\d{1,4})$", clean)
        if cand_match:
            year = int(cand_match.group(1))
            if year < 100:
                year += 2000
            seq = int(cand_match.group(2))
            cand_pattern = f"%{year:04d}-{seq:03d}%"
            where = f"""(
                EXISTS (
                    SELECT 1 FROM admissions a_cand
                    WHERE a_cand.student_id = {student_id_ref}
                      AND (
                          (a_cand.candidate_year = ? AND a_cand.candidate_sequence = ?)
                          OR PRINTF('%04d-%03d', a_cand.candidate_year, a_cand.candidate_sequence) LIKE ?
                      )
                )
                OR CAST({prefix}id AS TEXT) = ?
            )"""
            return where, [year, seq, cand_pattern, str(seq)]

        # Pattern 2: Explicit ID search (e.g. #1, #529, ID 1, ID: 1, Student 1, STU-1, Roll 1)
        id_match = re.match(r"^(?:#|id[:\s#]*|student[:\s#]*|stu[:\s\-#]*|roll[:\s#]*)\s*(\d+)$", clean, re.IGNORECASE)
        if id_match:
            target_id = int(id_match.group(1))
            target_str = str(target_id)
            where = f"""(
                {prefix}id = ?
                OR CAST({prefix}id AS TEXT) = ?
                OR EXISTS (
                    SELECT 1 FROM admissions a_id
                    WHERE a_id.student_id = {student_id_ref}
                      AND (
                          a_id.candidate_sequence = ?
                          OR a_id.id = ?
                          OR PRINTF('%04d-%03d', a_id.candidate_year, a_id.candidate_sequence) LIKE ?
                      )
                )
            )"""
            return where, [target_id, target_str, target_id, target_id, f"%-{target_id:03d}%"]

        # Pattern 3: Pure digits
        clean_no_phone = re.sub(r"[\s\+\-\(\)]", "", clean)
        if clean_no_phone.isdigit():
            # If 8-12 digits: primarily phone number
            if len(clean_no_phone) >= 8 and len(clean_no_phone) <= 12:
                phone_digits = clean_no_phone
                if phone_digits.startswith("91") and len(phone_digits) == 12:
                    phone_digits = phone_digits[2:]
                pattern = f"%{phone_digits}%"
                where = f"""(
                    REPLACE(REPLACE(REPLACE({prefix}mobile_number, ' ', ''), '-', ''), '+', '') LIKE ?
                    OR REPLACE(REPLACE(REPLACE(COALESCE({prefix}secondary_mobile, ''), ' ', ''), '-', ''), '+', '') LIKE ?
                    OR CAST({prefix}id AS TEXT) = ?
                )"""
                return where, [pattern, pattern, clean_no_phone]

            # Short digits (1-6 digits): Student ID, candidate sequence, or name/phone token
            short_num = int(clean_no_phone)
            short_str = str(short_num)
            where = f"""(
                {prefix}id = ?
                OR CAST({prefix}id AS TEXT) = ?
                OR EXISTS (
                    SELECT 1 FROM admissions a_snum
                    WHERE a_snum.student_id = {student_id_ref}
                      AND (
                          a_snum.candidate_sequence = ?
                          OR a_snum.id = ?
                          OR PRINTF('%03d', a_snum.candidate_sequence) = ?
                          OR PRINTF('%04d-%03d', a_snum.candidate_year, a_snum.candidate_sequence) LIKE ?
                      )
                )
                OR {prefix}first_name LIKE ?
                OR {prefix}last_name LIKE ?
                OR {prefix}mobile_number LIKE ?
            )"""
            return where, [short_num, short_str, short_num, short_num, f"{short_num:03d}", f"%-{short_num:03d}%", f"%{clean}%", f"%{clean}%", f"%{clean}%"]

        # Pattern 4: General Name, Alter-Name, and Multi-token search
        sanitized = re.sub(r"[,;:\-_\/|\#]", " ", clean)
        tokens = [t.strip() for t in sanitized.split() if t.strip()]
        if not tokens:
            return "", []

        # Check for words like "ID 529" or "Student 1"
        if len(tokens) == 2 and tokens[0].upper() in ("ID", "STUDENT", "STU", "ROLL", "NO", "NUM") and tokens[1].isdigit():
            target_id = int(tokens[1])
            where = f"""(
                {prefix}id = ?
                OR CAST({prefix}id AS TEXT) = ?
                OR EXISTS (
                    SELECT 1 FROM admissions a_id2
                    WHERE a_id2.student_id = {student_id_ref}
                      AND (a_id2.candidate_sequence = ? OR a_id2.id = ?)
                )
            )"""
            return where, [target_id, str(target_id), target_id, target_id]

        token_clauses = []
        params = []
        for token in tokens:
            tp = f"%{token}%"
            token_digits = re.sub(r"\D", "", token)
            has_digits = len(token_digits) >= 4

            clause = f"""(
                CAST({prefix}id AS TEXT) = ?
                OR {prefix}first_name LIKE ?
                OR {prefix}last_name LIKE ?
                OR COALESCE({prefix}middle_name, '') LIKE ?
                OR COALESCE({prefix}parent_guardian_name, '') LIKE ?
                OR COALESCE({prefix}mother_name, '') LIKE ?
                OR COALESCE({prefix}village, '') LIKE ?
                OR COALESCE({prefix}email, '') LIKE ?
                OR ({prefix}first_name || ' ' || {prefix}last_name) LIKE ?
                OR ({prefix}last_name || ' ' || {prefix}first_name) LIKE ?
                OR ({prefix}first_name || ' ' || COALESCE({prefix}middle_name, '') || ' ' || {prefix}last_name) LIKE ?
                OR ({prefix}last_name || ' ' || {prefix}first_name || ' ' || COALESCE({prefix}middle_name, '')) LIKE ?
                OR EXISTS (
                    SELECT 1 FROM admissions a_tok
                    WHERE a_tok.student_id = {student_id_ref}
                      AND (
                          PRINTF('%04d-%03d', a_tok.candidate_year, a_tok.candidate_sequence) LIKE ?
                          OR CAST(a_tok.candidate_sequence AS TEXT) = ?
                          OR CAST(a_tok.id AS TEXT) = ?
                      )
                )
            """
            token_params = [
                token,
                tp, tp, tp, tp, tp, tp, tp,
                tp, tp, tp, tp,
                tp, token, token
            ]
            if has_digits:
                clause += f" OR REPLACE(REPLACE(REPLACE({prefix}mobile_number, ' ', ''), '-', ''), '+', '') LIKE ?"
                token_params.append(f"%{token_digits}%")
            clause += ")"
            token_clauses.append(clause)
            params.extend(token_params)

        phrase_str = "%" + " ".join(tokens) + "%"
        full_phrase_clause = f"""(
            ({prefix}first_name || ' ' || {prefix}last_name) LIKE ?
            OR ({prefix}last_name || ' ' || {prefix}first_name) LIKE ?
            OR ({prefix}first_name || ' ' || COALESCE({prefix}middle_name, '') || ' ' || {prefix}last_name) LIKE ?
            OR ({prefix}last_name || ' ' || {prefix}first_name || ' ' || COALESCE({prefix}middle_name, '')) LIKE ?
        )"""

        joined_tokens = " AND ".join(token_clauses)
        where_clause = f"(({joined_tokens}) OR {full_phrase_clause})"
        params.extend([phrase_str, phrase_str, phrase_str, phrase_str])
        return where_clause, params

    def insert(self, data: dict[str, Any]) -> int:
        """Inserts a new student record and returns the generated ID."""
        sql = """
            INSERT INTO students (
                first_name, middle_name, last_name, mother_name, dob, gender,
                aadhaar_number, parent_guardian_name, village, address,
                qualification, blood_group, photo_path, signature_path,
                email, mobile_number, secondary_mobile
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        params = (
            data["first_name"],
            data.get("middle_name"),
            data["last_name"],
            data.get("mother_name"),
            data.get("dob"),
            data.get("gender"),
            data.get("aadhaar_number"),
            data.get("parent_guardian_name"),
            data.get("village"),
            data.get("address"),
            data.get("qualification"),
            data.get("blood_group"),
            data.get("photo_path"),
            data.get("signature_path"),
            data.get("email"),
            data.get("mobile_number"),
            data.get("secondary_mobile"),
        )
        return self.execute_insert(sql, params)

    def update(self, student_id: int, data: dict[str, Any]) -> int:
        """Updates an existing student record completely and returns affected rows count."""
        sql = """
            UPDATE students
            SET first_name = ?,
                middle_name = COALESCE(?, middle_name),
                last_name = ?,
                mother_name = COALESCE(?, mother_name),
                dob = COALESCE(?, dob),
                gender = COALESCE(?, gender),
                aadhaar_number = COALESCE(?, aadhaar_number),
                parent_guardian_name = COALESCE(?, parent_guardian_name),
                village = COALESCE(?, village),
                address = COALESCE(?, address),
                qualification = COALESCE(?, qualification),
                blood_group = COALESCE(?, blood_group),
                photo_path = COALESCE(?, photo_path),
                signature_path = COALESCE(?, signature_path),
                email = ?,
                mobile_number = ?,
                secondary_mobile = COALESCE(?, secondary_mobile),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?;
        """
        params = (
            data["first_name"],
            data.get("middle_name"),
            data["last_name"],
            data.get("mother_name"),
            data.get("dob"),
            data.get("gender"),
            data.get("aadhaar_number"),
            data.get("parent_guardian_name"),
            data.get("village"),
            data.get("address"),
            data.get("qualification"),
            data.get("blood_group"),
            data.get("photo_path"),
            data.get("signature_path"),
            data.get("email"),
            data.get("mobile_number"),
            data.get("secondary_mobile"),
            student_id,
        )
        return self.execute(sql, params)

    def update_document_path(self, student_id: int, doc_type: str, file_path: Optional[str]) -> int:
        """Updates photo_path or signature_path for a student."""
        col = "photo_path" if doc_type.lower() == "photo" else "signature_path"
        sql = f"UPDATE students SET {col} = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;"
        return self.execute(sql, (file_path, student_id))

    def get_by_id(self, student_id: int) -> Optional[dict[str, Any]]:
        """Retrieves a single student record with admission summary by Primary Key."""
        sql = f"""
            {self._STUDENT_SELECT_BASE}
            WHERE s.id = ?;
        """
        return self.execute_fetchone(sql, (student_id,))

    def get_by_mobile(self, mobile_number: str) -> Optional[dict[str, Any]]:
        """Retrieves a student record matching the mobile number as primary or secondary."""
        sql = """
            SELECT id, first_name, last_name, email, mobile_number, secondary_mobile, created_at
            FROM students
            WHERE mobile_number = ? OR secondary_mobile = ?
            LIMIT 1;
        """
        return self.execute_fetchone(sql, (mobile_number, mobile_number))

    def find_by_mobiles(self, mobiles: list[str]) -> list[dict[str, Any]]:
        """Finds all student records matching any of the given mobile numbers (primary or secondary)."""
        clean_mobiles = [m.strip() for m in mobiles if m and m.strip()]
        if not clean_mobiles:
            return []
        placeholders = ", ".join("?" for _ in clean_mobiles)
        sql = f"""
            SELECT s.*
            FROM students s
            WHERE s.mobile_number IN ({placeholders})
               OR s.secondary_mobile IN ({placeholders});
        """
        params = tuple(clean_mobiles + clean_mobiles)
        return self.execute_fetchall(sql, params)

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
        clauses: list[str] = []
        params: list[Any] = []

        if query and query.strip():
            search_clause, search_params = cls._build_search_conditions(query.strip(), table_alias=table_alias)
            if search_clause:
                clauses.append(f"({search_clause})")
                params.extend(search_params)

        if course_id is not None and int(course_id) > 0:
            clauses.append(f"""EXISTS (
                SELECT 1 FROM admissions a_cf
                JOIN admission_courses ac_cf ON ac_cf.admission_id = a_cf.id
                WHERE a_cf.student_id = {table_alias}.id AND ac_cf.course_id = ?
            )""")
            params.append(int(course_id))

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
        return cls._build_multi_order_by([(sort_by, sort_dir)])

    @classmethod
    def _build_multi_order_by(cls, sort_keys: list[tuple[str, str]] | None = None) -> str:
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
                continue

            if isinstance(mapping, list):
                for expr in mapping:
                    clauses.append(f"{expr} {dir_str}")
            else:
                clauses.append(f"{mapping} {dir_str}")

        if not clauses:
            return "ORDER BY s.id DESC"

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

        if query and query.strip():
            clean_q = query.strip()
            num_match = re.search(r"\b(\d{1,6})\b", clean_q)
            if num_match:
                target_id = int(num_match.group(1))
                if order_by.startswith("ORDER BY "):
                    order_by = f"ORDER BY CASE WHEN s.id = {target_id} THEN 0 ELSE 1 END, " + order_by[9:]

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

        if query and query.strip():
            clean_q = query.strip()
            num_match = re.search(r"\b(\d{1,6})\b", clean_q)
            if num_match:
                target_id = int(num_match.group(1))
                if order_by.startswith("ORDER BY "):
                    order_by = f"ORDER BY CASE WHEN s.id = {target_id} THEN 0 ELSE 1 END, " + order_by[9:]

        sql = f"""
            {self._STUDENT_SELECT_BASE}
            {where_clause}
            {order_by};
        """
        return self.execute_fetchall(sql, tuple(params))

    def get_all_paged(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        return self.filter_paged(limit=limit, offset=offset)

    def count_all(self) -> int:
        sql = "SELECT COUNT(*) as count FROM students;"
        row = self.execute_fetchone(sql)
        return int(row["count"]) if row else 0

    def search_paged(self, query: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        return self.filter_paged(query=query, limit=limit, offset=offset)

    def count_search(self, query: str) -> int:
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

    def has_admissions(self, student_id: int) -> bool:
        sql = "SELECT 1 FROM admissions WHERE student_id = ? LIMIT 1;"
        return self.exists(sql, (student_id,))

    def get_student_dependency_counts(self, student_id: int) -> dict[str, Any]:
        """Calculates exact count of relational dependencies attached to a student profile."""
        adm_row = self.execute_fetchone("SELECT count(*) as cnt FROM admissions WHERE student_id = ?;", (student_id,))
        pay_row = self.execute_fetchone("SELECT count(*) as cnt, COALESCE(SUM(amount), 0) as total FROM payments WHERE student_id = ?;", (student_id,))
        rcp_row = self.execute_fetchone("SELECT count(*) as cnt FROM receipts WHERE student_id = ?;", (student_id,))
        fr_row = self.execute_fetchone("SELECT count(*) as cnt FROM student_friendships WHERE student_id = ? OR friend_student_id = ?;", (student_id, student_id))
        stud_row = self.execute_fetchone("SELECT photo_path, signature_path FROM students WHERE id = ?;", (student_id,))

        doc_count = 0
        if stud_row:
            if stud_row.get("photo_path"):
                doc_count += 1
            if stud_row.get("signature_path"):
                doc_count += 1

        return {
            "admissions": int(adm_row["cnt"]) if adm_row else 0,
            "payments": int(pay_row["cnt"]) if pay_row else 0,
            "payments_total": float(pay_row["total"]) if pay_row else 0.0,
            "receipts": int(rcp_row["cnt"]) if rcp_row else 0,
            "friendships": int(fr_row["cnt"]) if fr_row else 0,
            "documents": doc_count,
        }

    def delete_student_cascade(self, student_id: int) -> None:
        """Deletes all child dependencies and student profile strictly within active transaction."""
        self.execute("DELETE FROM receipts WHERE student_id = ?;", (student_id,))
        self.execute("DELETE FROM payments WHERE student_id = ?;", (student_id,))
        self.execute("""
            DELETE FROM admission_courses 
            WHERE admission_id IN (SELECT id FROM admissions WHERE student_id = ?);
        """, (student_id,))
        self.execute("DELETE FROM student_friendships WHERE student_id = ? OR friend_student_id = ?;", (student_id, student_id))
        self.execute("DELETE FROM admissions WHERE student_id = ?;", (student_id,))
        self.execute("DELETE FROM students WHERE id = ?;", (student_id,))

    def delete(self, student_id: int) -> int:
        sql = "DELETE FROM students WHERE id = ?;"
        return self.execute(sql, (student_id,))

    def get_student_admissions(self, student_id: int) -> list[dict[str, Any]]:
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
        where_clause, params = self._build_search_conditions(query, table_alias="")
        if not where_clause:
            sql = """
                SELECT id, first_name, last_name, mobile_number
                FROM students
                ORDER BY first_name ASC, last_name ASC
                LIMIT ?;
            """
            return cast(list[StudentSearchRow], self.execute_fetchall(sql, (limit,)))

        clean_num = re.sub(r"\D", "", query)
        order_clause = "first_name ASC, last_name ASC"
        if clean_num and len(clean_num) <= 6:
            order_clause = f"CASE WHEN id = {int(clean_num)} THEN 0 ELSE 1 END, first_name ASC, last_name ASC"

        sql = f"""
            SELECT id, first_name, last_name, mobile_number
            FROM students
            WHERE {where_clause}
            ORDER BY {order_clause}
            LIMIT ?;
        """
        params.append(limit)
        return cast(list[StudentSearchRow], self.execute_fetchall(sql, tuple(params)))
