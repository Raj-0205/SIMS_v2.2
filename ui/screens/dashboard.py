# ui/screens/dashboard.py

from __future__ import annotations
from datetime import datetime
from typing import Callable, Optional
import flet as ft

from ui.themes.theme import AppTheme
from ui.layout.navigation import NavigationMenu
from ui.layout.content_host import ContentHost
from modules.student.views.student_home import StudentHome
from modules.admission.views.admission_home import AdmissionHome
from modules.course.views.course_home import CourseHome
from modules.batch.views.batch_home import BatchHome
from modules.attendance.views.attendance_home import AttendanceHome
from modules.reports.views.reports_home import ReportsHome
from modules.settings.views.settings_home import SettingsHome
from modules.enquiry.views.enquiry_home import EnquiryHome
from modules.admission.controller import AdmissionController
from modules.admission.dto import AdmissionSummaryDTO
from ui.screens.control_center import ControlCenterScreen
from ui.widgets import HoverCard, StatusBadge

__all__ = ["DashboardScreen", "DashboardHome"]


class DashboardHome(ft.Container):
    """
    Live Enterprise Dashboard View for SIMS v2.2.
    Displays dynamic KPI metric cards, quick action dispatchers,
    recent admission activity stream, and live financial summary.
    """

    def __init__(self, on_navigate: Optional[Callable[[str], None]] = None):
        super().__init__(
            expand=True,
            padding=ft.Padding(AppTheme.PAD_LG, AppTheme.PAD_MD, AppTheme.PAD_LG, AppTheme.PAD_MD),
            bgcolor=AppTheme.BACKGROUND,
        )
        self.on_navigate = on_navigate or (lambda route: None)
        self.adm_controller = AdmissionController()

        # Dynamic KPI Card Controls
        self.total_adm_text = ft.Text("—", size=26, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY)
        self.today_adm_text = ft.Text("0 Today", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY)

        self.confirmed_adm_text = ft.Text("—", size=26, weight=ft.FontWeight.BOLD, color=AppTheme.SUCCESS)
        self.registered_adm_text = ft.Text("— Admitted", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY)

        self.total_revenue_text = ft.Text("₹0.00", size=26, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY_HOVER)
        self.today_revenue_text = ft.Text("Today: ₹0.00", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY)

        self.pending_fee_text = ft.Text("₹0.00", size=26, weight=ft.FontWeight.BOLD, color=AppTheme.DANGER)
        self.pending_sub_text = ft.Text("Total Outstanding", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY)

        # Recent Admissions List
        self.recent_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Candidate #", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Student Name", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Course", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Status", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Fee Agreed", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Paid", weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
            heading_row_color=AppTheme.SURFACE_VARIANT,
            border=ft.Border.all(1, AppTheme.BORDER),
            border_radius=AppTheme.RADIUS_MD,
        )

        self.recent_container = ft.Container(
            content=ft.Row(
                controls=[self.recent_table],
                scroll=ft.ScrollMode.AUTO,
            ),
            bgcolor=AppTheme.SURFACE,
            border_radius=AppTheme.RADIUS_MD,
            padding=AppTheme.PAD_SM,
            animate_size=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
        )

        self._build_ui()

    def _make_kpi_card(
        self,
        title: str,
        icon: str,
        icon_color: str,
        main_text: ft.Text,
        sub_text: ft.Text,
        bg_color: Optional[str] = None,
    ) -> HoverCard:
        icon_bubble = ft.Container(
            content=ft.Icon(icon, color=icon_color, size=20),
            bgcolor=icon_color + "1A" if len(icon_color) == 7 else icon_color,
            padding=ft.Padding(7, 7, 7, 7),
            border_radius=AppTheme.RADIUS_SM,
        )
        return HoverCard(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text(title, size=13, weight=ft.FontWeight.W_600, color=AppTheme.TEXT_SECONDARY),
                            icon_bubble,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Container(height=AppTheme.PAD_XS),
                    main_text,
                    sub_text,
                ],
                spacing=2,
                tight=True,
            ),
            bgcolor=bg_color,
            padding=ft.Padding(18, 14, 18, 14),
            expand=True,
        )

    def _build_ui(self) -> None:
        # Header
        today_str = datetime.now().strftime("%A, %d %B %Y")
        header = ft.Row(
            controls=[
                ft.Column(
                    controls=[
                        ft.Text("Enterprise Dashboard", size=AppTheme.SIZE_H1, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                        ft.Text(f"Sudharm Infotech Management System (SIMS)  •  {today_str}", size=AppTheme.SIZE_BODY, color=AppTheme.TEXT_SECONDARY),
                    ],
                    spacing=2,
                ),
                ft.Row(
                    controls=[
                        ft.IconButton(
                            icon=ft.Icons.PALETTE_OUTLINED,
                            icon_color=AppTheme.PRIMARY,
                            tooltip="Theme & Appearance",
                            on_click=lambda _: self.on_navigate("/settings"),
                        ),
                        ft.OutlinedButton(
                            "Fee Reports",
                            icon=ft.Icons.ASSESSMENT,
                            on_click=lambda _: self.on_navigate("/fees"),
                        ),
                        ft.FilledButton(
                            "New Admission",
                            icon=ft.Icons.PERSON_ADD_ALT_1,
                            on_click=lambda _: self.on_navigate("/admissions"),
                        ),
                    ],
                    spacing=AppTheme.PAD_SM,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        # KPI Row
        kpi_row = ft.Row(
            controls=[
                self._make_kpi_card("Total Admissions", ft.Icons.HOW_TO_REG, AppTheme.PRIMARY, self.total_adm_text, self.today_adm_text),
                self._make_kpi_card("Confirmed Students", ft.Icons.VERIFIED, AppTheme.SUCCESS, self.confirmed_adm_text, self.registered_adm_text),
                self._make_kpi_card("Fee Collections", ft.Icons.MONETIZATION_ON, AppTheme.PRIMARY_HOVER, self.total_revenue_text, self.today_revenue_text),
                self._make_kpi_card("Outstanding Dues", ft.Icons.PENDING_ACTIONS, AppTheme.DANGER, self.pending_fee_text, self.pending_sub_text),
            ],
            spacing=AppTheme.PAD_MD,
        )

        # Quick Actions with Interactive Micro-Animations
        def _make_workflow_chip(label: str, icon: str, route: str):
            tile = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Icon(icon, size=17, color=AppTheme.PRIMARY),
                            bgcolor=AppTheme.PRIMARY_LIGHT,
                            padding=ft.Padding(6, 6, 6, 6),
                            border_radius=AppTheme.RADIUS_SM,
                        ),
                        ft.Text(label, size=AppTheme.SIZE_BODY, weight=ft.FontWeight.W_600, color=AppTheme.TEXT_PRIMARY),
                    ],
                    spacing=8,
                    tight=True,
                ),
                padding=ft.Padding(12, 8, 14, 8),
                border_radius=AppTheme.RADIUS_MD,
                border=ft.Border.all(1, AppTheme.BORDER),
                bgcolor=AppTheme.SURFACE,
                ink=True,
                tooltip=f"Launch {label}",
                on_click=lambda _: self.on_navigate(route),
                animate=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
                animate_scale=ft.Animation(140, ft.AnimationCurve.EASE_OUT),
            )
            def on_chip_hover(e):
                is_h = (e.data == "true")
                tile.border = ft.Border.all(1, AppTheme.PRIMARY if is_h else AppTheme.BORDER)
                tile.scale = 1.03 if is_h else 1.0
                tile.shadow = [ft.BoxShadow(spread_radius=0, blur_radius=8, color="#00000014", offset=ft.Offset(0, 3))] if is_h else None
                try:
                    tile.update()
                except Exception:
                    pass
            tile.on_hover = on_chip_hover
            return tile

        actions_card = HoverCard(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.FLASH_ON, color=AppTheme.PRIMARY, size=20),
                            ft.Text("Quick Workflows", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                        ],
                        spacing=6,
                    ),
                    ft.Divider(height=10, color=AppTheme.BORDER),
                    ft.Row(
                        controls=[
                            _make_workflow_chip("Walk-ins & Enquiries", ft.Icons.SUPPORT_AGENT, "/enquiries"),
                            _make_workflow_chip("Students Directory", ft.Icons.PEOPLE, "/students"),
                            _make_workflow_chip("Admissions Form", ft.Icons.APP_REGISTRATION, "/admissions"),
                            _make_workflow_chip("Course Catalog", ft.Icons.MENU_BOOK, "/courses"),
                            _make_workflow_chip("Fee Installments", ft.Icons.PAYMENTS, "/fees"),
                            _make_workflow_chip("System Settings", ft.Icons.SETTINGS, "/settings"),
                        ],
                        spacing=AppTheme.PAD_SM,
                        wrap=True,
                    ),
                ],
                spacing=AppTheme.PAD_SM,
                tight=True,
            ),
            padding=ft.Padding(18, 16, 18, 16),
        )

        # Recent Admissions Stream Header
        recent_section = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("Recent Admissions & Registrations", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                        ft.TextButton("View All", icon=ft.Icons.ARROW_FORWARD, on_click=lambda _: self.on_navigate("/admissions")),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                self.recent_container,
            ],
            spacing=AppTheme.PAD_SM,
        )

        self.content = ft.ListView(
            controls=[
                header,
                ft.Container(height=AppTheme.PAD_SM),
                kpi_row,
                ft.Container(height=AppTheme.PAD_SM),
                actions_card,
                ft.Container(height=AppTheme.PAD_SM),
                recent_section,
            ],
            spacing=AppTheme.PAD_MD,
            expand=True,
        )

    def load_data(self) -> None:
        """Asynchronously loads live KPI metrics and recent admissions."""
        try:
            stats: AdmissionSummaryDTO = self.adm_controller.get_summary_stats()
            self.total_adm_text.value = f"{stats.total_admissions:,}"
            self.today_adm_text.value = f"+{stats.today_admissions} Registered Today"

            self.confirmed_adm_text.value = f"{stats.confirmed_count:,}"
            self.registered_adm_text.value = f"{stats.registered_count} Pending Confirmation"

            self.total_revenue_text.value = f"₹{stats.total_revenue:,.2f}"
            self.today_revenue_text.value = f"Today: ₹{stats.today_collection:,.2f}"

            self.pending_fee_text.value = f"₹{stats.total_pending:,.2f}"
            self.pending_sub_text.value = f"Drafts: {stats.draft_count} in pipeline"

            # Load latest 5 admissions
            adms, _ = self.adm_controller.filter_admissions({"limit": 5, "sort_keys": [("id", "desc")]})
            rows = []
            for a in adms:
                cand_num = f"{a.candidate_year or 2026}-{a.candidate_sequence:03d}" if a.candidate_sequence else f"#{a.id}"
                rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(cand_num, weight=ft.FontWeight.W_600)),
                            ft.DataCell(ft.Text(f"{a.first_name} {a.last_name}", weight=ft.FontWeight.W_500)),
                            ft.DataCell(ft.Text(a.course_name or "—")),
                            ft.DataCell(StatusBadge(label=a.status, variant=a.status)),
                            ft.DataCell(ft.Text(f"₹{a.agreed_fee:,.2f}")),
                            ft.DataCell(ft.Text(f"₹{a.total_paid:,.2f}", weight=ft.FontWeight.W_600, color=AppTheme.SUCCESS)),
                        ]
                    )
                )
            self.recent_table.rows = rows

            try:
                self.update()
            except Exception:
                pass

            # Pre-warm Fees Report cache in background thread
            def _prewarm_fees_cache():
                try:
                    from modules.reports.service import ReportsService
                    ReportsService().get_admission_fees_report_paginated(page=1, page_size=30)
                except Exception:
                    pass

            import threading
            threading.Thread(target=_prewarm_fees_cache, daemon=True).start()
        except Exception:
            pass


