# ui/layout/content_host.py

import flet as ft

__all__ = ["ContentHost"]


class ContentHost(ft.Container):
    """Dynamic content area."""

    def __init__(self) -> None:
        super().__init__(
            expand=True,
            padding=30,
            alignment=ft.Alignment.TOP_LEFT,
        )

    def mount(self, view: ft.Control) -> None:
        self.content = view

        # Update only after the control is attached to a page.
        try:
            self.update()
        except RuntimeError:
            pass
