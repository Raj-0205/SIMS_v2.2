# modules/student/controller.py

from modules.student.service import StudentSearchService
from modules.student.dto import StudentSearchResultDTO

__all__ = ["StudentController"]


class StudentController:
    """
    Application Layer for Student operations.
    Acts as a thin pass-through between UI and Business Services.
    """

    def __init__(self) -> None:
        self.search_service = StudentSearchService()

    def search_students(self, query: str) -> list[StudentSearchResultDTO]:
        """
        Receives raw UI search query, strips whitespace, and delegates.
        Returns strict DTOs. No business logic here.
        """
        clean_query = str(query).strip() if query else ""
        return self.search_service.search_students(clean_query)
