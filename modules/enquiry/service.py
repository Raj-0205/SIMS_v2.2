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
    EnquiryCategorySummaryDTO,
    CreateFollowUpDTO,
    FollowUpDTO,
    VillagePeerDTO,
)
from modules.enquiry.repository import EnquiryRepository

__all__ = ["EnquiryService"]

VALID_STATUSES = {"NEW", "CONTACTED", "VISITED", "CONVERTED", "CLOSED"}
VALID_CATEGORIES = {"HOT", "WARM", "COLD", "LOST", "CONVERTED"}


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

        if getattr(dto, "category", None) and dto.category not in VALID_CATEGORIES:
            raise ValidationError(f"Invalid category '{dto.category}'. Must be one of {sorted(VALID_CATEGORIES)}.")

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

        if getattr(dto, "category", None) and dto.category not in VALID_CATEGORIES:
            raise ValidationError(f"Invalid category '{dto.category}'. Must be one of {sorted(VALID_CATEGORIES)}.")

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

    def get_category_summary(self) -> EnquiryCategorySummaryDTO:
        """Calculates lead counts across categories (Hot, Warm, Cold, Lost) and follow-up queues."""
        with self.unit_of_work():
            counts = self.repo.get_category_summary()
            return EnquiryCategorySummaryDTO(
                total=counts.get("total", 0),
                hot=counts.get("hot", 0),
                warm=counts.get("warm", 0),
                cold=counts.get("cold", 0),
                lost=counts.get("lost", 0),
                converted=counts.get("converted", 0),
                today_followup=counts.get("today_followup", 0),
                overdue_followup=counts.get("overdue_followup", 0),
            )

    def record_follow_up(self, dto: CreateFollowUpDTO) -> int:
        """Records a new call/conversation log and automatically syncs the parent enquiry."""
        if not dto.enquiry_id or dto.enquiry_id <= 0:
            raise ValidationError("Valid enquiry ID is required.")
        if not dto.discussion_notes or not dto.discussion_notes.strip():
            raise ValidationError("Follow-up discussion notes are required.")
        if dto.category_after_call and dto.category_after_call not in VALID_CATEGORIES:
            raise ValidationError(f"Invalid category '{dto.category_after_call}'.")

        with self.unit_of_work():
            existing = self.repo.get_by_id(dto.enquiry_id)
            if not existing:
                raise NotFoundError(f"Enquiry with ID {dto.enquiry_id} does not exist.")

            # 1. Insert follow-up entry
            follow_up_id = self.repo.create_follow_up(dto)

            # 2. Update parent status & category
            update_status = existing.get("status") or "NEW"
            if dto.category_after_call == "LOST":
                update_status = "CLOSED"
            elif dto.category_after_call == "CONVERTED":
                update_status = "CONVERTED"
            elif update_status == "NEW":
                update_status = "CONTACTED"

            # 3. Append note to parent notes
            updated_notes = existing.get("notes") or ""
            timestamp_str = datetime.now().strftime("%d-%b %H:%M")
            counselor = dto.counselor_name or "Staff"
            new_remark = f"[{timestamp_str} by {counselor}]: {dto.discussion_notes.strip()}"
            combined_notes = f"{new_remark}\n{updated_notes}".strip() if updated_notes else new_remark

            update_dto = UpdateEnquiryDTO(
                id=existing["id"],
                student_name=existing["student_name"],
                mobile_number=existing["mobile_number"],
                alternate_mobile=existing.get("alternate_mobile"),
                email=existing.get("email"),
                village=existing.get("village"),
                address=existing.get("address"),
                course_id=existing.get("course_id"),
                interested_course=existing.get("interested_course"),
                qualification=existing.get("qualification"),
                gender=existing.get("gender") or "MALE",
                status=update_status,
                category=dto.category_after_call,
                preferred_timing=existing.get("preferred_timing") or "ANY",
                source=existing.get("source") or "WALK_IN",
                follow_up_date=dto.next_follow_up_date or existing.get("follow_up_date"),
                notes=combined_notes,
                counselor_name=dto.counselor_name or existing.get("counselor_name"),
                converted_admission_id=existing.get("converted_admission_id"),
                loss_reason=dto.loss_reason or existing.get("loss_reason"),
            )
            self.repo.update(update_dto)
            return follow_up_id

    def get_follow_ups(self, enquiry_id: int) -> list[FollowUpDTO]:
        """Retrieves chronological call logs for an enquiry."""
        with self.unit_of_work():
            rows = self.repo.get_follow_ups(enquiry_id)
            return [
                FollowUpDTO(
                    id=r["id"],
                    enquiry_id=r["enquiry_id"],
                    follow_up_date=str(r.get("follow_up_date") or ""),
                    call_type=r.get("call_type") or "PHONE",
                    discussion_notes=r.get("discussion_notes") or "",
                    category_after_call=r.get("category_after_call") or "WARM",
                    next_follow_up_date=str(r.get("next_follow_up_date") or "") if r.get("next_follow_up_date") else None,
                    counselor_name=r.get("counselor_name"),
                    created_at=str(r.get("created_at") or ""),
                )
                for r in rows
            ]

    def search_for_admission(self, query: str = "", limit: int = 15) -> list[EnquiryDTO]:
        """Searches enquiries to allow 1-click candidate selection and auto-fill inside the Admission Form."""
        with self.unit_of_work():
            rows = self.repo.search_for_admission(query, limit)
            return [self._map_row_to_dto(r) for r in rows]

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
            "student_name": enquiry.student_name,
            "mobile_number": enquiry.mobile_number,
            "secondary_mobile": enquiry.alternate_mobile or "",
            "email": enquiry.email or "",
            "village": enquiry.village or "",
            "address": enquiry.address or "",
            "gender": enquiry.gender or "MALE",
            "course_id": enquiry.course_id,
            "interested_course": enquiry.interested_course or enquiry.course_name,
            "qualification": enquiry.qualification or "",
            "notes": enquiry.notes or "",
            "category": enquiry.category,
            "preferred_timing": enquiry.preferred_timing,
            "source": enquiry.source,
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
            category=row.get("category") or "WARM",
            preferred_timing=row.get("preferred_timing") or "ANY",
            source=row.get("source") or "WALK_IN",
            follow_up_date=row.get("follow_up_date"),
            notes=row.get("notes"),
            counselor_name=row.get("counselor_name"),
            converted_admission_id=row.get("converted_admission_id"),
            loss_reason=row.get("loss_reason"),
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
            category=dto.category,
            follow_up_filter=dto.follow_up_filter,
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
            "CATEGORY",
            "TIMING",
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
                getattr(enq, "category", "WARM") or "WARM",
                getattr(enq, "preferred_timing", "ANY") or "ANY",
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
            category=dto.category,
            follow_up_filter=dto.follow_up_filter,
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
