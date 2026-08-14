# modules/student/service.py

from __future__ import annotations

from core.service.base import BaseService
from modules.student.repository import StudentRepository
from modules.student.mapper import StudentSearchMapper
from modules.student.dto import StudentSearchResultDTO

__all__ = ["StudentSearchService"]


class StudentSearchService(BaseService):
    """
    Business Logic Layer for Student operations.
    """

    def __init__(self) -> None:
        self.repository = StudentRepository()

    def search_students(self, query: str, limit: int = 25) -> list[StudentSearchResultDTO]:
        """
        Searches students based on a query string.
        Enforces a minimum character length to prevent heavy DB loads.
        """
        # Business Rule: Minimum 2 characters required for a search
        clean_query = query.strip()
        if not clean_query or len(clean_query) < 2:
            return []

        # Delegate to Repository
        rows = self.repository.search(clean_query, limit)
        
        # Map to DTOs
        return [StudentSearchMapper.to_result_dto(row) for row in rows]
