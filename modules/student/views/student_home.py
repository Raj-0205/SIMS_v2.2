# modules/student/views/student_home.py

import flet as ft

__all__ = ["StudentHome"]


class StudentHome(ft.Column):
    """Module Landing Page for Students."""
    def __init__(self) -> None:
        super().__init__(spacing=20, horizontal_alignment=ft.CrossAxisAlignment.START)
        
        self.controls = [
            ft.Text("Student Management", size=24, weight=ft.FontWeight.BOLD),
            ft.Divider(),
            ft.Row([
                ft.ElevatedButton("Register New Student", icon=ft.icons.PERSON_ADD, disabled=True),
                ft.ElevatedButton("Search Database", icon=ft.icons.SEARCH, disabled=True),
            ]),
            ft.Text("Full CRUD functionality coming in next sprint.", color=ft.colors.GREY_500, italic=True)
        ]
