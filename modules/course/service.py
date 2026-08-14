# modules/course/service.py

from __future__ import annotations

from core.service.base import BaseService
from modules.course.repository import CourseRepository
from modules.course.mapper import CourseSearchMapper
from modules.course.dto import CourseSearchResultDTO

__all__ = ["CourseSearchService"]


class CourseSearchService(BaseService):
    """Business logic for Course searches."""

    def __init__(self) -> None:
        self.repository = CourseRepository()

    def search_courses(self, query: str, limit: int = 25) -> list[CourseSearchResultDTO]:
        """Case-insensitive search enforcing minimum character limits."""
        clean_query = query.strip()
        if not clean_query or len(clean_query) < 2:
            return []

        rows = self.repository.search(clean_query, limit)
        return [CourseSearchMapper.to_result_dto(row) for row in rows]
