# modules/student/mapper.py

from modules.student.dto import StudentSearchResultDTO
from modules.student.repository import StudentSearchRow

__all__ = ["StudentSearchMapper"]


class StudentSearchMapper:
    """Translates raw database rows into strict search DTOs."""

    @staticmethod
    def to_result_dto(row: StudentSearchRow) -> StudentSearchResultDTO:
        """Maps a typed database row to a Response DTO. Pure mapping, no logic."""
        return StudentSearchResultDTO(
            id=row["id"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            mobile_number=row["mobile_number"]
        )
