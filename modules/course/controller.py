# modules/course/controller.py

from modules.course.service import CourseSearchService
from modules.course.dto import CourseSearchResultDTO

__all__ = ["CourseController"]


class CourseController:
    """Thin Application Layer for Courses."""

    def __init__(self) -> None:
        self.search_service = CourseSearchService()

    def search_courses(self, query: str) -> list[CourseSearchResultDTO]:
        clean_query = str(query).strip() if query else ""
        return self.search_service.search_courses(clean_query)
