# ui/router.py

import flet as ft
from ui.screens.login import LoginScreen
from ui.screens.dashboard import DashboardScreen

__all__ = ["AppRouter"]

class AppRouter:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.page.on_route_change = self.handle_route_change
        self.dashboard = None

    def handle_route_change(self, e: ft.RouteChangeEvent) -> None:
        route = e.route
        self.page.views.clear()

        if route == "/login":
            self.page.views.append(ft.View(route="/login", controls=[LoginScreen(self.page)]))
        else:
            if not self.dashboard:
                self.dashboard = DashboardScreen(self.page)
            if route == "/":
                route = "/dashboard"
                
            self.dashboard.mount_view(route)
            self.page.views.append(ft.View(route=route, controls=[self.dashboard], padding=0))
            
        self.page.update()
