# modules/admission/views/admission_home.py

from __future__ import annotations
from pathlib import Path
from typing import Optional, Any
import flet as ft

from core.logger.service import LogService
from ui.themes.theme import AppTheme
from modules.admission.controller import AdmissionController
from modules.admission.constants import AdmissionStatus, ADMISSION_STATUS_COLORS
from modules.admission.dto import AdmissionDTO
from modules.admission.views.admission_form_modal import AdmissionFormModal
from modules.admission.views.admission_workspace_dialog import AdmissionWorkspaceDialog
from modules.course.controller import CourseController
from shared.utils.os_helper import open_path_externally

__all__ = ["AdmissionHome"]


class AdmissionHome(ft.Container):
    """
    Official SIMS v2.2 Admission Management Directory.
    Form-First Operational Directory:
    - Header with primary 'New Admission' button and Refresh.
    - Prominent centered Universal Search Bar.
    - Minimal useful filters (Course, Status).
    - Tabular Admission records with candidate badges (YYYY-NNN) and semantic status colors.
    - Direct access to 360° Admission Workspace on row click or action button.
    - Clean pagination footer.
    """

    def __init__(self) -> None:
        super().__init__(expand=True, padding=AppTheme.PAD_LG)

        self.controller = AdmissionController()
        self.course_controller = CourseController()

        # State Variables
        self.admissions: list[AdmissionDTO] = []
        self.total_count: int = 0
        self.current_page: int = 0
        self.page_size: int = 25

        # Filter State
        self.search_query: str = ""
        self.selected_status: str = "ALL"
        self.selected_course_id: Optional[int] = None

        # Build UI Structure
        self._build_ui()

    def _build_ui(self) -> None:
        # ----------------------------------------------------
        # 1. Header (Title, Subtitle & Primary Action)
        # ----------------------------------------------------
        self.title_text = ft.Text(
            "Admissions",
            size=AppTheme.SIZE_H1,
            weight=ft.FontWeight.BOLD,
            color=AppTheme.TEXT_PRIMARY,
        )
        self.subtitle_text = ft.Text(
            "Manage student admissions, candidate numbering, batch enrollments, and status lifecycle.",
            size=AppTheme.SIZE_BODY,
            color=AppTheme.TEXT_SECONDARY,
        )

        self.new_adm_btn = ft.ElevatedButton(
            content=ft.Text("New Admission", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.W_600),
            icon=ft.Icons.PERSON_ADD_ALT_1,
            style=ft.ButtonStyle(
                bgcolor=AppTheme.PRIMARY,
                color=AppTheme.SURFACE,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                padding=ft.Padding(left=18, top=12, right=18, bottom=12),
            ),
            on_click=self.handle_new_admission,
        )

        self.refresh_btn = ft.IconButton(
            icon=ft.Icons.REFRESH,
            icon_size=20,
            icon_color=AppTheme.TEXT_SECONDARY,
            tooltip="Refresh Directory",
            on_click=lambda e: self.load_data(),
        )

        self.export_excel_btn = ft.FilledButton(
            content=ft.Text("Export Excel (.xlsx)", size=AppTheme.SIZE_CAPTION),
            icon=ft.Icons.TABLE_VIEW,
            style=ft.ButtonStyle(
                bgcolor=AppTheme.PRIMARY,
                color=AppTheme.SURFACE,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
            ),
            on_click=self.handle_export_excel,
        )

        header_row = ft.Row(
            controls=[
                ft.Column(controls=[self.title_text, self.subtitle_text], spacing=2),
                ft.Row(
                    controls=[
                        self.export_excel_btn,
                        self.refresh_btn,
                        self.new_adm_btn,
                    ],
                    spacing=AppTheme.PAD_SM,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        # ----------------------------------------------------
        # 2. Universal Search Bar
        # ----------------------------------------------------
        self.search_field = ft.TextField(
            hint_text="Search by Candidate No (YYYY-NNN), Student Name, Mobile Number, or Course...",
            prefix_icon=ft.Icons.SEARCH,
            suffix=ft.IconButton(
                icon=ft.Icons.CLEAR,
                icon_size=16,
                tooltip="Clear search",
                on_click=self.handle_clear_search,
            ),
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
            on_change=self.handle_search_change,
            expand=True,
        )

        search_container = ft.Container(
            content=self.search_field,
            padding=ft.Padding(0, AppTheme.PAD_SM, 0, AppTheme.PAD_XS),
        )

        # ----------------------------------------------------
        # 3. Minimal Useful Filter Bar
        # ----------------------------------------------------
        self.status_filter = ft.Dropdown(
            label="Admission Status",
            value="ALL",
            width=170,
            text_size=AppTheme.SIZE_BODY,
            border_radius=AppTheme.RADIUS_MD,
            options=[
                ft.DropdownOption(key="ALL", text="All Statuses"),
                ft.DropdownOption(key="ACTIVE", text="Active Workflow"),
                ft.DropdownOption(key="REGISTERED", text="Registered"),
                ft.DropdownOption(key="CONFIRMED", text="Confirmed"),
                ft.DropdownOption(key="DRAFT", text="Draft"),
                ft.DropdownOption(key="CANCELLED", text="Cancelled"),
            ],
            on_select=self.handle_filter_change,
        )

        self.course_filter = ft.Dropdown(
            label="Filter by Course",
            value="ALL",
            width=240,
            text_size=AppTheme.SIZE_BODY,
            border_radius=AppTheme.RADIUS_MD,
            options=[ft.DropdownOption(key="ALL", text="All Courses")],
            on_select=self.handle_filter_change,
        )

        self.reset_filters_btn = ft.TextButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.FILTER_ALT_OFF, size=16, color=AppTheme.TEXT_SECONDARY),
                    ft.Text("Reset Filters", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                ],
                spacing=4,
            ),
            on_click=self.handle_reset_filters,
        )

        filter_row = ft.Row(
            controls=[
                self.status_filter,
                self.course_filter,
                self.reset_filters_btn,
            ],
            spacing=AppTheme.PAD_MD,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # ----------------------------------------------------
        # 4. Data Table
        # ----------------------------------------------------
        self.table_columns = [
            ft.DataColumn(label=ft.Text("Candidate No", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
            ft.DataColumn(label=ft.Text("Student Name", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
            ft.DataColumn(label=ft.Text("Mobile Number", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
            ft.DataColumn(label=ft.Text("Course", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
            ft.DataColumn(label=ft.Text("Batch", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
            ft.DataColumn(label=ft.Text("Admission Date", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
            ft.DataColumn(label=ft.Text("Status", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
            ft.DataColumn(label=ft.Text("Fee / Paid / Balance", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
            ft.DataColumn(label=ft.Text("Action", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
        ]

        self.data_table = ft.DataTable(
            columns=self.table_columns,
            rows=[],
            heading_row_color=AppTheme.SURFACE_VARIANT,
            heading_row_height=42,
            data_row_min_height=48,
            border=ft.Border.all(1, AppTheme.BORDER),
            border_radius=AppTheme.RADIUS_MD,
            vertical_lines=ft.BorderSide(0.5, AppTheme.BORDER),
            horizontal_lines=ft.BorderSide(0.5, AppTheme.BORDER),
        )

        self.empty_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.SEARCH_OFF, size=48, color=AppTheme.TEXT_MUTED),
                    ft.Text("No matching admissions found", size=AppTheme.SIZE_H3, weight=ft.FontWeight.W_600, color=AppTheme.TEXT_SECONDARY),
                    ft.Text("Click 'New Admission' above to register a candidate.", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED),
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
        # 5. Pagination Footer
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
                ft.DropdownOption(key="10", text="10 / page"),
                ft.DropdownOption(key="25", text="25 / page"),
                ft.DropdownOption(key="50", text="50 / page"),
                ft.DropdownOption(key="100", text="100 / page"),
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
                    controls=[
                        self.page_size_dropdown,
                        self.prev_page_btn,
                        self.next_page_btn,
                    ],
                    spacing=AppTheme.PAD_XS,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        # ----------------------------------------------------
        # Assemble Main Layout
        # ----------------------------------------------------
        self.content = ft.Column(
            controls=[
                header_row,
                ft.Divider(height=1, color=AppTheme.BORDER),
                search_container,
                filter_row,
                self.table_container,
                ft.Divider(height=1, color=AppTheme.BORDER),
                pagination_row,
            ],
            spacing=AppTheme.PAD_MD,
            expand=True,
        )

    @property
    def safe_page(self) -> Optional[ft.Page]:
        try:
            return getattr(self, "_root_page", None) or self.page or getattr(self, "_page", None)
        except (RuntimeError, AttributeError):
            return getattr(self, "_root_page", None) or getattr(self, "_page", None)

    def did_mount(self) -> None:
        self.load_data()

    def _safe_update(self) -> None:
        p = self.safe_page
        if p:
            try:
                self.update()
            except RuntimeError:
                pass

    def load_data(self) -> None:
        """Loads course filter options and the filtered admissions list."""
        self._load_course_options()
        self._load_admissions()

    def _load_course_options(self) -> None:
        try:
            courses, _ = self.course_controller.list_courses(limit=200)
            options = [ft.DropdownOption(key="ALL", text="All Courses")] + [
                ft.DropdownOption(key=str(c.id), text=f"{c.name} ({c.code})") for c in courses
            ]
            self.course_filter.options = options
        except Exception as ex:
            LogService.error(f"Failed to load course options for filter: {ex}", context=self.__class__.__name__)

    def _load_admissions(self) -> None:
        try:
            filters: dict[str, Any] = {
                "limit": self.page_size,
                "offset": self.current_page * self.page_size,
            }

            if self.search_query:
                filters["query"] = self.search_query

            if self.selected_status != "ALL":
                filters["status"] = self.selected_status

            if self.selected_course_id:
                filters["course_id"] = self.selected_course_id

            admissions, total = self.controller.filter_admissions(filters)
            self.admissions = admissions
            self.total_count = total

            self._render_table()
            self._update_pagination()
            self._safe_update()
        except Exception as ex:
            LogService.error(f"Failed to load admissions table: {ex}", context=self.__class__.__name__)

    def _render_table(self) -> None:
        rows: list[ft.DataRow] = []

        from core.security.context import SecurityContext
        from core.security.roles import Role
        current_role = SecurityContext.get_current_role()
        is_admin = (str(current_role).upper() == Role.ADMINISTRATOR.value)

        for adm in self.admissions:
            status_color = ADMISSION_STATUS_COLORS.get(adm.status, AppTheme.PRIMARY)
            status_badge = ft.Container(
                content=ft.Text(
                    adm.status,
                    size=AppTheme.SIZE_CAPTION,
                    weight=ft.FontWeight.W_600,
                    color=status_color,
                ),
                bgcolor=status_color + "1A",
                padding=ft.Padding(6, 2, 6, 2),
                border_radius=AppTheme.RADIUS_SM,
            )

            cand_badge = ft.Container(
                content=ft.Text(
                    adm.admission_number,
                    size=AppTheme.SIZE_CAPTION,
                    weight=ft.FontWeight.BOLD,
                    color=AppTheme.PRIMARY,
                ),
                bgcolor=AppTheme.PRIMARY_LIGHT,
                padding=ft.Padding(6, 2, 6, 2),
                border_radius=AppTheme.RADIUS_SM,
            )

            fee_info = ft.Column(
                controls=[
                    ft.Text(f"Fee: ₹{adm.agreed_fee:,.0f}", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD),
                    ft.Text(f"Paid: ₹{adm.total_paid:,.0f} | Bal: ₹{adm.pending_amount:,.0f}", size=11, color=AppTheme.TEXT_SECONDARY),
                ],
                spacing=1,
            )

            open_btn = ft.IconButton(
                icon=ft.Icons.OPEN_IN_NEW,
                icon_size=16,
                icon_color=AppTheme.PRIMARY,
                tooltip="Open 360° Admission Workspace",
                on_click=lambda e, a_id=adm.id: self.open_admission_workspace(a_id),
            )

            actions = [open_btn]
            if is_admin:
                delete_btn = ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    icon_size=16,
                    icon_color=AppTheme.DANGER,
                    tooltip="Delete Admission (Administrator Only)",
                    on_click=lambda e, a_id=adm.id, a_num=adm.admission_number, s_name=adm.student_name: self.handle_delete_admission(a_id, a_num, s_name),
                )
                actions.append(delete_btn)

            row = ft.DataRow(
                cells=[
                    ft.DataCell(cand_badge),
                    ft.DataCell(ft.Text(adm.student_name, weight=ft.FontWeight.W_600, size=AppTheme.SIZE_BODY)),
                    ft.DataCell(ft.Text(adm.mobile_number or "—", size=AppTheme.SIZE_BODY, color=AppTheme.TEXT_SECONDARY)),
                    ft.DataCell(ft.Text(adm.course_name, size=AppTheme.SIZE_BODY)),
                    ft.DataCell(ft.Text(adm.batch_name or "Unassigned", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY)),
                    ft.DataCell(ft.Text(adm.created_at[:10] if adm.created_at else "—", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED)),
                    ft.DataCell(status_badge),
                    ft.DataCell(fee_info),
                    ft.DataCell(ft.Row(controls=actions, spacing=2)),
                ],
                on_select_change=lambda e, a_id=adm.id: self.open_admission_workspace(a_id),
            )
            rows.append(row)

        self.data_table.rows = rows
        self.empty_container.visible = (len(rows) == 0)
        self.data_table.visible = (len(rows) > 0)

    def _update_pagination(self) -> None:
        total = self.total_count
        start_idx = self.current_page * self.page_size + 1 if total > 0 else 0
        end_idx = min((self.current_page + 1) * self.page_size, total)

        self.pagination_info.value = f"Showing {start_idx}-{end_idx} of {total:,} admissions"
        self.prev_page_btn.disabled = (self.current_page == 0)
        self.next_page_btn.disabled = (end_idx >= total)

    # ── Event Handlers ──

    def handle_search_change(self, e: ft.ControlEvent) -> None:
        self.search_query = (e.control.value or "").strip()
        self.current_page = 0
        self._load_admissions()

    def handle_clear_search(self, e: ft.ControlEvent) -> None:
        self.search_field.value = ""
        self.search_query = ""
        self.current_page = 0
        self._load_admissions()

    def handle_filter_change(self, e: ft.ControlEvent) -> None:
        self.selected_status = self.status_filter.value or "ALL"
        raw_course = self.course_filter.value
        self.selected_course_id = int(raw_course) if raw_course and raw_course != "ALL" else None
        self.current_page = 0
        self._load_admissions()

    def handle_reset_filters(self, e: ft.ControlEvent) -> None:
        self.status_filter.value = "ALL"
        self.course_filter.value = "ALL"
        self.selected_status = "ALL"
        self.selected_course_id = None
        self.search_field.value = ""
        self.search_query = ""
        self.current_page = 0
        self._load_admissions()

    def handle_page_size_change(self, e: ft.ControlEvent) -> None:
        if e.control.value:
            self.page_size = int(e.control.value)
            self.current_page = 0
            self._load_admissions()

    def handle_prev_page(self, e: ft.ControlEvent) -> None:
        if self.current_page > 0:
            self.current_page -= 1
            self._load_admissions()

    def handle_next_page(self, e: ft.ControlEvent) -> None:
        if (self.current_page + 1) * self.page_size < self.total_count:
            self.current_page += 1
            self._load_admissions()

    def handle_new_admission(self, e: ft.ControlEvent) -> None:
        p = self.safe_page
        if p:
            modal = AdmissionFormModal(on_saved=self.load_data)
            p.show_dialog(modal)

    def open_admission_workspace(self, admission_id: int) -> None:
        p = self.safe_page
        if p:
            dlg = AdmissionWorkspaceDialog(admission_id=admission_id, on_updated=self.load_data)
            p.show_dialog(dlg)

    def handle_delete_admission(self, admission_id: int, admission_number: str, student_name: str) -> None:
        """Opens Administrator Destructive Deletion Dialog with exact dependency breakdown."""
        from core.security.context import SecurityContext
        from core.security.roles import Role
        from core.exceptions import ForbiddenError, ValidationError, ConflictError, ServiceError

        current_role = SecurityContext.get_current_role()
        if str(current_role).upper() != Role.ADMINISTRATOR.value:
            p = self.safe_page
            if p:
                snack = ft.SnackBar(
                    content=ft.Text("Access Denied: Only an Administrator can delete admissions."),
                    bgcolor=AppTheme.DANGER,
                )
                p.overlay.append(snack)
                snack.open = True
                p.update()
            return

        try:
            impact = self.controller.get_deletion_impact(admission_id)
        except Exception as ex:
            LogService.error(f"Failed to calculate deletion impact: {ex}", context=self.__class__.__name__)
            return

        p = self.safe_page
        if not p:
            return

        def confirm_delete(e):
            msg = ""
            err = False
            try:
                self.controller.delete_admission(admission_id)
                msg = f"Admission #{admission_id} ({admission_number}) and all linked records permanently deleted."
            except (ValidationError, ConflictError, ServiceError, ForbiddenError) as ex:
                msg = str(ex)
                err = True
            except Exception as ex:
                LogService.error(f"Error during admission deletion: {ex}", context="AdmissionDelete")
                msg = "An unexpected error occurred during deletion."
                err = True
            finally:
                try:
                    p.pop_dialog()
                except RuntimeError:
                    pass

                if msg:
                    snack = ft.SnackBar(
                        content=ft.Text(msg),
                        bgcolor=AppTheme.DANGER if err else AppTheme.SUCCESS,
                    )
                    p.overlay.append(snack)
                    snack.open = True
                    p.update()
                if not err:
                    self.load_data()

        def cancel_delete(e):
            try:
                p.pop_dialog()
            except RuntimeError:
                pass

        details_controls = [
            ft.Text(
                f"Permanently delete admission {admission_number} for '{student_name}' (ID: #{admission_id})?",
                size=AppTheme.SIZE_BODY,
                weight=ft.FontWeight.BOLD,
                color=AppTheme.TEXT_PRIMARY,
            ),
            ft.Container(height=4),
            ft.Text("The following associated records will also be permanently deleted:", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
            ft.Text(f"• Payments: {impact.get('payments', 0)} (Total: ₹{impact.get('payments_total', 0.0):,.2f})", size=AppTheme.SIZE_CAPTION),
            ft.Text(f"• Receipts: {impact.get('receipts', 0)}", size=AppTheme.SIZE_CAPTION),
            ft.Text(f"• Course Enrolments: {impact.get('courses', 0)}", size=AppTheme.SIZE_CAPTION),
            ft.Text("• Student Profile: Preserved (Only this admission record is removed)", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD),
            ft.Container(height=6),
            ft.Text(
                "CAUTION: This operation cannot be undone. An audit event will be recorded.",
                size=AppTheme.SIZE_CAPTION,
                color=AppTheme.DANGER,
                weight=ft.FontWeight.BOLD,
            ),
        ]

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.WARNING_AMBER, color=AppTheme.DANGER, size=24),
                    ft.Text("Permanent Admission Deletion", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_H2),
                ],
                spacing=8,
            ),
            content=ft.Container(
                content=ft.Column(controls=details_controls, tight=True, spacing=4),
                width=480,
                padding=ft.Padding(0, 8, 0, 8),
            ),
            actions=[
                ft.TextButton(
                    content=ft.Text("Cancel", size=AppTheme.SIZE_BODY),
                    on_click=cancel_delete,
                ),
                ft.ElevatedButton(
                    content=ft.Text("Delete Permanently", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD),
                    icon=ft.Icons.DELETE_FOREVER,
                    style=ft.ButtonStyle(
                        bgcolor=AppTheme.DANGER,
                        color=AppTheme.SURFACE,
                    ),
                    on_click=confirm_delete,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        p.show_dialog(dialog)

    # ----------------------------------------------------
    # Export Handlers
    # ----------------------------------------------------
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

    def handle_export_excel(self, e: ft.ControlEvent) -> None:
        """Exports currently filtered admission dataset to styled Microsoft Excel (.xlsx) format."""
        try:
            filters: dict[str, Any] = {}
            if self.search_query:
                filters["query"] = self.search_query
            if self.selected_status != "ALL":
                filters["status"] = self.selected_status
            if self.selected_course_id:
                filters["course_id"] = self.selected_course_id

            path = self.controller.export_admissions_excel(filters)
            self._show_toast(f"Admissions data exported to Excel (.xlsx): {path}", is_success=True)
            open_path_externally(Path(path).parent)
        except Exception as ex:
            LogService.error(f"Error exporting admissions to Excel: {ex}", context=self.__class__.__name__)
            self._show_toast("Failed to export admissions Excel data.", is_error=True)

    def handle_export_csv(self, e: ft.ControlEvent) -> None:
        """Delegates export to professional Excel (.xlsx) format per template specifications."""
        self.handle_export_excel(e)
