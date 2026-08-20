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

