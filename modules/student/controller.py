# modules/student/controller.py

from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping, Optional

from modules.student.service import StudentService
from modules.student.dto import (
    StudentDTO,
    StudentFilterDTO,
    StudentCreateDTO,
    StudentUpdateDTO,
    StudentSearchResultDTO,
    StudentWorkspaceDTO,
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
        self.search_service = self.service

    def create_student(self, raw_data: Mapping[str, Any]) -> int:
        """Translates raw form dictionary into StudentCreateDTO and delegates."""
        dto = StudentCreateDTO(
            first_name=str(raw_data.get("first_name") or "").strip(),
            last_name=str(raw_data.get("last_name") or "").strip(),
            mobile_number=str(raw_data.get("mobile_number") or "").strip() or None,
            email=str(raw_data.get("email") or "").strip() or None,
        )
        return self.service.create_student(dto)

    def update_student(self, student_id: int, raw_data: Mapping[str, Any]) -> None:
        """Translates raw form dictionary into StudentUpdateDTO and delegates."""
        dto = StudentUpdateDTO(
            id=student_id,
            first_name=str(raw_data.get("first_name") or "").strip(),
            last_name=str(raw_data.get("last_name") or "").strip(),
            mobile_number=str(raw_data.get("mobile_number") or "").strip() or None,
            email=str(raw_data.get("email") or "").strip() or None,
        )
        self.service.update_student(dto)

    def delete_student(self, student_id: int) -> None:
        """Deletes student record via service."""
        self.service.delete_student(student_id)

    def get_student(self, student_id: int) -> StudentDTO:
        """Fetches full student profile by ID."""
        return self.service.get_student(student_id)

    def get_student_workspace(self, student_id: int) -> StudentWorkspaceDTO:
        """Fetches aggregate data required by the Student Workspace."""
        return self.service.get_student_workspace(student_id)

    def filter_students(self, raw_filter: Mapping[str, Any]) -> tuple[list[StudentDTO], int]:
        """Translates raw filter map into StudentFilterDTO and delegates."""
        # Resolve sort_keys: expects list of (field, direction) tuples or None
        raw_sort_keys = raw_filter.get("sort_keys")
        sort_keys_tuple: tuple[tuple[str, str], ...] = ()
        if raw_sort_keys and isinstance(raw_sort_keys, (list, tuple)):
            sort_keys_tuple = tuple(
                (str(sk[0]).strip(), str(sk[1]).strip()) for sk in raw_sort_keys if len(sk) >= 2
            )

        dto = StudentFilterDTO(
            query=str(raw_filter.get("query")).strip() if raw_filter.get("query") else None,
            course_id=int(raw_filter["course_id"]) if raw_filter.get("course_id") else None,
            status=str(raw_filter["status"]).strip() if raw_filter.get("status") else None,
            year=int(raw_filter["year"]) if raw_filter.get("year") else None,
            month=int(raw_filter["month"]) if raw_filter.get("month") else None,
            sort_by=str(raw_filter.get("sort_by") or "id").strip(),
            sort_dir=str(raw_filter.get("sort_dir") or "desc").strip(),
            sort_keys=sort_keys_tuple,
            limit=int(raw_filter.get("limit") or 50),
            offset=int(raw_filter.get("offset") or 0),
        )
        return self.service.filter_students(dto)

    def export_students_csv(
        self, raw_filter: Mapping[str, Any], target_path: Optional[str] = None
    ) -> str:
        """Translates raw filter map and exports matching student data to Excel CSV."""
        raw_sort_keys = raw_filter.get("sort_keys")
        sort_keys_tuple: tuple[tuple[str, str], ...] = ()
        if raw_sort_keys and isinstance(raw_sort_keys, (list, tuple)):
            sort_keys_tuple = tuple(
                (str(sk[0]).strip(), str(sk[1]).strip()) for sk in raw_sort_keys if len(sk) >= 2
            )

        dto = StudentFilterDTO(
            query=str(raw_filter.get("query")).strip() if raw_filter.get("query") else None,
            course_id=int(raw_filter["course_id"]) if raw_filter.get("course_id") else None,
            status=str(raw_filter["status"]).strip() if raw_filter.get("status") else None,
            year=int(raw_filter["year"]) if raw_filter.get("year") else None,
            month=int(raw_filter["month"]) if raw_filter.get("month") else None,
            sort_by=str(raw_filter.get("sort_by") or "id").strip(),
            sort_dir=str(raw_filter.get("sort_dir") or "desc").strip(),
            sort_keys=sort_keys_tuple,
        )
        path = self.service.export_students_csv(dto, target_path=target_path)
        return str(path)

    def export_students_pdf(
        self, raw_filter: Mapping[str, Any], target_path: Optional[str] = None
    ) -> str:
        """Translates raw filter map and exports matching student data to PDF report."""
        raw_sort_keys = raw_filter.get("sort_keys")
        sort_keys_tuple: tuple[tuple[str, str], ...] = ()
        if raw_sort_keys and isinstance(raw_sort_keys, (list, tuple)):
            sort_keys_tuple = tuple(
                (str(sk[0]).strip(), str(sk[1]).strip()) for sk in raw_sort_keys if len(sk) >= 2
            )

        dto = StudentFilterDTO(
            query=str(raw_filter.get("query")).strip() if raw_filter.get("query") else None,
            course_id=int(raw_filter["course_id"]) if raw_filter.get("course_id") else None,
            status=str(raw_filter["status"]).strip() if raw_filter.get("status") else None,
            year=int(raw_filter["year"]) if raw_filter.get("year") else None,
            month=int(raw_filter["month"]) if raw_filter.get("month") else None,
            sort_by=str(raw_filter.get("sort_by") or "id").strip(),
            sort_dir=str(raw_filter.get("sort_dir") or "desc").strip(),
            sort_keys=sort_keys_tuple,
        )
        path = self.service.export_students_pdf(dto, target_path=target_path)
        return str(path)

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
