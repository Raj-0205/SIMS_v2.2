# modules/student/views/student_home.py

from __future__ import annotations
import asyncio
from datetime import datetime
from typing import Optional
import flet as ft

from core.exceptions import ValidationError, ConflictError, ServiceError
from core.logger.service import LogService
from modules.course.controller import CourseController
from modules.student.controller import StudentController
from modules.student.dto import StudentDTO
from modules.student.views.student_form_modal import StudentFormModal
from modules.student.views.student_workspace_dialog import StudentWorkspaceDialog
from ui.themes.theme import AppTheme

__all__ = ["StudentHome"]

# ──────────────────────────────────────────────────────────────────────────
# MONTH DISPLAY NAMES
# ──────────────────────────────────────────────────────────────────────────
_MONTH_NAMES: dict[int, str] = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}

# ──────────────────────────────────────────────────────────────────────────
# SORT FIELD DISPLAY LABELS
# ──────────────────────────────────────────────────────────────────────────
_SORT_FIELD_LABELS: dict[str, str] = {
    "id": "Student ID",
    "name": "Name",
    "admission_id": "Admission ID",
    "mobile": "Mobile",
    "course": "Course",
    "date": "Admission Date",
    "status": "Status",
    "fee": "Fee",
    "year": "Year",
    "month": "Month",
}


