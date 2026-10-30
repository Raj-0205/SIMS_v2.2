# modules/student/views/student_detail_dialog.py

from __future__ import annotations
from typing import Optional, Callable
import flet as ft

from modules.student.dto import StudentDTO
from ui.themes.theme import AppTheme

__all__ = ["StudentDetailDialog"]


class StudentDetailDialog(ft.AlertDialog):
    """
    Read-only Modal Dialog displaying full student profile details with quick Switch Batch action.
    """

    def __init__(
        self,
        student: StudentDTO,
        on_updated: Optional[Callable[[], None]] = None,
        page: Optional[ft.Page] = None,
    ) -> None:
        super().__init__()

        self.student = student
        self.on_updated = on_updated
        self._root_page = page
        self.modal = True

        self.title = ft.SelectionArea(
            content=ft.Row(
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
            ),
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

        fields = [
            make_field("Student Name", student.display_name, ft.Icons.PERSON),
            ft.Divider(height=1, color=AppTheme.BORDER),
            make_field("Student ID", str(student.id), ft.Icons.NUMBERS),
        ]
        if student.current_course:
            fields.extend([
                ft.Divider(height=1, color=AppTheme.BORDER),
                make_field("Enrolled Course", student.current_course, ft.Icons.SCHOOL),
            ])
        fields.extend([
            ft.Divider(height=1, color=AppTheme.BORDER),
            make_field("Mobile Number", student.mobile_number or "N/A", ft.Icons.PHONE),
            ft.Divider(height=1, color=AppTheme.BORDER),
            make_field("Email Address", student.email or "Not Provided", ft.Icons.EMAIL),
            ft.Divider(height=1, color=AppTheme.BORDER),
            make_field("Registration Date", student.created_at or "N/A", ft.Icons.CALENDAR_TODAY),
        ])

        self.content = ft.Container(
            width=420,
            content=ft.SelectionArea(
                content=ft.Column(
                    controls=fields,
                    spacing=0,
                    tight=True,
                ),
            ),
        )

        self.actions = [
            ft.OutlinedButton(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.SWAP_HORIZ, size=18, color=AppTheme.PRIMARY),
                        ft.Text("Switch Batch", color=AppTheme.PRIMARY, weight=ft.FontWeight.BOLD),
                    ],
                    spacing=6,
                ),
                style=ft.ButtonStyle(
                    side=ft.BorderSide(1, AppTheme.PRIMARY),
                    shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                ),
                on_click=self.handle_switch_batch_action,
            ),
            ft.ElevatedButton(
                content=ft.Text("Close"),
                style=ft.ButtonStyle(
                    bgcolor=AppTheme.PRIMARY,
                    color=AppTheme.SURFACE,
                    shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                ),
                on_click=self.close_dialog,
            ),
        ]
        self.actions_alignment = ft.MainAxisAlignment.END

    @property
    def safe_page(self) -> ft.Page | None:
        p = getattr(self, "_root_page", None) or getattr(self, "_page", None)
        if p:
            return p
        try:
            return self.page
        except RuntimeError:
            return None

    def handle_switch_batch_action(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Opens batch switch / assignment modal for this student."""
        p = self.safe_page
        if not p:
            return

        from modules.admission.views.batch_assignment_dialog import BatchAssignmentDialog
        from modules.student.service import StudentService

        admissions = []
        try:
            ws = StudentService().get_student_workspace(self.student.id)
            admissions = ws.admissions
        except Exception:
            admissions = []

        if not admissions and not self.student.latest_admission_id:
            sb = ft.SnackBar(
                content=ft.Text("This student has no course admissions yet. Please enroll first.", color=AppTheme.SURFACE),
                bgcolor=AppTheme.DANGER,
            )
            p.show_dialog(sb)
            return

        def on_batch_updated():
            if self.on_updated:
                self.on_updated()
            sb = ft.SnackBar(
                content=ft.Text("Batch allocation updated successfully.", color=AppTheme.SURFACE),
                bgcolor=AppTheme.SUCCESS,
            )
            p.show_dialog(sb)

        self.close_dialog()

        if len(admissions) <= 1:
            aid = admissions[0].admission_id if admissions else self.student.latest_admission_id
            dlg = BatchAssignmentDialog(admission_id=aid, on_updated=on_batch_updated, page=p)
            p.show_dialog(dlg)
        else:
            def pick_and_open(aid: int):
                try:
                    p.pop_dialog()
                except Exception:
                    pass
                dlg = BatchAssignmentDialog(admission_id=aid, on_updated=on_batch_updated, page=p)
                p.show_dialog(dlg)

            options = []
            for adm in admissions:
                c_name = adm.course_name or "Course"
                b_name = f"{adm.batch_name} ({adm.batch_timing})" if adm.batch_name else "Unallocated"
                options.append(
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.SCHOOL, color=AppTheme.PRIMARY),
                        title=ft.Text(f"{c_name} • Adm #{adm.admission_id}", weight=ft.FontWeight.BOLD),
                        subtitle=ft.Text(f"Current Batch: {b_name}"),
                        trailing=ft.ElevatedButton(
                            content=ft.Text("Select"),
                            style=ft.ButtonStyle(bgcolor=AppTheme.PRIMARY, color=AppTheme.SURFACE),
                            on_click=lambda _, a=adm.admission_id: pick_and_open(a),
                        ),
                    )
                )

            picker = ft.AlertDialog(
                title=ft.Text("Select Admission to Switch Batch", size=AppTheme.SIZE_H2, weight=ft.FontWeight.BOLD),
                content=ft.Container(
                    width=460,
                    content=ft.Column(controls=options, tight=True, spacing=6),
                ),
                actions=[
                    ft.TextButton(content=ft.Text("Cancel"), on_click=lambda _: p.pop_dialog())
                ],
            )
            p.show_dialog(picker)

    def close_dialog(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Closes the dialog safely using Flet's pop_dialog."""
        p = self.safe_page
        if p:
            try:
                p.pop_dialog()
            except Exception:
                pass
        self.open = False
