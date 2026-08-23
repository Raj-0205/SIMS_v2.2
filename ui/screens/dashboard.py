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
from modules.reports.views.reports_home import ReportsHome
from modules.settings.views.settings_home import SettingsHome
from modules.admission.controller import AdmissionController
from modules.admission.dto import AdmissionSummaryDTO

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
        self.registered_adm_text = ft.Text("— Registered", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY)

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
            content=self.recent_table,
            bgcolor=AppTheme.SURFACE,
            border_radius=AppTheme.RADIUS_MD,
            padding=AppTheme.PAD_SM,
        )

        self._build_ui()

    def _make_kpi_card(
        self,
        title: str,
        icon: str,
        icon_color: str,
        main_text: ft.Text,
        sub_text: ft.Text,
        bg_color: str = AppTheme.SURFACE,
    ) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text(title, size=AppTheme.SIZE_BODY, weight=ft.FontWeight.W_600, color=AppTheme.TEXT_SECONDARY),
                            ft.Icon(icon, color=icon_color, size=22),
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
            padding=ft.Padding(16, 14, 16, 14),
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
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

        # Quick Actions Card
        actions_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Quick Workflows", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                    ft.Divider(height=12),
                    ft.Row(
                        controls=[
                            ft.OutlinedButton("Students Directory", icon=ft.Icons.PEOPLE, on_click=lambda _: self.on_navigate("/students")),
                            ft.OutlinedButton("Admissions Form", icon=ft.Icons.APP_REGISTRATION, on_click=lambda _: self.on_navigate("/admissions")),
                            ft.OutlinedButton("Course Catalog", icon=ft.Icons.MENU_BOOK, on_click=lambda _: self.on_navigate("/courses")),
                            ft.OutlinedButton("Fee Installments", icon=ft.Icons.PAYMENTS, on_click=lambda _: self.on_navigate("/fees")),
                            ft.OutlinedButton("System Settings", icon=ft.Icons.SETTINGS, on_click=lambda _: self.on_navigate("/settings")),
                        ],
                        spacing=AppTheme.PAD_SM,
                        wrap=True,
                    ),
                ],
                spacing=AppTheme.PAD_SM,
                tight=True,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=ft.Padding(16, 14, 16, 14),
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
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
                status_color = AppTheme.SUCCESS if a.status == "CONFIRMED" else (AppTheme.PRIMARY if a.status == "REGISTERED" else AppTheme.TEXT_SECONDARY)
                cand_num = f"{a.candidate_year or 2026}-{a.candidate_sequence:03d}" if a.candidate_sequence else f"#{a.id}"
                rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(cand_num, weight=ft.FontWeight.W_600)),
                            ft.DataCell(ft.Text(f"{a.first_name} {a.last_name}")),
                            ft.DataCell(ft.Text(a.course_name or "—")),
                            ft.DataCell(
                                ft.Container(
                                    content=ft.Text(a.status, size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD, color=status_color),
                                    padding=ft.Padding(6, 2, 6, 2),
                                    border_radius=AppTheme.RADIUS_SM,
                                    bgcolor=AppTheme.SURFACE_VARIANT,
                                )
                            ),
                            ft.DataCell(ft.Text(f"₹{a.agreed_fee:,.2f}")),
                            ft.DataCell(ft.Text(f"₹{a.total_paid:,.2f}", weight=ft.FontWeight.W_600, color=AppTheme.SUCCESS)),
                        ]
                    )
                )
            self.recent_table.rows = rows

            if self.page:
                self.update()
        except Exception:
            pass


class DashboardScreen(ft.Row):
    """Main ERP Dashboard Layout."""

    def __init__(self, page: ft.Page, on_route_request: Callable[[str], None]):
        super().__init__(
            expand=True,
            spacing=0,
        )

        self._page = page
        self.on_route_request = on_route_request

        self.content_host = ContentHost()

        self.nav_menu = NavigationMenu(
            on_nav_change=self.on_route_request
        )

        self.placeholder_view = ft.Text(
            "Module Under Construction",
            size=24,
            color=AppTheme.TEXT_MUTED,
        )

        self.controls = [
            self.nav_menu,
            ft.VerticalDivider(
                width=1,
                color=AppTheme.BORDER,
            ),
            self.content_host,
        ]

    def mount_view(self, route: str):
        self.nav_menu.set_route(route)
        if route == "/dashboard":
            view = DashboardHome(on_navigate=self.on_route_request)
        elif route == "/students":
            view = StudentHome()
        elif route == "/admissions":
            view = AdmissionHome()
        elif route == "/courses":
            view = CourseHome()
        elif route == "/fees":
            view = ReportsHome()
        elif route == "/settings":
            view = SettingsHome()
        elif route == "/batch":
            view = CourseHome()
        else:
            view = DashboardHome(on_navigate=self.on_route_request)

        self.content_host.mount(view)
        if hasattr(view, "load_data"):
            view.load_data()

