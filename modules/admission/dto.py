# modules/admission/dto.py

from dataclasses import dataclass
from typing import TypedDict
from modules.admission.constants import AdmissionStatus

__all__ = ["AdmissionCreateDTO", "AdmissionResponseDTO", "AdmissionRow"]


class AdmissionRow(TypedDict):
    id: int
    student_id: int
    status: str


@dataclass
class AdmissionCreateDTO:
    """Strict contract for creating a new Admission. Now securely holds course data."""
    student_id: int
    course_id: int  # <-- Contract Fixed: No floating variables
    status: AdmissionStatus = AdmissionStatus.DRAFT

    def to_dict(self) -> dict[str, int | str]:
        return {
            "student_id": self.student_id,
            "status": self.status.value
        }

@dataclass
class AdmissionResponseDTO:
    """Strict contract returned after creating/fetching an admission."""
    id: int
    student_id: int
    status: AdmissionStatus
