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

    def get_admission_fees_report(
        self,
        course_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        with self.unit_of_work():
            clauses = []
            params = []

            if search and search.strip():
                p = f"%{search.strip()}%"
                clauses.append("""(
                    s.first_name LIKE ? OR s.last_name LIKE ? OR (s.first_name || ' ' || s.last_name) LIKE ?
                    OR s.mobile_number LIKE ? OR CAST(a.id AS TEXT) LIKE ? OR c.name LIKE ?
                    OR (CAST(a.candidate_year AS TEXT) || '-' || printf('%03d', a.candidate_sequence)) LIKE ?
                )""")
                params.extend([p, p, p, p, p, p, p])

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

            # Single aggregated SQL query eliminating N+1 loop queries (SIMS-PERF-01)
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
                       c.name AS course_name,
                       COALESCE((SELECT SUM(amount) FROM payments WHERE admission_id = a.id AND installment_number = 1), 0.0) AS inst1,
                       COALESCE((SELECT SUM(amount) FROM payments WHERE admission_id = a.id AND installment_number = 2), 0.0) AS inst2,
                       COALESCE((SELECT SUM(amount) FROM payments WHERE admission_id = a.id AND installment_number = 3), 0.0) AS inst3,
                       COALESCE((SELECT SUM(amount) FROM payments WHERE admission_id = a.id AND installment_number = 4), 0.0) AS inst4,
                       COALESCE((SELECT SUM(amount) FROM payments WHERE admission_id = a.id), 0.0) AS total_paid,
                       (
                           SELECT TRIM(s_f.first_name || ' ' || s_f.last_name)
                           FROM student_friendships sf
                           JOIN students s_f ON s_f.id = (CASE WHEN sf.student_id = s.id THEN sf.friend_student_id ELSE sf.student_id END)
                           WHERE (sf.student_id = s.id OR sf.friend_student_id = s.id) AND sf.is_active = 1
                           LIMIT 1
                       ) AS friend_name,
                       (
                           SELECT s_f.mobile_number
                           FROM student_friendships sf
                           JOIN students s_f ON s_f.id = (CASE WHEN sf.student_id = s.id THEN sf.friend_student_id ELSE sf.student_id END)
                           WHERE (sf.student_id = s.id OR sf.friend_student_id = s.id) AND sf.is_active = 1
                           LIMIT 1
                       ) AS friend_mobile
                FROM admissions a
                JOIN students s ON s.id = a.student_id
                LEFT JOIN admission_courses ac ON ac.admission_id = a.id
                LEFT JOIN courses c ON c.id = ac.course_id
                {where_sql}
                ORDER BY a.id DESC;
            """

            raw_admissions = self.repo.execute_fetchall(sql, tuple(params))
            results = []

            for idx, adm in enumerate(raw_admissions, start=1):
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

            if sort_by:
                if sort_by == "INST1":
                    results.sort(key=lambda x: x["inst1"], reverse=True)
                elif sort_by == "INST2":
                    results.sort(key=lambda x: x["inst2"], reverse=True)
                elif sort_by == "INST3":
                    results.sort(key=lambda x: x["inst3"], reverse=True)
                elif sort_by == "INST4":
                    results.sort(key=lambda x: x["inst4"], reverse=True)
                elif sort_by == "PAID":
                    results.sort(key=lambda x: x["total_paid"], reverse=True)
                elif sort_by == "PENDING":
                    results.sort(key=lambda x: x["pending_fees"], reverse=True)

            return results


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

        metadata = {
            "Module": "SIMS v2.2 Admission & Fee Reporting System",
            "Export Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Total Records": len(report_rows),
        }

        return ExcelExporter.export_to_csv(headers=headers, rows=csv_rows, output_path=path, metadata=metadata)
