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
                clauses.append("a.status IN ('DRAFT', 'REGISTERED')")
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
                "admission_id_raw": int(adm_id),
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

    def _map_bulk_admission_record(self, raw: dict[str, Any]) -> dict[str, Any]:
        adm_id_raw = int(raw["admission_id_raw"])
        inst1 = float(raw.get("inst1") or 0.0)
        inst2 = float(raw.get("inst2") or 0.0)
        inst3 = float(raw.get("inst3") or 0.0)
        inst4 = float(raw.get("inst4") or 0.0)
        total_paid = float(raw.get("total_paid") or 0.0)

        agreed_fee = float(raw.get("agreed_fee") or 0.0)
        discount = float(raw.get("discount") or 0.0)
        total_fees = agreed_fee - discount
        pending_fees = max(0.0, total_fees - total_paid)

        friend_name = (raw.get("friend_name") or "").strip() or "—"
        friend_mobile = raw.get("friend_mobile") or "—"

        c_year = raw.get("candidate_year") or 2026
        c_seq = raw.get("candidate_sequence") or adm_id_raw
        try:
            c_seq_int = int(c_seq)
            adm_num = f"{c_year}-{c_seq_int:03d}"
        except (ValueError, TypeError):
            adm_num = f"{c_year}-{c_seq}"

        first_name = (raw.get("first_name") or "").strip()
        last_name = (raw.get("last_name") or "").strip()
        full_name = f"{first_name} {last_name}".strip()
        mobile = raw.get("mobile_number") or "—"

        all_courses_str = raw.get("all_courses") or raw.get("course_name") or ""
        all_course_ids_raw = raw.get("all_course_ids") or ""
        all_course_ids_set = set()
        if raw.get("course_id"):
            all_course_ids_set.add(int(raw["course_id"]))
        for cid in str(all_course_ids_raw).split(","):
            cid_s = cid.strip()
            if cid_s.isdigit():
                all_course_ids_set.add(int(cid_s))

        course_map = {}
        if raw.get("course_id") and raw.get("course_name"):
            course_map[int(raw["course_id"])] = str(raw["course_name"])

        friend_sid = int(raw["friend_student_id"]) if raw.get("friend_student_id") else None

        return {
            "admission_id_raw": adm_id_raw,
            "student_id": int(raw["student_id"]) if raw.get("student_id") else 0,
            "course_id": int(raw["course_id"]) if raw.get("course_id") else None,
            "all_course_ids": all_course_ids_set,
            "all_courses": all_courses_str,
            "course_map": course_map,
            "candidate_year": c_year,
            "candidate_sequence": c_seq,
            "admission_id": adm_num,
            "admission_date": str(raw.get("admission_date") or "")[:10],
            "admission_status": raw.get("admission_status") or "REGISTERED",
            "first_name": first_name,
            "last_name": last_name,
            "name": full_name,
            "mob_no": mobile,
            "mobile_number": mobile,
            "course_name": raw.get("course_name") or "General Course",
            "agreed_fee": agreed_fee,
            "discount": discount,
            "total_fees": total_fees,
            "inst1": inst1,
            "inst2": inst2,
            "inst3": inst3,
            "inst4": inst4,
            "total_paid": total_paid,
            "pending_fees": pending_fees,
            "address": raw.get("address") or raw.get("village") or "—",
            "friend_student_id": friend_sid,
            "friend_name": friend_name,
            "friend_mobile": friend_mobile,
        }

    def _fetch_bulk_admission_fees_dataset(self) -> list[dict[str, Any]]:
        """
        Executes single bulk query fetching all admissions, payments, courses, and friends.
        R1 First-Access Bulk Preload.
        """
        with self.unit_of_work():
            sql = """
                SELECT a.id AS admission_id_raw,
                       a.id AS admission_id,
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
                       f.friend_student_id,
                       f.friend_name,
                       f.friend_mobile,
                       ac_all.all_courses,
                       ac_all.all_course_ids
                FROM admissions a
                JOIN students s ON s.id = a.student_id
                LEFT JOIN admission_courses ac ON ac.admission_id = a.id
                LEFT JOIN courses c ON c.id = ac.course_id
                LEFT JOIN (
                    SELECT ac2.admission_id,
                           GROUP_CONCAT(c2.name, '|||') AS all_courses,
                           GROUP_CONCAT(ac2.course_id, ',') AS all_course_ids
                    FROM admission_courses ac2
                    JOIN courses c2 ON c2.id = ac2.course_id
                    GROUP BY ac2.admission_id
                ) ac_all ON ac_all.admission_id = a.id
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
                        sf.target_friend_id AS friend_student_id,
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
                GROUP BY a.id
                ORDER BY a.id DESC;
            """
            raw_admissions = self.repo.execute_fetchall(sql)
            return [self._map_bulk_admission_record(raw) for raw in raw_admissions]

    def fetch_single_admission_fees_record(self, admission_id: int) -> Optional[dict[str, Any]]:
        """
        Fetches a single admission record formatted for targeted cache updates.
        """
        with self.unit_of_work():
            sql = """
                SELECT a.id AS admission_id_raw,
                       a.id AS admission_id,
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
                       f.friend_student_id,
                       f.friend_name,
                       f.friend_mobile,
                       ac_all.all_courses,
                       ac_all.all_course_ids
                FROM admissions a
                JOIN students s ON s.id = a.student_id
                LEFT JOIN admission_courses ac ON ac.admission_id = a.id
                LEFT JOIN courses c ON c.id = ac.course_id
                LEFT JOIN (
                    SELECT ac2.admission_id,
                           GROUP_CONCAT(c2.name, '|||') AS all_courses,
                           GROUP_CONCAT(ac2.course_id, ',') AS all_course_ids
                    FROM admission_courses ac2
                    JOIN courses c2 ON c2.id = ac2.course_id
                    GROUP BY ac2.admission_id
                ) ac_all ON ac_all.admission_id = a.id
                LEFT JOIN (
                    SELECT admission_id,
                           SUM(CASE WHEN installment_number = 1 THEN amount ELSE 0 END) AS inst1,
                           SUM(CASE WHEN installment_number = 2 THEN amount ELSE 0 END) AS inst2,
                           SUM(CASE WHEN installment_number = 3 THEN amount ELSE 0 END) AS inst3,
                           SUM(CASE WHEN installment_number = 4 THEN amount ELSE 0 END) AS inst4,
                           SUM(amount) AS total_paid
                    FROM payments
                    WHERE admission_id = ?
                    GROUP BY admission_id
                ) p ON p.admission_id = a.id
                LEFT JOIN (
                    SELECT 
                        sf.base_student_id,
                        sf.target_friend_id AS friend_student_id,
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
                WHERE a.id = ?
                GROUP BY a.id
                LIMIT 1;
            """
            raw = self.repo.execute_fetchone(sql, (admission_id, admission_id))
            if not raw:
                return None
            return self._map_bulk_admission_record(raw)

    def get_admission_fees_report(
        self,
        course_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Returns full unpaginated admission fees report rows (legacy compatible with caching)."""
        from core.cache.fees_cache import FeesCacheManager

        if not FeesCacheManager.is_loaded():
            bulk_dataset = self._fetch_bulk_admission_fees_dataset()
            FeesCacheManager.bulk_preload(bulk_dataset)

        rows = FeesCacheManager.query_all_preloaded(
            course_id=course_id,
            status=status,
            search=search,
            sort_by=sort_by,
        )
        if rows is not None:
            return rows

        bulk_dataset = self._fetch_bulk_admission_fees_dataset()
        FeesCacheManager.bulk_preload(bulk_dataset)
        return FeesCacheManager.query_all_preloaded(
            course_id=course_id,
            status=status,
            search=search,
            sort_by=sort_by,
        ) or []

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
        R1 First-Access Bulk Preload + R2 Subsequent Cached Reads.
        """
        from core.cache.fees_cache import FeesCacheManager

        page_val = max(1, page)
        page_size_val = max(1, page_size)

        if not FeesCacheManager.is_loaded():
            bulk_dataset = self._fetch_bulk_admission_fees_dataset()
            FeesCacheManager.bulk_preload(bulk_dataset)
            res = FeesCacheManager.query_preloaded(
                course_id=course_id,
                status=status,
                search=search,
                sort_by=sort_by,
                page=page_val,
                page_size=page_size_val,
            )
            if res is not None:
                res["from_cache"] = False
                return res

        res = FeesCacheManager.query_preloaded(
            course_id=course_id,
            status=status,
            search=search,
            sort_by=sort_by,
            page=page_val,
            page_size=page_size_val,
        )
        if res is not None:
            return res

        bulk_dataset = self._fetch_bulk_admission_fees_dataset()
        FeesCacheManager.bulk_preload(bulk_dataset)
        return FeesCacheManager.query_preloaded(
            course_id=course_id,
            status=status,
            search=search,
            sort_by=sort_by,
            page=page_val,
            page_size=page_size_val,
        ) or {
            "rows": [],
            "total_count": 0,
            "page": page_val,
            "page_size": page_size_val,
            "total_pages": 1,
            "from_cache": True,
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
        Retrieves a single micro-chunk of the fees report
        for progressive streaming with continuous sequential sr_no and total count.
        """
        from core.cache.fees_cache import FeesCacheManager

        offset_val = max(0, offset)
        limit_val = max(1, limit)

        if not FeesCacheManager.is_loaded():
            bulk_dataset = self._fetch_bulk_admission_fees_dataset()
            FeesCacheManager.bulk_preload(bulk_dataset)
            res = FeesCacheManager.query_chunk_preloaded(
                course_id=course_id,
                status=status,
                search=search,
                sort_by=sort_by,
                offset=offset_val,
                limit=limit_val,
            )
            if res is not None:
                res["from_cache"] = False
                return res

        res = FeesCacheManager.query_chunk_preloaded(
            course_id=course_id,
            status=status,
            search=search,
            sort_by=sort_by,
            offset=offset_val,
            limit=limit_val,
        )
        if res is not None:
            return res

        bulk_dataset = self._fetch_bulk_admission_fees_dataset()
        FeesCacheManager.bulk_preload(bulk_dataset)
        return FeesCacheManager.query_chunk_preloaded(
            course_id=course_id,
            status=status,
            search=search,
            sort_by=sort_by,
            offset=offset_val,
            limit=limit_val,
        ) or {
            "rows": [],
            "total_count": 0,
            "offset": offset_val,
            "limit": limit_val,
            "from_cache": True,
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
                    "admission_id": r["admission_id"],
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

        if not FeesCacheManager.is_loaded():
            bulk_dataset = self._fetch_bulk_admission_fees_dataset()
            FeesCacheManager.bulk_preload(bulk_dataset)

        kpi = FeesCacheManager.get_kpi_summary_preloaded(course_id)
        if kpi is not None:
            return kpi

        bulk_dataset = self._fetch_bulk_admission_fees_dataset()
        FeesCacheManager.bulk_preload(bulk_dataset)
        return FeesCacheManager.get_kpi_summary_preloaded(course_id) or {}

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
