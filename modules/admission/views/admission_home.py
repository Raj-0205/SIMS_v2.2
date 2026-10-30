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
from shared.utils.export_helper import export_and_prompt_save
from ui.widgets.badge import StatusBadge

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
        self.show_controls_panel: bool = True
        self.auto_fit_screen: bool = True

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

        self.toggle_controls_btn = ft.OutlinedButton(
            content=ft.Text("Hide Controls", size=AppTheme.SIZE_CAPTION),
            icon=ft.Icons.FILTER_ALT_OFF,
            tooltip="Hide search and filter controls",
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
            ),
            on_click=self.handle_toggle_controls,
        )

        self.toggle_autofit_btn = ft.OutlinedButton(
            content=ft.Text("Auto-Fit: ON", size=AppTheme.SIZE_CAPTION),
            icon=ft.Icons.FIT_SCREEN,
            tooltip="Auto-fit table to available screen width (Click to toggle)",
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
            ),
            on_click=self.handle_toggle_autofit,
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

        self.collect_payment_btn = ft.ElevatedButton(
            content=ft.Text("Collect Payment", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.W_600),
            icon=ft.Icons.POINT_OF_SALE,
            tooltip="Quick Payment Gateway Shortcut",
            style=ft.ButtonStyle(
                bgcolor="#059669",
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                padding=ft.Padding(left=16, top=12, right=16, bottom=12),
            ),
            on_click=lambda _: self.handle_collect_payment(None),
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
                        self.toggle_controls_btn,
                        self.toggle_autofit_btn,
                        self.export_excel_btn,
                        self.refresh_btn,
                        self.collect_payment_btn,
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
                ft.DropdownOption(key="REGISTERED", text="Admitted"),
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
        # 4. Data Table — Frozen Header & Scrollable Body Architecture
        # ----------------------------------------------------
        self.col_specs = [
            ("Candidate No", 110),
            ("Student Name", 180),
            ("Mobile Number", 120),
            ("Course", 140),
            ("Batch", 120),
            ("Admission Date", 110),
            ("Status", 100),
            ("Fee / Paid / Balance", 160),
            ("Action", 80),
        ]

        self.table_columns = [
            ft.DataColumn(label=ft.Container(content=ft.Text(label, weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION), width=w))
            for label, w in self.col_specs
        ]

        self.dummy_columns = [
            ft.DataColumn(label=ft.Container(width=w))
            for _, w in self.col_specs
        ]

        self.header_table = ft.DataTable(
            columns=self.table_columns,
            rows=[],
            heading_row_color=AppTheme.SURFACE_VARIANT,
            heading_row_height=42,
            border=ft.Border.all(1, AppTheme.BORDER),
            border_radius=ft.BorderRadius(AppTheme.RADIUS_MD, AppTheme.RADIUS_MD, 0, 0),
            vertical_lines=ft.BorderSide(0.5, AppTheme.BORDER),
            horizontal_lines=ft.BorderSide(0.5, AppTheme.BORDER),
        )

        self.data_table = ft.DataTable(
            columns=self.dummy_columns,
            rows=[],
            heading_row_height=0,
            divider_thickness=0,
            data_row_min_height=48,
            border=ft.Border.all(1, AppTheme.BORDER),
            border_radius=ft.BorderRadius(0, 0, AppTheme.RADIUS_MD, AppTheme.RADIUS_MD),
            vertical_lines=ft.BorderSide(0.5, AppTheme.BORDER),
            horizontal_lines=ft.BorderSide(0.5, AppTheme.BORDER),
        )

        self.empty_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.SEARCH_OFF, size=48, color=AppTheme.TEXT_MUTED),
                    ft.Text("No matching admissions found", size=AppTheme.SIZE_H3, weight=ft.FontWeight.W_600, color=AppTheme.TEXT_SECONDARY),
                    ft.Text("Click 'New Admission' above to admit a student.", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=AppTheme.PAD_XS,
            ),
            padding=ft.Padding(0, 40, 0, 40),
            visible=False,
        )

        base_cols_w = sum(w for _, w in self.col_specs) + (len(self.col_specs) - 1) * 18 + 2 * 14
        self.table_column = ft.Column(
            controls=[
                self.header_table,
                ft.Container(
                    content=ft.ListView(
                        controls=[self.data_table],
                        expand=True,
                    ),
                    expand=True,
                    width=base_cols_w,
                ),
            ],
            spacing=0,
            width=base_cols_w,
        )

        self.table_scroll_row = ft.Row(
            controls=[self.table_column],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        self.table_container = ft.Container(
            content=ft.Column(
                controls=[self.table_scroll_row, self.empty_container],
                expand=True,
            ),
            expand=True,
            animate_size=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
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
        self.controls_panel = ft.Column(
            controls=[
                search_container,
                filter_row,
            ],
            spacing=AppTheme.PAD_SM,
            visible=True,
            animate_size=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
            animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT),
        )

        self.content = ft.Column(
            controls=[
                header_row,
                ft.Divider(height=1, color=AppTheme.BORDER),
                self.controls_panel,
                self.table_container,
                ft.Divider(height=1, color=AppTheme.BORDER),
                pagination_row,
            ],
            spacing=AppTheme.PAD_MD,
            expand=True,
        )

    def handle_toggle_controls(self, e=None) -> None:
        self.show_controls_panel = not self.show_controls_panel
        self.controls_panel.visible = self.show_controls_panel
        if self.show_controls_panel:
            self.toggle_controls_btn.content = ft.Text("Hide Controls", size=AppTheme.SIZE_CAPTION)
            self.toggle_controls_btn.icon = ft.Icons.FILTER_ALT_OFF
            self.toggle_controls_btn.tooltip = "Hide search and filter controls"
        else:
            self.toggle_controls_btn.content = ft.Text("Show Controls", size=AppTheme.SIZE_CAPTION)
            self.toggle_controls_btn.icon = ft.Icons.FILTER_ALT
            self.toggle_controls_btn.tooltip = "Show search and filter controls"
        self._safe_update()

    def handle_toggle_autofit(self, e=None) -> None:
        self.auto_fit_screen = not self.auto_fit_screen
        if self.auto_fit_screen:
            self.toggle_autofit_btn.content = ft.Text("Auto-Fit: ON", size=AppTheme.SIZE_CAPTION)
            self.toggle_autofit_btn.icon = ft.Icons.FIT_SCREEN
            self.toggle_autofit_btn.tooltip = "Auto-fit table to available screen width (Click to toggle)"
        else:
            self.toggle_autofit_btn.content = ft.Text("Auto-Fit: OFF", size=AppTheme.SIZE_CAPTION)
            self.toggle_autofit_btn.icon = ft.Icons.FIT_SCREEN_OUTLINED
            self.toggle_autofit_btn.tooltip = "Table in compact mode (Click to enable auto-fit)"
        self._render_table()
        self._safe_update()

    def _render_table_rows(self) -> None:
        """Backward-compatible alias for _render_table."""
        self._render_table()

    def _compute_column_spacing(self, num_columns: int = 9, base_content_width: int = 1050) -> tuple[int, int]:
        if not getattr(self, "auto_fit_screen", True):
            return 18, 14

        p = self.safe_page
        screen_w = p.width if (p and p.width and p.width > 300) else 1920

        sidebar_w = 68
        container_pad = 64
        avail_w = max(base_content_width + 100, screen_w - sidebar_w - container_pad)

        gaps = max(1, num_columns - 1)
        extra_w = avail_w - base_content_width - 36
        if extra_w > 0:
            spacing = max(18, min(150, int(extra_w / gaps)))
            return spacing, 18
        return 18, 14

    @property
    def safe_page(self) -> Optional[ft.Page]:
        try:
            return getattr(self, "_root_page", None) or self.page or getattr(self, "_page", None)
        except (RuntimeError, AttributeError):
            return getattr(self, "_root_page", None) or getattr(self, "_page", None)

    def did_mount(self) -> None:
        self.load_data()
        p = self.safe_page
        if p:
            def _on_page_resize(e):
                if not getattr(self, "page", None) and not getattr(self, "_root_page", None):
                    return
                if getattr(self, "auto_fit_screen", True):
                    self._render_table()
                    self._safe_update()
            p.on_resize = _on_page_resize

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
            variant = "success" if adm.status in ("CONFIRMED", "ENROLLED", "ADMITTED") else ("warning" if adm.status == "PENDING" else ("danger" if adm.status == "CANCELLED" else "primary"))
            display_status = "Admitted" if adm.status == "REGISTERED" else adm.status
            status_badge = StatusBadge(label=display_status, variant=variant)

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
            if adm.pending_amount > 0:
                pay_action_btn = ft.IconButton(
                    icon=ft.Icons.PAYMENTS,
                    icon_size=16,
                    icon_color=AppTheme.SUCCESS,
                    tooltip=f"Collect Payment (Pending: ₹{adm.pending_amount:,.0f})",
                    on_click=lambda e, a_id=adm.id: self.handle_collect_payment(a_id),
                )
                actions.append(pay_action_btn)
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
                    ft.DataCell(ft.Container(content=cand_badge, width=110)),
                    ft.DataCell(ft.Container(content=ft.Text(adm.student_name, weight=ft.FontWeight.W_600, size=AppTheme.SIZE_BODY, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS), width=180)),
                    ft.DataCell(ft.Container(content=ft.Text(adm.mobile_number or "—", size=AppTheme.SIZE_BODY, color=AppTheme.TEXT_SECONDARY, no_wrap=True), width=120)),
                    ft.DataCell(ft.Container(content=ft.Text(adm.course_name, size=AppTheme.SIZE_BODY, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS), width=140)),
                    ft.DataCell(
                        ft.Container(
                            content=ft.Row(
                                controls=[
                                    ft.Icon(
                                        ft.Icons.ADD_TASK if not adm.batch_name else ft.Icons.CLASS_,
                                        size=12,
                                        color=AppTheme.WARNING if not adm.batch_name else AppTheme.TEXT_SECONDARY,
                                    ),
                                    ft.Text(
                                        adm.batch_name or "Unassigned",
                                        size=AppTheme.SIZE_CAPTION,
                                        color=AppTheme.WARNING if not adm.batch_name else AppTheme.TEXT_SECONDARY,
                                        weight=ft.FontWeight.BOLD if not adm.batch_name else ft.FontWeight.NORMAL,
                                        no_wrap=True,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                ],
                                spacing=4,
                                tight=True,
                            ),
                            width=120,
                            tooltip="Click to assign or switch batch",
                            on_click=lambda e, a_id=adm.id: self.open_batch_dialog(a_id),
                        )
                    ),
                    ft.DataCell(ft.Container(content=ft.Text(adm.created_at[:10] if adm.created_at else "—", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED, no_wrap=True), width=110)),
                    ft.DataCell(ft.Container(content=status_badge, width=100)),
                    ft.DataCell(ft.Container(content=fee_info, width=160)),
                    ft.DataCell(ft.Container(content=ft.Row(controls=actions, spacing=2), width=80)),
                ],
                on_select_change=lambda e, a_id=adm.id: self.open_admission_workspace(a_id),
            )
            rows.append(row)

        col_spacing, horiz_margin = self._compute_column_spacing(num_columns=9, base_content_width=1050)
        total_cols_w = sum(w for _, w in self.col_specs)
        total_table_w = total_cols_w + (len(self.col_specs) - 1) * col_spacing + 2 * horiz_margin
        self.table_column.width = total_table_w
        if len(self.table_column.controls) > 1 and isinstance(self.table_column.controls[1], ft.Container):
            self.table_column.controls[1].width = total_table_w

        self.header_table.column_spacing = col_spacing
        self.header_table.horizontal_margin = horiz_margin
        self.header_table.visible = (len(rows) > 0)
        self.data_table.column_spacing = col_spacing
        self.data_table.horizontal_margin = horiz_margin
        self.data_table.rows = rows
        self.table_scroll_row.visible = (len(rows) > 0)
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

    def handle_collect_payment(self, admission_id: Optional[int] = None) -> None:
        p = self.safe_page
        if p:
            from modules.admission.views.payment_dialog import PaymentDialog
            dlg = PaymentDialog(
                admission_id=admission_id,
                page=p,
                on_payment_completed=lambda pid: self.load_data(),
            )
            p.show_dialog(dlg)

    def open_admission_workspace(self, admission_id: int) -> None:
        p = self.safe_page
        if p:
            dlg = AdmissionWorkspaceDialog(admission_id=admission_id, on_updated=self.load_data)
            p.show_dialog(dlg)

    def open_batch_dialog(self, admission_id: int) -> None:
        """Opens modal to assign a batch to unallocated candidate or switch class timing."""
        from modules.admission.views.batch_assignment_dialog import BatchAssignmentDialog
        p = self.safe_page
        if p:
            dlg = BatchAssignmentDialog(admission_id=admission_id, on_updated=self.load_data, page=p)
            p.show_dialog(dlg)

    def handle_delete_admission(self, admission_id: int, admission_number: str, student_name: str) -> None:
        """Opens Administrator Destructive Deletion Dialog with exact dependency breakdown."""
        from core.security.context import SecurityContext
        from core.security.roles import Role
        from core.exceptions import ForbiddenError, ValidationError, ConflictError, ServiceError

        current_role = SecurityContext.get_current_role()
        if str(current_role).upper() != Role.ADMINISTRATOR.value:
            self._show_toast("Access Denied: Only an Administrator can delete admissions.", is_error=True)
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
                    self._show_toast(msg, is_error=err, is_success=not err)
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
            title=ft.SelectionArea(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.WARNING_AMBER, color=AppTheme.DANGER, size=24),
                        ft.Text("Permanent Admission Deletion", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_H2),
                    ],
                    spacing=8,
                ),
            ),
            content=ft.Container(
                content=ft.SelectionArea(
                    content=ft.Column(controls=details_controls, tight=True, spacing=4),
                ),
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
        bg = AppTheme.DANGER if is_error else (AppTheme.SUCCESS if is_success else AppTheme.PRIMARY)
        snack = ft.SnackBar(
            content=ft.Text(message, color=AppTheme.SURFACE),
            bgcolor=bg,
        )
        if hasattr(p, "show_dialog"):
            try:
                p.show_dialog(snack)
                return
            except Exception:
                pass
        p.snack_bar = snack
        snack.open = True
        try:
            p.update()
        except RuntimeError:
            pass

    def handle_export_excel(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Exports currently filtered admission dataset to styled Microsoft Excel (.xlsx) format with custom save prompt."""
        try:
            filters: dict[str, Any] = {}
            if self.search_query:
                filters["query"] = self.search_query
            if self.selected_status != "ALL":
                filters["status"] = self.selected_status
            if self.selected_course_id:
                filters["course_id"] = self.selected_course_id

            path = self.controller.export_admissions_excel(filters)
            export_and_prompt_save(
                source_file_path=path,
                dialog_title="Save Admissions Export As",
                allowed_extensions=[".xlsx"],
                show_toast=self._show_toast,
            )
        except Exception as ex:
            LogService.error(f"Error exporting admissions to Excel: {ex}", context=self.__class__.__name__)
            self._show_toast("Failed to export admissions Excel data.", is_error=True)

    def handle_export_csv(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Exports currently filtered admission dataset to clean CSV format with custom save prompt."""
        try:
            filters: dict[str, Any] = {}
            if self.search_query:
                filters["query"] = self.search_query
            if self.selected_status != "ALL":
                filters["status"] = self.selected_status
            if self.selected_course_id:
                filters["course_id"] = self.selected_course_id

            path = self.controller.export_admissions_csv(filters)
            export_and_prompt_save(
                source_file_path=path,
                dialog_title="Save Admissions CSV As",
                allowed_extensions=[".csv"],
                show_toast=self._show_toast,
            )
        except Exception as ex:
            LogService.error(f"Error exporting admissions to CSV: {ex}", context=self.__class__.__name__)
            self._show_toast("Failed to export admissions CSV data.", is_error=True)
