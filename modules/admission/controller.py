# modules/admission/controller.py

from typing import Any
from modules.admission.service import AdmissionService
from modules.admission.mapper import AdmissionMapper
from modules.admission.constants import AdmissionStatus

__all__ = ["AdmissionController"]


class AdmissionController:
    """Thin Application Layer for Admissions. NO database interactions allowed."""

    def __init__(self) -> None:
        self.service = AdmissionService()
        # <-- Repository dependency removed. Controller is dumb again.

    def create_admission(self, raw_data: dict[str, Any]) -> int:
        # Default status assignment moved here (Application Layer decides, not Mapper)
        if "status" not in raw_data:
            raw_data["status"] = AdmissionStatus.DRAFT.value

        dto = AdmissionMapper.to_create_dto(raw_data)
        
        # Single delegate to Service. It owns the transaction.
        return self.service.create(dto)
