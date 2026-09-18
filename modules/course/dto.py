# modules/course/dto.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from modules.course.constants import CourseStatus

__all__ = [
    "CourseDTO",
    "CourseCreateDTO",
    "CourseUpdateDTO",
    "CourseSearchResultDTO",
    "CourseFeeChangeDTO",
    "CourseFeeHistoryDTO",
    "CourseOperationalSummaryDTO",
]


@dataclass(frozen=True)
class CourseDTO:
    """Full domain representation of a Course entity."""
    id: int
    code: str
    name: str
    status: CourseStatus
    base_fee: float = 0.0
    duration: Optional[str] = None
    category: str = "General"
    description: Optional[str] = None
    created_at: str = ""
    updated_at: Optional[str] = None

    @property
    def display_name(self) -> str:
        """Formatted string for UI dropdowns and headers."""
        return f"{self.code} - {self.name}"

    @property
    def is_active(self) -> bool:
        """Determines if course is active and selectable for new admissions."""
        return self.status == CourseStatus.ACTIVE


@dataclass(frozen=True)
class CourseCreateDTO:
    """Contract for creating a new Course."""
    code: str
    name: str
    base_fee: float = 0.0
    duration: Optional[str] = None
    category: str = "General"
    description: Optional[str] = None
    status: CourseStatus = CourseStatus.ACTIVE


@dataclass(frozen=True)
class CourseUpdateDTO:
    """Contract for updating an existing Course."""
    id: int
    code: str
    name: str
    base_fee: float = 0.0
    duration: Optional[str] = None
    category: str = "General"
    description: Optional[str] = None
    status: CourseStatus = CourseStatus.ACTIVE


@dataclass(frozen=True)
class CourseSearchResultDTO:
    """Strict contract for Course search results (UI & Admission compatibility)."""
    id: int
    code: str
    name: str
    status: CourseStatus

    @property
    def display_name(self) -> str:
        """Helper for UI."""
        return f"{self.code} - {self.name}"


@dataclass(frozen=True)
class CourseFeeChangeDTO:
    """Command DTO for authorized Institute Course Fee modifications."""
    course_id: int
    new_fee: float
    admin_pin: str
    reason: str
    user_id: Optional[int] = None
    username: Optional[str] = None


@dataclass(frozen=True)
class CourseFeeHistoryDTO:
    """Read DTO for historical course fee revision audit trail."""
    id: int
    course_id: int
    old_fee: float
    new_fee: float
    changed_by_user_id: Optional[int]
    changed_by_username: str
    reason: str
    changed_at: str


@dataclass(frozen=True)
class CourseOperationalSummaryDTO:
    """Operational summary metrics for a Course."""
    course_id: int
    batch_count: int = 0
    active_batch_count: int = 0
    total_admissions_count: int = 0
