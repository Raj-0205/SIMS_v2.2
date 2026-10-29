# modules/attendance/views/offline_register_dialog.py

from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
import flet as ft

from core.logger.service import LogService
from modules.attendance.controller import AttendanceController
from modules.attendance.dto import OfflineRegisterConfigDTO
from shared.utils.os_helper import open_path_externally
from shared.utils.export_helper import export_and_prompt_save
from ui.themes.theme import AppTheme


class OfflineRegisterDialog(ft.AlertDialog):
    """
    Modal dialog allowing the user to configure and generate a downloadable
    multi-day digital Excel attendance register (.xlsx) covering 8 days, 15 days,
    1 month, or 2 months, complete with formulas and validation rules.
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

        # 1. Period Options
        self.duration_dropdown = ft.Dropdown(
            label="Attendance Period Coverage *",
            value="15_DAYS",
            width=220,
            border_radius=AppTheme.RADIUS_MD,
            options=[
                ft.dropdown.Option("8_DAYS", "8 Days"),
                ft.dropdown.Option("15_DAYS", "15 Days (Fortnight)"),
                ft.dropdown.Option("1_MONTH", "1 Month (30 Days)"),
                ft.dropdown.Option("2_MONTHS", "2 Months (60 Days)"),
            ],
        )

        # 2. Start Date Selector
        self.start_date_field = ft.TextField(
            label="Start Date *",
            value=datetime.now().strftime("%Y-%m-%d"),
            width=180,
            border_radius=AppTheme.RADIUS_MD,
            hint_text="YYYY-MM-DD",
        )

        # 3. Column Options
        self.chk_name = ft.Checkbox(label="Student Full Name", value=True, disabled=True)
        self.chk_mobile = ft.Checkbox(label="Contact Mobile Number", value=True)
        self.chk_adm_date = ft.Checkbox(label="Admission Date", value=False)
        self.chk_pending_fees = ft.Checkbox(label="Pending Fees Status (₹)", value=False)

        # 4. Action Buttons
        self.generate_btn = ft.FilledButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.DOWNLOAD, size=16),
                    ft.Text("Generate & Open Register (.xlsx)", weight=ft.FontWeight.BOLD),
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
            content=ft.SelectionArea(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            f"Generate multi-day attendance register for: {self.batch_name} ({self.course_name})",
                            size=AppTheme.SIZE_BODY,
                            color=AppTheme.TEXT_SECONDARY,
                        ),
                        ft.Divider(height=1, color=AppTheme.BORDER),
                        ft.Text(
                            "Step 1: Choose Period & Starting Date:",
                            size=AppTheme.SIZE_BODY,
                            weight=ft.FontWeight.BOLD,
                            color=AppTheme.TEXT_PRIMARY,
                        ),
                        ft.Row(
                            controls=[
                                self.duration_dropdown,
                                self.start_date_field,
                            ],
                            spacing=12,
                        ),
                        ft.Divider(height=1, color=AppTheme.BORDER),
                        ft.Text(
                            "Step 2: Optional Columns to Include:",
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
                                ],
                                spacing=4,
                            ),
                            bgcolor=AppTheme.SURFACE_VARIANT,
                            padding=ft.Padding(12, 10, 12, 10),
                            border_radius=AppTheme.RADIUS_MD,
                        ),
                        ft.Text(
                            "• File format: Microsoft Excel (.xlsx)\n"
                            "• Includes dynamic formulas (=COUNTIF) for present counts and attendance %\n"
                            "• Enter 'P' for Present and 'A' for Absent. Leave cell blank for holidays.\n"
                            "• You can edit and upload this file back to SIMS anytime.",
                            size=AppTheme.SIZE_CAPTION,
                            color=AppTheme.TEXT_MUTED,
                        ),
                    ],
                    spacing=12,
                    tight=True,
                )
            ),
            width=520,
            padding=ft.Padding(6, 4, 6, 4),
        )

        super().__init__(
            title=ft.SelectionArea(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.TABLE_CHART, color=AppTheme.PRIMARY),
                        ft.Text("Generate Offline Attendance Register", weight=ft.FontWeight.BOLD),
                    ],
                    spacing=8,
                )
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
            duration_key = self.duration_dropdown.value or "15_DAYS"
            days_map = {"8_DAYS": 8, "15_DAYS": 15, "1_MONTH": 30, "2_MONTHS": 60}
            num_days = days_map.get(duration_key, 15)

            config = OfflineRegisterConfigDTO(
                batch_id=self.batch_id,
                duration_type=duration_key,
                num_days=num_days,
                start_date=self.start_date_field.value.strip() or datetime.now().strftime("%Y-%m-%d"),
                include_student_name=True,
                include_contact_number=bool(self.chk_mobile.value),
                include_admission_date=bool(self.chk_adm_date.value),
                include_pending_fees=bool(self.chk_pending_fees.value),
            )

            path_str = self.controller.generate_offline_register(config)

            def _notify(msg: str, is_error: bool = False, is_success: bool = False):
                p = getattr(self, "_root_page", None) or self.page or getattr(self, "_page", None)
                if p:
                    snack = ft.SnackBar(
                        content=ft.Text(msg, color=AppTheme.SURFACE),
                        bgcolor=AppTheme.DANGER if is_error else (AppTheme.SUCCESS if is_success else AppTheme.PRIMARY),
                    )
                    p.overlay.append(snack)
                    snack.open = True
                    try:
                        p.update()
                    except Exception:
                        pass

            export_and_prompt_save(
                source_file_path=path_str,
                dialog_title="Save Attendance Register As",
                allowed_extensions=[".xlsx"],
                show_toast=_notify,
            )

            if self.on_generated:
                self.on_generated(path_str)

            self._close()

        except Exception as exc:
            LogService.error(f"Failed to generate offline register: {exc}", context="OfflineRegisterDialog")
            p = getattr(self, "_root_page", None) or self.page or getattr(self, "_page", None)
            if p:
                snack = ft.SnackBar(
                    content=ft.Text(f"Failed to generate register: {exc}", color=AppTheme.SURFACE),
                    bgcolor=AppTheme.DANGER,
                )
                p.overlay.append(snack)
                snack.open = True
                try:
                    p.update()
                except Exception:
                    pass
