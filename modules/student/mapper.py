# modules/student/mapper.py

from __future__ import annotations
from typing import Any, Mapping
from modules.student.dto import (
    StudentDTO,
    StudentSearchResultDTO,
    StudentAdmissionDTO,
    StudentTimelineItemDTO,
)

__all__ = ["StudentMapper", "StudentSearchMapper"]


class StudentMapper:
    """Translates raw database rows into strict domain DTOs."""

    @staticmethod
    def to_dto(row: Mapping[str, Any]) -> StudentDTO:
        """Maps a database row dictionary to StudentDTO."""
        return StudentDTO(
            id=int(row["id"]),
            first_name=str(row.get("first_name") or ""),
            last_name=str(row.get("last_name") or ""),
            mobile_number=str(row.get("mobile_number") or "") if row.get("mobile_number") else None,
            email=str(row["email"]) if row.get("email") else None,
            created_at=str(row.get("created_at") or ""),
            admissions_count=int(row.get("admissions_count") or 0),
            current_course=str(row["latest_course_name"]) if row.get("latest_course_name") else None,
            latest_admission_id=int(row["latest_admission_id"]) if row.get("latest_admission_id") else None,
            admission_status=str(row["latest_admission_status"]) if row.get("latest_admission_status") else None,
            latest_admission_date=str(row["latest_admission_date"]) if row.get("latest_admission_date") else None,
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
            course_id=int(row["course_id"]) if row.get("course_id") else None,
            course_code=str(row["course_code"]) if row.get("course_code") else None,
            course_name=str(row["course_name"]) if row.get("course_name") else None,
        )


class StudentSearchMapper:
    """Backward-compatible search mapper wrapper."""

    @staticmethod
    def to_result_dto(row: Mapping[str, Any]) -> StudentSearchResultDTO:
        return StudentMapper.to_result_dto(row)
