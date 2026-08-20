# modules/student/service.py

from __future__ import annotations
import re
from typing import Optional

from core.logger.service import LogService
from core.service.base import BaseService
from core.exceptions import ValidationError, ConflictError, ServiceError
from modules.student.repository import StudentRepository
from modules.student.mapper import StudentMapper, StudentSearchMapper
from modules.student.dto import (
    StudentDTO,
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

    def _sanitize_string(self, value: Optional[str]) -> str:
        return str(value).strip() if value else ""

    def _validate_names(self, first_name: str, last_name: str) -> tuple[str, str]:
        clean_first = self._sanitize_string(first_name)
        clean_last = self._sanitize_string(last_name)

        if not clean_first:
            raise ValidationError("First name is required and cannot be blank.")
        if not clean_last:
            raise ValidationError("Last name is required and cannot be blank.")
        if len(clean_first) < 2:
            raise ValidationError("First name must be at least 2 characters.")
        if len(clean_last) < 2:
            raise ValidationError("Last name must be at least 2 characters.")

        return clean_first, clean_last

    def _validate_mobile(self, mobile_number: Optional[str]) -> Optional[str]:
        clean_mobile = self._sanitize_string(mobile_number)
        if not clean_mobile:
            return None

        # Normalize by removing hyphens and spaces
        normalized = re.sub(r"[\s\-]", "", clean_mobile)

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
        Creates a new student record.
        HARD BLOCK: Rejects duplicate mobile numbers.
        """
        first_name, last_name = self._validate_names(dto.first_name, dto.last_name)
        mobile_number = self._validate_mobile(dto.mobile_number)
        email = self._validate_email(dto.email)

        data = {
            "first_name": first_name,
            "last_name": last_name,
            "mobile_number": mobile_number,
            "email": email,
        }

        # Atomic Unit of Work
        with self.unit_of_work():
            # 1. Pre-check duplicate mobile number (HARD BLOCK if provided)
            if mobile_number:
                existing_mobile = self.repository.get_by_mobile(mobile_number)
                if existing_mobile:
                    LogService.warning(
                        f"Student creation rejected: Duplicate mobile '{mobile_number}'.",
                        context=self.__class__.__name__,
                    )
                    raise ConflictError(
                        f"A student with mobile number '{mobile_number}' already exists."
                    )

            # 2. Pre-check duplicate email (if provided)
            if email:
                existing_email = self.repository.get_by_email(email)
                if existing_email:
                    raise ConflictError(f"A student with email '{email}' already exists.")

            # 3. Insert Record
            student_id = self.repository.insert(data)
            if not student_id or student_id <= 0:
                raise ServiceError("Failed to insert student record.")

            LogService.info(
                f"Student created successfully with ID: {student_id}",
                context=self.__class__.__name__,
            )
            return student_id

    def update_student(self, dto: StudentUpdateDTO) -> None:
        """
        Updates an existing student record.
        HARD BLOCK: Rejects duplicate mobile numbers assigned to other students.
        """
        if not dto.id or dto.id <= 0:
            raise ValidationError("Valid student ID is required for update.")

        first_name, last_name = self._validate_names(dto.first_name, dto.last_name)
        mobile_number = self._validate_mobile(dto.mobile_number)
        email = self._validate_email(dto.email)

        data = {
            "first_name": first_name,
            "last_name": last_name,
            "mobile_number": mobile_number,
            "email": email,
        }

        # Atomic Unit of Work
        with self.unit_of_work():
            # 1. Verify existence
            existing_student = self.repository.get_by_id(dto.id)
            if not existing_student:
                raise ValidationError(f"Student with ID {dto.id} does not exist.")

            # 2. Check duplicate mobile against OTHER students (if provided)
            if mobile_number:
                mobile_owner = self.repository.get_by_mobile(mobile_number)
                if mobile_owner and int(mobile_owner["id"]) != int(dto.id):
                    LogService.warning(
                        f"Student update rejected: Mobile '{mobile_number}' is owned by student ID {mobile_owner['id']}.",
                        context=self.__class__.__name__,
                    )
                    raise ConflictError(
                        f"Mobile number '{mobile_number}' is already registered to another student."
                    )

            # 3. Check duplicate email against OTHER students (if provided)
            if email:
                email_owner = self.repository.get_by_email(email)
                if email_owner and int(email_owner["id"]) != int(dto.id):
                    raise ConflictError(
                        f"Email address '{email}' is already registered to another student."
                    )

            # 4. Execute Update
            rows_affected = self.repository.update(dto.id, data)
            if rows_affected <= 0:
                raise ServiceError(f"Failed to update student record ID {dto.id}.")

            LogService.info(
                f"Student ID {dto.id} updated successfully.",
                context=self.__class__.__name__,
            )

    def delete_student(self, student_id: int) -> None:
        """
        Deletes a student profile.
        ERP Business Rule: Restrict deletion if student has active or historical admissions.
        """
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
        """Retrieves full student details by ID."""
        if not student_id or student_id <= 0:
            raise ValidationError("A valid student ID is required.")

        with self.unit_of_work():
            row = self.repository.get_by_id(student_id)
            if not row:
                raise ValidationError(f"Student with ID {student_id} not found.")
            return StudentMapper.to_dto(row)

    def get_student_workspace(self, student_id: int) -> StudentWorkspaceDTO:
        """
        Aggregates complete Student Workspace data:
        - Master Student profile
        - All linked admissions (Student != Admission)
        - Chronological history timeline
        """
        student = self.get_student(student_id)

        with self.unit_of_work():
            # 1. Fetch Admissions
            admission_rows = self.repository.get_student_admissions(student_id)
            admissions = [StudentMapper.to_admission_dto(r) for r in admission_rows]

            # 2. Build Chronological Timeline Events
            timeline: list[StudentTimelineItemDTO] = []

            # Registration Event
            if student.created_at:
                timeline.append(
                    StudentTimelineItemDTO(
                        timestamp=student.created_at,
                        title="Student Profile Registered",
                        description=f"Student record created for {student.display_name}.",
                        event_type="REGISTRATION",
                    )
                )

            # Admission Events
            for adm in admissions:
                course_text = f"Course: {adm.course_name} ({adm.course_code})" if adm.course_name else "Course Assignment Pending"
                timeline.append(
                    StudentTimelineItemDTO(
                        timestamp=adm.admission_date or "N/A",
                        title=f"Admission #{adm.admission_id} - {adm.status}",
                        description=f"Enrolled in {course_text}. Status: {adm.status}.",
                        event_type="ADMISSION",
                    )
                )

            # Sort timeline newest first
            timeline.sort(key=lambda t: t.timestamp, reverse=True)

            return StudentWorkspaceDTO(
                student=student,
                admissions=admissions,
                timeline=timeline,
            )

    def list_students(self, limit: int = 50, offset: int = 0) -> tuple[list[StudentDTO], int]:
        """Fetches a paginated list of students along with total count."""
        safe_limit = max(1, min(limit, 100))
        safe_offset = max(0, offset)

        with self.unit_of_work():
            rows = self.repository.get_all_paged(safe_limit, safe_offset)
            total = self.repository.count_all()
            return [StudentMapper.to_dto(r) for r in rows], total

    def search_students_paged(
        self, query: str, limit: int = 50, offset: int = 0
    ) -> tuple[list[StudentDTO], int]:
        """
        Searches students across fields with pagination and total count.
        """
        clean_query = self._sanitize_string(query)
        safe_limit = max(1, min(limit, 100))
        safe_offset = max(0, offset)

        with self.unit_of_work():
            if not clean_query:
                rows = self.repository.get_all_paged(safe_limit, safe_offset)
                total = self.repository.count_all()
            else:
                rows = self.repository.search_paged(clean_query, safe_limit, safe_offset)
                total = self.repository.count_search(clean_query)

            return [StudentMapper.to_dto(r) for r in rows], total

    def count_students(self) -> int:
        """Returns total active student count."""
        with self.unit_of_work():
            return self.repository.count_all()

    def search_students(self, query: str, limit: int = 25) -> list[StudentSearchResultDTO]:
        """
        Backward-compatible search API consumed by AdmissionForm and SearchDialog.
        Enforces minimum 2-character rule.
        """
        clean_query = self._sanitize_string(query)
        if not clean_query or len(clean_query) < 2:
            return []

        with self.unit_of_work():
            rows = self.repository.search(clean_query, limit)
            return [StudentSearchMapper.to_result_dto(row) for row in rows]


class StudentSearchService(StudentService):
    """Backward-compatible alias for existing search service references."""
    pass
