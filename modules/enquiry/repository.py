# modules/enquiry/repository.py

from __future__ import annotations
from typing import Any, Optional
from core.database.repository import BaseRepository
from modules.enquiry.dto import (
    CreateEnquiryDTO,
    UpdateEnquiryDTO,
    EnquiryFilterDTO,
)

__all__ = ["EnquiryRepository"]


class EnquiryRepository(BaseRepository):
    """Persistence repository for walk-in and prospective student enquiries."""

    def create(self, dto: CreateEnquiryDTO) -> int:
        sql = """
            INSERT INTO enquiries (
                student_name,
                mobile_number,
                alternate_mobile,
                email,
                village,
                address,
                course_id,
                interested_course,
                qualification,
                gender,
                status,
                source,
                follow_up_date,
                notes,
                counselor_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        params = (
            dto.student_name,
            dto.mobile_number,
            dto.alternate_mobile,
            dto.email,
            dto.village,
            dto.address,
            dto.course_id,
            dto.interested_course,
            dto.qualification,
            dto.gender,
            dto.status,
            dto.source,
            dto.follow_up_date,
            dto.notes,
            dto.counselor_name,
        )
        return self.execute_insert(sql, params)

    def update(self, dto: UpdateEnquiryDTO) -> bool:
        sql = """
            UPDATE enquiries
            SET student_name = ?,
                mobile_number = ?,
                alternate_mobile = ?,
                email = ?,
                village = ?,
                address = ?,
                course_id = ?,
                interested_course = ?,
                qualification = ?,
                gender = ?,
                status = ?,
                source = ?,
                follow_up_date = ?,
                notes = ?,
                counselor_name = ?,
                converted_admission_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?;
        """
        params = (
            dto.student_name,
            dto.mobile_number,
            dto.alternate_mobile,
            dto.email,
            dto.village,
            dto.address,
            dto.course_id,
            dto.interested_course,
            dto.qualification,
            dto.gender,
            dto.status,
            dto.source,
            dto.follow_up_date,
            dto.notes,
            dto.counselor_name,
            dto.converted_admission_id,
            dto.id,
        )
        return self.execute(sql, params) > 0

    def get_by_id(self, enquiry_id: int) -> Optional[dict[str, Any]]:
        sql = """
            SELECT e.*, c.name AS course_name
            FROM enquiries e
            LEFT JOIN courses c ON c.id = e.course_id
            WHERE e.id = ?;
        """
        return self.execute_fetchone(sql, (enquiry_id,))

    def search(self, filter_dto: EnquiryFilterDTO) -> tuple[list[dict[str, Any]], int]:
        conditions: list[str] = []
        params: list[Any] = []

        if filter_dto.query and filter_dto.query.strip():
            term = f"%{filter_dto.query.strip()}%"
            conditions.append(
                "(e.student_name LIKE ? OR e.mobile_number LIKE ? OR e.village LIKE ? OR e.interested_course LIKE ? OR e.counselor_name LIKE ?)"
            )
            params.extend([term, term, term, term, term])

        if filter_dto.status and filter_dto.status != "ALL":
            conditions.append("e.status = ?")
            params.append(filter_dto.status)

        if filter_dto.course_id:
            conditions.append("e.course_id = ?")
            params.append(filter_dto.course_id)

        if filter_dto.village and filter_dto.village.strip():
            conditions.append("LOWER(e.village) = LOWER(?)")
            params.append(filter_dto.village.strip())

        if filter_dto.date_from:
            conditions.append("DATE(e.created_at) >= DATE(?)")
            params.append(filter_dto.date_from)

        if filter_dto.date_to:
            conditions.append("DATE(e.created_at) <= DATE(?)")
            params.append(filter_dto.date_to)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # Count total
        count_sql = f"SELECT COUNT(*) AS total FROM enquiries e {where_clause};"
        count_res = self.execute_fetchone(count_sql, tuple(params))
        total = count_res["total"] if count_res else 0

        # Fetch records
        data_sql = f"""
            SELECT e.*, c.name AS course_name
            FROM enquiries e
            LEFT JOIN courses c ON c.id = e.course_id
            {where_clause}
            ORDER BY e.created_at DESC
            LIMIT ? OFFSET ?;
        """
        data_params = tuple(params + [filter_dto.limit, filter_dto.offset])
        rows = self.execute_fetchall(data_sql, data_params)
        return rows, total

    def get_summary_counts(self) -> dict[str, int]:
        sql = """
            SELECT 
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'NEW' THEN 1 ELSE 0 END) AS new_count,
                SUM(CASE WHEN status = 'CONTACTED' THEN 1 ELSE 0 END) AS contacted_count,
                SUM(CASE WHEN status = 'VISITED' THEN 1 ELSE 0 END) AS visited_count,
                SUM(CASE WHEN status = 'CONVERTED' THEN 1 ELSE 0 END) AS converted_count,
                SUM(CASE WHEN status = 'CLOSED' THEN 1 ELSE 0 END) AS closed_count
            FROM enquiries;
        """
        row = self.execute_fetchone(sql, ())
        if not row:
            return {"total": 0, "new": 0, "contacted": 0, "visited": 0, "converted": 0, "closed": 0}
        return {
            "total": row.get("total") or 0,
            "new": row.get("new_count") or 0,
            "contacted": row.get("contacted_count") or 0,
            "visited": row.get("visited_count") or 0,
            "converted": row.get("converted_count") or 0,
            "closed": row.get("closed_count") or 0,
        }

    def mark_converted(self, enquiry_id: int, admission_id: int) -> bool:
        sql = """
            UPDATE enquiries
            SET status = 'CONVERTED',
                converted_admission_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?;
        """
        return self.execute(sql, (admission_id, enquiry_id)) > 0

    def delete(self, enquiry_id: int) -> bool:
        sql = "DELETE FROM enquiries WHERE id = ?;"
        return self.execute(sql, (enquiry_id,)) > 0
