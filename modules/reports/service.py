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
            adm_num = f"{c_year}-{c_seq:03d}"

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
        """Returns full unpaginated admission fees report rows (legacy compatible)."""
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
            return self._map_report_rows(raw_admissions, start_idx=1)

    def get_admission_fees_report_paginated(
        self,
        course_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """Returns paginated fees report with metadata and sequential sr_no."""
        with self.unit_of_work():
            where_sql, params = self._build_fees_filter_clauses(course_id, status, search)

            # Count total matching records
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

            page_val = max(1, page)
            page_size_val = max(1, page_size)
            offset_val = (page_val - 1) * page_size_val
            total_pages = max(1, (total_count + page_size_val - 1) // page_size_val)

            order_by_sql = self._resolve_sort_order(sort_by)

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

            return {
                "rows": rows,
                "total_count": total_count,
                "page": page_val,
                "page_size": page_size_val,
                "total_pages": total_pages,
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
        """Filters payments matching exact amount (e.g. ₹500, ₹1000)."""
        with self.unit_of_work():
            clauses = ["p.amount = ?"]
            params = [target_amount]

            if search and search.strip():
                p = f"%{search.strip()}%"
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
                out.append({
                    "payment_id": r["id"],
                    "admission_number": f"{c_year}-{c_seq:03d}",
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
            return out

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
