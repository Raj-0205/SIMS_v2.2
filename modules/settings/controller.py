# modules/settings/controller.py

from __future__ import annotations
from typing import Any, Optional
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

    def save_institute_profile(self, profile: dict[str, str]) -> None:
        self.service.save_institute_profile(profile)

    def verify_admin_pin(self, pin: str) -> bool:
        return self.service.verify_admin_pin(pin)

    def set_admin_pin(self, new_pin: str, current_pin: Optional[str] = None) -> bool:
        return self.service.set_admin_pin(new_pin, current_pin)

    def list_institutions(self) -> list[dict[str, Any]]:
        return self.service.list_institutions()

    def get_active_institutions(self) -> list[dict[str, Any]]:
        return self.service.get_active_institutions()

    def create_institution(self, name: str, institution_type: str = "COLLEGE", address: Optional[str] = None) -> int:
        return self.service.create_institution(name, institution_type, address)

    def update_institution(self, inst_id: int, name: str, institution_type: str, address: Optional[str] = None, is_active: bool = True) -> None:
        self.service.update_institution(inst_id, name, institution_type, address, is_active)

    def toggle_institution_status(self, inst_id: int) -> bool:
        return self.service.toggle_institution_status(inst_id)
