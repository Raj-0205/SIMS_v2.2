# modules/student/views/student_home.py

from __future__ import annotations
import threading
from typing import Optional
import flet as ft

from core.logger.service import LogService
from modules.student.controller import StudentController
from modules.student.dto import StudentDTO
from modules.student.views.student_form_modal import StudentFormModal
from modules.student.views.student_detail_dialog import StudentDetailDialog
from ui.themes.theme import AppTheme

__all__ = ["StudentHome"]


class StudentHome(ft.Container):
    """
    Main Student Management Screen.
    Provides directory search, database-level pagination, real-time summary KPIs,
    clean empty-states, error states, and modal workflows for Add/Edit/View.
    """

    PAGE_SIZE: int = 15

    def __init__(self) -> None:
        super().__init__(
            expand=True,
            padding=AppTheme.PAD_LG,
            bgcolor=AppTheme.BACKGROUND,
        )

        self.controller = StudentController()

        # State
        self.current_page: int = 0
        self.current_query: str = ""
        self.total_count: int = 0
        self.students: list[StudentDTO] = []
        self._search_timer: Optional[threading.Timer] = None

        # UI Components
        self.header = self._build_header()
        self.summary_card = self._build_summary_card()
        self.table_container = ft.Container(expand=True)
        self.pagination_bar = self._build_pagination_bar()

        self.content = ft.Column(
            controls=[
                self.header,
                self.summary_card,
                self.table_container,
                self.pagination_bar,
            ],
            spacing=AppTheme.PAD_MD,
            expand=True,
        )

    def did_mount(self) -> None:
        """Called when the control is mounted to the page tree."""
        self.load_data()

    def show_snackbar(self, message: str, is_error: bool = False) -> None:
        """Displays transient feedback snackbar to the user."""
        if not self.page:
            return
        bg_color = AppTheme.DANGER if is_error else AppTheme.SUCCESS
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message, color=AppTheme.SURFACE),
            bgcolor=bg_color,
        )
        self.page.snack_bar.open = True
        self.page.update()

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
                                    "Manage institute student records, registrations, and contact info",
                                    size=AppTheme.SIZE_CAPTION,
                                    color=AppTheme.TEXT_SECONDARY,
                                ),
                            ],
                            spacing=2,
                        ),
                    ],
                    spacing=AppTheme.PAD_SM,
                ),
                ft.ElevatedButton(
                    content=ft.Text("Add Student"),
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
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

    def _build_summary_card(self) -> ft.Container:
        self.total_badge_text = ft.Text(
            "Total Students: 0",
            size=AppTheme.SIZE_BODY,
            weight=ft.FontWeight.BOLD,
            color=AppTheme.PRIMARY,
        )

        self.search_field = ft.TextField(
            hint_text="Search by name, mobile, email, or ID...",
            prefix_icon=ft.Icons.SEARCH,
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
            content_padding=ft.Padding(left=12, top=8, right=12, bottom=8),
            width=360,
            on_change=self.handle_search_change,
            on_submit=self.handle_search_submit,
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
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=AppTheme.PAD_MD,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

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

    def _build_empty_state(self, is_search: bool = False) -> ft.Container:
        if is_search:
            icon = ft.Icons.SEARCH_OFF
            title = "No matching students found"
            subtitle = f"No student records matched '{self.current_query}'."
            action_btn = ft.ElevatedButton(
                content=ft.Text("Clear Search"),
                icon=ft.Icons.CLEAR,
                style=ft.ButtonStyle(
                    bgcolor=AppTheme.SURFACE_VARIANT,
                    color=AppTheme.TEXT_PRIMARY,
                    shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                ),
                on_click=self.handle_clear_search,
            )
        else:
            icon = ft.Icons.PEOPLE_OUTLINE
            title = "No students registered yet"
            subtitle = "Click 'Add Student' above to register your first student record."
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

    def _build_data_table(self) -> ft.Container:
        rows = []
        for student in self.students:
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(str(student.id), weight=ft.FontWeight.W_500, size=AppTheme.SIZE_BODY)),
                        ft.DataCell(
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.ACCOUNT_CIRCLE, size=20, color=AppTheme.PRIMARY),
                                    ft.Text(student.display_name, weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_BODY),
                                ],
                                spacing=6,
                            )
                        ),
                        ft.DataCell(ft.Text(student.mobile_number, size=AppTheme.SIZE_BODY)),
                        ft.DataCell(ft.Text(student.email or "—", color=AppTheme.TEXT_SECONDARY if not student.email else AppTheme.TEXT_PRIMARY, size=AppTheme.SIZE_BODY)),
                        ft.DataCell(ft.Text(student.created_at[:10] if len(student.created_at) >= 10 else student.created_at, size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY)),
                        ft.DataCell(
                            ft.Row(
                                controls=[
                                    ft.IconButton(
                                        icon=ft.Icons.VISIBILITY_OUTLINED,
                                        icon_color=AppTheme.PRIMARY,
                                        icon_size=18,
                                        tooltip="View Details",
                                        on_click=lambda e, s=student: self.handle_view_student(s),
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.EDIT_OUTLINED,
                                        icon_color=AppTheme.TEXT_SECONDARY,
                                        icon_size=18,
                                        tooltip="Edit Student",
                                        on_click=lambda e, s=student: self.handle_edit_student(s),
                                    ),
                                ],
                                spacing=2,
                            )
                        ),
                    ]
                )
            )

        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("ID", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Name", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Mobile Number", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Email", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Created", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Actions", weight=ft.FontWeight.BOLD)),
            ],
            rows=rows,
            heading_row_color=AppTheme.SURFACE_VARIANT,
            data_row_min_height=44,
            data_row_max_height=52,
            column_spacing=24,
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

    def load_data(self) -> None:
        """Fetches paginated data from controller and updates UI view."""
        offset = self.current_page * self.PAGE_SIZE

        try:
            if self.current_query:
                students, total = self.controller.search_students_paged(
                    self.current_query, limit=self.PAGE_SIZE, offset=offset
                )
            else:
                students, total = self.controller.list_students(
                    limit=self.PAGE_SIZE, offset=offset
                )

            self.students = students
            self.total_count = total

            # Update badge
            self.total_badge_text.value = f"Total Students: {self.total_count}"

            # Update Table or Empty State
            if not self.students:
                self.table_container.content = self._build_empty_state(is_search=bool(self.current_query))
            else:
                self.table_container.content = self._build_data_table()

            # Update Pagination Bar
            start_num = (self.current_page * self.PAGE_SIZE) + 1 if self.total_count > 0 else 0
            end_num = min(start_num + len(self.students) - 1, self.total_count) if self.total_count > 0 else 0
            self.pagination_info.value = f"Showing {start_num} to {end_num} of {self.total_count} students"
            self.prev_btn.disabled = self.current_page == 0
            self.next_btn.disabled = end_num >= self.total_count

            if self.page:
                self.update()

        except Exception as ex:
            LogService.error(f"Error loading student directory: {ex}", context=self.__class__.__name__)
            self.table_container.content = self._build_error_state("An internal error occurred while fetching records.")
            if self.page:
                self.update()

    def handle_search_change(self, e: ft.ControlEvent) -> None:
        """Debounced search input handling (300ms delay)."""
        query = (self.search_field.value or "").strip()
        if self._search_timer:
            self._search_timer.cancel()

        self._search_timer = threading.Timer(0.3, self._apply_search, args=[query])
        self._search_timer.start()

    def handle_search_submit(self, e: ft.ControlEvent) -> None:
        """Immediate search on Enter key."""
        if self._search_timer:
            self._search_timer.cancel()
        query = (self.search_field.value or "").strip()
        self._apply_search(query)

    def handle_clear_search(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Clears search filter and reloads normal student directory."""
        if self._search_timer:
            self._search_timer.cancel()
        self.search_field.value = ""
        self.current_query = ""
        self.current_page = 0
        self.load_data()

    def _apply_search(self, query: str) -> None:
        self.current_query = query
        self.current_page = 0
        self.load_data()

    def handle_prev_page(self, e: ft.ControlEvent) -> None:
        if self.current_page > 0:
            self.current_page -= 1
            self.load_data()

    def handle_next_page(self, e: ft.ControlEvent) -> None:
        if (self.current_page + 1) * self.PAGE_SIZE < self.total_count:
            self.current_page += 1
            self.load_data()

    def _on_student_saved(self, message: str) -> None:
        """Callback invoked when student is successfully added or updated."""
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

    def handle_view_student(self, student: StudentDTO) -> None:
        """Opens the Student Details dialog."""
        dialog = StudentDetailDialog(student=student)
        self._open_dialog(dialog)

    def _open_dialog(self, dialog: ft.AlertDialog) -> None:
        if not self.page:
            return
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()
