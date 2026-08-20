# modules/payments/service.py

from __future__ import annotations
from typing import Optional
from core.service.base import BaseService
from core.logger.service import LogService
from core.exceptions import ValidationError, ServiceError
from modules.payments.dto import PaymentCreateDTO, PaymentDTO, PaymentSummaryDTO
from modules.payments.mapper import PaymentMapper
from modules.payments.repository import PaymentRepository

__all__ = ["PaymentService"]


class PaymentService(BaseService):
    """Business logic for recording and querying payments and installment progression."""

    def __init__(self) -> None:
        self.repository = PaymentRepository()

    def record_payment(self, dto: PaymentCreateDTO) -> int:
        """
        Records an append-only installment payment.
        Must be executed within an active unit of work transaction.
        """
        if not dto.admission_id or dto.admission_id <= 0:
            raise ValidationError("Valid Admission ID is required.")
        if not dto.student_id or dto.student_id <= 0:
            raise ValidationError("Valid Student ID is required.")
        if dto.amount <= 0:
            raise ValidationError("Payment amount must be greater than zero.")
        if not dto.collector_name or not dto.collector_name.strip():
            raise ValidationError("Collector name is required.")

        mode_str = dto.payment_mode.value if hasattr(dto.payment_mode, "value") else str(dto.payment_mode).upper()
        if mode_str not in ("CASH", "UPI", "CARD", "NET_BANKING", "CHEQUE"):
            raise ValidationError(f"Invalid payment mode '{mode_str}'.")

        next_inst = self.repository.get_next_installment_number(dto.admission_id)

        data = {
            "admission_id": dto.admission_id,
            "student_id": dto.student_id,
            "installment_number": next_inst,
            "amount": float(dto.amount),
            "payment_mode": mode_str,
            "collector_id": dto.collector_id,
            "collector_name": dto.collector_name.strip(),
            "transaction_ref": dto.transaction_ref.strip() if dto.transaction_ref else None,
            "remarks": dto.remarks.strip() if dto.remarks else None,
            "created_by": dto.created_by,
        }

        payment_id = self.repository.insert(data)
        if not payment_id or payment_id <= 0:
            raise ServiceError("Failed to record payment transaction.")

        LogService.info(
            f"Payment recorded: ID {payment_id}, Admission {dto.admission_id}, Installment {next_inst}, Amount ₹{dto.amount}",
            context=self.__class__.__name__,
        )
        return payment_id

    def get_payments_for_admission(self, admission_id: int) -> list[PaymentDTO]:
        with self.unit_of_work():
            rows = self.repository.get_by_admission_id(admission_id)
            return [PaymentMapper.to_dto(r) for r in rows]

    def get_payments_for_student(self, student_id: int) -> list[PaymentDTO]:
        with self.unit_of_work():
            rows = self.repository.get_by_student_id(student_id)
            return [PaymentMapper.to_dto(r) for r in rows]

    def get_total_paid(self, admission_id: int) -> float:
        with self.unit_of_work():
            return self.repository.get_total_paid_for_admission(admission_id)

    def get_next_installment(self, admission_id: int) -> int:
        with self.unit_of_work():
            return self.repository.get_next_installment_number(admission_id)
