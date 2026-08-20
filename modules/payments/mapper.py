# modules/payments/mapper.py

from __future__ import annotations
from typing import Any, Mapping
from modules.payments.dto import PaymentDTO

__all__ = ["PaymentMapper"]


class PaymentMapper:
    @staticmethod
    def to_dto(row: Mapping[str, Any]) -> PaymentDTO:
        return PaymentDTO(
            id=int(row["id"]),
            admission_id=int(row["admission_id"]),
            student_id=int(row["student_id"]),
            installment_number=int(row["installment_number"]),
            amount=float(row["amount"]),
            payment_mode=str(row["payment_mode"]),
            payment_date=str(row["payment_date"]),
            collector_name=str(row["collector_name"]),
            collector_id=int(row["collector_id"]) if row.get("collector_id") else None,
            transaction_ref=str(row["transaction_ref"]) if row.get("transaction_ref") else None,
            remarks=str(row["remarks"]) if row.get("remarks") else None,
            created_at=str(row["created_at"]) if row.get("created_at") else None,
        )
