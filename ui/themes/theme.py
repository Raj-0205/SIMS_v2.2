# ui/themes/theme.py

from dataclasses import dataclass

__all__ = ["AppTheme"]


@dataclass(frozen=True)
class AppTheme:
    """
    Central Design Tokens for SIMS v2.2.
    Provides consistent colors, typography sizing, spacing, and border radius tokens.
    """

    # --- Colors ---
    PRIMARY: str = "#1E3A8A"          # Deep Navy Blue
    PRIMARY_HOVER: str = "#2563EB"    # Bright Accent Blue
    PRIMARY_LIGHT: str = "#EFF6FF"    # Subtle Blue Tint
    
    SURFACE: str = "#FFFFFF"          # Pure White Card/Surface
    SURFACE_VARIANT: str = "#F8FAFC"  # Light Slate Surface
    BACKGROUND: str = "#F1F5F9"       # Muted Canvas Background
    
    BORDER: str = "#E2E8F0"           # Light Border
    BORDER_FOCUS: str = "#3B82F6"     # Focus Border
    
    TEXT_PRIMARY: str = "#0F172A"     # High-contrast Slate Text
    TEXT_SECONDARY: str = "#64748B"   # Medium Muted Slate
    TEXT_MUTED: str = "#94A3B8"       # Low-contrast Placeholder
    
    SUCCESS: str = "#10B981"          # Emerald Green
    SUCCESS_LIGHT: str = "#ECFDF5"    # Emerald Tint
    
    WARNING: str = "#F59E0B"          # Warm Amber
    
    DANGER: str = "#EF4444"           # Crimson Red
    DANGER_LIGHT: str = "#FEF2F2"     # Crimson Tint

    # --- Spacing & Padding ---
    PAD_XS: int = 4
    PAD_SM: int = 8
    PAD_MD: int = 16
    PAD_LG: int = 24
    PAD_XL: int = 32

    # --- Border Radius ---
    RADIUS_SM: int = 6
    RADIUS_MD: int = 8
    RADIUS_LG: int = 12
    RADIUS_PILL: int = 999

    # --- Typography ---
    FONT_FAMILY: str = "Helvetica Neue"
    SIZE_H1: int = 24
    SIZE_H2: int = 18
    SIZE_H3: int = 16
    SIZE_BODY: int = 14
    SIZE_CAPTION: int = 12

    # --- Elevation ---
    ELEVATION_CARD: int = 1
    ELEVATION_MODAL: int = 8
