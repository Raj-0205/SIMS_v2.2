# modules/course/service.py

from __future__ import annotations
from typing import Optional

from core.logger.service import LogService
from core.service.base import BaseService
from core.exceptions import ValidationError, ConflictError, ServiceError
from core.security.authorization import AuthorizationService
from core.security.permissions import Permission
from modules.course.constants import CourseStatus
from modules.course.repository import CourseRepository
from modules.course.mapper import CourseMapper, CourseSearchMapper
from modules.course.dto import (
    CourseDTO,
    CourseCreateDTO,
    CourseUpdateDTO,
    CourseSearchResultDTO,
    CourseFeeChangeDTO,
    CourseFeeHistoryDTO,
    CourseOperationalSummaryDTO,
)
from modules.settings.service import SettingsService
from modules.admission.activity_log_repository import ActivityLogRepository

__all__ = ["CourseService", "CourseSearchService"]


class CourseService(BaseService):
    """
    Business Logic Layer for Course operations.
    Enforces business rules, unique code constraints, pricing validations,
    admin PIN authorization for fee revisions, and transactional boundaries.
    """

    def __init__(self) -> None:
        self.repository = CourseRepository()
        self.settings_service = SettingsService()
        self.activity_log_repo = ActivityLogRepository()

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
        AuthorizationService.enforce(Permission.COURSE_CREATE)
        clean_code, clean_name, fee_val = self._validate_course_input(
            dto.code, dto.name, dto.base_fee
        )

        status_val = (
            dto.status.value
            if isinstance(dto.status, CourseStatus)
            else str(dto.status or "ACTIVE").upper()
        )
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

            self.activity_log_repo.insert(
                entity_type="COURSE",
                entity_id=course_id,
                action="CREATED",
                actor_name="ADMIN",
                details=f"Created course {clean_name} ({clean_code}) with initial Institute Fee ₹{fee_val:,.2f}",
            )

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
        """
        Updates non-financial course metadata with validation and duplicate checking.
        Preserves base_fee if already set, or updates if explicitly authorized.
        """
        AuthorizationService.enforce(Permission.COURSE_MANAGE)
        if not dto.id or dto.id <= 0:
            raise ValidationError("A valid Course ID is required for update.")

        clean_code, clean_name, fee_val = self._validate_course_input(
            dto.code, dto.name, dto.base_fee
        )

        status_val = (
            dto.status.value
            if isinstance(dto.status, CourseStatus)
            else str(dto.status or "ACTIVE").upper()
        )
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

            # Preserve existing base_fee unless changed via change_institute_fee
            preserved_fee = float(existing.get("base_fee", fee_val))

            update_data = {
                "code": clean_code,
                "name": clean_name,
                "status": status_val,
                "base_fee": preserved_fee,
                "duration": self._sanitize_string(dto.duration) or None,
                "category": self._sanitize_string(dto.category) or "General",
                "description": self._sanitize_string(dto.description) or None,
            }

            self.repository.update(dto.id, update_data)
            LogService.info(
                f"Course #{dto.id} ({clean_code}) updated successfully.",
                context=self.__class__.__name__,
            )

    def change_institute_fee(self, dto: CourseFeeChangeDTO) -> None:
        """
        Atomically updates the default Institute Course Fee for new admissions.
        Enforces Admin PIN authorization, reason validation, no-op rejection,
        fee history recording, and activity logging within ONE atomic transaction.
        """
        AuthorizationService.enforce(Permission.COURSE_MANAGE)
        if not dto.course_id or dto.course_id <= 0:
            raise ValidationError("A valid Course ID is required for fee modification.")

        try:
            new_fee_val = float(dto.new_fee)
        except (TypeError, ValueError):
            raise ValidationError("New Institute Fee must be a valid numeric amount.")

        if new_fee_val < 0.0:
            raise ValidationError("Institute Fee cannot be negative.")

        clean_reason = self._sanitize_string(dto.reason)
        if not clean_reason:
            raise ValidationError("A reason for revising the course fee is required.")
        if len(clean_reason) < 3:
            raise ValidationError("Reason for fee revision must be at least 3 characters long.")

        # Admin PIN Authorization
        if not dto.admin_pin or not self.settings_service.verify_admin_pin(dto.admin_pin):
            raise ValidationError("Invalid Admin Authorization PIN. Fee change rejected.")

        with self.unit_of_work():
            existing = self.repository.get_by_id(dto.course_id)
            if not existing:
                raise ValidationError(f"Course with ID {dto.course_id} not found.")

            old_fee_val = float(existing.get("base_fee") or 0.0)
            if abs(old_fee_val - new_fee_val) < 0.01:
                raise ValidationError("New fee cannot be identical to the current fee.")

            # Update base_fee on courses
            update_data = dict(existing)
            update_data["base_fee"] = new_fee_val
            self.repository.update(dto.course_id, update_data)

            # Insert audit history
            actor_user_id = getattr(dto, "user_id", None) or getattr(dto, "changed_by_user_id", None)
            actor_username = self._sanitize_string(getattr(dto, "username", None) or getattr(dto, "changed_by_username", None)) or "ADMIN"
            history_id = self.repository.insert_fee_history(
                course_id=dto.course_id,
                old_fee=old_fee_val,
                new_fee=new_fee_val,
                reason=clean_reason,
                changed_by_username=actor_username,
                changed_by_user_id=actor_user_id,
            )

            # Insert activity log
            self.activity_log_repo.insert(
                entity_type="COURSE",
                entity_id=dto.course_id,
                action="FEE_CHANGED",
                actor_name=actor_username,
                actor_id=actor_user_id,
                details=f"Base fee updated from {old_fee_val:.2f} to {new_fee_val:.2f}. Reason: {clean_reason}",
            )

            LogService.info(
                f"Course #{dto.course_id} fee changed from {old_fee_val:.2f} to {new_fee_val:.2f}. History #{history_id}.",
                context=self.__class__.__name__,
            )

    def get_fee_history(self, course_id: int, limit: int = 50) -> list[CourseFeeHistoryDTO]:
        """Returns the fee revision audit trail for a course in reverse-chronological order."""
        if not course_id or course_id <= 0:
            return []
        with self.unit_of_work():
            rows = self.repository.get_fee_history(course_id, limit=limit)
            return [CourseMapper.to_fee_history_dto(r) for r in rows]

    def toggle_status(self, course_id: int) -> CourseStatus:
        """Toggles a course status between ACTIVE and INACTIVE."""
        AuthorizationService.enforce(Permission.COURSE_MANAGE)
        if not course_id or course_id <= 0:
            raise ValidationError("A valid Course ID is required.")

        with self.unit_of_work():
            existing = self.repository.get_by_id(course_id)
            if not existing:
                raise ValidationError(f"Course with ID {course_id} not found.")

            current_status = str(existing.get("status") or "ACTIVE").upper()
            new_status = CourseStatus.INACTIVE if current_status == CourseStatus.ACTIVE.value else CourseStatus.ACTIVE

            update_data = dict(existing)
            update_data["status"] = new_status.value
            self.repository.update(course_id, update_data)

            self.activity_log_repo.insert(
                entity_type="COURSE",
                entity_id=course_id,
                action="STATUS_CHANGED",
                actor_name="ADMIN",
                details=f"Course status changed from {current_status} to {new_status.value}",
            )

            LogService.info(
                f"Course #{course_id} status toggled to {new_status.value}.",
                context=self.__class__.__name__,
            )
            return new_status

    def delete_course(self, course_id: int) -> None:
        """
        Deletes a course if not referenced by admissions or batches.
        """
        AuthorizationService.enforce(Permission.COURSE_DELETE)
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
        search: Optional[str] = None,
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
                search=search,
            )
            total_count = self.repository.count(
                status=status, category=category, search=search
            )
            return [CourseMapper.to_dto(r) for r in rows], total_count

    def count_courses(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
    ) -> int:
        """Returns total course count matching optional filters."""
        with self.unit_of_work():
            return self.repository.count(status=status, category=category, search=search)

    def get_categories(self) -> list[str]:
        """Returns distinct non-empty category names from database."""
        with self.unit_of_work():
            return self.repository.get_categories()

    def get_operational_summary(self, course_id: int) -> CourseOperationalSummaryDTO:
        """Returns operational summary for a specific course."""
        if not course_id or course_id <= 0:
            return CourseOperationalSummaryDTO(course_id=course_id)
        with self.unit_of_work():
            raw = self.repository.get_operational_summary(course_id)
            return CourseMapper.to_operational_summary_dto(course_id, raw)

    def get_overall_summary(self) -> dict[str, int]:
        """Returns high-level KPI counts across all courses."""
        with self.unit_of_work():
            return self.repository.get_overall_summary()

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
