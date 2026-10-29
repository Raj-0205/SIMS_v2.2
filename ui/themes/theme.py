# ui/themes/theme.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Optional, Dict, List
import flet as ft

__all__ = ["ThemeTokens", "THEMES", "ThemeManager", "AppTheme"]


@dataclass(frozen=True)
class ThemeTokens:
    """Design Tokens for a specific SIMS visual theme."""

    id: str
    name: str
    description: str
    theme_mode: ft.ThemeMode = ft.ThemeMode.LIGHT

    # Core Colors
    PRIMARY: str = "#1E3A8A"
    PRIMARY_HOVER: str = "#2563EB"
    PRIMARY_LIGHT: str = "#EFF6FF"

    SECONDARY: str = "#64748B"
    SECONDARY_LIGHT: str = "#F1F5F9"

    SURFACE: str = "#FFFFFF"
    SURFACE_VARIANT: str = "#F8FAFC"
    BACKGROUND: str = "#F1F5F9"

    BORDER: str = "#E2E8F0"
    BORDER_FOCUS: str = "#3B82F6"

    # High-contrast Typography (WCAG AAA compliant)
    TEXT_PRIMARY: str = "#0F172A"
    TEXT_SECONDARY: str = "#475569"
    TEXT_MUTED: str = "#94A3B8"

    # Status
    SUCCESS: str = "#10B981"
    SUCCESS_LIGHT: str = "#ECFDF5"
    INFO: str = "#2563EB"
    INFO_LIGHT: str = "#EFF6FF"
    WARNING: str = "#F59E0B"
    WARNING_LIGHT: str = "#FFFBEB"
    DANGER: str = "#EF4444"
    DANGER_LIGHT: str = "#FEF2F2"

    # Spacing
    PAD_XS: int = 4
    PAD_SM: int = 8
    PAD_MD: int = 16
    PAD_LG: int = 24
    PAD_XL: int = 32

    # Radii
    RADIUS_SM: int = 6
    RADIUS_MD: int = 8
    RADIUS_LG: int = 12
    RADIUS_PILL: int = 999

    # Typography
    FONT_FAMILY: str = "Helvetica Neue"
    SIZE_H1: int = 24
    SIZE_H2: int = 18
    SIZE_H3: int = 16
    SIZE_BODY: int = 14
    SIZE_CAPTION: int = 12

    # Depth & Shadows
    ELEVATION_CARD: int = 1
    ELEVATION_MODAL: int = 8
    shadows: Optional[List[ft.BoxShadow]] = None
    hover_shadows: Optional[List[ft.BoxShadow]] = None
    border_width: float = 1.0
    hover_scale: float = 1.0
    animation_duration: int = 200
    animation_curve: ft.AnimationCurve = ft.AnimationCurve.EASE_OUT


