# modules/receipts/dto.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

__all__ = ["ReceiptCreateDTO", "ReceiptDTO"]


@dataclass(frozen=True)
class ReceiptCreateDTO:
    """Strict contract for generating a new receipt record."""
    payment_id: int
    admission_id: int
    student_id: int
    total_course_fee: float
    amount_paid: float
    total_paid_till_now: float
    pending_amount: float
    installment_number: int
    payment_mode: str
    collector_name: str
    generated_by: Optional[int] = None
    pdf_path: Optional[str] = None


@dataclass(frozen=True)
class ReceiptDTO:
    """Read contract for a fee receipt."""
    id: int
    payment_id: int
    admission_id: int
    student_id: int
    receipt_number: str
    receipt_date: str
    total_course_fee: float
    amount_paid: float
    total_paid_till_now: float
    pending_amount: float
    installment_number: int
    payment_mode: str
    collector_name: str
    pdf_path: Optional[str] = None
    generated_at: Optional[str] = None
    generated_by: Optional[int] = None

    @property
    def formatted_installment(self) -> str:
        return f"Installment {self.installment_number:02d}"
