# modules/payments/dto.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from modules.payments.constants import PaymentMode

__all__ = ["PaymentCreateDTO", "PaymentDTO", "PaymentSummaryDTO"]


@dataclass(frozen=True)
class PaymentCreateDTO:
    """Strict DTO for creating a payment transaction."""
    admission_id: int
    student_id: int
    amount: float
    payment_mode: PaymentMode | str
    collector_name: str
    collector_id: Optional[int] = None
    transaction_ref: Optional[str] = None
    remarks: Optional[str] = None
    created_by: Optional[int] = None


@dataclass(frozen=True)
class PaymentDTO:
    """Read contract for a recorded payment."""
    id: int
    admission_id: int
    student_id: int
    installment_number: int
    amount: float
    payment_mode: str
    payment_date: str
    collector_name: str
    collector_id: Optional[int] = None
    transaction_ref: Optional[str] = None
    remarks: Optional[str] = None
    created_at: Optional[str] = None

    @property
    def formatted_installment(self) -> str:
        return f"Installment {self.installment_number:02d}"


@dataclass(frozen=True)
class PaymentSummaryDTO:
    """Summary of financial status for an admission."""
    admission_id: int
    agreed_fee: float
    discount: float
    final_fee: float
    total_paid: float
    pending_amount: float
    installments_count: int
    is_fully_paid: bool
