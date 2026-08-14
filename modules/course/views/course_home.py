# modules/course/views/course_home.py

import flet as ft

__all__ = ["CourseHome"]


class CourseHome(ft.Column):
    """Module Landing Page for Courses."""
    def __init__(self) -> None:
        super().__init__(spacing=20, horizontal_alignment=ft.CrossAxisAlignment.START)
        
        self.controls = [
            ft.Text("Course Master", size=24, weight=ft.FontWeight.BOLD),
            ft.Divider(),
            ft.Row([
                ft.ElevatedButton("Add New Course", icon=ft.icons.ADD_BOX, disabled=True),
                ft.ElevatedButton("Manage Existing", icon=ft.icons.SETTINGS, disabled=True),
            ]),
            ft.Text("Course management coming in next sprint.", color=ft.colors.GREY_500, italic=True)
        ]
