# ui/app.py

import flet as ft
from ui.router import AppRouter

__all__ = ["main"]


def main(page: ft.Page) -> None:
    """
    Application UI Bootstrap.
    Configures Flet, initializes the Router, and triggers the first paint.
    """
    page.title = "SIMS v2.2 - ERP Dashboard"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    
    # Initialize Core Router (It automatically binds to page.on_route_change)
    router = AppRouter(page)
    
    # Send the user to the starting state
    page.go("/login")

if __name__ == "__main__":
    ft.app(target=main)
