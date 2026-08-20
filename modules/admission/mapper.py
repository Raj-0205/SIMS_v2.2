# modules/admission/mapper.py

from __future__ import annotations
from typing import Any, Mapping
from modules.admission.dto import AdmissionCreateDTO, AdmissionResponseDTO
from modules.admission.constants import AdmissionStatus

__all__ = ["AdmissionMapper"]


class AdmissionMapper:
    """Strict mapping only. No parsing, casting, or defaults."""

    @staticmethod
    def to_create_dto(data: Mapping[str, Any]) -> AdmissionCreateDTO:
        return AdmissionCreateDTO(
            student_id=int(data["student_id"]),
            course_id=int(data["course_id"]),
            status=AdmissionStatus(data["status"]),
            candidate_year=int(data["candidate_year"]) if data.get("candidate_year") else None,
            candidate_sequence=int(data["candidate_sequence"]) if data.get("candidate_sequence") else None,
        )

    @staticmethod
    def to_response_dto(data: Mapping[str, Any]) -> AdmissionResponseDTO:
        return AdmissionResponseDTO(
            id=int(data["id"]),
            student_id=int(data["student_id"]),
            status=AdmissionStatus(data["status"]),
            candidate_year=int(data["candidate_year"]) if data.get("candidate_year") else None,
            candidate_sequence=int(data["candidate_sequence"]) if data.get("candidate_sequence") else None,
            created_at=str(data["created_at"]) if data.get("created_at") else None,
        )
