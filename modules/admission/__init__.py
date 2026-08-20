# modules/admission/__init__.py

from modules.admission.constants import (
    AdmissionStatus,
    Qualification,
    BloodGroup,
    Gender,
    ADMISSION_STATUS_COLORS,
)
from modules.admission.dto import (
    AdmissionCreateDTO,
    AdmissionUpdateDTO,
    AdmissionDTO,
    AdmissionResponseDTO,
    AdmissionFilterDTO,
    AdmissionSummaryDTO,
    AdmissionWorkspaceDTO,
    FriendSuggestionDTO,
)
from modules.admission.mapper import AdmissionMapper
from modules.admission.repository import AdmissionRepository
from modules.admission.service import AdmissionService
from modules.admission.controller import AdmissionController

__all__ = [
    "AdmissionStatus",
    "Qualification",
    "BloodGroup",
    "Gender",
    "ADMISSION_STATUS_COLORS",
    "AdmissionCreateDTO",
    "AdmissionUpdateDTO",
    "AdmissionDTO",
    "AdmissionResponseDTO",
    "AdmissionFilterDTO",
    "AdmissionSummaryDTO",
    "AdmissionWorkspaceDTO",
    "FriendSuggestionDTO",
    "AdmissionMapper",
    "AdmissionRepository",
    "AdmissionService",
    "AdmissionController",
]
