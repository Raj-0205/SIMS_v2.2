# ui/layout/navigation.py

import flet as ft
from typing import Callable

__all__ = ["NavigationMenu"]


class NavigationMenu(ft.NavigationRail):
    """Emits navigation intent only. Includes logout trail trigger."""

    def __init__(self, on_nav_change: Callable[[str], None]):

        logout_button = ft.IconButton(
            icon=ft.Icons.LOGOUT,
            tooltip="Logout",
            on_click=lambda _: on_nav_change("/logout"),
        )

        super().__init__(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            extended=True,
            min_width=200,
            min_extended_width=200,
            group_alignment=-0.95,
            trailing=logout_button,
        )

        self.on_nav_change = on_nav_change

        self.routes = [
            "/dashboard",
            "/students",
            "/admissions",
            "/courses",
            "/fees",
            "/batch",
            "/settings",
        ]

        self.destinations = [
            ft.NavigationRailDestination(
                icon=ft.Icons.DASHBOARD,
                label="Dashboard",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.PEOPLE,
                label="Students",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.APP_REGISTRATION,
                label="Admissions",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.MENU_BOOK,
                label="Courses",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.MONETIZATION_ON,
                label="Fees",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.GROUP_WORK,
                label="Batch",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.SETTINGS,
                label="Settings",
            ),
        ]

        from core.security.context import SecurityContext
        from core.security.roles import Role
        current_role = SecurityContext.get_current_role()
        if current_role and str(current_role).upper() == Role.ADMINISTRATOR.value:
            self.routes.insert(0, "/control-center")
            self.destinations.insert(
                0,
                ft.NavigationRailDestination(
                    icon=ft.Icons.ADMIN_PANEL_SETTINGS,
                    label="Control Center",
                ),
            )

        self.on_change = self.handle_change

    def handle_change(self, e: ft.ControlEvent):
        self.on_nav_change(self.routes[e.control.selected_index])

    def set_route(self, route: str):
        if route in self.routes:
            self.selected_index = self.routes.index(route)
            try:
                if self.page:
                    self.update()
            except RuntimeError:
                pass
