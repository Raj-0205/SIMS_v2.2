# modules/enquiry/dto.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class VillagePeerDTO:
    """Enrolled student peer from the same village for social proof and network discovery."""
    id: int
    name: str
    mobile: str
    gender: Optional[str] = None
    village: Optional[str] = None
    course_name: Optional[str] = None


@dataclass(frozen=True)
class CreateEnquiryDTO:
    """Payload to record a new walk-in or prospective student enquiry."""
    student_name: str
    mobile_number: str
    alternate_mobile: Optional[str] = None
    email: Optional[str] = None
    village: Optional[str] = None
    address: Optional[str] = None
    course_id: Optional[int] = None
    interested_course: Optional[str] = None
    qualification: Optional[str] = None
    gender: str = "MALE"
    status: str = "NEW"
    category: str = "WARM"  # HOT (High Priority), WARM (Interested), COLD (Exploring), LOST (Not Interested), CONVERTED
    preferred_timing: Optional[str] = "ANY"  # MORNING, AFTERNOON, EVENING, WEEKEND, ANY
    source: str = "WALK_IN"
    follow_up_date: Optional[str] = None
    notes: Optional[str] = None
    counselor_name: Optional[str] = None
    loss_reason: Optional[str] = None


@dataclass(frozen=True)
class UpdateEnquiryDTO:
    """Payload to update an existing enquiry record."""
    id: int
    student_name: str
    mobile_number: str
    alternate_mobile: Optional[str] = None
    email: Optional[str] = None
    village: Optional[str] = None
    address: Optional[str] = None
    course_id: Optional[int] = None
    interested_course: Optional[str] = None
    qualification: Optional[str] = None
    gender: str = "MALE"
    status: str = "NEW"
    category: str = "WARM"
    preferred_timing: Optional[str] = "ANY"
    source: str = "WALK_IN"
    follow_up_date: Optional[str] = None
    notes: Optional[str] = None
    counselor_name: Optional[str] = None
    converted_admission_id: Optional[int] = None
    loss_reason: Optional[str] = None


@dataclass(frozen=True)
class EnquiryDTO:
    """Full enquiry model returned by service and repository layers."""
    id: int
    student_name: str
    mobile_number: str
    alternate_mobile: Optional[str] = None
    email: Optional[str] = None
    village: Optional[str] = None
    address: Optional[str] = None
    course_id: Optional[int] = None
    interested_course: Optional[str] = None
    qualification: Optional[str] = None
    gender: str = "MALE"
    status: str = "NEW"
    category: str = "WARM"
    preferred_timing: Optional[str] = "ANY"
    source: str = "WALK_IN"
    follow_up_date: Optional[str] = None
    notes: Optional[str] = None
    counselor_name: Optional[str] = None
    converted_admission_id: Optional[int] = None
    loss_reason: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    course_name: Optional[str] = None

    @property
    def enquiry_number(self) -> str:
        return f"ENQ-{self.id:04d}"

    @property
    def first_name(self) -> str:
        parts = (self.student_name or "").strip().split(" ", 2)
        return parts[0] if parts else ""

    @property
    def middle_name(self) -> str:
        parts = (self.student_name or "").strip().split(" ", 2)
        return parts[1] if len(parts) > 2 else ""

    @property
    def last_name(self) -> str:
        parts = (self.student_name or "").strip().split(" ", 2)
        return parts[-1] if len(parts) > 1 else ""

    @property
    def secondary_mobile(self) -> Optional[str]:
        return self.alternate_mobile


@dataclass(frozen=True)
class EnquiryFilterDTO:
    """Filter parameters for listing and searching enquiries."""
    query: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None
    follow_up_filter: Optional[str] = None  # ALL, TODAY, OVERDUE, UPCOMING
    course_id: Optional[int] = None
    village: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True)
class CreateFollowUpDTO:
    """Payload to log a call or counseling remark for an enquiry."""
    enquiry_id: int
    discussion_notes: str
    category_after_call: str = "WARM"  # HOT, WARM, COLD, LOST, CONVERTED
    call_type: str = "PHONE"           # PHONE, WALK_IN, WHATSAPP, VISIT
    follow_up_date: Optional[str] = None
    next_follow_up_date: Optional[str] = None
    counselor_name: Optional[str] = None
    loss_reason: Optional[str] = None


@dataclass(frozen=True)
class FollowUpDTO:
    """Historical timeline entry of an enquiry discussion or follow-up call."""
    id: int
    enquiry_id: int
    follow_up_date: str
    call_type: str
    discussion_notes: str
    category_after_call: str
    next_follow_up_date: Optional[str] = None
    counselor_name: Optional[str] = None
    created_at: str = ""


@dataclass(frozen=True)
class EnquirySummaryDTO:
    """Metrics and KPIs for enquiries."""
    total: int = 0
    new: int = 0
    contacted: int = 0
    visited: int = 0
    converted: int = 0
    closed: int = 0


@dataclass(frozen=True)
class EnquiryCategorySummaryDTO:
    """High-conversion operational metrics for categorized leads and follow-ups."""
    total: int = 0
    hot: int = 0             # High Priority (High Intent)
    warm: int = 0            # Interested (Exploring / Demo)
    cold: int = 0            # Exploring / Low Intent
    lost: int = 0            # Not Interested / Dropped
    converted: int = 0       # Formally Admitted
    today_followup: int = 0  # Calls scheduled for today
    overdue_followup: int = 0 # Calls overdue from past dates

    @property
    def today_follow_ups(self) -> int:
        return self.today_followup

    @property
    def overdue_follow_ups(self) -> int:
        return self.overdue_followup

    @property
    def conversion_rate(self) -> float:
        return (self.converted / self.total * 100.0) if self.total > 0 else 0.0

