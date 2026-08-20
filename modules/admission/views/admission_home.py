# modules/admission/views/admission_home.py

from __future__ import annotations
from typing import Optional, Any
import flet as ft

from core.logger.service import LogService
from ui.themes.theme import AppTheme
from modules.admission.controller import AdmissionController
from modules.admission.constants import AdmissionStatus, ADMISSION_STATUS_COLORS
from modules.admission.dto import AdmissionDTO, AdmissionSummaryDTO
from modules.admission.views.admission_form_modal import AdmissionFormModal
from modules.admission.views.admission_workspace_dialog import AdmissionWorkspaceDialog
from modules.course.controller import CourseController

__all__ = ["AdmissionHome"]


class AdmissionHome(ft.Container):
    """
    Official Enterprise Admission Management Directory.
    Features:
    - Live Summary KPI metrics (Total, Confirmed, Registered, Drafts, Today)
    - Full-Width Centered Universal Search Bar
    - Independent Composable Filter Controls (Status, Course, Year, Month)
    - Multi-Column Sorting Toolbar with active removable chips
    - Data Table with candidate number badges (YYYY-NNN) and semantic status colors
    - Fast CSV & PDF Exporting
    - Double-click row interaction to open 360° Admission Workspace
    - Full Pagination Support
    """

    MONTH_NAMES = [
        ("1", "January"), ("2", "February"), ("3", "March"), ("4", "April"),
        ("5", "May"), ("6", "June"), ("7", "July"), ("8", "August"),
        ("9", "September"), ("10", "October"), ("11", "November"), ("12", "December"),
    ]

    SORT_OPTIONS = [
        ("id", "Admission ID"),
        ("candidate_number", "Candidate Number"),
        ("student_name", "Student Name"),
        ("course_name", "Course Name"),
        ("date", "Admission Date"),
        ("agreed_fee", "Agreed Fee"),
        ("status", "Status"),
    ]

    def __init__(self) -> None:
        super().__init__(expand=True, padding=AppTheme.PAD_LG)

        self.controller = AdmissionController()
        self.course_controller = CourseController()

        # State Variables
        self.admissions: list[AdmissionDTO] = []
        self.total_count: int = 0
        self.current_page: int = 0
        self.page_size: int = 25
        self.summary_stats: Optional[AdmissionSummaryDTO] = None

        # Filter State
        self.search_query: str = ""
        self.selected_status: str = "ALL"
        self.selected_course_id: Optional[int] = None
        self.selected_year: Optional[int] = None
        self.selected_month: Optional[int] = None

        # Multi-Sort State: list of (field, direction)
        self.active_sorts: list[tuple[str, str]] = [("id", "desc")]

        # Build UI Structure
        self._build_ui()

    def _build_ui(self) -> None:
        # ----------------------------------------------------
        # 1. Header & KPI Summary Cards
        # ----------------------------------------------------
        self.title_text = ft.Text(
            "Admission Directory",
            size=AppTheme.SIZE_H1,
            weight=ft.FontWeight.BOLD,
            color=AppTheme.TEXT_PRIMARY,
        )
        self.subtitle_text = ft.Text(
            "Manage student admissions, candidate numbering, batch enrollments, and status lifecycle.",
            size=AppTheme.SIZE_BODY,
            color=AppTheme.TEXT_SECONDARY,
        )

        # Action Buttons
        self.new_adm_btn = ft.ElevatedButton(
            content=ft.Text("New Admission", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.W_600),
            icon=ft.Icons.PERSON_ADD_ALT_1,
            style=ft.ButtonStyle(
                bgcolor=AppTheme.PRIMARY,
                color=AppTheme.SURFACE,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                padding=ft.Padding(left=16, top=12, right=16, bottom=12),
            ),
            on_click=self.handle_new_admission,
        )

        self.export_csv_btn = ft.OutlinedButton(
            content=ft.Text("Export CSV", size=AppTheme.SIZE_CAPTION),
            icon=ft.Icons.DOWNLOAD,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD)),
            on_click=self.handle_export_csv,
        )

        self.export_pdf_btn = ft.OutlinedButton(
            content=ft.Text("Export PDF", size=AppTheme.SIZE_CAPTION),
            icon=ft.Icons.PICTURE_AS_PDF,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD)),
            on_click=self.handle_export_pdf,
        )

        self.refresh_btn = ft.IconButton(
            icon=ft.Icons.REFRESH,
            icon_size=20,
            tooltip="Refresh Directory",
            on_click=lambda e: self.load_data(),
        )

        header_row = ft.Row(
            controls=[
                ft.Column(controls=[self.title_text, self.subtitle_text], spacing=2),
                ft.Row(
                    controls=[self.export_csv_btn, self.export_pdf_btn, self.refresh_btn, self.new_adm_btn],
                    spacing=AppTheme.PAD_SM,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        # KPI Summary Badges
        self.kpi_total_text = ft.Text("0", size=AppTheme.SIZE_H2, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY)
        self.kpi_confirmed_text = ft.Text("0", size=AppTheme.SIZE_H2, weight=ft.FontWeight.BOLD, color=AppTheme.SUCCESS)
        self.kpi_registered_text = ft.Text("0", size=AppTheme.SIZE_H2, weight=ft.FontWeight.BOLD, color="#3B82F6")
        self.kpi_draft_text = ft.Text("0", size=AppTheme.SIZE_H2, weight=ft.FontWeight.BOLD, color=AppTheme.WARNING)
        self.kpi_today_text = ft.Text("0", size=AppTheme.SIZE_H2, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY)

        kpi_row = ft.Row(
            controls=[
                self._kpi_card("Total Admissions", self.kpi_total_text, ft.Icons.APP_REGISTRATION, AppTheme.PRIMARY_LIGHT),
                self._kpi_card("Confirmed", self.kpi_confirmed_text, ft.Icons.CHECK_CIRCLE, AppTheme.SUCCESS_LIGHT),
                self._kpi_card("Registered", self.kpi_registered_text, ft.Icons.HOW_TO_REG, "#EFF6FF"),
                self._kpi_card("Pending Drafts", self.kpi_draft_text, ft.Icons.EDIT_NOTE, "#FEF3C7"),
                self._kpi_card("Today's Admissions", self.kpi_today_text, ft.Icons.TODAY, AppTheme.SURFACE_VARIANT),
            ],
            spacing=AppTheme.PAD_MD,
        )

        # ----------------------------------------------------
        # 2. Universal Search Bar
        # ----------------------------------------------------
        self.search_field = ft.TextField(
            hint_text="Search admissions by Candidate No (e.g. 2026-001), Student Name, Mobile, Course, or Batch...",
            prefix_icon=ft.Icons.SEARCH,
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
            expand=True,
            on_change=self.handle_search_change,
            on_submit=self.handle_search_submit,
        )

        self.clear_search_btn = ft.IconButton(
            icon=ft.Icons.CLEAR,
            icon_size=18,
            tooltip="Clear Search",
            visible=False,
            on_click=self.handle_clear_search,
        )

        search_container = ft.Container(
            content=ft.Row(
                controls=[self.search_field, self.clear_search_btn],
                spacing=AppTheme.PAD_XS,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=ft.Padding(left=8, top=4, right=8, bottom=4),
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        # ----------------------------------------------------
        # 3. Independent Filters Panel
        # ----------------------------------------------------
        self.status_filter = ft.Dropdown(
            label="Status",
            value="ALL",
            width=160,
            text_size=AppTheme.SIZE_BODY,
            border_radius=AppTheme.RADIUS_MD,
            options=[
                ft.DropdownOption("ALL", "All Statuses"),
                ft.DropdownOption("REGISTERED", "Registered"),
                ft.DropdownOption("CONFIRMED", "Confirmed"),
                ft.DropdownOption("DRAFT", "Draft"),
                ft.DropdownOption("CANCELLED", "Cancelled"),
            ],
            on_select=self.handle_filter_change,
        )

        self.course_filter = ft.Dropdown(
            label="Course",
            value="ALL",
            width=200,
            text_size=AppTheme.SIZE_BODY,
            border_radius=AppTheme.RADIUS_MD,
            options=[ft.DropdownOption("ALL", "All Courses")],
            on_select=self.handle_filter_change,
        )

        current_year = 2026
        year_options = [ft.DropdownOption("ALL", "All Years")] + [
            ft.DropdownOption(str(y), str(y)) for y in range(current_year + 1, current_year - 5, -1)
        ]
        self.year_filter = ft.Dropdown(
            label="Academic Year",
            value="ALL",
            width=140,
            text_size=AppTheme.SIZE_BODY,
            border_radius=AppTheme.RADIUS_MD,
            options=year_options,
            on_select=self.handle_filter_change,
        )

        month_options = [ft.DropdownOption("ALL", "All Months")] + [
            ft.DropdownOption(val, name) for val, name in self.MONTH_NAMES
        ]
        self.month_filter = ft.Dropdown(
            label="Admission Month",
            value="ALL",
            width=160,
            text_size=AppTheme.SIZE_BODY,
            border_radius=AppTheme.RADIUS_MD,
            options=month_options,
            on_select=self.handle_filter_change,
        )

        self.reset_filters_btn = ft.TextButton(
            content=ft.Row(
                controls=[ft.Icon(ft.Icons.FILTER_ALT_OFF, size=16, color=AppTheme.TEXT_SECONDARY), ft.Text("Reset Filters", size=AppTheme.SIZE_CAPTION)],
                spacing=4,
            ),
            on_click=self.handle_reset_filters,
        )

        filters_row = ft.Row(
            controls=[
                self.status_filter,
                self.course_filter,
                self.year_filter,
                self.month_filter,
                self.reset_filters_btn,
            ],
            spacing=AppTheme.PAD_SM,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # ----------------------------------------------------
        # 4. Multi-Sort Toolbar & Chips
        # ----------------------------------------------------
        self.sort_field_dropdown = ft.Dropdown(
            label="Sort Field",
            value="id",
            width=170,
            text_size=AppTheme.SIZE_BODY,
            border_radius=AppTheme.RADIUS_MD,
            options=[ft.DropdownOption(f, lbl) for f, lbl in self.SORT_OPTIONS],
        )

        self.sort_direction_dropdown = ft.Dropdown(
            label="Direction",
            value="desc",
            width=130,
            text_size=AppTheme.SIZE_BODY,
            border_radius=AppTheme.RADIUS_MD,
            options=[
                ft.DropdownOption("asc", "Ascending (A-Z)"),
                ft.DropdownOption("desc", "Descending (Z-A)"),
            ],
        )

        self.add_sort_btn = ft.OutlinedButton(
            content=ft.Text("Add Sort", size=AppTheme.SIZE_CAPTION),
            icon=ft.Icons.SORT,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD)),
            on_click=self.handle_add_sort,
        )

        self.clear_sort_btn = ft.TextButton(
            content=ft.Text("Clear Sort", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
            on_click=self.handle_clear_sorts,
        )

        self.sort_chips_row = ft.Row(spacing=AppTheme.PAD_XS, wrap=True)

        sort_controls_row = ft.Row(
            controls=[
                self.sort_field_dropdown,
                self.sort_direction_dropdown,
                self.add_sort_btn,
                self.clear_sort_btn,
                ft.VerticalDivider(width=1, color=AppTheme.BORDER),
                ft.Container(content=self.sort_chips_row, expand=True),
            ],
            spacing=AppTheme.PAD_SM,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # ----------------------------------------------------
        # 5. Data Table
        # ----------------------------------------------------
        self.table_columns = [
            ft.DataColumn(label=ft.Text("Candidate No", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
            ft.DataColumn(label=ft.Text("Student Name", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
            ft.DataColumn(label=ft.Text("Mobile Number", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
            ft.DataColumn(label=ft.Text("Course", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
            ft.DataColumn(label=ft.Text("Batch", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
            ft.DataColumn(label=ft.Text("Status", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
            ft.DataColumn(label=ft.Text("Agreed Fee", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
            ft.DataColumn(label=ft.Text("Admission Date", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
            ft.DataColumn(label=ft.Text("Actions", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
        ]

        self.data_table = ft.DataTable(
            columns=self.table_columns,
            rows=[],
            heading_row_color=AppTheme.SURFACE_VARIANT,
            heading_row_height=42,
            data_row_min_height=48,
            data_row_max_height=56,
            horizontal_margin=AppTheme.PAD_MD,
            column_spacing=AppTheme.PAD_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
            border_radius=AppTheme.RADIUS_MD,
        )

        self.empty_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.SEARCH_OFF, size=48, color=AppTheme.TEXT_MUTED),
                    ft.Text("No matching admissions found", size=AppTheme.SIZE_H3, weight=ft.FontWeight.W_600, color=AppTheme.TEXT_SECONDARY),
                    ft.Text("Try adjusting your search criteria or filters.", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=AppTheme.PAD_XS,
            ),
            padding=ft.Padding(0, 40, 0, 40),
            visible=False,
        )

        self.table_container = ft.Container(
            content=ft.Column(
                controls=[self.data_table, self.empty_container],
                scroll=ft.ScrollMode.AUTO,
            ),
            expand=True,
        )

        # ----------------------------------------------------
        # 6. Pagination Footer
        # ----------------------------------------------------
        self.pagination_info = ft.Text(
            "Showing 0 of 0 admissions",
            size=AppTheme.SIZE_CAPTION,
            color=AppTheme.TEXT_SECONDARY,
        )

        self.page_size_dropdown = ft.Dropdown(
            value=str(self.page_size),
            width=110,
            text_size=AppTheme.SIZE_CAPTION,
            options=[
                ft.DropdownOption("10", "10 / page"),
                ft.DropdownOption("25", "25 / page"),
                ft.DropdownOption("50", "50 / page"),
                ft.DropdownOption("100", "100 / page"),
            ],
            on_select=self.handle_page_size_change,
        )

        self.prev_page_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_LEFT,
            icon_size=18,
            disabled=True,
            on_click=self.handle_prev_page,
        )

        self.next_page_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_RIGHT,
            icon_size=18,
            disabled=True,
            on_click=self.handle_next_page,
        )

        pagination_row = ft.Row(
            controls=[
                self.pagination_info,
                ft.Row(
                    controls=[self.page_size_dropdown, self.prev_page_btn, self.next_page_btn],
                    spacing=AppTheme.PAD_XS,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        # Main Layout Assembly
        self.content = ft.Column(
            controls=[
                header_row,
                ft.Divider(height=1, color=AppTheme.BORDER),
                kpi_row,
                search_container,
                filters_row,
                sort_controls_row,
                ft.Divider(height=1, color=AppTheme.BORDER),
                self.table_container,
                pagination_row,
            ],
            spacing=AppTheme.PAD_MD,
            expand=True,
        )

    def _kpi_card(self, label: str, value_control: ft.Text, icon: str, bgcolor: str) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(icon, size=24, color=AppTheme.PRIMARY),
                    ft.Column(
                        controls=[
                            value_control,
                            ft.Text(label, size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                        ],
                        spacing=0,
                    ),
                ],
                spacing=AppTheme.PAD_SM,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=bgcolor,
            padding=ft.Padding(left=16, top=12, right=16, bottom=12),
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
            expand=True,
        )

    def _safe_update(self) -> None:
        try:
            if self.page:
                self.update()
        except RuntimeError:
            pass

    def load_data(self) -> None:
        """Loads courses, KPI summary, and filtered admissions list."""
        self._load_course_filter_options()
        self._load_summary_kpis()
        self._load_admissions_table()
        self._render_sort_chips()
        self._safe_update()

    def _load_course_filter_options(self) -> None:
        try:
            courses, _ = self.course_controller.list_courses(limit=200)
            options = [ft.DropdownOption("ALL", "All Courses")] + [
                ft.DropdownOption(str(c.id), f"{c.name} ({c.code})") for c in courses
            ]
            self.course_filter.options = options
        except Exception as ex:
            LogService.error(f"Failed to load course options for filter: {ex}", context=self.__class__.__name__)

    def _load_summary_kpis(self) -> None:
        try:
            stats = self.controller.get_summary_stats()
            self.summary_stats = stats
            self.kpi_total_text.value = f"{stats.total_admissions:,}"
            self.kpi_confirmed_text.value = f"{stats.confirmed_count:,}"
            self.kpi_registered_text.value = f"{stats.registered_count:,}"
            self.kpi_draft_text.value = f"{stats.draft_count:,}"
            self.kpi_today_text.value = f"{stats.today_count:,}"
        except Exception as ex:
            LogService.error(f"Failed to load summary stats: {ex}", context=self.__class__.__name__)

    def _load_admissions_table(self) -> None:
        try:
            criteria = {
                "query": self.search_query,
                "status": self.selected_status if self.selected_status != "ALL" else None,
                "course_id": self.selected_course_id,
                "year": self.selected_year,
                "month": self.selected_month,
                "limit": self.page_size,
                "offset": self.current_page * self.page_size,
                "sorts": self.active_sorts,
            }

            admissions, total = self.controller.filter_admissions(criteria)
            self.admissions = admissions
            self.total_count = total

            # Populate Rows
            rows = []
            for adm in admissions:
                status_color = ADMISSION_STATUS_COLORS.get(adm.status, AppTheme.PRIMARY)
                status_badge = ft.Container(
                    content=ft.Text(adm.status_label, size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD, color=AppTheme.SURFACE),
                    bgcolor=status_color,
                    padding=ft.Padding(left=8, top=2, right=8, bottom=2),
                    border_radius=AppTheme.RADIUS_SM,
                )

                candidate_badge = ft.Container(
                    content=ft.Text(adm.admission_number, size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.W_600, color=AppTheme.PRIMARY),
                    bgcolor=AppTheme.PRIMARY_LIGHT,
                    padding=ft.Padding(left=8, top=2, right=8, bottom=2),
                    border_radius=AppTheme.RADIUS_SM,
                )

                action_btns = ft.Row(
                    controls=[
                        ft.IconButton(
                            icon=ft.Icons.VISIBILITY,
                            icon_size=16,
                            icon_color=AppTheme.PRIMARY,
                            tooltip="Open Workspace Details",
                            on_click=lambda ev, aid=adm.id: self.open_workspace(aid),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.EDIT,
                            icon_size=16,
                            icon_color=AppTheme.TEXT_SECONDARY,
                            tooltip="Edit Admission",
                            on_click=lambda ev, a=adm: self.open_edit_modal(a),
                        ),
                    ],
                    spacing=0,
                )

                row = ft.DataRow(
                    cells=[
                        ft.DataCell(candidate_badge),
                        ft.DataCell(ft.Text(adm.student_name, weight=ft.FontWeight.W_600, size=AppTheme.SIZE_BODY)),
                        ft.DataCell(ft.Text(adm.student_mobile or "—", size=AppTheme.SIZE_BODY)),
                        ft.DataCell(ft.Text(adm.course_name or "—", size=AppTheme.SIZE_BODY)),
                        ft.DataCell(ft.Text(adm.batch_name or "—", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY)),
                        ft.DataCell(status_badge),
                        ft.DataCell(ft.Text(adm.fee_display, weight=ft.FontWeight.W_600, size=AppTheme.SIZE_BODY)),
                        ft.DataCell(ft.Text(adm.created_date_display, size=AppTheme.SIZE_CAPTION)),
                        ft.DataCell(action_btns),
                    ],
                    on_select_changed=lambda e, aid=adm.id: self.open_workspace(aid),
                )
                rows.append(row)

            self.data_table.rows = rows
            self.empty_container.visible = (total == 0)
            self.data_table.visible = (total > 0)

            # Update Pagination
            start_idx = self.current_page * self.page_size + 1 if total > 0 else 0
            end_idx = min((self.current_page + 1) * self.page_size, total)
            self.pagination_info.value = f"Showing {start_idx}-{end_idx} of {total:,} admissions"
            self.prev_page_btn.disabled = (self.current_page == 0)
            self.next_page_btn.disabled = (end_idx >= total)

        except Exception as ex:
            LogService.error(f"Failed to load admissions table: {ex}", context=self.__class__.__name__)

    def _render_sort_chips(self) -> None:
        """Renders active multi-sort chips with priority tags and remove handles."""
        chips = []
        for idx, (field, direction) in enumerate(self.active_sorts):
            label_name = next((lbl for f, lbl in self.SORT_OPTIONS if f == field), field.title())
            dir_arrow = "↑ ASC" if direction.lower() == "asc" else "↓ DESC"

            chip = ft.Chip(
                label=ft.Text(f"#{idx+1} {label_name} {dir_arrow}", size=AppTheme.SIZE_CAPTION),
                leading=ft.Icon(ft.Icons.SORT_BY_ALPHA if "name" in field else ft.Icons.SORT, size=14),
                on_delete=lambda e, f=field: self.handle_remove_sort(f),
            )
            chips.append(chip)

        self.sort_chips_row.controls = chips

    # ----------------------------------------------------
    # Event Handlers
    # ----------------------------------------------------
    def handle_search_change(self, e: ft.ControlEvent) -> None:
        val = (self.search_field.value or "").strip()
        self.clear_search_btn.visible = bool(val)
        self.search_query = val
        self.current_page = 0
        self._load_admissions_table()
        self._safe_update()

    def handle_search_submit(self, e: ft.ControlEvent) -> None:
        self.handle_search_change(e)

    def handle_clear_search(self, e: ft.ControlEvent) -> None:
        self.search_field.value = ""
        self.clear_search_btn.visible = False
        self.search_query = ""
        self.current_page = 0
        self._load_admissions_table()
        self._safe_update()

    def handle_filter_change(self, e: ft.ControlEvent) -> None:
        self.selected_status = self.status_filter.value or "ALL"

        course_val = self.course_filter.value
        self.selected_course_id = int(course_val) if course_val and course_val != "ALL" else None

        year_val = self.year_filter.value
        self.selected_year = int(year_val) if year_val and year_val != "ALL" else None

        month_val = self.month_filter.value
        self.selected_month = int(month_val) if month_val and month_val != "ALL" else None

        self.current_page = 0
        self._load_admissions_table()
        self._safe_update()

    def handle_reset_filters(self, e: ft.ControlEvent) -> None:
        self.status_filter.value = "ALL"
        self.course_filter.value = "ALL"
        self.year_filter.value = "ALL"
        self.month_filter.value = "ALL"
        self.selected_status = "ALL"
        self.selected_course_id = None
        self.selected_year = None
        self.selected_month = None
        self.current_page = 0
        self._load_admissions_table()
        self._safe_update()

    def handle_add_sort(self, e: ft.ControlEvent) -> None:
        field = self.sort_field_dropdown.value or "id"
        direction = self.sort_direction_dropdown.value or "desc"

        existing_idx = next((i for i, (f, _) in enumerate(self.active_sorts) if f == field), None)
        if existing_idx is not None:
            self.active_sorts[existing_idx] = (field, direction)
        else:
            self.active_sorts.append((field, direction))

        self.current_page = 0
        self._load_admissions_table()
        self._render_sort_chips()
        self._safe_update()

    def handle_remove_sort(self, field: str) -> None:
        self.active_sorts = [(f, d) for f, d in self.active_sorts if f != field]
        if not self.active_sorts:
            self.active_sorts = [("id", "desc")]
        self.current_page = 0
        self._load_admissions_table()
        self._render_sort_chips()
        self._safe_update()

    def handle_clear_sorts(self, e: ft.ControlEvent) -> None:
        self.active_sorts = [("id", "desc")]
        self.current_page = 0
        self._load_admissions_table()
        self._render_sort_chips()
        self._safe_update()

    def handle_page_size_change(self, e: ft.ControlEvent) -> None:
        self.page_size = int(self.page_size_dropdown.value or "25")
        self.current_page = 0
        self._load_admissions_table()
        self._safe_update()

    def handle_prev_page(self, e: ft.ControlEvent) -> None:
        if self.current_page > 0:
            self.current_page -= 1
            self._load_admissions_table()
            self._safe_update()

    def handle_next_page(self, e: ft.ControlEvent) -> None:
        if (self.current_page + 1) * self.page_size < self.total_count:
            self.current_page += 1
            self._load_admissions_table()
            self._safe_update()

    def handle_new_admission(self, e: ft.ControlEvent) -> None:
        if not self.page:
            return
        modal = AdmissionFormModal(on_saved=self.load_data)
        self.page.show_dialog(modal)

    def open_edit_modal(self, admission: AdmissionDTO) -> None:
        if not self.page:
            return
        modal = AdmissionFormModal(admission=admission, on_saved=self.load_data)
        self.page.show_dialog(modal)

    def open_workspace(self, admission_id: int) -> None:
        if not self.page:
            return
        dialog = AdmissionWorkspaceDialog(admission_id=admission_id, on_updated=self.load_data)
        self.page.show_dialog(dialog)

    def show_snackbar(self, message: str, is_error: bool = False) -> None:
        if not self.page:
            return
        snack = ft.SnackBar(
            content=ft.Text(message, color=AppTheme.SURFACE),
            bgcolor=AppTheme.DANGER if is_error else AppTheme.SUCCESS,
        )
        self.page.show_dialog(snack)

    def handle_export_csv(self, e: ft.ControlEvent) -> None:
        try:
            filters = {
                "query": self.search_query,
                "status": self.selected_status if self.selected_status != "ALL" else None,
                "course_id": self.selected_course_id,
                "year": self.selected_year,
                "month": self.selected_month,
                "sorts": self.active_sorts,
            }
            path = self.controller.export_admissions_csv(filters)
            self.show_snackbar(f"Admission directory exported to CSV: {path}")
        except Exception as ex:
            LogService.error(f"Failed to export CSV: {ex}", context=self.__class__.__name__)
            self.show_snackbar("Failed to export admission CSV data.", is_error=True)

    def handle_export_pdf(self, e: ft.ControlEvent) -> None:
        try:
            filters = {
                "query": self.search_query,
                "status": self.selected_status if self.selected_status != "ALL" else None,
                "course_id": self.selected_course_id,
                "year": self.selected_year,
                "month": self.selected_month,
                "sorts": self.active_sorts,
            }
            path = self.controller.export_admissions_pdf(filters)
            self.show_snackbar(f"Admission directory exported to PDF: {path}")
        except Exception as ex:
            LogService.error(f"Failed to export PDF: {ex}", context=self.__class__.__name__)
            self.show_snackbar("Failed to export admission PDF report.", is_error=True)
