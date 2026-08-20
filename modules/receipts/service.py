# modules/receipts/service.py

from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Optional

from core.service.base import BaseService
from core.logger.service import LogService
from core.exceptions import ValidationError, ServiceError
from modules.receipts.dto import ReceiptCreateDTO, ReceiptDTO
from modules.receipts.mapper import ReceiptMapper
from modules.receipts.repository import ReceiptRepository
from modules.settings.service import SettingsService
from infrastructure.pdf.receipt_generator import ReceiptPDFGenerator

__all__ = ["ReceiptService"]


class ReceiptService(BaseService):
    """Business logic for generating and managing fee receipts and PDF slips."""

    def __init__(self) -> None:
        self.repository = ReceiptRepository()
        self.settings_service = SettingsService()

    def generate_receipt_number(self, year: Optional[int] = None) -> str:
        """Generates atomic, non-reusable sequential receipt number format: RCP-YYYY-XXXXX."""
        receipt_year = year or datetime.now().year
        seq = self.repository.get_next_sequence_for_year(receipt_year)
        return f"RCP-{receipt_year}-{seq:05d}"

    def create_receipt(self, dto: ReceiptCreateDTO, context_data: Optional[Mapping[str, Any]] = None) -> int:
        """
        Creates an immutable receipt record and renders the vector PDF.
        Must be executed inside an active unit of work transaction.
        """
        if not dto.payment_id or dto.payment_id <= 0:
            raise ValidationError("Valid Payment ID is required for receipt.")
        if not dto.admission_id or dto.admission_id <= 0:
            raise ValidationError("Valid Admission ID is required for receipt.")
        if not dto.student_id or dto.student_id <= 0:
            raise ValidationError("Valid Student ID is required for receipt.")

        # Check existing receipt for this payment
        existing = self.repository.get_by_payment_id(dto.payment_id)
        if existing:
            return int(existing["id"])

        receipt_number = self.generate_receipt_number()
        
        # Prepare PDF generation
        project_root = Path(__file__).resolve().parent.parent.parent
        exports_dir = project_root / "exports" / "receipts"
        pdf_filename = f"receipt_{receipt_number.lower().replace('-', '_')}.pdf"
        pdf_path = exports_dir / pdf_filename

        ctx = dict(context_data or {})
        render_payload = {
            "receipt_number": receipt_number,
            "receipt_date": datetime.now().strftime("%d-%b-%Y %I:%M %p"),
            "student_name": ctx.get("student_name", "Student"),
            "student_id": dto.student_id,
            "candidate_number": ctx.get("candidate_number", f"#{dto.admission_id}"),
            "admission_id": dto.admission_id,
            "course_name": ctx.get("course_name", "Course"),
            "installment_number": dto.installment_number,
            "amount_paid": dto.amount_paid,
            "total_course_fee": dto.total_course_fee,
            "total_paid_till_now": dto.total_paid_till_now,
            "pending_amount": dto.pending_amount,
            "payment_mode": dto.payment_mode,
            "collector_name": dto.collector_name,
        }

        try:
            profile = self.settings_service.get_institute_profile()
            ReceiptPDFGenerator.generate_receipt_pdf(render_payload, pdf_path, profile)
        except Exception as ex:
            LogService.warning(f"Receipt PDF rendering note: {ex}", context=self.__class__.__name__)
            # Fallback path if rendering fails
            pdf_path = None

        data = {
            "payment_id": dto.payment_id,
            "admission_id": dto.admission_id,
            "student_id": dto.student_id,
            "receipt_number": receipt_number,
            "total_course_fee": dto.total_course_fee,
            "amount_paid": dto.amount_paid,
            "total_paid_till_now": dto.total_paid_till_now,
            "pending_amount": dto.pending_amount,
            "installment_number": dto.installment_number,
            "payment_mode": dto.payment_mode,
            "collector_name": dto.collector_name,
            "pdf_path": str(pdf_path) if pdf_path else None,
            "generated_by": dto.generated_by,
        }

        receipt_id = self.repository.insert(data)
        if not receipt_id or receipt_id <= 0:
            raise ServiceError("Failed to persist receipt record.")

        LogService.info(
            f"Receipt created: ID {receipt_id}, Number {receipt_number}, Amount ₹{dto.amount_paid}",
            context=self.__class__.__name__,
        )
        return receipt_id

    def get_receipt(self, receipt_id: int) -> ReceiptDTO:
        with self.unit_of_work():
            row = self.repository.get_by_id(receipt_id)
            if not row:
                raise ValidationError(f"Receipt with ID {receipt_id} not found.")
            return ReceiptMapper.to_dto(row)

    def get_receipt_by_payment(self, payment_id: int) -> Optional[ReceiptDTO]:
        with self.unit_of_work():
            row = self.repository.get_by_payment_id(payment_id)
            return ReceiptMapper.to_dto(row) if row else None

    def get_receipts_for_admission(self, admission_id: int) -> list[ReceiptDTO]:
        with self.unit_of_work():
            rows = self.repository.get_by_admission_id(admission_id)
            return [ReceiptMapper.to_dto(r) for r in rows]

    def get_receipts_for_student(self, student_id: int) -> list[ReceiptDTO]:
        with self.unit_of_work():
            rows = self.repository.get_by_student_id(student_id)
            return [ReceiptMapper.to_dto(r) for r in rows]
