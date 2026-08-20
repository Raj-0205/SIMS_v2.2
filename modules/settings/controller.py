# modules/settings/controller.py

from __future__ import annotations
from typing import Optional
from modules.settings.service import SettingsService

__all__ = ["SettingsController"]


class SettingsController:
    """Thin Application Layer for Settings."""

    def __init__(self) -> None:
        self.service = SettingsService()

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return self.service.get_setting(key, default)

    def set_setting(self, key: str, value: str, category: str = "GENERAL") -> None:
        self.service.set_setting(key, value, category)

    def get_institute_profile(self) -> dict[str, str]:
        return self.service.get_institute_profile()

    def verify_admin_pin(self, pin: str) -> bool:
        return self.service.verify_admin_pin(pin)

    def set_admin_pin(self, new_pin: str, current_pin: Optional[str] = None) -> bool:
        return self.service.set_admin_pin(new_pin, current_pin)