class ErrorRecoveryView(ft.Container):
    """
    Actionable Error Recovery View for SIMS v2.2.
    Renders when a route or screen fails to mount/load data,
    providing error diagnostics, a 'Go Back' action, a 'Retry' action,
    and a 'Return to Dashboard' button.
    """

    def __init__(
        self,
        route: str,
        error_message: str,
        on_retry: Optional[Callable[[], None]] = None,
        on_back: Optional[Callable[[], None]] = None,
        on_dashboard: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(
            expand=True,
            padding=ft.Padding(AppTheme.PAD_LG, AppTheme.PAD_LG, AppTheme.PAD_LG, AppTheme.PAD_LG),
            bgcolor=AppTheme.BACKGROUND,
            alignment=ft.Alignment(0, 0),
        )

        card = ft.Container(
            width=640,
            padding=AppTheme.PAD_LG,
            bgcolor=AppTheme.SURFACE,
            border_radius=AppTheme.RADIUS_LG,
            border=ft.Border.all(1, AppTheme.DANGER_LIGHT),
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.ERROR_OUTLINE, color=AppTheme.DANGER, size=32),
                            ft.Column(
                                controls=[
                                    ft.Text("Screen Load Failure", size=AppTheme.SIZE_H2, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                                    ft.Text(f"Failed to initialize view for: {route}", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                                ],
                                spacing=2,
                            ),
                        ],
                        spacing=AppTheme.PAD_MD,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    ft.Text(
                        "An unexpected error occurred while loading this module. Full forensics have been recorded in the application log.",
                        size=AppTheme.SIZE_BODY,
                        color=AppTheme.TEXT_SECONDARY,
                    ),
                    ft.Container(
                        content=ft.Text(
                            error_message or "Unknown exception",
                            size=AppTheme.SIZE_CAPTION,
                            font_family="monospace",
                            color=AppTheme.DANGER,
                            selectable=True,
                        ),
                        bgcolor=AppTheme.DANGER_LIGHT,
                        border_radius=AppTheme.RADIUS_MD,
                        padding=AppTheme.PAD_MD,
                        width=600,
                    ),
                    ft.Row(
                        controls=[
                            ft.FilledButton(
                                "Go Back",
                                icon=ft.Icons.ARROW_BACK,
                                style=ft.ButtonStyle(bgcolor=AppTheme.PRIMARY, color=AppTheme.SURFACE),
                                on_click=lambda _: on_back() if on_back else None,
                            ),
                            ft.OutlinedButton(
                                "Retry",
                                icon=ft.Icons.REFRESH,
                                on_click=lambda _: on_retry() if on_retry else None,
                            ),
                            ft.TextButton(
                                "Return to Dashboard",
                                on_click=lambda _: on_dashboard() if on_dashboard else None,
                            ),
                        ],
                        spacing=AppTheme.PAD_SM,
                        alignment=ft.MainAxisAlignment.END,
                    ),
                ],
                spacing=AppTheme.PAD_MD,
                tight=True,
            ),
        )

        self.content = ft.SelectionArea(content=card)


