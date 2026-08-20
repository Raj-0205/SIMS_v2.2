# modules/receipts/repository.py

from __future__ import annotations
from typing import Any, Optional
from core.database.repository import BaseRepository

__all__ = ["ReceiptRepository"]


class ReceiptRepository(BaseRepository):
    """Persistence for fee payment receipts."""

    def insert(self, data: dict[str, Any]) -> int:
        sql = """
            INSERT INTO receipts (
                payment_id, admission_id, student_id, receipt_number,
                total_course_fee, amount_paid, total_paid_till_now,
                pending_amount, installment_number, payment_mode,
                collector_name, pdf_path, generated_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        params = (
            data["payment_id"],
            data["admission_id"],
            data["student_id"],
            data["receipt_number"],
            data["total_course_fee"],
            data["amount_paid"],
            data["total_paid_till_now"],
            data["pending_amount"],
            data["installment_number"],
            data["payment_mode"],
            data["collector_name"],
            data.get("pdf_path"),
            data.get("generated_by"),
        )
        return self.execute_insert(sql, params)

    def get_by_id(self, receipt_id: int) -> Optional[dict[str, Any]]:
        sql = "SELECT * FROM receipts WHERE id = ? LIMIT 1;"
        return self.execute_fetchone(sql, (receipt_id,))

    def get_by_payment_id(self, payment_id: int) -> Optional[dict[str, Any]]:
        sql = "SELECT * FROM receipts WHERE payment_id = ? LIMIT 1;"
        return self.execute_fetchone(sql, (payment_id,))

    def get_by_receipt_number(self, receipt_no: str) -> Optional[dict[str, Any]]:
        sql = "SELECT * FROM receipts WHERE receipt_number = ? LIMIT 1;"
        return self.execute_fetchone(sql, (receipt_no,))

    def get_by_admission_id(self, admission_id: int) -> list[dict[str, Any]]:
        sql = "SELECT * FROM receipts WHERE admission_id = ? ORDER BY id ASC;"
        return self.execute_fetchall(sql, (admission_id,))

    def get_by_student_id(self, student_id: int) -> list[dict[str, Any]]:
        sql = "SELECT * FROM receipts WHERE student_id = ? ORDER BY id DESC;"
        return self.execute_fetchall(sql, (student_id,))

    def get_next_sequence_for_year(self, year: int) -> int:
        """Finds max sequential receipt number for the year to ensure sequential non-reuse."""
        sql = """
            SELECT COUNT(*) AS total_for_year
            FROM receipts
            WHERE receipt_number LIKE ?;
        """
        prefix = f"RCP-{year}-%"
        row = self.execute_fetchone(sql, (prefix,))
        return (int(row["total_for_year"]) if row and row["total_for_year"] is not None else 0) + 1
