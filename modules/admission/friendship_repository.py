# modules/admission/friendship_repository.py

from __future__ import annotations
from typing import Any, Optional
from core.database.repository import BaseRepository

__all__ = ["FriendshipRepository"]


class FriendshipRepository(BaseRepository):
    """Persistence for student peer suggestions and confirmed friendships."""

    def get_suggested_friends(
        self,
        village: str,
        exclude_student_id: int = 0,
        gender: Optional[str] = None,
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        """
        Suggests recent students from the same village with same-gender priority.
        Ordered by: same gender first, then recent admissions first.
        Capped at limit (max 3).
        """
        if not village or not village.strip():
            return []

        clean_village = village.strip()
        clean_gender = (gender or "").strip().upper()

        sql = """
            SELECT s.id, s.first_name, s.last_name, s.mobile_number, COALESCE(s.gender, a.gender) AS gender, COALESCE(s.village, a.village) AS village,
                   a.id AS admission_id, a.candidate_year, a.candidate_sequence, c.name AS course_name
            FROM students s
            LEFT JOIN admissions a ON a.student_id = s.id
            LEFT JOIN admission_courses ac ON ac.admission_id = a.id
            LEFT JOIN courses c ON c.id = ac.course_id
            WHERE (LOWER(TRIM(COALESCE(s.village, ''))) = LOWER(?) OR LOWER(TRIM(COALESCE(a.village, ''))) = LOWER(?))
              AND s.id <> ?
            GROUP BY s.id
            ORDER BY 
                (CASE WHEN UPPER(COALESCE(s.gender, a.gender, '')) = UPPER(?) THEN 1 ELSE 2 END) ASC,
                COALESCE(a.created_at, s.created_at) DESC
            LIMIT ?;
        """
        params = (clean_village, clean_village, exclude_student_id, clean_gender, limit)
        return self.execute_fetchall(sql, params)

    def add_friendship(self, student_id: int, friend_student_id: int, admission_id: Optional[int] = None) -> int:
        """
        Records an explicit confirmed friendship between two students.
        Enforces canonical pair ordering (min, max) and avoids self or duplicate pairs.
        """
        if student_id == friend_student_id:
            return 0

        p1, p2 = min(student_id, friend_student_id), max(student_id, friend_student_id)

        sql = """
            INSERT OR IGNORE INTO student_friendships (student_id, friend_student_id, admission_id, is_active)
            VALUES (?, ?, ?, 1);
        """
        return self.execute_insert(sql, (p1, p2, admission_id))

    def get_confirmed_friends(self, student_id: int) -> list[dict[str, Any]]:
        sql = """
            SELECT s.id, s.first_name, s.last_name, s.mobile_number, s.gender, s.village, sf.created_at as friendship_date
            FROM student_friendships sf
            JOIN students s ON s.id = (CASE WHEN sf.student_id = ? THEN sf.friend_student_id ELSE sf.student_id END)
            WHERE (sf.student_id = ? OR sf.friend_student_id = ?)
              AND sf.is_active = 1
            ORDER BY sf.created_at DESC;
        """
        return self.execute_fetchall(sql, (student_id, student_id, student_id))

    def remove_friendship(self, student_id: int, friend_student_id: int) -> int:
        p1, p2 = min(student_id, friend_student_id), max(student_id, friend_student_id)
        sql = "UPDATE student_friendships SET is_active = 0 WHERE student_id = ? AND friend_student_id = ?;"
        return self.execute(sql, (p1, p2))

    def get_friends_for_admission(self, admission_id: int) -> list[dict[str, Any]]:
        sql = """
            SELECT s.id, s.first_name, s.last_name, s.mobile_number, s.village
            FROM student_friendships sf
            JOIN students s ON s.id = sf.friend_student_id
            WHERE sf.admission_id = ? AND sf.is_active = 1
            ORDER BY sf.created_at ASC;
        """
        return self.execute_fetchall(sql, (admission_id,))
