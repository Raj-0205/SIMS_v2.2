# modules/student/controller.py

from __future__ import annotations
from typing import Any, Mapping

from modules.student.service import StudentService
from modules.student.dto import (
    StudentDTO,
    StudentCreateDTO,
    StudentUpdateDTO,
    StudentSearchResultDTO,
)

__all__ = ["StudentController"]


class StudentController:
    """
    Application Layer for Student operations.
    Acts as a thin pass-through between UI and Business Services.
    Converts raw UI payloads into strict DTOs and handles no business logic directly.
    """

    def __init__(self) -> None:
        self.service = StudentService()
        # Keep search_service alias for any legacy internal reference
        self.search_service = self.service

    def create_student(self, raw_data: Mapping[str, Any]) -> int:
        """Translates raw form dictionary into StudentCreateDTO and delegates."""
        dto = StudentCreateDTO(
            first_name=str(raw_data.get("first_name") or "").strip(),
            last_name=str(raw_data.get("last_name") or "").strip(),
            mobile_number=str(raw_data.get("mobile_number") or "").strip(),
            email=str(raw_data.get("email") or "").strip() or None,
        )
        return self.service.create_student(dto)

    def update_student(self, student_id: int, raw_data: Mapping[str, Any]) -> None:
        """Translates raw form dictionary into StudentUpdateDTO and delegates."""
        dto = StudentUpdateDTO(
            id=student_id,
            first_name=str(raw_data.get("first_name") or "").strip(),
            last_name=str(raw_data.get("last_name") or "").strip(),
            mobile_number=str(raw_data.get("mobile_number") or "").strip(),
            email=str(raw_data.get("email") or "").strip() or None,
        )
        self.service.update_student(dto)

    def get_student(self, student_id: int) -> StudentDTO:
        """Fetches full student profile by ID."""
        return self.service.get_student(student_id)

    def list_students(self, limit: int = 50, offset: int = 0) -> tuple[list[StudentDTO], int]:
        """Returns paginated list of students and total count."""
        return self.service.list_students(limit=limit, offset=offset)

    def search_students_paged(
        self, query: str, limit: int = 50, offset: int = 0
    ) -> tuple[list[StudentDTO], int]:
        """Returns filtered, paginated student records."""
        clean_query = str(query).strip() if query else ""
        return self.service.search_students_paged(clean_query, limit=limit, offset=offset)

    def count_students(self) -> int:
        """Returns total student count."""
        return self.service.count_students()

    def search_students(self, query: str) -> list[StudentSearchResultDTO]:
        """
        Receives raw UI search query, strips whitespace, and delegates.
        Mandatory for Admission module backward compatibility.
        """
        clean_query = str(query).strip() if query else ""
        return self.service.search_students(clean_query)
