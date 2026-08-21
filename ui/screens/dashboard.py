# ui/screens/dashboard.py

import flet as ft
from typing import Callable

from ui.layout.navigation import NavigationMenu
from ui.layout.content_host import ContentHost
from modules.student.views.student_home import StudentHome
from modules.admission.views.admission_home import AdmissionHome
from modules.reports.views.reports_home import ReportsHome
from modules.settings.views.settings_home import SettingsHome

__all__ = ["DashboardScreen"]


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
            color=ft.Colors.GREY_400,
        )

        self.controls = [
            self.nav_menu,
            ft.VerticalDivider(
                width=1,
                color=ft.Colors.GREY_300,
            ),
            self.content_host,
        ]

    def mount_view(self, route: str):
        self.nav_menu.set_route(route)
        if route == "/students":
            view = StudentHome()
        elif route == "/admissions":
            view = AdmissionHome()
        elif route == "/fees":
            view = ReportsHome()
        elif route == "/settings":
            view = SettingsHome()
        elif route == "/dashboard":
            view = ReportsHome()
        else:
            view = self.placeholder_view

        self.content_host.mount(view)
        if hasattr(view, "load_data"):
            view.load_data()