THEMES: Dict[str, ThemeTokens] = {
    # 1. MINIMALISM
    "minimalism": ThemeTokens(
        id="minimalism",
        name="Minimalism",
        description="Clean, distraction-free interface with refined hairline borders, mono-slate tones, and high contrast.",
        theme_mode=ft.ThemeMode.LIGHT,
        PRIMARY="#18181B",
        PRIMARY_HOVER="#27272A",
        PRIMARY_LIGHT="#F4F4F5",
        SECONDARY="#64748B",
        SECONDARY_LIGHT="#F1F5F9",
        SURFACE="#FFFFFF",
        SURFACE_VARIANT="#FAFAFA",
        BACKGROUND="#F8FAFC",
        BORDER="#E2E8F0",
        BORDER_FOCUS="#18181B",
        TEXT_PRIMARY="#09090B",
        TEXT_SECONDARY="#52525B",
        TEXT_MUTED="#A1A1AA",
        RADIUS_SM=4,
        RADIUS_MD=6,
        RADIUS_LG=8,
        border_width=1.0,
        shadows=[
            ft.BoxShadow(spread_radius=0, blur_radius=2, color="#00000008", offset=ft.Offset(0, 1))
        ],
        hover_shadows=[
            ft.BoxShadow(spread_radius=0, blur_radius=12, color="#00000014", offset=ft.Offset(0, 6)),
            ft.BoxShadow(spread_radius=0, blur_radius=3, color="#0000000A", offset=ft.Offset(0, 1)),
        ],
        hover_scale=1.01,
        animation_duration=180,
        animation_curve=ft.AnimationCurve.EASE_OUT,
    ),

    # 2. NEUMORPHISM
    "neumorphism": ThemeTokens(
        id="neumorphism",
        name="Neumorphism",
        description="Soft, tactile extruded surfaces with realistic dual light and dark shadow casting.",
        theme_mode=ft.ThemeMode.LIGHT,
        PRIMARY="#2563EB",
        PRIMARY_HOVER="#1D4ED8",
        PRIMARY_LIGHT="#DBEAFE",
        SECONDARY="#64748B",
        SECONDARY_LIGHT="#E2E8F0",
        SURFACE="#E8ECF2",
        SURFACE_VARIANT="#DFE5ED",
        BACKGROUND="#E8ECF2",
        BORDER="#D1D9E6",
        BORDER_FOCUS="#2563EB",
        TEXT_PRIMARY="#0F172A",
        TEXT_SECONDARY="#334155",
        TEXT_MUTED="#64748B",
        RADIUS_SM=10,
        RADIUS_MD=16,
        RADIUS_LG=22,
        border_width=1.0,
        shadows=[
            ft.BoxShadow(spread_radius=1, blur_radius=10, color="#FFFFFF", offset=ft.Offset(-5, -5)),
            ft.BoxShadow(spread_radius=1, blur_radius=10, color="#CCD5E2", offset=ft.Offset(5, 5)),
        ],
        hover_shadows=[
            ft.BoxShadow(spread_radius=2, blur_radius=16, color="#FFFFFF", offset=ft.Offset(-7, -7)),
            ft.BoxShadow(spread_radius=2, blur_radius=16, color="#B0BFD3", offset=ft.Offset(7, 7)),
        ],
        hover_scale=1.015,
        animation_duration=220,
        animation_curve=ft.AnimationCurve.EASE_IN_OUT,
    ),

    # 3. CLAYMORPHISM
    "claymorphism": ThemeTokens(
        id="claymorphism",
        name="Claymorphism",
        description="Playful 3D clay aesthetic with pillowy curves, bouncy feedback, and glowing ambient drop shadows.",
        theme_mode=ft.ThemeMode.LIGHT,
        PRIMARY="#6366F1",
        PRIMARY_HOVER="#4F46E5",
        PRIMARY_LIGHT="#EEF2FF",
        SECONDARY="#8B5CF6",
        SECONDARY_LIGHT="#F5F3FF",
        SURFACE="#FFFFFF",
        SURFACE_VARIANT="#F5F3FF",
        BACKGROUND="#EEF2FF",
        BORDER="#E0E7FF",
        BORDER_FOCUS="#6366F1",
        TEXT_PRIMARY="#1E1B4B",
        TEXT_SECONDARY="#4338CA",
        TEXT_MUTED="#6B7280",
        RADIUS_SM=12,
        RADIUS_MD=20,
        RADIUS_LG=28,
        RADIUS_PILL=999,
        border_width=1.5,
        shadows=[
            ft.BoxShadow(spread_radius=0, blur_radius=16, color="#6366F126", offset=ft.Offset(0, 8)),
            ft.BoxShadow(spread_radius=0, blur_radius=2, color="#00000008", offset=ft.Offset(0, 1)),
        ],
        hover_shadows=[
            ft.BoxShadow(spread_radius=2, blur_radius=24, color="#6366F13D", offset=ft.Offset(0, 12)),
            ft.BoxShadow(spread_radius=0, blur_radius=4, color="#00000010", offset=ft.Offset(0, 2)),
        ],
        hover_scale=1.025,
        animation_duration=260,
        animation_curve=ft.AnimationCurve.EASE_OUT_BACK,
    ),

    # 4. FLAT DESIGN
    "flat": ThemeTokens(
        id="flat",
        name="Flat Design",
        description="Crisp modern Swiss flat UI with structured geometry, sky blue accents, and solid drop shadows.",
        theme_mode=ft.ThemeMode.LIGHT,
        PRIMARY="#0284C7",
        PRIMARY_HOVER="#0369A1",
        PRIMARY_LIGHT="#E0F2FE",
        SECONDARY="#475569",
        SECONDARY_LIGHT="#F1F5F9",
        SURFACE="#FFFFFF",
        SURFACE_VARIANT="#F8FAFC",
        BACKGROUND="#F8FAFC",
        BORDER="#CBD5E1",
        BORDER_FOCUS="#0284C7",
        TEXT_PRIMARY="#0F172A",
        TEXT_SECONDARY="#334155",
        TEXT_MUTED="#64748B",
        RADIUS_SM=4,
        RADIUS_MD=6,
        RADIUS_LG=8,
        border_width=1.5,
        shadows=[
            ft.BoxShadow(spread_radius=0, blur_radius=0, color="#CBD5E1", offset=ft.Offset(2, 2))
        ],
        hover_shadows=[
            ft.BoxShadow(spread_radius=0, blur_radius=0, color="#0284C7", offset=ft.Offset(4, 4))
        ],
        hover_scale=1.0,
        animation_duration=140,
        animation_curve=ft.AnimationCurve.LINEAR,
    ),

    # 5. BENTO UI
    "bento": ThemeTokens(
        id="bento",
        name="Bento UI",
        description="High-tech dark obsidian compartmentalized grid with radiant cyan borders and acrylic depth.",
        theme_mode=ft.ThemeMode.DARK,
        PRIMARY="#38BDF8",
        PRIMARY_HOVER="#60A5FA",
        PRIMARY_LIGHT="#082F49",
        SECONDARY="#94A3B8",
        SECONDARY_LIGHT="#1E293B",
        SURFACE="#131B2E",
        SURFACE_VARIANT="#1E293B",
        BACKGROUND="#0B0F17",
        BORDER="#233044",
        BORDER_FOCUS="#38BDF8",
        TEXT_PRIMARY="#F8FAFC",
        TEXT_SECONDARY="#94A3B8",
        TEXT_MUTED="#64748B",
        SUCCESS="#34D399",
        SUCCESS_LIGHT="#064E3B",
        WARNING="#FBBF24",
        WARNING_LIGHT="#451A03",
        DANGER="#F87171",
        DANGER_LIGHT="#450A0A",
        RADIUS_SM=8,
        RADIUS_MD=14,
        RADIUS_LG=20,
        border_width=1.0,
        shadows=[
            ft.BoxShadow(spread_radius=0, blur_radius=16, color="#00000080", offset=ft.Offset(0, 4)),
            ft.BoxShadow(spread_radius=0, blur_radius=1, color="#38BDF81F", offset=ft.Offset(0, 0)),
        ],
        hover_shadows=[
            ft.BoxShadow(spread_radius=2, blur_radius=26, color="#000000B0", offset=ft.Offset(0, 8)),
            ft.BoxShadow(spread_radius=1, blur_radius=12, color="#38BDF855", offset=ft.Offset(0, 0)),
        ],
        hover_scale=1.018,
        animation_duration=280,
        animation_curve=ft.AnimationCurve.EASE_IN_OUT_CUBIC,
    ),

    # 6. ARP STUDIO
    "arp_studio": ThemeTokens(
        id="arp_studio",
        name="ARP Studio",
        description="Liquid organic neumorphism with midnight indigo contrast, frosted lavender-pearl surfaces, and fluid neon accents.",
        theme_mode=ft.ThemeMode.LIGHT,
        PRIMARY="#4361EE",
        PRIMARY_HOVER="#3A0CA3",
        PRIMARY_LIGHT="#EEF2FF",
        SECONDARY="#64748B",
        SECONDARY_LIGHT="#F1F5F9",
        SURFACE="#FFFFFF",
        SURFACE_VARIANT="#EAEFFB",
        BACKGROUND="#EDF0F8",
        BORDER="#D5DCF0",
        BORDER_FOCUS="#4361EE",
        TEXT_PRIMARY="#0F172A",
        TEXT_SECONDARY="#334155",
        TEXT_MUTED="#64748B",
        SUCCESS="#10B981",
        SUCCESS_LIGHT="#ECFDF5",
        INFO="#4361EE",
        INFO_LIGHT="#EEF2FF",
        WARNING="#F59E0B",
        WARNING_LIGHT="#FFFBEB",
        DANGER="#EF4444",
        DANGER_LIGHT="#FEF2F2",
        RADIUS_SM=8,
        RADIUS_MD=14,
        RADIUS_LG=22,
        RADIUS_PILL=999,
        border_width=1.2,
        shadows=[
            ft.BoxShadow(spread_radius=1, blur_radius=12, color="#FFFFFFF0", offset=ft.Offset(-4, -4)),
            ft.BoxShadow(spread_radius=0, blur_radius=14, color="#C4CEE888", offset=ft.Offset(5, 5)),
        ],
        hover_shadows=[
            ft.BoxShadow(spread_radius=2, blur_radius=18, color="#FFFFFF", offset=ft.Offset(-6, -6)),
            ft.BoxShadow(spread_radius=1, blur_radius=20, color="#B0BEDE99", offset=ft.Offset(6, 6)),
            ft.BoxShadow(spread_radius=0, blur_radius=12, color="#4361EE33", offset=ft.Offset(0, 4)),
        ],
        hover_scale=1.02,
        animation_duration=220,
        animation_curve=ft.AnimationCurve.EASE_OUT,
    ),
}


