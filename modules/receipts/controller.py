# modules/receipts/controller.py

from __future__ import annotations
from typing import Any, Mapping, Optional
from modules.receipts.service import ReceiptService
from modules.receipts.dto import ReceiptCreateDTO, ReceiptDTO

__all__ = ["ReceiptController"]


class ReceiptController:
    """Application layer pass-through for Receipts."""

    def __init__(self) -> None:
        self.service = ReceiptService()

    def get_receipt(self, receipt_id: int) -> ReceiptDTO:
        return self.service.get_receipt(receipt_id)

    def get_receipt_by_payment(self, payment_id: int) -> Optional[ReceiptDTO]:
        return self.service.get_receipt_by_payment(payment_id)

    def get_receipts_for_admission(self, admission_id: int) -> list[ReceiptDTO]:
        return self.service.get_receipts_for_admission(admission_id)

    def get_receipts_for_student(self, student_id: int) -> list[ReceiptDTO]:
        return self.service.get_receipts_for_student(student_id)