class StudentHome(ft.Container):
    """
    Main Student Management Screen (Student Directory).
    Follows Part 05 of the SIMS Blueprint:
    Provides full-width search bar, composable persistent filter chips,
    independent multi-sort chips, database-level pagination,
    Excel & PDF exports, real-time KPI badge,
    robust empty/error states, double-click workspace opening, and context actions.
    """

    PAGE_SIZE: int = 15

    def __init__(self) -> None:
        super().__init__(
            expand=True,
            padding=AppTheme.PAD_LG,
            bgcolor=AppTheme.BACKGROUND,
        )

        self.controller = StudentController()
        self.course_controller = CourseController()

        # ── Filter State (independent, composable, persistent) ──
        self.current_query: str = ""
        self.current_course_id: Optional[int] = None
        self.current_course_label: Optional[str] = None
        self.current_status: Optional[str] = None
        self.current_year: Optional[int] = None
        self.current_month: Optional[int] = None

        # ── Sort State (independent, multi-column) ──
        # List of (field, direction) tuples in priority order
        self.sort_keys: list[tuple[str, str]] = [("id", "desc")]

        # ── Pagination State ──
        self.current_page: int = 0
        self.total_count: int = 0
        self.students: list[StudentDTO] = []

        # ── Debounce State ──
        self._search_generation: int = 0

        # ── Course Options Cache ──
        self._course_options: dict[int, str] = {}

        # ── UI Components ──
        self.header = self._build_header()
        self.search_bar = self._build_search_bar()
        self.filter_controls = self._build_filter_controls()
        self.filter_chips_row = ft.Row(controls=[], spacing=6, wrap=True)
        self.sort_chips_row = ft.Row(controls=[], spacing=6, wrap=True)
        self.active_state_bar = self._build_active_state_bar()
        self.table_container = ft.Container(expand=True)
        self.pagination_bar = self._build_pagination_bar()

        self.content = ft.Column(
            controls=[
                self.header,
                self.search_bar,
                self.filter_controls,
                self.active_state_bar,
                self.table_container,
                self.pagination_bar,
            ],
            spacing=AppTheme.PAD_SM,
            expand=True,
        )

    def did_mount(self) -> None:
        """Called when the control is mounted to the page tree."""
        self._populate_course_filter()
        self.load_data()

    def show_snackbar(self, message: str, is_error: bool = False) -> None:
        """Displays transient feedback snackbar to the user using Flet's show_dialog."""
        try:
            page = self.page
        except RuntimeError:
            page = None

        if not page:
            return
        bg_color = AppTheme.DANGER if is_error else AppTheme.SUCCESS
        snackbar = ft.SnackBar(
            content=ft.Text(message, color=AppTheme.SURFACE),
            bgcolor=bg_color,
        )
        page.show_dialog(snackbar)

    # ══════════════════════════════════════════════════════════════════════
    # HEADER — Title + Action Buttons
    # ══════════════════════════════════════════════════════════════════════
    def _build_header(self) -> ft.Row:
        return ft.Row(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.PEOPLE_ALT, size=28, color=AppTheme.PRIMARY),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    "Student Directory",
                                    size=AppTheme.SIZE_H1,
                                    weight=ft.FontWeight.BOLD,
                                    color=AppTheme.TEXT_PRIMARY,
                                ),
                                ft.Text(
                                    "Manage institute student master records, registrations, and academic history",
                                    size=AppTheme.SIZE_CAPTION,
                                    color=AppTheme.TEXT_SECONDARY,
                                ),
                            ],
                            spacing=2,
                        ),
                    ],
                    spacing=AppTheme.PAD_SM,
                ),
                ft.Row(
                    controls=[
                        ft.OutlinedButton(
                            content=ft.Text("Export CSV"),
                            icon=ft.Icons.TABLE_VIEW,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                            ),
                            on_click=self.handle_export_csv,
                        ),
                        ft.OutlinedButton(
                            content=ft.Text("Export PDF"),
                            icon=ft.Icons.PICTURE_AS_PDF,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                            ),
                            on_click=self.handle_export_pdf,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.REFRESH,
                            tooltip="Refresh Directory",
                            icon_color=AppTheme.PRIMARY,
                            on_click=lambda _: self.load_data(),
                        ),
                        ft.ElevatedButton(
                            content=ft.Text("Register Student"),
                            icon=ft.Icons.PERSON_ADD,
                            style=ft.ButtonStyle(
                                bgcolor=AppTheme.PRIMARY,
                                color=AppTheme.SURFACE,
                                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                                padding=ft.Padding(left=16, top=12, right=16, bottom=12),
                            ),
                            on_click=self.handle_add_student,
                        ),
                    ],
                    spacing=AppTheme.PAD_SM,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

    # ══════════════════════════════════════════════════════════════════════
    # SEARCH BAR — Full-width, prominent, centered
    # ══════════════════════════════════════════════════════════════════════
    def _build_search_bar(self) -> ft.Container:
        self.clear_search_btn = ft.IconButton(
            icon=ft.Icons.CLEAR,
            icon_size=18,
            tooltip="Clear search",
            visible=False,
            on_click=self.handle_clear_search,
        )

        self.search_field = ft.TextField(
            hint_text="Search students by name, mobile, email, admission ID (YYYY-NNN), or student ID...",
            prefix_icon=ft.Icons.SEARCH,
            suffix=self.clear_search_btn,
            border_radius=AppTheme.RADIUS_LG,
            text_size=AppTheme.SIZE_BODY,
            content_padding=ft.Padding(left=16, top=12, right=16, bottom=12),
            expand=True,
            on_change=self.handle_search_change,
            on_submit=self.handle_search_submit,
        )

        self.total_badge_text = ft.Text(
            "Total: 0",
            size=AppTheme.SIZE_BODY,
            weight=ft.FontWeight.BOLD,
            color=AppTheme.PRIMARY,
        )

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.DATA_ARRAY, size=18, color=AppTheme.PRIMARY),
                                self.total_badge_text,
                            ],
                            spacing=6,
                        ),
                        bgcolor=AppTheme.PRIMARY_LIGHT,
                        padding=ft.Padding(left=12, top=8, right=12, bottom=8),
                        border_radius=AppTheme.RADIUS_SM,
                    ),
                    self.search_field,
                ],
                spacing=AppTheme.PAD_MD,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=AppTheme.PAD_MD,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

    # ══════════════════════════════════════════════════════════════════════
    # FILTER CONTROLS — Dropdowns for Course, Status, Year, Month + Sort
    # ══════════════════════════════════════════════════════════════════════
    def _build_filter_controls(self) -> ft.Container:
        self.course_dropdown = ft.Dropdown(
            label="Course",
            width=200,
            content_padding=ft.Padding(left=10, top=4, right=10, bottom=4),
            border_radius=AppTheme.RADIUS_MD,
            options=[ft.DropdownOption(key="ALL", text="All Courses")],
            value="ALL",
            on_select=self.handle_course_filter_change,
        )

        self.status_dropdown = ft.Dropdown(
            label="Status",
            width=150,
            content_padding=ft.Padding(left=10, top=4, right=10, bottom=4),
            border_radius=AppTheme.RADIUS_MD,
            options=[
                ft.DropdownOption(key="ALL", text="All Statuses"),
                ft.DropdownOption(key="REGISTERED", text="Registered"),
                ft.DropdownOption(key="CONFIRMED", text="Confirmed"),
                ft.DropdownOption(key="DRAFT", text="Draft"),
                ft.DropdownOption(key="CANCELLED", text="Cancelled"),
                ft.DropdownOption(key="COMPLETED", text="Completed"),
            ],
            value="ALL",
            on_select=self.handle_status_filter_change,
        )

        current_year_val = datetime.now().year
        year_options = [ft.DropdownOption(key="ALL", text="All Years")]
        for y in range(current_year_val, current_year_val - 5, -1):
            year_options.append(ft.DropdownOption(key=str(y), text=str(y)))

        self.year_dropdown = ft.Dropdown(
            label="Year",
            width=110,
            content_padding=ft.Padding(left=10, top=4, right=10, bottom=4),
            border_radius=AppTheme.RADIUS_MD,
            options=year_options,
            value="ALL",
            on_select=self.handle_year_filter_change,
        )

        month_options = [ft.DropdownOption(key="ALL", text="All Months")]
        for m in range(1, 13):
            month_options.append(ft.DropdownOption(key=str(m), text=_MONTH_NAMES[m]))

        self.month_dropdown = ft.Dropdown(
            label="Month",
            width=130,
            content_padding=ft.Padding(left=10, top=4, right=10, bottom=4),
            border_radius=AppTheme.RADIUS_MD,
            options=month_options,
            value="ALL",
            on_select=self.handle_month_filter_change,
        )

        # Sort field + direction (adds to multi-sort)
        self.sort_field_dropdown = ft.Dropdown(
            label="Sort Field",
            width=150,
            content_padding=ft.Padding(left=10, top=4, right=10, bottom=4),
            border_radius=AppTheme.RADIUS_MD,
            options=[
                ft.DropdownOption(key="id", text="Student ID"),
                ft.DropdownOption(key="name", text="Name"),
                ft.DropdownOption(key="admission_id", text="Admission ID"),
                ft.DropdownOption(key="mobile", text="Mobile"),
                ft.DropdownOption(key="course", text="Course"),
                ft.DropdownOption(key="date", text="Admission Date"),
                ft.DropdownOption(key="status", text="Status"),
                ft.DropdownOption(key="fee", text="Fee"),
                ft.DropdownOption(key="year", text="Year"),
                ft.DropdownOption(key="month", text="Month"),
            ],
            value="id",
        )

        self.sort_dir_dropdown = ft.Dropdown(
            label="Direction",
            width=110,
            content_padding=ft.Padding(left=10, top=4, right=10, bottom=4),
            border_radius=AppTheme.RADIUS_MD,
            options=[
                ft.DropdownOption(key="asc", text="ASC ↑"),
                ft.DropdownOption(key="desc", text="DESC ↓"),
            ],
            value="desc",
        )

        self.add_sort_btn = ft.ElevatedButton(
            content=ft.Text("Add Sort"),
            icon=ft.Icons.SORT,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                bgcolor=AppTheme.SURFACE_VARIANT,
                color=AppTheme.TEXT_PRIMARY,
                padding=ft.Padding(left=12, top=8, right=12, bottom=8),
            ),
            on_click=self.handle_add_sort,
        )

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text("Filters:", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                    self.course_dropdown,
                    self.status_dropdown,
                    self.year_dropdown,
                    self.month_dropdown,
                    ft.VerticalDivider(width=1, thickness=1, color=AppTheme.BORDER),
                    ft.Text("Sort:", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                    self.sort_field_dropdown,
                    self.sort_dir_dropdown,
                    self.add_sort_btn,
                ],
                spacing=AppTheme.PAD_SM,
                wrap=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=ft.Padding(left=AppTheme.PAD_MD, top=AppTheme.PAD_SM, right=AppTheme.PAD_MD, bottom=AppTheme.PAD_SM),
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

    # ══════════════════════════════════════════════════════════════════════
    # ACTIVE STATE BAR — Filter Chips + Sort Chips + Clear buttons
    # ══════════════════════════════════════════════════════════════════════
    def _build_active_state_bar(self) -> ft.Container:
        self.clear_filters_btn = ft.TextButton(
            content=ft.Text("Clear Filters", size=AppTheme.SIZE_CAPTION),
            icon=ft.Icons.FILTER_ALT_OFF,
            visible=False,
            on_click=self.handle_clear_filters,
        )

        self.clear_sorting_btn = ft.TextButton(
            content=ft.Text("Clear Sorting", size=AppTheme.SIZE_CAPTION),
            icon=ft.Icons.SORT,
            visible=False,
            on_click=self.handle_clear_sorting,
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("Active Filters:", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_SECONDARY),
                            self.filter_chips_row,
                            self.clear_filters_btn,
                        ],
                        spacing=AppTheme.PAD_SM,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        wrap=True,
                    ),
                    ft.Row(
                        controls=[
                            ft.Text("Active Sort:", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_SECONDARY),
                            self.sort_chips_row,
                            self.clear_sorting_btn,
                        ],
                        spacing=AppTheme.PAD_SM,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        wrap=True,
                    ),
                ],
                spacing=4,
            ),
            visible=False,  # Hidden until there's something to show
        )

    def _refresh_active_state_bar(self) -> None:
        """Rebuilds the filter and sort chip rows based on current state."""
        # ── Filter Chips ──
        filter_chips = []
        if self.current_course_id is not None:
            label = self.current_course_label or f"Course #{self.current_course_id}"
            filter_chips.append(self._make_chip(f"Course: {label}", self._remove_filter_course))
        if self.current_status:
            filter_chips.append(self._make_chip(f"Status: {self.current_status}", self._remove_filter_status))
        if self.current_year is not None:
            filter_chips.append(self._make_chip(f"Year: {self.current_year}", self._remove_filter_year))
        if self.current_month is not None:
            month_name = _MONTH_NAMES.get(self.current_month, str(self.current_month))
            filter_chips.append(self._make_chip(f"Month: {month_name}", self._remove_filter_month))

        self.filter_chips_row.controls = filter_chips
        has_filters = bool(filter_chips)
        self.clear_filters_btn.visible = has_filters

        # ── Sort Chips ──
        sort_chips = []
        default_sort = [("id", "desc")]
        is_default_sort = self.sort_keys == default_sort
        for idx, (field, direction) in enumerate(self.sort_keys):
            field_label = _SORT_FIELD_LABELS.get(field, field.title())
            dir_label = "↑" if direction == "asc" else "↓"
            chip_label = f"{field_label} {dir_label}"
            sort_chips.append(self._make_sort_chip(chip_label, idx))

        self.sort_chips_row.controls = sort_chips
        self.clear_sorting_btn.visible = not is_default_sort

        # Show/hide entire bar
        self.active_state_bar.visible = has_filters or not is_default_sort

    def _make_chip(self, label: str, on_remove) -> ft.Container:
        """Creates a removable filter chip."""
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(label, size=AppTheme.SIZE_CAPTION, color=AppTheme.PRIMARY),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE,
                        icon_size=14,
                        icon_color=AppTheme.TEXT_SECONDARY,
                        on_click=on_remove,
                        tooltip=f"Remove {label}",
                        width=22,
                        height=22,
                    ),
                ],
                spacing=2,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=AppTheme.PRIMARY_LIGHT,
            padding=ft.Padding(left=10, top=4, right=4, bottom=4),
            border_radius=AppTheme.RADIUS_PILL,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

    def _make_sort_chip(self, label: str, index: int) -> ft.Container:
        """Creates a removable sort chip."""
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(f"{index + 1}.", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_MUTED),
                    ft.Text(label, size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_PRIMARY),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE,
                        icon_size=14,
                        icon_color=AppTheme.TEXT_SECONDARY,
                        on_click=lambda _, i=index: self._remove_sort_key(i),
                        tooltip=f"Remove sort: {label}",
                        width=22,
                        height=22,
                    ),
                ],
                spacing=2,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=AppTheme.SURFACE_VARIANT,
            padding=ft.Padding(left=8, top=4, right=4, bottom=4),
            border_radius=AppTheme.RADIUS_PILL,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

    # ══════════════════════════════════════════════════════════════════════
    # FILTER / SORT CHIP REMOVAL HANDLERS
    # ══════════════════════════════════════════════════════════════════════
    def _remove_filter_course(self, e=None) -> None:
        self.current_course_id = None
        self.current_course_label = None
        self.course_dropdown.value = "ALL"
        self.current_page = 0
        self.load_data()

    def _remove_filter_status(self, e=None) -> None:
        self.current_status = None
        self.status_dropdown.value = "ALL"
        self.current_page = 0
        self.load_data()

    def _remove_filter_year(self, e=None) -> None:
        self.current_year = None
        self.year_dropdown.value = "ALL"
        self.current_page = 0
        self.load_data()

    def _remove_filter_month(self, e=None) -> None:
        self.current_month = None
        self.month_dropdown.value = "ALL"
        self.current_page = 0
        self.load_data()

    def _remove_sort_key(self, index: int, e=None) -> None:
        """Removes a single sort key by index. If all removed, resets to default."""
        if 0 <= index < len(self.sort_keys):
            self.sort_keys.pop(index)
        if not self.sort_keys:
            self.sort_keys = [("id", "desc")]
        self.current_page = 0
        self.load_data()

    # ══════════════════════════════════════════════════════════════════════
    # COURSE FILTER POPULATION
    # ══════════════════════════════════════════════════════════════════════
    def _populate_course_filter(self) -> None:
        """Populates the course dropdown filter with available courses."""
        try:
            courses, _ = self.course_controller.list_courses(limit=100, status="ACTIVE")
            options = [ft.DropdownOption(key="ALL", text="All Courses")]
            self._course_options = {}
            for c in courses:
                label = f"{c.code} - {c.name}"
                options.append(ft.DropdownOption(key=str(c.id), text=label))
                self._course_options[c.id] = label
            self.course_dropdown.options = options
        except Exception as ex:
            LogService.warning(f"Could not load course options for filter: {ex}", context=self.__class__.__name__)

    # ══════════════════════════════════════════════════════════════════════
    # PAGINATION BAR
    # ══════════════════════════════════════════════════════════════════════
    def _build_pagination_bar(self) -> ft.Container:
        self.pagination_info = ft.Text(
            "Showing 0 of 0 students",
            size=AppTheme.SIZE_CAPTION,
            color=AppTheme.TEXT_SECONDARY,
        )

        self.prev_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_LEFT,
            icon_color=AppTheme.PRIMARY,
            tooltip="Previous Page",
            disabled=True,
            on_click=self.handle_prev_page,
        )

        self.next_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_RIGHT,
            icon_color=AppTheme.PRIMARY,
            tooltip="Next Page",
            disabled=True,
            on_click=self.handle_next_page,
        )

        return ft.Container(
            content=ft.Row(
                controls=[
                    self.pagination_info,
                    ft.Row(controls=[self.prev_btn, self.next_btn], spacing=4),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            padding=ft.Padding(left=AppTheme.PAD_MD, top=4, right=AppTheme.PAD_MD, bottom=4),
        )

    # ══════════════════════════════════════════════════════════════════════
    # EMPTY / ERROR STATES
    # ══════════════════════════════════════════════════════════════════════
    def _build_empty_state(self, is_filtered: bool = False) -> ft.Container:
        if is_filtered:
            icon = ft.Icons.SEARCH_OFF
            title = "No matching students found"
            subtitle = "No student records matched the current filter/search criteria."
            action_btn = ft.ElevatedButton(
                content=ft.Text("Reset Filters"),
                icon=ft.Icons.CLEAR,
                style=ft.ButtonStyle(
                    bgcolor=AppTheme.SURFACE_VARIANT,
                    color=AppTheme.TEXT_PRIMARY,
                    shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                ),
                on_click=self.handle_reset_all,
            )
        else:
            icon = ft.Icons.PEOPLE_OUTLINE
            title = "No students registered yet"
            subtitle = "Click 'Register Student' above to add your first student record."
            action_btn = ft.ElevatedButton(
                content=ft.Text("Register Student"),
                icon=ft.Icons.PERSON_ADD,
                style=ft.ButtonStyle(
                    bgcolor=AppTheme.PRIMARY,
                    color=AppTheme.SURFACE,
                    shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                ),
                on_click=self.handle_add_student,
            )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(icon, size=64, color=AppTheme.TEXT_MUTED),
                    ft.Text(title, size=AppTheme.SIZE_H2, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                    ft.Text(subtitle, size=AppTheme.SIZE_BODY, color=AppTheme.TEXT_SECONDARY, text_align=ft.TextAlign.CENTER),
                    action_btn,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=AppTheme.PAD_MD,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            alignment=ft.Alignment.CENTER,
            expand=True,
            bgcolor=AppTheme.SURFACE,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
            padding=AppTheme.PAD_XL,
        )

    def _build_error_state(self, error_message: str) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE, size=64, color=AppTheme.DANGER),
                    ft.Text("Unable to load student directory", size=AppTheme.SIZE_H2, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                    ft.Text(error_message, size=AppTheme.SIZE_BODY, color=AppTheme.TEXT_SECONDARY, text_align=ft.TextAlign.CENTER),
                    ft.ElevatedButton(
                        content=ft.Text("Retry"),
                        icon=ft.Icons.REFRESH,
                        style=ft.ButtonStyle(
                            bgcolor=AppTheme.PRIMARY,
                            color=AppTheme.SURFACE,
                            shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                        ),
                        on_click=lambda _: self.load_data(),
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=AppTheme.PAD_MD,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            alignment=ft.Alignment.CENTER,
            expand=True,
            bgcolor=AppTheme.SURFACE,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
            padding=AppTheme.PAD_XL,
        )

    # ══════════════════════════════════════════════════════════════════════
    # DATA TABLE
    # ══════════════════════════════════════════════════════════════════════
    def _build_data_table(self) -> ft.Container:
        rows = []
        for student in self.students:
            status_text = student.status_label
            is_active = status_text in ("ACTIVE", "CONFIRMED", "ENROLLED")
            status_bg = AppTheme.SUCCESS_LIGHT if is_active else AppTheme.PRIMARY_LIGHT
            status_fg = AppTheme.SUCCESS if is_active else AppTheme.PRIMARY

            adm_display = student.candidate_number or "—"

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(
                            ft.Text(
                                adm_display,
                                weight=ft.FontWeight.BOLD if student.candidate_number else ft.FontWeight.NORMAL,
                                size=AppTheme.SIZE_BODY,
                                color=AppTheme.PRIMARY if student.candidate_number else AppTheme.TEXT_MUTED,
                            ),
                            on_double_tap=lambda e, s=student: self.handle_open_workspace(s.id),
                        ),
                        ft.DataCell(
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.ACCOUNT_CIRCLE, size=20, color=AppTheme.PRIMARY),
                                    ft.Text(student.display_name, weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_BODY),
                                ],
                                spacing=6,
                            ),
                            on_double_tap=lambda e, s=student: self.handle_open_workspace(s.id),
                        ),
                        ft.DataCell(ft.Text(student.mobile_number or "—", size=AppTheme.SIZE_BODY)),
                        ft.DataCell(
                            ft.Text(
                                student.current_course or "Not Enrolled",
                                color=AppTheme.TEXT_PRIMARY if student.current_course else AppTheme.TEXT_MUTED,
                                size=AppTheme.SIZE_BODY,
                                weight=ft.FontWeight.W_500 if student.current_course else ft.FontWeight.NORMAL,
                            )
                        ),
                        ft.DataCell(
                            ft.Text(
                                (student.latest_admission_date or student.created_at)[:10] if (student.latest_admission_date or student.created_at) else "—",
                                size=AppTheme.SIZE_CAPTION,
                                color=AppTheme.TEXT_SECONDARY,
                            )
                        ),
                        ft.DataCell(
                            ft.Container(
                                content=ft.Text(status_text, size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD, color=status_fg),
                                bgcolor=status_bg,
                                padding=ft.Padding(left=8, top=2, right=8, bottom=2),
                                border_radius=AppTheme.RADIUS_SM,
                            )
                        ),
                        ft.DataCell(
                            ft.Text(
                                student.fee_display,
                                size=AppTheme.SIZE_BODY,
                                weight=ft.FontWeight.W_500,
                                color=AppTheme.TEXT_PRIMARY if student.total_fee is not None else AppTheme.TEXT_MUTED,
                            )
                        ),
                        ft.DataCell(
                            ft.Row(
                                controls=[
                                    ft.IconButton(
                                        icon=ft.Icons.OPEN_IN_NEW,
                                        icon_color=AppTheme.PRIMARY,
                                        icon_size=18,
                                        tooltip="Open Workspace (Double-click)",
                                        on_click=lambda e, s=student: self.handle_open_workspace(s.id),
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.EDIT_OUTLINED,
                                        icon_color=AppTheme.TEXT_SECONDARY,
                                        icon_size=18,
                                        tooltip="Edit Profile",
                                        on_click=lambda e, s=student: self.handle_edit_student(s),
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE_OUTLINE,
                                        icon_color=AppTheme.DANGER,
                                        icon_size=18,
                                        tooltip="Delete Student",
                                        on_click=lambda e, s=student: self.handle_delete_student(s),
                                    ),
                                ],
                                spacing=2,
                            )
                        ),
                    ],
                    on_select_change=lambda e, s=student: self.handle_open_workspace(s.id),
                )
            )

        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Admission ID", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Student Name", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Mobile Number", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Course", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Admission Date", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Status", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Total Fee", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Actions", weight=ft.FontWeight.BOLD)),
            ],
            rows=rows,
            heading_row_color=AppTheme.SURFACE_VARIANT,
            data_row_min_height=48,
            data_row_max_height=56,
            column_spacing=20,
            horizontal_margin=16,
        )

        return ft.Container(
            content=ft.ListView(
                controls=[table],
                expand=True,
            ),
            bgcolor=AppTheme.SURFACE,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
            expand=True,
        )

    # ══════════════════════════════════════════════════════════════════════
    # DATA LOADING — Central query builder from current state
    # ══════════════════════════════════════════════════════════════════════
    def _get_active_filters(self) -> dict[str, object]:
        """Constructs filter map for controller calls from independent state."""
        offset = self.current_page * self.PAGE_SIZE
        return {
            "query": self.current_query or None,
            "course_id": self.current_course_id,
            "status": self.current_status,
            "year": self.current_year,
            "month": self.current_month,
            "sort_keys": self.sort_keys,
            "sort_by": self.sort_keys[0][0] if self.sort_keys else "id",
            "sort_dir": self.sort_keys[0][1] if self.sort_keys else "desc",
            "limit": self.PAGE_SIZE,
            "offset": offset,
        }

    def load_data(self) -> None:
        """Fetches filtered, paginated data from controller and updates UI view."""
        try:
            filters = self._get_active_filters()
            students, total = self.controller.filter_students(filters)

            self.students = students
            self.total_count = total

            # Update badge
            self.total_badge_text.value = f"Total: {self.total_count}"
            self.clear_search_btn.visible = bool(self.current_query)

            # Refresh active state chips
            self._refresh_active_state_bar()

            # Update Table or Empty State
            is_filtered = bool(
                self.current_query
                or self.current_course_id
                or self.current_status
                or self.current_year
                or self.current_month
            )
            if not self.students:
                self.table_container.content = self._build_empty_state(is_filtered=is_filtered)
            else:
                self.table_container.content = self._build_data_table()

            # Update Pagination Bar
            start_num = (self.current_page * self.PAGE_SIZE) + 1 if self.total_count > 0 else 0
            end_num = min(start_num + len(self.students) - 1, self.total_count) if self.total_count > 0 else 0
            self.pagination_info.value = f"Showing {start_num} to {end_num} of {self.total_count} students"
            self.prev_btn.disabled = self.current_page == 0
            self.next_btn.disabled = end_num >= self.total_count

            try:
                page = self.page
            except RuntimeError:
                page = None

            if page:
                self.update()

        except Exception as ex:
            LogService.error(f"Error loading student directory: {ex}", context=self.__class__.__name__)
            self.table_container.content = self._build_error_state("An internal error occurred while fetching records.")
            try:
                page = self.page
            except RuntimeError:
                page = None
            if page:
                self.update()

    # ══════════════════════════════════════════════════════════════════════
    # SEARCH HANDLERS
    # ══════════════════════════════════════════════════════════════════════
    def handle_search_change(self, e: ft.ControlEvent) -> None:
        """Flet-safe async debounced search input handling."""
        query = (self.search_field.value or "").strip()
        self._search_generation += 1
        current_gen = self._search_generation

        async def _debounced() -> None:
            await asyncio.sleep(0.3)
            # Guard against stale search query execution
            if current_gen == self._search_generation:
                self._apply_search(query)

        try:
            page = self.page
        except RuntimeError:
            page = None

        if page:
            page.run_task(_debounced)
        else:
            self._apply_search(query)

    def handle_search_submit(self, e: ft.ControlEvent) -> None:
        """Immediate search on Enter key."""
        self._search_generation += 1
        query = (self.search_field.value or "").strip()
        self._apply_search(query)

    def handle_clear_search(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Clears search query only. Preserves filters and sorting."""
        self._search_generation += 1
        self.search_field.value = ""
        self.clear_search_btn.visible = False
        self.current_query = ""
        self.current_page = 0
        self.load_data()

    def _apply_search(self, query: str) -> None:
        """Applies search query. Does NOT reset filters or sorting."""
        self.current_query = query
        self.current_page = 0
        self.load_data()

    # ══════════════════════════════════════════════════════════════════════
    # FILTER HANDLERS — Each modifies ONLY its own state
    # ══════════════════════════════════════════════════════════════════════
    def handle_course_filter_change(self, e: ft.ControlEvent) -> None:
        val = self.course_dropdown.value
        if val and val != "ALL":
            self.current_course_id = int(val)
            self.current_course_label = self._course_options.get(int(val), f"Course #{val}")
        else:
            self.current_course_id = None
            self.current_course_label = None
        self.current_page = 0
        self.load_data()

    def handle_status_filter_change(self, e: ft.ControlEvent) -> None:
        val = self.status_dropdown.value
        self.current_status = val if val and val != "ALL" else None
        self.current_page = 0
        self.load_data()

    def handle_year_filter_change(self, e: ft.ControlEvent) -> None:
        val = self.year_dropdown.value
        self.current_year = int(val) if val and val != "ALL" else None
        self.current_page = 0
        self.load_data()

    def handle_month_filter_change(self, e: ft.ControlEvent) -> None:
        val = self.month_dropdown.value
        self.current_month = int(val) if val and val != "ALL" else None
        self.current_page = 0
        self.load_data()

    # ══════════════════════════════════════════════════════════════════════
    # SORT HANDLERS — Independent from filters
    # ══════════════════════════════════════════════════════════════════════
    def handle_add_sort(self, e: ft.ControlEvent) -> None:
        """Adds or replaces a sort key. If the field already exists, updates its direction."""
        field = self.sort_field_dropdown.value or "id"
        direction = self.sort_dir_dropdown.value or "desc"

        # Check if field already exists -> update direction
        for idx, (existing_field, _) in enumerate(self.sort_keys):
            if existing_field == field:
                self.sort_keys[idx] = (field, direction)
                self.current_page = 0
                self.load_data()
                return

        # New sort key
        # If current sort is just default [("id", "desc")], replace it
        if self.sort_keys == [("id", "desc")] and field != "id":
            self.sort_keys = [(field, direction)]
        else:
            self.sort_keys.append((field, direction))

        self.current_page = 0
        self.load_data()

    def handle_clear_sorting(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Resets sorting to default. Does NOT modify filters or search."""
        self.sort_keys = [("id", "desc")]
        self.sort_field_dropdown.value = "id"
        self.sort_dir_dropdown.value = "desc"
        self.current_page = 0
        self.load_data()

    # ══════════════════════════════════════════════════════════════════════
    # CLEAR HANDLERS — Each clears ONLY its domain
    # ══════════════════════════════════════════════════════════════════════
    def handle_clear_filters(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Clears all filters. Preserves search and sorting."""
        self.current_course_id = None
        self.current_course_label = None
        self.course_dropdown.value = "ALL"
        self.current_status = None
        self.status_dropdown.value = "ALL"
        self.current_year = None
        self.year_dropdown.value = "ALL"
        self.current_month = None
        self.month_dropdown.value = "ALL"
        self.current_page = 0
        self.load_data()

    def handle_reset_all(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Full reset of search, filters, and sorting."""
        self.search_field.value = ""
        self.clear_search_btn.visible = False
        self.current_query = ""
        self.current_course_id = None
        self.current_course_label = None
        self.course_dropdown.value = "ALL"
        self.current_status = None
        self.status_dropdown.value = "ALL"
        self.current_year = None
        self.year_dropdown.value = "ALL"
        self.current_month = None
        self.month_dropdown.value = "ALL"
        self.sort_keys = [("id", "desc")]
        self.sort_field_dropdown.value = "id"
        self.sort_dir_dropdown.value = "desc"
        self.current_page = 0
        self.load_data()

    # Legacy alias for backward compatibility with empty state button
    def handle_reset_filters(self, e: Optional[ft.ControlEvent] = None) -> None:
        self.handle_reset_all(e)

    # ══════════════════════════════════════════════════════════════════════
    # EXPORT HANDLERS
    # ══════════════════════════════════════════════════════════════════════
    def handle_export_csv(self, e: ft.ControlEvent) -> None:
        """Exports currently filtered student dataset to Excel CSV format."""
        try:
            filters = self._get_active_filters()
            path = self.controller.export_students_csv(filters)
            self.show_snackbar(f"Student data exported to CSV: {path}")
        except Exception as ex:
            LogService.error(f"Error exporting CSV: {ex}", context=self.__class__.__name__)
            self.show_snackbar("Failed to export student CSV data.", is_error=True)

    def handle_export_pdf(self, e: ft.ControlEvent) -> None:
        """Exports currently filtered student dataset to PDF report format."""
        try:
            filters = self._get_active_filters()
            path = self.controller.export_students_pdf(filters)
            self.show_snackbar(f"Student data exported to PDF: {path}")
        except Exception as ex:
            LogService.error(f"Error exporting PDF: {ex}", context=self.__class__.__name__)
            self.show_snackbar("Failed to export student PDF report.", is_error=True)

    # ══════════════════════════════════════════════════════════════════════
    # PAGINATION HANDLERS
    # ══════════════════════════════════════════════════════════════════════
    def handle_prev_page(self, e: ft.ControlEvent) -> None:
        if self.current_page > 0:
            self.current_page -= 1
            self.load_data()

    def handle_next_page(self, e: ft.ControlEvent) -> None:
        if (self.current_page + 1) * self.PAGE_SIZE < self.total_count:
            self.current_page += 1
            self.load_data()

    # ══════════════════════════════════════════════════════════════════════
    # STUDENT CRUD / WORKSPACE HANDLERS
    # ══════════════════════════════════════════════════════════════════════
    def _on_student_saved(self, message: str) -> None:
        """Callback invoked AFTER modal has closed to refresh table and display snackbar."""
        self.load_data()
        self.show_snackbar(message)

    def handle_add_student(self, e: ft.ControlEvent) -> None:
        """Opens the Student Registration modal."""
        modal = StudentFormModal(
            controller=self.controller,
            on_saved=lambda: self._on_student_saved("Student registered successfully!"),
        )
        self._open_dialog(modal)

    def handle_edit_student(self, student: StudentDTO) -> None:
        """Opens the Student Edit modal."""
        modal = StudentFormModal(
            controller=self.controller,
            on_saved=lambda: self._on_student_saved("Student profile updated successfully!"),
            student=student,
        )
        self._open_dialog(modal)

    def handle_open_workspace(self, student_id: int) -> None:
        """Opens the full Student Workspace (Blueprint Part 05)."""
        workspace = StudentWorkspaceDialog(
            controller=self.controller,
            student_id=student_id,
            on_refresh_required=self.load_data,
        )
        self._open_dialog(workspace)

    def handle_delete_student(self, student: StudentDTO) -> None:
        """Opens Delete Confirmation Dialog with ERP foreign key & audit rules."""
        def confirm_delete(e):
            msg = ""
            err = False
            try:
                self.controller.delete_student(student.id)
                msg = f"Student '{student.display_name}' deleted successfully."
            except (ValidationError, ConflictError, ServiceError) as ex:
                msg = str(ex)
                err = True
            except Exception as ex:
                LogService.error(f"Error during student deletion: {ex}", context="StudentDelete")
                msg = "An unexpected error occurred during deletion."
                err = True
            finally:
                # Pop confirmation dialog FIRST
                try:
                    if self.page:
                        self.page.pop_dialog()
                except RuntimeError:
                    pass

                # Then show snackbar and refresh table
                if msg:
                    self.show_snackbar(msg, is_error=err)
                if not err:
                    self.load_data()

        def cancel_delete(e):
            try:
                if self.page:
                    self.page.pop_dialog()
            except RuntimeError:
                pass

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.WARNING_AMBER, color=AppTheme.DANGER, size=24),
                    ft.Text("Confirm Student Deletion", size=AppTheme.SIZE_H2, weight=ft.FontWeight.BOLD),
                ],
                spacing=AppTheme.PAD_SM,
            ),
            content=ft.Container(
                width=420,
                content=ft.Column(
                    controls=[
                        ft.Text(
                            f"Are you sure you want to delete student '{student.display_name}' (ID: #{student.id})?",
                            size=AppTheme.SIZE_BODY,
                            color=AppTheme.TEXT_PRIMARY,
                        ),
                        ft.Text(
                            "ERP Policy: Student profiles with linked admission history cannot be deleted.",
                            size=AppTheme.SIZE_CAPTION,
                            color=AppTheme.TEXT_SECONDARY,
                        ),
                    ],
                    spacing=AppTheme.PAD_SM,
                    tight=True,
                ),
            ),
            actions=[
                ft.TextButton(content=ft.Text("Cancel"), on_click=cancel_delete),
                ft.ElevatedButton(
                    content=ft.Text("Delete Record"),
                    style=ft.ButtonStyle(bgcolor=AppTheme.DANGER, color=AppTheme.SURFACE),
                    on_click=confirm_delete,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._open_dialog(dialog)

    def _open_dialog(self, dialog: ft.AlertDialog) -> None:
        try:
            page = self.page
        except RuntimeError:
            page = None
        if not page:
            return
        page.show_dialog(dialog)
