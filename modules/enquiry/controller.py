# modules/enquiry/controller.py

from __future__ import annotations
from typing import Any, Mapping, Optional
from modules.enquiry.dto import (
    CreateEnquiryDTO,
    UpdateEnquiryDTO,
    EnquiryDTO,
    EnquiryFilterDTO,
    EnquirySummaryDTO,
    VillagePeerDTO,
)
from modules.enquiry.service import EnquiryService

__all__ = ["EnquiryController"]


class EnquiryController:
    """Thin Application Layer for Enquiries. Connects UI and EnquiryService."""

    def __init__(self, service: Optional[EnquiryService] = None) -> None:
        self.service = service or EnquiryService()

    def create_enquiry(self, raw_data: Mapping[str, Any]) -> int:
        dto = CreateEnquiryDTO(
            student_name=str(raw_data.get("student_name") or "").strip(),
            mobile_number=str(raw_data.get("mobile_number") or "").strip(),
            alternate_mobile=str(raw_data.get("alternate_mobile") or "").strip() or None,
            email=str(raw_data.get("email") or "").strip() or None,
            village=str(raw_data.get("village") or "").strip() or None,
            address=str(raw_data.get("address") or "").strip() or None,
            course_id=int(raw_data["course_id"]) if raw_data.get("course_id") else None,
            interested_course=str(raw_data.get("interested_course") or "").strip() or None,
            qualification=str(raw_data.get("qualification") or "").strip() or None,
            gender=str(raw_data.get("gender") or "MALE").strip().upper(),
            status=str(raw_data.get("status") or "NEW").strip().upper(),
            source=str(raw_data.get("source") or "WALK_IN").strip().upper(),
            follow_up_date=str(raw_data.get("follow_up_date") or "").strip() or None,
            notes=str(raw_data.get("notes") or "").strip() or None,
            counselor_name=str(raw_data.get("counselor_name") or "").strip() or None,
        )
        return self.service.create_enquiry(dto)

    def update_enquiry(self, raw_data: Mapping[str, Any]) -> bool:
        dto = UpdateEnquiryDTO(
            id=int(raw_data["id"]),
            student_name=str(raw_data.get("student_name") or "").strip(),
            mobile_number=str(raw_data.get("mobile_number") or "").strip(),
            alternate_mobile=str(raw_data.get("alternate_mobile") or "").strip() or None,
            email=str(raw_data.get("email") or "").strip() or None,
            village=str(raw_data.get("village") or "").strip() or None,
            address=str(raw_data.get("address") or "").strip() or None,
            course_id=int(raw_data["course_id"]) if raw_data.get("course_id") else None,
            interested_course=str(raw_data.get("interested_course") or "").strip() or None,
            qualification=str(raw_data.get("qualification") or "").strip() or None,
            gender=str(raw_data.get("gender") or "MALE").strip().upper(),
            status=str(raw_data.get("status") or "NEW").strip().upper(),
            source=str(raw_data.get("source") or "WALK_IN").strip().upper(),
            follow_up_date=str(raw_data.get("follow_up_date") or "").strip() or None,
            notes=str(raw_data.get("notes") or "").strip() or None,
            counselor_name=str(raw_data.get("counselor_name") or "").strip() or None,
            converted_admission_id=int(raw_data["converted_admission_id"]) if raw_data.get("converted_admission_id") else None,
        )
        return self.service.update_enquiry(dto)

    def get_enquiry(self, enquiry_id: int) -> EnquiryDTO:
        return self.service.get_enquiry(enquiry_id)

    def list_enquiries(
        self,
        query: Optional[str] = None,
        status: Optional[str] = None,
        course_id: Optional[int] = None,
        village: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[EnquiryDTO], int]:
        filters = EnquiryFilterDTO(
            query=query,
            status=status,
            course_id=course_id,
            village=village,
            limit=limit,
            offset=offset,
        )
        return self.service.list_enquiries(filters)

    def get_summary(self) -> EnquirySummaryDTO:
        return self.service.get_summary()

    def delete_enquiry(self, enquiry_id: int) -> bool:
        return self.service.delete_enquiry(enquiry_id)

    def get_village_peers(self, village: str, gender: Optional[str] = None) -> list[VillagePeerDTO]:
        return self.service.get_village_peers(village=village, gender=gender)

    def convert_to_admission_draft(self, enquiry_id: int) -> dict[str, Any]:
        return self.service.convert_to_admission_draft(enquiry_id)

    def export_enquiries_excel(
        self,
        query: Optional[str] = None,
        status: Optional[str] = None,
        course_id: Optional[int] = None,
        village: Optional[str] = None,
        target_path: Optional[str] = None,
    ) -> str:
        dto = EnquiryFilterDTO(
            query=query,
            status=status if status and status != "ALL" else None,
            course_id=course_id,
            village=village,
            limit=100000,
            offset=0,
        )
        return str(self.service.export_enquiries_excel(dto, target_path=target_path))

    def export_enquiries_csv(
        self,
        query: Optional[str] = None,
        status: Optional[str] = None,
        course_id: Optional[int] = None,
        village: Optional[str] = None,
        target_path: Optional[str] = None,
    ) -> str:
        dto = EnquiryFilterDTO(
            query=query,
            status=status if status and status != "ALL" else None,
            course_id=course_id,
            village=village,
            limit=100000,
            offset=0,
        )
        return str(self.service.export_enquiries_csv(dto, target_path=target_path))
