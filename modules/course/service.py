# modules/course/service.py

from __future__ import annotations
from typing import Optional

from core.logger.service import LogService
from core.service.base import BaseService
from core.exceptions import ValidationError, ConflictError, ServiceError
from modules.course.constants import CourseStatus
from modules.course.repository import CourseRepository
from modules.course.mapper import CourseMapper, CourseSearchMapper
from modules.course.dto import (
    CourseDTO,
    CourseCreateDTO,
    CourseUpdateDTO,
    CourseSearchResultDTO,
)

__all__ = ["CourseService", "CourseSearchService"]


class CourseService(BaseService):
    """
    Business Logic Layer for Course operations.
    Enforces business rules, unique code constraints, pricing validations,
    and transactional boundaries.
    """

    def __init__(self) -> None:
        self.repository = CourseRepository()

    def _sanitize_string(self, value: Optional[str]) -> str:
        return str(value).strip() if value else ""

    def _validate_course_input(
        self, code: str, name: str, base_fee: float
    ) -> tuple[str, str, float]:
        clean_code = self._sanitize_string(code).upper()
        clean_name = self._sanitize_string(name)

        if not clean_code:
            raise ValidationError("Course code is required and cannot be blank.")
        if len(clean_code) < 2:
            raise ValidationError("Course code must be at least 2 characters.")

        if not clean_name:
            raise ValidationError("Course name is required and cannot be blank.")
        if len(clean_name) < 2:
            raise ValidationError("Course name must be at least 2 characters.")

        try:
            fee_val = float(base_fee)
        except (TypeError, ValueError):
            raise ValidationError("Base fee must be a valid numeric amount.")

        if fee_val < 0.0:
            raise ValidationError("Base fee cannot be negative.")

        return clean_code, clean_name, fee_val

    def create_course(self, dto: CourseCreateDTO) -> int:
        """
        Creates a new course entity with validation and unique code checking.
        """
        clean_code, clean_name, fee_val = self._validate_course_input(
            dto.code, dto.name, dto.base_fee
        )

        status_val = dto.status.value if isinstance(dto.status, CourseStatus) else str(dto.status or "ACTIVE").upper()
        if status_val not in (CourseStatus.ACTIVE.value, CourseStatus.INACTIVE.value):
            raise ValidationError(f"Invalid course status: '{status_val}'.")

        with self.unit_of_work():
            if self.repository.is_code_taken(clean_code):
                raise ConflictError(f"Course with code '{clean_code}' already exists.")

            insert_data = {
                "code": clean_code,
                "name": clean_name,
                "status": status_val,
                "base_fee": fee_val,
                "duration": self._sanitize_string(dto.duration) or None,
                "category": self._sanitize_string(dto.category) or "General",
                "description": self._sanitize_string(dto.description) or None,
            }

            course_id = self.repository.create(insert_data)
            if not course_id or course_id <= 0:
                raise ServiceError("Failed to create course record.")

            LogService.info(
                f"Course created successfully. ID: {course_id}, Code: {clean_code}",
                context=self.__class__.__name__,
            )
            return course_id

    def get_course(self, course_id: int) -> CourseDTO:
        """Fetches full course details by primary key."""
        if not course_id or course_id <= 0:
            raise ValidationError("A valid Course ID is required.")

        with self.unit_of_work():
            row = self.repository.get_by_id(course_id)
            if not row:
                raise ValidationError(f"Course with ID {course_id} not found.")
            return CourseMapper.to_dto(row)

    def get_course_by_code(self, code: str) -> Optional[CourseDTO]:
        """Fetches course details by business code."""
        clean_code = self._sanitize_string(code).upper()
        if not clean_code:
            return None

        with self.unit_of_work():
            row = self.repository.get_by_code(clean_code)
            return CourseMapper.to_dto(row) if row else None

    def update_course(self, dto: CourseUpdateDTO) -> None:
        """Updates an existing course with validation and duplicate checking."""
        if not dto.id or dto.id <= 0:
            raise ValidationError("A valid Course ID is required for update.")

        clean_code, clean_name, fee_val = self._validate_course_input(
            dto.code, dto.name, dto.base_fee
        )

        status_val = dto.status.value if isinstance(dto.status, CourseStatus) else str(dto.status or "ACTIVE").upper()
        if status_val not in (CourseStatus.ACTIVE.value, CourseStatus.INACTIVE.value):
            raise ValidationError(f"Invalid course status: '{status_val}'.")

        with self.unit_of_work():
            existing = self.repository.get_by_id(dto.id)
            if not existing:
                raise ValidationError(f"Course with ID {dto.id} not found.")

            if self.repository.is_code_taken(clean_code, exclude_id=dto.id):
                raise ConflictError(
                    f"Course code '{clean_code}' is already registered to another course."
                )

            update_data = {
                "code": clean_code,
                "name": clean_name,
                "status": status_val,
                "base_fee": fee_val,
                "duration": self._sanitize_string(dto.duration) or None,
                "category": self._sanitize_string(dto.category) or "General",
                "description": self._sanitize_string(dto.description) or None,
            }

            self.repository.update(dto.id, update_data)
            LogService.info(
                f"Course #{dto.id} ({clean_code}) updated successfully.",
                context=self.__class__.__name__,
            )

    def delete_course(self, course_id: int) -> None:
        """
        Deletes a course if not referenced by admissions or batches.
        """
        if not course_id or course_id <= 0:
            raise ValidationError("A valid Course ID is required for deletion.")

        with self.unit_of_work():
            existing = self.repository.get_by_id(course_id)
            if not existing:
                raise ValidationError(f"Course with ID {course_id} not found.")

            # ERP History Preservation Rules
            if self.repository.has_linked_admissions(course_id):
                raise ConflictError(
                    "Cannot delete course linked to existing admissions. "
                    "ERP audit policy preserves historical admission data."
                )

            if self.repository.has_linked_batches(course_id):
                raise ConflictError(
                    "Cannot delete course with associated batches. "
                    "Please archive or delete related batches first."
                )

            self.repository.delete(course_id)
            LogService.info(
                f"Course #{course_id} ({existing['code']}) deleted successfully.",
                context=self.__class__.__name__,
            )

    def list_courses(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
        category: Optional[str] = None,
    ) -> tuple[list[CourseDTO], int]:
        """Returns paginated courses and total count matching filters."""
        limit_val = max(1, min(limit, 200))
        offset_val = max(0, offset)

        with self.unit_of_work():
            rows = self.repository.list(
                limit=limit_val,
                offset=offset_val,
                status=status,
                category=category,
            )
            total_count = self.repository.count(status=status, category=category)
            return [CourseMapper.to_dto(r) for r in rows], total_count

    def count_courses(
        self, status: Optional[str] = None, category: Optional[str] = None
    ) -> int:
        """Returns total course count matching optional filters."""
        with self.unit_of_work():
            return self.repository.count(status=status, category=category)

    def search_courses(
        self, query: str, limit: int = 25, active_only: bool = False
    ) -> list[CourseSearchResultDTO]:
        """
        Searches courses by code or name.
        Enforces 2-character minimum query requirement.
        """
        clean_query = self._sanitize_string(query)
        if not clean_query or len(clean_query) < 2:
            return []

        with self.unit_of_work():
            rows = self.repository.search(clean_query, limit=limit, active_only=active_only)
            return [CourseSearchMapper.to_result_dto(row) for row in rows]


class CourseSearchService(CourseService):
    """
    Backward-compatibility wrapper for existing CourseSearchService usages.
    """
    pass

