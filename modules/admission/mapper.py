# modules/admission/mapper.py

from modules.admission.dto import AdmissionCreateDTO, AdmissionResponseDTO
from modules.admission.constants import AdmissionStatus

__all__ = ["AdmissionMapper"]


class AdmissionMapper:
    """Strict mapping only. No parsing, casting, or defaults."""

    @staticmethod
    def to_create_dto(data: dict[str, int | str]) -> AdmissionCreateDTO:
        return AdmissionCreateDTO(
            student_id=data["student_id"],
            course_id=data["course_id"],  # <-- Contract Fixed
            status=AdmissionStatus(data["status"])
        )

    @staticmethod
    def to_response_dto(data: dict[str, int | str]) -> AdmissionResponseDTO:
        return AdmissionResponseDTO(
            id=data["id"],
            student_id=data["student_id"],
            status=AdmissionStatus(data["status"])
        )
