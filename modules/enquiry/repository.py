# modules/enquiry/repository.py

from __future__ import annotations
from typing import Any, Optional
from core.database.repository import BaseRepository
from modules.enquiry.dto import (
    CreateEnquiryDTO,
    UpdateEnquiryDTO,
    EnquiryFilterDTO,
    CreateFollowUpDTO,
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
                category,
                preferred_timing,
                source,
                follow_up_date,
                notes,
                counselor_name,
                loss_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
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
            getattr(dto, "category", "WARM") or "WARM",
            getattr(dto, "preferred_timing", "ANY") or "ANY",
            dto.source,
            dto.follow_up_date,
            dto.notes,
            dto.counselor_name,
            getattr(dto, "loss_reason", None),
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
                category = ?,
                preferred_timing = ?,
                source = ?,
                follow_up_date = ?,
                notes = ?,
                counselor_name = ?,
                converted_admission_id = ?,
                loss_reason = ?,
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
            getattr(dto, "category", "WARM") or "WARM",
            getattr(dto, "preferred_timing", "ANY") or "ANY",
            dto.source,
            dto.follow_up_date,
            dto.notes,
            dto.counselor_name,
            dto.converted_admission_id,
            getattr(dto, "loss_reason", None),
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

        if filter_dto.category and filter_dto.category != "ALL":
            conditions.append("e.category = ?")
            params.append(filter_dto.category)

        if filter_dto.follow_up_filter:
            f_upper = filter_dto.follow_up_filter.upper()
            if f_upper == "TODAY":
                conditions.append("DATE(e.follow_up_date) = DATE('now', 'localtime') AND e.status != 'CONVERTED'")
            elif f_upper == "OVERDUE":
                conditions.append("DATE(e.follow_up_date) < DATE('now', 'localtime') AND e.status != 'CONVERTED' AND e.category != 'LOST'")
            elif f_upper == "UPCOMING":
                conditions.append("DATE(e.follow_up_date) > DATE('now', 'localtime') AND e.status != 'CONVERTED'")

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

    def get_category_summary(self) -> dict[str, int]:
        """Calculates lead counts across operational categories and follow-up urgencies."""
        sql = """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN category = 'HOT' AND status != 'CONVERTED' THEN 1 ELSE 0 END) AS hot_count,
                SUM(CASE WHEN (category = 'WARM' OR category IS NULL OR category = '') AND status != 'CONVERTED' THEN 1 ELSE 0 END) AS warm_count,
                SUM(CASE WHEN category = 'COLD' AND status != 'CONVERTED' THEN 1 ELSE 0 END) AS cold_count,
                SUM(CASE WHEN category = 'LOST' OR status = 'CLOSED' THEN 1 ELSE 0 END) AS lost_count,
                SUM(CASE WHEN category = 'CONVERTED' OR status = 'CONVERTED' THEN 1 ELSE 0 END) AS converted_count,
                SUM(CASE WHEN DATE(follow_up_date) = DATE('now', 'localtime') AND status != 'CONVERTED' THEN 1 ELSE 0 END) AS today_followup_count,
                SUM(CASE WHEN DATE(follow_up_date) < DATE('now', 'localtime') AND status != 'CONVERTED' AND category != 'LOST' AND status != 'CLOSED' THEN 1 ELSE 0 END) AS overdue_followup_count
            FROM enquiries;
        """
        row = self.execute_fetchone(sql, ())
        if not row:
            return {"total": 0, "hot": 0, "warm": 0, "cold": 0, "lost": 0, "converted": 0, "today_followup": 0, "overdue_followup": 0}
        return {
            "total": row.get("total") or 0,
            "hot": row.get("hot_count") or 0,
            "warm": row.get("warm_count") or 0,
            "cold": row.get("cold_count") or 0,
            "lost": row.get("lost_count") or 0,
            "converted": row.get("converted_count") or 0,
            "today_followup": row.get("today_followup_count") or 0,
            "overdue_followup": row.get("overdue_followup_count") or 0,
        }

    def create_follow_up(self, dto: CreateFollowUpDTO) -> int:
        """Inserts a historical call log or counseling remark."""
        sql = """
            INSERT INTO enquiry_follow_ups (
                enquiry_id,
                follow_up_date,
                call_type,
                discussion_notes,
                category_after_call,
                next_follow_up_date,
                counselor_name
            ) VALUES (?, COALESCE(?, DATE('now', 'localtime')), ?, ?, ?, ?, ?);
        """
        params = (
            dto.enquiry_id,
            dto.follow_up_date,
            dto.call_type,
            dto.discussion_notes,
            dto.category_after_call,
            dto.next_follow_up_date,
            dto.counselor_name,
        )
        return self.execute_insert(sql, params)

    def get_follow_ups(self, enquiry_id: int) -> list[dict[str, Any]]:
        """Retrieves chronological call logs for an enquiry."""
        sql = """
            SELECT *
            FROM enquiry_follow_ups
            WHERE enquiry_id = ?
            ORDER BY created_at DESC, id DESC;
        """
        return self.execute_fetchall(sql, (enquiry_id,))

    def search_for_admission(self, query: str = "", limit: int = 15) -> list[dict[str, Any]]:
        """Searches enquiries to allow 1-click candidate selection and auto-fill inside the Admission Form."""
        conditions = ["e.status != 'CONVERTED'"]
        params: list[Any] = []

        if query and query.strip():
            term = f"%{query.strip()}%"
            conditions.append(
                "(e.student_name LIKE ? OR e.mobile_number LIKE ? OR e.village LIKE ? OR e.interested_course LIKE ?)"
            )
            params.extend([term, term, term, term])

        where_clause = f"WHERE {' AND '.join(conditions)}"
        sql = f"""
            SELECT e.*, c.name AS course_name
            FROM enquiries e
            LEFT JOIN courses c ON c.id = e.course_id
            {where_clause}
            ORDER BY e.created_at DESC
            LIMIT ?;
        """
        params.append(limit)
        return self.execute_fetchall(sql, tuple(params))

    def mark_converted(self, enquiry_id: int, admission_id: int) -> bool:
        sql = """
            UPDATE enquiries
            SET status = 'CONVERTED',
                category = 'CONVERTED',
                converted_admission_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?;
        """
        return self.execute(sql, (admission_id, enquiry_id)) > 0

    def delete(self, enquiry_id: int) -> bool:
        self.execute("DELETE FROM enquiry_follow_ups WHERE enquiry_id = ?;", (enquiry_id,))
        sql = "DELETE FROM enquiries WHERE id = ?;"
        return self.execute(sql, (enquiry_id,)) > 0

