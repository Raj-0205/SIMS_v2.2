# ui/layout/navigation.py

from __future__ import annotations
from typing import Callable, Optional
import flet as ft
from ui.themes.theme import AppTheme

__all__ = ["NavigationMenu"]


class NavigationMenu(ft.NavigationRail):
    """
    Enterprise Navigation Rail with collapsible icon/expanded states,
    close/hide action, and logout trail trigger.
    """

    def __init__(
        self,
        on_nav_change: Callable[[str], None],
        on_toggle_visibility: Optional[Callable[[], None]] = None,
        on_logout_request: Optional[Callable[[], None]] = None,
    ):
        self.on_nav_change = on_nav_change
        self.on_toggle_visibility = on_toggle_visibility
        self.on_logout_request = on_logout_request

        self.logout_full_btn = ft.OutlinedButton(
            "Log Out",
            icon=ft.Icons.LOGOUT,
            tooltip="Log Out of SIMS",
            style=ft.ButtonStyle(
                color=AppTheme.DANGER,
            ),
            on_click=lambda _: self.on_logout_request() if self.on_logout_request else on_nav_change("/logout"),
            width=178,
        )

        self.logout_icon_btn = ft.IconButton(
            icon=ft.Icons.LOGOUT,
            tooltip="Log Out of SIMS",
            icon_color=AppTheme.DANGER,
            on_click=lambda _: self.on_logout_request() if self.on_logout_request else on_nav_change("/logout"),
        )

        self.trailing_container = ft.Container(
            content=self.logout_full_btn,
            padding=ft.Padding(16, 8, 16, 16),
            alignment=ft.Alignment.BOTTOM_LEFT,
        )


        # Header controls
        self.brand_icon = ft.Icon(ft.Icons.SCHOOL, color=AppTheme.PRIMARY, size=24)
        self.brand_title = ft.Text(
            "SIMS v2.2",
            size=AppTheme.SIZE_BODY,
            weight=ft.FontWeight.BOLD,
            color=AppTheme.TEXT_PRIMARY,
        )
        self.about_btn = ft.IconButton(
            icon=ft.Icons.INFO_OUTLINE,
            icon_size=18,
            icon_color=AppTheme.TEXT_SECONDARY,
            tooltip="About SIMS & The ARP Group",
            on_click=self.handle_open_about,
        )
        self.brand_row = ft.Container(
            content=ft.Row([self.brand_icon, self.brand_title], spacing=6),
            on_click=self.handle_open_about,
            tooltip="About SIMS & The ARP Group",
            border_radius=AppTheme.RADIUS_SM,
        )
        self.collapse_btn = ft.IconButton(
            icon=ft.Icons.MENU_OPEN,
            icon_size=20,
            icon_color=AppTheme.TEXT_SECONDARY,
            tooltip="Collapse to Icons",
            on_click=self.handle_toggle_extended,
        )
        self.close_btn = ft.IconButton(
            icon=ft.Icons.KEYBOARD_DOUBLE_ARROW_LEFT,
            icon_size=20,
            icon_color=AppTheme.TEXT_SECONDARY,
            tooltip="Close Sidebar (Full Width)",
            on_click=lambda _: self.on_toggle_visibility() if self.on_toggle_visibility else None,
        )
        self.compact_close_btn = ft.IconButton(
            icon=ft.Icons.KEYBOARD_DOUBLE_ARROW_LEFT,
            icon_size=18,
            icon_color=AppTheme.TEXT_SECONDARY,
            tooltip="Close Sidebar",
            on_click=lambda _: self.on_toggle_visibility() if self.on_toggle_visibility else None,
        )

        self.header_container = ft.Container(
            content=ft.Row(
                controls=[
                    self.brand_row,
                    ft.Row([self.collapse_btn, self.close_btn], spacing=2),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(12, 10, 8, 10),
            width=210,
            animate_size=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
        )

        super().__init__(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            extended=True,
            min_width=68,
            min_extended_width=210,
            group_alignment=-0.95,
            leading=self.header_container,
            trailing=self.trailing_container,
        )

        self.routes = [
            "/dashboard",
            "/enquiries",
            "/admissions",
            "/students",
            "/courses",
            "/batch",
            "/attendance",
            "/fees",
            "/settings",
        ]

        self.destinations = [
            ft.NavigationRailDestination(
                icon=ft.Icons.DASHBOARD,
                label="Dashboard",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.SUPPORT_AGENT,
                label="Enquiries",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.APP_REGISTRATION,
                label="Admissions",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.PEOPLE,
                label="Students",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.MENU_BOOK,
                label="Courses",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.GROUP_WORK,
                label="Batch",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.CO_PRESENT,
                label="Attendance",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.MONETIZATION_ON,
                label="Fees",
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

    def handle_open_about(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Opens the About SIMS Dialog displaying The ARP Group and Copyright notices."""
        from ui.widgets.about_dialog import open_about_dialog
        p = getattr(self, "_root_page", None) or getattr(self, "_page", None)
        if not p and e and hasattr(e, "page") and e.page:
            p = e.page
        if not p:
            try:
                p = self.page
            except (RuntimeError, AttributeError):
                p = None
        if p:
            open_about_dialog(p)

    def handle_toggle_extended(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Toggles between full expanded sidebar (210px) and compact icon rail (68px)."""
        self.extended = not self.extended
        if self.extended:
            self.collapse_btn.icon = ft.Icons.MENU_OPEN
            self.collapse_btn.tooltip = "Collapse to Icons"
            self.header_container.width = 210
            self.header_container.content = ft.Row(
                controls=[
                    self.brand_row,
                    ft.Row([self.collapse_btn, self.close_btn], spacing=2),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
            self.trailing_container.content = self.logout_full_btn
            self.trailing_container.alignment = ft.Alignment.BOTTOM_LEFT
            self.trailing_container.padding = ft.Padding(16, 8, 16, 16)
        else:
            self.collapse_btn.icon = ft.Icons.MENU
            self.collapse_btn.tooltip = "Expand Sidebar"
            self.header_container.width = 68
            self.header_container.content = ft.Column(
                controls=[
                    self.collapse_btn,
                    self.compact_close_btn,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
            )
            self.trailing_container.content = self.logout_icon_btn
            self.trailing_container.alignment = ft.Alignment.BOTTOM_CENTER
            self.trailing_container.padding = ft.Padding(8, 8, 8, 16)

        try:
            if self.page:
                self.page.update()
            else:
                self.update()
        except Exception:
            pass

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
