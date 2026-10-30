# modules/attendance/views/attendance_home.py

from __future__ import annotations
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import webbrowser
import flet as ft

from core.logger.service import LogService
from modules.attendance.constants import (
    AttendanceMode,
    HEALTH_BG_COLORS,
    HEALTH_COLORS,
    AttendanceHealth,
)
from modules.attendance.controller import AttendanceController
from modules.attendance.dto import (
    AttendanceRecordDTO,
    AttendanceSessionDTO,
    BatchAttendanceMatrixDTO,
    BatchAttendanceMatrixRowDTO,
    BatchStudentDTO,
    StudentAttendanceHealthDTO,
)
from modules.attendance.views.excel_import_reconciliation_modal import ExcelImportReconciliationModal
from modules.attendance.views.offline_format_dialog import OfflineFormatDialog
from modules.attendance.views.offline_register_dialog import OfflineRegisterDialog
from modules.attendance.views.offline_upload_modal import OfflineUploadModal
from shared.utils.formatting import format_whatsapp_url
from shared.utils.os_helper import open_path_externally
from shared.utils.export_helper import export_and_prompt_save
from core.utils.image_utils import is_valid_image_file
from ui.themes.theme import AppTheme
from ui.widgets.hover_card import HoverCard
from ui.widgets.badge import StatusBadge



