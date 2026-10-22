# modules/attendance/views/attendance_home.py

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import flet as ft

from core.logger.service import LogService
from modules.attendance.constants import AttendanceMode, HEALTH_BG_COLORS, HEALTH_COLORS
from modules.attendance.controller import AttendanceController
from modules.attendance.dto import (
    AttendanceRecordDTO,
    AttendanceSessionDTO,
    BatchAttendanceMatrixDTO,
    BatchStudentDTO,
)
from modules.attendance.views.offline_format_dialog import OfflineFormatDialog
from modules.attendance.views.offline_upload_modal import OfflineUploadModal
from shared.utils.os_helper import open_path_externally
from ui.themes.theme import AppTheme


class AttendanceHome(ft.Container):
    """
    Main Attendance Workspace view in SIMS v2.2.
    Supports Batch Selection, Live Online Attendance Marking with Toggle Switches,
    Offline Excel Format Printing, OCR Upload & Scan, and the Unified Multi-Session
    Attendance Spreadsheet Matrix with Excel and Watermarked PDF exports.
    """

    def __init__(
        self,
        initial_batch_id: Optional[int] = None,
        controller: Optional[AttendanceController] = None,
    ):
        super().__init__(expand=True, padding=AppTheme.PAD_LG)
        self.controller = controller or AttendanceController()
        self.selected_batch_id: Optional[int] = initial_batch_id
        self.selected_date: str = datetime.now().strftime("%Y-%m-%d")
        self.active_subtab_index: int = 0  # 0: Online Attendance, 1: Batch Matrix Spreadsheet

        # Data cache
        self.batches: List[Dict[str, Any]] = []
        self.enrolled_students: List[BatchStudentDTO] = []
        self.student_toggles: Dict[int, ft.Switch] = {}
        self.current_matrix: Optional[BatchAttendanceMatrixDTO] = None

        # ══════════════════════════════════════════════════════════════════════
        # 1. HEADER ROW & ACTION BUTTONS
        # ══════════════════════════════════════════════════════════════════════
        self.title_text = ft.Text(
            "Attendance Management",
            size=AppTheme.SIZE_H1,
            weight=ft.FontWeight.BOLD,
            color=AppTheme.TEXT_PRIMARY,
        )
        self.subtitle_text = ft.Text(
            "Live batch attendance, optical sheet scanning & spreadsheet ledger",
            size=AppTheme.SIZE_CAPTION,
            color=AppTheme.TEXT_SECONDARY,
        )

        self.print_format_btn = ft.OutlinedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.PRINT, size=15),
                    ft.Text("Print Offline Format", size=AppTheme.SIZE_CAPTION),
                ],
                spacing=4,
            ),
            tooltip="Generate fixed printable attendance format in Excel with customizable columns",
            on_click=self.handle_open_print_format,
        )

        self.upload_ocr_btn = ft.OutlinedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.DOCUMENT_SCANNER, size=15),
                    ft.Text("Upload Offline Scan", size=AppTheme.SIZE_CAPTION),
                ],
                spacing=4,
            ),
            tooltip="Upload marked attendance sheet photo (JPG/PNG, no size limit) for OCR scan",
            on_click=self.handle_open_ocr_upload,
        )

        self.export_excel_btn = ft.FilledButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.TABLE_VIEW, size=15),
                    ft.Text("Export Excel (.xlsx)", size=AppTheme.SIZE_CAPTION),
                ],
                spacing=4,
            ),
            style=ft.ButtonStyle(
                bgcolor=AppTheme.PRIMARY,
                color=AppTheme.SURFACE,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
            ),
            tooltip="Export batch attendance spreadsheet matrix to styled Excel",
            on_click=self.handle_export_excel,
        )

        self.export_pdf_btn = ft.OutlinedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.PICTURE_AS_PDF, size=15),
                    ft.Text("Export PDF", size=AppTheme.SIZE_CAPTION),
                ],
                spacing=4,
            ),
            tooltip="Export batch attendance spreadsheet to vector PDF with SIMS watermark",
            on_click=self.handle_export_pdf,
        )

        self.refresh_btn = ft.IconButton(
            icon=ft.Icons.REFRESH,
            icon_size=20,
            tooltip="Refresh Attendance",
            on_click=lambda _: self.load_data(),
        )

        action_buttons_row = ft.Row(
            controls=[
                self.print_format_btn,
                self.upload_ocr_btn,
                self.export_excel_btn,
                self.export_pdf_btn,
                self.refresh_btn,
            ],
            spacing=AppTheme.PAD_SM,
            wrap=True,
        )

        header_row = ft.Row(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.CO_PRESENT, size=28, color=AppTheme.PRIMARY),
                        ft.Column(controls=[self.title_text, self.subtitle_text], spacing=2),
                    ],
                    spacing=AppTheme.PAD_SM,
                ),
                action_buttons_row,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            wrap=True,
        )

        # ══════════════════════════════════════════════════════════════════════
        # 2. SELECTOR TOOLBAR: BATCH DROPDOWN, DATE & MODE SWITCHER
        # ══════════════════════════════════════════════════════════════════════
        self.batch_dropdown = ft.Dropdown(
            label="Select Batch",
            hint_text="Choose a training batch...",
            width=360,
            border_radius=AppTheme.RADIUS_MD,
            on_select=self.handle_batch_change,
        )

        self.date_field = ft.TextField(
            label="Session Date",
            value=self.selected_date,
            width=150,
            border_radius=AppTheme.RADIUS_MD,
            on_change=self.handle_date_change,
        )

        # Mode Tab Switchers
        self.tab_online_btn = ft.TextButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.TOGGLE_ON, size=16),
                    ft.Text("Online Attendance (Toggles)", weight=ft.FontWeight.BOLD),
                ],
                spacing=6,
            ),
            style=ft.ButtonStyle(
                bgcolor=AppTheme.PRIMARY_LIGHT,
                color=AppTheme.PRIMARY,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
            ),
            on_click=lambda _: self._set_subtab(0),
        )

        self.tab_matrix_btn = ft.TextButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.GRID_ON, size=16),
                    ft.Text("Batch Matrix Spreadsheet", weight=ft.FontWeight.NORMAL),
                ],
                spacing=6,
            ),
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.TRANSPARENT,
                color=AppTheme.TEXT_SECONDARY,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
            ),
            on_click=lambda _: self._set_subtab(1),
        )

        selector_card = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Row(
                        controls=[
                            self.batch_dropdown,
                            self.date_field,
                        ],
                        spacing=12,
                    ),
                    ft.Row(
                        controls=[
                            self.tab_online_btn,
                            self.tab_matrix_btn,
                        ],
                        spacing=8,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                wrap=True,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=ft.Padding(14, 10, 14, 10),
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        # ══════════════════════════════════════════════════════════════════════
        # 3. ONLINE ATTENDANCE PANEL (LIVE TOGGLE SWITCHES)
        # ══════════════════════════════════════════════════════════════════════
        self.enrolled_count_badge = ft.Text("0 Enrolled", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD)
        self.present_count_text = ft.Text("0 Present", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color="#059669")
        self.absent_count_text = ft.Text("0 Absent", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color="#DC2626")

        self.mark_all_present_btn = ft.OutlinedButton(
            content=ft.Text("All Present (✓)", size=AppTheme.SIZE_CAPTION),
            icon=ft.Icons.DONE_ALL,
            style=ft.ButtonStyle(color="#059669"),
            on_click=self.handle_mark_all_present,
        )

        self.mark_all_absent_btn = ft.OutlinedButton(
            content=ft.Text("All Absent (✗)", size=AppTheme.SIZE_CAPTION),
            icon=ft.Icons.REMOVE_DONE,
            style=ft.ButtonStyle(color="#DC2626"),
            on_click=self.handle_mark_all_absent,
        )

        self.save_online_btn = ft.FilledButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.SAVE, size=16),
                    ft.Text("Save Attendance to Spreadsheet", weight=ft.FontWeight.BOLD),
                ],
                spacing=6,
            ),
            style=ft.ButtonStyle(
                bgcolor=AppTheme.PRIMARY,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                padding=ft.Padding(16, 10, 16, 10),
            ),
            on_click=self.handle_save_online_attendance,
        )

        online_actions_row = ft.Row(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.PEOPLE_ALT, size=18, color=AppTheme.TEXT_SECONDARY),
                        self.enrolled_count_badge,
                        ft.Container(width=8),
                        self.present_count_text,
                        ft.Text("•", color=AppTheme.TEXT_MUTED),
                        self.absent_count_text,
                    ],
                    spacing=6,
                ),
                ft.Row(
                    controls=[
                        self.mark_all_present_btn,
                        self.mark_all_absent_btn,
                        self.save_online_btn,
                    ],
                    spacing=8,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            wrap=True,
        )

        self.online_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("S.No", weight=ft.FontWeight.BOLD, size=11), numeric=True),
                ft.DataColumn(ft.Text("Candidate No", weight=ft.FontWeight.BOLD, size=11)),
                ft.DataColumn(ft.Text("Student Name", weight=ft.FontWeight.BOLD, size=11)),
                ft.DataColumn(ft.Text("Contact Mobile", weight=ft.FontWeight.BOLD, size=11)),
                ft.DataColumn(ft.Text("Pending Fees", weight=ft.FontWeight.BOLD, size=11)),
                ft.DataColumn(ft.Text("Mark Attendance (Default: Absent)", weight=ft.FontWeight.BOLD, size=11)),
            ],
            rows=[],
            heading_row_color=AppTheme.SURFACE_VARIANT,
            heading_row_height=40,
            data_row_min_height=48,
            border=ft.Border.all(1, AppTheme.BORDER),
            border_radius=AppTheme.RADIUS_MD,
            vertical_lines=ft.BorderSide(0.5, AppTheme.BORDER),
            horizontal_lines=ft.BorderSide(0.5, AppTheme.BORDER),
        )

        self.online_table_container = ft.Container(
            content=ft.ListView(
                controls=[self.online_table],
                expand=True,
            ),
            expand=True,
        )

        self.online_panel = ft.Column(
            controls=[
                online_actions_row,
                self.online_table_container,
            ],
            spacing=10,
            expand=True,
            visible=True,
        )

        # ══════════════════════════════════════════════════════════════════════
        # 4. BATCH MATRIX SPREADSHEET PANEL (MULTI-SESSION VIEW)
        # ══════════════════════════════════════════════════════════════════════
        self.matrix_stats_text = ft.Text(
            "Overall Attendance: 0%",
            size=AppTheme.SIZE_BODY,
            weight=ft.FontWeight.BOLD,
            color=AppTheme.PRIMARY,
        )

        matrix_top_row = ft.Row(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.TABLE_CHART, size=18, color=AppTheme.PRIMARY),
                        self.matrix_stats_text,
                    ],
                    spacing=6,
                ),
                ft.Text(
                    "Legend: [P] = Present (Green)  •  [A] = Absent (Red)  •  [—] = Unmarked",
                    size=AppTheme.SIZE_CAPTION,
                    color=AppTheme.TEXT_MUTED,
                    italic=True,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.default_matrix_columns = [
            ft.DataColumn(ft.Text("Candidate No", weight=ft.FontWeight.BOLD, size=11)),
            ft.DataColumn(ft.Text("Student Name", weight=ft.FontWeight.BOLD, size=11)),
            ft.DataColumn(ft.Text("Mobile", weight=ft.FontWeight.BOLD, size=11)),
            ft.DataColumn(ft.Text("Attendance Status", weight=ft.FontWeight.BOLD, size=11)),
        ]

        self.matrix_table = ft.DataTable(
            columns=self.default_matrix_columns,
            rows=[],
            heading_row_color=AppTheme.SURFACE_VARIANT,
            heading_row_height=40,
            data_row_min_height=44,
            border=ft.Border.all(1, AppTheme.BORDER),
            border_radius=AppTheme.RADIUS_MD,
            vertical_lines=ft.BorderSide(0.5, AppTheme.BORDER),
            horizontal_lines=ft.BorderSide(0.5, AppTheme.BORDER),
        )

        self.matrix_scroll_col = ft.Column(
            controls=[self.matrix_table],
            scroll=ft.ScrollMode.AUTO,
        )

        self.matrix_scroll_row = ft.Row(
            controls=[self.matrix_scroll_col],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        self.matrix_empty_text = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.FACT_CHECK, size=48, color=AppTheme.TEXT_MUTED),
                    ft.Text(
                        "No attendance sessions recorded yet for this batch.",
                        size=AppTheme.SIZE_BODY,
                        color=AppTheme.TEXT_SECONDARY,
                    ),
                    ft.Text(
                        "Use Online Toggles or Upload an Offline Scan to record presenty.",
                        size=AppTheme.SIZE_CAPTION,
                        color=AppTheme.TEXT_MUTED,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=6,
            ),
            padding=ft.Padding(0, 40, 0, 40),
            alignment=ft.Alignment(0, 0),
            visible=False,
        )

        self.matrix_panel = ft.Column(
            controls=[
                matrix_top_row,
                ft.Container(
                    content=ft.Column(
                        controls=[self.matrix_scroll_row, self.matrix_empty_text],
                        expand=True,
                    ),
                    expand=True,
                ),
            ],
            spacing=10,
            expand=True,
            visible=False,
        )

        # ══════════════════════════════════════════════════════════════════════
        # 5. ASSEMBLE CONTENT
        # ══════════════════════════════════════════════════════════════════════
        self.content = ft.Column(
            controls=[
                header_row,
                ft.Divider(height=1, color=AppTheme.BORDER),
                selector_card,
                self.online_panel,
                self.matrix_panel,
            ],
            spacing=AppTheme.PAD_MD,
            expand=True,
        )

    @property
    def safe_page(self) -> Optional[ft.Page]:
        try:
            return getattr(self, "_root_page", None) or self.page or getattr(self, "_page", None)
        except (RuntimeError, AttributeError):
            return None

    def did_mount(self) -> None:
        """Called when view is mounted."""
        self.load_data()

    def _show_toast(self, message: str, is_error: bool = False, is_success: bool = False) -> None:
        p = self.safe_page
        if not p:
            return
        snack = ft.SnackBar(
            content=ft.Text(message, color=AppTheme.SURFACE),
            bgcolor=AppTheme.DANGER if is_error else (AppTheme.SUCCESS if is_success else AppTheme.PRIMARY),
        )
        p.overlay.append(snack)
        snack.open = True
        try:
            p.update()
        except RuntimeError:
            pass

    def _open_dialog(self, dlg: ft.AlertDialog) -> None:
        p = self.safe_page
        if not p:
            return
        if hasattr(p, "show_dialog"):
            p.show_dialog(dlg)
        elif hasattr(p, "open_dialog"):
            p.open_dialog(dlg)
        else:
            p.dialog = dlg
            dlg.open = True
            p.update()

    def _set_subtab(self, index: int) -> None:
        self.active_subtab_index = index
        is_online = (index == 0)

        self.online_panel.visible = is_online
        self.matrix_panel.visible = not is_online

        if is_online:
            self.tab_online_btn.style.bgcolor = AppTheme.PRIMARY_LIGHT
            self.tab_online_btn.style.color = AppTheme.PRIMARY
            self.tab_online_btn.content.controls[1].weight = ft.FontWeight.BOLD

            self.tab_matrix_btn.style.bgcolor = ft.Colors.TRANSPARENT
            self.tab_matrix_btn.style.color = AppTheme.TEXT_SECONDARY
            self.tab_matrix_btn.content.controls[1].weight = ft.FontWeight.NORMAL
        else:
            self.tab_online_btn.style.bgcolor = ft.Colors.TRANSPARENT
            self.tab_online_btn.style.color = AppTheme.TEXT_SECONDARY
            self.tab_online_btn.content.controls[1].weight = ft.FontWeight.NORMAL

            self.tab_matrix_btn.style.bgcolor = AppTheme.PRIMARY_LIGHT
            self.tab_matrix_btn.style.color = AppTheme.PRIMARY
            self.tab_matrix_btn.content.controls[1].weight = ft.FontWeight.BOLD

        p = self.safe_page
        if p:
            try:
                p.update()
            except RuntimeError:
                pass

    def load_data(self) -> None:
        """Loads all batches and populates dropdown and table."""
        try:
            self.batches = self.controller.get_batches()
            options = []
            for b in self.batches:
                label = f"{b['batch_name']} — {b['course_name']} ({b['timing']}) • {b['enrolled_count']} students"
                options.append(ft.dropdown.Option(str(b["id"]), label))

            self.batch_dropdown.options = options

            if not self.selected_batch_id and self.batches:
                self.selected_batch_id = self.batches[0]["id"]

            if self.selected_batch_id:
                self.batch_dropdown.value = str(self.selected_batch_id)
                self.load_batch_attendance(self.selected_batch_id)

        except Exception as exc:
            LogService.error(f"Failed to load attendance batches: {exc}", context="AttendanceHome")
            self._show_toast("Failed to load batch list.", is_error=True)

    def load_batch_attendance(self, batch_id: int) -> None:
        """Loads students, existing session for selected date, and multi-session matrix."""
        try:
            self.enrolled_students = self.controller.get_enrolled_students(batch_id)
            self.enrolled_count_badge.value = f"{len(self.enrolled_students)} Enrolled"

            # Check if an attendance session already exists for this date
            existing_session = self.controller.get_session(batch_id, self.selected_date)
            existing_marks: Dict[int, str] = {}
            if existing_session:
                for rec in existing_session.records:
                    existing_marks[rec.student_id] = rec.status

            # Populate Online Table
            self._build_online_table_rows(existing_marks)

            # Load and populate Multi-Session Matrix
            self.current_matrix = self.controller.get_batch_matrix(batch_id)
            self._build_matrix_table(self.current_matrix)

            p = self.safe_page
            if p:
                try:
                    p.update()
                except RuntimeError:
                    pass

        except Exception as exc:
            LogService.error(f"Failed to load batch attendance: {exc}", context="AttendanceHome")
            self._show_toast(f"Failed to load attendance for batch {batch_id}", is_error=True)

    def _build_online_table_rows(self, existing_marks: Dict[int, str]) -> None:
        """Builds student rows with interactive toggle switches."""
        self.student_toggles.clear()
        rows: List[ft.DataRow] = []
        p_count = 0
        a_count = 0

        for idx, st in enumerate(self.enrolled_students, 1):
            # Default is OFF (Absent) unless already recorded as PRESENT
            is_present = (existing_marks.get(st.student_id) == "PRESENT")
            if is_present:
                p_count += 1
            else:
                a_count += 1

            sw = ft.Switch(
                value=is_present,
                active_color="#059669",
                scale=0.9,
                tooltip="ON = Present, OFF = Absent",
                on_change=self._on_toggle_changed,
            )
            self.student_toggles[st.student_id] = sw

            status_chip = ft.Text(
                "PRESENT" if is_present else "ABSENT",
                size=11,
                weight=ft.FontWeight.BOLD,
                color="#059669" if is_present else "#DC2626",
            )

            pending_val = f"₹{st.pending_fees:,.2f}" if st.pending_fees > 0 else "₹0.00"

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(str(idx), size=11)),
                        ft.DataCell(ft.Text(st.candidate_number or "—", size=11, weight=ft.FontWeight.W_500)),
                        ft.DataCell(ft.Text(st.student_name, size=11, weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(st.mobile_number or "—", size=11)),
                        ft.DataCell(
                            ft.Text(
                                pending_val,
                                size=11,
                                weight=ft.FontWeight.BOLD if st.pending_fees > 0 else ft.FontWeight.NORMAL,
                                color=AppTheme.DANGER if st.pending_fees > 0 else AppTheme.SUCCESS,
                            )
                        ),
                        ft.DataCell(
                            ft.Row(
                                controls=[sw, status_chip],
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            )
                        ),
                    ]
                )
            )

        self.online_table.rows = rows
        self.present_count_text.value = f"{p_count} Present"
        self.absent_count_text.value = f"{a_count} Absent"

    def _on_toggle_changed(self, e: ft.ControlEvent) -> None:
        """Updates present/absent counters when an individual switch is toggled."""
        p_count = 0
        a_count = 0
        for st_id, sw in self.student_toggles.items():
            if sw.value:
                p_count += 1
            else:
                a_count += 1

        self.present_count_text.value = f"{p_count} Present"
        self.absent_count_text.value = f"{a_count} Absent"

        # Update adjacent chip label in table row
        for r in self.online_table.rows:
            cell_row = r.cells[5].content
            if isinstance(cell_row, ft.Row) and len(cell_row.controls) >= 2:
                sw_ctrl = cell_row.controls[0]
                chip = cell_row.controls[1]
                if isinstance(sw_ctrl, ft.Switch) and isinstance(chip, ft.Text):
                    is_p = sw_ctrl.value
                    chip.value = "PRESENT" if is_p else "ABSENT"
                    chip.color = "#059669" if is_p else "#DC2626"

        p = self.safe_page
        if p:
            try:
                p.update()
            except RuntimeError:
                pass

    def _build_matrix_table(self, matrix: BatchAttendanceMatrixDTO) -> None:
        """Constructs multi-session matrix columns and rows for spreadsheet viewing."""
        has_sessions = len(matrix.session_dates) > 0 and len(matrix.rows) > 0
        self.matrix_scroll_row.visible = has_sessions
        self.matrix_empty_text.visible = not has_sessions
        self.matrix_stats_text.value = f"Overall Attendance: {matrix.overall_attendance_rate}%  •  {len(matrix.session_dates)} Sessions"

        if not has_sessions:
            self.matrix_table.columns = self.default_matrix_columns
            self.matrix_table.rows = []
            return

        # Build dynamic columns
        cols: List[ft.DataColumn] = [
            ft.DataColumn(ft.Text("Candidate No", weight=ft.FontWeight.BOLD, size=11)),
            ft.DataColumn(ft.Text("Student Name", weight=ft.FontWeight.BOLD, size=11)),
            ft.DataColumn(ft.Text("Mobile", weight=ft.FontWeight.BOLD, size=11)),
        ]

        for d in matrix.session_dates:
            # Short label MM-DD
            short_d = d[5:]
            cols.append(ft.DataColumn(ft.Text(short_d, weight=ft.FontWeight.BOLD, size=11), numeric=True))

        cols.extend([
            ft.DataColumn(ft.Text("Present", weight=ft.FontWeight.BOLD, size=11), numeric=True),
            ft.DataColumn(ft.Text("Absent", weight=ft.FontWeight.BOLD, size=11), numeric=True),
            ft.DataColumn(ft.Text("% Health", weight=ft.FontWeight.BOLD, size=11), numeric=True),
        ])

        # Build rows
        rows: List[ft.DataRow] = []
        for r in matrix.rows:
            cells: List[ft.DataCell] = [
                ft.DataCell(ft.Text(r.candidate_number or "—", size=11)),
                ft.DataCell(ft.Text(r.student_name, size=11, weight=ft.FontWeight.BOLD)),
                ft.DataCell(ft.Text(r.mobile_number or "—", size=11)),
            ]

            for d in matrix.session_dates:
                mark = r.date_marks.get(d, "—")
                bg_col = "#ECFDF5" if mark == "P" else ("#FEF2F2" if mark == "A" else ft.Colors.TRANSPARENT)
                fg_col = "#059669" if mark == "P" else ("#DC2626" if mark == "A" else AppTheme.TEXT_MUTED)

                chip = ft.Container(
                    content=ft.Text(mark, size=11, weight=ft.FontWeight.BOLD, color=fg_col),
                    bgcolor=bg_col,
                    border_radius=4,
                    padding=ft.Padding(6, 2, 6, 2),
                    alignment=ft.Alignment(0, 0),
                    width=30,
                )
                cells.append(ft.DataCell(chip))

            # Summary cells
            cells.append(ft.DataCell(ft.Text(str(r.total_present), size=11, weight=ft.FontWeight.BOLD, color="#059669")))
            cells.append(ft.DataCell(ft.Text(str(r.total_absent), size=11, weight=ft.FontWeight.BOLD, color="#DC2626")))

            health_col = HEALTH_COLORS.get(r.health_status, "#059669")
            health_bg = HEALTH_BG_COLORS.get(r.health_status, "#ECFDF5")
            badge = ft.Container(
                content=ft.Text(f"{r.attendance_percentage}%", size=11, weight=ft.FontWeight.BOLD, color=health_col),
                bgcolor=health_bg,
                border_radius=AppTheme.RADIUS_PILL,
                padding=ft.Padding(8, 2, 8, 2),
                alignment=ft.Alignment(0, 0),
            )
            cells.append(ft.DataCell(badge))

            rows.append(ft.DataRow(cells=cells))

        self.matrix_table.columns = cols
        self.matrix_table.rows = rows

    # ══════════════════════════════════════════════════════════════════════
    # EVENT HANDLERS
    # ══════════════════════════════════════════════════════════════════════
    def handle_batch_change(self, e: ft.ControlEvent) -> None:
        val = self.batch_dropdown.value
        if val:
            self.selected_batch_id = int(val)
            self.load_batch_attendance(self.selected_batch_id)

    def handle_date_change(self, e: ft.ControlEvent) -> None:
        self.selected_date = self.date_field.value.strip() or datetime.now().strftime("%Y-%m-%d")
        if self.selected_batch_id:
            self.load_batch_attendance(self.selected_batch_id)

    def handle_mark_all_present(self, e: ft.ControlEvent) -> None:
        for sw in self.student_toggles.values():
            sw.value = True
        self._on_toggle_changed(None)

    def handle_mark_all_absent(self, e: ft.ControlEvent) -> None:
        for sw in self.student_toggles.values():
            sw.value = False
        self._on_toggle_changed(None)

    def handle_save_online_attendance(self, e: ft.ControlEvent) -> None:
        """Saves current toggle states into the database attendance spreadsheet."""
        if not self.selected_batch_id:
            self._show_toast("Please select a batch first.", is_error=True)
            return

        student_marks = []
        for st in self.enrolled_students:
            sw = self.student_toggles.get(st.student_id)
            is_present = sw.value if sw else False
            student_marks.append(
                {
                    "student_id": st.student_id,
                    "admission_id": st.admission_id,
                    "is_present": is_present,
                    "status": "PRESENT" if is_present else "ABSENT",
                }
            )

        try:
            self.controller.record_online_attendance(
                batch_id=self.selected_batch_id,
                session_date=self.selected_date,
                student_marks=student_marks,
            )
            self._show_toast(f"✓ Attendance saved to spreadsheet for {self.selected_date}!", is_success=True)
            self.load_batch_attendance(self.selected_batch_id)

        except Exception as exc:
            LogService.error(f"Failed to save online attendance: {exc}", context="AttendanceHome")
            self._show_toast(f"Failed to save attendance: {exc}", is_error=True)

    def handle_open_print_format(self, e: ft.ControlEvent) -> None:
        """Opens modal to customize and generate physical attendance sheet."""
        if not self.selected_batch_id:
            self._show_toast("Please select a batch first.", is_error=True)
            return

        batch_name = "Batch"
        course_name = "Course"
        for b in self.batches:
            if b["id"] == self.selected_batch_id:
                batch_name = b["batch_name"]
                course_name = b["course_name"]
                break

        def on_done(path: str):
            self._show_toast(f"Generated attendance format: {Path(path).name}", is_success=True)

        dlg = OfflineFormatDialog(
            batch_id=self.selected_batch_id,
            batch_name=batch_name,
            course_name=course_name,
            on_generated=on_done,
            controller=self.controller,
        )
        self._open_dialog(dlg)

    def handle_open_ocr_upload(self, e: ft.ControlEvent) -> None:
        """Opens modal to upload and scan offline physical sheet image."""
        if not self.selected_batch_id:
            self._show_toast("Please select a batch first.", is_error=True)
            return

        batch_name = "Batch"
        for b in self.batches:
            if b["id"] == self.selected_batch_id:
                batch_name = b["batch_name"]
                break

        def on_saved():
            self.load_batch_attendance(self.selected_batch_id)

        dlg = OfflineUploadModal(
            batch_id=self.selected_batch_id,
            batch_name=batch_name,
            session_date=self.selected_date,
            on_saved=on_saved,
            controller=self.controller,
        )
        self._open_dialog(dlg)

    def handle_export_excel(self, e: ft.ControlEvent) -> None:
        """Exports batch attendance matrix to Excel (.xlsx)."""
        if not self.selected_batch_id:
            self._show_toast("Please select a batch first.", is_error=True)
            return
        try:
            path = self.controller.export_matrix_excel(self.selected_batch_id)
            self._show_toast(f"Attendance matrix exported to Excel: {Path(path).name}", is_success=True)
            open_path_externally(Path(path).parent)
        except Exception as exc:
            LogService.error(f"Failed to export attendance Excel: {exc}", context="AttendanceHome")
            self._show_toast("Failed to export attendance Excel.", is_error=True)

    def handle_export_pdf(self, e: ft.ControlEvent) -> None:
        """Exports batch attendance matrix to watermarked PDF."""
        if not self.selected_batch_id:
            self._show_toast("Please select a batch first.", is_error=True)
            return
        try:
            path = self.controller.export_matrix_pdf(self.selected_batch_id)
            self._show_toast(f"Attendance report exported with SIMS watermark: {Path(path).name}", is_success=True)
            open_path_externally(Path(path).parent)
        except Exception as exc:
            LogService.error(f"Failed to export attendance PDF: {exc}", context="AttendanceHome")
            self._show_toast("Failed to export attendance PDF.", is_error=True)
