# modules/admission/service.py

from __future__ import annotations
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from core.service.base import BaseService
from core.security.auth import AuthService
from core.logger.service import LogService
from core.exceptions import ServiceError, ValidationError, ConflictError
from modules.admission.constants import AdmissionStatus, Qualification, BloodGroup, Gender
from modules.admission.dto import (
    AdmissionCreateDTO,
    AdmissionUpdateDTO,
    AdmissionDTO,
    AdmissionResponseDTO,
    AdmissionFilterDTO,
    AdmissionSummaryDTO,
    AdmissionWorkspaceDTO,
    FriendSuggestionDTO,
)
from modules.admission.mapper import AdmissionMapper
from modules.admission.repository import AdmissionRepository
from modules.admission_course.repository import AdmissionCourseRepository
from modules.admission.institution_repository import EducationalInstitutionRepository
from modules.admission.collector_repository import PaymentCollectorRepository
from modules.admission.friendship_repository import FriendshipRepository
from modules.admission.activity_log_repository import ActivityLogRepository
from modules.student.repository import StudentRepository
from modules.course.repository import CourseRepository
from modules.batch.repository import BatchRepository
from modules.payments.repository import PaymentRepository
from modules.payments.mapper import PaymentMapper
from modules.receipts.repository import ReceiptRepository
from modules.receipts.mapper import ReceiptMapper
from modules.settings.repository import SettingsRepository
from infrastructure.pdf.receipt_generator import ReceiptPDFGenerator

__all__ = ["AdmissionService"]


