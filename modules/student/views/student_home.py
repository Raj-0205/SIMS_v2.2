# modules/student/views/student_home.py

from __future__ import annotations
import asyncio
from typing import Optional
import flet as ft

from core.exceptions import ValidationError, ConflictError, ServiceError
from core.logger.service import LogService
from modules.student.controller import StudentController
from modules.student.dto import StudentDTO
from modules.student.views.student_form_modal import StudentFormModal
from modules.student.views.student_workspace_dialog import StudentWorkspaceDialog
from ui.themes.theme import AppTheme

__all__ = ["StudentHome"]


class StudentHome(ft.Container):
    """
    Main Student Management Screen (Student Directory).
    Follows Part 05 of the SIMS Blueprint:
    Provides fast indexed search, database-level pagination, real-time KPI badge,
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

        # State
        self.current_page: int = 0
        self.current_query: str = ""
        self.total_count: int = 0
        self.students: list[StudentDTO] = []
        self._search_generation: int = 0

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

    def _build_summary_card(self) -> ft.Container:
        self.total_badge_text = ft.Text(
            "Total Students: 0",
            size=AppTheme.SIZE_BODY,
            weight=ft.FontWeight.BOLD,
            color=AppTheme.PRIMARY,
        )

        self.clear_btn = ft.IconButton(
            icon=ft.Icons.CLEAR,
            icon_size=16,
            tooltip="Clear search",
            visible=False,
            on_click=self.handle_clear_search,
        )

        self.search_field = ft.TextField(
            hint_text="Search by name, mobile, email, or ID...",
            prefix_icon=ft.Icons.SEARCH,
            suffix=self.clear_btn,
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
            content_padding=ft.Padding(left=12, top=8, right=12, bottom=8),
            width=400,
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

    def _build_data_table(self) -> ft.Container:
        rows = []
        for student in self.students:
            status_text = student.status_label
            is_active = status_text in ("ACTIVE", "CONFIRMED", "ENROLLED")
            status_bg = AppTheme.SUCCESS_LIGHT if is_active else AppTheme.PRIMARY_LIGHT
            status_fg = AppTheme.SUCCESS if is_active else AppTheme.PRIMARY

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(f"#{student.id}", weight=ft.FontWeight.W_500, size=AppTheme.SIZE_BODY)),
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
                                student.created_at[:10] if len(student.created_at) >= 10 else student.created_at or "—",
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
                ft.DataColumn(ft.Text("ID", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Student Name", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Mobile Number", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Current Course", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Registration Date", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Status", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Actions", weight=ft.FontWeight.BOLD)),
            ],
            rows=rows,
            heading_row_color=AppTheme.SURFACE_VARIANT,
            data_row_min_height=48,
            data_row_max_height=56,
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
            self.clear_btn.visible = bool(self.current_query)

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
        """Clears search filter and reloads normal student directory."""
        self._search_generation += 1
        self.search_field.value = ""
        self.clear_btn.visible = False
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
