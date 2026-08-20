# modules/admission/repository.py

from __future__ import annotations
from typing import Any, Optional

from core.database.repository import BaseRepository

__all__ = ["AdmissionRepository"]


class AdmissionRepository(BaseRepository):
    """
    Handles all database interactions for the Admission entity.
    STRICT RULE: Pure SQL execution. No business logic.
    """

    def has_admission_in_state(self, student_id: int, status: str) -> bool:
        """
        Checks if the student already has an admission record in the specified status.
        Used to enforce the 'State-Restricted Multiple Admissions' policy.
        """
        query = "SELECT 1 FROM admissions WHERE student_id = ? AND status = ? LIMIT 1;"
        return self.exists(query, (student_id, status))

    def get_next_sequence_for_year(self, year: int) -> int:
        """
        Finds the highest candidate sequence for the given calendar year and returns the next sequence number.
        Must be executed within an active transaction for concurrency safety.
        """
        sql = """
            SELECT COALESCE(MAX(candidate_sequence), 0) + 1 AS next_seq
            FROM admissions
            WHERE candidate_year = ?;
        """
        row = self.execute_fetchone(sql, (year,))
        return int(row["next_seq"]) if row and row["next_seq"] is not None else 1

    def insert(self, admission_data: dict[str, Any]) -> int:
        """
        Inserts a new admission record with candidate year and sequential number.
        Returns the new Admission ID (Primary Key).
        """
        query = """
            INSERT INTO admissions (student_id, status, candidate_year, candidate_sequence)
            VALUES (?, ?, ?, ?);
        """
        params = (
            admission_data["student_id"],
            admission_data["status"],
            admission_data.get("candidate_year"),
            admission_data.get("candidate_sequence"),
        )
        return self.execute_insert(query, params)

    def get_by_id(self, admission_id: int) -> Optional[dict[str, Any]]:
        """Retrieves an admission record by primary key."""
        sql = """
            SELECT id, student_id, status, created_at, candidate_year, candidate_sequence
            FROM admissions
            WHERE id = ?;
        """
        return self.execute_fetchone(sql, (admission_id,))

    def get_by_candidate_number(self, year: int, sequence: int) -> Optional[dict[str, Any]]:
        """Retrieves an admission record by its business candidate number."""
        sql = """
            SELECT id, student_id, status, created_at, candidate_year, candidate_sequence
            FROM admissions
            WHERE candidate_year = ? AND candidate_sequence = ?;
        """
        return self.execute_fetchone(sql, (year, sequence))
