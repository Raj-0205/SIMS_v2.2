# modules/payments/service.py

from __future__ import annotations
from typing import Optional
from datetime import datetime
from core.service.base import BaseService
from core.logger.service import LogService
from core.exceptions import ValidationError, ServiceError
from modules.payments.dto import PaymentCreateDTO, PaymentDTO, PaymentSummaryDTO
from modules.payments.mapper import PaymentMapper
from modules.payments.repository import PaymentRepository
from modules.admission.repository import AdmissionRepository
from modules.receipts.service import ReceiptService
from modules.receipts.dto import ReceiptCreateDTO
from modules.admission.constants import AdmissionStatus
from modules.admission.activity_log_repository import ActivityLogRepository



__all__ = ["PaymentService"]


class PaymentService(BaseService):
    """
    Centralized financial business service for recording, validating,
    and managing all payments, installment progression, receipts, and status lifecycles.
    """

    MIN_CONFIRMATION_AMOUNT = 500.0

    def __init__(self) -> None:
        self.repository = PaymentRepository()
        self.admission_repo = AdmissionRepository()
        self.receipt_service = ReceiptService()
        self.activity_repo = ActivityLogRepository()

    def record_payment(self, dto: PaymentCreateDTO) -> int:
        """
        Records an append-only installment payment.
        Central financial SSOT enforcing:
        1. Valid admission existence & ownership
        2. Admission not CANCELLED or COMPLETED
        3. Payment floor rules (Initial >= ₹500 unless pending < ₹500; Subsequent > 0)
        4. Strict overpayment prevention (amount <= pending_balance)
        5. Sequential installment numbering
        6. Atomic payment row insertion
        7. Status progression (DRAFT/REGISTERED -> CONFIRMED -> COMPLETED)
        8. Atomic Receipt creation and Vector PDF generation
        9. Audited activity logging
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

        # Transaction Reference Format & Anti-Fraud Validation
        clean_tx_ref = dto.transaction_ref.strip() if dto.transaction_ref else None
        if mode_str in ("UPI", "NET_BANKING"):
            if mode_str == "UPI" and not clean_tx_ref:
                raise ValidationError("Bank UTR / Transaction Reference Number is mandatory for UPI payments.")
            if clean_tx_ref:
                if len(clean_tx_ref) != 12 or not clean_tx_ref.isdigit():
                    raise ValidationError(
                        f"Invalid Transaction Reference '{clean_tx_ref}'. Bank UTR / UPI Reference Number must be exactly 12 numeric digits."
                    )
                dummy_refs = {
                    "000000000000", "111111111111", "222222222222", "333333333333",
                    "444444444444", "555555555555", "666666666666", "777777777777",
                    "888888888888", "999999999999", "123456789012"
                }
                if clean_tx_ref in dummy_refs:
                    raise ValidationError(
                        f"Invalid Transaction Reference '{clean_tx_ref}'. Dummy reference numbers are not permitted."
                    )
        elif clean_tx_ref:
            dummy_refs = {
                "123", "1234", "12345", "123456", "0000", "000000", "000000000000",
                "test", "testing", "dummy", "sample", "na", "n/a", "cash", "upi", "none", "null", "nil"
            }
            if clean_tx_ref.lower() in dummy_refs or len(clean_tx_ref) < 4:
                raise ValidationError(
                    f"Invalid Transaction Reference '{clean_tx_ref}'. Please enter a valid transaction reference."
                )

        with self.unit_of_work():
            # Duplicate Transaction Replay Prevention
            if clean_tx_ref:
                existing_tx = self.repository.get_by_transaction_ref(clean_tx_ref)
                if existing_tx:
                    dup_adm = existing_tx.get("admission_id")
                    dup_date = existing_tx.get("payment_date") or "earlier date"
                    raise ValidationError(
                        f"Security Alert: Transaction Reference / UTR '{clean_tx_ref}' has already been recorded for Admission #{dup_adm} on {dup_date}. Duplicate payment reference cannot be reused."
                    )

            # 1. Fetch & Validate Admission
            adm = self.admission_repo.get_by_id(dto.admission_id)
            if not adm:
                raise ValidationError(f"Admission with ID {dto.admission_id} not found.")

            if int(adm["student_id"]) != int(dto.student_id):
                raise ValidationError("Payment student ID does not match the admission record.")

            current_status = str(adm["status"]).upper()
            if current_status == AdmissionStatus.CANCELLED.value:
                raise ValidationError(f"Cannot record payment for a CANCELLED admission (#{dto.admission_id}).")
            if current_status == AdmissionStatus.COMPLETED.value:
                raise ValidationError(f"Admission (#{dto.admission_id}) is already COMPLETED and fully paid.")

            # 2. Financial Calculations
            agreed_fee = float(adm.get("agreed_fee") or 0.0)
            discount = float(adm.get("discount") or 0.0)
            final_fee = max(0.0, agreed_fee - discount)
            total_paid_so_far = float(self.repository.get_total_paid_for_admission(dto.admission_id) or 0.0)
            pending_balance = max(0.0, final_fee - total_paid_so_far)

            # 3. Overpayment Prevention (Non-negotiable Invariant)
            if dto.amount > pending_balance:
                raise ValidationError(
                    f"Payment amount (₹{dto.amount:,.2f}) exceeds pending balance (₹{pending_balance:,.2f}). Overpayment is strictly rejected."
                )

            # 4. Payment Floor Rules (SIMS-FIN-01)
            if current_status in (AdmissionStatus.DRAFT.value, AdmissionStatus.REGISTERED.value):
                # Initial confirmation payment
                if pending_balance >= self.MIN_CONFIRMATION_AMOUNT and dto.amount < self.MIN_CONFIRMATION_AMOUNT:
                    raise ValidationError(
                        f"Initial confirmation requires a minimum payment of ₹{self.MIN_CONFIRMATION_AMOUNT:,.2f}. Provided: ₹{dto.amount:,.2f}."
                    )
            # For CONFIRMED admissions: subsequent payments only require amount > 0 and amount <= pending_balance

            # 5. Installment Number
            next_inst = self.repository.get_next_installment_number(dto.admission_id)

            # 6. Insert Payment Record
            cand_year = adm.get("candidate_year") or datetime.now().year
            cand_seq = adm.get("candidate_sequence") or dto.admission_id
            cand_num = f"{cand_year}-{cand_seq:03d}"

            data = {
                "admission_id": dto.admission_id,
                "student_id": dto.student_id,
                "installment_number": next_inst,
                "amount": float(dto.amount),
                "payment_mode": mode_str,
                "collector_id": dto.collector_id,
                "collector_name": dto.collector_name.strip(),
                "transaction_ref": dto.transaction_ref.strip() if dto.transaction_ref else None,
                "remarks": dto.remarks.strip() if dto.remarks else f"Payment for admission {cand_num}",
                "created_by": dto.created_by,
            }

            payment_id = self.repository.insert(data)
            if not payment_id or payment_id <= 0:
                raise ServiceError("Failed to record payment transaction.")

            new_total_paid = total_paid_so_far + float(dto.amount)
            new_pending = max(0.0, final_fee - new_total_paid)

            # 7. Admission Status Progression (SIMS-DB-01 & Blueprint Section 8)
            new_status = current_status
            if current_status in (AdmissionStatus.DRAFT.value, AdmissionStatus.REGISTERED.value):
                if new_pending <= 0.0:
                    new_status = AdmissionStatus.COMPLETED.value
                else:
                    new_status = AdmissionStatus.CONFIRMED.value
                self.admission_repo.update_status(dto.admission_id, new_status)
            elif current_status == AdmissionStatus.CONFIRMED.value and new_pending <= 0.0:
                new_status = AdmissionStatus.COMPLETED.value
                self.admission_repo.update_status(dto.admission_id, new_status)

            # 8. Receipt & Vector PDF Creation (Atomic)
            student_name = f"{adm.get('first_name', '')} {adm.get('last_name', '')}".strip() or "Student"
            course_name = adm.get("course_name") or "Course"

            receipt_dto = ReceiptCreateDTO(
                payment_id=payment_id,
                admission_id=dto.admission_id,
                student_id=dto.student_id,
                total_course_fee=final_fee,
                amount_paid=float(dto.amount),
                total_paid_till_now=new_total_paid,
                pending_amount=new_pending,
                installment_number=next_inst,
                payment_mode=mode_str,
                collector_name=dto.collector_name.strip(),
                generated_by=dto.created_by,
                transaction_ref=clean_tx_ref,
            )

            context_data = {
                "student_name": student_name,
                "candidate_number": cand_num,
                "course_name": course_name,
                "transaction_ref": clean_tx_ref,
            }

            self.receipt_service.create_receipt(receipt_dto, context_data=context_data)

            # 9. Audit Activity Logging
            self.activity_repo.insert(
                entity_type="PAYMENT",
                entity_id=payment_id,
                action="RECORDED",
                actor_name=dto.collector_name.strip(),
                actor_id=dto.created_by,
                details=f"Payment ₹{dto.amount:,.2f} recorded for {cand_num} (Installment #{next_inst}).",
            )
            if new_status != current_status:
                self.activity_repo.insert(
                    entity_type="ADMISSION",
                    entity_id=dto.admission_id,
                    action=new_status,
                    actor_name=dto.collector_name.strip(),
                    actor_id=dto.created_by,
                    details=f"Admission transitioned to {new_status} on payment of ₹{dto.amount:,.2f}.",
                )

            LogService.info(
                f"Payment recorded successfully: ID {payment_id}, Admission {dto.admission_id}, Status {new_status}, Installment {next_inst}, Amount ₹{dto.amount}",
                context=self.__class__.__name__,
            )

        # Targeted in-memory cache update upon successful transaction commit (R3, R4, R11, R12, R14)
        from core.cache.fees_cache import FeesCacheManager
        FeesCacheManager.targeted_payment_update(
            admission_id=dto.admission_id,
            installment_number=next_inst,
            amount=float(dto.amount),
            new_status=new_status,
        )

        return payment_id

    def get_payments_for_admission(self, admission_id: int) -> list[PaymentDTO]:
        from core.cache.fees_cache import FeesCacheManager
        cached = FeesCacheManager.get_admission_payments(admission_id)
        if cached is not None:
            return [PaymentMapper.to_dto(r) for r in cached]

        with self.unit_of_work():
            rows = self.repository.get_by_admission_id(admission_id)
            FeesCacheManager.set_admission_payments(admission_id, [dict(r) for r in rows])
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
