# modules/admission/repository.py

from __future__ import annotations
from typing import Any, Optional
from core.database.repository import BaseRepository
from modules.admission.dto import AdmissionFilterDTO

__all__ = ["AdmissionRepository"]


class AdmissionRepository(BaseRepository):
    """
    Handles all database interactions for the Admission entity.
    STRICT RULE: Pure SQL execution. Parameterized queries only.
    """

    _SORT_FIELD_MAP = {
        "id": "a.id",
        "candidate_number": "a.candidate_sequence",
        "student_name": "s.first_name",
        "course_name": "c.name",
        "date": "a.created_at",
        "agreed_fee": "a.agreed_fee",
        "status": "a.status",
        "total_fee": "(a.agreed_fee - a.discount)",
        "total_paid": "total_paid",
        "pending": "(a.agreed_fee - a.discount - total_paid)",
    }

    def has_admission_in_state(self, student_id: int, status: str) -> bool:
        query = "SELECT 1 FROM admissions WHERE student_id = ? AND status = ? LIMIT 1;"
        return self.exists(query, (student_id, status))

    def has_active_admission_for_course(self, student_id: int, course_id: int) -> bool:
        """Checks if a student already has an active unfinalized admission for a specific course."""
        query = """
            SELECT 1
            FROM admissions a
            JOIN admission_courses ac ON ac.admission_id = a.id
            WHERE a.student_id = ?
              AND ac.course_id = ?
              AND a.status IN ('DRAFT', 'REGISTERED')
            LIMIT 1;
        """
        return self.exists(query, (student_id, course_id))

    def get_next_sequence_for_year(self, year: int) -> int:
        sql = """
            SELECT COALESCE(MAX(candidate_sequence), 0) + 1 AS next_seq
            FROM admissions
            WHERE candidate_year = ?;
        """
        row = self.execute_fetchone(sql, (year,))
        return int(row["next_seq"]) if row and row["next_seq"] is not None else 1

    def insert(self, data: dict[str, Any]) -> int:
        sql = """
            INSERT INTO admissions (
                student_id, status, candidate_year, candidate_sequence,
                batch_id, agreed_fee, discount, remarks,
                institution_id, institution_name, qualification, qualification_other,
                blood_group, village, address, aadhaar_number,
                mother_name, parent_guardian_name, dob, gender, middle_name,
                photo_path, signature_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        params = (
            data["student_id"],
            data["status"],
            data.get("candidate_year"),
            data.get("candidate_sequence"),
            data.get("batch_id"),
            data.get("agreed_fee", 0.0),
            data.get("discount", 0.0),
            data.get("remarks"),
            data.get("institution_id"),
            data.get("institution_name"),
            data.get("qualification"),
            data.get("qualification_other"),
            data.get("blood_group"),
            data.get("village"),
            data.get("address"),
            data.get("aadhaar_number"),
            data.get("mother_name"),
            data.get("parent_guardian_name"),
            data.get("dob"),
            data.get("gender"),
            data.get("middle_name"),
            data.get("photo_path"),
            data.get("signature_path"),
        )
        return self.execute_insert(sql, params)

    def update(self, admission_id: int, data: dict[str, Any]) -> int:
        sql = """
            UPDATE admissions
            SET batch_id = ?,
                agreed_fee = ?,
                discount = ?,
                status = ?,
                remarks = ?,
                institution_id = ?,
                institution_name = ?,
                qualification = ?,
                qualification_other = ?,
                blood_group = ?,
                village = ?,
                address = ?,
                aadhaar_number = ?,
                mother_name = ?,
                parent_guardian_name = ?,
                dob = ?,
                gender = ?,
                middle_name = ?,
                photo_path = ?,
                signature_path = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?;
        """
        params = (
            data.get("batch_id"),
            data.get("agreed_fee", 0.0),
            data.get("discount", 0.0),
            data.get("status"),
            data.get("remarks"),
            data.get("institution_id"),
            data.get("institution_name"),
            data.get("qualification"),
            data.get("qualification_other"),
            data.get("blood_group"),
            data.get("village"),
            data.get("address"),
            data.get("aadhaar_number"),
            data.get("mother_name"),
            data.get("parent_guardian_name"),
            data.get("dob"),
            data.get("gender"),
            data.get("middle_name"),
            data.get("photo_path"),
            data.get("signature_path"),
            admission_id,
        )
        return self.execute(sql, params)

    def update_status(self, admission_id: int, status: str) -> int:
        sql = "UPDATE admissions SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;"
        return self.execute(sql, (status, admission_id))

    def get_by_id(self, admission_id: int) -> Optional[dict[str, Any]]:
        sql = """
            SELECT a.*,
                   s.first_name, s.last_name, s.email, s.mobile_number,
                   c.id AS course_id, c.code AS course_code, c.name AS course_name, c.base_fee AS course_base_fee,
                   b.batch_name, b.timing,
                   COALESCE((SELECT SUM(amount) FROM payments p WHERE p.admission_id = a.id), 0.0) AS total_paid
            FROM admissions a
            JOIN students s ON s.id = a.student_id
            LEFT JOIN admission_courses ac ON ac.admission_id = a.id
            LEFT JOIN courses c ON c.id = ac.course_id
            LEFT JOIN batches b ON b.id = a.batch_id
            WHERE a.id = ?
            LIMIT 1;
        """
        return self.execute_fetchone(sql, (admission_id,))

    def get_by_candidate_number(self, year: int, sequence: int) -> Optional[dict[str, Any]]:
        sql = """
            SELECT a.*,
                   s.first_name, s.last_name, s.email, s.mobile_number,
                   c.id AS course_id, c.code AS course_code, c.name AS course_name, c.base_fee AS course_base_fee,
                   b.batch_name, b.timing,
                   COALESCE((SELECT SUM(amount) FROM payments p WHERE p.admission_id = a.id), 0.0) AS total_paid
            FROM admissions a
            JOIN students s ON s.id = a.student_id
            LEFT JOIN admission_courses ac ON ac.admission_id = a.id
            LEFT JOIN courses c ON c.id = ac.course_id
            LEFT JOIN batches b ON b.id = a.batch_id
            WHERE a.candidate_year = ? AND a.candidate_sequence = ?
            LIMIT 1;
        """
        return self.execute_fetchone(sql, (year, sequence))

    def _build_filter_clauses(self, dto: AdmissionFilterDTO) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []

        if dto.query and dto.query.strip():
            raw_q = dto.query.strip()
            pattern = f"%{raw_q}%"
            clauses.append("""(
                s.first_name LIKE ? OR s.last_name LIKE ? OR (s.first_name || ' ' || s.last_name) LIKE ?
                OR s.mobile_number LIKE ? OR s.email LIKE ? OR s.aadhaar_number LIKE ?
                OR CAST(a.id AS TEXT) LIKE ? OR c.name LIKE ? OR c.code LIKE ?
                OR (CAST(a.candidate_year AS TEXT) || '-' || printf('%03d', a.candidate_sequence)) LIKE ?
            )""")
            params.extend([pattern, pattern, pattern, pattern, pattern, pattern, pattern, pattern, pattern, pattern])

        if dto.course_id and dto.course_id > 0:
            clauses.append("ac.course_id = ?")
            params.append(dto.course_id)

        if dto.status and dto.status.strip() and dto.status.strip().upper() != "ALL":
            st = dto.status.strip().upper()
            if st == "ACTIVE":
                clauses.append("a.status IN ('DRAFT', 'REGISTERED')")
            else:
                clauses.append("a.status = ?")
                params.append(st)

        if dto.year and dto.year > 0 and dto.month and 1 <= dto.month <= 12:
            clauses.append("( (a.candidate_year = ? OR CAST(strftime('%Y', a.created_at) AS INTEGER) = ?) AND CAST(strftime('%m', a.created_at) AS INTEGER) = ? )")
            params.extend([dto.year, dto.year, dto.month])
        elif dto.year and dto.year > 0:
            clauses.append("(a.candidate_year = ? OR CAST(strftime('%Y', a.created_at) AS INTEGER) = ?)")
            params.extend([dto.year, dto.year])
        elif dto.month and 1 <= dto.month <= 12:
            clauses.append("CAST(strftime('%m', a.created_at) AS INTEGER) = ?")
            params.append(dto.month)

        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return where_clause, params

    def _build_order_by(self, sort_keys: list[tuple[str, str]]) -> str:
        order_parts = []
        for field, direction in sort_keys:
            clean_field = field.lower().strip()
            clean_dir = "DESC" if direction.lower().strip() == "desc" else "ASC"
            if clean_field in self._SORT_FIELD_MAP:
                order_parts.append(f"{self._SORT_FIELD_MAP[clean_field]} {clean_dir}")

        if not order_parts:
            order_parts.append("a.id DESC")

        order_parts.append("a.id ASC")
        return f"ORDER BY {', '.join(order_parts)}"

    def filter_admissions(self, dto: AdmissionFilterDTO) -> tuple[list[dict[str, Any]], int]:
        where_clause, params = self._build_filter_clauses(dto)
        order_clause = self._build_order_by(dto.sort_keys)

        # 1. Total Count Query
        count_sql = f"""
            SELECT COUNT(DISTINCT a.id) AS total
            FROM admissions a
            JOIN students s ON s.id = a.student_id
            LEFT JOIN admission_courses ac ON ac.admission_id = a.id
            LEFT JOIN courses c ON c.id = ac.course_id
            {where_clause};
        """
        count_row = self.execute_fetchone(count_sql, tuple(params))
        total_count = int(count_row["total"]) if count_row and count_row["total"] is not None else 0

        # 2. Paged Data Query
        data_sql = f"""
            SELECT a.*,
                   s.first_name, s.last_name, s.email, s.mobile_number,
                   c.id AS course_id, c.code AS course_code, c.name AS course_name, c.base_fee AS course_base_fee,
                   b.batch_name, b.timing,
                   COALESCE((SELECT SUM(amount) FROM payments p WHERE p.admission_id = a.id), 0.0) AS total_paid
            FROM admissions a
            JOIN students s ON s.id = a.student_id
            LEFT JOIN admission_courses ac ON ac.admission_id = a.id
            LEFT JOIN courses c ON c.id = ac.course_id
            LEFT JOIN batches b ON b.id = a.batch_id
            {where_clause}
            {order_clause}
            LIMIT ? OFFSET ?;
        """
        paged_params = list(params) + [dto.limit, dto.offset]
        rows = self.execute_fetchall(data_sql, tuple(paged_params))

        return rows, total_count

    def get_summary_statistics(self) -> dict[str, Any]:
        """Calculates global admission and revenue KPI metrics."""
        sql = """
            SELECT 
                COUNT(*) AS total_admissions,
                SUM(CASE WHEN status = 'CONFIRMED' THEN 1 ELSE 0 END) AS confirmed_count,
                SUM(CASE WHEN status = 'REGISTERED' THEN 1 ELSE 0 END) AS registered_count,
                SUM(CASE WHEN status = 'DRAFT' THEN 1 ELSE 0 END) AS draft_count,
                SUM(CASE WHEN DATE(created_at) = DATE('now', 'localtime') THEN 1 ELSE 0 END) AS today_admissions,
                COALESCE(SUM(agreed_fee - discount), 0.0) AS total_revenue
            FROM admissions;
        """
        row = self.execute_fetchone(sql)
        stats = dict(row or {})

        # Payments totals
        pay_sql = """
            SELECT 
                COALESCE(SUM(amount), 0.0) AS total_collection,
                COALESCE(SUM(CASE WHEN DATE(payment_date) = DATE('now', 'localtime') THEN amount ELSE 0.0 END), 0.0) AS today_collection
            FROM payments;
        """
        pay_row = self.execute_fetchone(pay_sql)
        pay_stats = dict(pay_row or {})

        total_rev = float(stats.get("total_revenue", 0.0))
        total_coll = float(pay_stats.get("total_collection", 0.0))
        total_pending = max(0.0, total_rev - total_coll)

        return {
            "total_admissions": int(stats.get("total_admissions", 0)),
            "confirmed_count": int(stats.get("confirmed_count", 0)),
            "registered_count": int(stats.get("registered_count", 0)),
            "draft_count": int(stats.get("draft_count", 0)),
            "today_admissions": int(stats.get("today_admissions", 0)),
            "total_revenue": total_rev,
            "today_collection": float(pay_stats.get("today_collection", 0.0)),
            "total_pending": total_pending,
        }

    def delete(self, admission_id: int) -> int:
        """Deletes an admission record and course bridge linkage."""
        self.execute("DELETE FROM admission_courses WHERE admission_id = ?;", (admission_id,))
        return self.execute("DELETE FROM admissions WHERE id = ?;", (admission_id,))
