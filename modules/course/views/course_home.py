# modules/course/views/course_home.py

from __future__ import annotations
from typing import Optional
import flet as ft

from core.logger.service import LogService
from ui.themes.theme import AppTheme
from modules.course.controller import CourseController
from modules.course.dto import CourseDTO
from modules.course.views.course_form_modal import CourseFormModal
from modules.course.views.course_fee_dialog import CourseFeeDialog
from modules.course.views.course_detail_dialog import CourseDetailDialog

__all__ = ["CourseHome"]


class CourseHome(ft.Column):
    """
    Enterprise Course Master Workspace.
    Provides responsive course cards, live search, category/status filtering,
    operational statistics, and administration controls.
    """

    def __init__(self) -> None:
        super().__init__(spacing=16, expand=True, scroll=ft.ScrollMode.AUTO)
        self.controller = CourseController()

        # State Variables
        self.current_search: str = ""
        self.current_category: str = "ALL"
        self.current_status: str = "ALL"
        self.page_size: int = 50
        self.current_page_idx: int = 0

        # UI Control References
        self.kpi_total_text = ft.Text("0", size=20, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY)
        self.kpi_active_text = ft.Text("0", size=20, weight=ft.FontWeight.BOLD, color=AppTheme.SUCCESS)
        self.kpi_inactive_text = ft.Text("0", size=20, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_MUTED)
        self.kpi_enrollments_text = ft.Text("0", size=20, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY)

        self.cards_grid = ft.ResponsiveRow(spacing=16, run_spacing=16)
        self.empty_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.SEARCH_OFF, size=48, color=AppTheme.TEXT_MUTED),
                    ft.Text("No courses found matching criteria.", size=AppTheme.SIZE_BODY, color=AppTheme.TEXT_SECONDARY),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            padding=ft.Padding(32, 32, 32, 32),
            alignment=ft.Alignment(0, 0),
            visible=False,
        )

        # Build Layout Controls
        self._build_header()
        self._build_kpi_row()
        self._build_filter_bar()

        self.controls = [
            self.header_row,
            self.kpi_row,
            self.filter_bar,
            ft.Divider(height=4, color=AppTheme.BORDER),
            self.cards_grid,
            self.empty_container,
        ]

    def did_mount(self) -> None:
        """Invoked when control is attached to the page."""
        self.refresh_data()

    def _build_header(self) -> None:
        self.header_row = ft.Row(
            controls=[
                ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.SCHOOL, color=AppTheme.PRIMARY, size=28),
                                ft.Text("Courses Master", size=AppTheme.SIZE_H1, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                            ],
                            spacing=8,
                        ),
                        ft.Text(
                            "Manage courses, institute pricing, availability, and batch assignments",
                            size=AppTheme.SIZE_BODY,
                            color=AppTheme.TEXT_SECONDARY,
                        ),
                    ],
                    spacing=2,
                ),
                ft.ElevatedButton(
                    content=ft.Text("Add New Course"),
                    icon=ft.Icons.ADD_BOX,
                    bgcolor=AppTheme.PRIMARY,
                    color=AppTheme.SURFACE,
                    on_click=self._handle_add_course,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _build_kpi_row(self) -> None:
        self.kpi_row = ft.Row(
            controls=[
                self._kpi_card("Total Courses", self.kpi_total_text, ft.Icons.AUTO_STORIES, AppTheme.PRIMARY),
                self._kpi_card("Active Offerings", self.kpi_active_text, ft.Icons.CHECK_CIRCLE, AppTheme.SUCCESS),
                self._kpi_card("Inactive / Closed", self.kpi_inactive_text, ft.Icons.ARCHIVE, AppTheme.TEXT_MUTED),
                self._kpi_card("Total Enrollments", self.kpi_enrollments_text, ft.Icons.APP_REGISTRATION, AppTheme.PRIMARY_HOVER),
            ],
            spacing=12,
        )

    def _kpi_card(self, label: str, value_ctrl: ft.Text, icon: str, icon_color: str) -> ft.Control:
        return ft.Container(
            expand=True,
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(icon, color=icon_color, size=24),
                        bgcolor=AppTheme.SURFACE_VARIANT,
                        padding=ft.Padding(8, 8, 8, 8),
                        border_radius=AppTheme.RADIUS_MD,
                    ),
                    ft.Column(
                        controls=[
                            value_ctrl,
                            ft.Text(label, size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                        ],
                        spacing=0,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=ft.Padding(14, 12, 14, 12),
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

    def _build_filter_bar(self) -> None:
        self.search_input = ft.TextField(
            hint_text="Search by code or course name...",
            prefix_icon=ft.Icons.SEARCH,
            border_radius=AppTheme.RADIUS_MD,
            dense=True,
            on_change=self._handle_search_change,
            expand=True,
        )

        # Dynamic Category Dropdown
        categories = ["ALL"] + self.controller.get_categories()
        self.category_dropdown = ft.Dropdown(
            options=[ft.DropdownOption(key=c, text=c if c != "ALL" else "All Categories") for c in categories],
            value="ALL",
            border_radius=AppTheme.RADIUS_MD,
            dense=True,
            width=180,
            on_select=self._handle_filter_change,
        )

        self.status_dropdown = ft.Dropdown(
            options=[
                ft.DropdownOption(key="ALL", text="All Status"),
                ft.DropdownOption(key="ACTIVE", text="Active Only"),
                ft.DropdownOption(key="INACTIVE", text="Inactive Only"),
            ],
            value="ALL",
            border_radius=AppTheme.RADIUS_MD,
            dense=True,
            width=150,
            on_select=self._handle_filter_change,
        )

        self.filter_bar = ft.Row(
            controls=[
                self.search_input,
                self.category_dropdown,
                self.status_dropdown,
            ],
            spacing=12,
        )

    def _handle_search_change(self, e: ft.ControlEvent) -> None:
        self.current_search = str(self.search_input.value or "").strip()
        self.refresh_data()

    def _handle_filter_change(self, e: ft.ControlEvent) -> None:
        self.current_category = str(self.category_dropdown.value or "ALL")
        self.current_status = str(self.status_dropdown.value or "ALL")
        self.refresh_data()

    def refresh_data(self) -> None:
        """Fetches courses, calculates summaries, and re-renders course cards."""
        try:
            # 1. Update KPI Summary
            overall = self.controller.get_overall_summary()
            self.kpi_total_text.value = str(overall.get("total_courses", 0))
            self.kpi_active_text.value = str(overall.get("active_courses", 0))
            self.kpi_inactive_text.value = str(overall.get("inactive_courses", 0))
            self.kpi_enrollments_text.value = str(overall.get("total_enrollments", 0))

            # 2. Fetch Filtered Courses
            courses, total_count = self.controller.list_courses(
                limit=self.page_size,
                offset=self.current_page_idx * self.page_size,
                status=self.current_status if self.current_status != "ALL" else None,
                category=self.current_category if self.current_category != "ALL" else None,
                search=self.current_search if self.current_search else None,
            )

            # 3. Render Cards
            self.cards_grid.controls.clear()
            if not courses:
                self.empty_container.visible = True
            else:
                self.empty_container.visible = False
                for course in courses:
                    summary = self.controller.get_operational_summary(course.id)
                    card = self._create_course_card(course, summary)
                    self.cards_grid.controls.append(card)

            # Update category options if new categories were created
            current_cats = ["ALL"] + self.controller.get_categories()
            existing_keys = [opt.key for opt in self.category_dropdown.options]
            if current_cats != existing_keys:
                self.category_dropdown.options = [
                    ft.DropdownOption(key=c, text=c if c != "ALL" else "All Categories") for c in current_cats
                ]

            try:
                self.update()
            except Exception:
                pass

        except Exception as exc:
            LogService.error(f"Failed to refresh CourseHome: {exc}", context=self.__class__.__name__)

    def _create_course_card(self, course: CourseDTO, summary) -> ft.Control:
        """Generates a responsive course master card."""
        status_color = AppTheme.SUCCESS if course.is_active else AppTheme.TEXT_MUTED
        status_text = "ACTIVE" if course.is_active else "INACTIVE"

        # Category Color Coding
        cat_color = AppTheme.PRIMARY
        cat_upper = course.category.upper()
        if "IT LITERACY" in cat_upper:
            cat_color = "#059669"  # Emerald
        elif "PROGRAMMING" in cat_upper or "DEVELOPMENT" in cat_upper:
            cat_color = "#2563EB"  # Blue
        elif "ACCOUNTING" in cat_upper or "FINANCE" in cat_upper:
            cat_color = "#D97706"  # Amber
        elif "DESIGN" in cat_upper:
            cat_color = "#7C3AED"  # Purple
        elif "OFFICE" in cat_upper:
            cat_color = "#0D9488"  # Teal

        card_content = ft.Container(
            content=ft.Column(
                controls=[
                    # Header: Name, Code, Category Chip
                    ft.Row(
                        controls=[
                            ft.Text(
                                course.name,
                                size=AppTheme.SIZE_H3,
                                weight=ft.FontWeight.BOLD,
                                color=AppTheme.TEXT_PRIMARY,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                expand=True,
                            ),
                            ft.Container(
                                content=ft.Text(f"● {status_text}", size=10, weight=ft.FontWeight.BOLD, color=status_color),
                                bgcolor=AppTheme.SURFACE_VARIANT,
                                padding=ft.Padding(6, 2, 6, 2),
                                border_radius=AppTheme.RADIUS_SM,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Text(course.code, size=11, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                                bgcolor=AppTheme.PRIMARY_LIGHT,
                                padding=ft.Padding(6, 2, 6, 2),
                                border_radius=AppTheme.RADIUS_SM,
                            ),
                            ft.Container(
                                content=ft.Text(course.category, size=11, weight=ft.FontWeight.W_500, color=cat_color),
                                bgcolor=AppTheme.SURFACE_VARIANT,
                                padding=ft.Padding(6, 2, 6, 2),
                                border_radius=AppTheme.RADIUS_SM,
                                border=ft.Border.all(1, AppTheme.BORDER),
                            ),
                        ],
                        spacing=6,
                    ),
                    ft.Divider(height=6, color=AppTheme.BORDER),
                    # Body: Duration & Operational Summary
                    ft.Row(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.TIMER_OUTLINED, size=14, color=AppTheme.TEXT_MUTED),
                                    ft.Text(course.duration or "Self-paced", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                                ],
                                spacing=4,
                            ),
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.GROUP_WORK_OUTLINED, size=14, color=AppTheme.TEXT_MUTED),
                                    ft.Text(f"{summary.active_batch_count} Batches", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                                ],
                                spacing=4,
                            ),
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.APP_REGISTRATION, size=14, color=AppTheme.TEXT_MUTED),
                                    ft.Text(f"{summary.total_admissions_count} Enrollments", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                                ],
                                spacing=4,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Container(height=4),
                    # Pricing Box
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Column(
                                    controls=[
                                        ft.Text("Institute Fee", size=10, color=AppTheme.TEXT_MUTED, weight=ft.FontWeight.W_500),
                                        ft.Text(f"₹{course.base_fee:,.2f}", size=18, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                                    ],
                                    spacing=0,
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.LOCK_RESET,
                                    icon_color=AppTheme.PRIMARY,
                                    icon_size=18,
                                    tooltip="Change Institute Fee",
                                    on_click=lambda e, c=course: self._handle_change_fee(c),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        bgcolor=AppTheme.SURFACE_VARIANT,
                        padding=ft.Padding(10, 6, 10, 6),
                        border_radius=AppTheme.RADIUS_SM,
                    ),
                    ft.Divider(height=6, color=AppTheme.BORDER),
                    # Actions Footer
                    ft.Row(
                        controls=[
                            ft.ElevatedButton(
                                content=ft.Text("View Details"),
                                icon=ft.Icons.VISIBILITY,
                                bgcolor=AppTheme.PRIMARY,
                                color=AppTheme.SURFACE,
                                on_click=lambda e, cid=course.id: self._handle_view_details(cid),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.EDIT_OUTLINED,
                                icon_color=AppTheme.TEXT_SECONDARY,
                                tooltip="Edit Course Descriptors",
                                on_click=lambda e, c=course: self._handle_edit_course(c),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ],
                spacing=8,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=ft.Padding(14, 12, 14, 12),
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=4,
                color="#0F172A0A",
                offset=ft.Offset(0, 2),
            ),
        )

        return ft.Container(
            content=card_content,
            col={"xs": 12, "sm": 6, "md": 4, "lg": 4, "xl": 3},
        )

    def _handle_add_course(self, e: ft.ControlEvent) -> None:
        if not self.page:
            return
        modal = CourseFormModal(on_saved=lambda cid: self.refresh_data(), page=self.page)
        self.page.open(modal)

    def _handle_edit_course(self, course: CourseDTO) -> None:
        if not self.page:
            return
        modal = CourseFormModal(course=course, on_saved=lambda cid: self.refresh_data(), page=self.page)
        self.page.open(modal)

    def _handle_change_fee(self, course: CourseDTO) -> None:
        if not self.page:
            return
        dialog = CourseFeeDialog(course=course, on_fee_updated=lambda cid: self.refresh_data(), page=self.page)
        self.page.open(dialog)

    def _handle_view_details(self, course_id: int) -> None:
        if not self.page:
            return
        dialog = CourseDetailDialog(course_id=course_id, on_course_mutated=self.refresh_data, page=self.page)
        self.page.open(dialog)
