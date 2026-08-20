# modules/batch/mapper.py

from __future__ import annotations
from typing import Any, Mapping
from modules.batch.constants import BatchStatus
from modules.batch.dto import BatchDTO, BatchSummaryDTO

__all__ = ["BatchMapper"]


class BatchMapper:
    """Translates raw database rows into strict Batch domain DTOs."""

    @staticmethod
    def to_dto(row: Mapping[str, Any]) -> BatchDTO:
        """Maps a database row dictionary to BatchDTO."""
        raw_status = str(row.get("status") or "OPEN").upper()
        try:
            status_enum = BatchStatus(raw_status)
        except ValueError:
            status_enum = BatchStatus.OPEN

        return BatchDTO(
            id=int(row["id"]),
            course_id=int(row["course_id"]),
            batch_name=str(row.get("batch_name") or ""),
            timing=str(row.get("timing") or ""),
            max_capacity=int(row.get("max_capacity") or 0),
            status=status_enum,
            batch_code=str(row["batch_code"]) if row.get("batch_code") else None,
            start_date=str(row["start_date"]) if row.get("start_date") else None,
            end_date=str(row["end_date"]) if row.get("end_date") else None,
            created_at=str(row.get("created_at") or ""),
            updated_at=str(row["updated_at"]) if row.get("updated_at") else None,
            course_code=str(row["course_code"]) if row.get("course_code") else None,
            course_name=str(row["course_name"]) if row.get("course_name") else None,
        )

    @staticmethod
    def to_summary_dto(row: Mapping[str, Any]) -> BatchSummaryDTO:
        """Maps a database row dictionary to BatchSummaryDTO."""
        raw_status = str(row.get("status") or "OPEN").upper()
        try:
            status_enum = BatchStatus(raw_status)
        except ValueError:
            status_enum = BatchStatus.OPEN

        return BatchSummaryDTO(
            id=int(row["id"]),
            course_id=int(row["course_id"]),
            batch_name=str(row.get("batch_name") or ""),
            timing=str(row.get("timing") or ""),
            max_capacity=int(row.get("max_capacity") or 0),
            status=status_enum,
            course_name=str(row["course_name"]) if row.get("course_name") else None,
        )
