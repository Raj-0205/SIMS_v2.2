# modules/enquiry/service.py

from __future__ import annotations
from datetime import datetime
from pathlib import Path
import re
from typing import Any, Optional
from core.service.base import BaseService
from core.exceptions import ValidationError, NotFoundError
from modules.admission.friendship_repository import FriendshipRepository
from modules.enquiry.dto import (
    CreateEnquiryDTO,
    UpdateEnquiryDTO,
    EnquiryDTO,
    EnquiryFilterDTO,
    EnquirySummaryDTO,
    VillagePeerDTO,
)
from modules.enquiry.repository import EnquiryRepository

__all__ = ["EnquiryService"]

VALID_STATUSES = {"NEW", "CONTACTED", "VISITED", "CONVERTED", "CLOSED"}


class EnquiryService(BaseService):
    """Business logic and validation service for student walk-ins and enquiries."""

    def __init__(self, repo: Optional[EnquiryRepository] = None, friendship_repo: Optional[FriendshipRepository] = None) -> None:
        self.repo = repo or EnquiryRepository()
        self.friendship_repo = friendship_repo or FriendshipRepository()

    def _validate_mobile(self, mobile: Optional[str], field_label: str = "Mobile number", required: bool = True) -> str:
        if not mobile or not mobile.strip():
            if required:
                raise ValidationError(f"{field_label} is required.")
            return ""
        
        cleaned = re.sub(r"\D", "", mobile.strip())
        if len(cleaned) != 10:
            raise ValidationError(f"{field_label} must be exactly 10 digits (got {len(cleaned)} digits).")
        return cleaned

    def _validate_create_dto(self, dto: CreateEnquiryDTO) -> None:
        if not dto.student_name or len(dto.student_name.strip()) < 2:
            raise ValidationError("Student name is required and must be at least 2 characters.")

        self._validate_mobile(dto.mobile_number, "Primary mobile number", required=True)

        if dto.alternate_mobile and dto.alternate_mobile.strip():
            self._validate_mobile(dto.alternate_mobile, "Secondary / alternate mobile", required=False)

        if dto.status and dto.status not in VALID_STATUSES:
            raise ValidationError(f"Invalid status '{dto.status}'. Must be one of {sorted(VALID_STATUSES)}.")

    def _validate_update_dto(self, dto: UpdateEnquiryDTO) -> None:
        if not dto.id or dto.id <= 0:
            raise ValidationError("A valid Enquiry ID is required.")

        if not dto.student_name or len(dto.student_name.strip()) < 2:
            raise ValidationError("Student name is required and must be at least 2 characters.")

        self._validate_mobile(dto.mobile_number, "Primary mobile number", required=True)

        if dto.alternate_mobile and dto.alternate_mobile.strip():
            self._validate_mobile(dto.alternate_mobile, "Secondary / alternate mobile", required=False)

        if dto.status and dto.status not in VALID_STATUSES:
            raise ValidationError(f"Invalid status '{dto.status}'. Must be one of {sorted(VALID_STATUSES)}.")

    def create_enquiry(self, dto: CreateEnquiryDTO) -> int:
        self._validate_create_dto(dto)
        with self.unit_of_work():
            return self.repo.create(dto)

    def update_enquiry(self, dto: UpdateEnquiryDTO) -> bool:
        self._validate_update_dto(dto)
        with self.unit_of_work():
            existing = self.repo.get_by_id(dto.id)
            if not existing:
                raise NotFoundError(f"Enquiry with ID {dto.id} does not exist.")
            return self.repo.update(dto)

    def get_enquiry(self, enquiry_id: int) -> EnquiryDTO:
        with self.unit_of_work():
            row = self.repo.get_by_id(enquiry_id)
            if not row:
                raise NotFoundError(f"Enquiry with ID {enquiry_id} does not exist.")
            return self._map_row_to_dto(row)

    def list_enquiries(self, filter_dto: Optional[EnquiryFilterDTO] = None) -> tuple[list[EnquiryDTO], int]:
        filters = filter_dto or EnquiryFilterDTO()
        with self.unit_of_work():
            rows, total = self.repo.search(filters)
            dtos = [self._map_row_to_dto(r) for r in rows]
            return dtos, total

    def get_summary(self) -> EnquirySummaryDTO:
        with self.unit_of_work():
            counts = self.repo.get_summary_counts()
            return EnquirySummaryDTO(
                total=counts.get("total", 0),
                new=counts.get("new", 0),
                contacted=counts.get("contacted", 0),
                visited=counts.get("visited", 0),
                converted=counts.get("converted", 0),
                closed=counts.get("closed", 0),
            )

    def delete_enquiry(self, enquiry_id: int) -> bool:
        with self.unit_of_work():
            existing = self.repo.get_by_id(enquiry_id)
            if not existing:
                raise NotFoundError(f"Enquiry with ID {enquiry_id} does not exist.")
            return self.repo.delete(enquiry_id)

    def mark_converted(self, enquiry_id: int, admission_id: int) -> bool:
        with self.unit_of_work():
            return self.repo.mark_converted(enquiry_id, admission_id)

    def get_village_peers(self, village: str, gender: Optional[str] = None, limit: int = 5) -> list[VillagePeerDTO]:
        """Find enrolled students from the same village to show village peers/friends list."""
        if not village or not village.strip():
            return []
        with self.unit_of_work():
            rows = self.friendship_repo.get_suggested_friends(village=village, gender=gender, limit=limit)
            peers = []
            for r in rows:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip()
                peers.append(
                    VillagePeerDTO(
                        id=r["id"],
                        name=name,
                        mobile=r.get("mobile_number") or "",
                        gender=r.get("gender"),
                        village=r.get("village"),
                        course_name=r.get("course_name"),
                    )
                )
            return peers

    def convert_to_admission_draft(self, enquiry_id: int) -> dict[str, Any]:
        """Pre-populates an admission draft dictionary from an existing enquiry."""
        enquiry = self.get_enquiry(enquiry_id)
        parts = enquiry.student_name.strip().split(" ", 2)
        first_name = parts[0]
        last_name = parts[-1] if len(parts) > 1 else ""
        middle_name = parts[1] if len(parts) > 2 else ""

        return {
            "first_name": first_name,
            "middle_name": middle_name,
            "last_name": last_name,
            "mobile_number": enquiry.mobile_number,
            "secondary_mobile": enquiry.alternate_mobile or "",
            "email": enquiry.email or "",
            "village": enquiry.village or "",
            "address": enquiry.address or "",
            "gender": enquiry.gender or "MALE",
            "course_id": enquiry.course_id,
            "qualification": enquiry.qualification or "",
            "notes": enquiry.notes or "",
            "enquiry_id": enquiry.id,
        }

    def _map_row_to_dto(self, row: dict[str, Any]) -> EnquiryDTO:
        return EnquiryDTO(
            id=row["id"],
            student_name=row["student_name"],
            mobile_number=row["mobile_number"],
            alternate_mobile=row.get("alternate_mobile"),
            email=row.get("email"),
            village=row.get("village"),
            address=row.get("address"),
            course_id=row.get("course_id"),
            interested_course=row.get("interested_course"),
            qualification=row.get("qualification"),
            gender=row.get("gender") or "MALE",
            status=row.get("status") or "NEW",
            source=row.get("source") or "WALK_IN",
            follow_up_date=row.get("follow_up_date"),
            notes=row.get("notes"),
            counselor_name=row.get("counselor_name"),
            converted_admission_id=row.get("converted_admission_id"),
            created_at=str(row.get("created_at") or ""),
            updated_at=str(row.get("updated_at") or ""),
            course_name=row.get("course_name"),
        )

    def export_enquiries_excel(self, filter_dto: Optional[EnquiryFilterDTO] = None, target_path: Optional[str | Path] = None) -> Path:
        """Exports filtered enquiries into a styled Microsoft Excel (.xlsx) workbook with bold headers."""
        from infrastructure.excel.exporter import ExcelExporter

        dto = filter_dto or EnquiryFilterDTO()
        export_filter = EnquiryFilterDTO(
            query=dto.query,
            status=dto.status,
            course_id=dto.course_id,
            village=dto.village,
            date_from=dto.date_from,
            date_to=dto.date_to,
            limit=100000,
            offset=0,
        )
        enquiries, _ = self.list_enquiries(export_filter)

        default_dir = Path("exports/enquiries")
        default_name = f"enquiries_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        path = Path(target_path) if target_path else default_dir / default_name

        headers = [
            "SR.NO",
            "ENQUIRY DATE",
            "STUDENT NAME",
            "MOBILE NO",
            "ALTERNATE NO",
            "EMAIL",
            "VILLAGE",
            "INTERESTED COURSE",
            "QUALIFICATION",
            "GENDER",
            "STATUS",
            "SOURCE",
            "COUNSELOR",
            "FOLLOW UP DATE",
            "NOTES",
        ]
        rows = []
        for idx, enq in enumerate(enquiries, start=1):
            rows.append([
                idx,
                str(enq.created_at)[:10] if enq.created_at else "—",
                enq.student_name,
                enq.mobile_number or "—",
                enq.alternate_mobile or "—",
                enq.email or "—",
                enq.village or "—",
                enq.course_name or enq.interested_course or "—",
                enq.qualification or "—",
                enq.gender or "—",
                enq.status,
                enq.source,
                enq.counselor_name or "—",
                enq.follow_up_date or "—",
                enq.notes or "—",
            ])

        return ExcelExporter.export_to_excel(
            headers=headers,
            rows=rows,
            output_path=path,
            sheet_name="Enquiries",
            title="SUDHARM INFOTECH - PROSPECTIVE STUDENT ENQUIRIES",
            subtitle=f"Generated on {datetime.now().strftime('%d-%b-%Y %I:%M %p')} • Total Enquiries: {len(enquiries)}",
            include_totals=False,
        )

    def export_enquiries_csv(self, filter_dto: Optional[EnquiryFilterDTO] = None, target_path: Optional[str | Path] = None) -> Path:
        """Exports filtered enquiries to RFC-4180 CSV format."""
        from infrastructure.excel.exporter import ExcelExporter

        dto = filter_dto or EnquiryFilterDTO()
        export_filter = EnquiryFilterDTO(
            query=dto.query,
            status=dto.status,
            course_id=dto.course_id,
            village=dto.village,
            date_from=dto.date_from,
            date_to=dto.date_to,
            limit=100000,
            offset=0,
        )
        enquiries, _ = self.list_enquiries(export_filter)

        default_dir = Path("exports/enquiries")
        default_name = f"enquiries_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path = Path(target_path) if target_path else default_dir / default_name

        headers = [
            "SR.NO",
            "ENQUIRY DATE",
            "STUDENT NAME",
            "MOBILE NO",
            "ALTERNATE NO",
            "EMAIL",
            "VILLAGE",
            "INTERESTED COURSE",
            "QUALIFICATION",
            "GENDER",
            "STATUS",
            "SOURCE",
            "COUNSELOR",
            "FOLLOW UP DATE",
            "NOTES",
        ]
        rows = []
        for idx, enq in enumerate(enquiries, start=1):
            rows.append([
                idx,
                str(enq.created_at)[:10] if enq.created_at else "—",
                enq.student_name,
                enq.mobile_number or "—",
                enq.alternate_mobile or "—",
                enq.email or "—",
                enq.village or "—",
                enq.course_name or enq.interested_course or "—",
                enq.qualification or "—",
                enq.gender or "—",
                enq.status,
                enq.source,
                enq.counselor_name or "—",
                enq.follow_up_date or "—",
                enq.notes or "—",
            ])

        return ExcelExporter.export_to_csv(
            headers=headers,
            rows=rows,
            output_path=path,
        )
