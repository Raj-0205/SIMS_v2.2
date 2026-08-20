# modules/admission/mapper.py

from __future__ import annotations
from typing import Any, Mapping
from modules.admission.dto import (
    AdmissionCreateDTO,
    AdmissionDTO,
    AdmissionResponseDTO,
    FriendSuggestionDTO,
)
from modules.admission.constants import AdmissionStatus

__all__ = ["AdmissionMapper"]


class AdmissionMapper:
    """Mapping functions between database rows and strict domain DTOs."""

    @staticmethod
    def to_dto(row: Mapping[str, Any]) -> AdmissionDTO:
        course_fee = float(row.get("course_base_fee") or row.get("base_fee") or 0.0)
        agreed_fee = float(row.get("agreed_fee") or 0.0)
        discount = float(row.get("discount") or 0.0)
        total_paid = float(row.get("total_paid") or 0.0)

        return AdmissionDTO(
            id=int(row["id"]),
            student_id=int(row["student_id"]),
            first_name=str(row["first_name"]),
            last_name=str(row["last_name"]),
            course_id=int(row["course_id"]),
            course_code=str(row.get("course_code") or ""),
            course_name=str(row.get("course_name") or ""),
            course_fee=course_fee,
            status=str(row["status"]),
            created_at=str(row["created_at"]),
            middle_name=str(row["middle_name"]) if row.get("middle_name") else None,
            mother_name=str(row["mother_name"]) if row.get("mother_name") else None,
            parent_guardian_name=str(row["parent_guardian_name"]) if row.get("parent_guardian_name") else None,
            dob=str(row["dob"]) if row.get("dob") else None,
            gender=str(row["gender"]) if row.get("gender") else None,
            mobile_number=str(row["mobile_number"]) if row.get("mobile_number") else None,
            email=str(row["email"]) if row.get("email") else None,
            aadhaar_number=str(row["aadhaar_number"]) if row.get("aadhaar_number") else None,
            village=str(row["village"]) if row.get("village") else None,
            address=str(row["address"]) if row.get("address") else None,
            qualification=str(row["qualification"]) if row.get("qualification") else None,
            qualification_other=str(row["qualification_other"]) if row.get("qualification_other") else None,
            institution_id=int(row["institution_id"]) if row.get("institution_id") else None,
            institution_name=str(row["institution_name"]) if row.get("institution_name") else None,
            blood_group=str(row["blood_group"]) if row.get("blood_group") else None,
            batch_id=int(row["batch_id"]) if row.get("batch_id") else None,
            batch_name=str(row["batch_name"]) if row.get("batch_name") else None,
            batch_timing=str(row["timing"]) if row.get("timing") else (str(row["batch_timing"]) if row.get("batch_timing") else None),
            candidate_year=int(row["candidate_year"]) if row.get("candidate_year") else None,
            candidate_sequence=int(row["candidate_sequence"]) if row.get("candidate_sequence") else None,
            agreed_fee=agreed_fee,
            discount=discount,
            total_paid=total_paid,
            remarks=str(row["remarks"]) if row.get("remarks") else None,
            photo_path=str(row["photo_path"]) if row.get("photo_path") else None,
            signature_path=str(row["signature_path"]) if row.get("signature_path") else None,
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

    @staticmethod
    def to_friend_suggestion_dto(row: Mapping[str, Any]) -> FriendSuggestionDTO:
        yr = row.get("candidate_year")
        seq = row.get("candidate_sequence")
        adm_no = f"{yr}-{seq:03d}" if yr and seq else (f"#{row['admission_id']}" if row.get("admission_id") else None)
        return FriendSuggestionDTO(
            student_id=int(row["id"]),
            display_name=f"{row.get('first_name', '')} {row.get('last_name', '')}".strip(),
            gender=str(row["gender"]) if row.get("gender") else None,
            village=str(row["village"]) if row.get("village") else None,
            mobile_number=str(row["mobile_number"]) if row.get("mobile_number") else None,
            course_name=str(row["course_name"]) if row.get("course_name") else None,
            admission_number=adm_no,
        )
