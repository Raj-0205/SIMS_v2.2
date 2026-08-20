# modules/settings/service.py

from __future__ import annotations
from typing import Optional
from core.service.base import BaseService
from core.security.auth import AuthService
from core.logger.service import LogService
from core.exceptions import ValidationError, ServiceError
from modules.settings.repository import SettingsRepository

__all__ = ["SettingsService"]


class SettingsService(BaseService):
    """Business service for application & institute configuration and PIN security."""

    DEFAULT_ADMIN_PIN = "1234"

    def __init__(self) -> None:
        self.repository = SettingsRepository()

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self.unit_of_work():
            val = self.repository.get(key)
            return val if val is not None else default

    def set_setting(self, key: str, value: str, category: str = "GENERAL") -> None:
        if not key or not key.strip():
            raise ValidationError("Setting key cannot be empty.")
        with self.unit_of_work():
            self.repository.set(key.strip(), str(value), category=category)

    def get_institute_profile(self) -> dict[str, str]:
        """Returns the branding dictionary for receipts, headers, and UI."""
        return {
            "institute_name": self.get_setting("institute_name", "Sudharm Infotech") or "Sudharm Infotech",
            "contact_person": self.get_setting("contact_person", "Hemant Mahale") or "Hemant Mahale",
            "contact_mobile": self.get_setting("contact_mobile", "9271226772") or "9271226772",
            "alc_code": self.get_setting("alc_code", "57210242") or "57210242",
            "address_line1": self.get_setting("address_line1", "Renuka Complex, 3rd Floor,") or "Renuka Complex, 3rd Floor,",
            "address_line2": self.get_setting("address_line2", "Opp. Market Yard, Chandwad - 423101") or "Opp. Market Yard, Chandwad - 423101",
        }

    def verify_admin_pin(self, pin: str) -> bool:
        """
        Securely verifies Admin authorization PIN against the stored Argon2id hash.
        Never compares plaintext PIN directly.
        """
        if not pin or not pin.strip():
            return False

        pin_clean = pin.strip()
        stored_hash = self.get_setting("admin_pin_hash")

        if stored_hash:
            return AuthService.verify_password(stored_hash, pin_clean)

        # Fallback to default PIN hash if setting was missing
        default_hash = AuthService.hash_password(self.DEFAULT_ADMIN_PIN)
        return AuthService.verify_password(default_hash, pin_clean)
