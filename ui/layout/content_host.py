# ui/layout/content_host.py

from __future__ import annotations
import flet as ft
from ui.themes.theme import AppTheme

__all__ = ["ContentHost"]


class ContentHost(ft.Container):
    def __init__(self) -> None:
        self.switcher = ft.AnimatedSwitcher(
            content=ft.Container(),
            transition=ft.AnimatedSwitcherTransition.FADE,
            duration=260,
            reverse_duration=180,
            switch_in_curve=ft.AnimationCurve.EASE_OUT,
            switch_out_curve=ft.AnimationCurve.EASE_IN,
            expand=True,
        )

        self.selection_area = ft.SelectionArea(
            content=self.switcher,
            expand=True,
        )

        self._is_loading: bool = False

        super().__init__(
            content=self.selection_area,
            expand=True,
            padding=ft.Padding(16, 12, 16, 12),
            alignment=ft.Alignment.TOP_LEFT,
            animate_size=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
        )

    @property
    def is_loading(self) -> bool:
        return self._is_loading

    @property
    def content(self) -> ft.Control:
        if hasattr(self, "switcher") and self.switcher.content is not None:
            return self.switcher.content
        return self._values.get("content")

    @content.setter
    def content(self, val: ft.Control) -> None:
        if val is getattr(self, "selection_area", None) or val is getattr(self, "switcher", None):
            self._values["content"] = val
        elif hasattr(self, "switcher"):
            self.switcher.content = val
        else:
            self._values["content"] = val

    def show_loader(
        self,
        route: str,
        title: Optional[str] = None,
        icon: Optional[str] = None,
        description: Optional[str] = None,
    ) -> ft.Control:
        from ui.widgets.adaptive_loader import AdaptiveModuleLoader
        loader = AdaptiveModuleLoader(route, title=title, icon=icon, description=description)
        self._is_loading = True
        self.switcher.content = loader
        try:
            self.update()
        except (RuntimeError, AttributeError):
            pass
        return loader

    def mount(self, view: ft.Control) -> None:
        self._is_loading = False
        self.switcher.content = view
        try:
            self.update()
        except (RuntimeError, AttributeError):
            pass

