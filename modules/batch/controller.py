# modules/batch/controller.py

from __future__ import annotations
from typing import Any, Mapping, Optional

from modules.batch.constants import BatchStatus
from modules.batch.service import BatchService
from modules.batch.dto import (
    BatchDTO,
    BatchCreateDTO,
    BatchUpdateDTO,
    BatchSummaryDTO,
    BatchCapacityDTO,
)

__all__ = ["BatchController"]


class BatchController:
    """
    Application Layer for Batch operations.
    Thin pass-through translating UI/raw dictionaries into strict DTOs and delegating to BatchService.
    """

    def __init__(self) -> None:
        self.service = BatchService()

    def create_batch(self, raw_data: Mapping[str, Any]) -> int:
        """Translates raw form dictionary into BatchCreateDTO and delegates to service."""
        raw_status = str(raw_data.get("status") or "OPEN").upper()
        try:
            status_enum = BatchStatus(raw_status)
        except ValueError:
            status_enum = BatchStatus.OPEN

        raw_cap = raw_data.get("max_capacity")
        max_capacity_val = int(raw_cap) if raw_cap is not None and str(raw_cap).strip() != "" else 0

        dto = BatchCreateDTO(
            course_id=int(raw_data.get("course_id") or 0),
            batch_name=str(raw_data.get("batch_name") or "").strip(),
            timing=str(raw_data.get("timing") or "").strip(),
            max_capacity=max_capacity_val,
            status=status_enum,
            batch_code=str(raw_data.get("batch_code") or "").strip() or None,
            start_date=str(raw_data.get("start_date") or "").strip() or None,
            end_date=str(raw_data.get("end_date") or "").strip() or None,
        )
        return self.service.create_batch(dto)

    def update_batch(self, batch_id: int, raw_data: Mapping[str, Any]) -> None:
        """Translates raw form dictionary into BatchUpdateDTO and delegates to service."""
        raw_status = str(raw_data.get("status") or "OPEN").upper()
        try:
            status_enum = BatchStatus(raw_status)
        except ValueError:
            status_enum = BatchStatus.OPEN

        raw_cap = raw_data.get("max_capacity")
        max_capacity_val = int(raw_cap) if raw_cap is not None and str(raw_cap).strip() != "" else 0

        dto = BatchUpdateDTO(
            id=batch_id,
            course_id=int(raw_data.get("course_id") or 0),
            batch_name=str(raw_data.get("batch_name") or "").strip(),
            timing=str(raw_data.get("timing") or "").strip(),
            max_capacity=max_capacity_val,
            status=status_enum,
            batch_code=str(raw_data.get("batch_code") or "").strip() or None,
            start_date=str(raw_data.get("start_date") or "").strip() or None,
            end_date=str(raw_data.get("end_date") or "").strip() or None,
        )
        self.service.update_batch(dto)

    def delete_batch(self, batch_id: int) -> None:
        """Deletes batch record via service."""
        self.service.delete_batch(batch_id)

    def get_batch(self, batch_id: int) -> BatchDTO:
        """Fetches full batch details by ID."""
        return self.service.get_batch(batch_id)

    def list_batches(
        self,
        limit: int = 50,
        offset: int = 0,
        course_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> tuple[list[BatchDTO], int]:
        """Returns paginated list of batches and total count."""
        return self.service.list_batches(
            limit=limit, offset=offset, course_id=course_id, status=status
        )

    def list_batches_by_course(
        self,
        course_id: int,
        status: Optional[str] = None,
    ) -> list[BatchDTO]:
        """Returns list of batches belonging to a specific course."""
        return self.service.list_batches_by_course(course_id=course_id, status=status)

    def get_capacity_summary(self, batch_id: int) -> BatchCapacityDTO:
        """Returns capacity details for a batch."""
        return self.service.get_capacity_summary(batch_id)
