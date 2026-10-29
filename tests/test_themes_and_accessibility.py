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


def test_all_themes_registered():
    expected_themes = {"minimalism", "neumorphism", "claymorphism", "flat", "bento", "arp_studio"}
    assert expected_themes.issubset(set(THEMES.keys()))


@pytest.mark.parametrize("theme_id", ["minimalism", "neumorphism", "claymorphism", "flat", "bento", "arp_studio"])
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


def test_theme_persistence_file_write_and_read():
    import json
    from ui.themes.theme_manager import ThemePersistence

    storage_path = ThemePersistence._get_storage_path()
    ThemePersistence.save_theme(theme_id="bento")

    assert storage_path.exists(), "Persistent storage file was not created on disk"
    with open(storage_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data.get("theme_id") == "bento"
    assert ThemePersistence.load_theme() == "bento"


def test_theme_persistence_simulation_reboot():
    from ui.themes.theme_manager import ThemePersistence

    # User changes theme to claymorphism
    ThemeManager().set_theme("claymorphism", persist=True)
    assert ThemePersistence.load_theme() == "claymorphism"

    # Simulate app exit & fresh bootstrap by loading saved theme
    loaded = ThemeManager().load_saved_theme()
    assert loaded == "claymorphism"
    assert ThemeManager().current_theme_id == "claymorphism"
    assert AppTheme.PRIMARY == THEMES["claymorphism"].PRIMARY
    assert AppTheme.RADIUS_MD == THEMES["claymorphism"].RADIUS_MD


def test_theme_persistence_fallback_on_corrupt_json():
    from ui.themes.theme_manager import ThemePersistence

    storage_path = ThemePersistence._get_storage_path()
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    with open(storage_path, "w", encoding="utf-8") as f:
        f.write("{invalid_json_corrupted_data: true,")

    assert ThemePersistence.load_theme() == "minimalism"
    loaded = ThemeManager().load_saved_theme()
    assert loaded == "minimalism"
    assert ThemeManager().current_theme_id == "minimalism"
    assert AppTheme.PRIMARY == THEMES["minimalism"].PRIMARY


def test_theme_persistence_fallback_on_invalid_theme_id():
    import json
    from ui.themes.theme_manager import ThemePersistence

    storage_path = ThemePersistence._get_storage_path()
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    with open(storage_path, "w", encoding="utf-8") as f:
        json.dump({"theme_id": "non_existent_matrix_9000"}, f)

    assert ThemePersistence.load_theme() == "minimalism"
    loaded = ThemeManager().load_saved_theme()
    assert loaded == "minimalism"


def test_theme_persistence_db_fallback_when_file_deleted():
    from ui.themes.theme_manager import ThemePersistence
    from core.database.engine import DatabaseEngine
    from modules.settings.service import SettingsService

    if not DatabaseEngine.is_initialized():
        pytest.skip("DatabaseEngine not initialized in this context.")

    storage_path = ThemePersistence._get_storage_path()
    ThemePersistence.save_theme(theme_id="flat")

    # Verify written to DB
    setting_val = SettingsService().get_setting("active_theme")
    assert setting_val == "flat"

    # Delete disk file to simulate accidental file loss or fresh reinstall
    if storage_path.exists():
        storage_path.unlink()

    # Load should safely recover from DB
    recovered = ThemePersistence.load_theme()
    assert recovered == "flat"


def test_theme_persistence_atomic_write_integrity():
    from ui.themes.theme_manager import ThemePersistence

    storage_path = ThemePersistence._get_storage_path()
    tmp_path = storage_path.with_suffix(".tmp")

    ThemePersistence.save_theme(theme_id="neumorphism")
    assert storage_path.exists()
    assert not tmp_path.exists(), "Temporary file was not cleaned up after atomic rename"


@pytest.mark.parametrize("theme_id", ["minimalism", "neumorphism", "claymorphism", "flat", "bento", "arp_studio"])
def test_theme_persistence_all_themes_roundtrip(theme_id):
    from ui.themes.theme_manager import ThemePersistence

    ThemePersistence.save_theme(theme_id=theme_id)
    assert ThemePersistence.load_theme() == theme_id

    loaded = ThemeManager().load_saved_theme()
    assert loaded == theme_id
    assert ThemeManager().current_theme_id == theme_id
    assert AppTheme.PRIMARY == THEMES[theme_id].PRIMARY

