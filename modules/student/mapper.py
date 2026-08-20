# modules/student/mapper.py

from __future__ import annotations
from typing import Any, Mapping
from modules.student.dto import (
    StudentDTO,
    StudentSearchResultDTO,
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
            mobile_number=str(row.get("mobile_number") or ""),
            email=str(row["email"]) if row.get("email") else None,
            created_at=str(row.get("created_at") or ""),
        )

    @staticmethod
    def to_result_dto(row: Mapping[str, Any]) -> StudentSearchResultDTO:
        """Maps a database row to StudentSearchResultDTO."""
        return StudentSearchResultDTO(
            id=int(row["id"]),
            first_name=str(row.get("first_name") or ""),
            last_name=str(row.get("last_name") or ""),
            mobile_number=str(row.get("mobile_number") or ""),
        )


class StudentSearchMapper:
    """Backward-compatible search mapper wrapper."""

    @staticmethod
    def to_result_dto(row: Mapping[str, Any]) -> StudentSearchResultDTO:
        return StudentMapper.to_result_dto(row)
