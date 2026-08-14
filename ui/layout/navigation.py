# ui/layout/navigation.py

import flet as ft
from typing import Callable

__all__ = ["NavigationMenu"]


class NavigationMenu(ft.NavigationRail):

    def __init__(self, on_nav_change: Callable[[str], None]):
        super().__init__(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            extended=True,
            min_width=200,
            min_extended_width=200,
            group_alignment=-0.95,
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

        self.on_change = self.handle_change

    def handle_change(self, e: ft.ControlEvent):
        self.on_nav_change(self.routes[e.control.selected_index])

    def set_route(self, route: str):
        if route in self.routes:
            self.selected_index = self.routes.index(route)
            if self.page:
                self.update()
