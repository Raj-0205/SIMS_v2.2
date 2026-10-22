# ui/widgets/badge.py

from __future__ import annotations
from typing import Optional
import flet as ft

from ui.themes.theme import AppTheme

__all__ = ["StatusBadge"]


class StatusBadge(ft.Container):
    """
    Figma-styled status pill badge with clean typography, tinted background,
    and hairline accent border.
    """

    def __init__(
        self,
        label: str = "",
        variant: str = "primary",
        icon: Optional[str] = None,
        size: int = 12,
        text: Optional[str] = None,
        **kwargs,
    ):
        actual_label = text if text is not None else label
        text_color, bg_color = AppTheme.get_badge_colors(variant)

        controls = []
        if icon:
            controls.append(ft.Icon(icon, size=size + 2, color=text_color))
        else:
            # Subtle status indicator dot
            controls.append(
                ft.Container(
                    width=6,
                    height=6,
                    border_radius=AppTheme.RADIUS_PILL,
                    bgcolor=text_color,
                )
            )

        controls.append(
            ft.Text(
                actual_label.upper(),
                size=size - 1,
                weight=ft.FontWeight.BOLD,
                color=text_color,
            )
        )

        super().__init__(
            content=ft.Row(
                controls=controls,
                spacing=5,
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=bg_color,
            padding=ft.Padding(8, 4, 8, 4),
            border_radius=AppTheme.RADIUS_PILL,
            border=ft.Border.all(1, text_color + "33" if len(text_color) == 7 else text_color),
            **kwargs,
        )
