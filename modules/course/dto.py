# modules/course/dto.py

from dataclasses import dataclass
from modules.course.constants import CourseStatus

__all__ = ["CourseSearchResultDTO"]


@dataclass
class CourseSearchResultDTO:
    """Strict contract for Course search results."""
    id: int
    code: str
    name: str
    status: CourseStatus

    @property
    def display_name(self) -> str:
        """Helper for UI."""
        return f"{self.code} - {self.name}"
