# modules/payments/repository.py

from __future__ import annotations
from typing import Any, Optional
from core.database.repository import BaseRepository

__all__ = ["PaymentRepository"]


class PaymentRepository(BaseRepository):
    """Data persistence for payments and installments."""

    def insert(self, data: dict[str, Any]) -> int:
        sql = """
            INSERT INTO payments (
                admission_id, student_id, installment_number, amount,
                payment_mode, collector_id, collector_name, transaction_ref,
                remarks, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        params = (
            data["admission_id"],
            data["student_id"],
            data["installment_number"],
            data["amount"],
            data["payment_mode"],
            data.get("collector_id"),
            data["collector_name"],
            data.get("transaction_ref"),
            data.get("remarks"),
            data.get("created_by"),
        )
        return self.execute_insert(sql, params)

    def get_by_id(self, payment_id: int) -> Optional[dict[str, Any]]:
        sql = "SELECT * FROM payments WHERE id = ? LIMIT 1;"
        return self.execute_fetchone(sql, (payment_id,))

    def get_by_admission_id(self, admission_id: int) -> list[dict[str, Any]]:
        sql = "SELECT * FROM payments WHERE admission_id = ? ORDER BY installment_number ASC;"
        return self.execute_fetchall(sql, (admission_id,))

    def get_by_student_id(self, student_id: int) -> list[dict[str, Any]]:
        sql = "SELECT * FROM payments WHERE student_id = ? ORDER BY payment_date DESC;"
        return self.execute_fetchall(sql, (student_id,))

    def get_total_paid_for_admission(self, admission_id: int) -> float:
        sql = "SELECT COALESCE(SUM(amount), 0.0) AS total_paid FROM payments WHERE admission_id = ?;"
        row = self.execute_fetchone(sql, (admission_id,))
        return float(row["total_paid"]) if row and row["total_paid"] is not None else 0.0

    def get_next_installment_number(self, admission_id: int) -> int:
        sql = "SELECT COALESCE(MAX(installment_number), 0) + 1 AS next_inst FROM payments WHERE admission_id = ?;"
        row = self.execute_fetchone(sql, (admission_id,))
        return int(row["next_inst"]) if row and row["next_inst"] is not None else 1

    def get_today_collection(self) -> float:
        sql = "SELECT COALESCE(SUM(amount), 0.0) AS total FROM payments WHERE DATE(payment_date) = DATE('now', 'localtime');"
        row = self.execute_fetchone(sql)
        return float(row["total"]) if row and row["total"] is not None else 0.0

    def get_month_collection(self) -> float:
        sql = "SELECT COALESCE(SUM(amount), 0.0) AS total FROM payments WHERE strftime('%Y-%m', payment_date) = strftime('%Y-%m', 'now', 'localtime');"
        row = self.execute_fetchone(sql)
        return float(row["total"]) if row and row["total"] is not None else 0.0

    def get_recent_payments(self, limit: int = 10) -> list[dict[str, Any]]:
        sql = """
            SELECT p.*, s.first_name, s.last_name, a.candidate_year, a.candidate_sequence, c.name as course_name
            FROM payments p
            JOIN students s ON s.id = p.student_id
            JOIN admissions a ON a.id = p.admission_id
            LEFT JOIN admission_courses ac ON ac.admission_id = a.id
            LEFT JOIN courses c ON c.id = ac.course_id
            ORDER BY p.payment_date DESC
            LIMIT ?;
        """
        return self.execute_fetchall(sql, (limit,))