class ThemeManager:
    _instance: Optional[ThemeManager] = None

    def __new__(cls) -> ThemeManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._current_id = "minimalism"
            cls._instance._listeners: List[Callable[[str], None]] = []
        return cls._instance

    @property
    def current_theme_id(self) -> str:
        return self._current_id

    @property
    def current(self) -> ThemeTokens:
        return THEMES.get(self._current_id, THEMES["minimalism"])

    def add_listener(self, callback: Callable[[str], None]) -> None:
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[str], None]) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    def load_saved_theme(self) -> str:
        """Loads and applies the saved theme from persistent storage."""
        try:
            from ui.themes.theme_manager import ThemePersistence
            saved_id = ThemePersistence.load_theme()
            if saved_id in THEMES:
                self.set_theme(saved_id, persist=False)
                return saved_id
        except Exception:
            pass
        self.set_theme("minimalism", persist=False)
        return "minimalism"

    def set_theme(self, theme_id: str, persist: bool = True) -> None:
        if theme_id not in THEMES:
            theme_id = "minimalism"

        self._current_id = theme_id
        active = THEMES[theme_id]

        for field_name in ThemeTokens.__dataclass_fields__:
            val = getattr(active, field_name)
            attr_name = field_name.upper() if field_name.islower() and not field_name.startswith("RADIUS") else field_name
            setattr(AppTheme, attr_name, val)

        if persist:
            try:
                from ui.themes.theme_manager import ThemePersistence
                ThemePersistence.save_theme(None, theme_id)
            except Exception:
                pass

        for listener in list(self._listeners):
            try:
                listener(theme_id)
            except Exception:
                pass


