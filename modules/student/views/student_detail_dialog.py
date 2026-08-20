# modules/student/views/student_detail_dialog.py

from __future__ import annotations
from typing import Optional
import flet as ft

from modules.student.dto import StudentDTO
from ui.themes.theme import AppTheme

__all__ = ["StudentDetailDialog"]


class StudentDetailDialog(ft.AlertDialog):
    """
    Read-only Modal Dialog displaying full student profile details.
    """

    def __init__(self, student: StudentDTO) -> None:
        super().__init__()

        self.student = student
        self.modal = True

        self.title = ft.Row(
            controls=[
                ft.Icon(ft.Icons.BADGE, color=AppTheme.PRIMARY, size=24),
                ft.Text(
                    "Student Profile Details",
                    size=AppTheme.SIZE_H2,
                    weight=ft.FontWeight.BOLD,
                    color=AppTheme.TEXT_PRIMARY,
                ),
            ],
            spacing=AppTheme.PAD_SM,
        )

        def make_field(label: str, value: str, icon: str) -> ft.Container:
            return ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(icon, color=AppTheme.TEXT_SECONDARY, size=20),
                        ft.Column(
                            controls=[
                                ft.Text(label, size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                                ft.Text(value or "N/A", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.W_500, color=AppTheme.TEXT_PRIMARY),
                            ],
                            spacing=2,
                        ),
                    ],
                    spacing=AppTheme.PAD_MD,
                ),
                padding=ft.Padding(left=0, top=6, right=0, bottom=6),
            )

        self.content = ft.Container(
            width=420,
            content=ft.Column(
                controls=[
                    make_field("Student Name", student.display_name, ft.Icons.PERSON),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    make_field("Student ID", str(student.id), ft.Icons.NUMBERS),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    make_field("Mobile Number", student.mobile_number, ft.Icons.PHONE),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    make_field("Email Address", student.email or "Not Provided", ft.Icons.EMAIL),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    make_field("Registration Date", student.created_at or "N/A", ft.Icons.CALENDAR_TODAY),
                ],
                spacing=0,
                tight=True,
            ),
        )

        self.actions = [
            ft.ElevatedButton(
                content=ft.Text("Close"),
                style=ft.ButtonStyle(
                    bgcolor=AppTheme.PRIMARY,
                    color=AppTheme.SURFACE,
                    shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                ),
                on_click=self.close_dialog,
            )
        ]
        self.actions_alignment = ft.MainAxisAlignment.END

    def close_dialog(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Closes the dialog safely using Flet's pop_dialog."""
        try:
            if self.page:
                self.page.pop_dialog()
        except RuntimeError:
            pass
