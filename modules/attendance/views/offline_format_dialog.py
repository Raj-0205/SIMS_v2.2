# modules/attendance/views/offline_format_dialog.py

from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
import flet as ft

from core.logger.service import LogService
from modules.attendance.controller import AttendanceController
from modules.attendance.dto import OfflineFormatConfigDTO
from shared.utils.os_helper import open_path_externally
from ui.themes.theme import AppTheme


class OfflineFormatDialog(ft.AlertDialog):
    """
    Modal dialog allowing the Administrator to customize which student columns
    are included in the fixed, printable Excel attendance sheet format.
    """

    def __init__(
        self,
        batch_id: int,
        batch_name: str,
        course_name: str,
        on_generated: Optional[Callable[[str], None]] = None,
        controller: Optional[AttendanceController] = None,
    ):
        self.batch_id = batch_id
        self.batch_name = batch_name
        self.course_name = course_name
        self.on_generated = on_generated
        self.controller = controller or AttendanceController()

        # Customization Checkboxes
        self.chk_name = ft.Checkbox(label="Student Full Name", value=True, disabled=True)
        self.chk_mobile = ft.Checkbox(label="Mobile / Contact Number", value=True)
        self.chk_adm_date = ft.Checkbox(label="Admission Date", value=True)
        self.chk_pending_fees = ft.Checkbox(label="Pending Fees Status (₹)", value=True)
        self.chk_course = ft.Checkbox(label="Course Details", value=True)

        self.columns_count_dropdown = ft.Dropdown(
            label="Blank Days / Mark Columns",
            value="15",
            width=180,
            border_radius=AppTheme.RADIUS_MD,
            options=[
                ft.dropdown.Option("1", "Single Day (Today)"),
                ft.dropdown.Option("7", "1 Week (7 Days)"),
                ft.dropdown.Option("15", "Fortnight (15 Days)"),
                ft.dropdown.Option("30", "Full Month (30 Days)"),
            ],
        )

        self.date_field = ft.TextField(
            label="Specific Date (Optional)",
            value=datetime.now().strftime("%Y-%m-%d"),
            width=180,
            border_radius=AppTheme.RADIUS_MD,
        )

        self.generate_btn = ft.FilledButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.PRINT, size=16),
                    ft.Text("Generate & Open Format", weight=ft.FontWeight.BOLD),
                ],
                spacing=6,
            ),
            style=ft.ButtonStyle(
                bgcolor=AppTheme.PRIMARY,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                padding=ft.Padding(14, 10, 14, 10),
            ),
            on_click=self.handle_generate,
        )

        self.cancel_btn = ft.TextButton(
            "Cancel",
            on_click=lambda _: self._close(),
        )

        content = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        f"Customize physical attendance sheet for: {self.batch_name} ({self.course_name})",
                        size=AppTheme.SIZE_BODY,
                        color=AppTheme.TEXT_SECONDARY,
                    ),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    ft.Text(
                        "Administrator Column Customizer (Enable / Disable Columns):",
                        size=AppTheme.SIZE_BODY,
                        weight=ft.FontWeight.BOLD,
                        color=AppTheme.TEXT_PRIMARY,
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                self.chk_name,
                                self.chk_mobile,
                                self.chk_adm_date,
                                self.chk_pending_fees,
                                self.chk_course,
                            ],
                            spacing=4,
                        ),
                        bgcolor=AppTheme.SURFACE_VARIANT,
                        padding=ft.Padding(12, 10, 12, 10),
                        border_radius=AppTheme.RADIUS_MD,
                    ),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    ft.Row(
                        controls=[
                            self.columns_count_dropdown,
                            self.date_field,
                        ],
                        spacing=12,
                    ),
                    ft.Text(
                        "Note: Generated Excel sheet contains designated OCR check boxes [ ✓ ] aligned for automated scanner ingestion.",
                        size=AppTheme.SIZE_CAPTION,
                        color=AppTheme.TEXT_MUTED,
                        italic=True,
                    ),
                ],
                spacing=12,
                tight=True,
            ),
            width=500,
            padding=ft.Padding(6, 4, 6, 4),
        )

        super().__init__(
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.TABLE_VIEW, color=AppTheme.PRIMARY),
                    ft.Text("Print Offline Attendance Format", weight=ft.FontWeight.BOLD),
                ],
                spacing=8,
            ),
            content=content,
            actions=[self.cancel_btn, self.generate_btn],
            actions_alignment=ft.MainAxisAlignment.END,
            modal=True,
        )

    def _close(self) -> None:
        p = getattr(self, "_root_page", None) or self.page or getattr(self, "_page", None)
        if p and hasattr(p, "pop_dialog"):
            try:
                p.pop_dialog()
                return
            except Exception:
                pass
        self.open = False
        if p:
            try:
                p.update()
            except RuntimeError:
                pass

    def handle_generate(self, e: ft.ControlEvent) -> None:
        try:
            days_count = int(self.columns_count_dropdown.value or 15)
            config = OfflineFormatConfigDTO(
                batch_id=self.batch_id,
                include_student_name=True,
                include_contact_number=bool(self.chk_mobile.value),
                include_admission_date=bool(self.chk_adm_date.value),
                include_pending_fees=bool(self.chk_pending_fees.value),
                include_course_details=bool(self.chk_course.value),
                blank_session_columns=days_count,
                session_date=self.date_field.value.strip() or None,
            )

            path_str = self.controller.generate_offline_format(config)
            open_path_externally(Path(path_str))

            if self.on_generated:
                self.on_generated(path_str)

            self._close()

        except Exception as exc:
            LogService.error(f"Failed to generate offline format: {exc}", context="OfflineFormatDialog")
            p = getattr(self, "_root_page", None) or self.page or getattr(self, "_page", None)
            if p:
                snack = ft.SnackBar(
                    content=ft.Text(f"Failed to generate format: {exc}", color=AppTheme.SURFACE),
                    bgcolor=AppTheme.DANGER,
                )
                p.overlay.append(snack)
                snack.open = True
                p.update()
