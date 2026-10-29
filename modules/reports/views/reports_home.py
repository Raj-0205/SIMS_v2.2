# modules/reports/views/reports_home.py

from __future__ import annotations
from pathlib import Path
import threading
from typing import Optional, Any
import flet as ft

from core.logger.service import LogService
from core.security.context import SecurityContext
from modules.reports.controller import ReportsController
from modules.course.controller import CourseController
from shared.utils.os_helper import open_path_externally
from shared.utils.export_helper import export_and_prompt_save
from ui.themes.theme import AppTheme

__all__ = ["ReportsHome"]


class ReportsHome(ft.Container):
    """
    Official SIMS v2.2 Fees & Reports Module.
    Tab 1: Student / Admission Fees Report (17 columns, installment breakdown & sorting, Excel/CSV export)
    Tab 2: Payment Amount Search / Filter (Exact amount matches, e.g. ₹500, ₹1000)
    """

    def __init__(self, page: Optional[ft.Page] = None) -> None:
        super().__init__(
            expand=True,
            padding=0,
            animate_size=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
        )

        self._page = page
        self._root_page = page

        self.controller = ReportsController()
        self.course_controller = CourseController()

        self.active_tab: int = 0
        self.report_data: list[dict] = []
        self.payment_data: list[dict] = []

        # Filter states
        self.search_text: str = ""
        self.selected_course_id: Optional[int] = None
        self.selected_status: str = "ALL"
        self.sort_by: Optional[str] = None
        self.filter_amount: float = 500.0

        # Pagination states for Tab 1 (Default page size: 50 records)
        self.current_page: int = 1
        self.page_size: int = 50
        self.total_count: int = 0
        self.total_pages: int = 1
        self._courses_cache: Optional[list[Any]] = None
        self._is_loading: bool = False
        self._load_generation: int = 0
        self._active_data_table: Optional[ft.DataTable] = None
        self._rendered_cache_version: int = 0
        self._rendered_filter_state: tuple = ()
        self.show_controls_panel: bool = True
        self.filter_card: Optional[ft.Container] = None

        # Streaming indicator elements
        self.streaming_indicator = ft.ProgressRing(width=14, height=14, stroke_width=2, color=AppTheme.PRIMARY)
        self.streaming_text = ft.Text("Loading records...", size=AppTheme.SIZE_CAPTION, color=AppTheme.PRIMARY, weight=ft.FontWeight.W_500)
        self.streaming_badge = ft.Container(
            content=ft.Row(
                controls=[
                    self.streaming_indicator,
                    self.streaming_text,
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=AppTheme.PRIMARY_LIGHT,
            padding=ft.Padding(8, 3, 10, 3),
            border_radius=AppTheme.RADIUS_SM,
            visible=False,
        )

        # Live Cache Telemetry & Invalidation Controls
        self.cache_status_text = ft.Text("⚡ Cache Active", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.W_600, color=AppTheme.PRIMARY)
        self.cache_pill = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.FLASH_ON, size=14, color=AppTheme.PRIMARY),
                    self.cache_status_text,
                ],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=AppTheme.PRIMARY_LIGHT,
            padding=ft.Padding(8, 4, 10, 4),
            border_radius=AppTheme.RADIUS_SM,
            tooltip="In-memory cache accelerates fees queries. Click to re-sync from database.",
            ink=True,
            on_click=self.handle_sync_cache,
        )

        # Financial KPI Summary Cards
        self.kpi_cards_container = self._build_kpi_cards()

        self._build_ui()

    def _build_kpi_cards(self) -> ft.Container:
        self.kpi_billed_text = ft.Text("₹0.00", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY)
        self.kpi_collected_text = ft.Text("₹0.00", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color=AppTheme.SUCCESS)
        self.kpi_pending_text = ft.Text("₹0.00", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color=AppTheme.DANGER)
        self.kpi_rate_text = ft.Text("0.0%", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color="#0284C7")

        def _make_card(title: str, val_text: ft.Text, subtitle: str, icon: str, icon_color: str, bg_color: str):
            return ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Icon(icon, size=18, color=icon_color),
                            bgcolor=bg_color,
                            padding=6,
                            border_radius=AppTheme.RADIUS_SM,
                        ),
                        ft.Column(
                            controls=[
                                ft.Text(title, size=11, weight=ft.FontWeight.W_600, color=AppTheme.TEXT_SECONDARY),
                                val_text,
                                ft.Text(subtitle, size=10, color=AppTheme.TEXT_MUTED),
                            ],
                            spacing=1,
                            tight=True,
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor=AppTheme.SURFACE,
                padding=ft.Padding(12, 8, 12, 8),
                border_radius=AppTheme.RADIUS_MD,
                border=ft.Border.all(1, AppTheme.BORDER),
                expand=True,
            )

        return ft.Container(
            content=ft.Row(
                controls=[
                    _make_card("Total Billed Fees", self.kpi_billed_text, "Net Payable Fees", ft.Icons.ACCOUNT_BALANCE_WALLET, AppTheme.PRIMARY, AppTheme.PRIMARY_LIGHT),
                    _make_card("Total Collected", self.kpi_collected_text, "Realized to Date", ft.Icons.CHECK_CIRCLE, AppTheme.SUCCESS, "#ECFDF5"),
                    _make_card("Pending Balance", self.kpi_pending_text, "Outstanding Dues", ft.Icons.HOURGLASS_BOTTOM, AppTheme.DANGER, "#FEF2F2"),
                    _make_card("Collection Health", self.kpi_rate_text, "Recovery Rate", ft.Icons.INSIGHTS, "#0284C7", "#F0F9FF"),
                ],
                spacing=AppTheme.PAD_SM,
            ),
            margin=ft.Margin(0, 0, 0, 4),
        )

    def _update_kpi_cards(self) -> None:
        """Fetches cached financial KPI summary and updates the top metrics cards."""
        try:
            summary = self.controller.get_fees_kpi_summary(course_id=self.selected_course_id)
            if hasattr(self, "kpi_billed_text") and self.kpi_billed_text:
                self.kpi_billed_text.value = f"₹{summary['total_billed_fees']:,.2f}"
            if hasattr(self, "kpi_collected_text") and self.kpi_collected_text:
                self.kpi_collected_text.value = f"₹{summary['total_collected_fees']:,.2f}"
            if hasattr(self, "kpi_pending_text") and self.kpi_pending_text:
                self.kpi_pending_text.value = f"₹{summary['total_pending_fees']:,.2f}"
            if hasattr(self, "kpi_rate_text") and self.kpi_rate_text:
                self.kpi_rate_text.value = f"{summary['collection_rate_pct']}%"
        except Exception as ex:
            LogService.warning(f"Could not update fees KPI cards: {ex}", context="ReportsHome")

    def _update_cache_badge(self) -> None:
        """Updates live cache telemetry badge in header."""
        try:
            stats = self.controller.get_cache_stats()
            v = stats.get("version", 1)
            ratio = stats.get("hit_ratio_pct", 0.0)
            if hasattr(self, "cache_status_text") and self.cache_status_text:
                self.cache_status_text.value = f"⚡ Cache Active ({ratio}% Hits • v{v})"
        except Exception:
            pass

    def handle_sync_cache(self, e: ft.ControlEvent) -> None:
        """User action: Force manual cache invalidation and fresh database re-query."""
        self.controller.clear_cache(reason="Manual User Re-sync")
        self.show_toast("Fees cache refreshed from database.", is_success=True)
        self._update_cache_badge()
        self._trigger_load_data(sync=False)

    def _build_skeleton(self) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.ProgressRing(width=44, height=44, stroke_width=3.5, color=AppTheme.PRIMARY),
                    ft.Container(height=8),
                    ft.Text("Loading fees and admission records...", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.W_600, color=AppTheme.TEXT_PRIMARY),
                    ft.Text("Calculating 4-tier installment schedules and payment ledgers...", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=AppTheme.PAD_XS,
            ),
            padding=ft.Padding(0, 60, 0, 60),
            alignment=ft.Alignment(0, 0),
            bgcolor=AppTheme.SURFACE,
            border=ft.Border.all(1, AppTheme.BORDER),
            border_radius=AppTheme.RADIUS_MD,
            expand=True,
        )

    def _build_ui(self) -> None:
        self.toggle_controls_btn = ft.OutlinedButton(
            content=ft.Text("Hide Filters", size=AppTheme.SIZE_CAPTION),
            icon=ft.Icons.FILTER_ALT_OFF,
            tooltip="Hide filter and search controls",
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
            ),
            on_click=self.handle_toggle_controls,
        )

        self.collect_payment_btn = ft.FilledButton(
            "Collect Payment",
            icon=ft.Icons.POINT_OF_SALE,
            style=ft.ButtonStyle(
                bgcolor=AppTheme.SUCCESS,
                color=AppTheme.SURFACE,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
            ),
            tooltip="Open payment gateway to collect fees or settle balances",
            on_click=lambda _: self.handle_collect_payment(),
        )

        self.refresh_btn = ft.IconButton(
            icon=ft.Icons.REFRESH,
            icon_size=20,
            tooltip="Refresh Fees & Invalidate Cache",
            on_click=self.handle_sync_cache,
        )

        header = ft.Row(
            controls=[
                ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.PAYMENTS_OUTLINED, size=28, color=AppTheme.PRIMARY),
                                ft.Text("Fees & Financial Reports", size=AppTheme.SIZE_H1, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                            ],
                            spacing=AppTheme.PAD_SM,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Text(
                            "Detailed admission fees breakdown, 4-tier installment tracking, and exact payment filtering.",
                            size=AppTheme.SIZE_BODY,
                            color=AppTheme.TEXT_SECONDARY,
                        ),
                    ],
                    spacing=2,
                ),
                ft.Row(
                    controls=[
                        self.cache_pill,
                        self.toggle_controls_btn,
                        self.collect_payment_btn,
                        ft.FilledButton(
                            "Export Excel (.xlsx)",
                            icon=ft.Icons.TABLE_VIEW,
                            style=ft.ButtonStyle(
                                bgcolor=AppTheme.PRIMARY,
                                color=AppTheme.SURFACE,
                                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                            ),
                            on_click=self.handle_export_excel,
                        ),
                        self.refresh_btn,
                    ],
                    spacing=AppTheme.PAD_SM,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        # Tab Segmented Navigation
        self.tab_report_btn = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ASSESSMENT, size=18, color=AppTheme.SURFACE),
                    ft.Text("Admission Fees & Installment Report", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.W_600, color=AppTheme.SURFACE),
                ],
                spacing=8,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            padding=ft.Padding(16, 10, 16, 10),
            border_radius=AppTheme.RADIUS_MD,
            bgcolor=AppTheme.PRIMARY,
            border=ft.Border.all(1, AppTheme.PRIMARY),
            on_click=lambda _: self._set_tab(0),
            ink=True,
        )

        self.tab_filter_btn = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.FILTER_LIST, size=18, color=AppTheme.TEXT_SECONDARY),
                    ft.Text("Payment Amount Filter (e.g. ₹500, ₹1000)", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.W_600, color=AppTheme.TEXT_PRIMARY),
                ],
                spacing=8,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            padding=ft.Padding(16, 10, 16, 10),
            border_radius=AppTheme.RADIUS_MD,
            bgcolor=AppTheme.SURFACE,
            border=ft.Border.all(1, AppTheme.BORDER),
            on_click=lambda _: self._set_tab(1),
            ink=True,
        )

        self.tab_buttons = ft.Row(
            controls=[self.tab_report_btn, self.tab_filter_btn],
            spacing=AppTheme.PAD_SM,
        )

        # Notification Toast Banner
        self.toast_text = ft.Text("", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.W_500)
        self.toast_banner = ft.Container(
            content=ft.Row([ft.Icon(ft.Icons.INFO, size=18), self.toast_text], spacing=AppTheme.PAD_SM),
            padding=ft.Padding(14, 8, 14, 8),
            border_radius=AppTheme.RADIUS_MD,
            visible=False,
        )

        # Body Container initialized directly with the active fees report tab
        self.body_container = ft.Container(content=self._build_fees_report_tab(), expand=True)

        self.content = ft.Column(
            controls=[
                header,
                self.toast_banner,
                self.tab_buttons,
                ft.Divider(height=1, color=AppTheme.BORDER),
                self.body_container,
            ],
            spacing=AppTheme.PAD_MD,
            expand=True,
        )

    def _set_tab(self, index: int) -> None:
        self.active_tab = index
        if index == 0:
            self.tab_report_btn.bgcolor = AppTheme.PRIMARY
            self.tab_report_btn.border = ft.Border.all(1, AppTheme.PRIMARY)
            row0: ft.Row = self.tab_report_btn.content
            row0.controls[0].color = AppTheme.SURFACE
            row0.controls[1].color = AppTheme.SURFACE

            self.tab_filter_btn.bgcolor = AppTheme.SURFACE
            self.tab_filter_btn.border = ft.Border.all(1, AppTheme.BORDER)
            row1: ft.Row = self.tab_filter_btn.content
            row1.controls[0].color = AppTheme.TEXT_SECONDARY
            row1.controls[1].color = AppTheme.TEXT_PRIMARY

            self.body_container.content = self._build_fees_report_tab()
            self._safe_update()
            self._trigger_load_data()
        else:
            self.tab_report_btn.bgcolor = AppTheme.SURFACE
            self.tab_report_btn.border = ft.Border.all(1, AppTheme.BORDER)
            row0: ft.Row = self.tab_report_btn.content
            row0.controls[0].color = AppTheme.TEXT_SECONDARY
            row0.controls[1].color = AppTheme.TEXT_PRIMARY

            self.tab_filter_btn.bgcolor = AppTheme.PRIMARY
            self.tab_filter_btn.border = ft.Border.all(1, AppTheme.PRIMARY)
            row1: ft.Row = self.tab_filter_btn.content
            row1.controls[0].color = AppTheme.SURFACE
            row1.controls[1].color = AppTheme.SURFACE

            self.body_container.content = self._build_amount_filter_tab()
            self._safe_update()

    def did_mount(self) -> None:
        """
        Lifecycle hook invoked automatically by Flet when the control
        is mounted into the live page tree and self.page is accessible.
        Ensures immediate rendering of the fees report without requiring user interaction.
        """
        p = self.safe_page
        if p:
            self._page = p
            self._root_page = p

        from core.cache.fees_cache import FeesCacheManager
        if not self.report_data or not self._active_data_table:
            if FeesCacheManager.is_loaded():
                self._perform_query_and_render()
            else:
                self.load_data(sync=True)

        self._safe_update()
        p = self.safe_page
        if p and hasattr(p, "update"):
            try:
                p.update()
            except Exception:
                pass

    def _safe_update(self) -> None:
        """
        Safely dispatches UI updates to the active Flet page session.
        Explicitly updates mutated sub-controls (table_area, pagination controls, KPI container, etc.)
        as well as the parent container, ensuring Flet's sparse change tracking captures
        all modifications and renders immediately without requiring secondary user interaction.
        """
        for ctrl in [
            getattr(self, "table_area", None),
            getattr(self, "pagination_card", None),
            getattr(self, "pagination_info", None),
            getattr(self, "prev_page_btn", None),
            getattr(self, "next_page_btn", None),
            getattr(self, "kpi_cards_container", None),
            getattr(self, "body_container", None),
            getattr(self, "cache_status_text", None),
            getattr(self, "cache_pill", None),
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

        p = getattr(self, "safe_page", None)
        if p and hasattr(p, "update"):
            try:
                p.update()
            except Exception:
                pass

    @property
    def safe_page(self) -> Optional[ft.Page]:
        try:
            return getattr(self, "_root_page", None) or self.page or getattr(self, "_page", None)
        except (RuntimeError, AttributeError):
            return getattr(self, "_root_page", None) or getattr(self, "_page", None)

    def show_toast(self, message: str, is_error: bool = False, is_success: bool = False) -> None:
        self.toast_text.value = message
        self.toast_text.color = AppTheme.DANGER if is_error else (AppTheme.SUCCESS if is_success else AppTheme.PRIMARY)
        row: ft.Row = self.toast_banner.content
        row.controls[0].name = ft.Icons.ERROR_OUTLINE if is_error else (ft.Icons.CHECK_CIRCLE if is_success else ft.Icons.INFO)
        row.controls[0].color = AppTheme.DANGER if is_error else (AppTheme.SUCCESS if is_success else AppTheme.PRIMARY)
        self.toast_banner.bgcolor = AppTheme.DANGER_LIGHT if is_error else (AppTheme.SUCCESS_LIGHT if is_success else AppTheme.PRIMARY_LIGHT)
        self.toast_banner.visible = True
        self._safe_update()

    def load_data(self, sync: bool = False) -> None:
        """
        Public entrypoint called by DashboardScreen.mount_view.
        Executes non-blocking background fetch if connected to live page,
        or synchronous fetch when running in unit tests / headless.
        """
        if self.active_tab == 0:
            if not hasattr(self, "table_area") or self.table_area is None:
                self.body_container.content = self._build_fees_report_tab()
            from core.cache.fees_cache import FeesCacheManager
            if FeesCacheManager.is_loaded() or sync:
                self._perform_query_and_render()
            else:
                self._trigger_load_data(sync=False)
            self._safe_update()
            p = self.safe_page
            if p and hasattr(p, "update"):
                try:
                    p.update()
                except Exception:
                    pass
        else:
            self.body_container.content = self._build_amount_filter_tab()
            self._safe_update()

    def _trigger_load_data(self, sync: bool = False) -> None:
        """Sets loading animation, updates UI immediately, and executes single-shot page loader."""
        self._load_generation += 1
        current_gen = self._load_generation

        # If headless/unit-test (no page attached, or mock page without real session), sync requested,
        # or bulk in-memory cache is already loaded: render synchronously without delay or worker thread!
        is_mock_or_headless = self.safe_page is None or not hasattr(self.safe_page, "session")
        from core.cache.fees_cache import FeesCacheManager
        if sync or is_mock_or_headless or FeesCacheManager.is_loaded():
            self._perform_query_and_render()
            return

        # ── CACHE-FIRST CHECK: Instant zero-flicker render on cache hit ──
        status_param = None if self.selected_status == "ALL" else self.selected_status
        from core.cache.fees_cache import FeesCacheManager
        page_key = FeesCacheManager.make_page_key(
            self.selected_course_id,
            status_param,
            self.search_text,
            self.sort_by,
            self.page_size,
            self.current_page,
        )
        count_key = FeesCacheManager.make_count_key(
            self.selected_course_id,
            status_param,
            self.search_text,
        )

        cached_block = FeesCacheManager.get_block(page_key)
        cached_count = FeesCacheManager.get_total_count(count_key)

        if cached_block is not None and cached_count is not None:
            self.total_count = cached_count
            self.total_pages = max(1, (self.total_count + self.page_size - 1) // self.page_size)
            self.report_data = list(cached_block)
            if hasattr(self, "table_area") and self.table_area:
                self.table_area.content = self._build_table_view() if self.report_data else self._build_empty_view()

            start_item = (self.current_page - 1) * self.page_size + 1 if self.total_count > 0 else 0
            end_item = min(self.total_count, (self.current_page - 1) * self.page_size + len(self.report_data))
            if hasattr(self, "pagination_info") and self.pagination_info:
                self.pagination_info.value = (
                    f"Showing {start_item} - {end_item} of {self.total_count} admissions "
                    f"(Page {self.current_page} of {self.total_pages})"
                    if self.total_count > 0 else "Showing 0 of 0 admissions"
                )
            if hasattr(self, "prev_page_btn") and self.prev_page_btn:
                self.prev_page_btn.disabled = self.current_page <= 1
            if hasattr(self, "next_page_btn") and self.next_page_btn:
                self.next_page_btn.disabled = self.current_page >= self.total_pages
            if hasattr(self, "streaming_badge") and self.streaming_badge:
                self.streaming_badge.visible = False

            self._rendered_cache_version = FeesCacheManager.get_version()
            self._rendered_filter_state = (
                self.selected_course_id,
                self.selected_status,
                self.search_text,
                self.sort_by,
                self.current_page,
                self.page_size,
            )
            self._update_cache_badge()
            self._update_kpi_cards()
            self._safe_update()
            return

        # Live UI: Immediately show animated loading indicator in the table area
        if hasattr(self, "table_area") and self.table_area:
            self.table_area.content = self._build_loading_view()
        if hasattr(self, "prev_page_btn") and self.prev_page_btn:
            self.prev_page_btn.disabled = True
        if hasattr(self, "next_page_btn") and self.next_page_btn:
            self.next_page_btn.disabled = True
        if hasattr(self, "streaming_badge") and self.streaming_badge:
            self.streaming_badge.visible = False
        self._safe_update()

        # Propagate current SecurityContext into worker thread
        user_id = SecurityContext.get_current_user_id()
        username = SecurityContext.get_current_username()
        role = SecurityContext.get_current_role()

        def _worker():
            try:
                SecurityContext.set_current_user(user_id=user_id, username=username, role=role)
                if current_gen != self._load_generation:
                    return
                self._load_page_data(current_gen)
            except Exception as ex:
                LogService.error(f"Error loading fees report: {ex}", context="ReportsHome")
                if current_gen == self._load_generation:
                    self.show_toast(f"Failed to load records: {ex}", is_error=True)

        worker_thread = threading.Thread(target=_worker, daemon=True)
        worker_thread.start()

    def _load_page_data(self, current_gen: int) -> None:
        """
        Loads the active page in a single shot (default 50 rows)
        and renders the dual-table view without micro-chunk redraws.
        """
        status_param = None if self.selected_status == "ALL" else self.selected_status
        result = self.controller.get_admission_fees_report_paginated(
            course_id=self.selected_course_id,
            status=status_param,
            search=self.search_text,
            sort_by=self.sort_by,
            page=self.current_page,
            page_size=self.page_size,
        )

        if current_gen != self._load_generation:
            return

        self.report_data = list(result["rows"])
        self.total_count = result["total_count"]
        self.total_pages = max(1, result["total_pages"])
        self.current_page = result["page"]

        if self.total_count == 0 or not self.report_data:
            self.report_data = []
            if hasattr(self, "table_area") and self.table_area:
                self.table_area.content = self._build_empty_view()
            if hasattr(self, "pagination_info") and self.pagination_info:
                self.pagination_info.value = "Showing 0 of 0 admissions"
            if hasattr(self, "prev_page_btn") and self.prev_page_btn:
                self.prev_page_btn.disabled = True
            if hasattr(self, "next_page_btn") and self.next_page_btn:
                self.next_page_btn.disabled = True
            if hasattr(self, "streaming_badge") and self.streaming_badge:
                self.streaming_badge.visible = False
            self._update_cache_badge()
            self._update_kpi_cards()
            self._safe_update()
            return

        if hasattr(self, "table_area") and self.table_area:
            self.table_area.content = self._build_table_view()

        start_item = (self.current_page - 1) * self.page_size + 1 if self.total_count > 0 else 0
        end_item = min(self.total_count, (self.current_page - 1) * self.page_size + len(self.report_data))
        if hasattr(self, "pagination_info") and self.pagination_info:
            self.pagination_info.value = (
                f"Showing {start_item} - {end_item} of {self.total_count} admissions "
                f"(Page {self.current_page} of {self.total_pages})"
            )
        if hasattr(self, "prev_page_btn") and self.prev_page_btn:
            self.prev_page_btn.disabled = self.current_page <= 1
        if hasattr(self, "next_page_btn") and self.next_page_btn:
            self.next_page_btn.disabled = self.current_page >= self.total_pages
        if hasattr(self, "streaming_badge") and self.streaming_badge:
            self.streaming_badge.visible = False

        from core.cache.fees_cache import FeesCacheManager
        self._rendered_cache_version = FeesCacheManager.get_version()
        self._rendered_filter_state = (
            self.selected_course_id,
            self.selected_status,
            self.search_text,
            self.sort_by,
            self.current_page,
            self.page_size,
        )
        self._update_cache_badge()
        self._update_kpi_cards()
        self._safe_update()

    def _stream_chunks_and_render(self, current_gen: int) -> None:
        """Backward compatibility alias delegating to single-shot page loader."""
        self._load_page_data(current_gen)

    def _perform_query_and_render(self) -> None:
        """Executes single-shot query and updates table & pagination controls (used for sync / headless)."""
        self._load_page_data(self._load_generation)

    def _get_cached_courses(self) -> list[Any]:
        if self._courses_cache is None:
            try:
                courses, _ = self.course_controller.list_courses(limit=100)
                self._courses_cache = courses
            except Exception:
                self._courses_cache = []
        return self._courses_cache

    def handle_export_excel(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Exports filtered fees report to Excel (.xlsx) with custom save prompt."""
        try:
            status_param = None if self.selected_status == "ALL" else self.selected_status
            path = self.controller.export_filtered_fees_report_excel(
                course_id=self.selected_course_id,
                status=status_param,
                search=self.search_text,
                sort_by=self.sort_by,
            )
            export_and_prompt_save(
                source_file_path=path,
                dialog_title="Save Fee Report As",
                allowed_extensions=[".xlsx"],
                show_toast=self.show_toast,
            )
        except Exception as ex:
            self.show_toast(f"Excel export error: {ex}", is_error=True)

    def handle_export_csv(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Exports filtered fees report to CSV format with custom save prompt."""
        try:
            status_param = None if self.selected_status == "ALL" else self.selected_status
            path = self.controller.export_filtered_fees_report_csv(
                course_id=self.selected_course_id,
                status=status_param,
                search=self.search_text,
                sort_by=self.sort_by,
            )
            export_and_prompt_save(
                source_file_path=path,
                dialog_title="Save Fee Report CSV As",
                allowed_extensions=[".csv"],
                show_toast=self.show_toast,
            )
        except Exception as ex:
            self.show_toast(f"CSV export error: {ex}", is_error=True)

    def handle_collect_payment(self, admission_id: Optional[int] = None) -> None:
        """Opens smooth Payment Gateway modal from Fees Module."""
        p = self.safe_page
        if not p:
            return
        from modules.admission.views.payment_dialog import PaymentDialog
        dlg = PaymentDialog(
            admission_id=admission_id,
            page=p,
            on_payment_completed=lambda pid: self.handle_sync_cache(None),
        )
        p.show_dialog(dlg)

    def handle_collect_payment_for_row(self, r: dict[str, Any]) -> None:
        """Opens pre-filled Payment Gateway modal for a specific student with outstanding balance."""
        p = self.safe_page
        if not p:
            return
        from modules.admission.views.payment_dialog import PaymentDialog
        adm_id_raw = r.get("admission_id_raw")
        dlg = PaymentDialog(
            admission_id=int(adm_id_raw) if adm_id_raw else None,
            student_name=r.get("name", ""),
            course_name=r.get("course_name", ""),
            candidate_number=r.get("admission_id", ""),
            total_fee=float(r.get("total_fees", 0.0)),
            already_paid=float(r.get("total_paid", 0.0)),
            page=p,
            on_payment_completed=lambda pid: self.handle_sync_cache(None),
        )
        p.show_dialog(dlg)

    def handle_view_receipt(self, payment_id: int) -> None:
        """Opens Receipt Dialog for a recorded payment."""
        p = self.safe_page
        if not p:
            return
        from modules.receipts.controller import ReceiptController
        from modules.admission.views.receipt_dialog import ReceiptDialog
        r_dto = ReceiptController().get_receipt_by_payment(payment_id)
        if r_dto:
            dlg = ReceiptDialog(receipt=r_dto)
            p.show_dialog(dlg)
        else:
            self.show_toast(f"No receipt found for Payment #{payment_id}", is_error=True)

    # ── TAB 1: ADMISSION FEES REPORT (SHELL & 17 COLUMNS) ──
    def _build_fees_report_tab(self) -> ft.Container:
        # Search Box
        self.search_box = ft.TextField(
            hint_text="Search candidate, mobile, admission no...",
            prefix_icon=ft.Icons.SEARCH,
            value=self.search_text,
            border_radius=AppTheme.RADIUS_MD,
            width=260,
            text_size=AppTheme.SIZE_BODY,
            content_padding=ft.Padding(12, 10, 12, 10),
            on_submit=self._handle_search_submit,
        )

        self.search_btn = ft.FilledButton(
            "Search",
            icon=ft.Icons.SEARCH,
            style=ft.ButtonStyle(
                bgcolor=AppTheme.PRIMARY,
                color=AppTheme.SURFACE,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
            ),
            on_click=self._handle_search_submit,
        )

        # Courses Dropdown
        courses = self._get_cached_courses()
        c_options = [ft.DropdownOption(key="ALL", text="All Courses")]
        for c in courses:
            c_options.append(ft.DropdownOption(key=str(c.id), text=c.name))

        self.course_dropdown = ft.Dropdown(
            label="Course",
            options=c_options,
            value=str(self.selected_course_id) if self.selected_course_id else "ALL",
            border_radius=AppTheme.RADIUS_MD,
            width=200,
            content_padding=ft.Padding(10, 8, 10, 8),
            on_select=self._handle_course_change,
        )

        # Status Dropdown
        self.status_dropdown = ft.Dropdown(
            label="Admission Status",
            options=[
                ft.DropdownOption(key="ALL", text="All Statuses"),
                ft.DropdownOption(key="CONFIRMED", text="Confirmed"),
                ft.DropdownOption(key="REGISTERED", text="Registered"),
                ft.DropdownOption(key="CANCELLED", text="Cancelled"),
            ],
            value=self.selected_status or "ALL",
            border_radius=AppTheme.RADIUS_MD,
            width=160,
            content_padding=ft.Padding(10, 8, 10, 8),
            on_select=self._handle_status_change,
        )

        # Sort Dropdown
        self.sort_dropdown = ft.Dropdown(
            label="Sort Ledger",
            options=[
                ft.DropdownOption(key="NONE", text="Default (Admission ID)"),
                ft.DropdownOption(key="INST1", text="1st Installment"),
                ft.DropdownOption(key="INST2", text="2nd Installment"),
                ft.DropdownOption(key="INST3", text="3rd Installment"),
                ft.DropdownOption(key="INST4", text="4th Installment"),
                ft.DropdownOption(key="PAID", text="Total Fees Paid"),
                ft.DropdownOption(key="PENDING", text="Pending Fees"),
            ],
            value=self.sort_by or "NONE",
            border_radius=AppTheme.RADIUS_MD,
            width=190,
            content_padding=ft.Padding(10, 8, 10, 8),
            on_select=self._handle_sort_change,
        )

        self.clear_filter_btn = ft.OutlinedButton(
            "Reset Filters",
            icon=ft.Icons.REFRESH,
            style=ft.ButtonStyle(
                color=AppTheme.TEXT_SECONDARY,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
            ),
            on_click=self._handle_reset_filters,
        )

        # Filter Card Container
        self.filter_card = ft.Container(
            content=ft.Row(
                controls=[
                    self.search_box,
                    self.search_btn,
                    self.course_dropdown,
                    self.status_dropdown,
                    self.sort_dropdown,
                    self.clear_filter_btn,
                ],
                spacing=AppTheme.PAD_SM,
                wrap=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=ft.Padding(14, 10, 14, 10),
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
            visible=self.show_controls_panel,
            animate_size=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
            animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT),
        )

        # Table Area Container (Initially shows animated loading state)
        self.table_area = ft.Container(
            content=self._build_table_view() if self.report_data else self._build_loading_view(),
            expand=True,
            animate_size=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
        )

        # Pagination Controls
        start_item = (self.current_page - 1) * self.page_size + 1 if self.total_count > 0 else 0
        end_item = min(self.total_count, self.current_page * self.page_size)

        self.pagination_info = ft.Text(
            f"Showing {start_item} - {end_item} of {self.total_count} admissions (Page {self.current_page} of {self.total_pages})"
            if self.total_count > 0 else "Showing 0 of 0 admissions",
            size=AppTheme.SIZE_CAPTION,
            color=AppTheme.TEXT_SECONDARY,
            weight=ft.FontWeight.W_500,
        )

        self.streaming_indicator = ft.ProgressRing(width=14, height=14, stroke_width=2, color=AppTheme.PRIMARY)
        self.streaming_text = ft.Text("Loading records...", size=AppTheme.SIZE_CAPTION, color=AppTheme.PRIMARY, weight=ft.FontWeight.W_500)
        self.streaming_badge = ft.Container(
            content=ft.Row(
                controls=[
                    self.streaming_indicator,
                    self.streaming_text,
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=AppTheme.PRIMARY_LIGHT,
            padding=ft.Padding(8, 3, 10, 3),
            border_radius=AppTheme.RADIUS_SM,
            visible=False,
        )

        self.page_size_dropdown = ft.Dropdown(
            value=str(self.page_size),
            width=120,
            text_size=AppTheme.SIZE_CAPTION,
            content_padding=ft.Padding(8, 6, 8, 6),
            border_radius=AppTheme.RADIUS_MD,
            options=[
                ft.DropdownOption(key="10", text="10 / page"),
                ft.DropdownOption(key="30", text="30 / page"),
                ft.DropdownOption(key="50", text="50 / page"),
                ft.DropdownOption(key="100", text="100 / page"),
            ],
            on_select=self._handle_page_size_change,
        )

        self.prev_page_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_LEFT,
            tooltip="Previous Page",
            disabled=self.current_page <= 1,
            on_click=self._handle_prev_page,
        )
        self.next_page_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_RIGHT,
            tooltip="Next Page",
            disabled=self.current_page >= self.total_pages,
            on_click=self._handle_next_page,
        )

        self.pagination_card = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Row(
                        controls=[
                            self.pagination_info,
                            self.streaming_badge,
                        ],
                        spacing=AppTheme.PAD_SM,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        controls=[
                            ft.Text("Rows per page:", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                            self.page_size_dropdown,
                            ft.Container(width=4),
                            self.prev_page_btn,
                            self.next_page_btn,
                        ],
                        spacing=AppTheme.PAD_XS,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=ft.Padding(14, 8, 14, 8),
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    self.kpi_cards_container,
                    self.filter_card,
                    self.table_area,
                    self.pagination_card,
                ],
                spacing=AppTheme.PAD_SM,
                expand=True,
            ),
            expand=True,
        )

    def handle_toggle_controls(self, e=None) -> None:
        self.show_controls_panel = not self.show_controls_panel
        if hasattr(self, "filter_card") and self.filter_card:
            self.filter_card.visible = self.show_controls_panel
        if self.show_controls_panel:
            self.toggle_controls_btn.content = ft.Text("Hide Filters", size=AppTheme.SIZE_CAPTION)
            self.toggle_controls_btn.icon = ft.Icons.FILTER_ALT_OFF
            self.toggle_controls_btn.tooltip = "Hide filter and search controls"
        else:
            self.toggle_controls_btn.content = ft.Text("Show Filters", size=AppTheme.SIZE_CAPTION)
            self.toggle_controls_btn.icon = ft.Icons.FILTER_ALT
            self.toggle_controls_btn.tooltip = "Show filter and search controls"
        self._safe_update()

    def _build_loading_view(self, message: str = "Loading financial & installment records...") -> ft.Container:
        """High-clarity animated spinner shown immediately on click / filter."""
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.ProgressRing(width=44, height=44, stroke_width=3.5, color=AppTheme.PRIMARY),
                    ft.Container(height=8),
                    ft.Text(message, size=AppTheme.SIZE_BODY, weight=ft.FontWeight.W_600, color=AppTheme.TEXT_PRIMARY),
                    ft.Text(
                        "Calculating 4-tier installment schedules and payment ledgers...",
                        size=AppTheme.SIZE_CAPTION,
                        color=AppTheme.TEXT_MUTED,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=AppTheme.PAD_XS,
            ),
            padding=ft.Padding(0, 60, 0, 60),
            alignment=ft.Alignment(0, 0),
            bgcolor=AppTheme.SURFACE,
            border=ft.Border.all(1, AppTheme.BORDER),
            border_radius=AppTheme.RADIUS_MD,
            expand=True,
        )

    def _build_empty_view(self) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.SEARCH_OFF, size=48, color=AppTheme.TEXT_MUTED),
                    ft.Text("No admission records match current filters", size=AppTheme.SIZE_H3, weight=ft.FontWeight.W_600, color=AppTheme.TEXT_SECONDARY),
                    ft.Text("Try adjusting your search keywords, course filter, or status.", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=AppTheme.PAD_XS,
            ),
            padding=ft.Padding(0, 60, 0, 60),
            alignment=ft.Alignment(0, 0),
            bgcolor=AppTheme.SURFACE,
            border=ft.Border.all(1, AppTheme.BORDER),
            border_radius=AppTheme.RADIUS_MD,
            expand=True,
        )

    def _create_table_row(self, r: dict[str, Any]) -> ft.DataRow:
        st = r["admission_status"]
        st_color = AppTheme.SUCCESS if st in ("CONFIRMED", "REGISTERED") else (AppTheme.DANGER if st == "CANCELLED" else AppTheme.PRIMARY)
        st_bg = AppTheme.SUCCESS_LIGHT if st in ("CONFIRMED", "REGISTERED") else (AppTheme.DANGER_LIGHT if st == "CANCELLED" else AppTheme.PRIMARY_LIGHT)

        pending = float(r.get("pending_fees", 0.0))
        action_btn = (
            ft.IconButton(
                icon=ft.Icons.PAYMENTS,
                icon_color=AppTheme.SUCCESS,
                icon_size=20,
                tooltip=f"Collect Payment (Pending: ₹{pending:,.2f})",
                on_click=lambda _, row_data=r: self.handle_collect_payment_for_row(row_data),
            )
            if pending > 0
            else ft.Icon(ft.Icons.CHECK_CIRCLE, color=AppTheme.SUCCESS, size=20)
        )

        return ft.DataRow(
            cells=[
                ft.DataCell(ft.Text(str(r["sr_no"]), size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY, width=55)),
                ft.DataCell(ft.Text(r["course_name"], weight=ft.FontWeight.W_500, size=AppTheme.SIZE_BODY, no_wrap=True, width=140, overflow=ft.TextOverflow.ELLIPSIS)),
                ft.DataCell(ft.Text(r["admission_date"], size=AppTheme.SIZE_BODY, no_wrap=True, width=110)),
                ft.DataCell(ft.Text(r["admission_id"], weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY, size=AppTheme.SIZE_BODY, no_wrap=True, width=110)),
                ft.DataCell(ft.Text(r["name"], weight=ft.FontWeight.W_600, size=AppTheme.SIZE_BODY, no_wrap=True, width=160, overflow=ft.TextOverflow.ELLIPSIS)),
                ft.DataCell(ft.Text(r["mob_no"], size=AppTheme.SIZE_BODY, no_wrap=True, width=110)),
                ft.DataCell(
                    ft.Container(
                        content=ft.Text(st, size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD, color=st_color),
                        bgcolor=st_bg,
                        padding=ft.Padding(8, 3, 8, 3),
                        border_radius=AppTheme.RADIUS_SM,
                        width=100,
                    )
                ),
                ft.DataCell(ft.Text(f"₹{r['total_fees']:,.2f}", weight=ft.FontWeight.W_600, size=AppTheme.SIZE_BODY, no_wrap=True, width=105)),
                ft.DataCell(ft.Text(f"₹{r['inst1']:,.2f}" if r["inst1"] > 0 else "—", size=AppTheme.SIZE_BODY, no_wrap=True, width=95)),
                ft.DataCell(ft.Text(f"₹{r['inst2']:,.2f}" if r["inst2"] > 0 else "—", size=AppTheme.SIZE_BODY, no_wrap=True, width=95)),
                ft.DataCell(ft.Text(f"₹{r['inst3']:,.2f}" if r["inst3"] > 0 else "—", size=AppTheme.SIZE_BODY, no_wrap=True, width=95)),
                ft.DataCell(ft.Text(f"₹{r['inst4']:,.2f}" if r["inst4"] > 0 else "—", size=AppTheme.SIZE_BODY, no_wrap=True, width=95)),
                ft.DataCell(ft.Text(f"₹{r['total_paid']:,.2f}", color=AppTheme.SUCCESS, weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_BODY, no_wrap=True, width=105)),
                ft.DataCell(ft.Text(f"₹{r['pending_fees']:,.2f}", color=AppTheme.DANGER if r['pending_fees'] > 0 else AppTheme.SUCCESS, weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_BODY, no_wrap=True, width=110)),
                ft.DataCell(ft.Text(r["address"] or "—", size=AppTheme.SIZE_BODY, no_wrap=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, width=150)),
                ft.DataCell(ft.Text(r["friend_name"] or "—", size=AppTheme.SIZE_BODY, no_wrap=True, width=120)),
                ft.DataCell(ft.Text(r["friend_mobile"] or "—", size=AppTheme.SIZE_BODY, no_wrap=True, width=110)),
                ft.DataCell(ft.Container(content=action_btn, width=70, alignment=ft.Alignment(0, 0))),
            ]
        )

    def _build_table_view(self) -> ft.Container:
        """Constructs a responsive auto-fitting 2-axis scrolling DataTable with a frozen header."""
        if not self.report_data:
            self._active_data_table = None
            return self._build_empty_view()

        rows = [self._create_table_row(r) for r in self.report_data]

        col_specs = [
            ("SR.NO", 55, False),
            ("COURSE NAME", 140, False),
            ("ADMISSION DATE", 110, False),
            ("ADMISSION ID", 110, False),
            ("NAME", 160, False),
            ("MOB NO", 110, False),
            ("STATUS", 100, False),
            ("TOTAL FEES", 105, True),
            ("1ST INST.", 95, True),
            ("2ND INST.", 95, True),
            ("3RD INST.", 95, True),
            ("4TH INST.", 95, True),
            ("TOTAL PAID", 105, True),
            ("PENDING FEES", 110, True),
            ("ADDRESS / RESIDENCE", 150, False),
            ("FRIEND NAME", 120, False),
            ("FRIEND CONTACT", 110, False),
            ("ACTION", 70, False),
        ]

        header_cols = [
            ft.DataColumn(ft.Container(content=ft.Text(label, weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION), width=w), numeric=num)
            for label, w, num in col_specs
        ]

        dummy_cols = [
            ft.DataColumn(ft.Container(width=w), numeric=num)
            for _, w, num in col_specs
        ]

        header_table = ft.DataTable(
            columns=header_cols,
            rows=[],
            heading_row_color=AppTheme.SURFACE_VARIANT,
            heading_row_height=44,
            column_spacing=14,
            horizontal_margin=12,
            border=ft.Border.all(1, AppTheme.BORDER),
            border_radius=ft.BorderRadius(AppTheme.RADIUS_MD, AppTheme.RADIUS_MD, 0, 0),
            horizontal_lines=ft.BorderSide(0.5, AppTheme.BORDER),
            vertical_lines=ft.BorderSide(0.5, AppTheme.BORDER),
        )

        body_table = ft.DataTable(
            columns=dummy_cols,
            rows=rows,
            heading_row_height=0,
            divider_thickness=0,
            data_row_min_height=42,
            data_row_max_height=48,
            column_spacing=14,
            horizontal_margin=12,
            border=ft.Border.all(1, AppTheme.BORDER),
            border_radius=ft.BorderRadius(0, 0, AppTheme.RADIUS_MD, AppTheme.RADIUS_MD),
            horizontal_lines=ft.BorderSide(0.5, AppTheme.BORDER),
            vertical_lines=ft.BorderSide(0.5, AppTheme.BORDER),
        )
        self._active_data_table = body_table

        col_spacing = 14
        horiz_margin = 12
        total_cols_w = sum(w for _, w, *_ in col_specs)
        total_table_w = total_cols_w + (len(col_specs) - 1) * col_spacing + 2 * horiz_margin

        body_wrapper = ft.Container(
            content=ft.ListView(
                controls=[body_table],
                expand=True,
            ),
            expand=True,
            width=total_table_w,
        )

        table_column = ft.Column(
            controls=[
                header_table,
                body_wrapper,
            ],
            spacing=0,
            width=total_table_w,
        )

        return ft.Container(
            content=ft.Row(
                controls=[table_column],
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            bgcolor=AppTheme.SURFACE,
            border=ft.Border.all(1, AppTheme.BORDER),
            border_radius=AppTheme.RADIUS_MD,
            expand=True,
            animate_size=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
        )

    # ── EVENT HANDLERS ──
    def _handle_search_submit(self, e: Optional[ft.ControlEvent] = None) -> None:
        self.search_text = (self.search_box.value or "").strip()
        self.current_page = 1
        self._trigger_load_data()

    def _handle_course_change(self, e: ft.ControlEvent) -> None:
        val = self.course_dropdown.value
        self.selected_course_id = int(val) if val and val != "ALL" else None
        self.current_page = 1
        self._trigger_load_data()

    def _handle_status_change(self, e: ft.ControlEvent) -> None:
        self.selected_status = self.status_dropdown.value or "ALL"
        self.current_page = 1
        self._trigger_load_data()

    def _handle_sort_change(self, e: ft.ControlEvent) -> None:
        val = self.sort_dropdown.value
        self.sort_by = val if val != "NONE" else None
        self.current_page = 1
        self._trigger_load_data()

    def _handle_reset_filters(self, e: ft.ControlEvent) -> None:
        self.search_text = ""
        self.search_box.value = ""
        self.selected_course_id = None
        self.course_dropdown.value = "ALL"
        self.selected_status = "ALL"
        self.status_dropdown.value = "ALL"
        self.sort_by = None
        self.sort_dropdown.value = "NONE"
        self.current_page = 1
        self._trigger_load_data()

    def _handle_prev_page(self, e: ft.ControlEvent) -> None:
        if self.current_page > 1:
            self.current_page -= 1
            self._trigger_load_data()

    def _handle_next_page(self, e: ft.ControlEvent) -> None:
        if self.current_page < self.total_pages:
            self.current_page += 1
            self._trigger_load_data()

    def _handle_page_size_change(self, e: ft.ControlEvent) -> None:
        try:
            val = getattr(e, "data", None) or (self.page_size_dropdown.value if hasattr(self, "page_size_dropdown") and self.page_size_dropdown else None)
            if val:
                self.page_size = int(val)
                if hasattr(self, "page_size_dropdown") and self.page_size_dropdown:
                    self.page_size_dropdown.value = str(val)
            else:
                self.page_size = int(self.page_size_dropdown.value)
            self.current_page = 1
            self._trigger_load_data(sync=True)
            self._safe_update()
            p = self.safe_page
            if p and hasattr(p, "update"):
                try:
                    p.update()
                except Exception:
                    pass
        except (ValueError, TypeError):
            pass

    # ── TAB 2: PAYMENT AMOUNT FILTER ──
    def _build_amount_filter_tab(self) -> ft.Container:
        amt_input = ft.TextField(
            label="Payment Amount (₹) *",
            value=f"{self.filter_amount:.0f}",
            keyboard_type=ft.KeyboardType.NUMBER,
            border_radius=AppTheme.RADIUS_MD,
            width=200,
            prefix_icon=ft.Icons.CURRENCY_RUPEE,
            content_padding=ft.Padding(12, 10, 12, 10),
        )

        def do_filter(e):
            try:
                self.filter_amount = float(amt_input.value or 0.0)
            except ValueError:
                self.filter_amount = 500.0
            self.body_container.content = self._build_amount_filter_tab()
            self._safe_update()

        filter_btn = ft.FilledButton(
            "Search Payments",
            icon=ft.Icons.SEARCH,
            style=ft.ButtonStyle(
                bgcolor=AppTheme.PRIMARY,
                color=AppTheme.SURFACE,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
            ),
            on_click=do_filter,
        )

        amt_input.on_submit = do_filter

        filter_card = ft.Container(
            content=ft.Row(
                controls=[
                    amt_input,
                    filter_btn,
                    ft.Container(width=1, height=32, bgcolor=AppTheme.BORDER),
                    ft.Text(f"Showing exact matches of ₹{self.filter_amount:,.2f}", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.W_500, color=AppTheme.TEXT_SECONDARY),
                ],
                spacing=AppTheme.PAD_SM,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=ft.Padding(16, 12, 16, 12),
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        self.payment_data = self.controller.filter_payments_by_amount(target_amount=self.filter_amount)
        self._update_cache_badge()

        rows = []
        for p in self.payment_data:
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(f"#{p['payment_id']}", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_BODY)),
                        ft.DataCell(ft.Text(p["admission_number"], weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY, size=AppTheme.SIZE_BODY)),
                        ft.DataCell(ft.Text(p["student_name"], weight=ft.FontWeight.W_600, size=AppTheme.SIZE_BODY)),
                        ft.DataCell(ft.Text(p["mobile_number"], size=AppTheme.SIZE_BODY)),
                        ft.DataCell(ft.Text(p["course_name"], size=AppTheme.SIZE_BODY)),
                        ft.DataCell(ft.Text(f"Installment #{p['installment_number']}", size=AppTheme.SIZE_BODY)),
                        ft.DataCell(ft.Text(f"₹{p['amount']:,.2f}", color=AppTheme.SUCCESS, weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_BODY)),
                        ft.DataCell(
                            ft.Container(
                                content=ft.Text(p["payment_mode"], size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                                bgcolor=AppTheme.PRIMARY_LIGHT,
                                padding=ft.Padding(8, 3, 8, 3),
                                border_radius=AppTheme.RADIUS_SM,
                            )
                        ),
                        ft.DataCell(ft.Text(p["payment_date"], size=AppTheme.SIZE_BODY)),
                        ft.DataCell(ft.Text(p["collector_name"], size=AppTheme.SIZE_BODY)),
                        ft.DataCell(
                            ft.IconButton(
                                icon=ft.Icons.RECEIPT_LONG,
                                icon_color=AppTheme.PRIMARY,
                                tooltip=f"View Receipt #{p['payment_id']}",
                                on_click=lambda _, pid=p["payment_id"]: self.handle_view_receipt(pid),
                            )
                        ),
                    ]
                )
            )

        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Payment ID", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
                ft.DataColumn(ft.Text("Admission No", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
                ft.DataColumn(ft.Text("Student Name", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
                ft.DataColumn(ft.Text("Mobile Number", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
                ft.DataColumn(ft.Text("Course", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
                ft.DataColumn(ft.Text("Installment", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
                ft.DataColumn(ft.Text("Amount", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION), numeric=True),
                ft.DataColumn(ft.Text("Mode", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
                ft.DataColumn(ft.Text("Payment Date", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
                ft.DataColumn(ft.Text("Collected By", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
                ft.DataColumn(ft.Text("Receipt", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION)),
            ],
            rows=rows,
            heading_row_color=AppTheme.SURFACE_VARIANT,
            heading_row_height=48,
            data_row_min_height=48,
            data_row_max_height=56,
            column_spacing=20,
            horizontal_margin=16,
            border=ft.Border.all(1, AppTheme.BORDER),
            border_radius=AppTheme.RADIUS_MD,
            horizontal_lines=ft.BorderSide(0.5, AppTheme.BORDER),
        )

        empty_view = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.PAYMENTS_OUTLINED, size=48, color=AppTheme.TEXT_MUTED),
                    ft.Text(f"No payment records found for amount ₹{self.filter_amount:,.2f}", size=AppTheme.SIZE_H3, weight=ft.FontWeight.W_600, color=AppTheme.TEXT_SECONDARY),
                    ft.Text("Enter a different payment installment amount above.", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=AppTheme.PAD_XS,
            ),
            padding=ft.Padding(0, 60, 0, 60),
            alignment=ft.Alignment(0, 0),
            bgcolor=AppTheme.SURFACE,
            border=ft.Border.all(1, AppTheme.BORDER),
            border_radius=AppTheme.RADIUS_MD,
            expand=True,
        )

        table_container = ft.Container(
            content=ft.ListView(
                controls=[
                    ft.Row(
                        controls=[table],
                        scroll=ft.ScrollMode.AUTO,
                    )
                ],
                expand=True,
            ),
            expand=True,
            bgcolor=AppTheme.SURFACE,
            border=ft.Border.all(1, AppTheme.BORDER),
            border_radius=AppTheme.RADIUS_MD,
            animate_size=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
        ) if rows else empty_view

        return ft.Container(
            content=ft.Column(
                controls=[
                    filter_card,
                    table_container,
                ],
                spacing=AppTheme.PAD_SM,
                expand=True,
            ),
            expand=True,
            animate_size=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
        )
