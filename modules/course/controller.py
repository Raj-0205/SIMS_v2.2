# modules/course/controller.py

from __future__ import annotations
from typing import Any, Mapping, Optional

from modules.course.constants import CourseStatus
from modules.course.service import CourseService
from modules.course.dto import (
    CourseDTO,
    CourseCreateDTO,
    CourseUpdateDTO,
    CourseSearchResultDTO,
)

__all__ = ["CourseController"]


class CourseController:
    """
    Application Layer for Course operations.
    Acts as a thin pass-through between UI and Business Services.
    Converts raw UI payloads into strict DTOs and handles no business logic directly.
    """

    def __init__(self) -> None:
        self.service = CourseService()
        self.search_service = self.service

    def create_course(self, raw_data: Mapping[str, Any]) -> int:
        """Translates raw form dictionary into CourseCreateDTO and delegates."""
        raw_status = str(raw_data.get("status") or "ACTIVE").upper()
        try:
            status_enum = CourseStatus(raw_status)
        except ValueError:
            status_enum = CourseStatus.ACTIVE

        raw_fee = raw_data.get("base_fee")
        base_fee_val = float(raw_fee) if raw_fee is not None and str(raw_fee).strip() != "" else 0.0

        dto = CourseCreateDTO(
            code=str(raw_data.get("code") or "").strip(),
            name=str(raw_data.get("name") or "").strip(),
            base_fee=base_fee_val,
            duration=str(raw_data.get("duration") or "").strip() or None,
            category=str(raw_data.get("category") or "General").strip(),
            description=str(raw_data.get("description") or "").strip() or None,
            status=status_enum,
        )
        return self.service.create_course(dto)

    def update_course(self, course_id: int, raw_data: Mapping[str, Any]) -> None:
        """Translates raw form dictionary into CourseUpdateDTO and delegates."""
        raw_status = str(raw_data.get("status") or "ACTIVE").upper()
        try:
            status_enum = CourseStatus(raw_status)
        except ValueError:
            status_enum = CourseStatus.ACTIVE

        raw_fee = raw_data.get("base_fee")
        base_fee_val = float(raw_fee) if raw_fee is not None and str(raw_fee).strip() != "" else 0.0

        dto = CourseUpdateDTO(
            id=course_id,
            code=str(raw_data.get("code") or "").strip(),
            name=str(raw_data.get("name") or "").strip(),
            base_fee=base_fee_val,
            duration=str(raw_data.get("duration") or "").strip() or None,
            category=str(raw_data.get("category") or "General").strip(),
            description=str(raw_data.get("description") or "").strip() or None,
            status=status_enum,
        )
        self.service.update_course(dto)

    def delete_course(self, course_id: int) -> None:
        """Deletes course record via service."""
        self.service.delete_course(course_id)

    def get_course(self, course_id: int) -> CourseDTO:
        """Fetches full course details by ID."""
        return self.service.get_course(course_id)

    def get_course_by_code(self, code: str) -> Optional[CourseDTO]:
        """Fetches course details by Code."""
        return self.service.get_course_by_code(code)

    def list_courses(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
        category: Optional[str] = None,
    ) -> tuple[list[CourseDTO], int]:
        """Returns paginated list of courses and total count."""
        return self.service.list_courses(
            limit=limit, offset=offset, status=status, category=category
        )

    def count_courses(
        self, status: Optional[str] = None, category: Optional[str] = None
    ) -> int:
        """Returns total course count."""
        return self.service.count_courses(status=status, category=category)

    def search_courses(
        self, query: str, limit: int = 25, active_only: bool = False
    ) -> list[CourseSearchResultDTO]:
        """
        Receives raw UI search query, strips whitespace, and delegates.
        Mandatory for Admission module backward compatibility.
        """
        clean_query = str(query).strip() if query else ""
        return self.service.search_courses(clean_query, limit=limit, active_only=active_only)

