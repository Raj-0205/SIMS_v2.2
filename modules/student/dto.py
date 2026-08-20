# modules/student/dto.py

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

__all__ = [
    "StudentDTO",
    "StudentCreateDTO",
    "StudentUpdateDTO",
    "StudentSearchResultDTO",
    "StudentAdmissionDTO",
    "StudentTimelineItemDTO",
    "StudentWorkspaceDTO",
]


@dataclass(frozen=True)
class StudentDTO:
    """Full read contract for a student master entity."""
    id: int
    first_name: str
    last_name: str
    mobile_number: Optional[str] = None
    email: Optional[str] = None
    created_at: str = ""
    admissions_count: int = 0
    current_course: Optional[str] = None
    latest_admission_id: Optional[int] = None
    latest_admission_year: Optional[int] = None
    latest_admission_seq: Optional[int] = None
    admission_status: Optional[str] = None
    latest_admission_date: Optional[str] = None

    @property
    def display_name(self) -> str:
        """Helper for UI to display the full name cleanly."""
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def latest_admission_number(self) -> Optional[str]:
        """Formatted yearly candidate profile number (YYYY-NNN)."""
        if self.latest_admission_year and self.latest_admission_seq:
            return f"{self.latest_admission_year}-{self.latest_admission_seq:03d}"
        if self.latest_admission_id:
            return f"#{self.latest_admission_id}"
        return None

    @property
    def status_label(self) -> str:
        """Determines the status badge label for the student."""
        if self.admission_status:
            return self.admission_status
        if self.admissions_count > 0:
            return "ENROLLED"
        return "REGISTERED"


@dataclass(frozen=True)
class StudentCreateDTO:
    """Contract for creating a new student record."""
    first_name: str
    last_name: str
    mobile_number: Optional[str] = None
    email: Optional[str] = None


@dataclass(frozen=True)
class StudentUpdateDTO:
    """Contract for updating an existing student record."""
    id: int
    first_name: str
    last_name: str
    mobile_number: Optional[str] = None
    email: Optional[str] = None


@dataclass(frozen=True)
class StudentSearchResultDTO:
    """Strict contract for returning search results to the Application/UI layer."""
    id: int
    first_name: str
    last_name: str
    mobile_number: Optional[str] = None

    @property
    def display_name(self) -> str:
        """Helper for UI to display the full name easily."""
        return f"{self.first_name} {self.last_name}".strip()


@dataclass(frozen=True)
class StudentAdmissionDTO:
    """Contract for an admission linked to a student."""
    admission_id: int
    student_id: int
    status: str
    admission_date: str
    candidate_year: Optional[int] = None
    candidate_sequence: Optional[int] = None
    course_id: Optional[int] = None
    course_code: Optional[str] = None
    course_name: Optional[str] = None

    @property
    def admission_number(self) -> str:
        """Formatted yearly candidate profile number (YYYY-NNN)."""
        if self.candidate_year and self.candidate_sequence:
            return f"{self.candidate_year}-{self.candidate_sequence:03d}"
        return f"#{self.admission_id}"


@dataclass(frozen=True)
class StudentTimelineItemDTO:
    """Contract for chronological history/timeline events."""
    timestamp: str
    title: str
    description: str
    event_type: str  # "REGISTRATION", "ADMISSION", "PAYMENT", "UPDATE"


@dataclass(frozen=True)
class StudentWorkspaceDTO:
    """Comprehensive aggregate data contract for the Student Workspace."""
    student: StudentDTO
    admissions: list[StudentAdmissionDTO] = field(default_factory=list)
    timeline: list[StudentTimelineItemDTO] = field(default_factory=list)