class DashboardScreen(ft.Row):
    """Main ERP Dashboard Layout."""

    def __init__(
        self,
        page: ft.Page,
        on_route_request: Callable[[str], None],
        on_back_request: Optional[Callable[[], None]] = None,
    ):
        super().__init__(
            expand=True,
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )

        self._page = page
        self.on_route_request = on_route_request
        self.on_back_request = on_back_request
        self._nav_sequence: int = 0

        self.content_host = ContentHost()

        self.is_sidebar_visible = True

        self.nav_menu = NavigationMenu(
            on_nav_change=self.on_route_request,
            on_toggle_visibility=self.toggle_sidebar,
            on_logout_request=self.prompt_logout_confirmation,
        )
        self.nav_menu._page = page
        self.nav_menu._root_page = page

        self.sidebar_container = ft.Container(
            content=ft.SelectionArea(content=self.nav_menu),
            visible=True,
            animate_size=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
        )

        self.sidebar_divider = ft.VerticalDivider(
            width=1,
            color=AppTheme.BORDER,
            visible=True,
        )

        self.open_sidebar_btn = ft.Container(
            content=ft.SelectionArea(
                content=ft.Row(
                    controls=[
                        ft.IconButton(
                            icon=ft.Icons.MENU,
                            icon_size=20,
                            icon_color=AppTheme.PRIMARY,
                            tooltip="Open Modules Sidebar",
                            on_click=lambda _: self.toggle_sidebar(),
                        ),
                        ft.Text(
                            "Modules Menu",
                            size=AppTheme.SIZE_BODY,
                            weight=ft.FontWeight.W_600,
                            color=AppTheme.TEXT_SECONDARY,
                        ),
                    ],
                    spacing=4,
                ),
            ),
            padding=ft.Padding(12, 6, 12, 0),
            visible=False,
            animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT),
        )

        self.main_content_area = ft.Column(
            controls=[
                self.open_sidebar_btn,
                self.content_host,
            ],
            expand=True,
            spacing=0,
        )

        self.placeholder_view = ft.Text(
            "Module Under Construction",
            size=24,
            color=AppTheme.TEXT_MUTED,
            selectable=True,
        )

        self.controls = [
            self.sidebar_container,
            self.sidebar_divider,
            self.main_content_area,
        ]

    def prompt_logout_confirmation(self) -> None:
        """Displays a confirmation modal before logging out to safeguard active drafts."""
        def handle_cancel(e=None):
            confirm_dlg.open = False
            try:
                if hasattr(self._page, "pop_dialog"):
                    self._page.pop_dialog()
                else:
                    self._page.update()
            except Exception:
                pass
            if hasattr(self._page, "dialog") and self._page.dialog is confirm_dlg:
                self._page.dialog = None

        def handle_confirm(e=None):
            confirm_dlg.open = False
            try:
                if hasattr(self._page, "pop_dialog"):
                    self._page.pop_dialog()
                else:
                    self._page.update()
            except Exception:
                pass
            if hasattr(self._page, "dialog") and self._page.dialog is confirm_dlg:
                self._page.dialog = None
            self.on_route_request("/logout")

        confirm_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=AppTheme.DANGER, size=28),
                    ft.Text("Confirm Logout", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, selectable=True),
                ],
                spacing=AppTheme.PAD_SM,
            ),
            content=ft.Container(
                content=ft.SelectionArea(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                "Are you sure you want to log out of SIMS?",
                                size=AppTheme.SIZE_BODY,
                                weight=ft.FontWeight.W_500,
                            ),
                            ft.Text(
                                "If you have unsaved form drafts or active work, you can click Cancel to keep working safely.",
                                size=AppTheme.SIZE_CAPTION,
                                color=AppTheme.TEXT_SECONDARY,
                            ),
                        ],
                        spacing=AppTheme.PAD_XS,
                        tight=True,
                    ),
                ),
                width=420,
                padding=AppTheme.PAD_SM,
            ),
            actions=[
                ft.OutlinedButton(
                    content=ft.Text("Cancel / Keep Working"),
                    on_click=handle_cancel,
                ),
                ft.ElevatedButton(
                    content=ft.Text("Yes, Log Out"),
                    icon=ft.Icons.LOGOUT,
                    style=ft.ButtonStyle(bgcolor=AppTheme.DANGER, color=ft.Colors.WHITE),
                    on_click=handle_confirm,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        confirm_dlg.handle_cancel = handle_cancel
        confirm_dlg.handle_submit = handle_confirm
        confirm_dlg.submit_btn = confirm_dlg.actions[1]

        self._page.dialog = confirm_dlg
        if hasattr(self._page, "show_dialog"):
            try:
                self._page.show_dialog(confirm_dlg)
            except Exception:
                confirm_dlg.open = True
                try:
                    self._page.update()
                except Exception:
                    pass
        else:
            confirm_dlg.open = True
            try:
                self._page.update()
            except Exception:
                pass

    def toggle_sidebar(self, visible: Optional[bool] = None) -> None:
        """Toggles or sets the visibility of the left sidebar."""
        if visible is None:
            self.is_sidebar_visible = not self.is_sidebar_visible
        else:
            self.is_sidebar_visible = visible

        self.sidebar_container.visible = self.is_sidebar_visible
        self.sidebar_divider.visible = self.is_sidebar_visible
        self.open_sidebar_btn.visible = not self.is_sidebar_visible

        try:
            if self._page:
                self._page.update()
            else:
                self.update()
        except Exception:
            pass

    def _safe_page_update(self) -> None:
        try:
            if self._page:
                self._page.update()
            else:
                self.update()
        except Exception:
            pass

    def _create_view_instance(self, route: str) -> ft.Control:
        if route == "/dashboard":
            return DashboardHome(on_navigate=self.on_route_request)
        elif route == "/enquiries":
            return EnquiryHome()
        elif route == "/students":
            return StudentHome()
        elif route == "/attendance":
            return AttendanceHome()
        elif route == "/admissions":
            return AdmissionHome()
        elif route == "/courses":
            return CourseHome()
        elif route == "/fees":
            return ReportsHome(self._page)
        elif route == "/settings":
            return SettingsHome()
        elif route == "/batch":
            return BatchHome()
        elif route == "/control-center":
            return ControlCenterScreen(self._page, on_navigate=self.on_route_request)
        elif route == "/about":
            from ui.widgets.about_dialog import AboutScreenView
            return AboutScreenView()
        elif route == "/notifications":
            from ui.widgets.notifications_dialog import NotificationsScreenView
            return NotificationsScreenView()
        else:
            return DashboardHome(on_navigate=self.on_route_request)

    def _handle_mount_error(self, route: str, ex: Exception) -> None:
        import logging, traceback
        from datetime import datetime
        from core.security.context import SecurityContext
        current_user = SecurityContext.get_current_user_id() or "anonymous"
        logging.getLogger("sims.ui").error(
            f"[UI Forensic Error] User: {current_user} | Route: {route} | Time: {datetime.now().isoformat()} | Error: {str(ex)}\n{traceback.format_exc()}"
        )
        recovery_view = ErrorRecoveryView(
            route=route,
            error_message=str(ex),
            on_retry=lambda: self.mount_view(route),
            on_back=self.on_back_request or (lambda: self.on_route_request("/dashboard")),
            on_dashboard=lambda: self.on_route_request("/dashboard"),
        )
        self.content_host.mount(recovery_view)
        self._safe_page_update()

    def mount_view(self, route: str) -> None:
        self.nav_menu.set_route(route)
        self._nav_sequence += 1
        current_seq = self._nav_sequence

        is_live = bool(getattr(self._page, "session_id", None))

        if not is_live:
            # Synchronous mount for headless test runner environments
            try:
                view = self._create_view_instance(route)
                self.content_host.mount(view)
                if hasattr(view, "load_data"):
                    view.load_data()
                setattr(view, "_data_loaded", True)
                self._safe_page_update()
            except Exception as ex:
                self._handle_mount_error(route, ex)
            return

        # Live runtime mode: Adaptive loading screen displays while database loads
        self.content_host.show_loader(route)
        self._safe_page_update()

        import threading

        def _adaptive_load_worker(seq: int):
            try:
                view = self._create_view_instance(route)
                if hasattr(view, "load_data"):
                    view.load_data()
                setattr(view, "_data_loaded", True)

                # Guard against race conditions from rapid navigation clicks
                if self._nav_sequence == seq:
                    self.content_host.mount(view)
                    self._safe_page_update()
            except Exception as ex:
                if self._nav_sequence == seq:
                    self._handle_mount_error(route, ex)

        threading.Thread(target=_adaptive_load_worker, args=(current_seq,), daemon=True).start()


