# modules/admission/controller.py

from __future__ import annotations
from typing import Any, Mapping
from modules.admission.service import AdmissionService
from modules.admission.mapper import AdmissionMapper
from modules.admission.constants import AdmissionStatus
from modules.admission.dto import AdmissionResponseDTO

__all__ = ["AdmissionController"]


class AdmissionController:
    """Thin Application Layer for Admissions. NO database interactions allowed."""

    def __init__(self) -> None:
        self.service = AdmissionService()

    def create_admission(self, raw_data: Mapping[str, Any]) -> int:
        mutable_data = dict(raw_data)
        if "status" not in mutable_data:
            mutable_data["status"] = AdmissionStatus.DRAFT.value

        dto = AdmissionMapper.to_create_dto(mutable_data)
        return self.service.create(dto)

    def get_admission(self, admission_id: int) -> AdmissionResponseDTO:
        return self.service.get_admission(admission_id)
