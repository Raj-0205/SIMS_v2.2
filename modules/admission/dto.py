# modules/admission/dto.py

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Any
from modules.admission.constants import AdmissionStatus
from modules.payments.dto import PaymentDTO
from modules.receipts.dto import ReceiptDTO

__all__ = [
    "AdmissionCreateDTO",
    "AdmissionUpdateDTO",
    "AdmissionDTO",
    "AdmissionResponseDTO",
    "AdmissionFilterDTO",
    "AdmissionSummaryDTO",
    "AdmissionWorkspaceDTO",
    "FriendSuggestionDTO",
]


@dataclass(frozen=True)
class AdmissionCreateDTO:
    """
    Contract for creating a complete enterprise admission transaction.
    Supports existing student resolution or new student inline creation,
    location, qualification, school/college, course, batch, friend linking,
    and optional initial payment / confirmation.
    """
    course_id: int
    student_id: Optional[int] = None

    # Inline student creation fields (if student_id is None)
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    mother_name: Optional[str] = None
    dob: Optional[str] = None
    gender: Optional[str] = None
    mobile_number: Optional[str] = None
    email: Optional[str] = None
    aadhaar_number: Optional[str] = None
    parent_guardian_name: Optional[str] = None
    village: Optional[str] = None
    address: Optional[str] = None
    qualification: Optional[str] = None
    qualification_other: Optional[str] = None
    institution_id: Optional[int] = None
    institution_name: Optional[str] = None
    blood_group: Optional[str] = None
    photo_path: Optional[str] = None
    signature_path: Optional[str] = None
    photo_bytes: Optional[bytes] = None
    signature_bytes: Optional[bytes] = None

    # Academic & Financial Setup
    batch_id: Optional[int] = None
    agreed_fee: float = 0.0
    discount: float = 0.0
    status: AdmissionStatus = AdmissionStatus.DRAFT
    remarks: Optional[str] = None
    selected_friend_ids: list[int] = field(default_factory=list)

    # Initial Payment for Confirmation
    initial_payment_amount: float = 0.0
    payment_mode: Optional[str] = None
    collector_name: Optional[str] = None
    collector_id: Optional[int] = None
    admin_pin: Optional[str] = None
    transaction_ref: Optional[str] = None
    created_by: Optional[int] = None
    candidate_year: Optional[int] = None
    candidate_sequence: Optional[int] = None


@dataclass(frozen=True)
class AdmissionUpdateDTO:
    """Contract for updating an existing admission record."""
    id: int
    course_id: int
    batch_id: Optional[int] = None
    agreed_fee: float = 0.0
    discount: float = 0.0
    status: AdmissionStatus = AdmissionStatus.DRAFT
    remarks: Optional[str] = None
    qualification: Optional[str] = None
    qualification_other: Optional[str] = None
    institution_id: Optional[int] = None
    institution_name: Optional[str] = None
    blood_group: Optional[str] = None
    village: Optional[str] = None
    address: Optional[str] = None
    aadhaar_number: Optional[str] = None
    mother_name: Optional[str] = None
    parent_guardian_name: Optional[str] = None
    dob: Optional[str] = None
    gender: Optional[str] = None
    middle_name: Optional[str] = None
    photo_path: Optional[str] = None
    signature_path: Optional[str] = None


@dataclass(frozen=True)
class AdmissionDTO:
    """Comprehensive read contract for Admission records."""
    id: int
    student_id: int
    first_name: str
    last_name: str
    course_id: int
    course_code: str
    course_name: str
    course_fee: float
    status: str
    created_at: str
    middle_name: Optional[str] = None
    mother_name: Optional[str] = None
    parent_guardian_name: Optional[str] = None
    dob: Optional[str] = None
    gender: Optional[str] = None
    mobile_number: Optional[str] = None
    email: Optional[str] = None
    aadhaar_number: Optional[str] = None
    village: Optional[str] = None
    address: Optional[str] = None
    qualification: Optional[str] = None
    qualification_other: Optional[str] = None
    institution_id: Optional[int] = None
    institution_name: Optional[str] = None
    blood_group: Optional[str] = None
    batch_id: Optional[int] = None
    batch_name: Optional[str] = None
    batch_timing: Optional[str] = None
    candidate_year: Optional[int] = None
    candidate_sequence: Optional[int] = None
    agreed_fee: float = 0.0
    discount: float = 0.0
    total_paid: float = 0.0
    remarks: Optional[str] = None
    photo_path: Optional[str] = None
    signature_path: Optional[str] = None

    @property
    def student_name(self) -> str:
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join(p.strip() for p in parts if p and p.strip())

    @property
    def student_mobile(self) -> str:
        return self.mobile_number or ""

    @property
    def final_fee(self) -> float:
        fee = self.agreed_fee if self.agreed_fee > 0 else self.course_fee
        return max(0.0, fee - self.discount)

    @property
    def pending_amount(self) -> float:
        return max(0.0, self.final_fee - self.total_paid)

    @property
    def admission_number(self) -> str:
        """Official candidate number YYYY-NNN format."""
        if self.candidate_year and self.candidate_sequence:
            return f"{self.candidate_year}-{self.candidate_sequence:03d}"
        return f"#{self.id}"

    @property
    def fee_display(self) -> str:
        return f"₹{self.final_fee:,.2f}"


@dataclass(frozen=True)
class AdmissionResponseDTO:
    """Backward-compatible response contract."""
    id: int
    student_id: int
    status: AdmissionStatus
    candidate_year: Optional[int] = None
    candidate_sequence: Optional[int] = None
    created_at: Optional[str] = None

    @property
    def admission_number(self) -> str:
        if self.candidate_year and self.candidate_sequence:
            return f"{self.candidate_year}-{self.candidate_sequence:03d}"
        return f"#{self.id}"


@dataclass(frozen=True)
class AdmissionFilterDTO:
    """Query & Filter payload for Admissions directory."""
    query: Optional[str] = None
    course_id: Optional[int] = None
    status: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None
    sort_keys: list[tuple[str, str]] = field(default_factory=lambda: [("id", "desc")])
    limit: int = 25
    offset: int = 0


@dataclass(frozen=True)
class AdmissionSummaryDTO:
    """KPI summary cards for Admissions dashboard & directory."""
    total_admissions: int
    confirmed_count: int
    registered_count: int
    draft_count: int
    today_admissions: int
    total_revenue: float
    today_collection: float
    total_pending: float


@dataclass(frozen=True)
class AdmissionWorkspaceDTO:
    """Aggregate contract for the 360° Admission Workspace."""
    admission: AdmissionDTO
    payments: list[PaymentDTO] = field(default_factory=list)
    receipts: list[ReceiptDTO] = field(default_factory=list)
    confirmed_friends: list[dict[str, Any]] = field(default_factory=list)
    timeline: list[dict[str, Any]] = field(default_factory=list)
    available_batches: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class FriendSuggestionDTO:
    """Contract for suggested friends from the same village."""
    student_id: int
    display_name: str
    gender: Optional[str]
    village: Optional[str]
    mobile_number: Optional[str]
    course_name: Optional[str]
    admission_number: Optional[str]
