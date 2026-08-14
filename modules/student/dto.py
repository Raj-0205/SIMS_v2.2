# modules/student/dto.py

from dataclasses import dataclass

__all__ = ["StudentSearchResultDTO"]


@dataclass
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
