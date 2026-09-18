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
    CourseFeeChangeDTO,
    CourseFeeHistoryDTO,
    CourseOperationalSummaryDTO,
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
        base_fee_val = (
            float(raw_fee) if raw_fee is not None and str(raw_fee).strip() != "" else 0.0
        )

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
        base_fee_val = (
            float(raw_fee) if raw_fee is not None and str(raw_fee).strip() != "" else 0.0
        )

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

    def change_institute_fee(
        self,
        course_id: int,
        raw_data: Mapping[str, Any],
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> None:
        """Translates raw fee change dictionary into CourseFeeChangeDTO and delegates."""
        raw_fee = raw_data.get("new_fee")
        new_fee_val = float(raw_fee) if raw_fee is not None and str(raw_fee).strip() != "" else 0.0

        dto = CourseFeeChangeDTO(
            course_id=course_id,
            new_fee=new_fee_val,
            admin_pin=str(raw_data.get("admin_pin") or "").strip(),
            reason=str(raw_data.get("reason") or "").strip(),
            user_id=user_id,
            username=username,
        )
        self.service.change_institute_fee(dto)

    def get_fee_history(self, course_id: int, limit: int = 50) -> list[CourseFeeHistoryDTO]:
        """Fetches fee history records for a course."""
        return self.service.get_fee_history(course_id, limit=limit)

    def toggle_status(self, course_id: int) -> CourseStatus:
        """Toggles course status between ACTIVE and INACTIVE."""
        return self.service.toggle_status(course_id)

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
        search: Optional[str] = None,
    ) -> tuple[list[CourseDTO], int]:
        """Returns paginated list of courses and total count."""
        return self.service.list_courses(
            limit=limit,
            offset=offset,
            status=status,
            category=category,
            search=search,
        )

    def count_courses(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
    ) -> int:
        """Returns total course count."""
        return self.service.count_courses(
            status=status, category=category, search=search
        )

    def get_categories(self) -> list[str]:
        """Returns distinct category list."""
        return self.service.get_categories()

    def get_operational_summary(self, course_id: int) -> CourseOperationalSummaryDTO:
        """Returns operational summary metrics for a course."""
        return self.service.get_operational_summary(course_id)

    def get_overall_summary(self) -> dict[str, int]:
        """Returns high-level KPI counts."""
        return self.service.get_overall_summary()

    def search_courses(
        self, query: str, limit: int = 25, active_only: bool = False
    ) -> list[CourseSearchResultDTO]:
        """
        Receives raw UI search query, strips whitespace, and delegates.
        Mandatory for Admission module backward compatibility.
        """
        clean_query = str(query).strip() if query else ""
        return self.service.search_courses(
            clean_query, limit=limit, active_only=active_only
        )
