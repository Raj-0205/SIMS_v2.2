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
    source: str = "WALK_IN"
    follow_up_date: Optional[str] = None
    notes: Optional[str] = None
    counselor_name: Optional[str] = None


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
    source: str = "WALK_IN"
    follow_up_date: Optional[str] = None
    notes: Optional[str] = None
    counselor_name: Optional[str] = None
    converted_admission_id: Optional[int] = None


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
    source: str = "WALK_IN"
    follow_up_date: Optional[str] = None
    notes: Optional[str] = None
    counselor_name: Optional[str] = None
    converted_admission_id: Optional[int] = None
    created_at: str = ""
    updated_at: str = ""
    course_name: Optional[str] = None


@dataclass(frozen=True)
class EnquiryFilterDTO:
    """Filter parameters for listing and searching enquiries."""
    query: Optional[str] = None
    status: Optional[str] = None
    course_id: Optional[int] = None
    village: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True)
class EnquirySummaryDTO:
    """Metrics and KPIs for enquiries."""
    total: int = 0
    new: int = 0
    contacted: int = 0
    visited: int = 0
    converted: int = 0
    closed: int = 0
