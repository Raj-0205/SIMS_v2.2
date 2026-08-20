# modules/admission/dto.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, TypedDict
from modules.admission.constants import AdmissionStatus

__all__ = ["AdmissionCreateDTO", "AdmissionResponseDTO", "AdmissionRow"]


class AdmissionRow(TypedDict):
    id: int
    student_id: int
    status: str
    created_at: str
    candidate_year: Optional[int]
    candidate_sequence: Optional[int]


@dataclass(frozen=True)
class AdmissionCreateDTO:
    """Strict contract for creating a new Admission."""
    student_id: int
    course_id: int
    status: AdmissionStatus = AdmissionStatus.DRAFT
    candidate_year: Optional[int] = None
    candidate_sequence: Optional[int] = None

    def to_dict(self) -> dict[str, int | str | None]:
        return {
            "student_id": self.student_id,
            "status": self.status.value,
            "candidate_year": self.candidate_year,
            "candidate_sequence": self.candidate_sequence,
        }


@dataclass(frozen=True)
class AdmissionResponseDTO:
    """
    Strict contract returned after creating/fetching an admission.
    Exposes both internal integer PK (id) and human-facing Admission Number (admission_number).
    """
    id: int
    student_id: int
    status: AdmissionStatus
    candidate_year: Optional[int] = None
    candidate_sequence: Optional[int] = None
    created_at: Optional[str] = None

    @property
    def admission_number(self) -> str:
        """
        ERP-facing business identifier format: YYYY-NNN.
        e.g. 2026-001, 2026-002, 2027-001.
        """
        if self.candidate_year and self.candidate_sequence:
            return f"{self.candidate_year}-{self.candidate_sequence:03d}"
        return f"#{self.id}"
