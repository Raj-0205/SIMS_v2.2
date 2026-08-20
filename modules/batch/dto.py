# modules/batch/dto.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from modules.batch.constants import BatchStatus

__all__ = [
    "BatchDTO",
    "BatchCreateDTO",
    "BatchUpdateDTO",
    "BatchSummaryDTO",
    "BatchCapacityDTO",
]


@dataclass(frozen=True)
class BatchDTO:
    """Full domain representation of a Batch entity."""
    id: int
    course_id: int
    batch_name: str
    timing: str
    max_capacity: int = 0
    status: BatchStatus = BatchStatus.OPEN
    batch_code: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    created_at: str = ""
    updated_at: Optional[str] = None
    course_code: Optional[str] = None
    course_name: Optional[str] = None

    @property
    def display_name(self) -> str:
        """Formatted string for UI dropdowns and representations."""
        return f"{self.batch_name} ({self.timing})"

    @property
    def is_selectable_for_admission(self) -> bool:
        """Determines if batch is OPEN and available for enrolling students."""
        return self.status == BatchStatus.OPEN


@dataclass(frozen=True)
class BatchCreateDTO:
    """Contract for creating a new Batch."""
    course_id: int
    batch_name: str
    timing: str
    max_capacity: int
    status: BatchStatus = BatchStatus.OPEN
    batch_code: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@dataclass(frozen=True)
class BatchUpdateDTO:
    """Contract for updating an existing Batch."""
    id: int
    course_id: int
    batch_name: str
    timing: str
    max_capacity: int
    status: BatchStatus = BatchStatus.OPEN
    batch_code: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@dataclass(frozen=True)
class BatchSummaryDTO:
    """Lightweight summary DTO for batch listings and selection."""
    id: int
    course_id: int
    batch_name: str
    timing: str
    max_capacity: int
    status: BatchStatus
    course_name: Optional[str] = None


@dataclass(frozen=True)
class BatchCapacityDTO:
    """
    Capacity representation for a Batch.
    Note: Actual enrollment calculation depends on Admission/Batch linkage when implemented.
    """
    batch_id: int
    batch_name: str
    max_capacity: int
    enrolled_count: int = 0
    available_capacity: int = 0
    status: BatchStatus = BatchStatus.OPEN
