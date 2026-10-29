# modules/attendance/repository.py

from typing import Any, Dict, List, Optional
from core.database.repository import BaseRepository
from modules.attendance.constants import AttendanceHealth, HEALTH_BG_COLORS, HEALTH_COLORS
from modules.attendance.dto import (
    AttendanceRecordDTO,
    AttendanceSessionDTO,
    BatchAttendanceMatrixDTO,
    BatchAttendanceMatrixRowDTO,
    BatchStudentDTO,
    StudentAttendanceHealthDTO,
)


class AttendanceRepository(BaseRepository):
    """
    Data access layer for batch attendance sessions, individual student attendance
    records, and matrix spreadsheet aggregations.
    """

    def get_enrolled_students(self, batch_id: int) -> List[BatchStudentDTO]:
        """
        Retrieves all active students enrolled in a specific batch through confirmed,
        registered, or completed admissions.
        """
        sql = """
            SELECT 
                s.id AS student_id,
                a.id AS admission_id,
                COALESCE(
                    (CAST(a.candidate_year AS TEXT) || '-' || printf('%03d', a.candidate_sequence)),
                    printf('ADM-%04d', a.id)
                ) AS candidate_number,
                s.first_name,
                s.last_name,
                (s.first_name || ' ' || s.last_name) AS student_name,
                s.mobile_number,
                s.village,
                s.photo_path,
                c.id AS course_id,
                COALESCE(c.name, '—') AS course_name,
                a.created_at AS admission_date,
                MAX(0.0, (COALESCE(a.agreed_fee, 0.0) - COALESCE(a.discount, 0.0)) - COALESCE((SELECT SUM(amount) FROM payments p WHERE p.admission_id = a.id), 0.0)) AS pending_fees,
                COALESCE((SELECT SUM(amount) FROM payments p WHERE p.admission_id = a.id), 0.0) AS total_paid,
                (COALESCE(a.agreed_fee, 0.0) - COALESCE(a.discount, 0.0)) AS final_fee
            FROM admissions a
            JOIN students s ON s.id = a.student_id
            LEFT JOIN admission_courses ac ON ac.admission_id = a.id
            LEFT JOIN courses c ON c.id = ac.course_id
            WHERE a.batch_id = ?
              AND a.status IN ('CONFIRMED', 'REGISTERED', 'COMPLETED')
            ORDER BY s.first_name ASC, s.last_name ASC;
        """
        rows = self.execute_fetchall(sql, (batch_id,))
        results = []
        for r in rows:
            results.append(
                BatchStudentDTO(
                    student_id=r["student_id"],
                    admission_id=r["admission_id"],
                    candidate_number=r["candidate_number"],
                    student_name=r["student_name"].strip(),
                    first_name=r["first_name"] or "",
                    last_name=r["last_name"] or "",
                    mobile_number=r["mobile_number"],
                    village=r["village"],
                    photo_path=r["photo_path"] if r.get("photo_path") else None,
                    course_id=r["course_id"],
                    course_name=r["course_name"] or "—",
                    admission_date=r["admission_date"][:10] if r["admission_date"] else None,
                    pending_fees=float(r["pending_fees"] or 0.0),
                    total_paid=float(r["total_paid"] or 0.0),
                    final_fee=float(r["final_fee"] or 0.0),
                )
            )
        return results

    def get_session(self, batch_id: int, session_date: str) -> Optional[Dict[str, Any]]:
        """Retrieves an existing attendance session for a batch on a given date."""
        sql = """
            SELECT 
                s.id,
                s.batch_id,
                b.batch_name,
                c.name AS course_name,
                s.session_date,
                s.mode,
                s.scanned_image_path,
                s.recorded_by,
                s.remarks,
                s.created_at
            FROM batch_attendance_sessions s
            JOIN batches b ON b.id = s.batch_id
            JOIN courses c ON c.id = b.course_id
            WHERE s.batch_id = ? AND s.session_date = ?;
        """
        return self.execute_fetchone(sql, (batch_id, session_date))

    def get_session_by_id(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves an attendance session by primary key."""
        sql = """
            SELECT 
                s.id,
                s.batch_id,
                b.batch_name,
                c.name AS course_name,
                s.session_date,
                s.mode,
                s.scanned_image_path,
                s.recorded_by,
                s.remarks,
                s.created_at
            FROM batch_attendance_sessions s
            JOIN batches b ON b.id = s.batch_id
            JOIN courses c ON c.id = b.course_id
            WHERE s.id = ?;
        """
        return self.execute_fetchone(sql, (session_id,))

    def upsert_session(
        self,
        batch_id: int,
        session_date: str,
        mode: str = "ONLINE",
        recorded_by: Optional[str] = None,
        remarks: Optional[str] = None,
        scanned_image_path: Optional[Any] = None,
    ) -> int:
        """
        Creates or updates a session for a batch and date.
        Returns the session ID.
        """
        # Defensive conversion: Ensure Path/PosixPath is converted to str for SQLite driver
        clean_image_path = str(scanned_image_path) if scanned_image_path is not None else None

        existing = self.get_session(batch_id, session_date)
        if existing:
            session_id = existing["id"]
            sql_update = """
                UPDATE batch_attendance_sessions
                SET mode = ?,
                    recorded_by = COALESCE(?, recorded_by),
                    remarks = COALESCE(?, remarks),
                    scanned_image_path = COALESCE(?, scanned_image_path),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """
            self.execute(sql_update, (mode, recorded_by, remarks, clean_image_path, session_id))
            return session_id
        else:
            sql_insert = """
                INSERT INTO batch_attendance_sessions (
                    batch_id, session_date, mode, recorded_by, remarks, scanned_image_path
                ) VALUES (?, ?, ?, ?, ?, ?);
            """
            return self.execute_insert(
                sql_insert, (batch_id, session_date, mode, recorded_by, remarks, clean_image_path)
            )

    def save_records(
        self,
        session_id: int,
        batch_id: int,
        records: List[Dict[str, Any]],
    ) -> None:
        """
        Saves student attendance records for a session.
        Uses INSERT OR REPLACE to update existing markings seamlessly.
        """
        sql = """
            INSERT INTO student_attendance_records (
                session_id, batch_id, student_id, admission_id,
                status, marking_method, confidence_score, remarks
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id, student_id) DO UPDATE SET
                status = excluded.status,
                marking_method = excluded.marking_method,
                confidence_score = excluded.confidence_score,
                remarks = excluded.remarks;
        """
        for r in records:
            params = (
                session_id,
                batch_id,
                r["student_id"],
                r.get("admission_id"),
                r.get("status", "ABSENT"),
                r.get("marking_method", "TOGGLE"),
                float(r.get("confidence_score", 1.0)),
                r.get("remarks"),
            )
            self.execute(sql, params)

    def get_records_for_session(self, session_id: int) -> List[Dict[str, Any]]:
        """Retrieves all student records for a specific session."""
        sql = """
            SELECT 
                r.id,
                r.session_id,
                r.student_id,
                r.admission_id,
                r.status,
                r.marking_method,
                r.confidence_score,
                r.remarks,
                (s.first_name || ' ' || s.last_name) AS student_name,
                COALESCE(
                    (CAST(a.candidate_year AS TEXT) || '-' || printf('%03d', a.candidate_sequence)),
                    printf('ADM-%04d', a.id)
                ) AS candidate_number
            FROM student_attendance_records r
            JOIN students s ON s.id = r.student_id
            LEFT JOIN admissions a ON a.id = r.admission_id
            WHERE r.session_id = ?
            ORDER BY s.first_name ASC, s.last_name ASC;
        """
        return self.execute_fetchall(sql, (session_id,))

    def get_batch_matrix(self, batch_id: int) -> BatchAttendanceMatrixDTO:
        """
        Assembles the complete attendance spreadsheet matrix for a batch:
        - All dates where attendance was recorded (sorted ascending).
        - All active students enrolled in the batch.
        - Per-date 'P' / 'A' markings and calculated summary statistics.
        """
        # 1. Fetch batch metadata
        batch_sql = """
            SELECT b.id, b.batch_name, b.timing, c.name AS course_name
            FROM batches b
            JOIN courses c ON c.id = b.course_id
            WHERE b.id = ?;
        """
        batch_row = self.execute_fetchone(batch_sql, (batch_id,))
        if not batch_row:
            return BatchAttendanceMatrixDTO(
                batch_id=batch_id,
                batch_name="Unknown Batch",
                batch_timing="—",
                course_name="—",
            )

        # 2. Fetch distinct session dates
        dates_sql = """
            SELECT session_date
            FROM batch_attendance_sessions
            WHERE batch_id = ?
            ORDER BY session_date ASC;
        """
        date_rows = self.execute_fetchall(dates_sql, (batch_id,))
        session_dates = [r["session_date"] for r in date_rows]

        # 3. Fetch enrolled students
        students = self.get_enrolled_students(batch_id)

        # 4. Fetch all attendance marks for this batch
        records_sql = """
            SELECT 
                r.student_id,
                s.session_date,
                r.status
            FROM student_attendance_records r
            JOIN batch_attendance_sessions s ON s.id = r.session_id
            WHERE r.batch_id = ?;
        """
        rec_rows = self.execute_fetchall(records_sql, (batch_id,))
        
        # Build quick lookup: (student_id, date) -> 'P' | 'A'
        marks_lookup: Dict[tuple[int, str], str] = {}
        for row in rec_rows:
            marks_lookup[(row["student_id"], row["session_date"])] = "P" if row["status"] == "PRESENT" else "A"

        total_possible = 0
        total_present_all = 0
        matrix_rows: List[BatchAttendanceMatrixRowDTO] = []

        for st in students:
            date_marks: Dict[str, str] = {}
            p_count = 0
            a_count = 0

            for d in session_dates:
                mark = marks_lookup.get((st.student_id, d), "—")
                date_marks[d] = mark
                if mark == "P":
                    p_count += 1
                elif mark == "A":
                    a_count += 1

            total_sessions_student = p_count + a_count
            pct = round((p_count / total_sessions_student * 100.0), 1) if total_sessions_student > 0 else 100.0
            
            # Categorize health
            if pct >= 85.0:
                health = AttendanceHealth.EXCELLENT.value
            elif pct >= 75.0:
                health = AttendanceHealth.GOOD.value
            elif pct >= 60.0:
                health = AttendanceHealth.AVERAGE.value
            else:
                health = AttendanceHealth.CRITICAL.value

            total_possible += total_sessions_student
            total_present_all += p_count

            matrix_rows.append(
                BatchAttendanceMatrixRowDTO(
                    student_id=st.student_id,
                    candidate_number=st.candidate_number,
                    student_name=st.student_name,
                    mobile_number=st.mobile_number,
                    admission_date=st.admission_date,
                    pending_fees=st.pending_fees,
                    date_marks=date_marks,
                    total_present=p_count,
                    total_absent=a_count,
                    total_sessions=total_sessions_student,
                    attendance_percentage=pct,
                    health_status=health,
                )
            )

        overall_rate = round((total_present_all / total_possible * 100.0), 1) if total_possible > 0 else 0.0

        return BatchAttendanceMatrixDTO(
            batch_id=batch_id,
            batch_name=batch_row["batch_name"],
            batch_timing=batch_row["timing"],
            course_name=batch_row["course_name"],
            session_dates=session_dates,
            rows=matrix_rows,
            overall_attendance_rate=overall_rate,
        )

    def get_student_attendance_health(self, student_id: int) -> StudentAttendanceHealthDTO:
        """
        Computes the aggregate attendance health and recent session history for a student.
        """
        # Fetch student name
        student_sql = "SELECT (first_name || ' ' || last_name) AS student_name FROM students WHERE id = ?;"
        student_row = self.execute_fetchone(student_sql, (student_id,))
        student_name = student_row["student_name"].strip() if student_row else "Student"

        # Count present and absent
        stats_sql = """
            SELECT 
                COUNT(*) AS total_sessions,
                SUM(CASE WHEN r.status = 'PRESENT' THEN 1 ELSE 0 END) AS present_count,
                SUM(CASE WHEN r.status = 'ABSENT' THEN 1 ELSE 0 END) AS absent_count
            FROM student_attendance_records r
            WHERE r.student_id = ?;
        """
        stats_row = self.execute_fetchone(stats_sql, (student_id,))
        total_sessions = stats_row["total_sessions"] or 0
        present_count = stats_row["present_count"] or 0
        absent_count = stats_row["absent_count"] or 0

        pct = round((present_count / total_sessions * 100.0), 1) if total_sessions > 0 else 100.0

        if pct >= 85.0:
            health = AttendanceHealth.EXCELLENT
        elif pct >= 75.0:
            health = AttendanceHealth.GOOD
        elif pct >= 60.0:
            health = AttendanceHealth.AVERAGE
        else:
            health = AttendanceHealth.CRITICAL

        # Recent sessions
        history_sql = """
            SELECT 
                s.session_date,
                b.batch_name,
                b.timing,
                c.name AS course_name,
                s.mode,
                r.status,
                r.marking_method
            FROM student_attendance_records r
            JOIN batch_attendance_sessions s ON s.id = r.session_id
            JOIN batches b ON b.id = s.batch_id
            JOIN courses c ON c.id = b.course_id
            WHERE r.student_id = ?
            ORDER BY s.session_date DESC
            LIMIT 20;
        """
        history_rows = self.execute_fetchall(history_sql, (student_id,))
        recent_history = [
            {
                "date": h["session_date"],
                "batch_name": h["batch_name"],
                "timing": h["timing"],
                "course_name": h["course_name"],
                "mode": h["mode"],
                "status": h["status"],
                "marking_method": h["marking_method"],
            }
            for h in history_rows
        ]

        return StudentAttendanceHealthDTO(
            student_id=student_id,
            student_name=student_name,
            total_sessions_conducted=total_sessions,
            total_present=present_count,
            total_absent=absent_count,
            attendance_percentage=pct,
            health_status=health.value,
            health_color=HEALTH_COLORS[health],
            health_bg_color=HEALTH_BG_COLORS[health],
            recent_history=recent_history,
        )

    def get_batches_list(self) -> List[Dict[str, Any]]:
        """Retrieves list of all batches with course names for dropdown selectors."""
        sql = """
            SELECT 
                b.id,
                b.batch_name,
                b.timing,
                b.status,
                c.id AS course_id,
                c.name AS course_name,
                (SELECT COUNT(*) FROM admissions a WHERE a.batch_id = b.id AND a.status IN ('CONFIRMED', 'REGISTERED', 'COMPLETED')) AS enrolled_count
            FROM batches b
            JOIN courses c ON c.id = b.course_id
            WHERE b.status <> 'ARCHIVED'
            ORDER BY c.name ASC, b.batch_name ASC;
        """
        return self.execute_fetchall(sql)

    def get_batch_by_id(self, batch_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves details of a single batch with its course information."""
        sql = """
            SELECT 
                b.id,
                b.batch_name,
                b.timing,
                b.status,
                c.id AS course_id,
                c.name AS course_name,
                (SELECT COUNT(*) FROM admissions a WHERE a.batch_id = b.id AND a.status IN ('CONFIRMED', 'REGISTERED', 'COMPLETED')) AS enrolled_count
            FROM batches b
            JOIN courses c ON c.id = b.course_id
            WHERE b.id = ?;
        """
        return self.execute_fetchone(sql, (batch_id,))

    def get_session_marks_for_dates(self, batch_id: int, dates: List[str]) -> Dict[tuple[int, str], str]:
        """
        Returns a mapping of (student_id, session_date) -> status ('PRESENT' | 'ABSENT')
        for all existing recorded attendance in the specified batch and date list.
        """
        if not dates:
            return {}
        placeholders = ",".join("?" for _ in dates)
        sql = f"""
            SELECT 
                r.student_id,
                s.session_date,
                r.status
            FROM student_attendance_records r
            JOIN batch_attendance_sessions s ON s.id = r.session_id
            WHERE r.batch_id = ? AND s.session_date IN ({placeholders});
        """
        params = [batch_id] + list(dates)
        rows = self.execute_fetchall(sql, params)
        return {(r["student_id"], r["session_date"]): r["status"] for r in rows}

