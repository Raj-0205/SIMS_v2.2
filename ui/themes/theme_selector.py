# ui/themes/theme_selector.py

from typing import Callable, Optional
import flet as ft

from ui.themes.theme import ThemeManager, THEMES, AppTheme
from ui.themes.theme_manager import ThemePersistence

__all__ = ["ThemeSelector"]


class ThemeSelector(ft.Container):
    """
    Figma-grade Interactive Theme & Visual Identity Gallery for SIMS.
    Displays live interactive previews of each theme with real-time token
    swatches, hover-lifting cards, instant mode switching, and persistent storage.
    """

    def __init__(self, on_theme_changed: Optional[Callable[[str], None]] = None):
        super().__init__(expand=True)
        self.on_theme_changed = on_theme_changed or (lambda tid: None)
        self.tm = ThemeManager()
        self._build_ui()

    def _build_ui(self) -> None:
        header = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Icon(ft.Icons.PALETTE_ROUNDED, color=AppTheme.PRIMARY, size=24),
                            bgcolor=AppTheme.PRIMARY_LIGHT,
                            padding=ft.Padding(8, 8, 8, 8),
                            border_radius=AppTheme.RADIUS_MD,
                        ),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    "Application Theme & Visual Identity",
                                    size=AppTheme.SIZE_H2,
                                    weight=ft.FontWeight.BOLD,
                                    color=AppTheme.TEXT_PRIMARY,
                                ),
                                ft.Text(
                                    "Curated visual design systems for SIMS. Instant live switching with client persistence.",
                                    size=AppTheme.SIZE_BODY,
                                    color=AppTheme.TEXT_SECONDARY,
                                ),
                            ],
                            spacing=2,
                        ),
                    ],
                    spacing=AppTheme.PAD_SM,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=4,
        )

        cards = [self._create_theme_card(tid) for tid in THEMES.keys()]

        self.cards_grid = ft.ResponsiveRow(
            controls=cards,
            spacing=AppTheme.PAD_MD,
            run_spacing=AppTheme.PAD_MD,
        )

        self.content = ft.Column(
            controls=[
                header,
                ft.Divider(height=1, color=AppTheme.BORDER),
                self.cards_grid,
            ],
            spacing=AppTheme.PAD_MD,
            scroll=ft.ScrollMode.AUTO,
        )

    def _create_theme_card(self, theme_id: str) -> ft.Control:
        tokens = THEMES[theme_id]
        is_active = (self.tm.current_theme_id == theme_id)

        # Miniature realistic UI preview
        if theme_id == "arp_studio":
            preview_box = ft.Container(
                height=95,
                border_radius=tokens.RADIUS_MD,
                bgcolor="#16192E",
                border=ft.Border.all(tokens.border_width, "#2A2E4D"),
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                content=ft.Column(
                    controls=[
                        # Dark Midnight Header with glowing cyan bar & mini notch
                        ft.Container(
                            padding=ft.Padding(8, 6, 8, 4),
                            content=ft.Row(
                                controls=[
                                    ft.Row([
                                        ft.Container(width=10, height=10, border_radius=5, bgcolor="#38BDF8"),
                                        ft.Container(width=28, height=4, border_radius=2, bgcolor="#4361EE"),
                                    ], spacing=3),
                                    # Glowing liquid progress bar
                                    ft.Container(
                                        width=50,
                                        height=3,
                                        border_radius=2,
                                        bgcolor="#38BDF8",
                                        shadow=[ft.BoxShadow(spread_radius=0, blur_radius=6, color="#38BDF8AA")],
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                        ),
                        # Soft Frosted Pearl Lower Half with squircle icon chips and floating sync button
                        ft.Container(
                            expand=True,
                            bgcolor="#EDF0F8",
                            border_radius=ft.BorderRadius(14, 14, tokens.RADIUS_MD, tokens.RADIUS_MD),
                            padding=ft.Padding(8, 6, 8, 6),
                            content=ft.Row(
                                controls=[
                                    # Squircle 1: Amber folder
                                    ft.Container(
                                        width=20, height=20, border_radius=6, bgcolor="#FFFFFF",
                                        shadow=[ft.BoxShadow(blur_radius=4, color="#00000010", offset=ft.Offset(0, 2))],
                                        content=ft.Icon(ft.Icons.FOLDER, size=12, color="#F59E0B"),
                                        alignment=ft.Alignment(0, 0),
                                    ),
                                    # Squircle 2: Cyan media
                                    ft.Container(
                                        width=20, height=20, border_radius=6, bgcolor="#FFFFFF",
                                        shadow=[ft.BoxShadow(blur_radius=4, color="#00000010", offset=ft.Offset(0, 2))],
                                        content=ft.Icon(ft.Icons.IMAGE, size=12, color="#0EA5E9"),
                                        alignment=ft.Alignment(0, 0),
                                    ),
                                    # Squircle 3: Magenta audio
                                    ft.Container(
                                        width=20, height=20, border_radius=6, bgcolor="#FFFFFF",
                                        shadow=[ft.BoxShadow(blur_radius=4, color="#00000010", offset=ft.Offset(0, 2))],
                                        content=ft.Icon(ft.Icons.GRAPHIC_EQ, size=12, color="#EC4899"),
                                        alignment=ft.Alignment(0, 0),
                                    ),
                                    # Floating circular sync button
                                    ft.Container(
                                        width=22, height=22, border_radius=11, bgcolor="#FFFFFF",
                                        border=ft.Border.all(1, "#D5DCF0"),
                                        shadow=[ft.BoxShadow(blur_radius=6, color="#4361EE22", offset=ft.Offset(0, 2))],
                                        content=ft.Icon(ft.Icons.SYNC, size=13, color="#4361EE"),
                                        alignment=ft.Alignment(0, 0),
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        ),
                    ],
                    spacing=0,
                ),
            )
            swatches = ft.Row(
                controls=[
                    ft.Container(width=18, height=18, border_radius=tokens.RADIUS_PILL, bgcolor="#4361EE", tooltip="Liquid Cobalt Primary"),
                    ft.Container(width=18, height=18, border_radius=tokens.RADIUS_PILL, bgcolor="#38BDF8", tooltip="Neon Cyan Glow"),
                    ft.Container(width=18, height=18, border_radius=tokens.RADIUS_PILL, bgcolor="#EC4899", tooltip="Liquid Sunset Coral"),
                    ft.Container(width=18, height=18, border_radius=tokens.RADIUS_PILL, bgcolor="#16192E", border=ft.Border.all(1, "#333A5C"), tooltip="Midnight Indigo"),
                    ft.Container(width=18, height=18, border_radius=tokens.RADIUS_PILL, bgcolor="#EDF0F8", border=ft.Border.all(1, tokens.BORDER), tooltip="Frosted Pearl Base"),
                ],
                spacing=5,
            )
        else:
            preview_box = ft.Container(
                height=95,
                border_radius=tokens.RADIUS_MD,
                bgcolor=tokens.BACKGROUND,
                border=ft.Border.all(tokens.border_width, tokens.BORDER),
                padding=ft.Padding(10, 10, 10, 10),
                content=ft.Column(
                    controls=[
                        # Simulated Topbar
                        ft.Row(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Container(width=14, height=14, border_radius=tokens.RADIUS_SM, bgcolor=tokens.PRIMARY),
                                        ft.Container(width=32, height=6, border_radius=2, bgcolor=tokens.TEXT_SECONDARY),
                                    ],
                                    spacing=4,
                                ),
                                ft.Row(
                                    controls=[
                                        ft.Container(width=40, height=14, border_radius=tokens.RADIUS_PILL, bgcolor=tokens.PRIMARY_LIGHT),
                                        ft.Container(width=12, height=12, border_radius=tokens.RADIUS_PILL, bgcolor=tokens.SECONDARY),
                                    ],
                                    spacing=4,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        # Simulated Content Area with Card
                        ft.Row(
                            controls=[
                                # Mini Sidebar
                                ft.Column(
                                    controls=[
                                        ft.Container(width=12, height=4, border_radius=1, bgcolor=tokens.PRIMARY),
                                        ft.Container(width=10, height=4, border_radius=1, bgcolor=tokens.TEXT_MUTED),
                                        ft.Container(width=10, height=4, border_radius=1, bgcolor=tokens.TEXT_MUTED),
                                    ],
                                    spacing=3,
                                ),
                                # Mini Metric Card
                                ft.Container(
                                    expand=True,
                                    height=46,
                                    bgcolor=tokens.SURFACE,
                                    border_radius=tokens.RADIUS_SM,
                                    border=ft.Border.all(tokens.border_width, tokens.BORDER),
                                    shadow=tokens.shadows,
                                    padding=ft.Padding(6, 6, 6, 6),
                                    content=ft.Row(
                                        controls=[
                                            ft.Container(width=4, height=22, border_radius=2, bgcolor=tokens.PRIMARY),
                                            ft.Column(
                                                controls=[
                                                    ft.Container(width=44, height=6, border_radius=2, bgcolor=tokens.TEXT_PRIMARY),
                                                    ft.Container(width=28, height=4, border_radius=2, bgcolor=tokens.TEXT_MUTED),
                                                ],
                                                spacing=2,
                                                alignment=ft.MainAxisAlignment.CENTER,
                                            ),
                                        ],
                                        spacing=6,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                ),
                            ],
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            expand=True,
                        ),
                    ],
                    spacing=6,
                ),
            )

            # Palette color swatch chips
            swatches = ft.Row(
                controls=[
                    ft.Container(width=18, height=18, border_radius=tokens.RADIUS_PILL, bgcolor=tokens.PRIMARY, tooltip="Primary Accent"),
                    ft.Container(width=18, height=18, border_radius=tokens.RADIUS_PILL, bgcolor=tokens.PRIMARY_HOVER, tooltip="Primary Hover"),
                    ft.Container(width=18, height=18, border_radius=tokens.RADIUS_PILL, bgcolor=tokens.SECONDARY, tooltip="Secondary"),
                    ft.Container(width=18, height=18, border_radius=tokens.RADIUS_PILL, bgcolor=tokens.SURFACE, border=ft.Border.all(1, tokens.BORDER), tooltip="Surface"),
                    ft.Container(width=18, height=18, border_radius=tokens.RADIUS_PILL, bgcolor=tokens.BACKGROUND, border=ft.Border.all(1, tokens.BORDER), tooltip="Background"),
                ],
                spacing=5,
            )

        # Active status badge
        badge = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        ft.Icons.CHECK_CIRCLE if is_active else ft.Icons.RADIO_BUTTON_UNCHECKED,
                        size=14,
                        color=AppTheme.PRIMARY if is_active else AppTheme.TEXT_MUTED,
                    ),
                    ft.Text(
                        "ACTIVE" if is_active else "SELECT",
                        size=11,
                        weight=ft.FontWeight.BOLD,
                        color=AppTheme.PRIMARY if is_active else AppTheme.TEXT_MUTED,
                    ),
                ],
                spacing=4,
            ),
            bgcolor=AppTheme.PRIMARY_LIGHT if is_active else ft.Colors.TRANSPARENT,
            padding=ft.Padding(8, 3, 8, 3),
            border_radius=AppTheme.RADIUS_PILL,
        )

        mode_label = "DARK" if tokens.theme_mode == ft.ThemeMode.DARK else "LIGHT"
        mode_pill = ft.Container(
            content=ft.Text(mode_label, size=9, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_MUTED),
            bgcolor=AppTheme.SURFACE_VARIANT,
            padding=ft.Padding(6, 2, 6, 2),
            border_radius=AppTheme.RADIUS_SM,
        )

        card_container = ft.Container(
            content=ft.Column(
                controls=[
                    preview_box,
                    ft.Row(
                        controls=[
                            ft.Row([ft.Text(tokens.name, size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY), mode_pill], spacing=6),
                            badge,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Text(
                        tokens.description,
                        size=AppTheme.SIZE_CAPTION,
                        color=AppTheme.TEXT_SECONDARY,
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    swatches,
                ],
                spacing=8,
                tight=True,
            ),
            padding=AppTheme.PAD_MD,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(2 if is_active else 1, AppTheme.PRIMARY if is_active else AppTheme.BORDER),
            bgcolor=AppTheme.SURFACE,
            shadow=AppTheme.get_card_shadows(is_hovered=is_active),
            animate=ft.Animation(tokens.animation_duration, tokens.animation_curve),
            animate_scale=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
            tooltip=f"Switch to {tokens.name} Theme",
            ink=True,
            col={"xs": 12, "sm": 6, "md": 6, "lg": 4},
            on_click=lambda _: self._select_theme(theme_id),
        )

        def _on_card_hover(e: ft.ControlEvent) -> None:
            is_h = (e.data == "true")
            card_container.scale = 1.02 if is_h else 1.0
            card_container.border = ft.Border.all(
                2 if (is_active or is_h) else 1,
                AppTheme.PRIMARY if (is_active or is_h) else AppTheme.BORDER,
            )
            card_container.shadow = AppTheme.get_card_shadows(is_hovered=(is_active or is_h))
            try:
                card_container.update()
            except Exception:
                pass

        card_container.on_hover = _on_card_hover
        return card_container

    def _select_theme(self, theme_id: str) -> None:
        if self.page:
            ThemePersistence.save_theme(self.page, theme_id)
            ThemePersistence.apply_theme(self.page, theme_id)
        else:
            self.tm.set_theme(theme_id)

        self.on_theme_changed(theme_id)
        self._build_ui()
        try:
            self.update()
        except Exception:
            pass
