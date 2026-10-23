# ui/widgets/about_dialog.py

from __future__ import annotations
import webbrowser
from typing import Optional, Any
import flet as ft

from ui.themes.theme import AppTheme
from ui.widgets.hover_card import HoverCard
from ui.widgets.badge import StatusBadge

__all__ = [
    "AboutSIMSDialog",
    "AboutScreenView",
    "open_about_dialog",
    "build_about_content",
    "APP_FULL_NAME",
    "ARP_GROUP_NAME",
    "ARP_GROUP_URL",
    "COPYRIGHT_NOTICE",
]

APP_FULL_NAME = "Sudharm Infotech Management System"
ARP_GROUP_NAME = "The ARP Group"
ARP_GROUP_URL = "https://arpgroup.ai.studio"
COPYRIGHT_NOTICE = "© 2026 The ARP Group. All Rights Reserved."


def open_arp_website(e: Optional[Any] = None) -> None:
    """Safely opens The ARP Group official website in the default browser."""
    try:
        webbrowser.open_new_tab(ARP_GROUP_URL)
    except Exception:
        try:
            webbrowser.open(ARP_GROUP_URL)
        except Exception:
            pass

    if e and hasattr(e, "page") and e.page:
        try:
            e.page.launch_url(ARP_GROUP_URL)
        except Exception:
            pass


def build_about_content(show_full_page: bool = False) -> ft.Control:
    """
    Constructs the rich enterprise content view for SIMS v2.2,
    The ARP Group company profile, and official Copyright notices.
    Wrapped in SelectionArea for universal text selection.
    """
    # ── Section 1: Application Header ──
    app_badge = ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.SCHOOL, color=AppTheme.PRIMARY, size=28),
                ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Text("SIMS", size=AppTheme.SIZE_H2, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                                ft.Container(
                                    content=ft.Text("v2.2 Enterprise", size=11, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                                    bgcolor=AppTheme.PRIMARY_LIGHT,
                                    padding=ft.Padding(8, 2, 8, 2),
                                    border_radius=AppTheme.RADIUS_PILL,
                                ),
                            ],
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Text(
                            APP_FULL_NAME,
                            size=AppTheme.SIZE_BODY,
                            color=AppTheme.TEXT_SECONDARY,
                            weight=ft.FontWeight.W_500,
                        ),
                    ],
                    spacing=2,
                ),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=AppTheme.PAD_MD,
    )

    # ── Section 2: The ARP Group Company Card ──
    arp_website_btn = ft.ElevatedButton(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.OPEN_IN_NEW, size=16),
                ft.Text("Visit Official Website", weight=ft.FontWeight.BOLD),
            ],
            spacing=6,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        tooltip=f"Visit {ARP_GROUP_URL}",
        url=ARP_GROUP_URL,
        on_click=open_arp_website,
        style=ft.ButtonStyle(
            bgcolor=AppTheme.PRIMARY,
            color=ft.Colors.WHITE,
            padding=ft.Padding(16, 12, 16, 12),
        ),
    )

    company_card = HoverCard(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Icon(ft.Icons.BUSINESS, color=AppTheme.PRIMARY, size=22),
                            bgcolor=AppTheme.PRIMARY_LIGHT,
                            padding=8,
                            border_radius=AppTheme.RADIUS_SM,
                        ),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    "DEVELOPED & POWERED BY",
                                    size=10,
                                    weight=ft.FontWeight.BOLD,
                                    color=AppTheme.TEXT_SECONDARY,
                                ),
                                ft.Text(
                                    ARP_GROUP_NAME,
                                    size=AppTheme.SIZE_H3,
                                    weight=ft.FontWeight.BOLD,
                                    color=AppTheme.PRIMARY,
                                ),
                            ],
                            spacing=1,
                        ),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Text(
                    f"{ARP_GROUP_NAME} is an innovative enterprise solutions and AI-driven software engineering leader, "
                    "delivering mission-critical platforms, secure governance ecosystems, and scalable institutional technologies.",
                    size=AppTheme.SIZE_BODY,
                    color=AppTheme.TEXT_PRIMARY,
                ),
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.LANGUAGE, size=16, color=AppTheme.PRIMARY),
                        ft.Text(
                            ARP_GROUP_URL,
                            size=AppTheme.SIZE_BODY,
                            color=AppTheme.PRIMARY,
                            weight=ft.FontWeight.W_600,
                        ),
                    ],
                    spacing=6,
                ),
                ft.Container(height=4),
                ft.Row(
                    controls=[arp_website_btn],
                    alignment=ft.MainAxisAlignment.START,
                ),
            ],
            spacing=AppTheme.PAD_SM,
            tight=True,
        ),
        padding=AppTheme.PAD_LG,
    )

    # ── Section 3: Architecture & System Details ──
    specs_table = ft.Column(
        controls=[
            ft.Text("Application Specifications", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
            ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text("• Core Architecture: Clean Modular Domain-Driven Architecture", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                            ft.Text("• UI Framework: Flet (Flutter High-Performance Engine)", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                            ft.Text("• Runtime: Python 3.14+ Enterprise Environment", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                        ],
                        spacing=4,
                        expand=True,
                    ),
                    ft.Column(
                        controls=[
                            ft.Text("• Database: SQLite WAL High-Concurrency Engine", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                            ft.Text("• Security: Argon2id Hashing + 6-Digit Email OTP", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                            ft.Text("• Performance: Multi-Domain In-Memory Cache System", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                        ],
                        spacing=4,
                        expand=True,
                    ),
                ],
                spacing=AppTheme.PAD_MD,
            ),
        ],
        spacing=AppTheme.PAD_SM,
    )

    # ── Section 4: Copyright & Legal License ──
    copyright_card = ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.COPYRIGHT, color=AppTheme.TEXT_SECONDARY, size=20),
                        ft.Text("Copyright & Intellectual Property Notice", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Text(
                    COPYRIGHT_NOTICE,
                    size=AppTheme.SIZE_BODY,
                    weight=ft.FontWeight.BOLD,
                    color=AppTheme.TEXT_PRIMARY,
                ),
                ft.Text(
                    f"All rights reserved. This software ('SIMS v2.2'), its architecture, UI components, "
                    f"underlying databases, and documentation are the exclusive intellectual property of {ARP_GROUP_NAME}.",
                    size=AppTheme.SIZE_CAPTION,
                    color=AppTheme.TEXT_SECONDARY,
                ),
                ft.Text(
                    "Proprietary Enterprise License: Unauthorized copying, reproduction, distribution, "
                    "reverse engineering, decompilation, or transmission in any form without express written "
                    f"permission from {ARP_GROUP_NAME} is strictly prohibited and protected by international copyright laws.",
                    size=AppTheme.SIZE_CAPTION,
                    color=AppTheme.TEXT_SECONDARY,
                ),
                ft.Divider(height=1, color=AppTheme.BORDER),
                ft.Row(
                    controls=[
                        ft.Text("Official Portal:", size=11, color=AppTheme.TEXT_SECONDARY),
                        ft.Text(ARP_GROUP_URL, size=11, color=AppTheme.PRIMARY, weight=ft.FontWeight.BOLD),
                    ],
                    spacing=6,
                ),
            ],
            spacing=8,
            tight=True,
        ),
        bgcolor=AppTheme.SURFACE_VARIANT,
        border_radius=AppTheme.RADIUS_MD,
        padding=AppTheme.PAD_MD,
        border=ft.Border.all(1, AppTheme.BORDER),
    )

    content_column = ft.Column(
        controls=[
            app_badge,
            company_card,
            specs_table,
            copyright_card,
        ],
        spacing=AppTheme.PAD_MD,
        scroll=ft.ScrollMode.AUTO,
    )

    # Wrap in SelectionArea so all text is selectable!
    return ft.SelectionArea(
        content=content_column,
        expand=True,
    )


