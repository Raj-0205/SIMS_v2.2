# modules/attendance/controller.py

from pathlib import Path
from typing import Any, Dict, List, Optional

from modules.attendance.dto import (
    AttendanceSessionDTO,
    BatchAttendanceMatrixDTO,
    BatchStudentDTO,
    OCRScanResultDTO,
    OfflineFormatConfigDTO,
    StudentAttendanceHealthDTO,
)
from modules.attendance.service import AttendanceService


class AttendanceController:
    """
    Controller coordinating attendance operations, batch matrices, exports,
    and optical mark recognition scans between Flet UI views and backend services.
    """

    def __init__(self, service: Optional[AttendanceService] = None):
        self.service = service or AttendanceService()

    def get_batches(self) -> List[Dict[str, Any]]:
        """Retrieves list of active batches for selection dropdown."""
        return self.service.get_batches_list()

    def get_enrolled_students(self, batch_id: int) -> List[BatchStudentDTO]:
        """Retrieves all active students enrolled in a batch."""
        return self.service.get_enrolled_students(batch_id)

    def get_session(self, batch_id: int, session_date: str) -> Optional[AttendanceSessionDTO]:
        """Retrieves an existing session for a batch and date."""
        return self.service.get_session(batch_id, session_date)

    def record_online_attendance(
        self,
        batch_id: int,
        session_date: str,
        student_marks: List[Dict[str, Any]],
        recorded_by: Optional[str] = "admin",
        remarks: Optional[str] = None,
    ) -> AttendanceSessionDTO:
        """Saves attendance marked via interactive toggle switches."""
        return self.service.record_online_attendance(
            batch_id=batch_id,
            session_date=session_date,
            student_marks=student_marks,
            recorded_by=recorded_by,
            remarks=remarks,
        )

    def generate_offline_format(self, config: OfflineFormatConfigDTO) -> str:
        """Generates a fixed printable attendance format in Excel (.xlsx)."""
        path = self.service.generate_offline_format_excel(config)
        return str(path)

    def process_offline_image(
        self,
        image_path: str | Path,
        batch_id: int,
        session_date: Optional[str] = None,
    ) -> OCRScanResultDTO:
        """Executes optical mark scan on an uploaded physical attendance sheet."""
        return self.service.process_offline_image(image_path, batch_id, session_date)

    def commit_offline_attendance(
        self,
        batch_id: int,
        session_date: str,
        student_marks: List[Dict[str, Any]],
        scanned_image_path: Optional[str] = None,
        recorded_by: Optional[str] = "admin",
        remarks: Optional[str] = None,
    ) -> AttendanceSessionDTO:
        """Commits verified offline OCR attendance records to database."""
        return self.service.commit_offline_attendance(
            batch_id=batch_id,
            session_date=session_date,
            student_marks=student_marks,
            scanned_image_path=scanned_image_path,
            recorded_by=recorded_by,
            remarks=remarks,
        )

    def get_batch_matrix(self, batch_id: int) -> BatchAttendanceMatrixDTO:
        """Retrieves the full multi-session matrix spreadsheet for a batch."""
        return self.service.get_batch_matrix(batch_id)

    def export_matrix_excel(self, batch_id: int) -> str:
        """Exports batch attendance matrix to Microsoft Excel (.xlsx)."""
        path = self.service.export_matrix_excel(batch_id)
        return str(path)

    def export_matrix_pdf(self, batch_id: int) -> str:
        """Exports batch attendance matrix to watermarked PDF."""
        path = self.service.export_matrix_pdf(batch_id)
        return str(path)

    def get_student_attendance_health(self, student_id: int) -> StudentAttendanceHealthDTO:
        """Computes aggregate attendance health and recent history for student profile."""
        return self.service.get_student_attendance_health(student_id)
