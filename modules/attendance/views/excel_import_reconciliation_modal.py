# modules/attendance/views/excel_import_reconciliation_modal.py

from pathlib import Path
from typing import Callable, Optional
import flet as ft

from core.logger.service import LogService
from modules.attendance.controller import AttendanceController
from modules.attendance.dto import ExcelAttendanceImportPreviewDTO
from shared.utils.file_dialog import pick_file_async
from ui.themes.theme import AppTheme


class ExcelImportReconciliationModal(ft.AlertDialog):
    """
    Modal dialog allowing the user to upload a completed offline Excel register (.xlsx),
    review detected dates and student attendance marks, inspect changes against existing
    records (diff), verify Administrator PIN if overwriting historical records, and commit.
    """

    def __init__(
        self,
        batch_id: int,
        batch_name: str,
        on_saved: Optional[Callable[[], None]] = None,
        on_success: Optional[Callable[[], None]] = None,
        controller: Optional[AttendanceController] = None,
    ):
        self.batch_id = batch_id
        self.batch_name = batch_name
        self.on_saved = on_saved or on_success
        self.controller = controller or AttendanceController()

        self.selected_file_path: Optional[str] = None
        self.preview_data: Optional[ExcelAttendanceImportPreviewDTO] = None

        # 1. Intake Controls
        self.file_path_text = ft.Text(
            "No file chosen. Supported: Microsoft Excel (.xlsx)",
            size=AppTheme.SIZE_CAPTION,
            color=AppTheme.TEXT_MUTED,
            italic=True,
        )

        self.browse_btn = ft.FilledButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.UPLOAD_FILE, size=16),
                    ft.Text("Browse .xlsx Register", weight=ft.FontWeight.BOLD),
                ],
                spacing=6,
            ),
            style=ft.ButtonStyle(
                bgcolor=AppTheme.PRIMARY,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
            ),
            on_click=self.handle_browse_file,
        )

        self.analyze_btn = ft.FilledButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ANALYTICS, size=16),
                    ft.Text("Analyze & Preview Diff", weight=ft.FontWeight.BOLD),
                ],
                spacing=6,
            ),
            style=ft.ButtonStyle(
                bgcolor="#059669",
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
            ),
            disabled=True,
            on_click=self.handle_run_preview,
        )

        self.progress_ring = ft.ProgressRing(width=24, height=24, stroke_width=2.5, visible=False)
        self.status_msg = ft.Text("", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.W_500, visible=False)

        # 2. Metrics & Diff Container
        self.metrics_row = ft.Row(controls=[], spacing=8, wrap=True, visible=False)
        self.diff_list = ft.ListView(controls=[], spacing=4, expand=True, height=180)
        self.reconciliation_container = ft.Column(
            controls=[
                self.metrics_row,
                ft.Divider(height=1, color=AppTheme.BORDER),
                ft.Text("Detailed Changes / Overwrites Preview:", size=11, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_SECONDARY),
                self.diff_list,
            ],
            spacing=8,
            visible=False,
        )

        # 3. Admin PIN Input (revealed only if overwriting existing historical records)
        self.admin_pin_input = ft.TextField(
            label="Administrator Authorization PIN *",
            hint_text="Enter Admin PIN to authorize overwriting existing records",
            password=True,
            can_reveal_password=True,
            prefix_icon=ft.Icons.LOCK,
            width=360,
            border_radius=AppTheme.RADIUS_MD,
            visible=False,
        )

        # 4. Action Buttons
        self.commit_btn = ft.FilledButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.CHECK_CIRCLE, size=16),
                    ft.Text("Confirm & Save to Spreadsheet", weight=ft.FontWeight.BOLD),
                ],
                spacing=6,
            ),
            style=ft.ButtonStyle(
                bgcolor=AppTheme.PRIMARY,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                padding=ft.Padding(14, 10, 14, 10),
            ),
            visible=False,
            on_click=self.handle_commit_import,
        )

        self.cancel_btn = ft.TextButton("Cancel", on_click=lambda _: self._close())

        content = ft.Container(
            content=ft.SelectionArea(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            f"Upload updated Excel register for: {self.batch_name}",
                            size=AppTheme.SIZE_BODY,
                            color=AppTheme.TEXT_SECONDARY,
                        ),
                        ft.Row(
                            controls=[
                                self.browse_btn,
                                self.analyze_btn,
                            ],
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        self.file_path_text,
                        ft.Row(
                            controls=[self.progress_ring, self.status_msg],
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Divider(height=1, color=AppTheme.BORDER),
                        self.reconciliation_container,
                        self.admin_pin_input,
                    ],
                    spacing=10,
                    tight=True,
                )
            ),
            width=620,
            padding=ft.Padding(4, 4, 4, 4),
        )

        super().__init__(
            title=ft.SelectionArea(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.UPLOAD_FILE, color=AppTheme.PRIMARY),
                        ft.Text("Upload Offline Attendance Register (.xlsx)", weight=ft.FontWeight.BOLD),
                    ],
                    spacing=8,
                )
            ),
            content=content,
            actions=[self.cancel_btn, self.commit_btn],
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

    def handle_browse_file(self, e: ft.ControlEvent) -> None:
        p = getattr(self, "_root_page", None) or self.page or getattr(self, "_page", None)

        def on_file_picked(path: Optional[str]):
            if path and Path(path).is_file():
                self.selected_file_path = path
                file_name = Path(path).name
                size_kb = round(Path(path).stat().st_size / 1024, 1)
                self.file_path_text.value = f"Selected: {file_name} ({size_kb} KB)"
                self.file_path_text.color = AppTheme.TEXT_PRIMARY
                self.analyze_btn.disabled = False
            else:
                self.file_path_text.value = "No file chosen."
                self.file_path_text.color = AppTheme.TEXT_MUTED
                self.analyze_btn.disabled = True

            if p:
                try:
                    p.update()
                except RuntimeError:
                    pass

        pick_file_async(
            on_result=on_file_picked,
            title="Select Completed Attendance Register (.xlsx)",
            allowed_extensions=["xlsx"],
        )

    def handle_run_preview(self, e: ft.ControlEvent) -> None:
        if not self.selected_file_path or not Path(self.selected_file_path).is_file():
            return

        p = getattr(self, "_root_page", None) or self.page or getattr(self, "_page", None)
        self.progress_ring.visible = True
        self.status_msg.value = "Analyzing spreadsheet and computing attendance diff..."
        self.status_msg.color = AppTheme.PRIMARY
        self.status_msg.visible = True
        self.analyze_btn.disabled = True
        if p:
            p.update()

        try:
            self.preview_data = self.controller.parse_offline_register(
                file_path=self.selected_file_path,
                expected_batch_id=self.batch_id,
            )

            self._build_preview_ui(self.preview_data)
            self.progress_ring.visible = False
            self.status_msg.value = (
                f"✓ Analysis Complete: {len(self.preview_data.detected_dates)} Sessions detected, "
                f"{self.preview_data.new_marks_count} New marks, {self.preview_data.overwrite_marks_count} Overwrites"
            )
            self.status_msg.color = "#059669"

            if self.preview_data.requires_admin_pin:
                self.admin_pin_input.visible = True

            self.commit_btn.visible = True
            self.reconciliation_container.visible = True

        except Exception as exc:
            LogService.error(f"Failed to preview offline register: {exc}", context="ExcelImportReconciliationModal")
            self.progress_ring.visible = False
            self.status_msg.value = f"Error: {exc}"
            self.status_msg.color = AppTheme.DANGER
            self.analyze_btn.disabled = False

        if p:
            try:
                p.update()
            except RuntimeError:
                pass

    def _build_preview_ui(self, preview: ExcelAttendanceImportPreviewDTO) -> None:
        def _badge(label: str, count: int, col: str, bg: str) -> ft.Container:
            return ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Text(label, size=11, color=AppTheme.TEXT_SECONDARY),
                        ft.Text(str(count), size=12, weight=ft.FontWeight.BOLD, color=col),
                    ],
                    spacing=4,
                ),
                bgcolor=bg,
                padding=ft.Padding(8, 4, 8, 4),
                border_radius=AppTheme.RADIUS_PILL,
            )

        self.metrics_row.controls = [
            _badge("Dates:", len(preview.detected_dates), AppTheme.PRIMARY, AppTheme.PRIMARY_LIGHT),
            _badge("New Marks:", preview.new_marks_count, "#059669", "#ECFDF5"),
            _badge("Overwrites:", preview.overwrite_marks_count, "#D97706", "#FFFBEB"),
            _badge("Unchanged:", preview.unchanged_marks_count, "#475569", "#F1F5F9"),
            _badge("Blanks Skipped:", preview.skipped_blank_count, "#64748B", "#F8FAFC"),
        ]
        if preview.invalid_cells_count > 0:
            self.metrics_row.controls.append(
                _badge("Invalid Values:", preview.invalid_cells_count, "#DC2626", "#FEF2F2")
            )
        self.metrics_row.visible = True

        # Diff Items
        diff_controls = []
        actionable_items = [it for it in preview.diff_items if it.change_type in ("OVERWRITE", "NEW", "INVALID")]

        if not actionable_items:
            diff_controls.append(
                ft.Text("All entries match existing records. No changes detected.", size=12, color=AppTheme.TEXT_MUTED)
            )
        else:
            for item in actionable_items[:100]:  # Limit UI to 100 preview items
                if item.change_type == "OVERWRITE":
                    badge_col = "#D97706"
                    badge_bg = "#FFFBEB"
                    status_text = f"Overwrite: {item.existing_status} ➔ {item.mark}"
                elif item.change_type == "NEW":
                    badge_col = "#059669"
                    badge_bg = "#ECFDF5"
                    status_text = f"New Entry: {item.mark}"
                else:
                    badge_col = "#DC2626"
                    badge_bg = "#FEF2F2"
                    status_text = f"Invalid: {item.error_reason or item.mark}"

                diff_controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Container(
                                    content=ft.Text(item.change_type, size=10, weight=ft.FontWeight.BOLD, color=badge_col),
                                    bgcolor=badge_bg,
                                    padding=ft.Padding(6, 2, 6, 2),
                                    border_radius=4,
                                ),
                                ft.Text(f"{item.student_name} ({item.candidate_number or '—'})", size=11, weight=ft.FontWeight.BOLD),
                                ft.Text(f"Date: {item.session_date}", size=11, color=AppTheme.TEXT_MUTED),
                                ft.Text(status_text, size=11, weight=ft.FontWeight.W_500, color=badge_col),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        bgcolor=AppTheme.SURFACE_VARIANT,
                        padding=ft.Padding(8, 4, 8, 4),
                        border_radius=AppTheme.RADIUS_SM,
                    )
                )

        self.diff_list.controls = diff_controls

    def handle_commit_import(self, e: ft.ControlEvent) -> None:
        if not self.preview_data:
            return

        p = getattr(self, "_root_page", None) or self.page or getattr(self, "_page", None)
        pin_val = self.admin_pin_input.value.strip() if self.admin_pin_input.value else None

        if self.preview_data.requires_admin_pin and not pin_val:
            self.status_msg.value = "Error: Admin PIN is required to authorize overwriting existing records."
            self.status_msg.color = AppTheme.DANGER
            if p:
                try:
                    p.update()
                except RuntimeError:
                    pass
            return

        try:
            saved_count = self.controller.commit_offline_register_import(
                batch_id=self.batch_id,
                import_preview=self.preview_data,
                admin_pin=pin_val,
                recorded_by="admin",
            )

            if self.on_saved:
                self.on_saved()

            self._close()

            if p:
                snack = ft.SnackBar(
                    content=ft.Text(
                        f"✓ Successfully imported {saved_count} attendance records from Excel register!",
                        color=AppTheme.SURFACE,
                    ),
                    bgcolor=AppTheme.SUCCESS,
                )
                p.overlay.append(snack)
                snack.open = True
                try:
                    p.update()
                except Exception:
                    pass

        except Exception as exc:
            LogService.error(f"Failed to commit offline register: {exc}", context="ExcelImportReconciliationModal")
            self.status_msg.value = f"Commit Failed: {exc}"
            self.status_msg.color = AppTheme.DANGER
            if p:
                try:
                    p.update()
                except RuntimeError:
                    pass
