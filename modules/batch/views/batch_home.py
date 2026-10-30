# modules/batch/views/batch_home.py

from __future__ import annotations
from typing import Optional
import flet as ft

from core.logger.service import LogService
from core.exceptions import ValidationError, ConflictError, ServiceError
from ui.themes.theme import AppTheme
from modules.batch.controller import BatchController
from modules.batch.constants import BatchStatus
from modules.batch.dto import BatchDTO
from modules.batch.views.batch_form_modal import BatchFormModal
from modules.course.controller import CourseController
from ui.widgets.hover_card import HoverCard
from ui.widgets.badge import StatusBadge

__all__ = ["BatchHome"]

BATCH_STATUS_COLORS = {
    BatchStatus.OPEN.value: AppTheme.SUCCESS,
    BatchStatus.FULL.value: AppTheme.WARNING,
    BatchStatus.COMPLETED.value: AppTheme.PRIMARY,
    BatchStatus.CANCELLED.value: AppTheme.DANGER,
}


class BatchHome(ft.Container):
    """
    Enterprise Batch Management Workspace.
    Provides live batch statistics, course/status filtering,
    batch creation modal, editing, capacity monitoring, and safe deletion.
    """

    def __init__(self) -> None:
        super().__init__(expand=True, padding=AppTheme.PAD_LG)
        self.controller = BatchController()
        self.course_controller = CourseController()

        # State Variables
        self.batches: list[BatchDTO] = []
        self.total_count: int = 0
        self.current_page: int = 0
        self.page_size: int = 25
        self.show_controls_panel: bool = True
        self.auto_fit_screen: bool = True

        # Filter States
        self.selected_course_id: Optional[int] = None
        self.selected_status: str = "ALL"
        self.search_query: str = ""

        # UI Components
        self._build_ui()

    def _build_ui(self) -> None:
        # 1. Header
        self.title_text = ft.Text(
            "Batch Management",
            size=AppTheme.SIZE_H1,
            weight=ft.FontWeight.BOLD,
            color=AppTheme.TEXT_PRIMARY,
        )
        self.subtitle_text = ft.Text(
            "Manage course schedules, class timings, student capacities, and batch lifecycles.",
            size=AppTheme.SIZE_BODY,
            color=AppTheme.TEXT_SECONDARY,
        )

        self.toggle_controls_btn = ft.OutlinedButton(
            content=ft.Text("Hide Controls", size=AppTheme.SIZE_CAPTION),
            icon=ft.Icons.FILTER_ALT_OFF,
            tooltip="Hide KPI summary and filter controls",
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

        self.new_batch_btn = ft.ElevatedButton(
            content=ft.Text("New Batch", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.W_600),
            icon=ft.Icons.GROUP_ADD,
            style=ft.ButtonStyle(
                bgcolor=AppTheme.PRIMARY,
                color=AppTheme.SURFACE,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                padding=ft.Padding(left=18, top=12, right=18, bottom=12),
            ),
            on_click=self.handle_new_batch,
        )

        self.refresh_btn = ft.IconButton(
            icon=ft.Icons.REFRESH,
            icon_size=20,
            icon_color=AppTheme.TEXT_SECONDARY,
            tooltip="Refresh Directory",
            on_click=lambda e: self.load_data(),
        )

        header_row = ft.Row(
            controls=[
                ft.Column(controls=[self.title_text, self.subtitle_text], spacing=2),
                ft.Row(
                    controls=[
                        self.toggle_controls_btn,
                        self.toggle_autofit_btn,
                        self.refresh_btn,
                        self.new_batch_btn,
                    ],
                    spacing=AppTheme.PAD_SM,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        # 2. KPI Cards
        self.kpi_total_text = ft.Text("0", size=22, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY)
        self.kpi_open_text = ft.Text("0", size=22, weight=ft.FontWeight.BOLD, color=AppTheme.SUCCESS)
        self.kpi_full_text = ft.Text("0", size=22, weight=ft.FontWeight.BOLD, color=AppTheme.WARNING)
        self.kpi_completed_text = ft.Text("0", size=22, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_MUTED)

        kpis_row = ft.Row(
            controls=[
                self._make_kpi_card("Total Batches", ft.Icons.GROUP_WORK, AppTheme.PRIMARY, self.kpi_total_text),
                self._make_kpi_card("Open Batches", ft.Icons.CHECK_CIRCLE, AppTheme.SUCCESS, self.kpi_open_text),
                self._make_kpi_card("Full Batches", ft.Icons.PEOPLE, AppTheme.WARNING, self.kpi_full_text),
                self._make_kpi_card("Completed", ft.Icons.TASK_ALT, AppTheme.TEXT_MUTED, self.kpi_completed_text),
            ],
            spacing=AppTheme.PAD_MD,
        )

        # 3. Filter Bar
        self.course_filter = ft.Dropdown(
            label="Filter by Course",
            width=240,
            options=[ft.DropdownOption(key="ALL", text="All Courses")],
            value="ALL",
            border_radius=AppTheme.RADIUS_MD,
            on_select=self.handle_filter_change,
        )

        self.status_filter = ft.Dropdown(
            label="Filter by Status",
            width=180,
            options=[
                ft.DropdownOption(key="ALL", text="All Statuses"),
                ft.DropdownOption(key=BatchStatus.OPEN.value, text="Open"),
                ft.DropdownOption(key=BatchStatus.FULL.value, text="Full"),
                ft.DropdownOption(key=BatchStatus.COMPLETED.value, text="Completed"),
                ft.DropdownOption(key=BatchStatus.CANCELLED.value, text="Cancelled"),
            ],
            value="ALL",
            border_radius=AppTheme.RADIUS_MD,
            on_select=self.handle_filter_change,
        )

        self.search_field = ft.TextField(
            hint_text="Search batch name or timing...",
            prefix_icon=ft.Icons.SEARCH,
            border_radius=AppTheme.RADIUS_MD,
            expand=True,
            on_change=self.handle_search_change,
        )

        self.reset_filter_btn = ft.OutlinedButton(
            "Reset Filters",
            icon=ft.Icons.FILTER_ALT_OFF,
            on_click=self.handle_reset_filters,
        )

        filter_row = ft.Row(
            controls=[
                self.course_filter,
                self.status_filter,
                self.search_field,
                self.reset_filter_btn,
            ],
            spacing=AppTheme.PAD_SM,
        )

        # 4. Data Table
        self.data_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Batch", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Course", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Timing", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Capacity (Enrolled / Max)", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Dates", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Status", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Actions", weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
            heading_row_color=AppTheme.SURFACE_VARIANT,
            border=ft.Border.all(1, AppTheme.BORDER),
            border_radius=AppTheme.RADIUS_MD,
            horizontal_margin=AppTheme.PAD_MD,
            column_spacing=AppTheme.PAD_MD,
        )

        self.empty_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.SEARCH_OFF, size=48, color=AppTheme.TEXT_MUTED),
                    ft.Text("No batches found matching criteria.", size=AppTheme.SIZE_BODY, color=AppTheme.TEXT_SECONDARY),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            padding=ft.Padding(32, 32, 32, 32),
            alignment=ft.Alignment(0, 0),
            visible=False,
        )

        self.table_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.ListView(
                        controls=[
                            ft.Row(
                                controls=[self.data_table],
                                scroll=ft.ScrollMode.AUTO,
                            )
                        ],
                        expand=True,
                    ),
                    self.empty_container,
                ],
                expand=True,
            ),
            bgcolor=AppTheme.SURFACE,
            border_radius=AppTheme.RADIUS_MD,
            padding=AppTheme.PAD_SM,
            expand=True,
            animate_size=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
        )

        # 5. Pagination
        self.pagination_info = ft.Text(
            "Showing 0-0 of 0 batches",
            size=AppTheme.SIZE_CAPTION,
            color=AppTheme.TEXT_SECONDARY,
        )
        self.prev_page_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_LEFT,
            tooltip="Previous Page",
            disabled=True,
            on_click=self.handle_prev_page,
        )
        self.next_page_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_RIGHT,
            tooltip="Next Page",
            disabled=True,
            on_click=self.handle_next_page,
        )

        pagination_row = ft.Row(
            controls=[
                self.pagination_info,
                ft.Row(controls=[self.prev_page_btn, self.next_page_btn], spacing=AppTheme.PAD_XS),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        self.controls_panel = ft.Column(
            controls=[
                kpis_row,
                filter_row,
            ],
            spacing=AppTheme.PAD_SM,
            visible=True,
            animate_size=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
            animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT),
        )

        # Assemble Main Layout
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
            self.toggle_controls_btn.tooltip = "Hide KPI summary and filter controls"
        else:
            self.toggle_controls_btn.content = ft.Text("Show Controls", size=AppTheme.SIZE_CAPTION)
            self.toggle_controls_btn.icon = ft.Icons.FILTER_ALT
            self.toggle_controls_btn.tooltip = "Show KPI summary and filter controls"
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

    def _compute_column_spacing(self, num_columns: int = 7, base_content_width: int = 850) -> tuple[int, int]:
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

    def _make_kpi_card(self, title: str, icon: str, color: str, text_ctrl: ft.Text) -> ft.Container:
        return HoverCard(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text(title, size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY, weight=ft.FontWeight.W_500),
                            ft.Container(
                                content=ft.Icon(icon, color=color, size=18),
                                bgcolor=color + "1A",
                                padding=ft.Padding(6, 6, 6, 6),
                                border_radius=AppTheme.RADIUS_SM,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Container(height=4),
                    text_ctrl,
                ],
                spacing=2,
            ),
            padding=AppTheme.PAD_MD,
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
        """Loads course options, KPI summary stats, and filtered batches."""
        self._load_course_options()
        self._load_batches()

    def _load_course_options(self) -> None:
        try:
            courses, _ = self.course_controller.list_courses(limit=200)
            options = [ft.DropdownOption(key="ALL", text="All Courses")] + [
                ft.DropdownOption(key=str(c.id), text=f"{c.name} ({c.code})") for c in courses
            ]
            self.course_filter.options = options
        except Exception as ex:
            LogService.error(f"Failed to load courses for batch filter: {ex}", context=self.__class__.__name__)

    def _load_batches(self) -> None:
        try:
            status_param = self.selected_status if self.selected_status != "ALL" else None
            batches, total = self.controller.list_batches(
                limit=self.page_size,
                offset=self.current_page * self.page_size,
                course_id=self.selected_course_id,
                status=status_param,
            )

            # Filter locally if search query is present
            if self.search_query:
                q = self.search_query.lower()
                batches = [
                    b for b in batches
                    if q in b.batch_name.lower() or q in b.timing.lower() or (b.batch_code and q in b.batch_code.lower())
                ]
                total = len(batches)

            self.batches = batches
            self.total_count = total

            # Update KPI counters across all batches
            all_batches, all_count = self.controller.list_batches(limit=200, offset=0)
            open_count = sum(1 for b in all_batches if b.status == BatchStatus.OPEN)
            full_count = sum(1 for b in all_batches if b.status == BatchStatus.FULL)
            completed_count = sum(1 for b in all_batches if b.status == BatchStatus.COMPLETED)

            self.kpi_total_text.value = str(all_count)
            self.kpi_open_text.value = str(open_count)
            self.kpi_full_text.value = str(full_count)
            self.kpi_completed_text.value = str(completed_count)

            self._render_table()
            self._update_pagination()
            self._safe_update()
        except Exception as ex:
            LogService.error(f"Failed to load batches: {ex}", context=self.__class__.__name__)

    def _render_table(self) -> None:
        rows: list[ft.DataRow] = []

        for b in self.batches:
            status_val = b.status.value if isinstance(b.status, BatchStatus) else str(b.status or "OPEN").upper()
            variant_map = {
                BatchStatus.OPEN.value: "success",
                BatchStatus.FULL.value: "warning",
                BatchStatus.COMPLETED.value: "primary",
                BatchStatus.CANCELLED.value: "danger",
            }
            status_badge = StatusBadge(label=status_val, variant=variant_map.get(status_val, "primary"))

            # Capacity summary
            try:
                cap_summary = self.controller.get_capacity_summary(b.id)
                cap_display = f"{cap_summary.enrolled_count} / {cap_summary.max_capacity}"
                cap_color = AppTheme.WARNING if cap_summary.enrolled_count >= cap_summary.max_capacity else AppTheme.TEXT_PRIMARY
            except Exception:
                cap_display = f"— / {b.max_capacity}"
                cap_color = AppTheme.TEXT_PRIMARY

            dates_str = f"{b.start_date or '—'} to {b.end_date or '—'}" if (b.start_date or b.end_date) else "Flexible"

            edit_btn = ft.IconButton(
                icon=ft.Icons.EDIT,
                icon_size=16,
                icon_color=AppTheme.PRIMARY,
                tooltip="Edit Batch",
                on_click=lambda e, batch_obj=b: self.handle_edit_batch(batch_obj),
            )

            delete_btn = ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                icon_size=16,
                icon_color=AppTheme.DANGER,
                tooltip="Delete Batch",
                on_click=lambda e, batch_obj=b: self.handle_delete_batch(batch_obj),
            )

            batch_name_col = ft.Column(
                controls=[
                    ft.Text(b.batch_name, weight=ft.FontWeight.W_600, size=AppTheme.SIZE_BODY),
                    ft.Text(b.batch_code or f"BAT-{b.id}", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED),
                ],
                spacing=1,
            )

            row = ft.DataRow(
                cells=[
                    ft.DataCell(batch_name_col, on_double_tap=lambda e, batch_obj=b: self.handle_edit_batch(batch_obj)),
                    ft.DataCell(ft.Text(b.course_name or f"Course #{b.course_id}"), on_double_tap=lambda e, batch_obj=b: self.handle_edit_batch(batch_obj)),
                    ft.DataCell(ft.Text(b.timing), on_double_tap=lambda e, batch_obj=b: self.handle_edit_batch(batch_obj)),
                    ft.DataCell(ft.Text(cap_display, weight=ft.FontWeight.W_600, color=cap_color)),
                    ft.DataCell(ft.Text(dates_str, size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY)),
                    ft.DataCell(status_badge),
                    ft.DataCell(ft.Row(controls=[edit_btn, delete_btn], spacing=2)),
                ],
                on_select_change=lambda e, batch_obj=b: self.handle_edit_batch(batch_obj),
            )
            rows.append(row)

        col_spacing, horiz_margin = self._compute_column_spacing(num_columns=7, base_content_width=850)
        self.data_table.column_spacing = col_spacing
        self.data_table.horizontal_margin = horiz_margin
        self.data_table.rows = rows
        self.empty_container.visible = (len(rows) == 0)
        self.data_table.visible = (len(rows) > 0)

    def _update_pagination(self) -> None:
        total = self.total_count
        start_idx = self.current_page * self.page_size + 1 if total > 0 else 0
        end_idx = min((self.current_page + 1) * self.page_size, total)

        self.pagination_info.value = f"Showing {start_idx}-{end_idx} of {total:,} batches"
        self.prev_page_btn.disabled = (self.current_page == 0)
        self.next_page_btn.disabled = (end_idx >= total)

    # ── Event Handlers ──

    def handle_search_change(self, e: ft.ControlEvent) -> None:
        self.search_query = (e.control.value or "").strip()
        self.current_page = 0
        self._load_batches()

    def handle_filter_change(self, e: ft.ControlEvent) -> None:
        self.selected_status = self.status_filter.value or "ALL"
        raw_course = self.course_filter.value
        self.selected_course_id = int(raw_course) if raw_course and raw_course != "ALL" else None
        self.current_page = 0
        self._load_batches()

    def handle_reset_filters(self, e: ft.ControlEvent) -> None:
        self.course_filter.value = "ALL"
        self.status_filter.value = "ALL"
        self.search_field.value = ""
        self.selected_course_id = None
        self.selected_status = "ALL"
        self.search_query = ""
        self.current_page = 0
        self._load_batches()

    def handle_prev_page(self, e: ft.ControlEvent) -> None:
        if self.current_page > 0:
            self.current_page -= 1
            self._load_batches()

    def handle_next_page(self, e: ft.ControlEvent) -> None:
        if (self.current_page + 1) * self.page_size < self.total_count:
            self.current_page += 1
            self._load_batches()

    def handle_new_batch(self, e: ft.ControlEvent) -> None:
        p = self.safe_page
        if p:
            modal = BatchFormModal(
                on_saved=lambda _: self.load_data(),
                preselected_course_id=self.selected_course_id,
            )
            p.show_dialog(modal)

    def handle_edit_batch(self, batch: BatchDTO) -> None:
        p = self.safe_page
        if p:
            modal = BatchFormModal(
                batch=batch,
                on_saved=lambda _: self.load_data(),
            )
            p.show_dialog(modal)

    def handle_delete_batch(self, batch: BatchDTO) -> None:
        p = self.safe_page
        if not p:
            return

        def do_confirm(e):
            try:
                self.controller.delete_batch(batch.id)
                p.pop_dialog()
                self.load_data()
                snack = ft.SnackBar(
                    content=ft.Text(f"Batch '{batch.batch_name}' deleted successfully."),
                    bgcolor=AppTheme.SUCCESS,
                )
                p.overlay.append(snack)
                snack.open = True
                p.update()
            except (ConflictError, ValidationError, ServiceError) as ex:
                p.pop_dialog()
                snack = ft.SnackBar(
                    content=ft.Text(f"Cannot delete batch: {ex}"),
                    bgcolor=AppTheme.DANGER,
                )
                p.overlay.append(snack)
                snack.open = True
                p.update()
            except Exception as ex:
                p.pop_dialog()
                LogService.error(f"Error deleting batch: {ex}", context=self.__class__.__name__)
                snack = ft.SnackBar(
                    content=ft.Text(f"Unexpected error: {ex}"),
                    bgcolor=AppTheme.DANGER,
                )
                p.overlay.append(snack)
                snack.open = True
                p.update()

        def do_cancel(e):
            p.pop_dialog()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.SelectionArea(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.WARNING_AMBER, color=AppTheme.DANGER, size=24),
                        ft.Text("Confirm Batch Deletion", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_H2),
                    ],
                    spacing=8,
                )
            ),
            content=ft.Container(
                width=450,
                content=ft.SelectionArea(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                f"Are you sure you want to delete batch '{batch.batch_name}' ({batch.timing})?",
                                size=AppTheme.SIZE_BODY,
                            ),
                            ft.Text(
                                "Batches linked to active or historical student admissions cannot be deleted under ERP audit policies.",
                                size=AppTheme.SIZE_CAPTION,
                                color=AppTheme.TEXT_SECONDARY,
                            ),
                        ],
                        spacing=AppTheme.PAD_SM,
                        tight=True,
                    )
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=do_cancel),
                ft.ElevatedButton(
                    "Delete Batch",
                    style=ft.ButtonStyle(bgcolor=AppTheme.DANGER, color=AppTheme.SURFACE),
                    on_click=do_confirm,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        p.show_dialog(dlg)
