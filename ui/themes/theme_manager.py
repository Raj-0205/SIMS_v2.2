# ui/themes/theme_manager.py

import flet as ft
from ui.themes.theme import ThemeManager, THEMES

__all__ = ["ThemePersistence"]


class ThemePersistence:
    STORAGE_KEY = "sims_selected_theme"

    @classmethod
    def save_theme(cls, page: ft.Page, theme_id: str) -> None:
        try:
            page.client_storage.set(cls.STORAGE_KEY, theme_id)
        except Exception:
            pass

    @classmethod
    def load_theme(cls, page: ft.Page) -> str:
        try:
            tid = page.client_storage.get(cls.STORAGE_KEY)
            if tid and tid in THEMES:
                return str(tid)
        except Exception:
            pass
        return "minimalism"

    @classmethod
    def apply_theme(cls, page: ft.Page, theme_id: str | None = None) -> str:
        tid = theme_id or cls.load_theme(page)
        tokens = THEMES.get(tid, THEMES["minimalism"])
        ThemeManager().set_theme(tid)

        if page:
            page.theme_mode = tokens.theme_mode
            page.bgcolor = tokens.BACKGROUND
            transitions_cls = getattr(ft, "PageTransitionsTheme", getattr(ft, "PageTransitions", None))
            page_transitions = None
            if transitions_cls and hasattr(ft, "PageTransitionTheme"):
                page_transitions = transitions_cls(
                    windows=ft.PageTransitionTheme.FADE_UPWARDS,
                    linux=ft.PageTransitionTheme.FADE_UPWARDS,
                    macos=ft.PageTransitionTheme.CUPERTINO,
                )

            page.theme = ft.Theme(
                color_scheme_seed=tokens.PRIMARY,
                font_family=tokens.FONT_FAMILY,
                page_transitions=page_transitions,
            )
            try:
                page.update()
            except Exception:
                pass

        return tid
