# modules/course/views/course_search_dialog.py

import flet as ft
from typing import Callable, Optional
from modules.course.controller import CourseController
from modules.course.dto import CourseSearchResultDTO

__all__ = ["CourseSearchDialog"]


class CourseSearchDialog(ft.AlertDialog):
    """Reusable component for searching and selecting a course."""

    def __init__(
        self, 
        controller: CourseController, 
        on_course_selected: Callable[[CourseSearchResultDTO], None]
    ) -> None:
        super().__init__()
        self.controller = controller
        self.on_course_selected = on_course_selected
        
        self.title = ft.Text("Search Course")
        self.modal = True
        
        self.search_input = ft.TextField(
            label="Search by Code or Name",
            hint_text="Type and press Enter...",
            autofocus=True,
            on_submit=self.handle_search,
            prefix_icon=ft.Icons.SEARCH
        )
        
        self.results_list = ft.ListView(expand=1, spacing=5, height=350, width=500)
        self.content = ft.Column(controls=[self.search_input, self.results_list], tight=True)
        self.actions = [ft.TextButton(content=ft.Text("Cancel"), on_click=self.close_dialog)]

    def handle_search(self, e: ft.ControlEvent) -> None:
        query = self.search_input.value or ""
        results = self.controller.search_courses(query)
        self.results_list.controls.clear()
        
        if not results and len(query.strip()) >= 2:
            self.results_list.controls.append(
                ft.Container(content=ft.Text("No courses found.", color=ft.Colors.GREY_500), padding=20)
            )
            
        for course in results:
            self.results_list.controls.append(
                ft.ListTile(
                    title=ft.Text(course.display_name, weight=ft.FontWeight.W_500),
                    subtitle=ft.Text(f"Status: {course.status.value}"),
                    leading=ft.Icon(ft.Icons.BOOK),
                    on_click=lambda e, c=course: self.select_and_close(c)
                )
            )
        self.update()

    def select_and_close(self, course: CourseSearchResultDTO) -> None:
        self.search_input.value = ""
        self.results_list.controls.clear()
        self.on_course_selected(course)
        self.close_dialog()

    def close_dialog(self, e: Optional[ft.ControlEvent] = None) -> None:
        self.open = False
        try:
            if self.page:
                self.page.pop_dialog()
        except RuntimeError:
            pass
