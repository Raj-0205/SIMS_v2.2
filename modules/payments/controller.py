# modules/payments/controller.py

from __future__ import annotations
from typing import Any, Mapping
from modules.payments.service import PaymentService
from modules.payments.dto import PaymentCreateDTO, PaymentDTO

__all__ = ["PaymentController"]


class PaymentController:
    """Application layer pass-through for payments."""

    def __init__(self) -> None:
        self.service = PaymentService()

    def record_payment(self, raw_data: Mapping[str, Any]) -> int:
        dto = PaymentCreateDTO(
            admission_id=int(raw_data["admission_id"]),
            student_id=int(raw_data["student_id"]),
            amount=float(raw_data["amount"]),
            payment_mode=str(raw_data["payment_mode"]),
            collector_name=str(raw_data["collector_name"]),
            collector_id=int(raw_data["collector_id"]) if raw_data.get("collector_id") else None,
            transaction_ref=str(raw_data["transaction_ref"]) if raw_data.get("transaction_ref") else None,
            remarks=str(raw_data["remarks"]) if raw_data.get("remarks") else None,
            created_by=int(raw_data["created_by"]) if raw_data.get("created_by") else None,
        )
        return self.service.record_payment(dto)

    def get_payments_for_admission(self, admission_id: int) -> list[PaymentDTO]:
        return self.service.get_payments_for_admission(admission_id)

    def get_payments_for_student(self, student_id: int) -> list[PaymentDTO]:
        return self.service.get_payments_for_student(student_id)

    def get_total_paid(self, admission_id: int) -> float:
        return self.service.get_total_paid(admission_id)