class AdmissionService(BaseService):
    """
    Core Enterprise Business Logic Layer for Admission & Registration Transactions.
    Orchestrates repository calls under a single atomic unit_of_work boundary.
    Enforces atomic state transitions, fee calculations, ₹500 confirmation threshold,
    Admin PIN verification, sequential receipting, friend matching, and audit logging.
    """

    MAX_DOCUMENT_SIZE = 100 * 1024  # 100 KB
    MIN_CONFIRMATION_AMOUNT = 500.0
    DEFAULT_ADMIN_PIN = "1234"

    def __init__(self) -> None:
        self.repository = AdmissionRepository()
        self.bridge_repo = AdmissionCourseRepository()
        self.student_repo = StudentRepository()
        self.course_repo = CourseRepository()
        self.batch_repo = BatchRepository()
        self.institution_repo = EducationalInstitutionRepository()
        self.collector_repo = PaymentCollectorRepository()
        self.friendship_repo = FriendshipRepository()
        self.activity_repo = ActivityLogRepository()
        self.payment_repo = PaymentRepository()
        self.receipt_repo = ReceiptRepository()
        self.settings_repo = SettingsRepository()

    @staticmethod
    def _format_name(val: Optional[str]) -> str:
        if not val:
            return ""
        return " ".join(part.capitalize() for part in val.strip().split())

    def _verify_pin_hash(self, pin: str) -> bool:
        if not pin or not pin.strip():
            return False
        clean = pin.strip()
        stored_hash = self.settings_repo.get("admin_pin_hash")
        if stored_hash:
            return AuthService.verify_password(stored_hash, clean)
        default_hash = AuthService.hash_password(self.DEFAULT_ADMIN_PIN)
        return AuthService.verify_password(default_hash, clean)

    def _validate_personal_info(self, dto: AdmissionCreateDTO) -> tuple[int, dict[str, Any]]:
        """Validates personal information and resolves or creates the student profile."""
        has_village = bool(dto.village and dto.village.strip())
        has_address = bool(dto.address and dto.address.strip())
        if not has_village and not has_address:
            raise ValidationError("Location requirement: At least Village OR Address must be provided.")

        clean_village = dto.village.strip() if has_village else None
        clean_address = dto.address.strip() if has_address else None

        # Existing Student Resolution
        if dto.student_id and dto.student_id > 0:
            student = self.student_repo.get_by_id(dto.student_id)
            if not student:
                raise ValidationError(f"Student with ID {dto.student_id} not found.")

            student_id = dto.student_id
            update_data = {}
            if dto.middle_name:
                update_data["middle_name"] = self._format_name(dto.middle_name)
            if dto.mother_name:
                update_data["mother_name"] = self._format_name(dto.mother_name)
            if dto.dob:
                update_data["dob"] = dto.dob.strip()
            if dto.gender:
                update_data["gender"] = dto.gender.strip().upper()
            if dto.aadhaar_number:
                update_data["aadhaar_number"] = dto.aadhaar_number.strip()
            if dto.parent_guardian_name:
                update_data["parent_guardian_name"] = self._format_name(dto.parent_guardian_name)
            if clean_village:
                update_data["village"] = clean_village
            if clean_address:
                update_data["address"] = clean_address
            if dto.qualification:
                update_data["qualification"] = dto.qualification.strip()
            if dto.blood_group:
                update_data["blood_group"] = dto.blood_group.strip().upper()

            if update_data:
                update_data["first_name"] = student["first_name"]
                update_data["last_name"] = student["last_name"]
                update_data["mobile_number"] = student["mobile_number"]
                update_data["email"] = student["email"]
                self.student_repo.update(student_id, update_data)

            return student_id, {
                "first_name": student["first_name"],
                "last_name": student["last_name"],
                "mobile_number": student["mobile_number"],
                "village": clean_village or student.get("village"),
                "address": clean_address or student.get("address"),
            }

        # New Student Inline Creation
        first_name = self._format_name(dto.first_name)
        middle_name = self._format_name(dto.middle_name)
        last_name = self._format_name(dto.last_name)
        mother_name = self._format_name(dto.mother_name)
        parent_name = self._format_name(dto.parent_guardian_name)

        if not first_name or len(first_name) < 2:
            raise ValidationError("First name is required and must be at least 2 characters.")
        if not last_name or len(last_name) < 2:
            raise ValidationError("Surname / Last name is required and must be at least 2 characters.")
        if not mother_name:
            raise ValidationError("Mother's name is required.")
        if not dto.dob:
            raise ValidationError("Date of Birth is required.")
        if not dto.gender:
            raise ValidationError("Gender is required.")
        if not dto.mobile_number:
            raise ValidationError("Mobile number is required and cannot be blank.")
        if not dto.aadhaar_number or len(re.sub(r"\D", "", dto.aadhaar_number)) < 12:
            raise ValidationError("A valid 12-digit Aadhaar number is required.")

        clean_mobile = re.sub(r"[\s\-]", "", dto.mobile_number.strip())
        if clean_mobile.startswith("+91"):
            clean_mobile = clean_mobile[3:]
        elif clean_mobile.startswith("+"):
            clean_mobile = clean_mobile[1:]

        if not re.match(r"^[0-9]{10,15}$", clean_mobile):
            raise ValidationError("Mobile number must be a valid 10-digit number.")

        # Check duplicate mobile
        existing_mobile = self.student_repo.get_by_mobile(clean_mobile)
        if existing_mobile:
            raise ConflictError(f"A student with mobile number '{clean_mobile}' already exists.")

        student_data = {
            "first_name": first_name,
            "middle_name": middle_name,
            "last_name": last_name,
            "mother_name": mother_name,
            "parent_guardian_name": parent_name,
            "dob": dto.dob.strip(),
            "gender": dto.gender.strip().upper(),
            "mobile_number": clean_mobile,
            "email": dto.email.strip().lower() if dto.email else None,
            "aadhaar_number": dto.aadhaar_number.strip(),
            "village": clean_village,
            "address": clean_address,
            "qualification": dto.qualification.strip() if dto.qualification else None,
            "blood_group": dto.blood_group.strip().upper() if dto.blood_group else None,
        }

        student_id = self.student_repo.insert(student_data)
        if not student_id or student_id <= 0:
            raise ServiceError("Failed to create student profile.")

        self.activity_repo.insert("STUDENT", student_id, "CREATED", details=f"Registered student {first_name} {last_name}")
        return student_id, student_data

    def _validate_documents(self, dto: AdmissionCreateDTO, student_id: int) -> tuple[Optional[str], Optional[str]]:
        """Validates photo and signature constraints (<= 100KB) and saves files."""
        photo_path = dto.photo_path
        signature_path = dto.signature_path

        # Validate photo size
        if dto.photo_bytes is not None:
            if len(dto.photo_bytes) > self.MAX_DOCUMENT_SIZE:
                raise ValidationError(f"Student photo file size exceeds 100 KB limit ({len(dto.photo_bytes) / 1024:.1f} KB).")
            upload_dir = Path("uploads") / "photos"
            upload_dir.mkdir(parents=True, exist_ok=True)
            filename = f"photo_{student_id}_{int(datetime.now().timestamp())}.jpg"
            dest = upload_dir / filename
            dest.write_bytes(dto.photo_bytes)
            photo_path = str(dest)

        # Validate signature size
        if dto.signature_bytes is not None:
            if len(dto.signature_bytes) > self.MAX_DOCUMENT_SIZE:
                raise ValidationError(f"Student signature file size exceeds 100 KB limit ({len(dto.signature_bytes) / 1024:.1f} KB).")
            upload_dir = Path("uploads") / "signatures"
            upload_dir.mkdir(parents=True, exist_ok=True)
            filename = f"sig_{student_id}_{int(datetime.now().timestamp())}.png"
            dest = upload_dir / filename
            dest.write_bytes(dto.signature_bytes)
            signature_path = str(dest)

        # Settings checks - only enforced for non-draft admissions
        if dto.status != AdmissionStatus.DRAFT:
            req_photo = (self.settings_repo.get("require_photo") or "false").lower() == "true"
            req_sig = (self.settings_repo.get("require_signature") or "false").lower() == "true"

            if req_photo and not photo_path:
                raise ValidationError("Student photo is required by institute policy.")
            if req_sig and not signature_path:
                raise ValidationError("Student signature is required by institute policy.")

        return photo_path, signature_path

    def create_admission(self, dto: AdmissionCreateDTO) -> int:
        """
        Executes an atomic enterprise admission transaction.
        """
        target_status = dto.status
        is_confirming = (target_status == AdmissionStatus.CONFIRMED)
        init_amount = float(dto.initial_payment_amount or 0.0)

        # Validate confirmation prerequisites early
        if is_confirming:
            if init_amount < self.MIN_CONFIRMATION_AMOUNT:
                raise ValidationError(
                    f"Admission confirmation requires a minimum initial payment of ₹{self.MIN_CONFIRMATION_AMOUNT:,.2f}. "
                    f"Provided payment was ₹{init_amount:,.2f}."
                )

        with self.unit_of_work():
            # Validate PIN within transaction
            if is_confirming:
                if not dto.admin_pin or not self._verify_pin_hash(dto.admin_pin):
                    raise ValidationError("Invalid Admin authorization PIN. Payment rejected.")

            # 1. Verify Course Existence & Active Status
            course = self.course_repo.get_by_id(dto.course_id)
            if not course:
                raise ValidationError(f"Course with ID {dto.course_id} does not exist.")
            if course.get("status") != "ACTIVE":
                raise ValidationError(f"Course '{course['name']}' is INACTIVE and cannot accept new admissions.")

            course_fee = float(course.get("base_fee", 0.0))
            agreed_fee = float(dto.agreed_fee) if dto.agreed_fee > 0 else course_fee
            discount = float(dto.discount or 0.0)
            final_fee = max(0.0, agreed_fee - discount)

            # 2. Verify Batch Compatibility (if selected)
            if dto.batch_id and dto.batch_id > 0:
                batch = self.batch_repo.get_by_id(dto.batch_id)
                if not batch:
                    raise ValidationError(f"Batch with ID {dto.batch_id} not found.")
                if int(batch["course_id"]) != int(dto.course_id):
                    raise ValidationError(f"Selected batch '{batch['batch_name']}' does not belong to course '{course['name']}'.")
                if batch.get("status") in ("FULL", "COMPLETED", "CANCELLED", "ARCHIVED"):
                    raise ValidationError(f"Batch '{batch['batch_name']}' is {batch['status']} and cannot accept new enrollments.")

            if is_confirming and init_amount > final_fee:
                raise ValidationError(
                    f"Initial payment amount (₹{init_amount:,.2f}) cannot exceed final payable course fee (₹{final_fee:,.2f})."
                )

            # 3. Resolve or Create Student Profile
            student_id, student_info = self._validate_personal_info(dto)

            # 4. Document Validation
            photo_path, signature_path = self._validate_documents(dto, student_id)

            # 5. State Restriction: One Active Draft / Registered per Student
            if target_status in (AdmissionStatus.DRAFT, AdmissionStatus.REGISTERED):
                if self.repository.has_admission_in_state(student_id, target_status.value):
                    raise ConflictError(f"Student already has an active admission in '{target_status.value}' state.")

            # 6. Determine Candidate Year & Sequence (YYYY-NNN)
            admission_year = dto.candidate_year or datetime.now().year
            next_seq = dto.candidate_sequence or self.repository.get_next_sequence_for_year(admission_year)

            # 7. Resolve Institution Name
            inst_name = dto.institution_name
            if dto.institution_id:
                inst_row = self.institution_repo.get_by_id(dto.institution_id)
                if inst_row:
                    inst_name = str(inst_row["name"])

            insert_data = {
                "student_id": student_id,
                "status": target_status.value,
                "candidate_year": admission_year,
                "candidate_sequence": next_seq,
                "batch_id": dto.batch_id if dto.batch_id and dto.batch_id > 0 else None,
                "agreed_fee": agreed_fee,
                "discount": discount,
                "remarks": dto.remarks.strip() if dto.remarks else None,
                "institution_id": dto.institution_id if dto.institution_id and dto.institution_id > 0 else None,
                "institution_name": inst_name,
                "qualification": dto.qualification.strip() if dto.qualification else None,
                "qualification_other": dto.qualification_other.strip() if dto.qualification_other else None,
                "blood_group": dto.blood_group.strip().upper() if dto.blood_group else None,
                "village": dto.village.strip() if dto.village else None,
                "address": dto.address.strip() if dto.address else None,
                "aadhaar_number": dto.aadhaar_number.strip() if dto.aadhaar_number else None,
                "mother_name": dto.mother_name.strip() if dto.mother_name else None,
                "parent_guardian_name": dto.parent_guardian_name.strip() if dto.parent_guardian_name else None,
                "dob": dto.dob.strip() if dto.dob else None,
                "gender": dto.gender.strip().upper() if dto.gender else None,
                "middle_name": dto.middle_name.strip() if dto.middle_name else None,
                "photo_path": photo_path,
                "signature_path": signature_path,
            }

            # 8. Insert Core Admission Record
            admission_id = self.repository.insert(insert_data)
            if not admission_id or admission_id <= 0:
                raise ServiceError("Failed to create admission record.")

            # 9. Link Course in Bridge Table
            self.bridge_repo.link_course(admission_id, dto.course_id)

            candidate_number = f"{admission_year}-{next_seq:03d}"

            # 10. Record Initial Payment & Receipt if confirmed / paying now
            if init_amount > 0:
                pay_mode = (dto.payment_mode or "CASH").upper()
                collector = dto.collector_name or "Hemant Mahale (Sir)"

                next_inst = self.payment_repo.get_next_installment_number(admission_id)
                pay_data = {
                    "admission_id": admission_id,
                    "student_id": student_id,
                    "installment_number": next_inst,
                    "amount": init_amount,
                    "payment_mode": pay_mode,
                    "collector_id": dto.collector_id,
                    "collector_name": collector,
                    "transaction_ref": dto.transaction_ref.strip() if dto.transaction_ref else None,
                    "remarks": f"Initial confirmation payment for {candidate_number}",
                    "created_by": dto.created_by,
                }
                payment_id = self.payment_repo.insert(pay_data)

                # Generate Official Receipt
                receipt_seq = self.receipt_repo.get_next_sequence_for_year(admission_year)
                receipt_number = f"RCP-{admission_year}-{receipt_seq:05d}"

                project_root = Path(__file__).resolve().parent.parent.parent
                pdf_path = project_root / "exports" / "receipts" / f"receipt_{receipt_number.lower().replace('-', '_')}.pdf"

                render_payload = {
                    "receipt_number": receipt_number,
                    "receipt_date": datetime.now().strftime("%d-%b-%Y %I:%M %p"),
                    "student_name": f"{student_info.get('first_name', '')} {student_info.get('last_name', '')}".strip(),
                    "student_id": student_id,
                    "candidate_number": candidate_number,
                    "admission_id": admission_id,
                    "course_name": course["name"],
                    "installment_number": next_inst,
                    "amount_paid": init_amount,
                    "total_course_fee": final_fee,
                    "total_paid_till_now": init_amount,
                    "pending_amount": max(0.0, final_fee - init_amount),
                    "payment_mode": pay_mode,
                    "collector_name": collector,
                }

                try:
                    profile = {
                        "institute_name": self.settings_repo.get("institute_name") or "Sudharm Infotech",
                        "contact_person": self.settings_repo.get("contact_person") or "Hemant Mahale",
                        "contact_mobile": self.settings_repo.get("contact_mobile") or "9271226772",
                        "alc_code": self.settings_repo.get("alc_code") or "57210242",
                        "address_line1": self.settings_repo.get("address_line1") or "Renuka Complex, 3rd Floor,",
                        "address_line2": self.settings_repo.get("address_line2") or "Opp. Market Yard, Chandwad - 423101",
                    }
                    ReceiptPDFGenerator.generate_receipt_pdf(render_payload, pdf_path, profile)
                except Exception as ex:
                    LogService.warning(f"Receipt PDF rendering note: {ex}", context=self.__class__.__name__)
                    pdf_path = None

                rcp_data = {
                    "payment_id": payment_id,
                    "admission_id": admission_id,
                    "student_id": student_id,
                    "receipt_number": receipt_number,
                    "total_course_fee": final_fee,
                    "amount_paid": init_amount,
                    "total_paid_till_now": init_amount,
                    "pending_amount": max(0.0, final_fee - init_amount),
                    "installment_number": next_inst,
                    "payment_mode": pay_mode,
                    "collector_name": collector,
                    "pdf_path": str(pdf_path) if pdf_path else None,
                    "generated_by": dto.created_by,
                }
                self.receipt_repo.insert(rcp_data)

            # 11. Explicit Friendship Linking (B2, B24)
            if dto.selected_friend_ids:
                for friend_id in dto.selected_friend_ids[:3]:
                    if friend_id and friend_id > 0 and friend_id != student_id:
                        self.friendship_repo.add_friendship(student_id, friend_id, admission_id)

            # 12. Activity Log (B20)
            action_name = "CONFIRMED" if is_confirming else "CREATED"
            self.activity_repo.insert(
                "ADMISSION",
                admission_id,
                action_name,
                actor_name="OPERATOR",
                actor_id=dto.created_by,
                details=f"Admission {candidate_number} {action_name} for course {course['name']}. Status: {target_status.value}",
            )

            LogService.info(
                f"Admission created successfully: ID #{admission_id}, Number {candidate_number}, Status: {target_status.value}",
                context=self.__class__.__name__,
            )
            return admission_id

    def update_admission(self, dto: AdmissionUpdateDTO) -> None:
        """Updates an existing admission record."""
        with self.unit_of_work():
            existing = self.repository.get_by_id(dto.id)
            if not existing:
                raise ValidationError(f"Admission with ID {dto.id} not found.")

            data = {
                "batch_id": dto.batch_id if dto.batch_id and dto.batch_id > 0 else None,
                "agreed_fee": dto.agreed_fee,
                "discount": dto.discount,
                "status": dto.status.value,
                "remarks": dto.remarks.strip() if dto.remarks else None,
                "institution_id": dto.institution_id if dto.institution_id and dto.institution_id > 0 else None,
                "institution_name": dto.institution_name,
                "qualification": dto.qualification.strip() if dto.qualification else None,
                "qualification_other": dto.qualification_other.strip() if dto.qualification_other else None,
                "blood_group": dto.blood_group.strip().upper() if dto.blood_group else None,
                "village": dto.village.strip() if dto.village else None,
                "address": dto.address.strip() if dto.address else None,
                "aadhaar_number": dto.aadhaar_number.strip() if dto.aadhaar_number else None,
                "mother_name": dto.mother_name.strip() if dto.mother_name else None,
                "parent_guardian_name": dto.parent_guardian_name.strip() if dto.parent_guardian_name else None,
                "dob": dto.dob.strip() if dto.dob else None,
                "gender": dto.gender.strip().upper() if dto.gender else None,
                "middle_name": dto.middle_name.strip() if dto.middle_name else None,
                "photo_path": dto.photo_path,
                "signature_path": dto.signature_path,
            }
            self.repository.update(dto.id, data)
            self.activity_repo.insert("ADMISSION", dto.id, "UPDATED", details=f"Updated admission ID {dto.id}")

    def get_admission(self, admission_id: int) -> AdmissionDTO:
        with self.unit_of_work():
            row = self.repository.get_by_id(admission_id)
            if not row:
                raise ValidationError(f"Admission with ID {admission_id} not found.")
            return AdmissionMapper.to_dto(row)

    def get_admission_workspace(self, admission_id: int) -> AdmissionWorkspaceDTO:
        """Assembles full 360° detail workspace."""
        with self.unit_of_work():
            adm_row = self.repository.get_by_id(admission_id)
            if not adm_row:
                raise ValidationError(f"Admission with ID {admission_id} not found.")
            adm = AdmissionMapper.to_dto(adm_row)

            pay_rows = self.payment_repo.get_by_admission_id(admission_id)
            payments = [PaymentMapper.to_dto(p) for p in pay_rows]

            rcp_rows = self.receipt_repo.get_by_admission_id(admission_id)
            receipts = [ReceiptMapper.to_dto(r) for r in rcp_rows]

            confirmed_friends = self.friendship_repo.get_confirmed_friends(adm.student_id)

            timeline = []
            timeline.append({
                "timestamp": adm.created_at,
                "title": "Admission Registered",
                "description": f"Admission candidate profile {adm.admission_number} created.",
                "event_type": "REGISTRATION",
            })
            for p in payments:
                timeline.append({
                    "timestamp": p.payment_date,
                    "title": f"Payment ({p.formatted_installment})",
                    "description": f"Received ₹{p.amount:,.2f} via {p.payment_mode} (Collected by {p.collector_name}).",
                    "event_type": "PAYMENT",
                })
            for r in receipts:
                timeline.append({
                    "timestamp": r.receipt_date,
                    "title": f"Receipt #{r.receipt_number}",
                    "description": f"Official receipt issued for ₹{r.amount_paid:,.2f}.",
                    "event_type": "RECEIPT",
                })
            timeline.sort(key=lambda x: x["timestamp"], reverse=True)

            return AdmissionWorkspaceDTO(
                admission=adm,
                payments=payments,
                receipts=receipts,
                confirmed_friends=confirmed_friends,
                timeline=timeline,
            )

    def filter_admissions(self, dto: AdmissionFilterDTO) -> tuple[list[AdmissionDTO], int]:
        with self.unit_of_work():
            rows, total = self.repository.filter_admissions(dto)
            return [AdmissionMapper.to_dto(r) for r in rows], total

    def get_summary_statistics(self) -> AdmissionSummaryDTO:
        with self.unit_of_work():
            stats = self.repository.get_summary_statistics()
            return AdmissionSummaryDTO(
                total_admissions=stats["total_admissions"],
                confirmed_count=stats["confirmed_count"],
                registered_count=stats["registered_count"],
                draft_count=stats["draft_count"],
                today_admissions=stats["today_admissions"],
                total_revenue=stats["total_revenue"],
                today_collection=stats["today_collection"],
                total_pending=stats["total_pending"],
            )

    def get_suggested_friends(self, village: str, exclude_student_id: int = 0, gender: Optional[str] = None) -> list[FriendSuggestionDTO]:
        with self.unit_of_work():
            rows = self.friendship_repo.get_suggested_friends(village, exclude_student_id, gender, limit=3)
            return [AdmissionMapper.to_friend_suggestion_dto(r) for r in rows]

    def add_friendship(self, student_id: int, friend_student_id: int, admission_id: Optional[int] = None) -> None:
        with self.unit_of_work():
            self.friendship_repo.add_friendship(student_id, friend_student_id, admission_id)
            self.activity_repo.insert("STUDENT", student_id, "FRIEND_ADDED", details=f"Linked friend ID {friend_student_id}")

    def confirm_admission_with_payment(
        self,
        admission_id: int,
        amount: float,
        payment_mode: str,
        admin_pin: str,
        collector_name: str,
        collector_id: Optional[int] = None,
        transaction_ref: Optional[str] = None,
        actor_id: Optional[int] = None,
    ) -> int:
        """
        Transitions an existing DRAFT or REGISTERED admission to CONFIRMED
        with an atomic payment transaction of at least ₹500 and verified Admin PIN.
        """
        if amount < self.MIN_CONFIRMATION_AMOUNT:
            raise ValidationError(
                f"Admission confirmation requires a minimum initial payment of ₹{self.MIN_CONFIRMATION_AMOUNT:,.2f}. "
                f"Provided payment was ₹{amount:,.2f}."
            )

        with self.unit_of_work():
            if not admin_pin or not self._verify_pin_hash(admin_pin):
                raise ValidationError("Invalid Admin authorization PIN. Payment rejected.")

            adm_row = self.repository.get_by_id(admission_id)
            if not adm_row:
                raise ValidationError(f"Admission with ID {admission_id} not found.")
            adm = AdmissionMapper.to_dto(adm_row)

            # 1. Update Status to CONFIRMED
            self.repository.update_status(admission_id, AdmissionStatus.CONFIRMED.value)

            # 2. Record Payment
            next_inst = self.payment_repo.get_next_installment_number(admission_id)
            pay_data = {
                "admission_id": admission_id,
                "student_id": adm.student_id,
                "installment_number": next_inst,
                "amount": float(amount),
                "payment_mode": payment_mode.upper(),
                "collector_id": collector_id,
                "collector_name": collector_name,
                "transaction_ref": transaction_ref.strip() if transaction_ref else None,
                "remarks": f"Confirmation payment for admission {adm.admission_number}",
                "created_by": actor_id,
            }
            payment_id = self.payment_repo.insert(pay_data)

            # 3. Issue Receipt & PDF
            total_paid_now = adm.total_paid + amount
            receipt_year = adm.candidate_year or datetime.now().year
            receipt_seq = self.receipt_repo.get_next_sequence_for_year(receipt_year)
            receipt_number = f"RCP-{receipt_year}-{receipt_seq:05d}"

            project_root = Path(__file__).resolve().parent.parent.parent
            pdf_path = project_root / "exports" / "receipts" / f"receipt_{receipt_number.lower().replace('-', '_')}.pdf"

            render_payload = {
                "receipt_number": receipt_number,
                "receipt_date": datetime.now().strftime("%d-%b-%Y %I:%M %p"),
                "student_name": adm.student_name,
                "student_id": adm.student_id,
                "candidate_number": adm.admission_number,
                "admission_id": admission_id,
                "course_name": adm.course_name,
                "installment_number": next_inst,
                "amount_paid": amount,
                "total_course_fee": adm.final_fee,
                "total_paid_till_now": total_paid_now,
                "pending_amount": max(0.0, adm.final_fee - total_paid_now),
                "payment_mode": payment_mode.upper(),
                "collector_name": collector_name,
            }

            try:
                profile = {
                    "institute_name": self.settings_repo.get("institute_name") or "Sudharm Infotech",
                    "contact_person": self.settings_repo.get("contact_person") or "Hemant Mahale",
                    "contact_mobile": self.settings_repo.get("contact_mobile") or "9271226772",
                    "alc_code": self.settings_repo.get("alc_code") or "57210242",
                    "address_line1": self.settings_repo.get("address_line1") or "Renuka Complex, 3rd Floor,",
                    "address_line2": self.settings_repo.get("address_line2") or "Opp. Market Yard, Chandwad - 423101",
                }
                ReceiptPDFGenerator.generate_receipt_pdf(render_payload, pdf_path, profile)
            except Exception as ex:
                LogService.warning(f"Receipt PDF rendering note: {ex}", context=self.__class__.__name__)
                pdf_path = None

            rcp_data = {
                "payment_id": payment_id,
                "admission_id": admission_id,
                "student_id": adm.student_id,
                "receipt_number": receipt_number,
                "total_course_fee": adm.final_fee,
                "amount_paid": amount,
                "total_paid_till_now": total_paid_now,
                "pending_amount": max(0.0, adm.final_fee - total_paid_now),
                "installment_number": next_inst,
                "payment_mode": payment_mode.upper(),
                "collector_name": collector_name,
                "pdf_path": str(pdf_path) if pdf_path else None,
                "generated_by": actor_id,
            }
            self.receipt_repo.insert(rcp_data)

            # 4. Activity Log
            self.activity_repo.insert(
                "ADMISSION",
                admission_id,
                "CONFIRMED",
                actor_name="OPERATOR",
                actor_id=actor_id,
                details=f"Confirmed admission {adm.admission_number} with payment ₹{amount:,.2f} (Receipt #{receipt_number})",
            )
            return payment_id

    def export_admissions_csv(self, dto: AdmissionFilterDTO, target_path: Optional[str | Path] = None) -> Path:
        """Exports filtered admissions into Excel-compatible CSV."""
        from infrastructure.excel.exporter import ExcelExporter
        
        filter_all = AdmissionFilterDTO(
            query=dto.query,
            course_id=dto.course_id,
            status=dto.status,
            year=dto.year,
            month=dto.month,
            sort_keys=dto.sort_keys,
            limit=10000,
            offset=0,
        )
        admissions, total = self.filter_admissions(filter_all)
        
        default_dir = Path("exports/admissions")
        default_name = f"admission_directory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path = Path(target_path) if target_path else default_dir / default_name

        headers = [
            "Admission ID", "Candidate No", "Student Name", "Mobile", "Course",
            "Batch", "Date", "Status", "Total Fee", "Discount", "Paid", "Pending",
        ]
        rows = [
            [
                a.id,
                a.admission_number,
                a.student_name,
                a.mobile_number or "—",
                a.course_name,
                a.batch_name or "Unassigned",
                a.created_at[:10],
                a.status,
                f"Rs. {a.agreed_fee:,.2f}",
                f"Rs. {a.discount:,.2f}",
                f"Rs. {a.total_paid:,.2f}",
                f"Rs. {a.pending_amount:,.2f}",
            ]
            for a in admissions
        ]

        metadata = {
            "Module": "SIMS v2.2 Admission Management System",
            "Export Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Total Records": len(admissions),
            "Status Filter": dto.status or "All",
        }

        return ExcelExporter.export_to_csv(headers=headers, rows=rows, output_path=path, metadata=metadata)

    def export_admissions_pdf(self, dto: AdmissionFilterDTO, target_path: Optional[str | Path] = None) -> Path:
        """Exports filtered admissions into vector PDF report."""
        from infrastructure.pdf.exporter import PDFExporter
        
        filter_all = AdmissionFilterDTO(
            query=dto.query,
            course_id=dto.course_id,
            status=dto.status,
            year=dto.year,
            month=dto.month,
            sort_keys=dto.sort_keys,
            limit=10000,
            offset=0,
        )
        admissions, total = self.filter_admissions(filter_all)
        
        default_dir = Path("exports/admissions")
        default_name = f"admission_directory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        path = Path(target_path) if target_path else default_dir / default_name

        headers = [
            "ID", "Cand No", "Student Name", "Mobile", "Course",
            "Batch", "Date", "Status", "Fee", "Paid", "Pending",
        ]
        column_widths = [0.8, 1.4, 2.2, 1.4, 2.0, 1.4, 1.2, 1.2, 1.1, 1.1, 1.1]

        rows = [
            [
                a.id,
                a.admission_number,
                a.student_name,
                a.mobile_number or "—",
                a.course_name,
                a.batch_name or "—",
                a.created_at[:10],
                a.status,
                f"{a.agreed_fee:,.0f}",
                f"{a.total_paid:,.0f}",
                f"{a.pending_amount:,.0f}",
            ]
            for a in admissions
        ]

        metadata = {
            "Status Filter": dto.status or "All",
            "Total Records": len(admissions),
        }

        return PDFExporter.export_table_pdf(
            title="SIMS v2.2 — Admission Directory Report",
            headers=headers,
            column_widths=column_widths,
            rows=rows,
            output_path=path,
            subtitle=f"Exported on {datetime.now().strftime('%d-%b-%Y %H:%M:%S')}  |  Total Filtered Records: {len(admissions)}",
            metadata=metadata,
        )

    # Backward compatibility helper
    def create(self, dto: Any) -> int:
        if isinstance(dto, AdmissionCreateDTO):
            return self.create_admission(dto)
        return self.create_admission(dto)
