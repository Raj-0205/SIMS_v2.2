# ui/widgets/hover_card.py

from __future__ import annotations
from typing import Callable, Optional, Union
import flet as ft

from ui.themes.theme import AppTheme

__all__ = ["HoverCard"]


class HoverCard(ft.Container):
    """
    Figma-grade interactive card container with tactile mouse movement response.
    Features:
    - Subtle resting shadow and border defined by active theme tokens.
    - Smooth hover lift: expands shadows, illuminates border to theme primary/focus,
      and applies tactile micro-scale scaling.
    - Seamless multi-theme support (Minimalism, Neumorphism, Claymorphism, Flat, Bento).
    """

    def __init__(
        self,
        content: Optional[ft.Control] = None,
        padding: Optional[Union[ft.Padding, int]] = None,
        border_radius: Optional[int] = None,
        bgcolor: Optional[str] = None,
        expand: bool = False,
        col: Optional[Union[dict, int]] = None,
        tooltip: Optional[str] = None,
        ink: bool = False,
        hover_scale: Optional[float] = None,
        on_click: Optional[Callable[[ft.ControlEvent], None]] = None,
        **kwargs,
    ):
        self.custom_hover_scale = hover_scale
        tokens = AppTheme.tokens()

        card_padding = padding if padding is not None else AppTheme.PAD_MD
        card_radius = border_radius if border_radius is not None else tokens.RADIUS_MD
        card_bg = bgcolor if bgcolor is not None else tokens.SURFACE

        super().__init__(
            content=content,
            padding=card_padding,
            border_radius=card_radius,
            bgcolor=card_bg,
            border=AppTheme.get_card_border(is_hovered=False),
            shadow=AppTheme.get_card_shadows(is_hovered=False),
            animate=ft.Animation(tokens.animation_duration, tokens.animation_curve),
            animate_scale=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
            expand=expand,
            col=col,
            tooltip=tooltip,
            ink=ink or (on_click is not None),
            on_click=on_click,
            on_hover=self._handle_hover,
            **kwargs,
        )

    def _handle_hover(self, e: ft.ControlEvent) -> None:
        is_hovered = (e.data == "true")
        target_scale = (self.custom_hover_scale or AppTheme.get_hover_scale()) if is_hovered else 1.0

        self.shadow = AppTheme.get_card_shadows(is_hovered=is_hovered)
        self.border = AppTheme.get_card_border(is_hovered=is_hovered)
        self.scale = target_scale

        try:
            self.update()
        except Exception:
            pass
