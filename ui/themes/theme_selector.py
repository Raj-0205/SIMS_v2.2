# ui/themes/theme_selector.py

from typing import Callable
import flet as ft

from ui.themes.theme import ThemeManager, THEMES, app_theme
from ui.themes.theme_manager import ThemePersistence

__all__ = ["ThemeSelector"]

class ThemeSelector(ft.Container):
    """
    A premium Theme Selection UI component.
    Allows users to preview and select from the 6 available themes.
    """

    def __init__(self, on_theme_changed: Callable[[str], None]):
        super().__init__()
        self.on_theme_changed = on_theme_changed
        self.tm = ThemeManager()
        
        self._build_ui()

    def _build_ui(self) -> None:
        # Header
        header = ft.Column(
            controls=[
                ft.Text("Application Theme", size=app_theme.SIZE_H3, weight=ft.FontWeight.BOLD, color=app_theme.TEXT_PRIMARY),
                ft.Text("Customize the visual identity of your SIMS environment.", size=app_theme.SIZE_BODY, color=app_theme.TEXT_SECONDARY),
            ],
            spacing=2,
        )

        # Theme Grid
        self.theme_grid = ft.Row(
            controls=[self._create_theme_card(tid) for tid in THEMES.keys()],
            wrap=True,
            spacing=app_theme.PAD_MD,
            alignment=ft.MainAxisAlignment.START,
        )

        self.content = ft.Column(
            controls=[
                header,
                ft.Container(height=app_theme.PAD_SM),
                self.theme_grid,
            ],
            spacing=app_theme.PAD_MD,
            tight=True,
        )

    def _create_theme_card(self, theme_id: str) -> ft.Container:
        tokens = THEMES[theme_id]
        
        # Card visual: a small color swatch + name
        card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        height=40,
                        border_radius=app_theme.RADIUS_SM,
                        bgcolor=tokens.PRIMARY,
                        border=ft.Border.all(1, tokens.BORDER),
                    ),
                    ft.Text(
                        tokens.name, 
                        size=app_theme.SIZE_CAPTION, 
                        weight=ft.FontWeight.W_500, 
                        color=app_theme.TEXT_SECONDARY,
                        text_align=ft.TextAlign.CENTER
                    ),
                ],
                spacing=8,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                tight=True,
            ),
            width=120,
            padding=app_theme.PAD_SM,
            border_radius=app_theme.RADIUS_MD,
            border=ft.Border.all(1, app_theme.BORDER),
            bgcolor=app_theme.SURFACE,
            on_click=lambda e: self._select_theme(theme_id),
            ink=True,
        )

        # Highlight if currently active
        if self.tm.get_theme_id() == theme_id:
            card.border = ft.Border.all(2, tokens.PRIMARY)
            card.bgcolor = app_theme.PRIMARY_LIGHT

        return card

    def _select_theme(self, theme_id: str) -> None:
        self.tm.set_theme(theme_id)
        
        # Persist the choice
        page = self.page
        if page:
            ThemePersistence.save_theme(page, theme_id)
        
        # Notify the app to refresh (UI trigger)
        self.on_theme_changed(theme_id)
        
        # Update the selector UI to show current selection
        self.theme_grid.controls = [self._create_theme_card(tid) for tid in THEMES.keys()]
        self.update()

