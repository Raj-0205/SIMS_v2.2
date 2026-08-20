# modules/batch/service.py

from __future__ import annotations
from datetime import datetime
from typing import Optional

from core.logger.service import LogService
from core.service.base import BaseService
from core.exceptions import ValidationError, ConflictError, ServiceError
from modules.batch.constants import BatchStatus
from modules.batch.repository import BatchRepository
from modules.batch.mapper import BatchMapper
from modules.batch.dto import (
    BatchDTO,
    BatchCreateDTO,
    BatchUpdateDTO,
    BatchSummaryDTO,
    BatchCapacityDTO,
)

__all__ = ["BatchService"]


class BatchService(BaseService):
    """
    Business Logic Layer for Batch Management.
    Enforces business rules, capacity bounds, date range constraints,
    course existence, scoped unique batch names, and transactional safety.
    """

    def __init__(self) -> None:
        self.repository = BatchRepository()

    def _sanitize_string(self, value: Optional[str]) -> str:
        return str(value).strip() if value else ""

    def _validate_date_string(self, date_str: Optional[str], field_name: str) -> Optional[str]:
        clean = self._sanitize_string(date_str)
        if not clean:
            return None
        # Support YYYY-MM-DD (ISO)
        try:
            parsed = datetime.strptime(clean[:10], "%Y-%m-%d")
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            raise ValidationError(f"{field_name} must be a valid date in YYYY-MM-DD format.")

    def _validate_batch_input(
        self,
        course_id: int,
        batch_name: str,
        timing: str,
        max_capacity: int,
        status: BatchStatus | str,
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> tuple[int, str, str, int, str, Optional[str], Optional[str]]:
        if not course_id or int(course_id) <= 0:
            raise ValidationError("A valid Course ID is required.")

        clean_name = self._sanitize_string(batch_name)
        if not clean_name:
            raise ValidationError("Batch name is required and cannot be blank.")
        if len(clean_name) < 2:
            raise ValidationError("Batch name must be at least 2 characters.")

        clean_timing = self._sanitize_string(timing)
        if not clean_timing:
            raise ValidationError("Timing is required and cannot be blank.")

        try:
            cap_val = int(max_capacity)
        except (TypeError, ValueError):
            raise ValidationError("Max capacity must be a valid positive integer.")

        if cap_val <= 0:
            raise ValidationError("Max capacity must be greater than 0.")

        status_val = status.value if isinstance(status, BatchStatus) else str(status or "OPEN").upper()
        valid_statuses = {s.value for s in BatchStatus}
        if status_val not in valid_statuses:
            raise ValidationError(f"Invalid batch status: '{status_val}'. Must be one of {sorted(valid_statuses)}.")

        clean_start = self._validate_date_string(start_date, "Start date")
        clean_end = self._validate_date_string(end_date, "End date")

        if clean_start and clean_end:
            if clean_end < clean_start:
                raise ValidationError("End date cannot be earlier than start date.")

        return int(course_id), clean_name, clean_timing, cap_val, status_val, clean_start, clean_end

    def create_batch(self, dto: BatchCreateDTO) -> int:
        """
        Creates a new batch with validation and scoped unique name verification.
        """
        course_id, clean_name, clean_timing, cap_val, status_val, clean_start, clean_end = (
            self._validate_batch_input(
                dto.course_id,
                dto.batch_name,
                dto.timing,
                dto.max_capacity,
                dto.status,
                dto.start_date,
                dto.end_date,
            )
        )

        with self.unit_of_work():
            # 1. Verify Course exists
            if not self.repository.course_exists(course_id):
                raise ValidationError(f"Referenced course with ID {course_id} does not exist.")

            # 2. Check Scoped Uniqueness (course_id, batch_name)
            if self.repository.is_name_taken(course_id, clean_name):
                raise ConflictError(
                    f"A batch named '{clean_name}' already exists for this course."
                )

            insert_data = {
                "course_id": course_id,
                "batch_name": clean_name,
                "batch_code": self._sanitize_string(dto.batch_code) or None,
                "timing": clean_timing,
                "max_capacity": cap_val,
                "status": status_val,
                "start_date": clean_start,
                "end_date": clean_end,
            }

            batch_id = self.repository.create(insert_data)
            if not batch_id or batch_id <= 0:
                raise ServiceError("Failed to create batch record.")

            LogService.info(
                f"Batch created successfully. ID: {batch_id}, Name: '{clean_name}', Course ID: {course_id}",
                context=self.__class__.__name__,
            )
            return batch_id

    def get_batch(self, batch_id: int) -> BatchDTO:
        """Fetches full batch details by primary key."""
        if not batch_id or batch_id <= 0:
            raise ValidationError("A valid Batch ID is required.")

        with self.unit_of_work():
            row = self.repository.get_by_id(batch_id)
            if not row:
                raise ValidationError(f"Batch with ID {batch_id} not found.")
            return BatchMapper.to_dto(row)

    def update_batch(self, dto: BatchUpdateDTO) -> None:
        """Updates an existing batch record with validation and scoped unique name verification."""
        if not dto.id or dto.id <= 0:
            raise ValidationError("A valid Batch ID is required for update.")

        course_id, clean_name, clean_timing, cap_val, status_val, clean_start, clean_end = (
            self._validate_batch_input(
                dto.course_id,
                dto.batch_name,
                dto.timing,
                dto.max_capacity,
                dto.status,
                dto.start_date,
                dto.end_date,
            )
        )

        with self.unit_of_work():
            existing = self.repository.get_by_id(dto.id)
            if not existing:
                raise ValidationError(f"Batch with ID {dto.id} not found.")

            if not self.repository.course_exists(course_id):
                raise ValidationError(f"Referenced course with ID {course_id} does not exist.")

            if self.repository.is_name_taken(course_id, clean_name, exclude_id=dto.id):
                raise ConflictError(
                    f"A batch named '{clean_name}' already exists for this course."
                )

            update_data = {
                "course_id": course_id,
                "batch_name": clean_name,
                "batch_code": self._sanitize_string(dto.batch_code) or None,
                "timing": clean_timing,
                "max_capacity": cap_val,
                "status": status_val,
                "start_date": clean_start,
                "end_date": clean_end,
            }

            self.repository.update(dto.id, update_data)
            LogService.info(
                f"Batch #{dto.id} ('{clean_name}') updated successfully.",
                context=self.__class__.__name__,
            )

    def delete_batch(self, batch_id: int) -> None:
        """
        Deletes a batch if not referenced by admissions or historical records.
        """
        if not batch_id or batch_id <= 0:
            raise ValidationError("A valid Batch ID is required for deletion.")

        with self.unit_of_work():
            existing = self.repository.get_by_id(batch_id)
            if not existing:
                raise ValidationError(f"Batch with ID {batch_id} not found.")

            if self.repository.has_linked_admissions(batch_id):
                raise ConflictError(
                    "Cannot delete batch linked to student admissions. "
                    "ERP audit policy preserves historical batch assignments."
                )

            self.repository.delete(batch_id)
            LogService.info(
                f"Batch #{batch_id} ('{existing['batch_name']}') deleted successfully.",
                context=self.__class__.__name__,
            )

    def list_batches(
        self,
        limit: int = 50,
        offset: int = 0,
        course_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> tuple[list[BatchDTO], int]:
        """Returns paginated batches and total count matching optional filters."""
        limit_val = max(1, min(limit, 200))
        offset_val = max(0, offset)

        with self.unit_of_work():
            rows = self.repository.list(
                limit=limit_val,
                offset=offset_val,
                course_id=course_id,
                status=status,
            )
            total_count = self.repository.count(course_id=course_id, status=status)
            return [BatchMapper.to_dto(r) for r in rows], total_count

    def list_batches_by_course(
        self,
        course_id: int,
        status: Optional[str] = None,
    ) -> list[BatchDTO]:
        """Returns all batches under a specific course."""
        if not course_id or course_id <= 0:
            raise ValidationError("A valid Course ID is required.")

        with self.unit_of_work():
            rows = self.repository.list_by_course(course_id=course_id, status=status)
            return [BatchMapper.to_dto(r) for r in rows]

    def get_capacity_summary(self, batch_id: int) -> BatchCapacityDTO:
        """
        Returns capacity summary for a batch.
        Note: Exact enrolled count calculation depends on Admission/Batch linkage when implemented.
        """
        batch = self.get_batch(batch_id)
        return BatchCapacityDTO(
            batch_id=batch.id,
            batch_name=batch.batch_name,
            max_capacity=batch.max_capacity,
            enrolled_count=0,
            available_capacity=batch.max_capacity,
            status=batch.status,
        )
