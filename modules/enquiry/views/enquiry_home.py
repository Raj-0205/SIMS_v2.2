# modules/enquiry/views/enquiry_home.py

from __future__ import annotations
from datetime import date
from pathlib import Path
from typing import Optional, Any
import urllib.parse
import flet as ft

from core.logger.service import LogService
from ui.themes.theme import AppTheme
from modules.enquiry.controller import EnquiryController
from modules.enquiry.dto import EnquiryDTO, EnquiryCategorySummaryDTO
from modules.enquiry.views.enquiry_form_modal import EnquiryFormModal
from modules.enquiry.views.quick_enquiry_modal import QuickEnquiryModal
from modules.enquiry.views.follow_up_dialog import EnquiryFollowUpDialog
from modules.admission.views.admission_form_modal import AdmissionFormModal
from shared.utils.os_helper import open_path_externally
from shared.utils.export_helper import export_and_prompt_save
from ui.widgets.hover_card import HoverCard

__all__ = ["EnquiryHome"]

STATUS_COLORS = {
    "NEW": ("#EFF6FF", "#1D4ED8", "#93C5FD"),          # Blue
    "CONTACTED": ("#FEF3C7", "#D97706", "#FDE68A"),    # Amber
    "VISITED": ("#F3E8FF", "#7E22CE", "#D8B4FE"),      # Purple
    "CONVERTED": ("#ECFDF5", "#047857", "#A7F3D0"),    # Emerald
    "CLOSED": ("#F1F5F9", "#475569", "#CBD5E1"),       # Gray
}

CATEGORY_CONFIG = {
    "HOT": {
        "label": "Confirm Laga (Hot)",
        "badge_label": "Hot",
        "icon": ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED,
        "color": "#DC2626",
        "bgcolor": "#FEF2F2",
        "border": "#FCA5A5",
        "avatar_bg": "#EF4444",
        "subtext": "Admission pakka",
    },
    "WARM": {
        "label": "Interested (Warm)",
        "badge_label": "Warm",
        "icon": ft.Icons.THUMB_UP_ALT_ROUNDED,
        "color": "#D97706",
        "bgcolor": "#FFFBEB",
        "border": "#FCD34D",
        "avatar_bg": "#F59E0B",
        "subtext": "Needs follow-up",
    },
    "COLD": {
        "label": "Doubtful (Cold)",
        "badge_label": "Cold",
        "icon": ft.Icons.AC_UNIT_ROUNDED,
        "color": "#2563EB",
        "bgcolor": "#EFF6FF",
        "border": "#93C5FD",
        "avatar_bg": "#3B82F6",
        "subtext": "Fee/timing doubt",
    },
    "LOST": {
        "label": "Not Interested (Lost)",
        "badge_label": "Lost",
        "icon": ft.Icons.CANCEL_ROUNDED,
        "color": "#64748B",
        "bgcolor": "#F8FAFC",
        "border": "#CBD5E1",
        "avatar_bg": "#94A3B8",
        "subtext": "Dropped / Closed",
    },
    "CONVERTED": {
        "label": "Admitted (Converted)",
        "badge_label": "Admitted",
        "icon": ft.Icons.CHECK_CIRCLE_ROUNDED,
        "color": "#059669",
        "bgcolor": "#ECFDF5",
        "border": "#A7F3D0",
        "avatar_bg": "#10B981",
        "subtext": "Enrolled student",
    },
}

TIMING_LABELS = {
    "MORNING": "Morning (08:00 AM - 10:00 AM)",
    "AFTERNOON": "Afternoon (12:00 PM - 03:00 PM)",
    "EVENING": "Evening (04:00 PM - 07:00 PM)",
    "WEEKEND": "Weekend Batch",
    "ANY": "Flexible Timing",
}


