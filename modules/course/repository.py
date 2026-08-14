# modules/course/repository.py

from __future__ import annotations
from typing import TypedDict, cast

from core.database.repository import BaseRepository

__all__ = ["CourseRepository", "CourseSearchRow"]

class CourseSearchRow(TypedDict):
    """Strict typing for search results returned from the database."""
    id: int
    code: str
    name: str
    status: str

class CourseRepository(BaseRepository):
    """
    Handles database interactions for the Course entity.
    STRICT RULE: Pure SQL execution. No business logic.
    """

    def search(self, query: str, limit: int = 25) -> list[CourseSearchRow]:
        """
        Searches courses by Code or Name.
        Case-insensitive partial match.
        """
        search_pattern = f"%{query}%"
        
        sql = """
            SELECT 
                id, 
                code, 
                name, 
                status
            FROM courses
            WHERE 
                code LIKE ? OR
                name LIKE ?
            ORDER BY name ASC
            LIMIT ?;
        """
        
        params = (search_pattern, search_pattern, limit)
        
        return cast(list[CourseSearchRow], self.execute_fetchall(sql, params))
