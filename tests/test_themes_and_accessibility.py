# tests/test_themes_and_accessibility.py

import pytest
from ui.themes.theme import THEMES, ThemeManager, AppTheme


def relative_luminance(hex_color: str) -> float:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 8:
        hex_color = hex_color[:6]
    r, g, b = [int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4)]
    
    def transform(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * transform(r) + 0.7152 * transform(g) + 0.0722 * transform(b)


def contrast_ratio(color1: str, color2: str) -> float:
    l1 = relative_luminance(color1)
    l2 = relative_luminance(color2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def test_all_five_themes_registered():
    expected_themes = {"minimalism", "neumorphism", "claymorphism", "flat", "bento"}
    assert expected_themes.issubset(set(THEMES.keys()))


@pytest.mark.parametrize("theme_id", ["minimalism", "neumorphism", "claymorphism", "flat", "bento"])
def test_theme_wcag_text_contrast_conformance(theme_id):
    tokens = THEMES[theme_id]
    contrast_surface = contrast_ratio(tokens.TEXT_PRIMARY, tokens.SURFACE)
    assert contrast_surface >= 4.5, f"Theme '{theme_id}' fails WCAG AA on SURFACE"

    contrast_bg = contrast_ratio(tokens.TEXT_PRIMARY, tokens.BACKGROUND)
    assert contrast_bg >= 4.5, f"Theme '{theme_id}' fails WCAG AA on BACKGROUND"


def test_theme_manager_state_propagation():
    tm = ThemeManager()
    tm.set_theme("bento")
    assert AppTheme.PRIMARY == THEMES["bento"].PRIMARY
    assert AppTheme.BACKGROUND == THEMES["bento"].BACKGROUND

    tm.set_theme("claymorphism")
    assert AppTheme.PRIMARY == THEMES["claymorphism"].PRIMARY
    assert AppTheme.RADIUS_MD == THEMES["claymorphism"].RADIUS_MD

    tm.set_theme("minimalism")
    assert AppTheme.PRIMARY == THEMES["minimalism"].PRIMARY
