# modules/receipts/mapper.py

from __future__ import annotations
from typing import Any, Mapping
from modules.receipts.dto import ReceiptDTO

__all__ = ["ReceiptMapper"]


class ReceiptMapper:
    @staticmethod
    def to_dto(row: Mapping[str, Any]) -> ReceiptDTO:
        return ReceiptDTO(
            id=int(row["id"]),
            payment_id=int(row["payment_id"]),
            admission_id=int(row["admission_id"]),
            student_id=int(row["student_id"]),
            receipt_number=str(row["receipt_number"]),
            receipt_date=str(row["receipt_date"]),
            total_course_fee=float(row["total_course_fee"]),
            amount_paid=float(row["amount_paid"]),
            total_paid_till_now=float(row["total_paid_till_now"]),
            pending_amount=float(row["pending_amount"]),
            installment_number=int(row["installment_number"]),
            payment_mode=str(row["payment_mode"]),
            collector_name=str(row["collector_name"]),
            pdf_path=str(row["pdf_path"]) if row.get("pdf_path") else None,
            generated_at=str(row["generated_at"]) if row.get("generated_at") else None,
            generated_by=int(row["generated_by"]) if row.get("generated_by") else None,
        )
