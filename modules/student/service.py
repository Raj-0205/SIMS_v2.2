# modules/student/service.py

from __future__ import annotations
from datetime import datetime
from pathlib import Path
import re
from typing import Optional

from core.logger.service import LogService
from core.service.base import BaseService
from core.exceptions import ValidationError, ConflictError, ServiceError
from infrastructure.excel import ExcelExporter
from infrastructure.pdf import PDFExporter
from shared.utils import format_title_case, normalize_indian_mobile
from modules.student.repository import StudentRepository
from modules.admission.friendship_repository import FriendshipRepository
from modules.admission.activity_log_repository import ActivityLogRepository
from modules.student.mapper import StudentMapper, StudentSearchMapper
from modules.student.dto import (
    StudentDTO,
    StudentFilterDTO,
    StudentCreateDTO,
    StudentUpdateDTO,
    StudentSearchResultDTO,
    StudentAdmissionDTO,
    StudentTimelineItemDTO,
    StudentWorkspaceDTO,
)

__all__ = ["StudentService", "StudentSearchService"]


class StudentService(BaseService):
    """
    Business Logic Layer for Student operations.
    Enforces business validation, mobile uniqueness, workspace aggregations, and transaction boundaries.
    """

    _EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    _MOBILE_REGEX = re.compile(r"^\+?[0-9]{10,15}$")

    def __init__(self) -> None:
        self.repository = StudentRepository()
        self.friendship_repo = FriendshipRepository()
        self.activity_log_repo = ActivityLogRepository()

    def _sanitize_string(self, value: Optional[str]) -> str:
        return str(value).strip() if value else ""

    def _validate_names(self, first_name: str, last_name: str) -> tuple[str, str]:
        clean_first = format_title_case(first_name)
        clean_last = format_title_case(last_name)

        if not clean_first:
            raise ValidationError("First name is required and cannot be blank.")
        if not clean_last:
            raise ValidationError("Last name is required and cannot be blank.")
        if len(clean_first) < 2:
            raise ValidationError("First name must be at least 2 characters.")
        if len(clean_last) < 2:
            raise ValidationError("Last name must be at least 2 characters.")

        return clean_first, clean_last

    def _validate_mobile(self, mobile_number: Optional[str]) -> str:
        clean_mobile = self._sanitize_string(mobile_number)
        if not clean_mobile:
            raise ValidationError("Mobile number is required and cannot be blank.")

        normalized = normalize_indian_mobile(clean_mobile)
        if not self._MOBILE_REGEX.match(normalized):
            raise ValidationError("Invalid mobile number format. Must contain 10-15 digits.")

        return normalized

    def _validate_email(self, email: Optional[str]) -> Optional[str]:
        clean_email = self._sanitize_string(email)
        if not clean_email:
            return None

        if not self._EMAIL_REGEX.match(clean_email):
            raise ValidationError("Invalid email address format.")

        return clean_email.lower()

    def create_student(self, dto: StudentCreateDTO) -> int:
        """
        Creates a new student master record.
        HARD BLOCK: Rejects duplicate mobile numbers.
        """
        first_name, last_name = self._validate_names(dto.first_name, dto.last_name)
        mobile_number = self._validate_mobile(dto.mobile_number)
        email = self._validate_email(dto.email)

        data = {
            "first_name": first_name,
            "middle_name": format_title_case(dto.middle_name) if dto.middle_name else None,
            "last_name": last_name,
            "mother_name": format_title_case(dto.mother_name) if dto.mother_name else None,
            "dob": self._sanitize_string(dto.dob) or None,
            "gender": self._sanitize_string(dto.gender).upper() or None,
            "aadhaar_number": self._sanitize_string(dto.aadhaar_number) or None,
            "parent_guardian_name": format_title_case(dto.parent_guardian_name) if dto.parent_guardian_name else None,
            "village": format_title_case(dto.village) if dto.village else None,
            "address": format_title_case(dto.address) if dto.address else None,
            "qualification": format_title_case(dto.qualification) if dto.qualification else None,
            "blood_group": self._sanitize_string(dto.blood_group).upper() or None,
            "photo_path": dto.photo_path,
            "signature_path": dto.signature_path,
            "email": email,
            "mobile_number": mobile_number,
        }

        with self.unit_of_work():
            existing_mobile = self.repository.get_by_mobile(mobile_number)
            if existing_mobile:
                LogService.warning(
                    f"Student creation rejected: Duplicate mobile '{mobile_number}'.",
                    context=self.__class__.__name__,
                )
                raise ConflictError(
                    f"A student with mobile number '{mobile_number}' already exists."
                )

            if email:
                existing_email = self.repository.get_by_email(email)
                if existing_email:
                    raise ConflictError(f"A student with email '{email}' already exists.")

            student_id = self.repository.insert(data)
            if not student_id or student_id <= 0:
                raise ServiceError("Failed to insert student record.")

            self.activity_log_repo.insert(
                entity_type="STUDENT",
                entity_id=student_id,
                action="REGISTERED",
                actor_name="SYSTEM",
                details=f"Student profile created for {first_name} {last_name}."
            )

            LogService.info(
                f"Student created successfully with ID: {student_id}",
                context=self.__class__.__name__,
            )
            return student_id

    def update_student(self, dto: StudentUpdateDTO) -> None:
        """
        Updates an existing student master record completely.
        HARD BLOCK: Rejects duplicate mobile numbers assigned to other students.
        """
        if not dto.id or dto.id <= 0:
            raise ValidationError("Valid student ID is required for update.")

        first_name, last_name = self._validate_names(dto.first_name, dto.last_name)
        mobile_number = self._validate_mobile(dto.mobile_number)
        email = self._validate_email(dto.email)

        data = {
            "first_name": first_name,
            "middle_name": format_title_case(dto.middle_name) if dto.middle_name else None,
            "last_name": last_name,
            "mother_name": format_title_case(dto.mother_name) if dto.mother_name else None,
            "dob": self._sanitize_string(dto.dob) or None,
            "gender": self._sanitize_string(dto.gender).upper() or None,
            "aadhaar_number": self._sanitize_string(dto.aadhaar_number) or None,
            "parent_guardian_name": format_title_case(dto.parent_guardian_name) if dto.parent_guardian_name else None,
            "village": format_title_case(dto.village) if dto.village else None,
            "address": format_title_case(dto.address) if dto.address else None,
            "qualification": format_title_case(dto.qualification) if dto.qualification else None,
            "blood_group": self._sanitize_string(dto.blood_group).upper() or None,
            "photo_path": dto.photo_path,
            "signature_path": dto.signature_path,
            "email": email,
            "mobile_number": mobile_number,
        }

        with self.unit_of_work():
            existing_student = self.repository.get_by_id(dto.id)
            if not existing_student:
                raise ValidationError(f"Student with ID {dto.id} does not exist.")

            mobile_owner = self.repository.get_by_mobile(mobile_number)
            if mobile_owner and int(mobile_owner["id"]) != int(dto.id):
                LogService.warning(
                    f"Student update rejected: Mobile '{mobile_number}' owned by ID {mobile_owner['id']}.",
                    context=self.__class__.__name__,
                )
                raise ConflictError(
                    f"Mobile number '{mobile_number}' is already registered to another student."
                )

            if email:
                email_owner = self.repository.get_by_email(email)
                if email_owner and int(email_owner["id"]) != int(dto.id):
                    raise ConflictError(
                        f"Email address '{email}' is already registered to another student."
                    )

            rows_affected = self.repository.update(dto.id, data)
            if rows_affected <= 0:
                raise ServiceError(f"Failed to update student record ID {dto.id}.")

            self.activity_log_repo.insert(
                entity_type="STUDENT",
                entity_id=dto.id,
                action="PROFILE_UPDATED",
                actor_name="ADMIN",
                details=f"Master profile updated for {first_name} {last_name}."
            )

            LogService.info(
                f"Student ID {dto.id} updated successfully.",
                context=self.__class__.__name__,
            )

    def add_student_note(self, student_id: int, note_text: str, actor_name: str = "ADMIN") -> None:
        """Adds an internal note for a student enclosed in unit_of_work."""
        if not student_id or student_id <= 0:
            raise ValidationError("Valid student ID is required.")
        clean_note = self._sanitize_string(note_text)
        if not clean_note:
            raise ValidationError("Note content cannot be empty.")

        with self.unit_of_work():
            self.activity_log_repo.insert(
                entity_type="STUDENT",
                entity_id=student_id,
                action="NOTE_ADDED",
                actor_name=actor_name,
                details=clean_note,
            )

    def get_student_notes(self, student_id: int) -> list[dict[str, Any]]:
        """Fetches internal notes for a student enclosed in unit_of_work."""
        with self.unit_of_work():
            return self.activity_log_repo.get_logs_for_entity("STUDENT", student_id)

    def add_student_friend(self, student_id: int, friend_student_id: int, admission_id: Optional[int] = None) -> None:
        """Adds a confirmed village/peer friend connection within unit_of_work."""
        if student_id == friend_student_id:
            raise ValidationError("Cannot add student as their own friend.")

        with self.unit_of_work():
            self.friendship_repo.add_friendship(student_id, friend_student_id, admission_id)
            self.activity_log_repo.insert(
                entity_type="STUDENT",
                entity_id=student_id,
                action="FRIEND_ADDED",
                actor_name="ADMIN",
                details=f"Added friend student ID #{friend_student_id}.",
            )

    def remove_student_friend(self, student_id: int, friend_student_id: int) -> None:
        """Removes a friend connection within unit_of_work."""
        with self.unit_of_work():
            self.friendship_repo.remove_friendship(student_id, friend_student_id)
            self.activity_log_repo.insert(
                entity_type="STUDENT",
                entity_id=student_id,
                action="FRIEND_REMOVED",
                actor_name="ADMIN",
                details=f"Removed friend student ID #{friend_student_id}.",
            )

    def upload_student_document(
        self,
        student_id: int,
        doc_type: str,
        file_bytes: bytes,
        original_filename: str,
    ) -> str:
        """
        Validates and saves a student document (Photo or Signature).
        Strictly enforces 100 KB limit and allowed extensions (.jpg, .jpeg, .png).
        """
        if not student_id or student_id <= 0:
            raise ValidationError("Valid student ID is required for document upload.")

        if not file_bytes:
            raise ValidationError("No file content provided.")

        max_bytes = 100 * 1024  # 100 KB
        if len(file_bytes) > max_bytes:
            size_kb = len(file_bytes) / 1024
            raise ValidationError(
                f"File size ({size_kb:.1f} KB) exceeds the maximum limit of 100 KB. "
                "Please compress the image before uploading."
            )

        ext = Path(original_filename).suffix.lower()
        if ext not in (".jpg", ".jpeg", ".png"):
            raise ValidationError("Invalid file format. Only JPG, JPEG, and PNG images are allowed.")

        doc_kind = "photos" if doc_type.lower() == "photo" else "signatures"
        upload_dir = Path("uploads") / doc_kind
        upload_dir.mkdir(parents=True, exist_ok=True)

        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_filename = f"{doc_type.lower()}_{student_id}_{timestamp_str}{ext}"
        target_path = upload_dir / target_filename

        with open(target_path, "wb") as f:
            f.write(file_bytes)

        rel_path = str(target_path)

        with self.unit_of_work():
            self.repository.update_document_path(student_id, doc_type, rel_path)
            self.activity_log_repo.insert(
                entity_type="STUDENT",
                entity_id=student_id,
                action="DOCUMENT_UPLOADED",
                actor_name="ADMIN",
                details=f"Uploaded {doc_type} ({len(file_bytes)/1024:.1f} KB): {target_filename}",
            )

        return rel_path

    def delete_student_document(self, student_id: int, doc_type: str) -> None:
        """Clears a document path on the student record."""
        with self.unit_of_work():
            self.repository.update_document_path(student_id, doc_type, None)
            self.activity_log_repo.insert(
                entity_type="STUDENT",
                entity_id=student_id,
                action="DOCUMENT_REMOVED",
                actor_name="ADMIN",
                details=f"Removed {doc_type} document.",
            )

    def delete_student(self, student_id: int) -> None:
        if not student_id or student_id <= 0:
            raise ValidationError("A valid student ID is required for deletion.")

        with self.unit_of_work():
            existing = self.repository.get_by_id(student_id)
            if not existing:
                raise ValidationError(f"Student ID {student_id} not found.")

            if self.repository.has_admissions(student_id):
                raise ConflictError(
                    "Cannot delete student profile with linked admission records. "
                    "ERP audit policy preserves historical admission data."
                )

            self.repository.delete(student_id)
            LogService.info(
                f"Student ID {student_id} deleted successfully.",
                context=self.__class__.__name__,
            )

    def get_student(self, student_id: int) -> StudentDTO:
        if not student_id or student_id <= 0:
            raise ValidationError("A valid student ID is required.")

        with self.unit_of_work():
            row = self.repository.get_by_id(student_id)
            if not row:
                raise ValidationError(f"Student with ID {student_id} not found.")
            return StudentMapper.to_dto(row)

    def get_student_workspace(self, student_id: int) -> StudentWorkspaceDTO:
        student = self.get_student(student_id)

        with self.unit_of_work():
            admission_rows = self.repository.get_student_admissions(student_id)
            admissions = []
            all_payments = []
            for r in admission_rows:
                adm_id = int(r["admission_id"])
                p_rows = self.repository.execute_fetchall(
                    "SELECT * FROM payments WHERE admission_id = ? ORDER BY installment_number ASC, id ASC;",
                    (adm_id,)
                )
                all_payments.extend(p_rows)
                inst_dict: dict[int, float] = {}
                tot_p = 0.0
                for p in p_rows:
                    inum = int(p.get("installment_number") or 1)
                    amt = float(p.get("amount") or 0.0)
                    inst_dict[inum] = inst_dict.get(inum, 0.0) + amt
                    tot_p += amt
                admissions.append(StudentMapper.to_admission_dto(r, installments=inst_dict, total_paid=tot_p))

            rcp_rows = self.repository.execute_fetchall(
                """
                SELECT r.*, p.installment_number, p.payment_mode, a.candidate_year, a.candidate_sequence, c.name AS course_name
                FROM receipts r
                JOIN payments p ON p.id = r.payment_id
                JOIN admissions a ON a.id = r.admission_id
                LEFT JOIN admission_courses ac ON ac.admission_id = a.id
                LEFT JOIN courses c ON c.id = ac.course_id
                WHERE r.student_id = ?
                ORDER BY r.id DESC;
                """,
                (student_id,)
            )

            friend_rows = self.friendship_repo.get_confirmed_friends(student_id)
            note_rows = self.activity_log_repo.get_logs_for_entity("STUDENT", student_id)

            timeline: list[StudentTimelineItemDTO] = []

            if student.created_at:
                timeline.append(
                    StudentTimelineItemDTO(
                        timestamp=student.created_at,
                        title="Student Profile Registered",
                        description=f"Student record created for {student.display_name}.",
                        event_type="REGISTRATION",
                    )
                )

            for adm in admissions:
                course_text = f"Course: {adm.course_name} ({adm.course_code})" if adm.course_name else "Course Assignment Pending"
                adm_display = adm.admission_number if getattr(adm, "admission_number", None) else f"#{adm.admission_id}"
                timeline.append(
                    StudentTimelineItemDTO(
                        timestamp=adm.admission_date or "N/A",
                        title=f"Admission {adm_display} - {adm.status}",
                        description=f"Enrolled in {course_text}. Agreed Fee: ₹{adm.agreed_fee:,.2f}, Paid: ₹{adm.total_paid:,.2f}.",
                        event_type="ADMISSION",
                    )
                )

            for p in all_payments:
                timeline.append(
                    StudentTimelineItemDTO(
                        timestamp=str(p.get("created_at") or ""),
                        title=f"Payment Received: ₹{float(p.get('amount') or 0.0):,.2f}",
                        description=f"Installment #{p.get('installment_number')} via {p.get('payment_mode')}. Collector: {p.get('collector_name') or 'N/A'}.",
                        event_type="PAYMENT",
                    )
                )

            for log in note_rows:
                if log.get("action") == "NOTE_ADDED":
                    timeline.append(
                        StudentTimelineItemDTO(
                            timestamp=str(log.get("created_at") or ""),
                            title=f"Internal Note ({log.get('actor_name') or 'Admin'})",
                            description=str(log.get("details") or ""),
                            event_type="NOTE",
                        )
                    )

            timeline.sort(key=lambda t: t.timestamp, reverse=True)

            return StudentWorkspaceDTO(
                student=student,
                admissions=admissions,
                timeline=timeline,
                payments=all_payments,
                receipts=rcp_rows,
                friends=friend_rows,
                notes=note_rows,
            )

    def filter_students(self, filter_dto: StudentFilterDTO) -> tuple[list[StudentDTO], int]:
        clean_query = self._sanitize_string(filter_dto.query)
        safe_limit = max(1, min(filter_dto.limit, 200))
        safe_offset = max(0, filter_dto.offset)

        resolved_sort_keys: list[tuple[str, str]] | None = None
        if filter_dto.sort_keys:
            resolved_sort_keys = list(filter_dto.sort_keys)

        with self.unit_of_work():
            rows = self.repository.filter_paged(
                query=clean_query if clean_query else None,
                course_id=filter_dto.course_id,
                status=filter_dto.status,
                year=filter_dto.year,
                month=filter_dto.month,
                sort_by=filter_dto.sort_by,
                sort_dir=filter_dto.sort_dir,
                sort_keys=resolved_sort_keys,
                limit=safe_limit,
                offset=safe_offset,
            )
            total = self.repository.count_filtered(
                query=clean_query if clean_query else None,
                course_id=filter_dto.course_id,
                status=filter_dto.status,
                year=filter_dto.year,
                month=filter_dto.month,
            )
            return [StudentMapper.to_dto(r) for r in rows], total

    def list_students(self, limit: int = 50, offset: int = 0) -> tuple[list[StudentDTO], int]:
        return self.filter_students(StudentFilterDTO(limit=limit, offset=offset))

    def search_students_paged(
        self, query: str, limit: int = 50, offset: int = 0
    ) -> tuple[list[StudentDTO], int]:
        return self.filter_students(StudentFilterDTO(query=query, limit=limit, offset=offset))

    def count_students(self) -> int:
        with self.unit_of_work():
            return self.repository.count_all()

    def export_students_data(self, filter_dto: StudentFilterDTO) -> list[StudentDTO]:
        clean_query = self._sanitize_string(filter_dto.query)

        resolved_sort_keys: list[tuple[str, str]] | None = None
        if filter_dto.sort_keys:
            resolved_sort_keys = list(filter_dto.sort_keys)

        with self.unit_of_work():
            rows = self.repository.get_all_filtered(
                query=clean_query if clean_query else None,
                course_id=filter_dto.course_id,
                status=filter_dto.status,
                year=filter_dto.year,
                month=filter_dto.month,
                sort_by=filter_dto.sort_by,
                sort_dir=filter_dto.sort_dir,
                sort_keys=resolved_sort_keys,
            )
            return [StudentMapper.to_dto(r) for r in rows]

    def export_students_csv(
        self, filter_dto: StudentFilterDTO, target_path: Optional[str | Path] = None
    ) -> Path:
        students = self.export_students_data(filter_dto)
        default_dir = Path("exports/students")
        default_name = f"student_directory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path = Path(target_path) if target_path else default_dir / default_name

        headers = [
            "ID",
            "Admission No",
            "Student Name",
            "Mobile Number",
            "Email",
            "Current Course",
            "Admission Date",
            "Status",
            "Base Fee",
            "Paid Amount",
            "Pending Amount",
        ]

        rows = [
            [
                s.id,
                s.candidate_number or "—",
                s.display_name,
                s.mobile_number or "—",
                s.email or "—",
                s.current_course or "—",
                s.latest_admission_date[:10] if s.latest_admission_date else (s.created_at[:10] if s.created_at else "—"),
                s.status_label,
                s.fee_display,
                s.paid_display,
                s.pending_display,
            ]
            for s in students
        ]

        metadata = {
            "Module": "SIMS v2.2 Student Management System",
            "Export Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Total Records": len(students),
            "Search Query": filter_dto.query or "None",
            "Status Filter": filter_dto.status or "All",
        }

        return ExcelExporter.export_to_csv(
            headers=headers,
            rows=rows,
            output_path=path,
            metadata=metadata,
        )

    def export_students_pdf(
        self, filter_dto: StudentFilterDTO, target_path: Optional[str | Path] = None
    ) -> Path:
        students = self.export_students_data(filter_dto)
        default_dir = Path("exports/students")
        default_name = f"student_directory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        path = Path(target_path) if target_path else default_dir / default_name

        headers = [
            "ID",
            "Adm No",
            "Student Name",
            "Mobile",
            "Course",
            "Date",
            "Status",
            "Base Fee",
            "Paid",
            "Pending",
        ]
        column_widths = [0.8, 1.4, 2.2, 1.4, 2.0, 1.2, 1.2, 1.1, 1.3, 1.3]

        rows = [
            [
                s.id,
                s.candidate_number or "—",
                s.display_name,
                s.mobile_number or "—",
                s.current_course or "—",
                s.latest_admission_date[:10] if s.latest_admission_date else (s.created_at[:10] if s.created_at else "—"),
                s.status_label,
                s.fee_display,
                s.paid_display,
                s.pending_display,
            ]
            for s in students
        ]

        metadata = {
            "Filter Status": filter_dto.status or "All",
            "Sorted By": f"{filter_dto.sort_by} ({filter_dto.sort_dir.upper()})",
        }

        return PDFExporter.export_table_pdf(
            title="SIMS v2.2 — Student Directory Report",
            headers=headers,
            column_widths=column_widths,
            rows=rows,
            output_path=path,
            subtitle=f"Exported on {datetime.now().strftime('%d-%b-%Y %H:%M:%S')}  |  Total Filtered Records: {len(students)}",
            metadata=metadata,
        )

    def search_students(self, query: str, limit: int = 25) -> list[StudentSearchResultDTO]:
        clean_query = self._sanitize_string(query)
        if not clean_query or len(clean_query) < 2:
            return []

        with self.unit_of_work():
            rows = self.repository.search(clean_query, limit)
            return [StudentSearchMapper.to_result_dto(row) for row in rows]


class StudentSearchService(StudentService):
    pass
