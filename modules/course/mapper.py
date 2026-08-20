# modules/course/mapper.py

from __future__ import annotations
from typing import Any, Mapping
from modules.course.constants import CourseStatus
from modules.course.dto import CourseDTO, CourseSearchResultDTO

__all__ = ["CourseMapper", "CourseSearchMapper"]


class CourseMapper:
    """Translates raw database rows into strict Course domain DTOs."""

    @staticmethod
    def to_dto(row: Mapping[str, Any]) -> CourseDTO:
        """Maps a database row dictionary to CourseDTO."""
        raw_status = str(row.get("status") or "ACTIVE").upper()
        try:
            status_enum = CourseStatus(raw_status)
        except ValueError:
            status_enum = CourseStatus.ACTIVE

        return CourseDTO(
            id=int(row["id"]),
            code=str(row.get("code") or ""),
            name=str(row.get("name") or ""),
            status=status_enum,
            base_fee=float(row.get("base_fee") or 0.0),
            duration=str(row["duration"]) if row.get("duration") else None,
            category=str(row.get("category") or "General"),
            description=str(row["description"]) if row.get("description") else None,
            created_at=str(row.get("created_at") or ""),
            updated_at=str(row["updated_at"]) if row.get("updated_at") else None,
        )

    @staticmethod
    def to_result_dto(row: Mapping[str, Any]) -> CourseSearchResultDTO:
        """Maps a database row to CourseSearchResultDTO for search results."""
        raw_status = str(row.get("status") or "ACTIVE").upper()
        try:
            status_enum = CourseStatus(raw_status)
        except ValueError:
            status_enum = CourseStatus.ACTIVE

        return CourseSearchResultDTO(
            id=int(row["id"]),
            code=str(row.get("code") or ""),
            name=str(row.get("name") or ""),
            status=status_enum,
        )


class CourseSearchMapper:
    """Backward-compatible search mapper wrapper."""

    @staticmethod
    def to_result_dto(row: Mapping[str, Any]) -> CourseSearchResultDTO:
        return CourseMapper.to_result_dto(row)

