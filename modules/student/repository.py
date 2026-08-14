# modules/student/repository.py

from __future__ import annotations
from typing import TypedDict, cast

from core.database.repository import BaseRepository

__all__ = ["StudentRepository", "StudentSearchRow"]


class StudentSearchRow(TypedDict):
    """Strict typing for search results returned from the database."""
    id: int
    first_name: str
    last_name: str
    mobile_number: str


class StudentRepository(BaseRepository):
    """
    Handles all database interactions for the Student entity.
    STRICT RULE: Pure SQL execution. No business logic.
    """

    def search(self, query: str, limit: int = 25) -> list[StudentSearchRow]:
        """
        Searches students by ID, First Name, Last Name, or Mobile.
        Case-insensitive partial match.
        """
        # TODO (Commit Production Hardening): Implement SQLite FTS5 for high-performance full-text search.
        # TODO (Commit Production Hardening): Add advanced filtering and pagination.
        
        search_pattern = f"%{query}%"
        
        sql = """
            SELECT 
                id, 
                first_name, 
                last_name, 
                mobile_number
            FROM students
            WHERE 
                CAST(id AS TEXT) LIKE ? OR
                first_name LIKE ? OR
                last_name LIKE ? OR
                mobile_number LIKE ?
            ORDER BY first_name ASC, last_name ASC
            LIMIT ?;
        """
        
        params = (
            search_pattern,
            search_pattern,
            search_pattern,
            search_pattern,
            limit
        )
        
        # TODO (Commit #011): BaseRepository.execute_fetchall() should become Generic[T] 
        # to eliminate manual casts.
        return cast(list[StudentSearchRow], self.execute_fetchall(sql, params))