class EnquiryHome(ft.Container):
    """
    Modern ERP Workspace for Prospective Student Enquiries & Walk-ins.
    Features:
    - Real-time KPI summary counters & Category buckets (Hot, Warm, Cold, Lost, Converted)
    - 15-second Quick Walk-in fast intake modal
    - Direct Call Log & Timeline tracking modal
    - 1-click WhatsApp follow-up messaging
    - One-click Conversion & Auto-fill into Admission Modal
    - Live universal search & multi-dimensional filtering
    """

    def __init__(self) -> None:
        super().__init__(expand=True, padding=AppTheme.PAD_LG)

        self.controller = EnquiryController()
        self.enquiries: list[EnquiryDTO] = []
        self.total_count: int = 0
        self.search_query: str = ""
        self.selected_status: str = "ALL"
        self.selected_category: str = "ALL"
        self.selected_follow_up_filter: str = "ALL"
        self.show_controls_panel: bool = True
        self.auto_fit_screen: bool = True

        self._build_ui()

    @property
    def safe_page(self) -> Optional[ft.Page]:
        try:
            return self.page
        except (RuntimeError, AttributeError):
            return getattr(self, "_root_page", None) or getattr(self, "_page", None)

    def _safe_update(self) -> None:
        p = self.safe_page
        if p:
            try:
                self.update()
            except RuntimeError:
                pass

    def did_mount(self) -> None:
        self.load_data()
        p = self.safe_page
        if p:
            def _on_page_resize(e):
                if not getattr(self, "page", None) and not getattr(self, "_root_page", None):
                    return
                if getattr(self, "auto_fit_screen", True):
                    self._render_table_rows()
                    self._safe_update()
            p.on_resize = _on_page_resize

    def _open_dialog(self, dialog: ft.AlertDialog) -> None:
        p = self.safe_page
        if not p:
            return
        try:
            p.show_dialog(dialog)
        except Exception:
            p.dialog = dialog
            dialog.open = True
            p.update()

    def _build_ui(self) -> None:
        # ── 1. Modern Header Row & Action Toolbar ──
        title_badge = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.FLASH_ON_ROUNDED, size=13, color="#2563EB"),
                    ft.Text("CRM INTAKE HUB", size=10, weight=ft.FontWeight.BOLD, color="#1D4ED8"),
                ],
                spacing=4,
                tight=True,
            ),
            bgcolor="#EFF6FF",
            border=ft.Border.all(1, "#BFDBFE"),
            border_radius=ft.BorderRadius.all(6),
            padding=ft.Padding(7, 3, 7, 3),
        )

        title_text = ft.Text(
            "Enquiries & Walk-ins",
            size=AppTheme.SIZE_H1,
            weight=ft.FontWeight.BOLD,
            color=AppTheme.TEXT_PRIMARY,
        )
        subtitle_text = ft.Text(
            "Track counseling walk-ins, phone enquiries, call remarks timeline, and convert prospective candidates into admissions.",
            size=AppTheme.SIZE_BODY,
            color=AppTheme.TEXT_SECONDARY,
        )

        header_title_col = ft.Column(
            controls=[
                ft.Row(controls=[title_text, title_badge], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                subtitle_text,
            ],
            spacing=3,
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

        # Primary Quick Walk-in button (15-second fast intake) with gradient glow
        self.quick_enquiry_btn = ft.ElevatedButton(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.FLASH_ON_ROUNDED, size=18, color=ft.Colors.WHITE),
                    ft.Text("Quick Walk-in (15s)", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD),
                ],
                spacing=6,
            ),
            style=ft.ButtonStyle(
                bgcolor=AppTheme.PRIMARY,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                padding=ft.Padding(left=18, top=12, right=18, bottom=12),
                elevation=2,
            ),
            tooltip="Ultra-fast 15-second lead intake with automatic mobile clean and village suggestions",
            on_click=self.handle_new_enquiry,
        )

        # Secondary detailed form button
        self.detailed_enquiry_btn = ft.OutlinedButton(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.NOTE_ADD_ROUNDED, size=16, color=AppTheme.PRIMARY),
                    ft.Text("Detailed Form", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.W_600),
                ],
                spacing=5,
            ),
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
            ),
            tooltip="Open full detailed enquiry intake form with qualification and address",
            on_click=self.handle_detailed_enquiry,
        )

        self.export_excel_btn = ft.FilledButton(
            content=ft.Text("Export Excel (.xlsx)", size=AppTheme.SIZE_CAPTION),
            icon=ft.Icons.TABLE_VIEW_ROUNDED,
            style=ft.ButtonStyle(
                bgcolor=AppTheme.PRIMARY,
                color=AppTheme.SURFACE,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
            ),
            on_click=self.handle_export_excel,
        )

        self.refresh_btn = ft.IconButton(
            icon=ft.Icons.REFRESH_ROUNDED,
            icon_size=20,
            tooltip="Refresh Enquiries",
            on_click=lambda _: self.load_data(),
        )

        action_buttons_row = ft.Row(
            controls=[
                self.toggle_controls_btn,
                self.toggle_autofit_btn,
                self.export_excel_btn,
                self.refresh_btn,
                self.detailed_enquiry_btn,
                self.quick_enquiry_btn,
            ],
            spacing=AppTheme.PAD_SM,
            wrap=True,
        )

        header_row = ft.Row(
            controls=[
                header_title_col,
                action_buttons_row,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            wrap=True,
        )

        # ── 2. Modern Bento-Grid KPI Summary Cards ──
        self.kpi_total_text = ft.Text("0", size=24, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY)
        self.kpi_today_text = ft.Text("0", size=24, weight=ft.FontWeight.BOLD, color="#7C3AED")
        self.kpi_today_subtext = ft.Text("Scheduled today", size=10, color=AppTheme.TEXT_SECONDARY)
        self.kpi_hot_text = ft.Text("0", size=24, weight=ft.FontWeight.BOLD, color="#DC2626")
        self.kpi_warm_text = ft.Text("0", size=24, weight=ft.FontWeight.BOLD, color="#D97706")
        self.kpi_cold_text = ft.Text("0", size=24, weight=ft.FontWeight.BOLD, color="#2563EB")
        self.kpi_converted_text = ft.Text("0", size=24, weight=ft.FontWeight.BOLD, color="#059669")
        self.kpi_rate_text = ft.Text("0% conv. rate", size=10, color="#059669", weight=ft.FontWeight.W_500)

        def _make_category_kpi_card(
            title: str,
            count_control: ft.Text,
            sub_control: Optional[ft.Control],
            icon_name: str,
            icon_color: str,
            bg_badge: str,
            border_color: str = "#E2E8F0",
            on_click_action: Any = None,
            tooltip: str = "",
            category_key: str = "",
        ) -> HoverCard:
            col_items: list[ft.Control] = [
                ft.Text(title, size=11, color=AppTheme.TEXT_SECONDARY, weight=ft.FontWeight.W_600),
                count_control,
            ]
            if sub_control:
                col_items.append(sub_control)

            card_content = ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(icon_name, size=22, color=icon_color),
                        padding=9,
                        bgcolor=bg_badge,
                        border_radius=AppTheme.RADIUS_MD,
                    ),
                    ft.Column(
                        controls=col_items,
                        spacing=1,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

            card = HoverCard(
                content=card_content,
                padding=ft.Padding(14, 12, 14, 12),
                border_radius=AppTheme.RADIUS_MD,
                col={"xs": 12, "sm": 6, "md": 4, "lg": 2},
                ink=bool(on_click_action),
                on_click=on_click_action,
                tooltip=tooltip or f"Filter by {title}",
            )
            card._category_key = category_key
            card._base_border_color = border_color
            return card

        self.card_today = _make_category_kpi_card(
            "Today's Follow-up",
            self.kpi_today_text,
            self.kpi_today_subtext,
            ft.Icons.NOTIFICATION_IMPORTANT_ROUNDED,
            "#7C3AED",
            "#F5F3FF",
            border_color="#DDD6FE",
            on_click_action=lambda _: self._toggle_today_filter(),
            tooltip="Click to toggle today's call queue",
            category_key="TODAY",
        )
        self.card_hot = _make_category_kpi_card(
            "Confirm Laga (Hot)",
            self.kpi_hot_text,
            ft.Text("Admission pakka", size=10, color="#DC2626", weight=ft.FontWeight.W_500),
            ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED,
            "#DC2626",
            "#FEF2F2",
            border_color="#FECACA",
            on_click_action=lambda _: self._set_category_filter("HOT"),
            category_key="HOT",
        )
        self.card_warm = _make_category_kpi_card(
            "Interested (Warm)",
            self.kpi_warm_text,
            ft.Text("Needs follow-up", size=10, color="#D97706", weight=ft.FontWeight.W_500),
            ft.Icons.THUMB_UP_ALT_ROUNDED,
            "#D97706",
            "#FFFBEB",
            border_color="#FDE68A",
            on_click_action=lambda _: self._set_category_filter("WARM"),
            category_key="WARM",
        )
        self.card_cold = _make_category_kpi_card(
            "Doubtful (Cold)",
            self.kpi_cold_text,
            ft.Text("Fee/timing doubt", size=10, color="#2563EB", weight=ft.FontWeight.W_500),
            ft.Icons.AC_UNIT_ROUNDED,
            "#2563EB",
            "#EFF6FF",
            border_color="#BFDBFE",
            on_click_action=lambda _: self._set_category_filter("COLD"),
            category_key="COLD",
        )
        self.card_converted = _make_category_kpi_card(
            "Admitted",
            self.kpi_converted_text,
            self.kpi_rate_text,
            ft.Icons.CHECK_CIRCLE_ROUNDED,
            "#059669",
            "#ECFDF5",
            border_color="#A7F3D0",
            on_click_action=lambda _: self._set_category_filter("CONVERTED"),
            category_key="CONVERTED",
        )
        self.card_total = _make_category_kpi_card(
            "Total Leads",
            self.kpi_total_text,
            ft.Text("Click to view all", size=10, color=AppTheme.TEXT_MUTED),
            ft.Icons.ALL_INBOX_ROUNDED,
            "#475569",
            "#F8FAFC",
            border_color="#E2E8F0",
            on_click_action=lambda _: self._set_category_filter("ALL"),
            category_key="ALL",
        )

        kpis_row = ft.ResponsiveRow(
            controls=[
                self.card_today,
                self.card_hot,
                self.card_warm,
                self.card_cold,
                self.card_converted,
                self.card_total,
            ],
            spacing=10,
            run_spacing=10,
        )

        # ── 3. Modern Filter & Universal Search Toolbar ──
        self.search_field = ft.TextField(
            hint_text="Search candidate name, mobile, village, course, or counselor...",
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            suffix=ft.IconButton(
                icon=ft.Icons.CLEAR_ROUNDED,
                icon_size=16,
                tooltip="Clear search",
                on_click=self.handle_clear_search,
            ),
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
            on_change=self.handle_search_change,
            width=320,
            content_padding=ft.Padding(12, 10, 12, 10),
        )

        self.category_filter = ft.Dropdown(
            label="Category",
            value="ALL",
            width=210,
            border_radius=AppTheme.RADIUS_MD,
            options=[
                ft.dropdown.Option("ALL", "All Categories"),
                ft.dropdown.Option("HOT", "🔥 Confirm Laga (Hot)"),
                ft.dropdown.Option("WARM", "👍 Interested (Warm)"),
                ft.dropdown.Option("COLD", "❄️ Doubtful (Cold)"),
                ft.dropdown.Option("LOST", "❌ Not Interested (Lost)"),
                ft.dropdown.Option("CONVERTED", "🎓 Converted (Admitted)"),
            ],
            on_select=self.handle_category_change,
        )

        self.follow_up_filter_dropdown = ft.Dropdown(
            label="Follow-up Date",
            value="ALL",
            width=190,
            border_radius=AppTheme.RADIUS_MD,
            options=[
                ft.dropdown.Option("ALL", "All Follow-up Dates"),
                ft.dropdown.Option("TODAY", "📅 Today's Calls"),
                ft.dropdown.Option("OVERDUE", "⚠️ Overdue Calls"),
                ft.dropdown.Option("UPCOMING", "🕒 Upcoming Calls"),
            ],
            on_select=self.handle_follow_up_filter_change,
        )

        self.status_filter = ft.Dropdown(
            label="Status",
            value="ALL",
            width=160,
            border_radius=AppTheme.RADIUS_MD,
            options=[
                ft.dropdown.Option("ALL", "All Statuses"),
                ft.dropdown.Option("NEW", "New Leads"),
                ft.dropdown.Option("CONTACTED", "Contacted"),
                ft.dropdown.Option("VISITED", "Visited Campus"),
                ft.dropdown.Option("CONVERTED", "Converted"),
                ft.dropdown.Option("CLOSED", "Closed"),
            ],
            on_select=self.handle_status_change,
        )

        self.clear_all_filters_btn = ft.IconButton(
            icon=ft.Icons.FILTER_ALT_OFF_ROUNDED,
            tooltip="Reset All Filters",
            icon_color=AppTheme.TEXT_MUTED,
            on_click=self.handle_clear_all_filters,
        )

        filter_row = ft.Row(
            controls=[
                self.search_field,
                self.category_filter,
                self.follow_up_filter_dropdown,
                self.status_filter,
                self.clear_all_filters_btn,
            ],
            spacing=AppTheme.PAD_SM,
            wrap=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # ── 4. Data Table — Frozen Stationary Header Architecture ──
        self.col_specs = [
            ("Date & Timing", 130),
            ("Candidate & Category", 190),
            ("Mobile & Contacts", 140),
            ("Interested Course", 150),
            ("Follow-up / Counselor", 170),
            ("Actions", 160),
        ]

        self.table_columns = [
            ft.DataColumn(
                label=ft.Container(
                    content=ft.Text(label, weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_PRIMARY),
                    width=w,
                )
            )
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
            data_row_min_height=56,
            border=ft.Border.all(1, AppTheme.BORDER),
            border_radius=ft.BorderRadius(0, 0, AppTheme.RADIUS_MD, AppTheme.RADIUS_MD),
            vertical_lines=ft.BorderSide(0.5, AppTheme.BORDER),
            horizontal_lines=ft.BorderSide(0.5, AppTheme.BORDER),
        )

        # Modern empty state illustration
        self.empty_state_text = ft.Text(
            "No enquiry records found for the selected criteria.",
            size=AppTheme.SIZE_BODY,
            weight=ft.FontWeight.W_500,
            color=AppTheme.TEXT_SECONDARY,
        )
        self.empty_state_cta = ft.ElevatedButton(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.FLASH_ON_ROUNDED, size=16),
                    ft.Text("Record Walk-in Now", weight=ft.FontWeight.BOLD),
                ],
                spacing=6,
                tight=True,
            ),
            style=ft.ButtonStyle(
                bgcolor=AppTheme.PRIMARY,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
            ),
            on_click=self.handle_new_enquiry,
        )

        self.empty_state = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Icon(ft.Icons.SUPPORT_AGENT_ROUNDED, size=52, color=AppTheme.PRIMARY),
                        padding=16,
                        bgcolor="#EFF6FF",
                        border_radius=AppTheme.RADIUS_PILL,
                    ),
                    self.empty_state_text,
                    ft.Text("Try clearing filters or enter a 15-second lead intake.", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED),
                    self.empty_state_cta,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
            padding=ft.Padding(0, 56, 0, 56),
            alignment=ft.Alignment(0, 0),
            visible=False,
            animate_opacity=ft.Animation(220, ft.AnimationCurve.EASE_IN_OUT),
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

        table_container = ft.Container(
            content=ft.Column(
                controls=[self.table_scroll_row, self.empty_state],
                expand=True,
            ),
            expand=True,
            animate_size=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
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

        # Main Layout Column
        self.content = ft.Column(
            controls=[
                header_row,
                ft.Divider(height=1, color=AppTheme.BORDER),
                self.controls_panel,
                table_container,
            ],
            spacing=AppTheme.PAD_MD,
            expand=True,
        )

    def _update_card_highlights(self) -> None:
        """Applies active selection ring and styling to KPI cards matching current filter."""
        cards = [self.card_hot, self.card_warm, self.card_cold, self.card_converted, self.card_total]
        for c in cards:
            cat_key = getattr(c, "_category_key", "")
            base_border = getattr(c, "_base_border_color", "#E2E8F0")
            if cat_key == self.selected_category:
                c.border = ft.Border.all(2, AppTheme.PRIMARY)
            else:
                c.border = ft.Border.all(1, base_border)

        # Today card border
        if self.selected_follow_up_filter == "TODAY":
            self.card_today.border = ft.Border.all(2, "#7C3AED")
        else:
            self.card_today.border = ft.Border.all(1, getattr(self.card_today, "_base_border_color", "#DDD6FE"))

    def _toggle_today_filter(self) -> None:
        if self.selected_follow_up_filter == "TODAY":
            self.selected_follow_up_filter = "ALL"
            self.follow_up_filter_dropdown.value = "ALL"
        else:
            self.selected_follow_up_filter = "TODAY"
            self.follow_up_filter_dropdown.value = "TODAY"
        self._update_card_highlights()
        self.load_data()

    def _set_category_filter(self, category: str) -> None:
        self.selected_category = category
        self.category_filter.value = category
        self._update_card_highlights()
        self.load_data()

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
        self._render_table_rows()
        self._safe_update()

    def _compute_column_spacing(self, num_columns: int = 6, base_content_width: int = 940) -> tuple[int, int]:
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
            spacing = max(18, min(140, int(extra_w / gaps)))
            return spacing, 18
        return 18, 14

    def load_data(self) -> None:
        try:
            # 1. Load Category Summary & Update KPI counters
            cat_summary: EnquiryCategorySummaryDTO = self.controller.get_category_summary()
            self.kpi_total_text.value = str(cat_summary.total)
            self.kpi_today_text.value = str(cat_summary.today_follow_ups)
            if cat_summary.overdue_follow_ups > 0:
                self.kpi_today_subtext.value = f"⚠️ {cat_summary.overdue_follow_ups} overdue calls"
                self.kpi_today_subtext.color = "#DC2626"
                self.kpi_today_subtext.weight = ft.FontWeight.BOLD
                self.card_today._base_border_color = "#FCA5A5"
                if self.selected_follow_up_filter != "TODAY":
                    self.card_today.border = ft.Border.all(1.5, "#EF4444")
            else:
                self.kpi_today_subtext.value = "All calls up to date"
                self.kpi_today_subtext.color = AppTheme.TEXT_SECONDARY
                self.kpi_today_subtext.weight = ft.FontWeight.NORMAL
                self.card_today._base_border_color = "#DDD6FE"
                if self.selected_follow_up_filter != "TODAY":
                    self.card_today.border = ft.Border.all(1, "#DDD6FE")

            self.kpi_hot_text.value = str(cat_summary.hot)
            self.kpi_warm_text.value = str(cat_summary.warm)
            self.kpi_cold_text.value = str(cat_summary.cold)
            self.kpi_converted_text.value = str(cat_summary.converted)
            self.kpi_rate_text.value = f"{cat_summary.conversion_rate:.1f}% conv. rate"

            # 2. Load Filtered Records
            results, total = self.controller.list_enquiries(
                query=self.search_query if self.search_query else None,
                status=self.selected_status if self.selected_status != "ALL" else None,
                category=self.selected_category if self.selected_category != "ALL" else None,
                follow_up_filter=self.selected_follow_up_filter if self.selected_follow_up_filter != "ALL" else None,
                limit=150,
            )
            self.enquiries = results
            self.total_count = total

            self._update_card_highlights()
            self._render_table_rows()
            self._safe_update()
        except Exception as exc:
            LogService.error(f"Failed to load enquiries: {exc}", context="EnquiryHome")

    def _render_table_rows(self) -> None:
        if not self.enquiries:
            self.data_table.rows = []
            self.header_table.visible = False
            self.table_scroll_row.visible = False
            self.empty_state.visible = True
            return

        self.empty_state.visible = False
        rows = []
        today_iso = date.today().isoformat()

        for enq in self.enquiries:
            # 1. Category styling & Candidate Avatar
            cat_key = getattr(enq, "category", "WARM") or "WARM"
            cat_cfg = CATEGORY_CONFIG.get(cat_key, CATEGORY_CONFIG["WARM"])

            initials = (enq.first_name[:1] if enq.first_name else (enq.student_name[:1] if enq.student_name else "E")).upper()
            avatar_circle = ft.CircleAvatar(
                content=ft.Text(initials, size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                bgcolor=cat_cfg.get("avatar_bg", AppTheme.PRIMARY),
                radius=14,
            )

            category_badge = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(cat_cfg["icon"], size=11, color=cat_cfg["color"]),
                        ft.Text(cat_cfg["badge_label"], size=10, weight=ft.FontWeight.BOLD, color=cat_cfg["color"]),
                    ],
                    spacing=3,
                    tight=True,
                ),
                bgcolor=cat_cfg["bgcolor"],
                border=ft.Border.all(1, cat_cfg["border"]),
                border_radius=ft.BorderRadius.all(6),
                padding=ft.Padding(5, 2, 6, 2),
            )

            # 2. Timing badge
            timing_code = getattr(enq, "preferred_timing", "ANY") or "ANY"
            timing_display = TIMING_LABELS.get(timing_code, "Flexible Timing")
            timing_badge = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.SCHEDULE_ROUNDED, size=10, color=AppTheme.TEXT_MUTED),
                        ft.Text(timing_display, size=10, color=AppTheme.TEXT_SECONDARY, overflow=ft.TextOverflow.ELLIPSIS),
                    ],
                    spacing=3,
                    tight=True,
                ),
            )

            date_str = str(enq.created_at)[:10] if enq.created_at else "—"

            # 3. Follow-up Date formatting & Overdue Alert
            follow_up_str = enq.follow_up_date or "—"
            counselor = enq.counselor_name or "Front Desk"
            follow_up_color = AppTheme.TEXT_SECONDARY
            follow_up_prefix = ""
            follow_up_badge_bg = "#F8FAFC"
            follow_up_badge_border = "#E2E8F0"

            if enq.follow_up_date and enq.status != "CONVERTED" and enq.category != "LOST":
                if enq.follow_up_date < today_iso:
                    follow_up_color = "#DC2626"
                    follow_up_prefix = "⚠️ OVERDUE: "
                    follow_up_badge_bg = "#FEF2F2"
                    follow_up_badge_border = "#FECACA"
                elif enq.follow_up_date == today_iso:
                    follow_up_color = "#7C3AED"
                    follow_up_prefix = "📅 TODAY: "
                    follow_up_badge_bg = "#F5F3FF"
                    follow_up_badge_border = "#DDD6FE"

            # 4. Action Buttons with Figma-grade hover containers
            follow_up_btn = ft.IconButton(
                icon=ft.Icons.PHONE_IN_TALK_ROUNDED,
                icon_color=AppTheme.PRIMARY,
                icon_size=18,
                tooltip="Log Call & View History Timeline",
                on_click=lambda _, item=enq: self.handle_follow_up(item),
            )
            whatsapp_btn = ft.IconButton(
                icon=ft.Icons.CHAT_ROUNDED,
                icon_color="#16A34A",
                icon_size=18,
                tooltip="Open WhatsApp Chat",
                on_click=lambda _, item=enq: self.handle_whatsapp(item),
            )
            convert_btn = ft.IconButton(
                icon=ft.Icons.HOW_TO_REG_ROUNDED,
                icon_color="#059669",
                icon_size=18,
                tooltip="Convert to Admission (Auto-fills Admission Form)",
                on_click=lambda _, e_id=enq.id: self.handle_convert_to_admission(e_id),
                visible=(enq.status != "CONVERTED"),
            )
            edit_btn = ft.IconButton(
                icon=ft.Icons.EDIT_OUTLINED,
                icon_color="#475569",
                icon_size=18,
                tooltip="Edit Lead Details",
                on_click=lambda _, item=enq: self.handle_edit_enquiry(item),
            )
            delete_btn = ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                icon_color="#DC2626",
                icon_size=18,
                tooltip="Delete Enquiry",
                on_click=lambda _, e_id=enq.id: self.handle_delete_enquiry(e_id),
            )

            action_row = ft.Row(
                controls=[follow_up_btn, whatsapp_btn, convert_btn, edit_btn, delete_btn],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

            # Secondary contact text if available
            alt_mob = getattr(enq, "alternate_mobile", None) or getattr(enq, "secondary_mobile", None)
            alt_control = ft.Text(f"Alt: {alt_mob}", size=10, color=AppTheme.TEXT_MUTED) if alt_mob else ft.Container()

            # Loss reason text if lost
            loss_res = getattr(enq, "loss_reason", None)
            loss_control = (
                ft.Container(
                    content=ft.Text(f"Reason: {loss_res}", size=10, color="#DC2626", italic=True),
                    padding=ft.Padding(4, 1, 4, 1),
                    bgcolor="#FEF2F2",
                    border_radius=4,
                )
                if (cat_key == "LOST" and loss_res)
                else ft.Container()
            )

            rows.append(
                ft.DataRow(
                    cells=[
                        # Column 1: Date & Timing (width: 130)
                        ft.DataCell(
                            ft.Container(
                                content=ft.Column(
                                    controls=[
                                        ft.Row(
                                            controls=[
                                                ft.Icon(ft.Icons.CALENDAR_TODAY_ROUNDED, size=11, color=AppTheme.TEXT_MUTED),
                                                ft.Text(date_str, size=12, weight=ft.FontWeight.W_600),
                                            ],
                                            spacing=4,
                                            tight=True,
                                        ),
                                        timing_badge,
                                    ],
                                    spacing=2,
                                    alignment=ft.MainAxisAlignment.CENTER,
                                ),
                                width=130,
                            )
                        ),
                        # Column 2: Candidate & Category (width: 190)
                        ft.DataCell(
                            ft.Container(
                                content=ft.Row(
                                    controls=[
                                        avatar_circle,
                                        ft.Column(
                                            controls=[
                                                ft.Row(
                                                    controls=[
                                                        ft.Text(enq.student_name, size=12, weight=ft.FontWeight.BOLD, overflow=ft.TextOverflow.ELLIPSIS),
                                                        category_badge,
                                                    ],
                                                    spacing=6,
                                                    tight=True,
                                                ),
                                                ft.Row(
                                                    controls=[
                                                        ft.Icon(ft.Icons.LOCATION_ON_OUTLINED, size=11, color=AppTheme.TEXT_MUTED),
                                                        ft.Text(enq.village or "Chandwad", size=10, color=AppTheme.TEXT_SECONDARY),
                                                    ],
                                                    spacing=2,
                                                    tight=True,
                                                ),
                                            ],
                                            spacing=2,
                                            alignment=ft.MainAxisAlignment.CENTER,
                                        ),
                                    ],
                                    spacing=8,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                width=190,
                            )
                        ),
                        # Column 3: Mobile & Contacts (width: 140)
                        ft.DataCell(
                            ft.Container(
                                content=ft.Column(
                                    controls=[
                                        ft.Row(
                                            controls=[
                                                ft.Icon(ft.Icons.PHONE_ROUNDED, size=12, color=AppTheme.PRIMARY),
                                                ft.Text(enq.mobile_number, size=12, weight=ft.FontWeight.W_600),
                                            ],
                                            spacing=4,
                                            tight=True,
                                        ),
                                        alt_control,
                                    ],
                                    spacing=2,
                                    alignment=ft.MainAxisAlignment.CENTER,
                                ),
                                width=140,
                            )
                        ),
                        # Column 4: Interested Course (width: 150)
                        ft.DataCell(
                            ft.Container(
                                content=ft.Column(
                                    controls=[
                                        ft.Row(
                                            controls=[
                                                ft.Icon(ft.Icons.SCHOOL_ROUNDED, size=12, color=AppTheme.PRIMARY),
                                                ft.Text(
                                                    enq.course_name or enq.interested_course or "Not Assigned",
                                                    size=12,
                                                    weight=ft.FontWeight.W_500,
                                                    overflow=ft.TextOverflow.ELLIPSIS,
                                                ),
                                            ],
                                            spacing=4,
                                            tight=True,
                                        ),
                                        loss_control,
                                    ],
                                    spacing=2,
                                    alignment=ft.MainAxisAlignment.CENTER,
                                ),
                                width=150,
                            )
                        ),
                        # Column 5: Follow-up / Counselor (width: 170)
                        ft.DataCell(
                            ft.Container(
                                content=ft.Column(
                                    controls=[
                                        ft.Container(
                                            content=ft.Text(
                                                f"{follow_up_prefix}{follow_up_str}",
                                                size=10,
                                                weight=ft.FontWeight.BOLD if follow_up_prefix else ft.FontWeight.NORMAL,
                                                color=follow_up_color,
                                            ),
                                            bgcolor=follow_up_badge_bg,
                                            border=ft.Border.all(1, follow_up_badge_border),
                                            border_radius=ft.BorderRadius.all(4),
                                            padding=ft.Padding(5, 1, 5, 1),
                                        ),
                                        ft.Row(
                                            controls=[
                                                ft.Icon(ft.Icons.PERSON_OUTLINE_ROUNDED, size=10, color=AppTheme.TEXT_MUTED),
                                                ft.Text(f"{counselor}", size=10, color=AppTheme.TEXT_SECONDARY),
                                            ],
                                            spacing=3,
                                            tight=True,
                                        ),
                                    ],
                                    spacing=2,
                                    alignment=ft.MainAxisAlignment.CENTER,
                                ),
                                width=170,
                            )
                        ),
                        # Column 6: Actions (width: 160)
                        ft.DataCell(
                            ft.Container(
                                content=action_row,
                                width=160,
                            )
                        ),
                    ]
                )
            )

        col_spacing, horiz_margin = self._compute_column_spacing(num_columns=6, base_content_width=940)
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
        self.empty_state.visible = (len(rows) == 0)
        self.data_table.visible = (len(rows) > 0)

    def handle_new_enquiry(self, e: ft.ControlEvent) -> None:
        """Opens the ultra-fast 15-second Quick Walk-in Modal."""
        modal = QuickEnquiryModal(on_saved=self.load_data)
        self._open_dialog(modal)

    def handle_detailed_enquiry(self, e: ft.ControlEvent) -> None:
        """Opens full detailed enquiry intake modal."""
        modal = EnquiryFormModal(on_saved=self.load_data)
        self._open_dialog(modal)

    def handle_follow_up(self, enquiry: EnquiryDTO) -> None:
        """Opens follow-up call log and conversation timeline dialog."""
        dlg = EnquiryFollowUpDialog(enquiry=enquiry, on_updated=self.load_data)
        self._open_dialog(dlg)

    def handle_whatsapp(self, enquiry: EnquiryDTO) -> None:
        """Launches external WhatsApp web/desktop chat with pre-filled message."""
        mob = (enquiry.mobile_number or "").strip()
        clean_mob = "".join(filter(str.isdigit, mob))
        if len(clean_mob) == 10:
            clean_mob = f"91{clean_mob}"
        elif len(clean_mob) == 12 and clean_mob.startswith("91"):
            pass
        else:
            self._show_toast(f"Invalid mobile number for WhatsApp: {mob}", is_error=True)
            return

        course_name = enquiry.course_name or enquiry.interested_course or "our training programs"
        msg = f"Hello {enquiry.first_name}, greetings from SIMS Institute! We are following up regarding your enquiry for {course_name}. When would be a convenient time for counseling?"
        url = f"https://wa.me/{clean_mob}?text={urllib.parse.quote(msg)}"
        try:
            open_path_externally(url)
            self._show_toast(f"Opened WhatsApp chat with {enquiry.student_name}", is_success=True)
        except Exception as exc:
            LogService.warning(f"Could not open WhatsApp URL: {exc}", context="EnquiryHome")

    def handle_edit_enquiry(self, enquiry: EnquiryDTO) -> None:
        modal = EnquiryFormModal(enquiry=enquiry, on_saved=self.load_data)
        self._open_dialog(modal)

    def handle_delete_enquiry(self, enquiry_id: int) -> None:
        p = self.safe_page
        if not p:
            return

        def confirm_delete(_):
            try:
                self.controller.delete_enquiry(enquiry_id)
                try:
                    p.pop_dialog()
                except Exception:
                    confirm_dlg.open = False
                self.load_data()
                self._show_toast("Enquiry deleted successfully.", is_success=True)
            except Exception as exc:
                LogService.error(f"Failed to delete enquiry: {exc}", context="EnquiryHome")
                self._show_toast("Failed to delete enquiry.", is_error=True)

        confirm_dlg = ft.AlertDialog(
            title=ft.SelectionArea(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.DELETE_FOREVER, color=AppTheme.DANGER),
                        ft.Text("Confirm Deletion", weight=ft.FontWeight.BOLD),
                    ],
                    spacing=AppTheme.PAD_SM,
                )
            ),
            content=ft.SelectionArea(
                content=ft.Text("Are you sure you want to delete this enquiry record? This cannot be undone.")
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: p.pop_dialog() if hasattr(p, "pop_dialog") else setattr(confirm_dlg, "open", False) or p.update()),
                ft.ElevatedButton("Delete", bgcolor="#DC2626", color=ft.Colors.WHITE, on_click=confirm_delete),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._open_dialog(confirm_dlg)

    def handle_convert_to_admission(self, enquiry_id: int) -> None:
        """Launches AdmissionFormModal pre-populated with enquiry data."""
        try:
            draft = self.controller.convert_to_admission_draft(enquiry_id)
            admission_modal = AdmissionFormModal(
                on_saved=self.load_data,
                initial_enquiry_data=draft,
                initial_enquiry_id=enquiry_id,
            )
            self._open_dialog(admission_modal)
        except Exception as exc:
            LogService.error(f"Conversion draft error: {exc}", context="EnquiryHome")
            self._show_toast("Could not prepare admission draft from enquiry.", is_error=True)

    def handle_search_change(self, e: ft.ControlEvent) -> None:
        self.search_query = (self.search_field.value or "").strip()
        self.load_data()

    def handle_clear_search(self, e: ft.ControlEvent) -> None:
        self.search_field.value = ""
        self.search_query = ""
        self.load_data()

    def handle_category_change(self, e: ft.ControlEvent) -> None:
        self.selected_category = self.category_filter.value or "ALL"
        self._update_card_highlights()
        self.load_data()

    def handle_follow_up_filter_change(self, e: ft.ControlEvent) -> None:
        self.selected_follow_up_filter = self.follow_up_filter_dropdown.value or "ALL"
        self._update_card_highlights()
        self.load_data()

    def handle_status_change(self, e: ft.ControlEvent) -> None:
        self.selected_status = self.status_filter.value or "ALL"
        self.load_data()

    def handle_clear_all_filters(self, e: ft.ControlEvent) -> None:
        self.search_field.value = ""
        self.search_query = ""
        self.category_filter.value = "ALL"
        self.selected_category = "ALL"
        self.follow_up_filter_dropdown.value = "ALL"
        self.selected_follow_up_filter = "ALL"
        self.status_filter.value = "ALL"
        self.selected_status = "ALL"
        self._update_card_highlights()
        self.load_data()
        self._show_toast("All enquiry filters reset.", is_success=True)

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

    def handle_export_excel(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Exports currently filtered enquiry dataset to styled Microsoft Excel (.xlsx) format with custom save prompt."""
        try:
            path = self.controller.export_enquiries_excel(
                query=self.search_query or None,
                status=self.selected_status,
                category=self.selected_category,
                follow_up_filter=self.selected_follow_up_filter,
            )
            export_and_prompt_save(
                source_file_path=path,
                dialog_title="Save Enquiries Export As",
                allowed_extensions=[".xlsx"],
                show_toast=self._show_toast,
            )
        except Exception as ex:
            LogService.error(f"Error exporting enquiries to Excel: {ex}", context=self.__class__.__name__)
            self._show_toast("Failed to export enquiries Excel data.", is_error=True)

    def handle_export_csv(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Exports currently filtered enquiry dataset to CSV format with custom save prompt."""
        try:
            path = self.controller.export_enquiries_csv(
                query=self.search_query or None,
                status=self.selected_status,
                category=self.selected_category,
                follow_up_filter=self.selected_follow_up_filter,
            )
            export_and_prompt_save(
                source_file_path=path,
                dialog_title="Save Enquiries CSV As",
                allowed_extensions=[".csv"],
                show_toast=self._show_toast,
            )
        except Exception as ex:
            LogService.error(f"Error exporting enquiries to CSV: {ex}", context=self.__class__.__name__)
            self._show_toast("Failed to export enquiries CSV data.", is_error=True)
