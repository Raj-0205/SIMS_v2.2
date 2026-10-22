# modules/reports/service.py

from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from core.service.base import BaseService
from core.database.repository import BaseRepository
from infrastructure.excel.exporter import ExcelExporter

__all__ = ["ReportsService"]


class ReportsService(BaseService):
    """
    Business service for generating 17-column fee reports,
    installment breakdown, and exact payment amount filtering.
    """

    def __init__(self) -> None:
        self.repo = BaseRepository()

    def _build_fees_filter_clauses(
        self,
        course_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple[str, list[Any]]:
        clauses = []
        params = []

        if search and search.strip():
            p = f"%{search.strip()}%"
            clauses.append("""(
                s.first_name LIKE ? OR s.last_name LIKE ? OR (s.first_name || ' ' || s.last_name) LIKE ?
                OR s.mobile_number LIKE ? OR CAST(a.id AS TEXT) LIKE ? OR c.name LIKE ?
                OR (CAST(a.candidate_year AS TEXT) || '-' || printf('%03d', a.candidate_sequence)) LIKE ?
                OR EXISTS (
                    SELECT 1 FROM admission_courses ac2 
                    JOIN courses c2 ON c2.id = ac2.course_id 
                    WHERE ac2.admission_id = a.id AND c2.name LIKE ?
                )
            )""")
            params.extend([p, p, p, p, p, p, p, p])

        if course_id and course_id > 0:
            clauses.append("ac.course_id = ?")
            params.append(course_id)

        if status and status.strip() and status.strip().upper() != "ALL":
            st = status.strip().upper()
            if st == "ACTIVE":
                clauses.append("a.status IN ('DRAFT', 'REGISTERED', 'CONFIRMED')")
            else:
                clauses.append("a.status = ?")
                params.append(st)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return where_sql, params

    def _resolve_sort_order(self, sort_by: Optional[str]) -> str:
        if not sort_by or sort_by.upper() in ("NONE", "DEFAULT"):
            return "ORDER BY a.id DESC"
        st = sort_by.strip().upper()
        if st == "INST1":
            return "ORDER BY inst1 DESC, a.id DESC"
        elif st == "INST2":
            return "ORDER BY inst2 DESC, a.id DESC"
        elif st == "INST3":
            return "ORDER BY inst3 DESC, a.id DESC"
        elif st == "INST4":
            return "ORDER BY inst4 DESC, a.id DESC"
        elif st == "PAID":
            return "ORDER BY total_paid DESC, a.id DESC"
        elif st == "PENDING":
            return "ORDER BY pending_fees DESC, a.id DESC"
        return "ORDER BY a.id DESC"

    def _map_report_rows(self, raw_admissions: list[dict[str, Any]], start_idx: int = 1) -> list[dict[str, Any]]:
        results = []
        for idx, adm in enumerate(raw_admissions, start=start_idx):
            adm_id = adm["admission_id"]
            inst1 = float(adm.get("inst1") or 0.0)
            inst2 = float(adm.get("inst2") or 0.0)
            inst3 = float(adm.get("inst3") or 0.0)
            inst4 = float(adm.get("inst4") or 0.0)
            total_paid = float(adm.get("total_paid") or 0.0)

            total_fees = float(adm.get("agreed_fee") or 0.0) - float(adm.get("discount") or 0.0)
            pending_fees = max(0.0, total_fees - total_paid)

            friend_name = (adm.get("friend_name") or "").strip() or "—"
            friend_mobile = adm.get("friend_mobile") or "—"

            c_year = adm.get("candidate_year") or 2026
            c_seq = adm.get("candidate_sequence") or adm_id
            try:
                c_seq_int = int(c_seq)
                adm_num = f"{c_year}-{c_seq_int:03d}"
            except (ValueError, TypeError):
                adm_num = f"{c_year}-{c_seq}"

            results.append({
                "sr_no": idx,
                "course_name": adm.get("course_name") or "General Course",
                "admission_date": str(adm.get("admission_date") or "")[:10],
                "admission_id": adm_num,
                "name": f"{adm.get('first_name', '')} {adm.get('last_name', '')}".strip(),
                "mob_no": adm.get("mobile_number") or "—",
                "admission_status": adm.get("admission_status") or "REGISTERED",
                "total_fees": total_fees,
                "inst1": inst1,
                "inst2": inst2,
                "inst3": inst3,
                "inst4": inst4,
                "total_paid": total_paid,
                "pending_fees": pending_fees,
                "address": adm.get("address") or adm.get("village") or "—",
                "friend_name": friend_name,
                "friend_mobile": friend_mobile,
            })
        return results

    def get_admission_fees_report(
        self,
        course_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Returns full unpaginated admission fees report rows (legacy compatible with caching)."""
        from core.cache.fees_cache import FeesCacheManager

        status_clean = (status or "ALL").strip().upper()
        search_clean = (search or "").strip()
        sort_clean = (sort_by or "NONE").strip().upper()
        cache_key = (course_id, status_clean, search_clean, sort_clean)

        cached_report = FeesCacheManager.get_full_report(cache_key)
        if cached_report is not None:
            return cached_report

        with self.unit_of_work():
            where_sql, params = self._build_fees_filter_clauses(course_id, status, search)
            order_by_sql = self._resolve_sort_order(sort_by)

            # High-performance aggregated SQL query eliminating correlated subqueries (SIMS-PERF-01)
            sql = f"""
                SELECT a.id AS admission_id,
                       a.candidate_year,
                       a.candidate_sequence,
                       a.created_at AS admission_date,
                       a.status AS admission_status,
                       a.agreed_fee,
                       a.discount,
                       a.village,
                       a.address,
                       s.id AS student_id,
                       s.first_name,
                       s.last_name,
                       s.mobile_number,
                       c.id AS course_id,
                       COALESCE(c.name, 'General Course') AS course_name,
                       COALESCE(p.inst1, 0.0) AS inst1,
                       COALESCE(p.inst2, 0.0) AS inst2,
                       COALESCE(p.inst3, 0.0) AS inst3,
                       COALESCE(p.inst4, 0.0) AS inst4,
                       COALESCE(p.total_paid, 0.0) AS total_paid,
                       MAX(0.0, (COALESCE(a.agreed_fee, 0.0) - COALESCE(a.discount, 0.0)) - COALESCE(p.total_paid, 0.0)) AS pending_fees,
                       f.friend_name,
                       f.friend_mobile
                FROM admissions a
                JOIN students s ON s.id = a.student_id
                LEFT JOIN admission_courses ac ON ac.admission_id = a.id
                LEFT JOIN courses c ON c.id = ac.course_id
                LEFT JOIN (
                    SELECT admission_id,
                           SUM(CASE WHEN installment_number = 1 THEN amount ELSE 0 END) AS inst1,
                           SUM(CASE WHEN installment_number = 2 THEN amount ELSE 0 END) AS inst2,
                           SUM(CASE WHEN installment_number = 3 THEN amount ELSE 0 END) AS inst3,
                           SUM(CASE WHEN installment_number = 4 THEN amount ELSE 0 END) AS inst4,
                           SUM(amount) AS total_paid
                    FROM payments
                    GROUP BY admission_id
                ) p ON p.admission_id = a.id
                LEFT JOIN (
                    SELECT 
                        sf.base_student_id,
                        TRIM(s_f.first_name || ' ' || s_f.last_name) AS friend_name,
                        s_f.mobile_number AS friend_mobile
                    FROM (
                        SELECT 
                            student_id AS base_student_id,
                            friend_student_id AS target_friend_id,
                            ROW_NUMBER() OVER (PARTITION BY student_id ORDER BY id ASC) as rn
                        FROM student_friendships
                        WHERE is_active = 1
                        UNION ALL
                        SELECT 
                            friend_student_id AS base_student_id,
                            student_id AS target_friend_id,
                            ROW_NUMBER() OVER (PARTITION BY friend_student_id ORDER BY id ASC) as rn
                        FROM student_friendships
                        WHERE is_active = 1
                    ) sf
                    JOIN students s_f ON s_f.id = sf.target_friend_id
                    WHERE sf.rn = 1
                ) f ON f.base_student_id = s.id
                {where_sql}
                {order_by_sql};
            """
            raw_admissions = self.repo.execute_fetchall(sql, tuple(params))
            mapped_rows = self._map_report_rows(raw_admissions, start_idx=1)
            FeesCacheManager.set_full_report(cache_key, mapped_rows)
            return mapped_rows

    def get_admission_fees_report_paginated(
        self,
        course_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        page: int = 1,
        page_size: int = 30,
    ) -> dict[str, Any]:
        """
        Returns paginated fees report with metadata, sequential sr_no,
        in-memory LRU block caching, and sub-millisecond Page-First execution.
        """
        from core.cache.fees_cache import FeesCacheManager

        page_val = max(1, page)
        page_size_val = max(1, page_size)
        status_clean = (status or "ALL").strip().upper()
        search_clean = (search or "").strip()
        sort_clean = (sort_by or "NONE").strip().upper()

        cache_key = (course_id, status_clean, search_clean, sort_clean, page_size_val, page_val)
        count_key = (course_id, status_clean, search_clean)

        # 1. Fast Memory Cache Check
        cached_block = FeesCacheManager.get_block(cache_key)
        cached_count = FeesCacheManager.get_total_count(count_key)

        if cached_block is not None and cached_count is not None:
            total_pages = max(1, (cached_count + page_size_val - 1) // page_size_val)
            return {
                "rows": cached_block,
                "total_count": cached_count,
                "page": page_val,
                "page_size": page_size_val,
                "total_pages": total_pages,
                "from_cache": True,
            }

        # 2. Database Execution on Cache Miss
        with self.unit_of_work():
            where_sql, params = self._build_fees_filter_clauses(course_id, status, search)

            # Resolve total matching count (cached or queried)
            if cached_count is None:
                count_sql = f"""
                    SELECT COUNT(*) as cnt
                    FROM admissions a
                    JOIN students s ON s.id = a.student_id
                    LEFT JOIN admission_courses ac ON ac.admission_id = a.id
                    LEFT JOIN courses c ON c.id = ac.course_id
                    {where_sql};
                """
                count_res = self.repo.execute_fetchone(count_sql, tuple(params))
                total_count = int(count_res["cnt"]) if count_res else 0
                FeesCacheManager.set_total_count(count_key, total_count)
            else:
                total_count = cached_count

            offset_val = (page_val - 1) * page_size_val
            total_pages = max(1, (total_count + page_size_val - 1) // page_size_val)
            order_by_sql = self._resolve_sort_order(sort_by)

            # 3. Choose Optimal Query Strategy
            # If sorting by calculated fields (inst1..4, total_paid, pending_fees), use full aggregated sort.
            # Otherwise (Default, ID, Date, etc.), use the ultra-fast Page-First CTE (SIMS-PERF-02).
            is_calculated_sort = sort_clean in ("INST1", "INST2", "INST3", "INST4", "PAID", "PENDING")

            if not is_calculated_sort:
                sql = f"""
                    WITH target_page AS (
                        SELECT a.id as admission_id
                        FROM admissions a
                        JOIN students s ON s.id = a.student_id
                        LEFT JOIN admission_courses ac ON ac.admission_id = a.id
                        LEFT JOIN courses c ON c.id = ac.course_id
                        {where_sql}
                        {order_by_sql}
                        LIMIT ? OFFSET ?
                    )
                    SELECT a.id AS admission_id,
                           a.candidate_year,
                           a.candidate_sequence,
                           a.created_at AS admission_date,
                           a.status AS admission_status,
                           a.agreed_fee,
                           a.discount,
                           a.village,
                           a.address,
                           s.id AS student_id,
                           s.first_name,
                           s.last_name,
                           s.mobile_number,
                           c.id AS course_id,
                           COALESCE(c.name, 'General Course') AS course_name,
                           COALESCE(p.inst1, 0.0) AS inst1,
                           COALESCE(p.inst2, 0.0) AS inst2,
                           COALESCE(p.inst3, 0.0) AS inst3,
                           COALESCE(p.inst4, 0.0) AS inst4,
                           COALESCE(p.total_paid, 0.0) AS total_paid,
                           MAX(0.0, (COALESCE(a.agreed_fee, 0.0) - COALESCE(a.discount, 0.0)) - COALESCE(p.total_paid, 0.0)) AS pending_fees,
                           COALESCE(
                               (
                                   SELECT TRIM(s2.first_name || ' ' || s2.last_name)
                                   FROM student_friendships sf INDEXED BY idx_friendships_student_active
                                   JOIN students s2 ON s2.id = sf.friend_student_id
                                   WHERE sf.student_id = s.id AND sf.is_active = 1
                                   LIMIT 1
                               ),
                               (
                                   SELECT TRIM(s2.first_name || ' ' || s2.last_name)
                                   FROM student_friendships sf INDEXED BY idx_friendships_friend_active
                                   JOIN students s2 ON s2.id = sf.student_id
                                   WHERE sf.friend_student_id = s.id AND sf.is_active = 1
                                   LIMIT 1
                               )
                           ) AS friend_name,
                           COALESCE(
                               (
                                   SELECT s2.mobile_number
                                   FROM student_friendships sf INDEXED BY idx_friendships_student_active
                                   JOIN students s2 ON s2.id = sf.friend_student_id
                                   WHERE sf.student_id = s.id AND sf.is_active = 1
                                   LIMIT 1
                               ),
                               (
                                   SELECT s2.mobile_number
                                   FROM student_friendships sf INDEXED BY idx_friendships_friend_active
                                   JOIN students s2 ON s2.id = sf.student_id
                                   WHERE sf.friend_student_id = s.id AND sf.is_active = 1
                                   LIMIT 1
                               )
                           ) AS friend_mobile
                    FROM target_page tp
                    JOIN admissions a ON a.id = tp.admission_id
                    JOIN students s ON s.id = a.student_id
                    LEFT JOIN admission_courses ac ON ac.admission_id = a.id
                    LEFT JOIN courses c ON c.id = ac.course_id
                    LEFT JOIN (
                        SELECT admission_id,
                               SUM(CASE WHEN installment_number = 1 THEN amount ELSE 0 END) AS inst1,
                               SUM(CASE WHEN installment_number = 2 THEN amount ELSE 0 END) AS inst2,
                               SUM(CASE WHEN installment_number = 3 THEN amount ELSE 0 END) AS inst3,
                               SUM(CASE WHEN installment_number = 4 THEN amount ELSE 0 END) AS inst4,
                               SUM(amount) AS total_paid
                        FROM payments
                        WHERE admission_id IN (SELECT admission_id FROM target_page)
                        GROUP BY admission_id
                    ) p ON p.admission_id = a.id
                    {order_by_sql};
                """
            else:
                sql = f"""
                    SELECT a.id AS admission_id,
                           a.candidate_year,
                           a.candidate_sequence,
                           a.created_at AS admission_date,
                           a.status AS admission_status,
                           a.agreed_fee,
                           a.discount,
                           a.village,
                           a.address,
                           s.id AS student_id,
                           s.first_name,
                           s.last_name,
                           s.mobile_number,
                           c.id AS course_id,
                           COALESCE(c.name, 'General Course') AS course_name,
                           COALESCE(p.inst1, 0.0) AS inst1,
                           COALESCE(p.inst2, 0.0) AS inst2,
                           COALESCE(p.inst3, 0.0) AS inst3,
                           COALESCE(p.inst4, 0.0) AS inst4,
                           COALESCE(p.total_paid, 0.0) AS total_paid,
                           MAX(0.0, (COALESCE(a.agreed_fee, 0.0) - COALESCE(a.discount, 0.0)) - COALESCE(p.total_paid, 0.0)) AS pending_fees,
                           f.friend_name,
                           f.friend_mobile
                    FROM admissions a
                    JOIN students s ON s.id = a.student_id
                    LEFT JOIN admission_courses ac ON ac.admission_id = a.id
                    LEFT JOIN courses c ON c.id = ac.course_id
                    LEFT JOIN (
                        SELECT admission_id,
                               SUM(CASE WHEN installment_number = 1 THEN amount ELSE 0 END) AS inst1,
                               SUM(CASE WHEN installment_number = 2 THEN amount ELSE 0 END) AS inst2,
                               SUM(CASE WHEN installment_number = 3 THEN amount ELSE 0 END) AS inst3,
                               SUM(CASE WHEN installment_number = 4 THEN amount ELSE 0 END) AS inst4,
                               SUM(amount) AS total_paid
                        FROM payments
                        GROUP BY admission_id
                    ) p ON p.admission_id = a.id
                    LEFT JOIN (
                        SELECT 
                            sf.base_student_id,
                            TRIM(s_f.first_name || ' ' || s_f.last_name) AS friend_name,
                            s_f.mobile_number AS friend_mobile
                        FROM (
                            SELECT 
                                student_id AS base_student_id,
                                friend_student_id AS target_friend_id,
                                ROW_NUMBER() OVER (PARTITION BY student_id ORDER BY id ASC) as rn
                            FROM student_friendships
                            WHERE is_active = 1
                            UNION ALL
                            SELECT 
                                friend_student_id AS base_student_id,
                                student_id AS target_friend_id,
                                ROW_NUMBER() OVER (PARTITION BY friend_student_id ORDER BY id ASC) as rn
                            FROM student_friendships
                            WHERE is_active = 1
                        ) sf
                        JOIN students s_f ON s_f.id = sf.target_friend_id
                        WHERE sf.rn = 1
                    ) f ON f.base_student_id = s.id
                    {where_sql}
                    {order_by_sql}
                    LIMIT ? OFFSET ?;
                """

            exec_params = list(params) + [page_size_val, offset_val]
            raw_admissions = self.repo.execute_fetchall(sql, tuple(exec_params))
            rows = self._map_report_rows(raw_admissions, start_idx=offset_val + 1)

            # Store in Memory Block Cache
            FeesCacheManager.set_block(cache_key, rows)

            return {
                "rows": rows,
                "total_count": total_count,
                "page": page_val,
                "page_size": page_size_val,
                "total_pages": total_pages,
                "from_cache": False,
            }

    def get_admission_fees_report_chunk(
        self,
        course_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        offset: int = 0,
        limit: int = 10,
    ) -> dict[str, Any]:
        """
        Retrieves a single micro-chunk (e.g. 10 students) of the fees report
        for progressive streaming with continuous sequential sr_no and total count.
        """
        from core.cache.fees_cache import FeesCacheManager

        offset_val = max(0, offset)
        limit_val = max(1, limit)
        status_clean = (status or "ALL").strip().upper()
        search_clean = (search or "").strip()
        sort_clean = (sort_by or "NONE").strip().upper()

        count_key = (course_id, status_clean, search_clean)
        cached_count = FeesCacheManager.get_total_count(count_key)
        chunk_key = (course_id, status_clean, search_clean, sort_clean, offset_val, limit_val)
        cached_chunk = FeesCacheManager.get_block(chunk_key)

        if cached_chunk is not None and cached_count is not None:
            return {
                "rows": cached_chunk,
                "total_count": cached_count,
                "offset": offset_val,
                "limit": limit_val,
                "from_cache": True,
            }

        with self.unit_of_work():
            where_sql, params = self._build_fees_filter_clauses(course_id, status, search)

            if cached_count is None:
                count_sql = f"""
                    SELECT COUNT(*) as cnt
                    FROM admissions a
                    JOIN students s ON s.id = a.student_id
                    LEFT JOIN admission_courses ac ON ac.admission_id = a.id
                    LEFT JOIN courses c ON c.id = ac.course_id
                    {where_sql};
                """
                count_res = self.repo.execute_fetchone(count_sql, tuple(params))
                total_count = int(count_res["cnt"]) if count_res else 0
                FeesCacheManager.set_total_count(count_key, total_count)
            else:
                total_count = cached_count

            order_by_sql = self._resolve_sort_order(sort_by)
            is_calculated_sort = sort_clean in ("INST1", "INST2", "INST3", "INST4", "PAID", "PENDING")

            if not is_calculated_sort:
                sql = f"""
                    WITH target_page AS (
                        SELECT a.id as admission_id
                        FROM admissions a
                        JOIN students s ON s.id = a.student_id
                        LEFT JOIN admission_courses ac ON ac.admission_id = a.id
                        LEFT JOIN courses c ON c.id = ac.course_id
                        {where_sql}
                        {order_by_sql}
                        LIMIT ? OFFSET ?
                    )
                    SELECT a.id AS admission_id,
                           a.candidate_year,
                           a.candidate_sequence,
                           a.created_at AS admission_date,
                           a.status AS admission_status,
                           a.agreed_fee,
                           a.discount,
                           a.village,
                           a.address,
                           s.id AS student_id,
                           s.first_name,
                           s.last_name,
                           s.mobile_number,
                           c.id AS course_id,
                           COALESCE(c.name, 'General Course') AS course_name,
                           COALESCE(p.inst1, 0.0) AS inst1,
                           COALESCE(p.inst2, 0.0) AS inst2,
                           COALESCE(p.inst3, 0.0) AS inst3,
                           COALESCE(p.inst4, 0.0) AS inst4,
                           COALESCE(p.total_paid, 0.0) AS total_paid,
                           MAX(0.0, (COALESCE(a.agreed_fee, 0.0) - COALESCE(a.discount, 0.0)) - COALESCE(p.total_paid, 0.0)) AS pending_fees,
                           COALESCE(
                               (
                                   SELECT TRIM(s2.first_name || ' ' || s2.last_name)
                                   FROM student_friendships sf INDEXED BY idx_friendships_student_active
                                   JOIN students s2 ON s2.id = sf.friend_student_id
                                   WHERE sf.student_id = s.id AND sf.is_active = 1
                                   LIMIT 1
                               ),
                               (
                                   SELECT TRIM(s2.first_name || ' ' || s2.last_name)
                                   FROM student_friendships sf INDEXED BY idx_friendships_friend_active
                                   JOIN students s2 ON s2.id = sf.student_id
                                   WHERE sf.friend_student_id = s.id AND sf.is_active = 1
                                   LIMIT 1
                               )
                           ) AS friend_name,
                           COALESCE(
                               (
                                   SELECT s2.mobile_number
                                   FROM student_friendships sf INDEXED BY idx_friendships_student_active
                                   JOIN students s2 ON s2.id = sf.friend_student_id
                                   WHERE sf.student_id = s.id AND sf.is_active = 1
                                   LIMIT 1
                               ),
                               (
                                   SELECT s2.mobile_number
                                   FROM student_friendships sf INDEXED BY idx_friendships_friend_active
                                   JOIN students s2 ON s2.id = sf.student_id
                                   WHERE sf.friend_student_id = s.id AND sf.is_active = 1
                                   LIMIT 1
                               )
                           ) AS friend_mobile
                    FROM target_page tp
                    JOIN admissions a ON a.id = tp.admission_id
                    JOIN students s ON s.id = a.student_id
                    LEFT JOIN admission_courses ac ON ac.admission_id = a.id
                    LEFT JOIN courses c ON c.id = ac.course_id
                    LEFT JOIN (
                        SELECT admission_id,
                               SUM(CASE WHEN installment_number = 1 THEN amount ELSE 0 END) AS inst1,
                               SUM(CASE WHEN installment_number = 2 THEN amount ELSE 0 END) AS inst2,
                               SUM(CASE WHEN installment_number = 3 THEN amount ELSE 0 END) AS inst3,
                               SUM(CASE WHEN installment_number = 4 THEN amount ELSE 0 END) AS inst4,
                               SUM(amount) AS total_paid
                        FROM payments
                        WHERE admission_id IN (SELECT admission_id FROM target_page)
                        GROUP BY admission_id
                    ) p ON p.admission_id = a.id
                    {order_by_sql};
                """
            else:
                sql = f"""
                    SELECT a.id AS admission_id,
                           a.candidate_year,
                           a.candidate_sequence,
                           a.created_at AS admission_date,
                           a.status AS admission_status,
                           a.agreed_fee,
                           a.discount,
                           a.village,
                           a.address,
                           s.id AS student_id,
                           s.first_name,
                           s.last_name,
                           s.mobile_number,
                           c.id AS course_id,
                           COALESCE(c.name, 'General Course') AS course_name,
                           COALESCE(p.inst1, 0.0) AS inst1,
                           COALESCE(p.inst2, 0.0) AS inst2,
                           COALESCE(p.inst3, 0.0) AS inst3,
                           COALESCE(p.inst4, 0.0) AS inst4,
                           COALESCE(p.total_paid, 0.0) AS total_paid,
                           MAX(0.0, (COALESCE(a.agreed_fee, 0.0) - COALESCE(a.discount, 0.0)) - COALESCE(p.total_paid, 0.0)) AS pending_fees,
                           f.friend_name,
                           f.friend_mobile
                    FROM admissions a
                    JOIN students s ON s.id = a.student_id
                    LEFT JOIN admission_courses ac ON ac.admission_id = a.id
                    LEFT JOIN courses c ON c.id = ac.course_id
                    LEFT JOIN (
                        SELECT admission_id,
                               SUM(CASE WHEN installment_number = 1 THEN amount ELSE 0 END) AS inst1,
                               SUM(CASE WHEN installment_number = 2 THEN amount ELSE 0 END) AS inst2,
                               SUM(CASE WHEN installment_number = 3 THEN amount ELSE 0 END) AS inst3,
                               SUM(CASE WHEN installment_number = 4 THEN amount ELSE 0 END) AS inst4,
                               SUM(amount) AS total_paid
                        FROM payments
                        GROUP BY admission_id
                    ) p ON p.admission_id = a.id
                    LEFT JOIN (
                        SELECT 
                            sf.base_student_id,
                            TRIM(s_f.first_name || ' ' || s_f.last_name) AS friend_name,
                            s_f.mobile_number AS friend_mobile
                        FROM (
                            SELECT 
                                student_id AS base_student_id,
                                friend_student_id AS target_friend_id,
                                ROW_NUMBER() OVER (PARTITION BY student_id ORDER BY id ASC) as rn
                            FROM student_friendships
                            WHERE is_active = 1
                            UNION ALL
                            SELECT 
                                friend_student_id AS base_student_id,
                                student_id AS target_friend_id,
                                ROW_NUMBER() OVER (PARTITION BY friend_student_id ORDER BY id ASC) as rn
                            FROM student_friendships
                            WHERE is_active = 1
                        ) sf
                        JOIN students s_f ON s_f.id = sf.target_friend_id
                        WHERE sf.rn = 1
                    ) f ON f.base_student_id = s.id
                    {where_sql}
                    {order_by_sql}
                    LIMIT ? OFFSET ?;
                """

            exec_params = list(params) + [limit_val, offset_val]
            raw_admissions = self.repo.execute_fetchall(sql, tuple(exec_params))
            rows = self._map_report_rows(raw_admissions, start_idx=offset_val + 1)

            # Store in Memory Block Cache
            FeesCacheManager.set_block(chunk_key, rows)

            return {
                "rows": rows,
                "total_count": total_count,
                "offset": offset_val,
                "limit": limit_val,
                "from_cache": False,
            }

    def export_filtered_fees_report_csv(
        self,
        course_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        target_path: Optional[str | Path] = None,
    ) -> Path:
        """Exports all filtered report records (full dataset, not just current page) to CSV."""
        all_rows = self.get_admission_fees_report(
            course_id=course_id,
            status=status,
            search=search,
            sort_by=sort_by,
        )
        return self.export_fees_report_csv(all_rows, target_path=target_path)

    def export_filtered_fees_report_excel(
        self,
        course_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        target_path: Optional[str | Path] = None,
    ) -> Path:
        """Exports all filtered report records to styled Microsoft Excel (.xlsx) workbook."""
        all_rows = self.get_admission_fees_report(
            course_id=course_id,
            status=status,
            search=search,
            sort_by=sort_by,
        )
        return self.export_fees_report_excel(all_rows, target_path=target_path)

    def filter_payments_by_amount(self, target_amount: float, search: Optional[str] = None) -> list[dict[str, Any]]:
        """Filters payments matching exact amount (e.g. ₹500, ₹1000) with in-memory caching."""
        from core.cache.fees_cache import FeesCacheManager

        target_amount_val = round(float(target_amount), 2)
        search_clean = (search or "").strip()
        cache_key = (target_amount_val, search_clean)

        cached_payments = FeesCacheManager.get_payment_filter(cache_key)
        if cached_payments is not None:
            return cached_payments

        with self.unit_of_work():
            clauses = ["p.amount = ?"]
            params = [target_amount_val]

            if search_clean:
                p = f"%{search_clean}%"
                clauses.append("""(
                    s.first_name LIKE ? OR s.last_name LIKE ? OR (s.first_name || ' ' || s.last_name) LIKE ?
                    OR s.mobile_number LIKE ? OR p.collector_name LIKE ? OR c.name LIKE ?
                )""")
                params.extend([p, p, p, p, p, p])

            where_sql = f"WHERE {' AND '.join(clauses)}"

            sql = f"""
                SELECT p.*,
                       s.first_name, s.last_name, s.mobile_number,
                       c.name AS course_name,
                       a.candidate_year, a.candidate_sequence, a.status AS admission_status
                FROM payments p
                JOIN students s ON s.id = p.student_id
                JOIN admissions a ON a.id = p.admission_id
                LEFT JOIN admission_courses ac ON ac.admission_id = a.id
                LEFT JOIN courses c ON c.id = ac.course_id
                {where_sql}
                ORDER BY p.id DESC;
            """
            rows = self.repo.execute_fetchall(sql, tuple(params))
            out = []
            for r in rows:
                c_year = r.get("candidate_year") or 2026
                c_seq = r.get("candidate_sequence") or r["admission_id"]
                try:
                    c_seq_int = int(c_seq)
                    adm_num = f"{c_year}-{c_seq_int:03d}"
                except (ValueError, TypeError):
                    adm_num = f"{c_year}-{c_seq}"
                out.append({
                    "payment_id": r["id"],
                    "admission_number": adm_num,
                    "student_name": f"{r['first_name']} {r['last_name']}".strip(),
                    "mobile_number": r.get("mobile_number") or "—",
                    "course_name": r.get("course_name") or "General Course",
                    "installment_number": r.get("installment_number") or 1,
                    "amount": float(r.get("amount") or 0.0),
                    "payment_mode": r.get("payment_mode") or "CASH",
                    "payment_date": str(r.get("payment_date") or "")[:16],
                    "collector_name": r.get("collector_name") or "—",
                    "transaction_ref": r.get("transaction_ref") or "—",
                })

            FeesCacheManager.set_payment_filter(cache_key, out)
            return out

    def get_fees_kpi_summary(self, course_id: Optional[int] = None) -> dict[str, Any]:
        """
        Calculates and returns pre-aggregated financial KPI metrics
        (total billed, total collected, pending dues, collection rate, installment breakdown)
        with sub-millisecond in-memory caching.
        """
        from core.cache.fees_cache import FeesCacheManager

        cache_key = (course_id,)
        cached_kpi = FeesCacheManager.get_kpi_summary(cache_key)
        if cached_kpi is not None:
            return cached_kpi

        with self.unit_of_work():
            filter_course = course_id is not None and course_id > 0
            course_clause = "AND ac.course_id = ?" if filter_course else ""
            course_params = (course_id,) if filter_course else ()

            # 1. Total Billed Fees & Admissions
            adm_sql = f"""
                SELECT 
                    COUNT(DISTINCT a.id) AS total_admissions,
                    COALESCE(SUM(a.agreed_fee - a.discount), 0.0) AS total_billed_fees
                FROM admissions a
                LEFT JOIN admission_courses ac ON ac.admission_id = a.id
                WHERE a.status != 'CANCELLED'
                {course_clause};
            """
            adm_row = self.repo.execute_fetchone(adm_sql, course_params) or {}
            total_admissions = int(adm_row.get("total_admissions") or 0)
            total_billed_fees = round(float(adm_row.get("total_billed_fees") or 0.0), 2)

            # 2. Total Collected Fees & Installment Breakdown
            pay_sql = f"""
                SELECT 
                    COALESCE(SUM(p.amount), 0.0) AS total_collected_fees,
                    COALESCE(SUM(CASE WHEN p.installment_number = 1 THEN p.amount ELSE 0.0 END), 0.0) AS inst1_total,
                    COALESCE(SUM(CASE WHEN p.installment_number = 2 THEN p.amount ELSE 0.0 END), 0.0) AS inst2_total,
                    COALESCE(SUM(CASE WHEN p.installment_number = 3 THEN p.amount ELSE 0.0 END), 0.0) AS inst3_total,
                    COALESCE(SUM(CASE WHEN p.installment_number = 4 THEN p.amount ELSE 0.0 END), 0.0) AS inst4_total
                FROM payments p
                JOIN admissions a ON a.id = p.admission_id
                LEFT JOIN admission_courses ac ON ac.admission_id = a.id
                WHERE a.status != 'CANCELLED'
                {course_clause};
            """
            pay_row = self.repo.execute_fetchone(pay_sql, course_params) or {}
            total_collected_fees = round(float(pay_row.get("total_collected_fees") or 0.0), 2)
            inst1_total = round(float(pay_row.get("inst1_total") or 0.0), 2)
            inst2_total = round(float(pay_row.get("inst2_total") or 0.0), 2)
            inst3_total = round(float(pay_row.get("inst3_total") or 0.0), 2)
            inst4_total = round(float(pay_row.get("inst4_total") or 0.0), 2)

            # 3. Total Pending Fees & Collection Rate
            total_pending_fees = max(0.0, round(total_billed_fees - total_collected_fees, 2))
            collection_rate_pct = (
                round((total_collected_fees / total_billed_fees) * 100.0, 1)
                if total_billed_fees > 0
                else 0.0
            )

            # 4. Count of Students with Pending Dues
            dues_sql = f"""
                SELECT COUNT(*) AS dues_count
                FROM (
                    SELECT a.id,
                           (a.agreed_fee - a.discount) AS final_fee,
                           COALESCE(SUM(p.amount), 0.0) AS paid
                    FROM admissions a
                    LEFT JOIN admission_courses ac ON ac.admission_id = a.id
                    LEFT JOIN payments p ON p.admission_id = a.id
                    WHERE a.status != 'CANCELLED'
                    {course_clause}
                    GROUP BY a.id
                    HAVING (final_fee - paid) > 0.01
                );
            """
            dues_row = self.repo.execute_fetchone(dues_sql, course_params) or {}
            students_with_dues = int(dues_row.get("dues_count") or 0)

            summary = {
                "course_id": course_id,
                "total_admissions": total_admissions,
                "total_billed_fees": total_billed_fees,
                "total_collected_fees": total_collected_fees,
                "total_pending_fees": total_pending_fees,
                "collection_rate_pct": collection_rate_pct,
                "students_with_dues": students_with_dues,
                "installment_totals": {
                    "inst1": inst1_total,
                    "inst2": inst2_total,
                    "inst3": inst3_total,
                    "inst4": inst4_total,
                },
            }

            FeesCacheManager.set_kpi_summary(cache_key, summary)
            return summary

    def export_fees_report_csv(self, report_rows: list[dict[str, Any]], target_path: Optional[str | Path] = None) -> Path:
        headers = [
            "SR.NO",
            "COURSE NAME",
            "ADMISSION DATE",
            "ADMISSION ID",
            "NAME",
            "MOB NO",
            "ADMISSION STATUS",
            "TOTAL FEES",
            "1ST INSTALLMENT",
            "2ND INSTALLMENT",
            "3RD INSTALLMENT",
            "4TH INSTALLMENT",
            "TOTAL FEES PAID",
            "PENDING FEES",
            "ADDRESS",
            "FRIEND NAME",
            "FRIEND CONTACT NO",
        ]

        csv_rows = []
        for idx, r in enumerate(report_rows, start=1):
            csv_rows.append([
                idx,
                r["course_name"],
                r["admission_date"],
                r["admission_id"],
                r["name"],
                r["mob_no"],
                r["admission_status"],
                f"Rs. {r['total_fees']:,.2f}",
                f"Rs. {r['inst1']:,.2f}" if r["inst1"] > 0 else "—",
                f"Rs. {r['inst2']:,.2f}" if r["inst2"] > 0 else "—",
                f"Rs. {r['inst3']:,.2f}" if r["inst3"] > 0 else "—",
                f"Rs. {r['inst4']:,.2f}" if r["inst4"] > 0 else "—",
                f"Rs. {r['total_paid']:,.2f}",
                f"Rs. {r['pending_fees']:,.2f}",
                r["address"],
                r["friend_name"],
                r["friend_mobile"],
            ])

        default_dir = Path("exports/reports")
        default_dir.mkdir(parents=True, exist_ok=True)
        default_file = default_dir / f"fee_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path = Path(target_path) if target_path else default_file

        return ExcelExporter.export_to_csv(headers=headers, rows=csv_rows, output_path=path)

    def export_fees_report_excel(self, report_rows: list[dict[str, Any]], target_path: Optional[str | Path] = None) -> Path:
        """Exports fee report records into a styled Microsoft Excel (.xlsx) workbook with bold headers and totals."""
        headers = [
            "SR.NO",
            "COURSE NAME",
            "ADMISSION DATE",
            "ADMISSION ID",
            "NAME",
            "MOB NO",
            "ADMISSION STATUS",
            "TOTAL FEES",
            "1ST INSTALLMENT",
            "2ND INSTALLMENT",
            "3RD INSTALLMENT",
            "4TH INSTALLMENT",
            "TOTAL FEES PAID",
            "PENDING FEES",
            "ADDRESS",
            "FRIEND NAME",
            "FRIEND CONTACT NO",
        ]

        rows = []
        for idx, r in enumerate(report_rows, start=1):
            clean_name = str(r.get("name") or "").strip()
            clean_mob = str(r.get("mob_no") or "").strip()
            inst1_val = float(r.get("inst1") or 0.0)
            inst2_val = float(r.get("inst2") or 0.0)
            inst3_val = float(r.get("inst3") or 0.0)
            inst4_val = float(r.get("inst4") or 0.0)

            rows.append([
                idx,
                r.get("course_name") or "General Course",
                str(r.get("admission_date") or "")[:10],
                r.get("admission_id") or "—",
                clean_name or "—",
                clean_mob or "—",
                r.get("admission_status") or "CONFIRMED",
                float(r.get("total_fees") or 0.0),
                inst1_val if inst1_val > 0 else "—",
                inst2_val if inst2_val > 0 else "—",
                inst3_val if inst3_val > 0 else "—",
                inst4_val if inst4_val > 0 else "—",
                float(r.get("total_paid") or 0.0),
                float(r.get("pending_fees") or 0.0),
                r.get("address") or "—",
                r.get("friend_name") or "—",
                r.get("friend_mobile") or "—",
            ])

        default_dir = Path("exports/reports")
        default_dir.mkdir(parents=True, exist_ok=True)
        default_file = default_dir / f"fee_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        path = Path(target_path) if target_path else default_file

        return ExcelExporter.export_to_excel(
            headers=headers,
            rows=rows,
            output_path=path,
            sheet_name="Fee Report",
            title="SUDHARM INFOTECH - ADMISSION & FEE REPORT",
            subtitle=f"Generated on {datetime.now().strftime('%d-%b-%Y %I:%M %p')} • Total Records: {len(report_rows)}",
            include_totals=True,
        )
