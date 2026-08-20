# modules/admission_course/repository.py

from __future__ import annotations
from typing import TypedDict, cast
from core.database.repository import BaseRepository

__all__ = ["AdmissionCourseRepository", "AdmissionCourseRow"]


class AdmissionCourseRow(TypedDict):
    admission_id: int
    course_id: int


class AdmissionCourseRepository(BaseRepository):
    """Handles the M2M bridge table operations."""

    def link_course(self, admission_id: int, course_id: int) -> None:
        """Links a course to an admission."""
        sql = "INSERT INTO admission_courses (admission_id, course_id) VALUES (?, ?);"
        self.execute_insert(sql, (admission_id, course_id))

    def unlink_course(self, admission_id: int, course_id: int) -> int:
        """Removes a course from an admission."""
        sql = "DELETE FROM admission_courses WHERE admission_id = ? AND course_id = ?;"
        return self.execute(sql, (admission_id, course_id))

    def get_courses_for_admission(self, admission_id: int) -> list[AdmissionCourseRow]:
        """Fetches all courses attached to an admission."""
        sql = "SELECT admission_id, course_id FROM admission_courses WHERE admission_id = ?;"
        return cast(list[AdmissionCourseRow], self.execute_fetchall(sql, (admission_id,)))
