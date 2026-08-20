# modules/student/views/student_search_dialog.py

import flet as ft
from typing import Callable, Optional
from modules.student.controller import StudentController
from modules.student.dto import StudentSearchResultDTO

__all__ = ["StudentSearchDialog"]


class StudentSearchDialog(ft.AlertDialog):
    """Reusable UI Component for searching and selecting a student."""

    def __init__(
        self, 
        controller: StudentController, 
        on_student_selected: Callable[[StudentSearchResultDTO], None]
    ) -> None:
        super().__init__()
        
        # Dependency Injection (Passed from the parent form)
        self.controller = controller
        self.on_student_selected = on_student_selected
        
        self.title = ft.Text("Search Student")
        self.modal = True
        
        # TODO (Commit Production Hardening): Add debounce (300ms) for real-time search
        self.search_input = ft.TextField(
            label="Search by Name, Mobile, or ID",
            hint_text="Type and press Enter...",
            autofocus=True,
            on_submit=self.handle_search,  # Triggers only on Enter
            prefix_icon=ft.icons.SEARCH
        )
        
        self.results_list = ft.ListView(expand=1, spacing=5, height=350, width=500)
        
        self.content = ft.Column(controls=[self.search_input, self.results_list], tight=True)
        self.actions = [ft.TextButton(content=ft.Text("Cancel"), on_click=self.close_dialog)]

    def handle_search(self, e: ft.ControlEvent) -> None:
        """Fetches results from the Controller when user submits."""
        query = self.search_input.value or ""
        results = self.controller.search_students(query)
        
        self.results_list.controls.clear()
        
        if not results and len(query.strip()) >= 2:
            self.results_list.controls.append(
                ft.Container(content=ft.Text("No students found.", color=ft.colors.GREY_500), padding=20)
            )
            
        for student in results:
            self.results_list.controls.append(
                ft.ListTile(
                    title=ft.Text(student.display_name, weight=ft.FontWeight.W_500),
                    subtitle=ft.Text(f"Mobile: {student.mobile_number}  •  ID: {student.id}"),
                    leading=ft.Icon(ft.icons.PERSON),
                    on_click=lambda e, s=student: self.select_and_close(s)
                )
            )
        self.update()

    def select_and_close(self, student: StudentSearchResultDTO) -> None:
        """Triggers the callback and closes the modal."""
        self.on_student_selected(student)
        self.close_dialog()

    def close_dialog(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Closes the modal."""
        # TODO (Commit Production Hardening): Standardize dialog closing via self.page.close(dialog)
        self.open = False
        self.update()
