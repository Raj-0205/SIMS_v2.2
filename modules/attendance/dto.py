# modules/attendance/dto.py

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, List, Dict, Any


@dataclass
class BatchStudentDTO:
    """Enrolled student metadata for a given batch."""
    student_id: int
    admission_id: int
    candidate_number: Optional[str]
    student_name: str
    first_name: str
    last_name: str
    mobile_number: Optional[str]
    village: Optional[str]
    course_id: int
    course_name: str
    admission_date: Optional[str]
    pending_fees: float = 0.0
    total_paid: float = 0.0
    final_fee: float = 0.0


@dataclass
class AttendanceRecordDTO:
    """Attendance marking for a single student in a session."""
    student_id: int
    student_name: str
    candidate_number: Optional[str] = None
    status: str = "ABSENT"  # PRESENT / ABSENT
    marking_method: str = "TOGGLE"  # TOGGLE / OCR_SCAN / MANUAL_EDIT
    confidence_score: float = 1.0
    remarks: Optional[str] = None
    admission_id: Optional[int] = None
    record_id: Optional[int] = None


@dataclass
class AttendanceSessionDTO:
    """Attendance session header metadata for a batch on a date."""
    id: Optional[int]
    batch_id: int
    batch_name: str
    course_name: str
    session_date: str
    mode: str = "ONLINE"  # ONLINE / OFFLINE
    scanned_image_path: Optional[str] = None
    recorded_by: Optional[str] = None
    remarks: Optional[str] = None
    total_enrolled: int = 0
    total_present: int = 0
    total_absent: int = 0
    records: List[AttendanceRecordDTO] = field(default_factory=list)
    created_at: Optional[str] = None


@dataclass
class BatchAttendanceMatrixRowDTO:
    """A row in the unified batch attendance matrix spreadsheet."""
    student_id: int
    candidate_number: Optional[str]
    student_name: str
    mobile_number: Optional[str]
    admission_date: Optional[str]
    pending_fees: float = 0.0
    # Map of date_str (YYYY-MM-DD) -> 'P' | 'A' | '—'
    date_marks: Dict[str, str] = field(default_factory=dict)
    total_present: int = 0
    total_absent: int = 0
    total_sessions: int = 0
    attendance_percentage: float = 0.0
    health_status: str = "EXCELLENT"  # EXCELLENT, GOOD, AVERAGE, CRITICAL


@dataclass
class BatchAttendanceMatrixDTO:
    """Unified attendance spreadsheet for a batch across all marked dates."""
    batch_id: int
    batch_name: str
    batch_timing: str
    course_name: str
    session_dates: List[str] = field(default_factory=list)  # Sorted list of YYYY-MM-DD
    rows: List[BatchAttendanceMatrixRowDTO] = field(default_factory=list)
    overall_attendance_rate: float = 0.0


@dataclass
class StudentAttendanceHealthDTO:
    """Overall attendance health metrics for a student profile."""
    student_id: int
    student_name: str
    total_sessions_conducted: int = 0
    total_present: int = 0
    total_absent: int = 0
    attendance_percentage: float = 0.0
    health_status: str = "EXCELLENT"  # EXCELLENT, GOOD, AVERAGE, CRITICAL
    health_color: str = "#059669"
    health_bg_color: str = "#ECFDF5"
    recent_history: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class OfflineFormatConfigDTO:
    """Configuration options for generating the fixed Excel attendance format."""
    batch_id: int
    include_student_name: bool = True
    include_admission_date: bool = True
    include_pending_fees: bool = True
    include_batch_details: bool = True
    include_course_details: bool = True
    include_contact_number: bool = True
    blank_session_columns: int = 15  # Number of date/tick columns (e.g. 15 or 30 days)
    session_date: Optional[str] = None


@dataclass
class OCRScanItemDTO:
    """Result of scanning an individual student's mark from the physical sheet."""
    student_id: int
    student_name: str
    candidate_number: Optional[str]
    recognized_status: str  # PRESENT or ABSENT
    confidence: float       # 0.0 to 1.0
    is_uncertain: bool = False
    raw_mark_ratio: float = 0.0


@dataclass
class OCRScanResultDTO:
    """Complete results from processing an uploaded attendance sheet image."""
    batch_id: int
    batch_name: str
    detected_date: str
    image_path: str
    items: List[OCRScanItemDTO] = field(default_factory=list)
    total_detected: int = 0
    total_present: int = 0
    total_absent: int = 0
    confidence_avg: float = 1.0