class AppTheme:
    PRIMARY: str = THEMES["minimalism"].PRIMARY
    PRIMARY_HOVER: str = THEMES["minimalism"].PRIMARY_HOVER
    PRIMARY_LIGHT: str = THEMES["minimalism"].PRIMARY_LIGHT
    SECONDARY: str = THEMES["minimalism"].SECONDARY
    SECONDARY_LIGHT: str = THEMES["minimalism"].SECONDARY_LIGHT
    SURFACE: str = THEMES["minimalism"].SURFACE
    SURFACE_VARIANT: str = THEMES["minimalism"].SURFACE_VARIANT
    BACKGROUND: str = THEMES["minimalism"].BACKGROUND
    BORDER: str = THEMES["minimalism"].BORDER
    BORDER_FOCUS: str = THEMES["minimalism"].BORDER_FOCUS
    TEXT_PRIMARY: str = THEMES["minimalism"].TEXT_PRIMARY
    TEXT_SECONDARY: str = THEMES["minimalism"].TEXT_SECONDARY
    TEXT_MUTED: str = THEMES["minimalism"].TEXT_MUTED
    SUCCESS: str = THEMES["minimalism"].SUCCESS
    SUCCESS_LIGHT: str = THEMES["minimalism"].SUCCESS_LIGHT
    INFO: str = THEMES["minimalism"].INFO
    INFO_LIGHT: str = THEMES["minimalism"].INFO_LIGHT
    WARNING: str = THEMES["minimalism"].WARNING
    WARNING_LIGHT: str = THEMES["minimalism"].WARNING_LIGHT
    DANGER: str = THEMES["minimalism"].DANGER
    DANGER_LIGHT: str = THEMES["minimalism"].DANGER_LIGHT
    PAD_XS: int = 4
    PAD_SM: int = 8
    PAD_MD: int = 16
    PAD_LG: int = 24
    PAD_XL: int = 32
    RADIUS_SM: int = THEMES["minimalism"].RADIUS_SM
    RADIUS_MD: int = THEMES["minimalism"].RADIUS_MD
    RADIUS_LG: int = THEMES["minimalism"].RADIUS_LG
    RADIUS_PILL: int = THEMES["minimalism"].RADIUS_PILL
    FONT_FAMILY: str = "Helvetica Neue"
    SIZE_H1: int = 24
    SIZE_H2: int = 18
    SIZE_H3: int = 16
    SIZE_BODY: int = 14
    SIZE_CAPTION: int = 12
    ELEVATION_CARD: int = 1
    ELEVATION_MODAL: int = 8

    @classmethod
    def tokens(cls) -> ThemeTokens:
        return ThemeManager().current

    @classmethod
    def get_card_shadows(cls, is_hovered: bool = False) -> Optional[List[ft.BoxShadow]]:
        t = ThemeManager().current
        return t.hover_shadows if is_hovered else t.shadows

    @classmethod
    def get_card_border(cls, is_hovered: bool = False) -> ft.Border:
        t = ThemeManager().current
        color = t.PRIMARY if is_hovered else t.BORDER
        return ft.Border.all(t.border_width, color)

    @classmethod
    def get_hover_scale(cls) -> float:
        return ThemeManager().current.hover_scale

    @classmethod
    def get_scale_animation(cls) -> ft.Animation:
        return ft.Animation(160, ft.AnimationCurve.EASE_OUT)

    @classmethod
    def is_dark(cls) -> bool:
        return ThemeManager().current.theme_mode == ft.ThemeMode.DARK

    @classmethod
    def get_badge_colors(cls, variant: str = "primary") -> tuple[str, str]:
        t = ThemeManager().current
        v = variant.lower()
        if v in ("success", "confirmed", "active", "present", "paid"):
            return (t.SUCCESS, t.SUCCESS_LIGHT)
        elif v in ("warning", "pending", "registered", "draft"):
            return (t.WARNING, t.WARNING_LIGHT)
        elif v in ("danger", "error", "inactive", "absent", "failed", "cancelled"):
            return (t.DANGER, t.DANGER_LIGHT)
        elif v in ("info", "secondary"):
            return (t.INFO, t.INFO_LIGHT)
        return (t.PRIMARY, t.PRIMARY_LIGHT)


ThemeManager().load_saved_theme()
