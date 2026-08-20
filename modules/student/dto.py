# modules/student/dto.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

__all__ = [
    "StudentDTO",
    "StudentCreateDTO",
    "StudentUpdateDTO",
    "StudentSearchResultDTO",
]


@dataclass(frozen=True)
class StudentDTO:
    """Full read contract for a student entity."""
    id: int
    first_name: str
    last_name: str
    mobile_number: str
    email: Optional[str] = None
    created_at: str = ""

    @property
    def display_name(self) -> str:
        """Helper for UI to display the full name cleanly."""
        return f"{self.first_name} {self.last_name}".strip()


@dataclass(frozen=True)
class StudentCreateDTO:
    """Contract for creating a new student record."""
    first_name: str
    last_name: str
    mobile_number: str
    email: Optional[str] = None


@dataclass(frozen=True)
class StudentUpdateDTO:
    """Contract for updating an existing student record."""
    id: int
    first_name: str
    last_name: str
    mobile_number: str
    email: Optional[str] = None


@dataclass(frozen=True)
class StudentSearchResultDTO:
    """Strict contract for returning search results to the Application/UI layer."""
    id: int
    first_name: str
    last_name: str
    mobile_number: str

    @property
    def display_name(self) -> str:
        """Helper for UI to display the full name easily."""
        return f"{self.first_name} {self.last_name}".strip()
