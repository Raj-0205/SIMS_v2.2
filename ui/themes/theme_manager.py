from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Optional
import flet as ft
from ui.themes.theme import ThemeManager, THEMES

__all__ = ["ThemePersistence"]


class ThemePersistence:
    STORAGE_KEY = "sims_selected_theme"
    _CONFIG_FILE_NAME = "theme_preference.json"

    @classmethod
    def _get_storage_path(cls) -> Path:
        """
        Determines the persistent storage file path.
        In test mode (SIMS_ENV == 'testing'), uses an isolated test config path.
        Otherwise uses project's config directory, with home directory fallback.
        """
        sims_env = os.environ.get("SIMS_ENV", "").lower()
        project_root = Path(__file__).resolve().parent.parent.parent
        config_dir = project_root / "config"

        if sims_env == "testing":
            return config_dir / "theme_preference_test.json"

        try:
            config_dir.mkdir(parents=True, exist_ok=True)
            return config_dir / cls._CONFIG_FILE_NAME
        except Exception:
            home_dir = Path.home() / ".sudharm_sims"
            home_dir.mkdir(parents=True, exist_ok=True)
            return home_dir / cls._CONFIG_FILE_NAME

    @classmethod
    def save_theme(cls, page: Optional[Any] = None, theme_id: Optional[str] = None) -> None:
        """
        Persistently saves the selected theme to disk so it survives
        app closure, process termination, and PC shutdown.
        Also attempts saving to database settings if available.
        Can be called as save_theme(page, theme_id), save_theme(theme_id), or save_theme(theme_id=...).
        """
        if theme_id is None and isinstance(page, str):
            actual_theme_id = page
            actual_page = None
        else:
            actual_theme_id = theme_id
            actual_page = page if isinstance(page, ft.Page) else None

        if not actual_theme_id or actual_theme_id not in THEMES:
            return

        # 1. Save to persistent JSON file with atomic write and fsync
        file_path = cls._get_storage_path()
        tmp_path = file_path.with_suffix(".tmp")
        try:
            data = {"theme_id": actual_theme_id}
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, file_path)
        except Exception:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass
            # If project config is read-only (e.g. production packaged app), fallback to home directory
            if os.environ.get("SIMS_ENV", "").lower() != "testing":
                try:
                    home_dir = Path.home() / ".sudharm_sims"
                    home_dir.mkdir(parents=True, exist_ok=True)
                    home_file = home_dir / cls._CONFIG_FILE_NAME
                    home_tmp = home_file.with_suffix(".tmp")
                    with open(home_tmp, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                        f.flush()
                        os.fsync(f.fileno())
                    os.replace(home_tmp, home_file)
                except Exception:
                    if home_tmp.exists():
                        try:
                            home_tmp.unlink()
                        except Exception:
                            pass

        # 2. Save to SQLite database (if initialized)
        try:
            from core.database.engine import DatabaseEngine
            if DatabaseEngine.is_initialized():
                from modules.settings.service import SettingsService
                SettingsService().set_setting("active_theme", actual_theme_id, category="APPEARANCE")
        except Exception:
            pass

        # 3. Optional client_storage fallback (if supported by page)
        if actual_page is not None and hasattr(actual_page, "client_storage") and actual_page.client_storage is not None:
            try:
                actual_page.client_storage.set(cls.STORAGE_KEY, actual_theme_id)
            except Exception:
                pass

    @classmethod
    def load_theme(cls, page: Optional[ft.Page] = None) -> str:
        """
        Loads the persistently saved theme.
        Returns the saved theme_id if valid, otherwise 'minimalism'.
        """
        # 1. Try loading from client_storage if available on page
        if page is not None and hasattr(page, "client_storage") and page.client_storage is not None:
            try:
                tid = page.client_storage.get(cls.STORAGE_KEY)
                if tid and str(tid) in THEMES:
                    return str(tid)
            except Exception:
                pass

        # 2. Try loading from persistent JSON file
        file_path = cls._get_storage_path()
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    tid = data.get("theme_id")
                    if tid and str(tid) in THEMES:
                        return str(tid)
            except Exception:
                pass

        # 3. Try loading from database settings if DB is initialized
        try:
            from core.database.engine import DatabaseEngine
            if DatabaseEngine.is_initialized():
                from modules.settings.service import SettingsService
                tid = SettingsService().get_setting("active_theme")
                if tid and str(tid) in THEMES:
                    return str(tid)
        except Exception:
            pass

        # 4. Fallback to user home directory if not found in project config
        home_path = Path.home() / ".sudharm_sims" / cls._CONFIG_FILE_NAME
        if home_path.exists():
            try:
                with open(home_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    tid = data.get("theme_id")
                    if tid and str(tid) in THEMES:
                        return str(tid)
            except Exception:
                pass

        return "minimalism"

    @classmethod
    def apply_theme(cls, page: Optional[ft.Page] = None, theme_id: Optional[str] = None) -> str:
        tid = theme_id or cls.load_theme(page)
        if tid not in THEMES:
            tid = "minimalism"

        tokens = THEMES[tid]

        # Update ThemeManager and AppTheme
        ThemeManager().set_theme(tid, persist=False)

        # If a specific theme was requested to be applied, ensure it is saved
        if theme_id is not None:
            cls.save_theme(page, theme_id)

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
