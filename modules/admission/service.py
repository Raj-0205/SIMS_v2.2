# modules/admission/service.py

from __future__ import annotations
from datetime import datetime
from typing import Optional

from core.logger.service import LogService
from core.service.base import BaseService
from core.exceptions import ServiceError, ValidationError, ConflictError
from modules.admission.repository import AdmissionRepository
from modules.admission_course.repository import AdmissionCourseRepository
from modules.admission.constants import AdmissionStatus
from modules.admission.dto import AdmissionCreateDTO, AdmissionResponseDTO
from modules.admission.mapper import AdmissionMapper

__all__ = ["AdmissionService"]


class AdmissionService(BaseService):
    """
    Business Logic Layer for Admission operations.
    Enforces atomic candidate sequence generation (YYYY-NNN),
    state restrictions, and course linkage.
    """

    def __init__(self) -> None:
        self.repository = AdmissionRepository()
        self.bridge_repo = AdmissionCourseRepository()

    def create(self, dto: AdmissionCreateDTO) -> int:
        """
        Creates a new admission record with an atomic yearly candidate sequence (YYYY-NNN).
        """
        if not dto.student_id:
            raise ValidationError("A valid Student ID is required.")
        if not dto.course_id:
            raise ValidationError("A valid Course ID is required to complete registration.")
        if not dto.status:
            raise ValidationError("Admission status must be explicitly provided.")

        # ATOMIC TRANSACTION: Sequence generation + Admission insertion + Bridge linking
        with self.unit_of_work():
            # 1. State-Restricted Rule
            if dto.status in (AdmissionStatus.DRAFT, AdmissionStatus.REGISTERED):
                if self.repository.has_admission_in_state(dto.student_id, dto.status.value):
                    raise ConflictError(f"Student already has an active admission in '{dto.status.value}' state.")

            # 2. Determine Candidate Year & Sequence (YYYY-NNN)
            admission_year = dto.candidate_year or datetime.now().year
            if dto.candidate_sequence:
                next_seq = dto.candidate_sequence
            else:
                next_seq = self.repository.get_next_sequence_for_year(admission_year)

            insert_data = {
                "student_id": dto.student_id,
                "status": dto.status.value,
                "candidate_year": admission_year,
                "candidate_sequence": next_seq,
            }

            # 3. Insert Core Admission
            admission_id = self.repository.insert(insert_data)
            if not admission_id or admission_id <= 0:
                raise ServiceError("Failed to create admission record.")

            # 4. Link Course to Admission safely inside the same transaction
            self.bridge_repo.link_course(admission_id, dto.course_id)

            admission_no = f"{admission_year}-{next_seq:03d}"
            LogService.info(
                f"Admission created successfully. ID: {admission_id}, Candidate No: {admission_no}",
                context=self.__class__.__name__,
            )

            return admission_id

    def get_admission(self, admission_id: int) -> AdmissionResponseDTO:
        """Retrieves admission by ID."""
        with self.unit_of_work():
            row = self.repository.get_by_id(admission_id)
            if not row:
                raise ValidationError(f"Admission with ID {admission_id} not found.")
            return AdmissionMapper.to_response_dto(row)
