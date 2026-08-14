# modules/admission/service.py

from __future__ import annotations

from core.logger.service import LogService
from core.service.base import BaseService
from core.exceptions import ServiceError, ValidationError, ConflictError
from modules.admission.repository import AdmissionRepository
from modules.admission_course.repository import AdmissionCourseRepository
from modules.admission.constants import AdmissionStatus
from modules.admission.dto import AdmissionCreateDTO

__all__ = ["AdmissionService"]


class AdmissionService(BaseService):
    """Business Logic Layer for Admission operations."""

    def __init__(self) -> None:
        self.repository = AdmissionRepository()
        self.bridge_repo = AdmissionCourseRepository()

    def create(self, dto: AdmissionCreateDTO) -> int:
        if not dto.student_id:
            raise ValidationError("A valid Student ID is required.")
        if not dto.course_id:
            raise ValidationError("A valid Course ID is required to complete registration.")
        if not dto.status:
            raise ValidationError("Admission status must be explicitly provided.")

        # ATOMIC TRANSACTION: If anything fails, everything rolls back.
        with self.unit_of_work():
            # 1. Check Rules
            if dto.status in (AdmissionStatus.DRAFT, AdmissionStatus.REGISTERED):
                if self.repository.has_admission_in_state(dto.student_id, dto.status.value):
                    raise ConflictError(f"Student already has an active admission in '{dto.status.value}' state.")

            # 2. Insert Core Admission
            admission_id = self.repository.insert(dto.to_dict())
            if not admission_id or admission_id <= 0:
                raise ServiceError("Failed to create admission record.")
            
            # 3. Link Course to Admission safely inside the same transaction
            self.bridge_repo.link_course(admission_id, dto.course_id)
                
            LogService.info(
                f"Admission created & Course linked successfully. ID: {admission_id}", 
                context=self.__class__.__name__
            )
            
            return admission_id