class AboutSIMSDialog(ft.AlertDialog):
    """
    Enterprise About & Copyright Dialog for SIMS v2.2.
    Highlights The ARP Group and link to https://arpgroup.ai.studio.
    """

    def __init__(self, page: Optional[ft.Page] = None):
        self._root_page = page

        def close_dialog(e=None):
            self.open = False
            if self._root_page:
                try:
                    if hasattr(self._root_page, "pop_dialog"):
                        self._root_page.pop_dialog()
                    else:
                        self._root_page.update()
                except Exception:
                    pass

        super().__init__(
            modal=True,
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.INFO_OUTLINE, color=AppTheme.PRIMARY, size=24),
                    ft.Text("About SIMS & Legal Notice", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            content=ft.Container(
                content=build_about_content(show_full_page=False),
                width=580,
                padding=AppTheme.PAD_SM,
            ),
            actions=[
                ft.TextButton(
                    content=ft.Text("Visit Website", color=AppTheme.PRIMARY, weight=ft.FontWeight.BOLD),
                    icon=ft.Icons.OPEN_IN_NEW,
                    url=ARP_GROUP_URL,
                    on_click=open_arp_website,
                ),
                ft.ElevatedButton(
                    content=ft.Text("Close"),
                    on_click=close_dialog,
                    style=ft.ButtonStyle(bgcolor=AppTheme.PRIMARY, color=ft.Colors.WHITE),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        self.handle_cancel = close_dialog
        self.close_modal = close_dialog
        self.close_dialog = close_dialog


def open_about_dialog(page: ft.Page) -> AboutSIMSDialog:
    """Helper function to instantiate and display the About SIMS Dialog on any page."""
    dlg = AboutSIMSDialog(page)
    page.dialog = dlg
    if hasattr(page, "show_dialog"):
        try:
            page.show_dialog(dlg)
        except Exception:
            dlg.open = True
            try:
                page.update()
            except Exception:
                pass
    else:
        dlg.open = True
        try:
            page.update()
        except Exception:
            pass
    return dlg


class AboutScreenView(ft.Container):
    """
    Full-page enterprise About & Copyright view mounted inside ContentHost for /about route.
    """

    def __init__(self):
        super().__init__(
            content=build_about_content(show_full_page=True),
            padding=AppTheme.PAD_SM,
            expand=True,
        )

    def load_data(self) -> None:
        pass

