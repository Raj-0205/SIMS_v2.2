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
    DuplicateCheckDTO,
    DuplicateCheckResultDTO,
)
from shared.utils import format_title_case, normalize_name, normalize_mobile
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
from modules.payments.dto import PaymentCreateDTO
from modules.payments.service import PaymentService
from modules.receipts.repository import ReceiptRepository
from modules.receipts.mapper import ReceiptMapper
from modules.receipts.dto import ReceiptCreateDTO
from modules.receipts.service import ReceiptService
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
        self.payment_service = PaymentService()
        self.receipt_service = ReceiptService()

    @staticmethod
    def _format_name(val: Optional[str]) -> str:
        if not val:
            return ""
        return " ".join(part.capitalize() for part in val.strip().split())

    def _verify_pin_hash(self, pin: str) -> bool:
        if not pin or not pin.strip():
            return False
        clean = pin.strip()
        from core.database.transaction import TransactionManager
        if TransactionManager.in_transaction():
            stored_hash = self.settings_repo.get("admin_pin_hash")
        else:
            with self.unit_of_work():
                stored_hash = self.settings_repo.get("admin_pin_hash")
        if stored_hash and AuthService.verify_password(stored_hash, clean):
            return True
        default_hash = AuthService.hash_password(self.DEFAULT_ADMIN_PIN)
        return AuthService.verify_password(default_hash, clean)

    def check_duplicate(self, dto: DuplicateCheckDTO) -> DuplicateCheckResultDTO:
        """
        Deterministic duplicate identity and admission classification check.
        Canonical Rule: NORMALIZED FULL NAME MATCH + ANY ONE MOBILE NUMBER MATCH.
        Classification:
            - DUPLICATE_ACTIVE: Same student + same active course (REGISTERED or CONFIRMED) -> can_create=False
            - EXISTING_DRAFT: Same student + existing draft admission -> can_create=False (offer resume)
            - EXISTING_STUDENT_READMISSION: Same student + completed/closed admission -> can_create=True
            - EXISTING_STUDENT_NEW_COURSE: Same student + different course -> can_create=True
            - NONE: No identity match -> can_create=True
        """
        from core.database.transaction import TransactionManager
        if TransactionManager.in_transaction():
            return self._check_duplicate_internal(dto)
        with self.unit_of_work():
            return self._check_duplicate_internal(dto)

    def _check_duplicate_internal(self, dto: DuplicateCheckDTO) -> DuplicateCheckResultDTO:
        norm_name = normalize_name(dto.full_name)
        c1 = normalize_mobile(dto.contact1)
        c2 = normalize_mobile(dto.contact2) if dto.contact2 else None

        if not norm_name or not c1:
            return DuplicateCheckResultDTO(
                is_identity_match=False,
                classification="NONE",
                can_create_admission=True,
                message="Full name and primary mobile are required for identity verification.",
            )

        mobiles_to_check = [c1]
        if c2:
            mobiles_to_check.append(c2)

        candidates = self.student_repo.find_by_mobiles(mobiles_to_check)
        for cand in candidates:
            cand_full = f"{cand.get('first_name', '')} {cand.get('middle_name') or ''} {cand.get('last_name', '')}"
            cand_norm = normalize_name(cand_full)
            if cand_norm == norm_name:
                # Identity matched! Determine which mobile matched
                cand_mobiles = [normalize_mobile(cand.get("mobile_number"))]
                if cand.get("secondary_mobile"):
                    cand_mobiles.append(normalize_mobile(cand.get("secondary_mobile")))

                matched_mobile = None
                for m in mobiles_to_check:
                    if m in cand_mobiles:
                        matched_mobile = m
                        break

                student_id = cand["id"]
                display_name = f"{cand.get('first_name', '')} {cand.get('last_name', '')}".strip()
                admissions = self.repository.get_admissions_by_student_id(student_id)
                target_course_id = dto.course_id

                # 1. Same student + same active course (REGISTERED or CONFIRMED) -> Block
                if target_course_id:
                    active_same = [
                        a for a in admissions
                        if a.get("course_id") == target_course_id
                        and a.get("status") in (AdmissionStatus.REGISTERED.value, AdmissionStatus.CONFIRMED.value)
                    ]
                    if active_same:
                        course_name = active_same[0].get("course_name") or f"Course #{target_course_id}"
                        st = active_same[0].get("status")
                        return DuplicateCheckResultDTO(
                            is_identity_match=True,
                            existing_student_id=student_id,
                            existing_student_name=display_name,
                            matched_mobile=matched_mobile,
                            classification="DUPLICATE_ACTIVE",
                            can_create_admission=False,
                            message=f"Student '{display_name}' already has an active ({st}) admission for {course_name}. Creation is blocked.",
                            existing_admissions=admissions,
                        )

                # 2. Same student + existing draft admission -> Offer resume
                draft_admissions = [
                    a for a in admissions
                    if a.get("status") == AdmissionStatus.DRAFT.value
                    and (target_course_id is None or a.get("course_id") == target_course_id)
                ]
                if not draft_admissions and target_course_id:
                    draft_admissions = [
                        a for a in admissions
                        if a.get("status") == AdmissionStatus.DRAFT.value
                    ]

                if draft_admissions:
                    draft = draft_admissions[0]
                    c_name = draft.get("course_name") or "selected course"
                    return DuplicateCheckResultDTO(
                        is_identity_match=True,
                        existing_student_id=student_id,
                        existing_student_name=display_name,
                        matched_mobile=matched_mobile,
                        classification="EXISTING_DRAFT",
                        can_create_admission=False,
                        draft_admission_id=draft["id"],
                        message=f"Existing draft admission #{draft['id']} ({c_name}) found for '{display_name}'. You can resume this draft.",
                        existing_admissions=admissions,
                    )

                # 3. Same student + completed/closed past courses -> Allow re-admission
                if admissions and all(
                    a.get("status") in (AdmissionStatus.COMPLETED.value, AdmissionStatus.CANCELLED.value)
                    for a in admissions
                ):
                    return DuplicateCheckResultDTO(
                        is_identity_match=True,
                        existing_student_id=student_id,
                        existing_student_name=display_name,
                        matched_mobile=matched_mobile,
                        classification="EXISTING_STUDENT_READMISSION",
                        can_create_admission=True,
                        message=f"Existing student '{display_name}' has completed/closed past courses. Re-admission is allowed.",
                        existing_admissions=admissions,
                    )

                # 4. Same student + different course (or student with no previous admissions) -> Allow new admission
                return DuplicateCheckResultDTO(
                    is_identity_match=True,
                    existing_student_id=student_id,
                    existing_student_name=display_name,
                    matched_mobile=matched_mobile,
                    classification="EXISTING_STUDENT_NEW_COURSE",
                    can_create_admission=True,
                    message=f"Existing student profile '{display_name}' matched. New admission is allowed.",
                    existing_admissions=admissions,
                )

        return DuplicateCheckResultDTO(
            is_identity_match=False,
            classification="NONE",
            can_create_admission=True,
            message="No duplicate identity found. Proceeding with new student registration.",
        )

    def _validate_personal_info(self, dto: AdmissionCreateDTO) -> tuple[int, dict[str, Any]]:
        """Validates personal information and resolves or creates the student profile."""
        clean_village = dto.village.strip() if dto.village and dto.village.strip() else None
        clean_address = dto.address.strip() if dto.address and dto.address.strip() else None

        # Existing Student Resolution
        if dto.student_id and dto.student_id > 0:
            student = self.student_repo.get_by_id(dto.student_id)
            if not student:
                raise ValidationError(f"Student with ID {dto.student_id} not found.")

            student_id = dto.student_id
            effective_village = clean_village or student.get("village")
            effective_address = clean_address or student.get("address")

            update_data: dict[str, Any] = {}
            if dto.middle_name:
                update_data["middle_name"] = self._format_name(dto.middle_name)
            if dto.mother_name:
                update_data["mother_name"] = self._format_name(dto.mother_name)
            if dto.dob:
                update_data["dob"] = dto.dob.strip().replace("/", "-")
            if dto.gender:
                update_data["gender"] = dto.gender.strip().upper()
            if dto.aadhaar_number:
                digits = re.sub(r"\D", "", dto.aadhaar_number.strip())
                if len(digits) == 12:
                    update_data["aadhaar_number"] = digits
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
            if dto.secondary_mobile:
                sec = normalize_mobile(dto.secondary_mobile)
                if sec and sec != student.get("mobile_number"):
                    update_data["secondary_mobile"] = sec

            if update_data:
                update_data["first_name"] = student["first_name"]
                update_data["last_name"] = student["last_name"]
                update_data["mobile_number"] = student["mobile_number"]
                update_data["email"] = student.get("email")
                self.student_repo.update(student_id, update_data)

            return student_id, {
                "first_name": student["first_name"],
                "last_name": student["last_name"],
                "mobile_number": student["mobile_number"],
                "secondary_mobile": student.get("secondary_mobile"),
                "village": effective_village,
                "address": effective_address,
            }

        # Location requirement for new student registrations
        if not clean_village and not clean_address:
            raise ValidationError("Location requirement: At least Village OR Address must be provided.")

        # New Student Inline Creation
        first_name = self._format_name(dto.first_name)
        middle_name = self._format_name(dto.middle_name)
        last_name = self._format_name(dto.last_name)
        mother_name = self._format_name(dto.mother_name) if dto.mother_name else None
        parent_name = self._format_name(dto.parent_guardian_name) if dto.parent_guardian_name else None

        if not first_name or len(first_name) < 2:
            raise ValidationError("First name is required and must be at least 2 characters.")
        if not last_name or len(last_name) < 2:
            raise ValidationError("Surname / Last name is required and must be at least 2 characters.")

        # Validate Contact 1 (primary) and Contact 2 (secondary)
        c1 = normalize_mobile(dto.mobile_number)
        c2 = normalize_mobile(dto.secondary_mobile)

        if not c1 or not c2:
            raise ValidationError("Both Contact 1 (primary) and Contact 2 (secondary) mobile numbers are required.")

        if c1 == c2:
            raise ValidationError("Secondary mobile cannot be identical to primary mobile.")

        if not (len(c1) == 10 and c1.isdigit()) or not re.match(r"^[6-9][0-9]{9}$", c1):
            raise ValidationError("Primary mobile must be a valid 10-digit Indian mobile number.")

        if not (len(c2) == 10 and c2.isdigit()) or not re.match(r"^[6-9][0-9]{9}$", c2):
            raise ValidationError("Secondary mobile must be a valid 10-digit Indian mobile number.")

        clean_aadhaar = None
        if dto.aadhaar_number and dto.aadhaar_number.strip():
            digits = re.sub(r"\D", "", dto.aadhaar_number.strip())
            if len(digits) != 12:
                raise ValidationError("Aadhaar number must be exactly 12 digits if provided.")
            clean_aadhaar = digits

        # Run canonical duplicate identity check
        full_name = f"{first_name} {middle_name or ''} {last_name}".strip()
        dup_dto = DuplicateCheckDTO(
            full_name=full_name,
            contact1=c1,
            contact2=c2,
            course_id=dto.course_id,
        )
        dup_result = self.check_duplicate(dup_dto)

        if dup_result.is_identity_match:
            if not dup_result.can_create_admission:
                raise ConflictError(dup_result.message)
            # Allowed existing student (EXISTING_STUDENT_NEW_COURSE or EXISTING_STUDENT_READMISSION)
            student_id = dup_result.existing_student_id
            st = self.student_repo.get_by_id(student_id)
            return student_id, {
                "first_name": st["first_name"],
                "last_name": st["last_name"],
                "mobile_number": st["mobile_number"],
                "secondary_mobile": st.get("secondary_mobile"),
                "village": clean_village or st.get("village"),
                "address": clean_address or st.get("address"),
            }

        student_data = {
            "first_name": first_name,
            "middle_name": middle_name,
            "last_name": last_name,
            "mother_name": mother_name,
            "parent_guardian_name": parent_name,
            "dob": dto.dob.strip() if dto.dob else None,
            "gender": dto.gender.strip().upper() if dto.gender else None,
            "mobile_number": c1,
            "secondary_mobile": c2,
            "email": dto.email.strip().lower() if dto.email else None,
            "aadhaar_number": clean_aadhaar,
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

        if not photo_path and student_id:
            st = self.student_repo.get_by_id(student_id)
            if st and st.get("photo_path"):
                photo_path = st["photo_path"]
        if not signature_path and student_id:
            st = self.student_repo.get_by_id(student_id)
            if st and st.get("signature_path"):
                signature_path = st["signature_path"]

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

            # 5. State Restriction: Prevent duplicate concurrent active draft/registered for the SAME course
            if target_status in (AdmissionStatus.DRAFT, AdmissionStatus.REGISTERED):
                if self.repository.has_active_admission_for_course(student_id, dto.course_id):
                    raise ConflictError(f"Student already has an active '{target_status.value}' admission for course '{course['name']}'.")

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

                receipt_dto = ReceiptCreateDTO(
                    payment_id=payment_id,
                    admission_id=admission_id,
                    student_id=student_id,
                    total_course_fee=final_fee,
                    amount_paid=init_amount,
                    total_paid_till_now=init_amount,
                    pending_amount=max(0.0, final_fee - init_amount),
                    installment_number=next_inst,
                    payment_mode=pay_mode,
                    collector_name=collector,
                    generated_by=dto.created_by,
                )

                context_data = {
                    "student_name": f"{student_info.get('first_name', '')} {student_info.get('last_name', '')}".strip() or "Student",
                    "candidate_number": candidate_number,
                    "course_name": course["name"],
                }

                self.receipt_service.create_receipt(receipt_dto, context_data=context_data)

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
            logs = self.activity_repo.get_logs_for_entity("ADMISSION", admission_id)
            for l in logs:
                timeline.append({
                    "timestamp": l["created_at"],
                    "title": f"Admission {l['action'].capitalize()}",
                    "description": l.get("details") or f"Admission was {l['action'].lower()}.",
                    "event_type": l["action"],
                })
            if not timeline:
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
            timeline.sort(key=lambda x: str(x["timestamp"]), reverse=True)

            batches = self.batch_repo.list(course_id=adm.course_id, limit=50)

            return AdmissionWorkspaceDTO(
                admission=adm,
                payments=payments,
                receipts=receipts,
                confirmed_friends=confirmed_friends,
                timeline=timeline,
                available_batches=batches,
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

    def get_active_institutions(self) -> list[dict[str, Any]]:
        with self.unit_of_work():
            return self.institution_repo.get_active_institutions()

    def add_institution(self, name: str, institution_type: str = "COLLEGE", address: Optional[str] = None) -> int:
        if not name or not name.strip():
            raise ValidationError("Institution name is required.")
        with self.unit_of_work():
            return self.institution_repo.insert(name.strip(), institution_type, address)

    def get_active_collectors(self) -> list[dict[str, Any]]:
        with self.unit_of_work():
            return self.collector_repo.get_active_collectors()

    def add_collector(self, name: str, role_title: Optional[str] = None) -> int:
        if not name or not name.strip():
            raise ValidationError("Collector name is required.")
        with self.unit_of_work():
            return self.collector_repo.insert(name.strip(), role_title)

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
        with an atomic payment transaction and verified Admin PIN.
        Delegates financial mutations to centralized PaymentService.
        """
        if not admin_pin or not self._verify_pin_hash(admin_pin):
            raise ValidationError("Invalid Admin authorization PIN. Payment rejected.")

        with self.unit_of_work():
            adm_row = self.repository.get_by_id(admission_id)
            if not adm_row:
                raise ValidationError(f"Admission with ID {admission_id} not found.")
            adm = AdmissionMapper.to_dto(adm_row)


        pay_dto = PaymentCreateDTO(
            admission_id=admission_id,
            student_id=adm.student_id,
            amount=amount,
            payment_mode=payment_mode,
            collector_id=collector_id,
            collector_name=collector_name,
            transaction_ref=transaction_ref.strip() if transaction_ref else None,
            created_by=actor_id,
        )

        return self.payment_service.record_payment(pay_dto)

    def cancel_admission(self, admission_id: int, reason: str, actor_id: Optional[int] = None) -> bool:
        """
        Cancels an admission in an audited lifecycle operation.
        Preserves all financial records (payments, receipts) and historical data.
        """
        if not reason or not reason.strip():
            raise ValidationError("A cancellation reason is required.")

        adm = self.get_admission(admission_id)
        if not adm:
            raise NotFoundError(f"Admission #{admission_id} not found.")

        if adm.status == AdmissionStatus.CANCELLED.value:
            raise ValidationError("This admission has already been cancelled.")

        with self.unit_of_work():
            new_remarks = (adm.remarks + f"\n[CANCELLED]: {reason.strip()}") if adm.remarks else f"[CANCELLED]: {reason.strip()}"
            self.repository.update(admission_id, {
                "batch_id": adm.batch_id,
                "agreed_fee": adm.agreed_fee,
                "discount": adm.discount,
                "status": AdmissionStatus.CANCELLED.value,
                "remarks": new_remarks,
                "institution_id": adm.institution_id,
                "institution_name": adm.institution_name,
                "qualification": adm.qualification,
                "qualification_other": adm.qualification_other,
                "blood_group": adm.blood_group,
                "village": adm.village,
                "address": adm.address,
                "aadhaar_number": adm.aadhaar_number,
                "mother_name": adm.mother_name,
                "parent_guardian_name": adm.parent_guardian_name,
                "dob": adm.dob,
                "gender": adm.gender,
                "middle_name": adm.middle_name,
                "photo_path": adm.photo_path,
                "signature_path": adm.signature_path,
            })

            self.activity_repo.insert(
                "ADMISSION",
                admission_id,
                "CANCELLED",
                actor_name="OPERATOR",
                actor_id=actor_id,
                details=f"Admission {adm.admission_number} ({adm.course_name}) cancelled. Reason: {reason.strip()}",
            )
            LogService.info(f"Admission #{adm.admission_number} cancelled. Reason: {reason.strip()}", context="AdmissionService")
            return True

    def export_admissions_csv(self, dto: AdmissionFilterDTO, target_path: Optional[str | Path] = None) -> Path:
        """Exports filtered admissions into Excel-compatible CSV with installment breakdown."""
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
            "SR.NO",
            "COURSE NAME",
            "ADMISSION DATE",
            "ADMISSION ID",
            "NAME",
            "MOB NO",
            "ADMISSION STATUS",
            "TOTAL FEES",
            "1ST INSTALLMENT",
            "2ND INSTALLMENT",
            "3RD INSTALLMENT",
            "4TH INSTALLMENT",
            "TOTAL FEES PAID",
            "PENDING FEES",
            "ADDRESS",
            "FRIEND NAME",
            "FRIEND CONTACT NO",
        ]
        rows = []
        with self.unit_of_work():
            for idx, a in enumerate(admissions, start=1):
                payments = self.payment_repo.get_by_admission_id(a.id)
                inst_map = {}
                for p in payments:
                    inst_num = p.get("installment_number") or 1
                    inst_map[inst_num] = inst_map.get(inst_num, 0.0) + float(p.get("amount") or 0.0)

                inst1 = inst_map.get(1, 0.0)
                inst2 = inst_map.get(2, 0.0)
                inst3 = inst_map.get(3, 0.0)
                inst4 = inst_map.get(4, 0.0)
                total_paid = sum(inst_map.values())
                final_fee = a.agreed_fee - a.discount
                pending = max(0.0, final_fee - total_paid)

                friends = self.friendship_repo.get_friends_for_admission(a.id)
                if not friends:
                    friends = self.friendship_repo.get_confirmed_friends(a.student_id)
                friend_name = f"{friends[0]['first_name']} {friends[0]['last_name']}".strip() if friends else "—"
                friend_mobile = friends[0].get("mobile_number") or "—" if friends else "—"

                rows.append([
                    idx,
                    a.course_name,
                    a.created_at[:10],
                    a.admission_number,
                    a.student_name,
                    a.mobile_number or "—",
                    a.status,
                    f"Rs. {final_fee:,.2f}",
                    f"Rs. {inst1:,.2f}" if inst1 > 0 else "—",
                    f"Rs. {inst2:,.2f}" if inst2 > 0 else "—",
                    f"Rs. {inst3:,.2f}" if inst3 > 0 else "—",
                    f"Rs. {inst4:,.2f}" if inst4 > 0 else "—",
                    f"Rs. {total_paid:,.2f}",
                    f"Rs. {pending:,.2f}",
                    a.address or a.village or "—",
                    friend_name,
                    friend_mobile,
                ])

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
