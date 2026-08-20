# modules/student/mapper.py

from __future__ import annotations
from typing import Any, Mapping
from modules.student.dto import (
    StudentDTO,
    StudentSearchResultDTO,
    StudentAdmissionDTO,
)

__all__ = ["StudentMapper", "StudentSearchMapper"]


class StudentMapper:
    """Translates raw database rows into strict domain DTOs."""

    @staticmethod
    def to_dto(row: Mapping[str, Any]) -> StudentDTO:
        """Maps a database row dictionary to StudentDTO."""
        raw_fee = row.get("latest_course_base_fee")
        base_fee_val = float(raw_fee) if raw_fee is not None else None

        return StudentDTO(
            id=int(row["id"]),
            first_name=str(row.get("first_name") or ""),
            last_name=str(row.get("last_name") or ""),
            mobile_number=str(row.get("mobile_number") or "") if row.get("mobile_number") else None,
            email=str(row["email"]) if row.get("email") else None,
            address=str(row["address"]) if row.get("address") else None,
            created_at=str(row.get("created_at") or ""),
            admissions_count=int(row.get("admissions_count") or 0),
            course_id=int(row["latest_course_id"]) if row.get("latest_course_id") else None,
            current_course=str(row["latest_course_name"]) if row.get("latest_course_name") else None,
            latest_admission_id=int(row["latest_admission_id"]) if row.get("latest_admission_id") else None,
            latest_admission_year=int(row["latest_admission_year"]) if row.get("latest_admission_year") else None,
            latest_admission_seq=int(row["latest_admission_seq"]) if row.get("latest_admission_seq") else None,
            admission_status=str(row["latest_admission_status"]) if row.get("latest_admission_status") else None,
            latest_admission_date=str(row["latest_admission_date"]) if row.get("latest_admission_date") else None,
            total_fee=base_fee_val,
            paid_amount=None,      # Pending Finance Engine
            pending_amount=None,   # Pending Finance Engine
        )

    @staticmethod
    def to_result_dto(row: Mapping[str, Any]) -> StudentSearchResultDTO:
        """Maps a database row to StudentSearchResultDTO."""
        return StudentSearchResultDTO(
            id=int(row["id"]),
            first_name=str(row.get("first_name") or ""),
            last_name=str(row.get("last_name") or ""),
            mobile_number=str(row.get("mobile_number") or "") if row.get("mobile_number") else None,
        )

    @staticmethod
    def to_admission_dto(row: Mapping[str, Any]) -> StudentAdmissionDTO:
        """Maps a joined admission row to StudentAdmissionDTO."""
        return StudentAdmissionDTO(
            admission_id=int(row["admission_id"]),
            student_id=int(row["student_id"]),
            status=str(row.get("status") or "UNKNOWN"),
            admission_date=str(row.get("admission_date") or ""),
            candidate_year=int(row["candidate_year"]) if row.get("candidate_year") else None,
            candidate_sequence=int(row["candidate_sequence"]) if row.get("candidate_sequence") else None,
            course_id=int(row["course_id"]) if row.get("course_id") else None,
            course_code=str(row["course_code"]) if row.get("course_code") else None,
            course_name=str(row["course_name"]) if row.get("course_name") else None,
        )


class StudentSearchMapper:
    """Backward-compatible search mapper wrapper."""

    @staticmethod
    def to_result_dto(row: Mapping[str, Any]) -> StudentSearchResultDTO:
        return StudentMapper.to_result_dto(row)
