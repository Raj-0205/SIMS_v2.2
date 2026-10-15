# ui/themes/theme_manager.py

import flet as ft
from ui.themes.theme import ThemeManager, THEMES

__all__ = ["ThemePersistence"]

class ThemePersistence:
    """
    Handles the persistence of the selected theme.
    Uses Flet's client storage to store the theme ID without needing DB modifications.
    """
    STORAGE_KEY = "sims_selected_theme"

    @classmethod
    def save_theme(cls, page: ft.Page, theme_id: str) -> None:
        page.client_storage.set(cls.STORAGE_KEY, theme_id)

    @classmethod
    def load_theme(cls, page: ft.Page) -> str:
        tid = page.client_storage.get(cls.STORAGE_KEY)
        if tid and tid in THEMES:
            return tid
        return "indigo"

    @classmethod
    def apply_theme(cls, page: ft.Page) -> None:
        """
        Loads the persisted theme and applies it to the ThemeManager.
        """
        theme_id = cls.load_theme(page)
        ThemeManager().set_theme(theme_id)
