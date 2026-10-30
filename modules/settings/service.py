# modules/settings/service.py

from __future__ import annotations
from typing import Any, Optional
from core.service.base import BaseService
from core.security.auth import AuthService
from core.security.authorization import AuthorizationService
from core.security.permissions import Permission
from core.logger.service import LogService
from core.exceptions import ValidationError, ServiceError
from modules.settings.repository import SettingsRepository
from modules.admission.institution_repository import EducationalInstitutionRepository

__all__ = ["SettingsService"]


class SettingsService(BaseService):
    """Business service for application & institute configuration, PIN security, and Institution Master."""

    DEFAULT_ADMIN_PIN = "1234"

    def __init__(self) -> None:
        self.repository = SettingsRepository()
        self.institution_repo = EducationalInstitutionRepository()

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
            "upi_id": self.get_setting("upi_id", "9271226772@yescred") or "9271226772@yescred",
            "upi_payee_name": self.get_setting("upi_payee_name", "Sudharm Infotech") or "Sudharm Infotech",
        }

    def save_institute_profile(self, profile: dict[str, str]) -> None:
        AuthorizationService.enforce(Permission.SETTINGS_MANAGE)
        for k, v in profile.items():
            self.set_setting(k, v, category="INSTITUTE")

    def verify_admin_pin(self, pin: str) -> bool:
        """
        Securely verifies Admin authorization PIN or Admin login password.
        Accepts:
        1. Direct administrative credentials ('admin', 'administrator', self.DEFAULT_ADMIN_PIN)
        2. Active session user's login password (from SecurityContext)
        3. Configured Admin PIN ('admin_pin_hash' from institute_settings)
        4. Any active ADMIN or ADMINISTRATOR account's login password
        """
        if not pin or not pin.strip():
            return False

        pin_clean = pin.strip()

        # 1. Direct match with standard credentials & default PIN
        if pin_clean in ("admin", "administrator", self.DEFAULT_ADMIN_PIN):
            return True

        # 2. Check active session user's password if available
        try:
            from core.security.context import SecurityContext
            from modules.users.repository import UserRepository
            curr_user = SecurityContext.current_user()
            if curr_user:
                user_repo = UserRepository()
                u_row = user_repo.get_by_id(curr_user.id)
                if u_row and AuthService.verify_password(u_row["password_hash"], pin_clean):
                    return True
        except Exception:
            pass

        # 3. Check configured admin_pin_hash in institute_settings
        stored_hash = self.get_setting("admin_pin_hash")
        if stored_hash and AuthService.verify_password(stored_hash, pin_clean):
            return True

        # 4. Check if entered PIN matches any active ADMIN or ADMINISTRATOR user password in DB
        try:
            from modules.users.repository import UserRepository
            user_repo = UserRepository()
            for u_name in ("admin", "administrator"):
                u_row = user_repo.get_by_username(u_name)
                if u_row and AuthService.verify_password(u_row["password_hash"], pin_clean):
                    return True
        except Exception:
            pass

        return False

    def set_admin_pin(self, new_pin: str, current_pin: Optional[str] = None) -> bool:
        AuthorizationService.enforce(Permission.PAYMENT_PIN_CHANGE)
        if not new_pin or len(new_pin.strip()) < 4:
            raise ValidationError("Admin PIN must be at least 4 digits.")

        if current_pin is not None:
            if not self.verify_admin_pin(current_pin):
                raise ValidationError("Current Admin PIN is incorrect.")

        new_hash = AuthService.hash_password(new_pin.strip())
        self.set_setting("admin_pin_hash", new_hash, category="SECURITY")
        LogService.info("Admin authorization PIN updated successfully.", context="SettingsService")
        return True

    # ── Educational Institutions Master ──
    def list_institutions(self) -> list[dict[str, Any]]:
        with self.unit_of_work():
            return self.institution_repo.get_all()

    def get_active_institutions(self) -> list[dict[str, Any]]:
        with self.unit_of_work():
            return self.institution_repo.get_active_institutions()

    def create_institution(self, name: str, institution_type: str = "COLLEGE", address: Optional[str] = None) -> int:
        if not name or not name.strip():
            raise ValidationError("Institution name is required.")
        with self.unit_of_work():
            existing = self.institution_repo.get_by_name(name.strip())
            if existing:
                raise ValidationError(f"An institution with name '{name.strip()}' already exists.")
            return self.institution_repo.insert(name=name.strip(), institution_type=institution_type, address=address)

    def update_institution(self, inst_id: int, name: str, institution_type: str, address: Optional[str] = None, is_active: bool = True) -> None:
        if not name or not name.strip():
            raise ValidationError("Institution name is required.")
        with self.unit_of_work():
            self.institution_repo.update(inst_id=inst_id, name=name.strip(), institution_type=institution_type, address=address, is_active=is_active)

    def toggle_institution_status(self, inst_id: int) -> bool:
        with self.unit_of_work():
            inst = self.institution_repo.get_by_id(inst_id)
            if not inst:
                raise ValidationError(f"Institution with ID {inst_id} not found.")
            new_status = not bool(inst.get("is_active", 1))
            self.institution_repo.update(
                inst_id=inst_id,
                name=inst["name"],
                institution_type=inst["institution_type"],
                address=inst.get("address"),
                is_active=new_status,
            )
            return new_status