class AttendanceHome(ft.Container):
    """
    Modern Attendance Management & Analytics Workspace in SIMS v2.2.
    Features:
      1. Executive Top KPI Metrics Cards (Today's Markings, Batch Average, Sessions Conducted, Defaulters).
      2. Quick Date Navigation Stepper (<, >, Today, Date Input).
      3. Tab 0: Daily Attendance marking with interactive toggles, real-time search & status filtering.
      4. Tab 1: Multi-Session Batch Matrix Spreadsheet with dynamic search & health filtering.
      5. Tab 2: Defaulters & Student Health Analytics table for chronic absentee intervention.
      6. Offline Excel format generation, OCR sheet scanning, Excel & watermarked PDF exports.
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
        self.active_subtab_index: int = 0  # 0: Online, 1: Offline, 2: Matrix, 3: Health
        self.attendance_settings: Dict[str, Any] = self.controller.get_attendance_settings()

        # Data cache & state
        self.batches: List[Dict[str, Any]] = []
        self.enrolled_students: List[BatchStudentDTO] = []
        self.student_toggles: Dict[int, ft.Switch] = {}
        self.current_matrix: Optional[BatchAttendanceMatrixDTO] = None
        self.existing_session_marks: Dict[int, str] = {}

        # Search & Filter states
        self.online_search_query: str = ""
        self.online_filter_status: str = "ALL"  # ALL, PRESENT, ABSENT, DUES
        self.matrix_search_query: str = ""
        self.matrix_filter_health: str = "ALL"  # ALL, CRITICAL, AVERAGE, GOOD, EXCELLENT
        self.health_search_query: str = ""

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
            "Live daily marking, batch spreadsheet matrix, optical scan & health analytics",
            size=AppTheme.SIZE_CAPTION,
            color=AppTheme.TEXT_SECONDARY,
        )

        self.register_excel_btn = ft.OutlinedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.CALENDAR_MONTH, size=15),
                    ft.Text("Digital Register", size=AppTheme.SIZE_CAPTION),
                ],
                spacing=4,
            ),
            tooltip="Generate multi-day digital Excel register (8d/15d/1m/2m)",
            on_click=self.handle_open_offline_register,
        )

        self.print_format_btn = ft.OutlinedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.PRINT, size=15),
                    ft.Text("Print Format", size=AppTheme.SIZE_CAPTION),
                ],
                spacing=4,
            ),
            tooltip="Generate printable Excel format with custom columns",
            on_click=self.handle_open_print_format,
        )

        self.upload_ocr_btn = ft.OutlinedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.DOCUMENT_SCANNER, size=15),
                    ft.Text("Upload Scan", size=AppTheme.SIZE_CAPTION),
                ],
                spacing=4,
            ),
            tooltip="Upload marked sheet photo (JPG/PNG) for OCR scan",
            on_click=self.handle_open_ocr_upload,
        )

        self.export_excel_btn = ft.FilledButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.TABLE_VIEW, size=15),
                    ft.Text("Export Excel", size=AppTheme.SIZE_CAPTION),
                ],
                spacing=4,
            ),
            height=38,
            style=ft.ButtonStyle(
                bgcolor=AppTheme.PRIMARY,
                color=AppTheme.SURFACE,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
            ),
            tooltip="Export batch attendance spreadsheet matrix to Excel (.xlsx)",
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
            height=38,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
            ),
            tooltip="Export batch attendance matrix to watermarked PDF",
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
                self.refresh_btn,
            ],
            spacing=AppTheme.PAD_SM,
        )

        header_row = ft.Row(
            controls=[
                ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Icon(ft.Icons.CO_PRESENT, size=24, color=AppTheme.PRIMARY),
                            bgcolor=AppTheme.PRIMARY_LIGHT,
                            padding=8,
                            border_radius=AppTheme.RADIUS_MD,
                        ),
                        ft.Column(controls=[self.title_text, self.subtitle_text], spacing=2),
                    ],
                    spacing=AppTheme.PAD_SM,
                ),
                ft.Row(
                    controls=[
                        ft.OutlinedButton(
                            content=ft.Row([ft.Icon(ft.Icons.SYNC, size=15), ft.Text("Refresh", size=AppTheme.SIZE_CAPTION)], spacing=4),
                            height=36,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                            ),
                            tooltip="Synchronize and refresh all attendance data",
                            on_click=lambda _: self.load_data(),
                        ),
                    ],
                    spacing=8,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            wrap=True,
        )

        # ══════════════════════════════════════════════════════════════════════
        # 2. TOP METRIC KPI CARDS
        # ══════════════════════════════════════════════════════════════════════
        self.kpi_session_status_text = ft.Text("0 / 0 Present", size=15, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY)
        self.kpi_session_sub_text = ft.Text("No session for today", size=11, color=AppTheme.TEXT_MUTED)

        self.kpi_overall_rate_text = ft.Text("0.0%", size=15, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY)
        self.kpi_overall_sub_text = ft.Text("Batch average attendance", size=11, color=AppTheme.TEXT_MUTED)

        self.kpi_total_sessions_text = ft.Text("0 Sessions", size=15, weight=ft.FontWeight.BOLD, color="#4338CA")
        self.kpi_total_sessions_sub_text = ft.Text("Recorded in ledger", size=11, color=AppTheme.TEXT_MUTED)

        self.kpi_defaulters_text = ft.Text("0 Students", size=15, weight=ft.FontWeight.BOLD, color=AppTheme.SUCCESS)
        self.kpi_defaulters_sub_text = ft.Text("Attendance health: Normal", size=11, color=AppTheme.TEXT_MUTED)

        self.kpi_cards_container = self._build_kpi_cards()

        # ══════════════════════════════════════════════════════════════════════
        # 3. SELECTOR & DATE NAVIGATION CARD
        # ══════════════════════════════════════════════════════════════════════
        # Batch metadata indicators
        self.batch_course_chip = ft.Text("Course: —", size=11, color=AppTheme.TEXT_SECONDARY)
        self.batch_timing_chip = ft.Text("Schedule: —", size=11, color=AppTheme.TEXT_SECONDARY)
        self.batch_enrolled_chip = ft.Text("Enrolled: 0", size=11, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY)

        self.batch_meta_container = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Row([ft.Icon(ft.Icons.SCHOOL, size=13, color=AppTheme.PRIMARY), self.batch_course_chip], spacing=4),
                        bgcolor=AppTheme.PRIMARY_LIGHT,
                        padding=ft.Padding(8, 4, 8, 4),
                        border_radius=AppTheme.RADIUS_SM,
                    ),
                    ft.Container(
                        content=ft.Row([ft.Icon(ft.Icons.SCHEDULE, size=13, color="#4338CA"), self.batch_timing_chip], spacing=4),
                        bgcolor="#EEF2FF",
                        padding=ft.Padding(8, 4, 8, 4),
                        border_radius=AppTheme.RADIUS_SM,
                    ),
                    ft.Container(
                        content=ft.Row([ft.Icon(ft.Icons.GROUPS, size=13, color="#059669"), self.batch_enrolled_chip], spacing=4),
                        bgcolor="#ECFDF5",
                        padding=ft.Padding(8, 4, 8, 4),
                        border_radius=AppTheme.RADIUS_SM,
                    ),
                ],
                spacing=6,
                wrap=True,
            ),
            visible=False,
        )

        self.batch_dropdown = ft.Dropdown(
            label="Select Training Batch",
            hint_text="Choose a training batch...",
            width=480,
            border_radius=AppTheme.RADIUS_MD,
            on_select=self.handle_batch_change,
        )

        self.prev_date_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_LEFT,
            icon_size=18,
            tooltip="Previous Day",
            on_click=self._handle_prev_day,
        )

        self.date_field = ft.TextField(
            label="Session Date",
            value=self.selected_date,
            width=135,
            border_radius=AppTheme.RADIUS_MD,
            on_change=self.handle_date_change,
        )

        self.next_date_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_RIGHT,
            icon_size=18,
            tooltip="Next Day",
            on_click=self._handle_next_day,
        )

        self.today_btn = ft.OutlinedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.TODAY, size=14),
                    ft.Text("Today", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.W_500),
                ],
                spacing=4,
            ),
            tooltip="Jump to Today's date",
            on_click=self._handle_jump_today,
        )

        self.datepicker_btn = ft.IconButton(
            icon=ft.Icons.CALENDAR_MONTH,
            icon_size=18,
            tooltip="Open Calendar Date Picker",
            on_click=self._handle_open_datepicker,
        )

        self.date_weekday_text = ft.Text(
            datetime.now().strftime("%A, %d %b %Y"),
            size=11,
            color=AppTheme.TEXT_SECONDARY,
            weight=ft.FontWeight.W_500,
        )

        self.session_badge = ft.Container(
            content=ft.Text("🟡 Unsaved / New Session", size=10, weight=ft.FontWeight.BOLD, color="#D97706"),
            bgcolor="#FFFBEB",
            padding=ft.Padding(8, 4, 8, 4),
            border_radius=AppTheme.RADIUS_PILL,
            border=ft.Border.all(0.5, "#FDE68A"),
        )

        self.live_attendance_rate_chip = ft.Text(
            "0.0% Present Rate",
            size=11,
            weight=ft.FontWeight.BOLD,
            color=AppTheme.PRIMARY,
        )

        # 4-Tab Switcher: 0: Online, 1: Offline, 2: Matrix, 3: Health
        self.tab_online_btn = ft.TextButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.TOGGLE_ON, size=16),
                    ft.Text("Online Attendance", weight=ft.FontWeight.BOLD),
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

        self.tab_offline_btn = ft.TextButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.DESCRIPTION, size=16),
                    ft.Text("Offline Attendance", weight=ft.FontWeight.NORMAL),
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

        self.tab_matrix_btn = ft.TextButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.GRID_ON, size=16),
                    ft.Text("Matrix Ledger", weight=ft.FontWeight.NORMAL),
                ],
                spacing=6,
            ),
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.TRANSPARENT,
                color=AppTheme.TEXT_SECONDARY,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
            ),
            on_click=lambda _: self._set_subtab(2),
        )

        self.tab_health_btn = ft.TextButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.HEALTH_AND_SAFETY, size=16),
                    ft.Text("Health & Defaulters", weight=ft.FontWeight.NORMAL),
                ],
                spacing=6,
            ),
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.TRANSPARENT,
                color=AppTheme.TEXT_SECONDARY,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
            ),
            on_click=lambda _: self._set_subtab(3),
        )

        # Dedicated Batch Selection Card (Step 1)
        self.batch_selection_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Icon(ft.Icons.SCHOOL, size=22, color=AppTheme.PRIMARY),
                                bgcolor=AppTheme.PRIMARY_LIGHT,
                                padding=8,
                                border_radius=AppTheme.RADIUS_MD,
                            ),
                            ft.Column(
                                controls=[
                                    ft.Text("Step 1: Select Training Batch", size=15, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                                    ft.Text("Choose a batch to start taking live attendance, manage offline registers, or inspect spreadsheet matrices.", size=11, color=AppTheme.TEXT_SECONDARY),
                                ],
                                spacing=2,
                            ),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    ft.Row(
                        controls=[
                            self.batch_dropdown,
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=AppTheme.TEXT_MUTED),
                            ft.Text("Once selected, the batch workspace will load with full daily marking and analytics.", size=11, color=AppTheme.TEXT_MUTED),
                        ],
                        spacing=6,
                    ),
                ],
                spacing=10,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=ft.Padding(16, 14, 16, 14),
            border_radius=AppTheme.RADIUS_LG,
            border=ft.Border.all(1, AppTheme.BORDER),
            animate_opacity=ft.Animation(350, ft.AnimationCurve.EASE_OUT),
            visible=True,
        )
        self.selector_card = self.batch_selection_card  # Preserved reference

        # Active Batch Header Bar with Back Button
        self.back_to_batches_btn = ft.OutlinedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ARROW_BACK, size=15),
                    ft.Text("Change Batch", size=12, weight=ft.FontWeight.W_500),
                ],
                spacing=4,
            ),
            height=36,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                padding=ft.Padding(10, 4, 10, 4),
            ),
            tooltip="Return to Batch Selection",
            on_click=self._handle_back_to_batches,
        )

        self.active_batch_title_text = ft.Text(
            "Batch: —",
            size=15,
            weight=ft.FontWeight.BOLD,
            color=AppTheme.TEXT_PRIMARY,
        )

        self.active_batch_header_bar = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Row(
                        controls=[
                            self.back_to_batches_btn,
                            self.active_batch_title_text,
                            self.batch_meta_container,
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        wrap=True,
                    ),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                self.tab_online_btn,
                                self.tab_offline_btn,
                                self.tab_matrix_btn,
                                self.tab_health_btn,
                            ],
                            spacing=4,
                            wrap=True,
                        ),
                        bgcolor=AppTheme.SURFACE_VARIANT,
                        padding=ft.Padding(4, 4, 4, 4),
                        border_radius=AppTheme.RADIUS_MD,
                        border=ft.Border.all(1, AppTheme.BORDER),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                wrap=True,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=ft.Padding(14, 10, 14, 10),
            border_radius=AppTheme.RADIUS_LG,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        # ══════════════════════════════════════════════════════════════════════
        # 4. TAB 0: DAILY ONLINE ATTENDANCE PANEL
        # ══════════════════════════════════════════════════════════════════════
        self.enrolled_count_badge = ft.Text("0 Enrolled", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD)
        self.present_count_text = ft.Text("0 Present", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color="#059669")
        self.absent_count_text = ft.Text("0 Absent", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color="#DC2626")

        self.online_search_box = ft.TextField(
            hint_text="Search student name, roll no, mobile...",
            prefix_icon=ft.Icons.SEARCH,
            border_radius=AppTheme.RADIUS_MD,
            expand=True,
            height=38,
            dense=True,
            text_size=AppTheme.SIZE_BODY,
            content_padding=ft.Padding(10, 6, 10, 6),
            on_change=self._handle_online_search_change,
        )

        self.online_filter_dropdown = ft.Dropdown(
            label="Filter",
            value="ALL",
            width=190,
            height=38,
            dense=True,
            border_radius=AppTheme.RADIUS_MD,
            content_padding=ft.Padding(8, 4, 8, 4),
            options=[
                ft.dropdown.Option("ALL", "All Students"),
                ft.dropdown.Option("PRESENT", "Present Only"),
                ft.dropdown.Option("ABSENT", "Absent Only"),
                ft.dropdown.Option("DUES", "Pending Dues"),
            ],
            on_select=self._handle_online_filter_change,
        )

        self.mark_all_present_btn = ft.OutlinedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.DONE_ALL, size=14, color="#059669"),
                    ft.Text("All Present (✓)", size=12, weight=ft.FontWeight.W_500),
                ],
                spacing=4,
            ),
            height=34,
            style=ft.ButtonStyle(
                color="#059669",
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_SM),
                padding=ft.Padding(10, 4, 10, 4),
            ),
            tooltip="Mark all students present",
            on_click=self.handle_mark_all_present,
        )

        self.mark_all_absent_btn = ft.OutlinedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.REMOVE_DONE, size=14, color="#DC2626"),
                    ft.Text("All Absent (✗)", size=12, weight=ft.FontWeight.W_500),
                ],
                spacing=4,
            ),
            height=34,
            style=ft.ButtonStyle(
                color="#DC2626",
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_SM),
                padding=ft.Padding(10, 4, 10, 4),
            ),
            tooltip="Mark all students absent",
            on_click=self.handle_mark_all_absent,
        )

        self.invert_marks_btn = ft.OutlinedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.SWAP_HORIZ, size=14, color=AppTheme.TEXT_SECONDARY),
                    ft.Text("Invert (⇄)", size=12, weight=ft.FontWeight.W_500),
                ],
                spacing=4,
            ),
            height=34,
            style=ft.ButtonStyle(
                color=AppTheme.TEXT_SECONDARY,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_SM),
                padding=ft.Padding(10, 4, 10, 4),
            ),
            tooltip="Invert current toggle marks",
            on_click=self.handle_invert_marks,
        )

        self.whatsapp_absent_btn = ft.OutlinedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.CAMPAIGN, size=14, color="#059669"),
                    ft.Text("WhatsApp Absent", size=12, weight=ft.FontWeight.W_500),
                ],
                spacing=4,
            ),
            height=34,
            style=ft.ButtonStyle(
                color="#059669",
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_SM),
                padding=ft.Padding(10, 4, 10, 4),
            ),
            tooltip="Send WhatsApp alert to all absent students",
            on_click=self.handle_whatsapp_absent_batch,
        )

        self.save_online_btn = ft.FilledButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.SAVE, size=15),
                    ft.Text("Save Attendance to Spreadsheet", weight=ft.FontWeight.BOLD, size=12),
                ],
                spacing=6,
            ),
            height=34,
            style=ft.ButtonStyle(
                bgcolor=AppTheme.PRIMARY,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_SM),
                padding=ft.Padding(14, 4, 14, 4),
            ),
            on_click=self.handle_save_online_attendance,
        )

        online_search_filter_row = ft.Row(
            controls=[
                self.online_search_box,
                self.online_filter_dropdown,
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        online_actions_row = ft.Row(
            controls=[
                ft.Row(
                    controls=[
                        self.mark_all_present_btn,
                        self.mark_all_absent_btn,
                        self.invert_marks_btn,
                        self.whatsapp_absent_btn,
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                self.save_online_btn,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        online_toolbar = ft.Column(
            controls=[
                online_search_filter_row,
                online_actions_row,
            ],
            spacing=8,
        )

        self.online_table = ft.DataTable(
            columns=self._build_online_table_columns(),
            rows=[],
            heading_row_color=AppTheme.SURFACE_VARIANT,
            heading_row_height=42,
            data_row_min_height=48,
            border=ft.Border.all(1, AppTheme.BORDER),
            border_radius=AppTheme.RADIUS_MD,
            vertical_lines=ft.BorderSide(0.5, AppTheme.BORDER),
            horizontal_lines=ft.BorderSide(0.5, AppTheme.BORDER),
        )

        self.online_table_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[self.online_table],
                        scroll=ft.ScrollMode.AUTO,
                    )
                ],
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            expand=True,
        )

        online_session_header = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Row(
                                    controls=[
                                        self.prev_date_btn,
                                        self.date_field,
                                        self.next_date_btn,
                                        self.datepicker_btn,
                                        self.today_btn,
                                    ],
                                    spacing=2,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                            ),
                            self.date_weekday_text,
                            self.session_badge,
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.ANALYTICS_OUTLINED, size=15, color=AppTheme.PRIMARY),
                                self.live_attendance_rate_chip,
                                ft.Container(width=4),
                                ft.Icon(ft.Icons.PEOPLE_ALT, size=15, color=AppTheme.TEXT_SECONDARY),
                                self.enrolled_count_badge,
                                ft.Container(width=4),
                                self.present_count_text,
                                ft.Text("•", color=AppTheme.TEXT_MUTED),
                                self.absent_count_text,
                            ],
                            spacing=6,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        bgcolor=AppTheme.SURFACE_VARIANT,
                        padding=ft.Padding(10, 5, 10, 5),
                        border_radius=AppTheme.RADIUS_MD,
                        border=ft.Border.all(1, AppTheme.BORDER),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=ft.Padding(12, 6, 12, 6),
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        online_status_footer = online_session_header  # Preserved reference

        self.online_panel = ft.Column(
            controls=[
                online_session_header,
                online_toolbar,
                self.online_table_container,
            ],
            spacing=10,
            expand=True,
            visible=True,
            animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )

        # ══════════════════════════════════════════════════════════════════════
        # 4B. TAB 1: OFFLINE ATTENDANCE REGISTER & SCANNER PANEL
        # ══════════════════════════════════════════════════════════════════════
        self.offline_panel = self._build_offline_panel()


        # ══════════════════════════════════════════════════════════════════════
        # 5. TAB 1: BATCH MATRIX SPREADSHEET PANEL
        # ══════════════════════════════════════════════════════════════════════
        self.matrix_stats_text = ft.Text(
            "Overall Attendance: 0.0%",
            size=AppTheme.SIZE_BODY,
            weight=ft.FontWeight.BOLD,
            color=AppTheme.PRIMARY,
        )

        self.matrix_search_box = ft.TextField(
            hint_text="Search matrix by name or roll no...",
            prefix_icon=ft.Icons.SEARCH,
            border_radius=AppTheme.RADIUS_MD,
            width=260,
            height=38,
            text_size=AppTheme.SIZE_BODY,
            content_padding=ft.Padding(10, 6, 10, 6),
            on_change=self._handle_matrix_search_change,
        )

        self.matrix_health_dropdown = ft.Dropdown(
            label="Health Filter",
            value="ALL",
            width=160,
            height=38,
            border_radius=AppTheme.RADIUS_MD,
            content_padding=ft.Padding(8, 4, 8, 4),
            options=[
                ft.dropdown.Option("ALL", "All Healths"),
                ft.dropdown.Option("CRITICAL", "Critical (< 60%)"),
                ft.dropdown.Option("AVERAGE", "Average (60-74%)"),
                ft.dropdown.Option("GOOD", "Good (75-84%)"),
                ft.dropdown.Option("EXCELLENT", "Excellent (>= 85%)"),
            ],
            on_select=self._handle_matrix_health_change,
        )

        matrix_top_row = ft.Row(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.TABLE_CHART, size=18, color=AppTheme.PRIMARY),
                        self.matrix_stats_text,
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    controls=[
                        self.matrix_search_box,
                        self.matrix_health_dropdown,
                        self.export_excel_btn,
                        self.export_pdf_btn,
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    wrap=True,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            wrap=True,
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
            heading_row_height=42,
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
                        "Use Daily Marking or Upload an Offline Scan to record class sessions.",
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

        matrix_legend_row = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text("Legend: ", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_SECONDARY),
                    ft.Container(content=ft.Text("P = Present", size=10, weight=ft.FontWeight.BOLD, color="#059669"), bgcolor="#ECFDF5", padding=ft.Padding(6, 2, 6, 2), border_radius=4),
                    ft.Container(content=ft.Text("A = Absent", size=10, weight=ft.FontWeight.BOLD, color="#DC2626"), bgcolor="#FEF2F2", padding=ft.Padding(6, 2, 6, 2), border_radius=4),
                    ft.Container(content=ft.Text("— = Unmarked", size=10, color=AppTheme.TEXT_MUTED), bgcolor=AppTheme.SURFACE_VARIANT, padding=ft.Padding(6, 2, 6, 2), border_radius=4),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(12, 6, 12, 6),
            bgcolor=AppTheme.SURFACE,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        self.matrix_panel = ft.Column(
            controls=[
                matrix_top_row,
                matrix_legend_row,
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
            animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )

        # ══════════════════════════════════════════════════════════════════════
        # 6. TAB 2: DEFAULTERS & STUDENT HEALTH ANALYTICS
        # ══════════════════════════════════════════════════════════════════════
        self.health_search_box = ft.TextField(
            hint_text="Search students by name, contact, roll no...",
            prefix_icon=ft.Icons.SEARCH,
            border_radius=AppTheme.RADIUS_MD,
            width=280,
            height=38,
            text_size=AppTheme.SIZE_BODY,
            content_padding=ft.Padding(10, 6, 10, 6),
            on_change=self._handle_health_search_change,
        )

        self.health_filter_dropdown = ft.Dropdown(
            label="Health Bracket",
            value="ALL",
            width=180,
            height=38,
            border_radius=AppTheme.RADIUS_MD,
            content_padding=ft.Padding(8, 4, 8, 4),
            options=[
                ft.dropdown.Option("ALL", "All Students"),
                ft.dropdown.Option("CRITICAL", "Critical Defaulters (< 60%)"),
                ft.dropdown.Option("AVERAGE", "Average (60% - 74%)"),
                ft.dropdown.Option("GOOD", "Good (75% - 84%)"),
                ft.dropdown.Option("EXCELLENT", "Excellent (>= 85%)"),
            ],
            on_select=self._handle_health_filter_change,
        )

        self.whatsapp_defaulters_btn = ft.OutlinedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.CAMPAIGN, size=14, color="#DC2626"),
                    ft.Text("WhatsApp Defaulters (<60%)", size=AppTheme.SIZE_CAPTION),
                ],
                spacing=4,
            ),
            height=38,
            style=ft.ButtonStyle(
                color="#DC2626",
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
            ),
            tooltip="Send WhatsApp attendance warning notice to all critical defaulters (< 60%)",
            on_click=self.handle_whatsapp_defaulters_batch,
        )

        health_header_row = ft.Row(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.PERSON_SEARCH, size=18, color=AppTheme.PRIMARY),
                        ft.Text(
                            "Student Attendance Health & Chronic Absentee Roster",
                            size=AppTheme.SIZE_BODY,
                            weight=ft.FontWeight.BOLD,
                            color=AppTheme.TEXT_PRIMARY,
                        ),
                    ],
                    spacing=6,
                ),
                ft.Row(
                    controls=[
                        self.health_search_box,
                        self.health_filter_dropdown,
                        self.whatsapp_defaulters_btn,
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    wrap=True,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            wrap=True,
        )

        self.health_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("S.No", weight=ft.FontWeight.BOLD, size=11), numeric=True),
                ft.DataColumn(ft.Text("Candidate No", weight=ft.FontWeight.BOLD, size=11)),
                ft.DataColumn(ft.Text("Student Name", weight=ft.FontWeight.BOLD, size=11)),
                ft.DataColumn(ft.Text("Contact Mobile", weight=ft.FontWeight.BOLD, size=11)),
                ft.DataColumn(ft.Text("Sessions Attended", weight=ft.FontWeight.BOLD, size=11), numeric=True),
                ft.DataColumn(ft.Text("Sessions Missed", weight=ft.FontWeight.BOLD, size=11), numeric=True),
                ft.DataColumn(ft.Text("Attendance Rate", weight=ft.FontWeight.BOLD, size=11)),
                ft.DataColumn(ft.Text("Health Status", weight=ft.FontWeight.BOLD, size=11)),
                ft.DataColumn(ft.Text("Pending Balance", weight=ft.FontWeight.BOLD, size=11)),
            ],
            rows=[],
            heading_row_color=AppTheme.SURFACE_VARIANT,
            heading_row_height=42,
            data_row_min_height=46,
            border=ft.Border.all(1, AppTheme.BORDER),
            border_radius=AppTheme.RADIUS_MD,
            vertical_lines=ft.BorderSide(0.5, AppTheme.BORDER),
            horizontal_lines=ft.BorderSide(0.5, AppTheme.BORDER),
        )

        self.health_table_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[self.health_table],
                        scroll=ft.ScrollMode.AUTO,
                    )
                ],
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            expand=True,
        )

        self.health_panel = ft.Column(
            controls=[
                health_header_row,
                self.health_table_container,
            ],
            spacing=10,
            expand=True,
            visible=False,
            animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )

        # ══════════════════════════════════════════════════════════════════════
        # 7. ASSEMBLE CONTENT
        # ══════════════════════════════════════════════════════════════════════
        self.active_batch_workspace = ft.Column(
            controls=[
                self.active_batch_header_bar,
                self.kpi_cards_container,
                self.online_panel,
                self.offline_panel,
                self.matrix_panel,
                self.health_panel,
            ],
            spacing=AppTheme.PAD_MD,
            expand=True,
            visible=False,
            animate_opacity=ft.Animation(350, ft.AnimationCurve.EASE_OUT),
        )

        self.content = ft.Column(
            controls=[
                header_row,
                self.batch_selection_card,
                self.active_batch_workspace,
            ],
            spacing=AppTheme.PAD_MD,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

    def _build_online_table_columns(self) -> List[ft.DataColumn]:
        """Constructs online attendance table columns based on system settings."""
        cols = [
            ft.DataColumn(ft.Text("S.No", weight=ft.FontWeight.BOLD, size=11), numeric=True),
            ft.DataColumn(ft.Text("Candidate No", weight=ft.FontWeight.BOLD, size=11)),
            ft.DataColumn(ft.Text("Student Details", weight=ft.FontWeight.BOLD, size=11)),
        ]
        if self.attendance_settings.get("show_admission_date", False):
            cols.append(ft.DataColumn(ft.Text("Admission Date", weight=ft.FontWeight.BOLD, size=11)))
        if self.attendance_settings.get("show_contact_number", True):
            cols.append(ft.DataColumn(ft.Text("Contact Mobile", weight=ft.FontWeight.BOLD, size=11)))
        if self.attendance_settings.get("show_pending_fees", True):
            cols.append(ft.DataColumn(ft.Text("Pending Fees", weight=ft.FontWeight.BOLD, size=11)))
        cols.append(ft.DataColumn(ft.Text("Mark Attendance (Default: Absent)", weight=ft.FontWeight.BOLD, size=11)))
        return cols

    def _build_offline_panel(self) -> ft.Column:
        """Constructs the Step 3B / Step 4 Offline Attendance workspace panel."""
        header_banner = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.DESCRIPTION, size=20, color=AppTheme.PRIMARY),
                    ft.Column(
                        controls=[
                            ft.Text("Offline Attendance Management Hub", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD),
                            ft.Text(
                                "Generate multi-day digital registers or printable paper sheets, and reconcile marked records into the ledger.",
                                size=AppTheme.SIZE_CAPTION,
                                color=AppTheme.TEXT_MUTED,
                            ),
                        ],
                        spacing=1,
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=ft.Padding(12, 10, 12, 10),
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        # Card 1: Multi-day Digital Register (.xlsx)
        digital_card = HoverCard(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Icon(ft.Icons.TABLE_VIEW, size=24, color="#059669"),
                                bgcolor="#ECFDF5",
                                padding=8,
                                border_radius=AppTheme.RADIUS_MD,
                            ),
                            ft.Column(
                                controls=[
                                    ft.Row(
                                        controls=[
                                            ft.Text("Digital Excel Register", size=15, weight=ft.FontWeight.BOLD),
                                            StatusBadge("RECOMMENDED", variant="success", size=10),
                                        ],
                                        spacing=6,
                                    ),
                                    ft.Text("Automated formula calculation with safe, non-destructive import", size=11, color=AppTheme.TEXT_MUTED),
                                ],
                                spacing=2,
                            ),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    ft.Text("Select Period Duration:", size=11, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_SECONDARY),
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Text("8 Days", size=11, weight=ft.FontWeight.W_500, color="#059669"),
                                bgcolor="#ECFDF5",
                                padding=ft.Padding(10, 6, 10, 6),
                                border_radius=AppTheme.RADIUS_PILL,
                                border=ft.Border.all(1, "#A7F3D0"),
                            ),
                            ft.Container(
                                content=ft.Text("15 Days", size=11, weight=ft.FontWeight.W_500, color="#059669"),
                                bgcolor="#ECFDF5",
                                padding=ft.Padding(10, 6, 10, 6),
                                border_radius=AppTheme.RADIUS_PILL,
                                border=ft.Border.all(1, "#A7F3D0"),
                            ),
                            ft.Container(
                                content=ft.Text("30 Days (1 Month)", size=11, weight=ft.FontWeight.W_500, color="#059669"),
                                bgcolor="#ECFDF5",
                                padding=ft.Padding(10, 6, 10, 6),
                                border_radius=AppTheme.RADIUS_PILL,
                                border=ft.Border.all(1, "#A7F3D0"),
                            ),
                            ft.Container(
                                content=ft.Text("60 Days (2 Months)", size=11, weight=ft.FontWeight.W_500, color="#059669"),
                                bgcolor="#ECFDF5",
                                padding=ft.Padding(10, 6, 10, 6),
                                border_radius=AppTheme.RADIUS_PILL,
                                border=ft.Border.all(1, "#A7F3D0"),
                            ),
                        ],
                        spacing=6,
                        wrap=True,
                    ),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.CHECK_CIRCLE, size=14, color="#059669"),
                                ft.Text("Formulas: =COUNTIF Present • =COUNTA Total • % Attendance", size=11, color=AppTheme.TEXT_SECONDARY),
                            ],
                            spacing=6,
                        ),
                        bgcolor=AppTheme.SURFACE_VARIANT,
                        padding=ft.Padding(8, 6, 8, 6),
                        border_radius=AppTheme.RADIUS_SM,
                    ),
                    ft.Container(height=4),
                    ft.Row(
                        controls=[
                            ft.FilledButton(
                                content=ft.Row(
                                    controls=[
                                        ft.Icon(ft.Icons.FILE_DOWNLOAD, size=15),
                                        ft.Text("Generate Digital Register (.xlsx)", size=12, weight=ft.FontWeight.BOLD),
                                    ],
                                    spacing=6,
                                ),
                                height=40,
                                style=ft.ButtonStyle(
                                    bgcolor="#059669",
                                    color=ft.Colors.WHITE,
                                    shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                                ),
                                on_click=self.handle_open_offline_register,
                            ),
                            ft.OutlinedButton(
                                content=ft.Row(
                                    controls=[
                                        ft.Icon(ft.Icons.FILE_UPLOAD, size=15),
                                        ft.Text("Upload & Reconcile Register (.xlsx)", size=12),
                                    ],
                                    spacing=6,
                                ),
                                height=40,
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                                ),
                                on_click=self.handle_open_offline_upload,
                            ),
                        ],
                        spacing=10,
                        wrap=True,
                    ),
                ],
                spacing=10,
            ),
            padding=AppTheme.PAD_MD,
            border_radius=AppTheme.RADIUS_LG,
            expand=True,
            hover_scale=1.015,
        )

        # Card 2: Physical Printout & OCR Sheet Scanner
        paper_card = HoverCard(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Icon(ft.Icons.DOCUMENT_SCANNER, size=24, color=AppTheme.PRIMARY),
                                bgcolor=AppTheme.PRIMARY_LIGHT,
                                padding=8,
                                border_radius=AppTheme.RADIUS_MD,
                            ),
                            ft.Column(
                                controls=[
                                    ft.Text("Paper Format & Optical Scanner (OCR)", size=15, weight=ft.FontWeight.BOLD),
                                    ft.Text("Print physical attendance sheets and scan filled photo sheets via OCR", size=11, color=AppTheme.TEXT_MUTED),
                                ],
                                spacing=2,
                            ),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    ft.Text("Customizable Sheet Columns:", size=11, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_SECONDARY),
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Text("1 Date Column", size=11, weight=ft.FontWeight.W_500, color=AppTheme.PRIMARY),
                                bgcolor=AppTheme.PRIMARY_LIGHT,
                                padding=ft.Padding(10, 6, 10, 6),
                                border_radius=AppTheme.RADIUS_PILL,
                                border=ft.Border.all(1, "#BFDBFE"),
                            ),
                            ft.Container(
                                content=ft.Text("2 Date Columns", size=11, weight=ft.FontWeight.W_500, color=AppTheme.PRIMARY),
                                bgcolor=AppTheme.PRIMARY_LIGHT,
                                padding=ft.Padding(10, 6, 10, 6),
                                border_radius=AppTheme.RADIUS_PILL,
                                border=ft.Border.all(1, "#BFDBFE"),
                            ),
                            ft.Container(
                                content=ft.Text("3 Date Columns", size=11, weight=ft.FontWeight.W_500, color=AppTheme.PRIMARY),
                                bgcolor=AppTheme.PRIMARY_LIGHT,
                                padding=ft.Padding(10, 6, 10, 6),
                                border_radius=AppTheme.RADIUS_PILL,
                                border=ft.Border.all(1, "#BFDBFE"),
                            ),
                            ft.Container(
                                content=ft.Text("5 Date Columns", size=11, weight=ft.FontWeight.W_500, color=AppTheme.PRIMARY),
                                bgcolor=AppTheme.PRIMARY_LIGHT,
                                padding=ft.Padding(10, 6, 10, 6),
                                border_radius=AppTheme.RADIUS_PILL,
                                border=ft.Border.all(1, "#BFDBFE"),
                            ),
                        ],
                        spacing=6,
                        wrap=True,
                    ),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.DOCUMENT_SCANNER, size=14, color=AppTheme.PRIMARY),
                                ft.Text("Optical OCR: Detects check marks & roll numbers from phone photos (JPG/PNG)", size=11, color=AppTheme.TEXT_SECONDARY),
                            ],
                            spacing=6,
                        ),
                        bgcolor=AppTheme.SURFACE_VARIANT,
                        padding=ft.Padding(8, 6, 8, 6),
                        border_radius=AppTheme.RADIUS_SM,
                    ),
                    ft.Container(height=4),
                    ft.Row(
                        controls=[
                            ft.FilledButton(
                                content=ft.Row(
                                    controls=[
                                        ft.Icon(ft.Icons.PRINT, size=15),
                                        ft.Text("Print Paper Format", size=12, weight=ft.FontWeight.BOLD),
                                    ],
                                    spacing=6,
                                ),
                                height=40,
                                style=ft.ButtonStyle(
                                    bgcolor=AppTheme.PRIMARY,
                                    color=ft.Colors.WHITE,
                                    shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                                ),
                                on_click=self.handle_open_print_format,
                            ),
                            ft.OutlinedButton(
                                content=ft.Row(
                                    controls=[
                                        ft.Icon(ft.Icons.UPLOAD_FILE, size=15),
                                        ft.Text("Upload OCR Scan (JPG/PNG)", size=12),
                                    ],
                                    spacing=6,
                                ),
                                height=40,
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                                ),
                                on_click=self.handle_open_ocr_upload,
                            ),
                        ],
                        spacing=10,
                        wrap=True,
                    ),
                ],
                spacing=10,
            ),
            padding=AppTheme.PAD_MD,
            border_radius=AppTheme.RADIUS_LG,
            expand=True,
            hover_scale=1.015,
        )

        return ft.Column(
            controls=[
                header_banner,
                ft.Row(
                    controls=[digital_card, paper_card],
                    spacing=AppTheme.PAD_MD,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
            ],
            spacing=AppTheme.PAD_MD,
            expand=True,
            visible=False,
            animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )

    # ══════════════════════════════════════════════════════════════════════
    # KPI BUILDER
    # ══════════════════════════════════════════════════════════════════════
    def _build_kpi_cards(self) -> ft.Container:
        """Constructs 4 modern responsive top metric cards with HoverCard tactile effects."""
        def _make_card(title: str, val_ctrl: ft.Control, sub_ctrl: ft.Control, icon: str, icon_col: str, icon_bg: str) -> ft.Container:
            return HoverCard(
                content=ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Icon(icon, size=22, color=icon_col),
                            bgcolor=icon_bg,
                            padding=10,
                            border_radius=AppTheme.RADIUS_MD,
                        ),
                        ft.Column(
                            controls=[
                                ft.Text(title, size=11, weight=ft.FontWeight.W_600, color=AppTheme.TEXT_SECONDARY),
                                val_ctrl,
                                sub_ctrl,
                            ],
                            spacing=1,
                            tight=True,
                        ),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding(14, 12, 14, 12),
                border_radius=AppTheme.RADIUS_LG,
                expand=True,
                hover_scale=1.02,
            )

        return ft.Container(
            content=ft.Row(
                controls=[
                    _make_card("Today's Session", self.kpi_session_status_text, self.kpi_session_sub_text, ft.Icons.EVENT_AVAILABLE, "#059669", "#ECFDF5"),
                    _make_card("Batch Attendance", self.kpi_overall_rate_text, self.kpi_overall_sub_text, ft.Icons.ANALYTICS, AppTheme.PRIMARY, AppTheme.PRIMARY_LIGHT),
                    _make_card("Sessions Conducted", self.kpi_total_sessions_text, self.kpi_total_sessions_sub_text, ft.Icons.CALENDAR_MONTH, "#4338CA", "#EEF2FF"),
                    _make_card("Critical Defaulters", self.kpi_defaulters_text, self.kpi_defaulters_sub_text, ft.Icons.WARNING_AMBER_ROUNDED, "#DC2626", "#FEF2F2"),
                ],
                spacing=AppTheme.PAD_SM,
            ),
            margin=ft.Margin(0, 0, 0, 2),
        )

    # ══════════════════════════════════════════════════════════════════════
    # FLET LIFECYCLE & PAGE DISPATCH
    # ══════════════════════════════════════════════════════════════════════
    @property
    def safe_page(self) -> Optional[ft.Page]:
        try:
            return getattr(self, "_root_page", None) or self.page or getattr(self, "_page", None)
        except (RuntimeError, AttributeError):
            return None

    def did_mount(self) -> None:
        """Lifecycle hook invoked automatically by Flet when mounted into page tree."""
        self.load_data()

    def _safe_update(self) -> None:
        """Explicitly dispatches updates to sub-controls and parent view."""
        for ctrl in [
            getattr(self, "kpi_cards_container", None),
            getattr(self, "batch_dropdown", None),
            getattr(self, "date_field", None),
            getattr(self, "online_panel", None),
            getattr(self, "offline_panel", None),
            getattr(self, "matrix_panel", None),
            getattr(self, "health_panel", None),
            getattr(self, "online_table", None),
            getattr(self, "matrix_table", None),
            getattr(self, "health_table", None),
        ]:
            if ctrl is not None:
                try:
                    ctrl.update()
                except Exception:
                    pass

        try:
            self.update()
        except Exception:
            pass

        p = self.safe_page
        if p and hasattr(p, "update"):
            try:
                p.update()
            except Exception:
                pass

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
            try:
                p.update()
            except Exception:
                pass

    # ══════════════════════════════════════════════════════════════════════
    # SUBTAB SWITCHING
    # ══════════════════════════════════════════════════════════════════════
    def _set_subtab(self, index: int) -> None:
        self.active_subtab_index = index
        self.online_panel.visible = (index == 0)
        self.offline_panel.visible = (index == 1)
        self.matrix_panel.visible = (index == 2)
        self.health_panel.visible = (index == 3)

        buttons = [self.tab_online_btn, self.tab_offline_btn, self.tab_matrix_btn, self.tab_health_btn]
        for idx, btn in enumerate(buttons):
            if idx == index:
                btn.style.bgcolor = AppTheme.PRIMARY
                btn.style.color = ft.Colors.WHITE
                if btn.content and hasattr(btn.content, "controls"):
                    btn.content.controls[0].color = ft.Colors.WHITE
                    btn.content.controls[1].weight = ft.FontWeight.BOLD
                    btn.content.controls[1].color = ft.Colors.WHITE
            else:
                btn.style.bgcolor = ft.Colors.TRANSPARENT
                btn.style.color = AppTheme.TEXT_SECONDARY
                if btn.content and hasattr(btn.content, "controls"):
                    btn.content.controls[0].color = AppTheme.TEXT_SECONDARY
                    btn.content.controls[1].weight = ft.FontWeight.NORMAL
                    btn.content.controls[1].color = AppTheme.TEXT_SECONDARY

        self._safe_update()

    # ══════════════════════════════════════════════════════════════════════
    # DATA LOADING & RECONCILIATION
    # ══════════════════════════════════════════════════════════════════════
    def load_data(self) -> None:
        """Loads all batches and populates batch selector and active view."""
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
            else:
                self._safe_update()

        except Exception as exc:
            LogService.error(f"Failed to load attendance batches: {exc}", context="AttendanceHome")
            self._show_toast("Failed to load batch list.", is_error=True)

    def load_batch_attendance(self, batch_id: int) -> None:
        """Loads enrolled students, existing session for date, and multi-session matrix."""
        try:
            self.selected_batch_id = batch_id
            self.enrolled_students = self.controller.get_enrolled_students(batch_id)
            self.enrolled_count_badge.value = f"{len(self.enrolled_students)} Enrolled"
            self.attendance_settings = self.controller.get_attendance_settings()
            self.online_table.columns = self._build_online_table_columns()

            # Update batch metadata chips
            if not self.batches:
                try:
                    self.batches = self.controller.get_batches()
                except Exception:
                    pass
            batch_info = None
            for b in self.batches:
                if b["id"] == batch_id:
                    batch_info = b
                    break
            if batch_info and hasattr(self, "batch_meta_container"):
                self.batch_course_chip.value = f"Course: {batch_info.get('course_name', '—')}"
                self.batch_timing_chip.value = f"Schedule: {batch_info.get('timing', '—')}"
                self.batch_enrolled_chip.value = f"Enrolled: {len(self.enrolled_students)}"
                self.batch_meta_container.visible = True

            if hasattr(self, "active_batch_title_text") and batch_info:
                b_name = batch_info.get("batch_name", f"Batch #{batch_id}")
                self.active_batch_title_text.value = f"Batch: {b_name}"

            # Two-Stage View: Transition from batch selection to active batch workspace
            if hasattr(self, "batch_selection_card") and hasattr(self, "active_batch_workspace"):
                self.batch_selection_card.visible = False
                self.active_batch_workspace.visible = True
                self.active_batch_workspace.opacity = 1.0

            # Format weekday string for date display
            try:
                d_obj = datetime.strptime(self.selected_date, "%Y-%m-%d")
                weekday_str = d_obj.strftime("%A, %d %b %Y")
            except Exception:
                weekday_str = self.selected_date
            if hasattr(self, "date_weekday_text"):
                self.date_weekday_text.value = weekday_str

            # Check if an attendance session exists for selected date
            existing_session = self.controller.get_session(batch_id, self.selected_date)
            self.existing_session_marks.clear()
            if existing_session:
                for rec in existing_session.records:
                    self.existing_session_marks[rec.student_id] = rec.status
                if hasattr(self, "session_badge"):
                    self.session_badge.content = ft.Text(f"🟢 Saved in Ledger ({existing_session.total_present}/{len(self.enrolled_students)} Present)", size=10, weight=ft.FontWeight.BOLD, color="#059669")
                    self.session_badge.bgcolor = "#ECFDF5"
            else:
                if hasattr(self, "session_badge"):
                    self.session_badge.content = ft.Text("🟡 Unsaved / New Session", size=10, weight=ft.FontWeight.BOLD, color="#D97706")
                    self.session_badge.bgcolor = "#FFFBEB"

            # Populate Online Table
            self._build_online_table_rows(self.existing_session_marks)

            # Update Live Attendance Rate Chip
            tot = len(self.enrolled_students)
            p_cnt = sum(1 for sw in self.student_toggles.values() if sw.value)
            pct = round((p_cnt / tot) * 100, 1) if tot > 0 else 0.0
            if hasattr(self, "live_attendance_rate_chip"):
                self.live_attendance_rate_chip.value = f"{pct}% Present Rate"

            # Update Absentees button count
            a_cnt = tot - p_cnt
            if hasattr(self, "whatsapp_absent_btn") and len(self.whatsapp_absent_btn.content.controls) > 1:
                self.whatsapp_absent_btn.content.controls[1].value = f"WhatsApp Absent ({a_cnt})"

            # Load and populate Multi-Session Matrix
            self.current_matrix = self.controller.get_batch_matrix(batch_id)
            self._build_matrix_table(self.current_matrix)

            # Populate Tab 2: Defaulters & Student Health
            self._build_health_table(self.current_matrix)

            # Update KPI cards
            self._update_kpi_cards(existing_session, self.current_matrix)

            self._safe_update()

        except Exception as exc:
            LogService.error(f"Failed to load batch attendance: {exc}", context="AttendanceHome")
            self._show_toast(f"Failed to load attendance for batch {batch_id}", is_error=True)

    def _handle_back_to_batches(self, e: Any = None) -> None:
        """Transitions view back to batch selection card with smooth animation."""
        if hasattr(self, "active_batch_workspace") and hasattr(self, "batch_selection_card"):
            self.active_batch_workspace.visible = False
            self.batch_selection_card.visible = True
            self.batch_selection_card.opacity = 1.0
        self.selected_batch_id = None
        if hasattr(self, "batch_dropdown"):
            self.batch_dropdown.value = None
        self._safe_update()

    def _update_kpi_cards(self, session: Optional[AttendanceSessionDTO], matrix: Optional[BatchAttendanceMatrixDTO]) -> None:
        """Computes and updates top metric cards."""
        tot_enrolled = len(self.enrolled_students)

        # 1. Today's Session Card
        if session and session.total_enrolled > 0:
            self.kpi_session_status_text.value = f"{session.total_present} / {tot_enrolled} Present"
            pct = round((session.total_present / tot_enrolled) * 100, 1) if tot_enrolled > 0 else 0.0
            self.kpi_session_sub_text.value = f"{pct}% marked for {self.selected_date}"
            self.kpi_session_status_text.color = "#059669"
        else:
            p_cnt = sum(1 for sw in self.student_toggles.values() if sw.value)
            if p_cnt > 0:
                self.kpi_session_status_text.value = f"{p_cnt} / {tot_enrolled} Unsaved"
                self.kpi_session_sub_text.value = "Click 'Save Attendance' to persist"
                self.kpi_session_status_text.color = AppTheme.WARNING
            else:
                self.kpi_session_status_text.value = "Unmarked Today"
                self.kpi_session_sub_text.value = f"Date: {self.selected_date}"
                self.kpi_session_status_text.color = AppTheme.TEXT_MUTED

        # 2 & 3. Batch Overall & Sessions Conducted
        if matrix:
            self.kpi_overall_rate_text.value = f"{matrix.overall_attendance_rate}%"
            num_sess = len(matrix.session_dates)
            self.kpi_total_sessions_text.value = f"{num_sess} Sessions"
            self.kpi_total_sessions_sub_text.value = f"Recorded for this batch"

            # 4. Defaulters Alert (<60%)
            critical_students = sum(1 for r in matrix.rows if r.health_status == AttendanceHealth.CRITICAL.value or r.attendance_percentage < 60.0)
            if critical_students > 0:
                self.kpi_defaulters_text.value = f"{critical_students} Students"
                self.kpi_defaulters_text.color = "#DC2626"
                self.kpi_defaulters_sub_text.value = "Urgent: Attendance below 60%"
            else:
                self.kpi_defaulters_text.value = "0 Defaulters"
                self.kpi_defaulters_text.color = AppTheme.SUCCESS
                self.kpi_defaulters_sub_text.value = "All students >= 60% attendance"
        else:
            self.kpi_overall_rate_text.value = "0.0%"
            self.kpi_total_sessions_text.value = "0 Sessions"
            self.kpi_defaulters_text.value = "0 Students"

    # ══════════════════════════════════════════════════════════════════════
    # TAB 0: ONLINE ATTENDANCE TABLE BUILDER
    # ══════════════════════════════════════════════════════════════════════
    def _build_online_table_rows(self, existing_marks: Dict[int, str]) -> None:
        """Builds interactive student rows with switches, avatar initials, and fees badges."""
        self.student_toggles.clear()
        p_count = 0
        a_count = 0

        # First populate toggle state for all enrolled students
        for st in self.enrolled_students:
            is_present = (existing_marks.get(st.student_id) == "PRESENT")
            if is_present:
                p_count += 1
            else:
                a_count += 1

            sw = ft.Switch(
                value=is_present,
                active_color="#059669",
                scale=0.9,
                tooltip="Toggle: ON = Present, OFF = Absent",
                on_change=self._on_toggle_changed,
            )
            self.student_toggles[st.student_id] = sw

        self.present_count_text.value = f"{p_count} Present"
        self.absent_count_text.value = f"{a_count} Absent"

        self._render_filtered_online_rows()

    def _render_filtered_online_rows(self) -> None:
        """Filters and renders online table rows according to active search query and filter chip."""
        rows: List[ft.DataRow] = []
        q = self.online_search_query.strip().lower()
        filter_mode = self.online_filter_status

        show_adm_date = self.attendance_settings.get("show_admission_date", False)
        show_mobile = self.attendance_settings.get("show_contact_number", True)
        show_fees = self.attendance_settings.get("show_pending_fees", True)

        filtered_students = []
        for st in self.enrolled_students:
            # 1. Search Query filter
            if q:
                name_match = q in st.student_name.lower()
                num_match = q in (st.candidate_number or "").lower()
                mob_match = q in (st.mobile_number or "").lower()
                if not (name_match or num_match or mob_match):
                    continue

            # 2. Status filter
            sw = self.student_toggles.get(st.student_id)
            is_p = sw.value if sw else False

            if filter_mode == "PRESENT" and not is_p:
                continue
            if filter_mode == "ABSENT" and is_p:
                continue
            if filter_mode == "DUES" and st.pending_fees <= 0:
                continue

            filtered_students.append(st)

        for idx, st in enumerate(filtered_students, 1):
            sw = self.student_toggles[st.student_id]
            is_present = sw.value

            # Student Photo / Avatar
            has_photo = bool(st.photo_path and is_valid_image_file(st.photo_path))
            if has_photo:
                avatar_content = ft.Image(
                    src=st.photo_path,
                    width=32,
                    height=32,
                    fit="cover",
                    border_radius=AppTheme.RADIUS_PILL,
                )
            else:
                parts = st.student_name.strip().split()
                initials = (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper() if parts else "ST"
                avatar_content = ft.Text(initials, size=11, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY)

            avatar = ft.Container(
                content=avatar_content,
                bgcolor=AppTheme.PRIMARY_LIGHT if not has_photo else AppTheme.BACKGROUND,
                width=32,
                height=32,
                border_radius=16,
                border=ft.Border.all(1, AppTheme.PRIMARY if has_photo else AppTheme.BORDER),
                alignment=ft.Alignment(0, 0),
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            )

            student_cell = ft.Row(
                controls=[
                    avatar,
                    ft.Column(
                        controls=[
                            ft.Text(st.student_name, size=12, weight=ft.FontWeight.BOLD),
                            ft.Text(st.candidate_number or "No Reg ID", size=10, color=AppTheme.TEXT_MUTED),
                        ],
                        spacing=1,
                        tight=True,
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

            # Optional Contact Mobile with quick WhatsApp chat
            quick_chat = ft.IconButton(
                icon=ft.Icons.CHAT,
                icon_size=15,
                icon_color="#25D366",
                tooltip=f"Open WhatsApp Chat with {st.student_name}",
                visible=bool(st.mobile_number),
                on_click=lambda _, mob=st.mobile_number, n=st.student_name: self._open_whatsapp_chat(mob, n),
            )
            mobile_cell = ft.Row(
                controls=[
                    ft.Text(st.mobile_number or "—", size=11),
                    quick_chat,
                ],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

            pending_val = f"₹{st.pending_fees:,.2f}" if st.pending_fees > 0 else "Cleared ✓"
            fee_badge = ft.Container(
                content=ft.Text(
                    pending_val,
                    size=10,
                    weight=ft.FontWeight.BOLD if st.pending_fees > 0 else ft.FontWeight.NORMAL,
                    color="#DC2626" if st.pending_fees > 0 else "#059669",
                ),
                bgcolor="#FEF2F2" if st.pending_fees > 0 else "#ECFDF5",
                padding=ft.Padding(6, 2, 6, 2),
                border_radius=4,
            )

            # Far-right toggle switch + status chip + WhatsApp absentee alert
            whatsapp_alert_btn = ft.IconButton(
                icon=ft.Icons.CHECK_CIRCLE_OUTLINE if is_present else ft.Icons.NOTIFICATION_IMPORTANT,
                icon_size=16,
                icon_color="#059669" if is_present else "#DC2626",
                tooltip=f"Send Attendance Update to {st.student_name}" if is_present else f"Send Absentee Alert to {st.student_name}",
                visible=bool(st.mobile_number),
                on_click=lambda _, s=st: self._send_whatsapp_alert(s),
            )

            status_chip = ft.Container(
                content=ft.Text(
                    "PRESENT" if is_present else "ABSENT",
                    size=10,
                    weight=ft.FontWeight.BOLD,
                    color="#059669" if is_present else "#DC2626",
                ),
                bgcolor="#ECFDF5" if is_present else "#FEF2F2",
                padding=ft.Padding(8, 2, 8, 2),
                border_radius=AppTheme.RADIUS_PILL,
                data="status_chip",
            )

            toggle_cell = ft.Row(
                controls=[
                    status_chip,
                    sw,
                    whatsapp_alert_btn,
                ],
                spacing=8,
                alignment=ft.MainAxisAlignment.END,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

            cells = [
                ft.DataCell(ft.Text(str(idx), size=11)),
                ft.DataCell(ft.Text(st.candidate_number or "—", size=11, weight=ft.FontWeight.W_500)),
                ft.DataCell(student_cell),
            ]
            if show_adm_date:
                cells.append(ft.DataCell(ft.Text(st.admission_date[:10] if st.admission_date else "—", size=11)))
            if show_mobile:
                cells.append(ft.DataCell(mobile_cell))
            if show_fees:
                cells.append(ft.DataCell(fee_badge))
            cells.append(ft.DataCell(toggle_cell))

            rows.append(ft.DataRow(cells=cells))

        self.online_table.rows = rows

    def _on_toggle_changed(self, e: Optional[ft.ControlEvent]) -> None:
        """Updates present/absent tallies, status chips, and live ribbon when an individual switch is toggled."""
        p_count = sum(1 for sw in self.student_toggles.values() if sw.value)
        a_count = len(self.student_toggles) - p_count
        tot = len(self.enrolled_students)
        pct = round((p_count / tot) * 100, 1) if tot > 0 else 0.0

        self.present_count_text.value = f"{p_count} Present"
        self.absent_count_text.value = f"{a_count} Absent"

        if hasattr(self, "live_attendance_rate_chip"):
            self.live_attendance_rate_chip.value = f"{pct}% Present Rate"

        if hasattr(self, "session_badge"):
            self.session_badge.content = ft.Text("🟠 Unsaved Changes", size=10, weight=ft.FontWeight.BOLD, color="#C2410C")
            self.session_badge.bgcolor = "#FFEDD5"

        if hasattr(self, "whatsapp_absent_btn") and len(self.whatsapp_absent_btn.content.controls) > 1:
            self.whatsapp_absent_btn.content.controls[1].value = f"WhatsApp Absent ({a_count})"

        # Update status chip label and alert icon in table row (dynamically in the last cell)
        for r in self.online_table.rows:
            if not r.cells:
                continue
            cell_content = r.cells[-1].content
            if isinstance(cell_content, ft.Row):
                sw_ctrl = None
                chip = None
                wa_btn = None
                for c in cell_content.controls:
                    if isinstance(c, ft.Switch):
                        sw_ctrl = c
                    elif isinstance(c, ft.Container) and getattr(c, "data", None) == "status_chip":
                        chip = c
                    elif isinstance(c, ft.IconButton):
                        wa_btn = c
                if sw_ctrl and chip and isinstance(chip.content, ft.Text):
                    is_p = sw_ctrl.value
                    chip.content.value = "PRESENT" if is_p else "ABSENT"
                    chip.content.color = "#059669" if is_p else "#DC2626"
                    chip.bgcolor = "#ECFDF5" if is_p else "#FEF2F2"
                    if wa_btn:
                        wa_btn.icon = ft.Icons.CHECK_CIRCLE_OUTLINE if is_p else ft.Icons.NOTIFICATION_IMPORTANT
                        wa_btn.icon_color = "#059669" if is_p else "#DC2626"

        self._safe_update()

    def _handle_online_search_change(self, e: ft.ControlEvent) -> None:
        self.online_search_query = self.online_search_box.value or ""
        self._render_filtered_online_rows()
        self._safe_update()

    def _handle_online_filter_change(self, e: ft.ControlEvent) -> None:
        self.online_filter_status = self.online_filter_dropdown.value or "ALL"
        self._render_filtered_online_rows()
        self._safe_update()

    # ══════════════════════════════════════════════════════════════════════
    # TAB 1: BATCH MATRIX TABLE BUILDER
    # ══════════════════════════════════════════════════════════════════════
    def _build_matrix_table(self, matrix: Optional[BatchAttendanceMatrixDTO]) -> None:
        """Constructs multi-session matrix columns and rows for spreadsheet viewing."""
        has_sessions = bool(matrix and len(matrix.session_dates) > 0 and len(matrix.rows) > 0)
        self.matrix_scroll_row.visible = has_sessions
        self.matrix_empty_text.visible = not has_sessions

        if not matrix or not has_sessions:
            self.matrix_table.columns = self.default_matrix_columns
            self.matrix_table.rows = []
            self.matrix_stats_text.value = "Overall Attendance: 0.0%  •  0 Sessions"
            return

        self.matrix_stats_text.value = f"Overall Attendance: {matrix.overall_attendance_rate}%  •  {len(matrix.session_dates)} Sessions"

        # Dynamic Columns: Fixed metadata + Date columns + Summary metrics
        cols: List[ft.DataColumn] = [
            ft.DataColumn(ft.Text("Candidate No", weight=ft.FontWeight.BOLD, size=11)),
            ft.DataColumn(ft.Text("Student Name", weight=ft.FontWeight.BOLD, size=11)),
            ft.DataColumn(ft.Text("Mobile", weight=ft.FontWeight.BOLD, size=11)),
        ]

        for d in matrix.session_dates:
            short_d = d[5:]  # MM-DD
            cols.append(ft.DataColumn(ft.Text(short_d, weight=ft.FontWeight.BOLD, size=11), numeric=True))

        cols.extend([
            ft.DataColumn(ft.Text("Present", weight=ft.FontWeight.BOLD, size=11), numeric=True),
            ft.DataColumn(ft.Text("Absent", weight=ft.FontWeight.BOLD, size=11), numeric=True),
            ft.DataColumn(ft.Text("% Health", weight=ft.FontWeight.BOLD, size=11), numeric=True),
        ])

        self.matrix_table.columns = cols
        self._render_filtered_matrix_rows(matrix)

    def _render_filtered_matrix_rows(self, matrix: BatchAttendanceMatrixDTO) -> None:
        """Filters rows for Matrix Ledger based on search and health brackets."""
        rows: List[ft.DataRow] = []
        q = self.matrix_search_query.strip().lower()
        health_filter = self.matrix_filter_health

        for r in matrix.rows:
            # 1. Search Query filter
            if q:
                if not (q in r.student_name.lower() or q in (r.candidate_number or "").lower() or q in (r.mobile_number or "").lower()):
                    continue

            # 2. Health bracket filter
            if health_filter != "ALL":
                if r.health_status != health_filter:
                    continue

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
                    width=28,
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

        self.matrix_table.rows = rows

    def _handle_matrix_search_change(self, e: ft.ControlEvent) -> None:
        self.matrix_search_query = self.matrix_search_box.value or ""
        if self.current_matrix:
            self._render_filtered_matrix_rows(self.current_matrix)
            self._safe_update()

    def _handle_matrix_health_change(self, e: ft.ControlEvent) -> None:
        self.matrix_filter_health = self.matrix_health_dropdown.value or "ALL"
        if self.current_matrix:
            self._render_filtered_matrix_rows(self.current_matrix)
            self._safe_update()

    # ══════════════════════════════════════════════════════════════════════
    # TAB 2: DEFAULTERS & STUDENT HEALTH ANALYTICS BUILDER
    # ══════════════════════════════════════════════════════════════════════
    def _build_health_table(self, matrix: Optional[BatchAttendanceMatrixDTO]) -> None:
        """Constructs dedicated chronic absentee and health analytics table."""
        if not matrix or not matrix.rows:
            self.health_table.rows = []
            return

        rows: List[ft.DataRow] = []
        q = self.health_search_query.strip().lower()
        bracket_filter = self.health_filter_dropdown.value or "ALL"

        matching_rows = []
        for r in matrix.rows:
            if q:
                if not (q in r.student_name.lower() or q in (r.candidate_number or "").lower() or q in (r.mobile_number or "").lower()):
                    continue
            if bracket_filter != "ALL":
                if r.health_status != bracket_filter:
                    continue
            matching_rows.append(r)

        # Sort so that lowest attendance / most critical appear at the top!
        matching_rows.sort(key=lambda x: (x.attendance_percentage, -x.total_absent))

        for idx, r in enumerate(matching_rows, 1):
            h_col = HEALTH_COLORS.get(r.health_status, "#059669")
            h_bg = HEALTH_BG_COLORS.get(r.health_status, "#ECFDF5")

            status_badge = ft.Container(
                content=ft.Text(r.health_status, size=10, weight=ft.FontWeight.BOLD, color=h_col),
                bgcolor=h_bg,
                border_radius=AppTheme.RADIUS_PILL,
                padding=ft.Padding(8, 2, 8, 2),
            )

            # Mini visual rate bar
            rate_bar = ft.ProgressBar(
                value=max(0.0, min(1.0, r.attendance_percentage / 100.0)),
                color=h_col,
                bgcolor="#E2E8F0",
                height=6,
                width=80,
            )
            rate_cell = ft.Row(
                controls=[
                    ft.Text(f"{r.attendance_percentage:.1f}%", size=11, weight=ft.FontWeight.BOLD, color=h_col),
                    rate_bar,
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

            pending_val = f"₹{r.pending_fees:,.2f}" if r.pending_fees > 0 else "Cleared ✓"
            fee_badge = ft.Container(
                content=ft.Text(
                    pending_val,
                    size=10,
                    weight=ft.FontWeight.BOLD if r.pending_fees > 0 else ft.FontWeight.NORMAL,
                    color="#DC2626" if r.pending_fees > 0 else "#059669",
                ),
                bgcolor="#FEF2F2" if r.pending_fees > 0 else "#ECFDF5",
                padding=ft.Padding(6, 2, 6, 2),
                border_radius=4,
            )

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(str(idx), size=11)),
                        ft.DataCell(ft.Text(r.candidate_number or "—", size=11, weight=ft.FontWeight.W_500)),
                        ft.DataCell(ft.Text(r.student_name, size=11, weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(r.mobile_number or "—", size=11)),
                        ft.DataCell(ft.Text(str(r.total_present), size=11, weight=ft.FontWeight.BOLD, color="#059669")),
                        ft.DataCell(ft.Text(str(r.total_absent), size=11, weight=ft.FontWeight.BOLD, color="#DC2626")),
                        ft.DataCell(rate_cell),
                        ft.DataCell(status_badge),
                        ft.DataCell(fee_badge),
                    ]
                )
            )

        self.health_table.rows = rows

    def _handle_health_search_change(self, e: ft.ControlEvent) -> None:
        self.health_search_query = self.health_search_box.value or ""
        self._build_health_table(self.current_matrix)
        self._safe_update()

    def _handle_health_filter_change(self, e: ft.ControlEvent) -> None:
        self._build_health_table(self.current_matrix)
        self._safe_update()

    # ══════════════════════════════════════════════════════════════════════
    # EVENT HANDLERS & DATE STEPPERS
    # ══════════════════════════════════════════════════════════════════════
    def _handle_prev_day(self, e: ft.ControlEvent) -> None:
        """Decrements current date by 1 day and reloads."""
        try:
            date_str = (self.date_field.value or "").strip() or self.selected_date
            curr = datetime.strptime(date_str, "%Y-%m-%d")
            prev_d = curr - timedelta(days=1)
            self.selected_date = prev_d.strftime("%Y-%m-%d")
            self.date_field.value = self.selected_date
            if self.selected_batch_id:
                self.load_batch_attendance(self.selected_batch_id)
        except Exception:
            pass

    def _handle_next_day(self, e: ft.ControlEvent) -> None:
        """Increments current date by 1 day and reloads (prevents moving into future dates)."""
        try:
            date_str = (self.date_field.value or "").strip() or self.selected_date
            curr = datetime.strptime(date_str, "%Y-%m-%d").date()
            if curr >= date.today():
                self._show_toast("Cannot navigate to future dates. Attendance cannot be recorded in advance.", is_error=True)
                return
            next_d = curr + timedelta(days=1)
            self.selected_date = next_d.strftime("%Y-%m-%d")
            self.date_field.value = self.selected_date
            if self.selected_batch_id:
                self.load_batch_attendance(self.selected_batch_id)
        except Exception:
            pass

    def _handle_jump_today(self, e: ft.ControlEvent) -> None:
        """Jumps directly to Today's date."""
        self.selected_date = datetime.now().strftime("%Y-%m-%d")
        self.date_field.value = self.selected_date
        if self.selected_batch_id:
            self.load_batch_attendance(self.selected_batch_id)

    def _handle_open_datepicker(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Opens interactive graphical date picker modal."""
        p = self.safe_page
        if not p:
            return
        try:
            curr_d = datetime.strptime(self.selected_date, "%Y-%m-%d")
        except Exception:
            curr_d = datetime.now()

        now = datetime.now()
        if curr_d.date() > now.date():
            curr_d = now

        def on_date_change(evt: ft.ControlEvent):
            if evt.data:
                iso_d = evt.data[:10]
                try:
                    if datetime.strptime(iso_d, "%Y-%m-%d").date() > date.today():
                        self._show_toast("Future dates are not allowed. Agle din ki presenty aaj nahi lagayi ja sakti.", is_error=True)
                        return
                except Exception:
                    pass
                self.selected_date = iso_d
                self.date_field.value = iso_d
                if self.selected_batch_id:
                    self.load_batch_attendance(self.selected_batch_id)

        picker = ft.DatePicker(
            first_date=datetime(2020, 1, 1),
            last_date=now,
            value=curr_d,
            on_change=on_date_change,
        )
        if hasattr(p, "open"):
            try:
                p.open(picker)
                return
            except Exception:
                pass
        if hasattr(p, "overlay"):
            p.overlay.append(picker)
            picker.open = True
            try:
                p.update()
            except Exception:
                pass

    def handle_batch_change(self, e: ft.ControlEvent) -> None:
        val = self.batch_dropdown.value
        if val:
            self.selected_batch_id = int(val)
            self.load_batch_attendance(self.selected_batch_id)

    def handle_date_change(self, e: ft.ControlEvent) -> None:
        val = (self.date_field.value or "").strip()
        try:
            if val and datetime.strptime(val, "%Y-%m-%d").date() > date.today():
                self._show_toast("Cannot mark attendance for future dates. Agle din ki presenty aaj nahi lagayi ja sakti.", is_error=True)
                self.selected_date = date.today().isoformat()
                self.date_field.value = self.selected_date
                if self.selected_batch_id:
                    self.load_batch_attendance(self.selected_batch_id)
                return
        except ValueError:
            pass
        self.selected_date = val or date.today().isoformat()
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

    def handle_invert_marks(self, e: ft.ControlEvent) -> None:
        """Inverts all currently set marks."""
        for sw in self.student_toggles.values():
            sw.value = not sw.value
        self._on_toggle_changed(None)

    def handle_save_online_attendance(self, e: Optional[ft.ControlEvent] = None, admin_pin: Optional[str] = None) -> None:
        """Saves current toggle states into the database attendance spreadsheet."""
        if not self.selected_batch_id:
            self._show_toast("Please select a batch first.", is_error=True)
            return

        try:
            if datetime.strptime(self.selected_date, "%Y-%m-%d").date() > date.today():
                self._show_toast("Cannot mark attendance for future dates. Agle din ki presenty aaj nahi lagayi ja sakti.", is_error=True)
                return
        except Exception:
            pass

        is_overwrite = bool(self.existing_session_marks)
        pin_required = self.attendance_settings.get("require_admin_pin_for_edits", True)

        if admin_pin is not None:
            if not self.controller.verify_admin_pin(admin_pin):
                self._show_toast("Invalid Admin PIN. Save aborted.", is_error=True)
                return
            self._execute_save_online_attendance()
            return

        if is_overwrite and pin_required and self.safe_page:
            self._show_admin_pin_dialog_for_save()
            return

        self._execute_save_online_attendance()

    def _show_admin_pin_dialog_for_save(self) -> None:
        """Prompts for Admin PIN confirmation prior to overwriting existing attendance."""
        def on_confirm(_):
            entered_pin = (pin_field.value or "").strip()
            if not entered_pin:
                error_text.value = "Admin Password / PIN is required."
                self._safe_update()
                return
            if not self.controller.verify_admin_pin(entered_pin):
                error_text.value = "Invalid Admin Password / PIN. Authorization failed."
                self._safe_update()
                return

            dlg.open = False
            self._safe_update()
            self._execute_save_online_attendance()

        def on_cancel(_):
            dlg.open = False
            self._safe_update()

        pin_field = ft.TextField(
            label="Admin Password / PIN",
            hint_text="Enter login password or Admin PIN",
            password=True,
            can_reveal_password=True,
            max_length=32,
            width=280,
            border_radius=AppTheme.RADIUS_MD,
            autofocus=True,
            on_submit=on_confirm,
        )
        error_text = ft.Text("", color=AppTheme.DANGER, size=11)

        dlg = ft.AlertDialog(
            title=ft.SelectionArea(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.SECURITY, color=AppTheme.WARNING, size=22),
                        ft.Text("Admin PIN Authorization Required", weight=ft.FontWeight.BOLD, size=15),
                    ],
                    spacing=8,
                )
            ),
            content=ft.SelectionArea(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            f"Attendance session records already exist for {self.selected_date}. Modifying recorded session data requires administrative authorization.",
                            size=AppTheme.SIZE_BODY,
                        ),
                        pin_field,
                        error_text,
                    ],
                    spacing=10,
                    tight=True,
                )
            ),
            actions=[
                ft.TextButton("Cancel", on_click=on_cancel),
                ft.FilledButton(
                    "Authorize & Overwrite",
                    style=ft.ButtonStyle(bgcolor=AppTheme.PRIMARY, color=ft.Colors.WHITE),
                    on_click=on_confirm,
                ),
            ],
        )
        self._open_dialog(dlg)

    def _execute_save_online_attendance(self) -> None:
        """Internal execution of online attendance persistence."""
        if not self.selected_batch_id:
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

    def handle_open_offline_register(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Opens modal to configure and generate multi-day digital Excel register."""
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
            self._show_toast(f"Generated digital register: {Path(path).name}", is_success=True)

        dlg = OfflineRegisterDialog(
            batch_id=self.selected_batch_id,
            batch_name=batch_name,
            course_name=course_name,
            on_generated=on_done,
            controller=self.controller,
        )
        self._open_dialog(dlg)

    def handle_open_offline_upload(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Opens modal to upload and reconcile multi-day digital Excel register."""
        if not self.selected_batch_id:
            self._show_toast("Please select a batch first.", is_error=True)
            return

        batch_name = "Batch"
        for b in self.batches:
            if b["id"] == self.selected_batch_id:
                batch_name = b["batch_name"]
                break

        def on_success():
            self._show_toast("✓ Offline register imported and reconciled successfully!", is_success=True)
            self.load_batch_attendance(self.selected_batch_id)

        dlg = ExcelImportReconciliationModal(
            batch_id=self.selected_batch_id,
            batch_name=batch_name,
            on_success=on_success,
            on_saved=on_success,
            controller=self.controller,
        )
        self._open_dialog(dlg)

    def _open_whatsapp_chat(self, mobile_number: Optional[str], student_name: str) -> None:
        """Opens WhatsApp web or desktop chat with the student."""
        if not mobile_number:
            self._show_toast(f"No mobile number recorded for {student_name}.", is_error=True)
            return
        from core.utils.url_utils import safe_open_url
        url = format_whatsapp_url(mobile_number)
        try:
            safe_open_url(url)
        except Exception as exc:
            LogService.error(f"Failed to open WhatsApp URL: {exc}", context="AttendanceHome")
            self._show_toast(f"Unable to launch browser: {exc}", is_error=True)

    def _send_whatsapp_alert(self, student: BatchStudentDTO) -> None:
        """Sends an individual attendance status alert via WhatsApp."""
        if not student.mobile_number:
            self._show_toast(f"No mobile number available for {student.student_name}.", is_error=True)
            return

        sw = self.student_toggles.get(student.student_id)
        is_present = sw.value if sw else False
        status_str = "PRESENT" if is_present else "ABSENT"
        msg = (
            f"SIMS Attendance Notification\n"
            f"Student: {student.student_name}\n"
            f"Registration No: {student.candidate_number or 'N/A'}\n"
            f"Date: {self.selected_date}\n"
            f"Attendance Status: {status_str}\n"
            f"Thank you,\nAdministration"
        )
        url = format_whatsapp_url(student.mobile_number, msg)
        try:
            from core.utils.url_utils import safe_open_url
            safe_open_url(url)
            self._show_toast(f"WhatsApp alert opened for {student.student_name} ({status_str})", is_success=True)
        except Exception as exc:
            LogService.error(f"Failed to open WhatsApp URL: {exc}", context="AttendanceHome")
            self._show_toast(f"Unable to launch WhatsApp: {exc}", is_error=True)

    def handle_whatsapp_absent_batch(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Alerts absent students via WhatsApp modal dialog."""
        absent_students = [
            st for st in self.enrolled_students
            if not (self.student_toggles.get(st.student_id) and self.student_toggles[st.student_id].value)
        ]
        with_mobiles = [st for st in absent_students if st.mobile_number]
        if not absent_students:
            self._show_toast("All enrolled students are currently marked PRESENT.", is_success=True)
            return
        if not with_mobiles:
            self._show_toast(f"{len(absent_students)} students absent, but none have mobile numbers registered.", is_error=True)
            return

        items = []
        for st in with_mobiles:
            msg = (
                f"SIMS Absentee Notice\n"
                f"Dear Student/Parent,\n"
                f"{st.student_name} ({st.candidate_number or 'No Reg ID'}) was marked ABSENT for batch attendance on {self.selected_date}.\n"
                f"Please contact the institute for any queries."
            )
            btn = ft.IconButton(
                icon=ft.Icons.SEND,
                icon_size=16,
                icon_color="#25D366",
                tooltip=f"Send WhatsApp to {st.student_name}",
                on_click=lambda _, mob=st.mobile_number, m=msg: safe_open_url(format_whatsapp_url(mob, m)),
            )
            items.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.PERSON_OFF, color="#DC2626"),
                    title=ft.Text(st.student_name, weight=ft.FontWeight.BOLD, size=12),
                    subtitle=ft.Text(f"{st.candidate_number or 'No ID'} • {st.mobile_number}", size=11),
                    trailing=btn,
                )
            )

        dlg = ft.AlertDialog(
            title=ft.SelectionArea(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.CAMPAIGN, color="#25D366", size=22),
                        ft.Text(f"Absentee WhatsApp Alerts ({len(with_mobiles)} Students)", weight=ft.FontWeight.BOLD, size=15),
                    ],
                    spacing=8,
                )
            ),
            content=ft.SelectionArea(
                content=ft.Container(
                    content=ft.ListView(controls=items, spacing=4),
                    width=420,
                    height=300,
                )
            ),
            actions=[
                ft.TextButton("Close", on_click=lambda _: self._close_dialog(dlg)),
            ],
        )
        self._open_dialog(dlg)

    def _close_dialog(self, dlg: ft.AlertDialog) -> None:
        dlg.open = False
        self._safe_update()

    def handle_whatsapp_defaulters_batch(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Opens WhatsApp warning alert dialog for all critical defaulters (<60%)."""
        if not self.current_matrix or not self.current_matrix.rows:
            self._show_toast("No matrix data available to evaluate defaulters.", is_error=True)
            return

        critical_defaulters = [
            r for r in self.current_matrix.rows
            if (r.health_status == AttendanceHealth.CRITICAL.value or r.attendance_percentage < 60.0)
        ]
        with_mobiles = [r for r in critical_defaulters if r.mobile_number]

        if not critical_defaulters:
            self._show_toast("No critical defaulters (< 60%) in this batch! Attendance is healthy.", is_success=True)
            return
        if not with_mobiles:
            self._show_toast(f"{len(critical_defaulters)} students below 60%, but none have mobile numbers registered.", is_error=True)
            return

        items = []
        batch_name = self.current_matrix.batch_name
        course_name = self.current_matrix.course_name
        for d in with_mobiles:
            msg = (
                f"SIMS Urgent Attendance Warning\n"
                f"Dear Student/Parent,\n"
                f"This is an official notice regarding attendance in {course_name} ({batch_name}).\n"
                f"Student: {d.student_name} ({d.candidate_number or 'No Reg ID'})\n"
                f"Current Attendance: {d.attendance_percentage:.1f}%\n"
                f"Sessions Attended: {d.total_present} / {d.total_present + d.total_absent}\n"
                f"Your attendance is critically below the 60% requirement.\n"
                f"Please meet the batch coordinator immediately."
            )
            btn = ft.IconButton(
                icon=ft.Icons.SEND,
                icon_size=16,
                icon_color="#25D366",
                tooltip=f"Send Warning WhatsApp to {d.student_name}",
                on_click=lambda _, mob=d.mobile_number, m=msg: safe_open_url(format_whatsapp_url(mob, m)),
            )
            items.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color="#DC2626"),
                    title=ft.Text(f"{d.student_name} — {d.attendance_percentage:.1f}%", weight=ft.FontWeight.BOLD, size=12, color="#DC2626"),
                    subtitle=ft.Text(f"Missed: {d.total_absent} sessions • {d.mobile_number}", size=11),
                    trailing=btn,
                )
            )

        dlg = ft.AlertDialog(
            title=ft.SelectionArea(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.WARNING, color="#DC2626", size=22),
                        ft.Text(f"Defaulter Attendance Notices ({len(with_mobiles)} Students < 60%)", weight=ft.FontWeight.BOLD, size=15),
                    ],
                    spacing=8,
                )
            ),
            content=ft.SelectionArea(
                content=ft.Container(
                    content=ft.ListView(controls=items, spacing=4),
                    width=440,
                    height=300,
                )
            ),
            actions=[
                ft.TextButton("Close", on_click=lambda _: self._close_dialog(dlg)),
            ],
        )
        self._open_dialog(dlg)


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

    def handle_export_excel(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Exports batch attendance matrix to Excel (.xlsx) with custom save prompt."""
        if not self.selected_batch_id:
            self._show_toast("Please select a batch first.", is_error=True)
            return
        try:
            path = self.controller.export_matrix_excel(self.selected_batch_id)
            export_and_prompt_save(
                source_file_path=path,
                dialog_title="Save Attendance Matrix As",
                allowed_extensions=[".xlsx"],
                show_toast=self._show_toast,
            )
        except Exception as exc:
            LogService.error(f"Failed to export attendance Excel: {exc}", context="AttendanceHome")
            self._show_toast("Failed to export attendance Excel.", is_error=True)

    def handle_export_pdf(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Exports batch attendance matrix to watermarked PDF with custom save prompt."""
        if not self.selected_batch_id:
            self._show_toast("Please select a batch first.", is_error=True)
            return
        try:
            path = self.controller.export_matrix_pdf(self.selected_batch_id)
            export_and_prompt_save(
                source_file_path=path,
                dialog_title="Save Attendance PDF Report As",
                allowed_extensions=[".pdf"],
                show_toast=self._show_toast,
            )
        except Exception as exc:
            LogService.error(f"Failed to export attendance PDF: {exc}", context="AttendanceHome")
            self._show_toast("Failed to export attendance PDF.", is_error=True)
