# modules/admission/controller.py

from __future__ import annotations
from typing import Any, Mapping, Optional
from modules.admission.service import AdmissionService
from modules.admission.constants import AdmissionStatus
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
from modules.admission.institution_repository import EducationalInstitutionRepository
from modules.admission.collector_repository import PaymentCollectorRepository

__all__ = ["AdmissionController"]


class AdmissionController:
    """Thin Application Layer for Admissions. Acts as a pass-through between UI and Business Services."""

    def __init__(self) -> None:
        self.service = AdmissionService()
        self.institution_repo = EducationalInstitutionRepository()
        self.collector_repo = PaymentCollectorRepository()

    def create_admission(self, raw_data: Mapping[str, Any]) -> int:
        status_val = raw_data.get("status", AdmissionStatus.DRAFT.value)
        status_enum = AdmissionStatus(status_val) if isinstance(status_val, str) else status_val

        dto = AdmissionCreateDTO(
            course_id=int(raw_data["course_id"]),
            student_id=int(raw_data["student_id"]) if raw_data.get("student_id") else None,
            first_name=raw_data.get("first_name"),
            middle_name=raw_data.get("middle_name"),
            last_name=raw_data.get("last_name"),
            mother_name=raw_data.get("mother_name"),
            dob=raw_data.get("dob"),
            gender=raw_data.get("gender"),
            mobile_number=raw_data.get("mobile_number"),
            email=raw_data.get("email"),
            aadhaar_number=raw_data.get("aadhaar_number"),
            parent_guardian_name=raw_data.get("parent_guardian_name"),
            village=raw_data.get("village"),
            address=raw_data.get("address"),
            qualification=raw_data.get("qualification"),
            qualification_other=raw_data.get("qualification_other"),
            institution_id=int(raw_data["institution_id"]) if raw_data.get("institution_id") else None,
            institution_name=raw_data.get("institution_name"),
            blood_group=raw_data.get("blood_group"),
            photo_path=raw_data.get("photo_path"),
            signature_path=raw_data.get("signature_path"),
            photo_bytes=raw_data.get("photo_bytes"),
            signature_bytes=raw_data.get("signature_bytes"),
            batch_id=int(raw_data["batch_id"]) if raw_data.get("batch_id") else None,
            agreed_fee=float(raw_data.get("agreed_fee", 0.0)),
            discount=float(raw_data.get("discount", 0.0)),
            status=status_enum,
            remarks=raw_data.get("remarks"),
            selected_friend_ids=list(raw_data.get("selected_friend_ids", [])),
            initial_payment_amount=float(raw_data.get("initial_payment_amount", 0.0)),
            payment_mode=raw_data.get("payment_mode"),
            collector_name=raw_data.get("collector_name"),
            collector_id=int(raw_data["collector_id"]) if raw_data.get("collector_id") else None,
            admin_pin=raw_data.get("admin_pin"),
            transaction_ref=raw_data.get("transaction_ref"),
            created_by=int(raw_data["created_by"]) if raw_data.get("created_by") else None,
            candidate_year=int(raw_data["candidate_year"]) if raw_data.get("candidate_year") else None,
            candidate_sequence=int(raw_data["candidate_sequence"]) if raw_data.get("candidate_sequence") else None,
        )
        return self.service.create_admission(dto)

    def update_admission(self, admission_id: int, raw_data: Mapping[str, Any]) -> None:
        status_val = raw_data.get("status", AdmissionStatus.DRAFT.value)
        status_enum = AdmissionStatus(status_val) if isinstance(status_val, str) else status_val

        dto = AdmissionUpdateDTO(
            id=admission_id,
            course_id=int(raw_data.get("course_id", 0)),
            batch_id=int(raw_data["batch_id"]) if raw_data.get("batch_id") else None,
            agreed_fee=float(raw_data.get("agreed_fee", 0.0)),
            discount=float(raw_data.get("discount", 0.0)),
            status=status_enum,
            remarks=raw_data.get("remarks"),
            qualification=raw_data.get("qualification"),
            qualification_other=raw_data.get("qualification_other"),
            institution_id=int(raw_data["institution_id"]) if raw_data.get("institution_id") else None,
            institution_name=raw_data.get("institution_name"),
            blood_group=raw_data.get("blood_group"),
            village=raw_data.get("village"),
            address=raw_data.get("address"),
            aadhaar_number=raw_data.get("aadhaar_number"),
            mother_name=raw_data.get("mother_name"),
            parent_guardian_name=raw_data.get("parent_guardian_name"),
            dob=raw_data.get("dob"),
            gender=raw_data.get("gender"),
            middle_name=raw_data.get("middle_name"),
            photo_path=raw_data.get("photo_path"),
            signature_path=raw_data.get("signature_path"),
        )
        self.service.update_admission(dto)

    def get_admission(self, admission_id: int) -> AdmissionDTO:
        return self.service.get_admission(admission_id)

    def get_admission_workspace(self, admission_id: int) -> AdmissionWorkspaceDTO:
        return self.service.get_admission_workspace(admission_id)

    def filter_admissions(self, filters: Mapping[str, Any]) -> tuple[list[AdmissionDTO], int]:
        dto = AdmissionFilterDTO(
            query=filters.get("query"),
            course_id=int(filters["course_id"]) if filters.get("course_id") and str(filters["course_id"]) != "ALL" else None,
            status=filters.get("status") if filters.get("status") and filters.get("status") != "ALL" else None,
            year=int(filters["year"]) if filters.get("year") and str(filters["year"]) != "ALL" else None,
            month=int(filters["month"]) if filters.get("month") and str(filters["month"]) != "ALL" else None,
            sort_keys=list(filters.get("sort_keys", [("id", "desc")])),
            limit=int(filters.get("limit", 25)),
            offset=int(filters.get("offset", 0)),
        )
        return self.service.filter_admissions(dto)

    def get_summary_statistics(self) -> AdmissionSummaryDTO:
        return self.service.get_summary_statistics()

    def get_suggested_friends(self, village: str, exclude_student_id: int = 0, gender: Optional[str] = None) -> list[FriendSuggestionDTO]:
        return self.service.get_suggested_friends(village, exclude_student_id, gender)

    def get_active_institutions(self) -> list[dict[str, Any]]:
        with self.service.unit_of_work():
            return self.institution_repo.get_active_institutions()

    def add_institution(self, name: str, institution_type: str = "COLLEGE", address: Optional[str] = None) -> int:
        with self.service.unit_of_work():
            return self.institution_repo.insert(name, institution_type, address)

    def get_active_collectors(self) -> list[dict[str, Any]]:
        with self.service.unit_of_work():
            return self.collector_repo.get_active_collectors()

    def add_collector(self, name: str, role_title: Optional[str] = None) -> int:
        with self.service.unit_of_work():
            return self.collector_repo.insert(name, role_title)

    def confirm_admission_with_payment(
        self,
        admission_id: int,
        amount: float,
        payment_mode: str,
        admin_pin: str,
        collector_name: str,
        collector_id: Optional[int] = None,
        transaction_ref: Optional[str] = None,
        actor_id: Optional[int] = None,
    ) -> int:
        return self.service.confirm_admission_with_payment(
            admission_id=admission_id,
            amount=amount,
            payment_mode=payment_mode,
            admin_pin=admin_pin,
            collector_name=collector_name,
            collector_id=collector_id,
            transaction_ref=transaction_ref,
            actor_id=actor_id,
        )

    def export_admissions_csv(self, raw_filter: Mapping[str, Any], target_path: Optional[str] = None) -> str:
        raw_sorts = raw_filter.get("sorts") or raw_filter.get("sort_keys") or [("id", "desc")]
        sort_keys = list(raw_sorts)
        dto = AdmissionFilterDTO(
            query=raw_filter.get("query"),
            course_id=int(raw_filter["course_id"]) if raw_filter.get("course_id") and str(raw_filter["course_id"]) != "ALL" else None,
            status=raw_filter.get("status") if raw_filter.get("status") and raw_filter.get("status") != "ALL" else None,
            year=int(raw_filter["year"]) if raw_filter.get("year") and str(raw_filter["year"]) != "ALL" else None,
            month=int(raw_filter["month"]) if raw_filter.get("month") and str(raw_filter["month"]) != "ALL" else None,
            sort_keys=sort_keys,
        )
        path = self.service.export_admissions_csv(dto, target_path=target_path)
        return str(path)

    def export_admissions_pdf(self, raw_filter: Mapping[str, Any], target_path: Optional[str] = None) -> str:
        raw_sorts = raw_filter.get("sorts") or raw_filter.get("sort_keys") or [("id", "desc")]
        sort_keys = list(raw_sorts)
        dto = AdmissionFilterDTO(
            query=raw_filter.get("query"),
            course_id=int(raw_filter["course_id"]) if raw_filter.get("course_id") and str(raw_filter["course_id"]) != "ALL" else None,
            status=raw_filter.get("status") if raw_filter.get("status") and raw_filter.get("status") != "ALL" else None,
            year=int(raw_filter["year"]) if raw_filter.get("year") and str(raw_filter["year"]) != "ALL" else None,
            month=int(raw_filter["month"]) if raw_filter.get("month") and str(raw_filter["month"]) != "ALL" else None,
            sort_keys=sort_keys,
        )
        path = self.service.export_admissions_pdf(dto, target_path=target_path)
        return str(path)
