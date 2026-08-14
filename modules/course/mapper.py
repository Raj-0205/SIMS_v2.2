# modules/course/mapper.py

from modules.course.dto import CourseSearchResultDTO
from modules.course.constants import CourseStatus
from modules.course.repository import CourseSearchRow

__all__ = ["CourseSearchMapper"]


class CourseSearchMapper:
    """Translates database rows into strict Course DTOs."""

    @staticmethod
    def to_result_dto(row: CourseSearchRow) -> CourseSearchResultDTO:
        return CourseSearchResultDTO(
            id=row["id"],
            code=row["code"],
            name=row["name"],
            status=CourseStatus(row["status"])
        )
