from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import cairo
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from core.database.transaction import TransactionManager
from core.exceptions import ValidationError, ServiceError
from core.logger.service import LogService
from core.service.base import BaseService
from modules.attendance.constants import AttendanceMode, MarkingMethod
from modules.attendance.dto import (
    AttendanceRecordDTO,
    AttendanceSessionDTO,
    BatchAttendanceMatrixDTO,
    BatchStudentDTO,
    ExcelAttendanceCellDiffDTO,
    ExcelAttendanceImportPreviewDTO,
    OCRScanResultDTO,
    OfflineFormatConfigDTO,
    OfflineRegisterConfigDTO,
    StudentAttendanceHealthDTO,
)
from modules.attendance.ocr_engine import AttendanceOCREngine
from modules.attendance.repository import AttendanceRepository
from modules.settings.service import SettingsService
from shared.utils.formatting import normalize_name


class AttendanceService(BaseService):
    """
    Business logic and orchestration service for online attendance recording,
    offline format generation, OCR sheet processing, matrix spreadsheet exports,
    and student attendance health analysis.
    """

    def __init__(
        self,
        repository: Optional[AttendanceRepository] = None,
        settings_service: Optional[SettingsService] = None,
    ):
        self.repository = repository or AttendanceRepository()
        self.settings_service = settings_service or SettingsService()

    @contextmanager
    def _tx(self):
        """Re-entrant transaction context: joins active transaction or creates unit_of_work."""
        if TransactionManager.in_transaction():
            yield
        else:
            with self.unit_of_work():
                yield

    def get_batches_list(self) -> List[Dict[str, Any]]:
        """Retrieves list of active batches for selection."""
        with self._tx():
            return self.repository.get_batches_list()

    def get_enrolled_students(self, batch_id: int) -> List[BatchStudentDTO]:
        """Retrieves enrolled students for a batch."""
        with self._tx():
            return self.repository.get_enrolled_students(batch_id)

    def get_session(self, batch_id: int, session_date: str) -> Optional[AttendanceSessionDTO]:
        """Fetches attendance session and records for a batch and date."""
        with self._tx():
            session_row = self.repository.get_session(batch_id, session_date)
            if not session_row:
                return None

            records_rows = self.repository.get_records_for_session(session_row["id"])
            records: List[AttendanceRecordDTO] = []
            p_count = 0
            a_count = 0

            for r in records_rows:
                is_present = (r["status"] == "PRESENT")
                if is_present:
                    p_count += 1
                else:
                    a_count += 1

                records.append(
                    AttendanceRecordDTO(
                        student_id=r["student_id"],
                        student_name=r["student_name"],
                        candidate_number=r["candidate_number"],
                        status=r["status"],
                        marking_method=r["marking_method"],
                        confidence_score=float(r["confidence_score"] or 1.0),
                        remarks=r["remarks"],
                        admission_id=r["admission_id"],
                        record_id=r["id"],
                    )
                )

            return AttendanceSessionDTO(
                id=session_row["id"],
                batch_id=session_row["batch_id"],
                batch_name=session_row["batch_name"],
                course_name=session_row["course_name"],
                session_date=session_row["session_date"],
                mode=session_row["mode"],
                scanned_image_path=session_row["scanned_image_path"],
                recorded_by=session_row["recorded_by"],
                remarks=session_row["remarks"],
                total_enrolled=len(records),
                total_present=p_count,
                total_absent=a_count,
                records=records,
                created_at=session_row["created_at"],
            )

    def record_online_attendance(
        self,
        batch_id: int,
        session_date: str,
        student_marks: List[Dict[str, Any]],
        recorded_by: Optional[str] = None,
        remarks: Optional[str] = None,
    ) -> AttendanceSessionDTO:
        """
        Records or updates an online attendance session using toggles.
        student_marks: List of dicts with 'student_id', 'is_present' (bool) or 'status' (PRESENT/ABSENT).
        """
        try:
            d = datetime.strptime(session_date, "%Y-%m-%d").date()
            if d > date.today():
                raise ValidationError("Cannot mark attendance for future dates. Attendance cannot be recorded in advance.")
        except ValueError:
            pass

        with self._tx():
            session_id = self.repository.upsert_session(
                batch_id=batch_id,
                session_date=session_date,
                mode=AttendanceMode.ONLINE.value,
                recorded_by=recorded_by,
                remarks=remarks,
            )

            prepared_records = []
            for sm in student_marks:
                status = "PRESENT" if sm.get("is_present") or sm.get("status") == "PRESENT" else "ABSENT"
                prepared_records.append(
                    {
                        "student_id": sm["student_id"],
                        "admission_id": sm.get("admission_id"),
                        "status": status,
                        "marking_method": MarkingMethod.TOGGLE.value,
                        "confidence_score": 1.0,
                        "remarks": sm.get("remarks"),
                    }
                )

            self.repository.save_records(session_id, batch_id, prepared_records)
            updated = self.get_session(batch_id, session_date)
            if not updated:
                raise RuntimeError("Failed to reload session after recording online attendance.")
            return updated

    def process_offline_image(
        self,
        image_path: str | Path,
        batch_id: int,
        session_date: Optional[str] = None,
    ) -> OCRScanResultDTO:
        """
        Runs the OCR engine over an uploaded physical attendance sheet image.
        """
        with self._tx():
            students = self.get_enrolled_students(batch_id)
            batch_info = self.repository.execute_fetchone("SELECT batch_name FROM batches WHERE id = ?;", (batch_id,))
            batch_name = batch_info["batch_name"] if batch_info else f"Batch-{batch_id}"

        return AttendanceOCREngine.scan_offline_sheet(
            image_path=image_path,
            batch_id=batch_id,
            batch_name=batch_name,
            enrolled_students=students,
            session_date=session_date,
        )

    def commit_offline_attendance(
        self,
        batch_id: int,
        session_date: str,
        student_marks: List[Dict[str, Any]],
        scanned_image_path: Optional[str] = None,
        recorded_by: Optional[str] = None,
        remarks: Optional[str] = None,
    ) -> AttendanceSessionDTO:
        """
        Commits verified OCR attendance scan into the database spreadsheet.
        """
        clean_image_path = str(scanned_image_path) if scanned_image_path is not None else None
        with self._tx():
            session_id = self.repository.upsert_session(
                batch_id=batch_id,
                session_date=session_date,
                mode=AttendanceMode.OFFLINE.value,
                recorded_by=recorded_by,
                remarks=remarks or "Recorded via OCR sheet scan",
                scanned_image_path=clean_image_path,
            )

            prepared_records = []
            for sm in student_marks:
                status = "PRESENT" if sm.get("is_present") or sm.get("status") == "PRESENT" else "ABSENT"
                prepared_records.append(
                    {
                        "student_id": sm["student_id"],
                        "admission_id": sm.get("admission_id"),
                        "status": status,
                        "marking_method": MarkingMethod.OCR_SCAN.value,
                        "confidence_score": sm.get("confidence", 1.0),
                        "remarks": sm.get("remarks"),
                    }
                )

            self.repository.save_records(session_id, batch_id, prepared_records)
            updated = self.get_session(batch_id, session_date)
            if not updated:
                raise RuntimeError("Failed to reload session after committing offline attendance.")
            return updated

    def get_batch_matrix(self, batch_id: int) -> BatchAttendanceMatrixDTO:
        """Retrieves full attendance matrix spreadsheet for a batch."""
        with self._tx():
            return self.repository.get_batch_matrix(batch_id)

    def get_student_attendance_health(self, student_id: int) -> StudentAttendanceHealthDTO:
        """Retrieves student attendance health indicators and session timeline."""
        with self._tx():
            return self.repository.get_student_attendance_health(student_id)

    # ══════════════════════════════════════════════════════════════════════
    # EXPORT ENGINES: PRINT OFFLINE FORMAT (EXCEL)
    # ══════════════════════════════════════════════════════════════════════
    def generate_offline_format_excel(
        self,
        config: OfflineFormatConfigDTO,
        target_dir: str | Path = "exports/attendance/formats",
    ) -> Path:
        """
        Generates a fixed, standardized physical attendance sheet in Excel (.xlsx) format.
        Supports administrator column customizer toggles.
        """
        with self._tx():
            students = self.get_enrolled_students(config.batch_id)
            batch_sql = """
                SELECT b.batch_name, b.timing, c.name AS course_name
                FROM batches b
                JOIN courses c ON c.id = b.course_id
                WHERE b.id = ?;
            """
            batch_row = self.repository.execute_fetchone(batch_sql, (config.batch_id,))
            batch_name = batch_row["batch_name"] if batch_row else f"Batch-{config.batch_id}"
            timing = batch_row["timing"] if batch_row else "—"
            course_name = batch_row["course_name"] if batch_row else "—"

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Attendance Sheet"

        # Theme styles
        navy_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        title_font = Font(name="Arial", size=14, bold=True, color="1E3A8A")
        sub_font = Font(name="Arial", size=9, bold=False, color="475569")
        data_font = Font(name="Arial", size=9)
        bold_data_font = Font(name="Arial", size=9, bold=True)

        thin_border = Border(
            left=Side(style="thin", color="CBD5E1"),
            right=Side(style="thin", color="CBD5E1"),
            top=Side(style="thin", color="CBD5E1"),
            bottom=Side(style="thin", color="CBD5E1"),
        )
        box_border = Border(
            left=Side(style="medium", color="475569"),
            right=Side(style="medium", color="475569"),
            top=Side(style="medium", color="475569"),
            bottom=Side(style="medium", color="475569"),
        )

        # Title Rows
        ws.merge_cells("A1:K1")
        ws["A1"] = "SIMS v2.2 — Standardized Physical Attendance Roster"
        ws["A1"].font = title_font
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 24

        meta_line = f"Course: {course_name}  |  Batch: {batch_name} ({timing})  |  Generated on: {datetime.now().strftime('%d-%b-%Y')}"
        ws.merge_cells("A2:K2")
        ws["A2"] = meta_line
        ws["A2"].font = sub_font
        ws["A2"].alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[2].height = 18

        # Instructions / Verification Bar
        ws.merge_cells("A3:K3")
        ws["A3"] = "Instructions: Mark [ ✓ ] for Present, [ ✗ ] for Absent inside the designated checkboxes. Scan/upload clearly without cropping borders."
        ws["A3"].font = Font(name="Arial", size=8, italic=True, color="64748B")
        ws["A3"].alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[3].height = 16

        # Assemble Column Headers based on Administrator Toggles
        headers = ["S.No", "Candidate No"]
        if config.include_student_name:
            headers.append("Student Name")
        if config.include_contact_number:
            headers.append("Mobile Number")
        if config.include_admission_date:
            headers.append("Adm Date")
        if config.include_pending_fees:
            headers.append("Pending Fees")
        if config.include_course_details:
            headers.append("Course")

        # Blank session date columns (for physical mark)
        num_sessions = max(1, min(config.blank_session_columns, 30))
        for col_i in range(1, num_sessions + 1):
            if num_sessions == 1 and config.session_date:
                headers.append(f"Mark ({config.session_date[-5:]})")
            else:
                headers.append(f"Day {col_i}")

        header_row_idx = 5
        ws.row_dimensions[header_row_idx].height = 24

        for col_idx, h_text in enumerate(headers, 1):
            cell = ws.cell(row=header_row_idx, column=col_idx, value=h_text)
            cell.fill = navy_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = thin_border

        # Populate Student Rows
        current_r = 6
        for s_idx, st in enumerate(students, 1):
            ws.row_dimensions[current_r].height = 22
            col_pos = 1

            # S.No
            cell = ws.cell(row=current_r, column=col_pos, value=s_idx)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.font = data_font
            cell.border = thin_border
            col_pos += 1

            # Candidate No
            cell = ws.cell(row=current_r, column=col_pos, value=st.candidate_number or "—")
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.font = bold_data_font
            cell.border = thin_border
            col_pos += 1

            # Student Name
            if config.include_student_name:
                cell = ws.cell(row=current_r, column=col_pos, value=st.student_name)
                cell.alignment = Alignment(horizontal="left", vertical="center")
                cell.font = bold_data_font
                cell.border = thin_border
                col_pos += 1

            # Mobile
            if config.include_contact_number:
                cell = ws.cell(row=current_r, column=col_pos, value=st.mobile_number or "—")
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.font = data_font
                cell.border = thin_border
                col_pos += 1

            # Admission Date
            if config.include_admission_date:
                cell = ws.cell(row=current_r, column=col_pos, value=st.admission_date or "—")
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.font = data_font
                cell.border = thin_border
                col_pos += 1

            # Pending Fees
            if config.include_pending_fees:
                fee_val = f"₹{st.pending_fees:,.2f}" if st.pending_fees > 0 else "₹0.00"
                cell = ws.cell(row=current_r, column=col_pos, value=fee_val)
                cell.alignment = Alignment(horizontal="right", vertical="center")
                cell.font = bold_data_font
                cell.border = thin_border
                col_pos += 1

            # Course Details
            if config.include_course_details:
                cell = ws.cell(row=current_r, column=col_pos, value=course_name)
                cell.alignment = Alignment(horizontal="left", vertical="center")
                cell.font = data_font
                cell.border = thin_border
                col_pos += 1

            # Blank Mark Boxes (Clear checkboxes for OCR bubble scanning)
            for _ in range(num_sessions):
                cell = ws.cell(row=current_r, column=col_pos, value="[   ]")
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.font = bold_data_font
                cell.border = box_border
                col_pos += 1

            current_r += 1

        # Signatures Area
        current_r += 2
        ws.cell(row=current_r, column=2, value="Coordinator / Faculty Signature: _________________________").font = sub_font
        ws.cell(row=current_r, column=max(col_pos - 3, 5), value="Principal / Admin Stamp: _________________________").font = sub_font

        # Auto-adjust column widths
        for col in ws.columns:
            max_len = 0
            c_letter = get_column_letter(col[0].column)
            for c in col:
                if c.row > 3 and c.value:
                    max_len = max(max_len, len(str(c.value)))
            ws.column_dimensions[c_letter].width = max(max_len + 3, 10)

        # Output save
        out_dir = Path(target_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        sanitized_batch = "".join(c if c.isalnum() else "_" for c in batch_name)
        file_name = f"SIMS_Attendance_Format_{sanitized_batch}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        target_path = out_dir / file_name

        wb.save(str(target_path))
        LogService.info(f"Generated fixed offline format: {target_path}", context="AttendanceService")
        return target_path

    # ══════════════════════════════════════════════════════════════════════
    # EXPORT ENGINES: EXCEL SPREADSHEET MATRIX
    # ══════════════════════════════════════════════════════════════════════
    def export_matrix_excel(
        self,
        batch_id: int,
        target_dir: str | Path = "exports/attendance",
    ) -> Path:
        """
        Exports the entire batch attendance matrix spreadsheet to styled Excel (.xlsx).
        Features green/red conditional fills for P/A marks and percentage health summaries.
        """
        matrix = self.get_batch_matrix(batch_id)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Attendance Matrix"

        # Styles
        title_font = Font(name="Arial", size=13, bold=True, color="1E3A8A")
        sub_font = Font(name="Arial", size=9, bold=False, color="475569")
        h_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
        h_font = Font(name="Arial", size=9, bold=True, color="FFFFFF")
        p_fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")  # Soft green
        p_font = Font(name="Arial", size=9, bold=True, color="166534")
        a_fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")  # Soft red
        a_font = Font(name="Arial", size=9, bold=True, color="991B1B")
        summary_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        border = Border(
            left=Side(style="thin", color="E2E8F0"),
            right=Side(style="thin", color="E2E8F0"),
            top=Side(style="thin", color="E2E8F0"),
            bottom=Side(style="thin", color="E2E8F0"),
        )

        # Title
        ws.merge_cells("A1:H1")
        ws["A1"] = f"SIMS v2.2 — Batch Attendance Ledger: {matrix.batch_name} ({matrix.course_name})"
        ws["A1"].font = title_font
        ws["A1"].alignment = Alignment(horizontal="left", vertical="center")

        ws.merge_cells("A2:H2")
        ws["A2"] = f"Timing: {matrix.batch_timing}  |  Overall Attendance Rate: {matrix.overall_attendance_rate}%  |  Exported: {datetime.now().strftime('%d-%b-%Y %H:%M')}"
        ws["A2"].font = sub_font
        ws["A2"].alignment = Alignment(horizontal="left", vertical="center")

        # Headers
        base_headers = ["Candidate No", "Student Name", "Mobile Number"]
        date_headers = [f"{d[5:]}" for d in matrix.session_dates]  # MM-DD
        summary_headers = ["Present", "Absent", "Total", "% Health"]
        all_headers = base_headers + date_headers + summary_headers

        ws.row_dimensions[4].height = 22
        for col_i, h in enumerate(all_headers, 1):
            cell = ws.cell(row=4, column=col_i, value=h)
            cell.fill = h_fill
            cell.font = h_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = border

        # Rows
        curr_r = 5
        for r in matrix.rows:
            ws.row_dimensions[curr_r].height = 20

            # Base info
            c1 = ws.cell(row=curr_r, column=1, value=r.candidate_number or "—")
            c1.alignment = Alignment(horizontal="center", vertical="center")
            c1.border = border

            c2 = ws.cell(row=curr_r, column=2, value=r.student_name)
            c2.alignment = Alignment(horizontal="left", vertical="center")
            c2.font = Font(name="Arial", size=9, bold=True)
            c2.border = border

            c3 = ws.cell(row=curr_r, column=3, value=r.mobile_number or "—")
            c3.alignment = Alignment(horizontal="center", vertical="center")
            c3.border = border

            col_pos = 4
            for d in matrix.session_dates:
                mark = r.date_marks.get(d, "—")
                cell = ws.cell(row=curr_r, column=col_pos, value=mark)
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = border

                if mark == "P":
                    cell.fill = p_fill
                    cell.font = p_font
                elif mark == "A":
                    cell.fill = a_fill
                    cell.font = a_font

                col_pos += 1

            # Summary values
            p_cell = ws.cell(row=curr_r, column=col_pos, value=r.total_present)
            p_cell.alignment = Alignment(horizontal="center", vertical="center")
            p_cell.fill = summary_fill
            p_cell.font = p_font
            p_cell.border = border
            col_pos += 1

            a_cell = ws.cell(row=curr_r, column=col_pos, value=r.total_absent)
            a_cell.alignment = Alignment(horizontal="center", vertical="center")
            a_cell.fill = summary_fill
            a_cell.font = a_font
            a_cell.border = border
            col_pos += 1

            t_cell = ws.cell(row=curr_r, column=col_pos, value=r.total_sessions)
            t_cell.alignment = Alignment(horizontal="center", vertical="center")
            t_cell.fill = summary_fill
            t_cell.border = border
            col_pos += 1

            pct_cell = ws.cell(row=curr_r, column=col_pos, value=f"{r.attendance_percentage}%")
            pct_cell.alignment = Alignment(horizontal="center", vertical="center")
            pct_cell.fill = summary_fill
            pct_cell.font = Font(name="Arial", size=9, bold=True, color="1E3A8A")
            pct_cell.border = border

            curr_r += 1

        for col in ws.columns:
            max_len = max(len(str(c.value or "")) for c in col)
            c_letter = get_column_letter(col[0].column)
            ws.column_dimensions[c_letter].width = max(max_len + 3, 9)

        out_dir = Path(target_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        sanitized_batch = "".join(c if c.isalnum() else "_" for c in matrix.batch_name)
        target_path = out_dir / f"SIMS_Attendance_Spreadsheet_{sanitized_batch}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        wb.save(str(target_path))
        LogService.info(f"Exported attendance matrix Excel: {target_path}", context="AttendanceService")
        return target_path

    # ══════════════════════════════════════════════════════════════════════
    # EXPORT ENGINES: PDF SPREADSHEET WITH "SIMS" WATERMARK
    # ══════════════════════════════════════════════════════════════════════
    def export_matrix_pdf(
        self,
        batch_id: int,
        target_dir: str | Path = "exports/attendance",
    ) -> Path:
        """
        Exports the entire batch attendance matrix spreadsheet to a professional
        multi-page vector PDF report using Cairo.
        Features a diagonal translucent "SIMS" watermark on every single page.
        """
        matrix = self.get_batch_matrix(batch_id)
        out_dir = Path(target_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        sanitized_batch = "".join(c if c.isalnum() else "_" for c in matrix.batch_name)
        path = out_dir / f"SIMS_Attendance_Report_{sanitized_batch}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        # A4 Landscape Dimensions
        page_width = 841.89
        page_height = 595.28
        margin_left = 36.0
        margin_right = 36.0
        margin_top = 40.0
        margin_bottom = 40.0
        content_width = page_width - margin_left - margin_right

        surface = cairo.PDFSurface(str(path), page_width, page_height)
        cr = cairo.Context(surface)

        # Build Headers & Column Weights
        headers = ["Candidate No", "Student Name", "Mobile"]
        for d in matrix.session_dates:
            headers.append(d[5:])  # MM-DD
        headers.extend(["Present", "Absent", "% Rate"])

        col_weights = [1.2, 2.2, 1.2]
        for _ in matrix.session_dates:
            col_weights.append(0.8)
        col_weights.extend([0.9, 0.9, 1.0])

        total_weight = sum(col_weights)
        scaled_widths = [(w / total_weight) * content_width for w in col_weights]

        row_height = 18.0
        header_height = 22.0
        start_y = margin_top + 45.0
        max_y = page_height - margin_bottom - 20.0

        current_y = start_y
        page_num = 1

        def draw_watermark_and_decorations(p_num: int) -> None:
            cr.save()

            # 1. DIAGONAL TRANSLUCENT "SIMS" WATERMARK
            cr.save()
            cr.translate(page_width / 2.0, page_height / 2.0)
            cr.rotate(-0.785398)  # -45 degrees
            cr.set_source_rgba(0.78, 0.82, 0.90, 0.22)  # Soft translucent slate-blue
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(96.0)
            extents = cr.text_extents("SIMS")
            cr.move_to(-extents.width / 2.0, extents.height / 2.0)
            cr.show_text("SIMS")
            cr.restore()

            # 2. Header
            cr.set_source_rgb(0.12, 0.23, 0.36)  # Deep Navy
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(14.0)
            cr.move_to(margin_left, margin_top)
            cr.show_text(f"SIMS v2.2 — Batch Attendance Ledger: {matrix.batch_name}")

            # 3. Subtitle
            cr.set_source_rgb(0.40, 0.45, 0.55)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(8.5)
            sub = f"Course: {matrix.course_name}  |  Timing: {matrix.batch_timing}  |  Overall Attendance: {matrix.overall_attendance_rate}%  |  Exported: {datetime.now().strftime('%d-%b-%Y %H:%M')}"
            cr.move_to(margin_left, margin_top + 14.0)
            cr.show_text(sub)

            # 4. Footer
            cr.set_line_width(0.5)
            cr.set_source_rgb(0.80, 0.84, 0.89)
            cr.move_to(margin_left, page_height - margin_bottom + 5.0)
            cr.line_to(page_width - margin_right, page_height - margin_bottom + 5.0)
            cr.stroke()

            cr.set_source_rgb(0.50, 0.55, 0.60)
            cr.set_font_size(8.0)
            cr.move_to(margin_left, page_height - margin_bottom + 16.0)
            cr.show_text(f"SIMS Enterprise ERP  •  Batch Attendance Matrix  •  Page {p_num}")
            cr.restore()

        def draw_table_headers(y_pos: float) -> float:
            cr.save()
            cr.set_source_rgb(0.08, 0.15, 0.28)  # Dark Navy
            cr.rectangle(margin_left, y_pos, content_width, header_height)
            cr.fill()

            cr.set_source_rgb(1.0, 1.0, 1.0)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(8.5)

            cur_x = margin_left
            for i, h in enumerate(headers):
                w = scaled_widths[i]
                cr.move_to(cur_x + 3.0, y_pos + 14.0)
                cr.show_text(str(h)[:14])
                cur_x += w

            cr.restore()
            return y_pos + header_height

        # Render First Page
        draw_watermark_and_decorations(page_num)
        current_y = draw_table_headers(current_y)

        # Render Rows
        for r_idx, r in enumerate(matrix.rows):
            if current_y + row_height > max_y:
                surface.show_page()
                page_num += 1
                draw_watermark_and_decorations(page_num)
                current_y = draw_table_headers(start_y)

            # Alternate row background
            if r_idx % 2 == 1:
                cr.save()
                cr.set_source_rgb(0.97, 0.98, 0.99)
                cr.rectangle(margin_left, current_y, content_width, row_height)
                cr.fill()
                cr.restore()

            # Assemble row values
            vals = [
                r.candidate_number or "—",
                r.student_name,
                r.mobile_number or "—",
            ]
            for d in matrix.session_dates:
                vals.append(r.date_marks.get(d, "—"))
            vals.extend([str(r.total_present), str(r.total_absent), f"{r.attendance_percentage}%"])

            cur_x = margin_left
            for c_idx, val in enumerate(vals):
                w = scaled_widths[c_idx]
                cr.save()

                # Highlight P (Green) and A (Red)
                if val == "P":
                    cr.set_source_rgb(0.08, 0.55, 0.25)
                    cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
                elif val == "A":
                    cr.set_source_rgb(0.85, 0.15, 0.15)
                    cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
                else:
                    cr.set_source_rgb(0.18, 0.22, 0.28)
                    cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)

                cr.set_font_size(8.0)
                txt = str(val)
                if len(txt) > 20:
                    txt = txt[:18] + ".."
                cr.move_to(cur_x + 3.0, current_y + 12.5)
                cr.show_text(txt)
                cr.restore()
                cur_x += w

            # Row divider
            cr.save()
            cr.set_line_width(0.3)
            cr.set_source_rgb(0.88, 0.90, 0.93)
            cr.move_to(margin_left, current_y + row_height)
            cr.line_to(page_width - margin_right, current_y + row_height)
            cr.stroke()
            cr.restore()

            current_y += row_height

        surface.finish()
        LogService.info(f"Exported attendance matrix watermarked PDF: {path}", context="AttendanceService")
        return path

    # ══════════════════════════════════════════════════════════════════════
    # ADMINISTRATOR CONFIGURATION & SECURITY HELPERS
    # ══════════════════════════════════════════════════════════════════════
    def get_attendance_settings(self) -> Dict[str, bool]:
        """Retrieves administrator configuration flags controlling attendance columns and security."""
        def _to_bool(k: str, default: str) -> bool:
            try:
                if not self.settings_service:
                    return default.lower() in ("true", "1", "yes")
                val = self.settings_service.get_setting(k, default)
                return str(val).strip().lower() in ("true", "1", "yes")
            except Exception:
                return default.lower() in ("true", "1", "yes")

        return {
            "show_admission_date": _to_bool("attendance_show_admission_date", "false"),
            "show_pending_fees": _to_bool("attendance_show_pending_fees", "true"),
            "show_contact_number": _to_bool("attendance_show_contact_number", "true"),
            "require_admin_pin_for_edits": _to_bool("attendance_require_admin_pin_for_edits", "true"),
        }


    def verify_admin_pin(self, pin: str) -> bool:
        """Verifies administrator authorization PIN."""
        return self.settings_service.verify_admin_pin(pin)

    # ══════════════════════════════════════════════════════════════════════
    # OFFLINE REGISTER GENERATION (.xlsx)
    # ══════════════════════════════════════════════════════════════════════
    def generate_offline_register_excel(
        self,
        config: OfflineRegisterConfigDTO,
        target_dir: str | Path = "exports/attendance/registers",
    ) -> Path:
        """
        Generates a standardized digital attendance register in Excel (.xlsx) format.
        Features machine-readable metadata, dynamic Excel formulas (=COUNTIF),
        data validation dropdowns ('P', 'A'), and A4 landscape print setup.
        """
        # 1. Determine period length in days
        duration_map = {
            "8_DAYS": 8,
            "15_DAYS": 15,
            "1_MONTH": 30,
            "2_MONTHS": 60,
        }
        num_days = duration_map.get(config.duration_type, config.num_days or 15)
        num_days = max(1, min(num_days, 60))

        # 2. Determine start and end dates
        if config.start_date and config.start_date.strip():
            try:
                start_dt = datetime.strptime(config.start_date.strip(), "%Y-%m-%d").date()
            except ValueError:
                start_dt = date.today()
        else:
            start_dt = date.today()

        dates = [start_dt + timedelta(days=i) for i in range(num_days)]
        start_str = dates[0].strftime("%Y-%m-%d")
        end_str = dates[-1].strftime("%Y-%m-%d")

        # 3. Retrieve batch and student details
        with self._tx():
            students = self.get_enrolled_students(config.batch_id)
            batch_info = self.repository.get_batch_by_id(config.batch_id)
            batch_name = batch_info["batch_name"] if batch_info else f"Batch-{config.batch_id}"
            timing = batch_info["timing"] if batch_info else "—"
            course_name = batch_info["course_name"] if batch_info else "—"

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Attendance Register"

        # Styles
        navy_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        date_h_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
        summary_h_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        summary_cell_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")

        header_font = Font(name="Arial", size=9, bold=True, color="FFFFFF")
        title_font = Font(name="Arial", size=13, bold=True, color="1E3A8A")
        sub_font = Font(name="Arial", size=9, color="475569")
        instr_font = Font(name="Arial", size=8, italic=True, color="64748B")
        meta_font = Font(name="Arial", size=7, color="94A3B8")
        data_font = Font(name="Arial", size=9)
        bold_data_font = Font(name="Arial", size=9, bold=True)

        thin_border = Border(
            left=Side(style="thin", color="CBD5E1"),
            right=Side(style="thin", color="CBD5E1"),
            top=Side(style="thin", color="CBD5E1"),
            bottom=Side(style="thin", color="CBD5E1"),
        )

        # Assemble Column Structure
        base_headers = ["S.No", "Candidate No", "Student Name"]
        if config.include_contact_number:
            base_headers.append("Mobile Number")
        if config.include_admission_date:
            base_headers.append("Adm Date")
        if config.include_pending_fees:
            base_headers.append("Pending Fees")

        date_headers = [d.strftime("%Y-%m-%d") for d in dates]
        summary_headers = ["Present Days", "Total Marked", "Attendance %"]
        all_headers = base_headers + date_headers + summary_headers
        total_cols = len(all_headers)
        last_col_letter = get_column_letter(total_cols)

        # Title Rows (1 to 3)
        ws.merge_cells(f"A1:{last_col_letter}1")
        ws["A1"] = "SIMS v2.2 — Standardized Batch Attendance Register"
        ws["A1"].font = title_font
        ws["A1"].alignment = Alignment(horizontal="left", vertical="center")
        ws.row_dimensions[1].height = 24

        ws.merge_cells(f"A2:{last_col_letter}2")
        ws["A2"] = f"Course: {course_name}  |  Batch: {batch_name} ({timing})  |  Period: {start_str} to {end_str} ({num_days} Days)"
        ws["A2"].font = sub_font
        ws["A2"].alignment = Alignment(horizontal="left", vertical="center")
        ws.row_dimensions[2].height = 18

        ws.merge_cells(f"A3:{last_col_letter}3")
        ws["A3"] = "Instructions: Enter 'P' for Present, 'A' for Absent. Leave cell blank for holidays or unconducted days. Do NOT modify Candidate Numbers."
        ws["A3"].font = instr_font
        ws["A3"].alignment = Alignment(horizontal="left", vertical="center")
        ws.row_dimensions[3].height = 16

        # Row 4: Machine-Readable Metadata Block
        ws.merge_cells(f"A4:{last_col_letter}4")
        ws["A4"] = f"SIMS_REGISTER|BATCH_ID={config.batch_id}|DATES={num_days}|START={start_str}|END={end_str}"
        ws["A4"].font = meta_font
        ws["A4"].alignment = Alignment(horizontal="left", vertical="center")
        ws.row_dimensions[4].height = 14

        # Row 5: Column Headers
        ws.row_dimensions[5].height = 24
        date_start_col_idx = len(base_headers) + 1
        date_end_col_idx = len(base_headers) + len(date_headers)
        present_col_idx = date_end_col_idx + 1
        total_col_idx = date_end_col_idx + 2
        pct_col_idx = date_end_col_idx + 3

        for col_idx, h_text in enumerate(all_headers, 1):
            cell = ws.cell(row=5, column=col_idx, value=h_text)
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = thin_border

            if col_idx <= len(base_headers):
                cell.fill = navy_fill
            elif col_idx <= date_end_col_idx:
                cell.fill = date_h_fill
            else:
                cell.fill = summary_h_fill

        # Rows 6 onwards: Student Data
        current_r = 6
        for s_idx, st in enumerate(students, 1):
            ws.row_dimensions[current_r].height = 20
            col_pos = 1

            # S.No
            c = ws.cell(row=current_r, column=col_pos, value=s_idx)
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.font = data_font
            c.border = thin_border
            col_pos += 1

            # Candidate No
            c = ws.cell(row=current_r, column=col_pos, value=st.candidate_number or "—")
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.font = bold_data_font
            c.border = thin_border
            col_pos += 1

            # Student Name
            c = ws.cell(row=current_r, column=col_pos, value=st.student_name)
            c.alignment = Alignment(horizontal="left", vertical="center")
            c.font = bold_data_font
            c.border = thin_border
            col_pos += 1

            # Mobile
            if config.include_contact_number:
                c = ws.cell(row=current_r, column=col_pos, value=st.mobile_number or "—")
                c.alignment = Alignment(horizontal="center", vertical="center")
                c.font = data_font
                c.border = thin_border
                col_pos += 1

            # Adm Date
            if config.include_admission_date:
                c = ws.cell(row=current_r, column=col_pos, value=st.admission_date or "—")
                c.alignment = Alignment(horizontal="center", vertical="center")
                c.font = data_font
                c.border = thin_border
                col_pos += 1

            # Pending Fees
            if config.include_pending_fees:
                fee_val = f"₹{st.pending_fees:,.2f}" if st.pending_fees > 0 else "₹0.00"
                c = ws.cell(row=current_r, column=col_pos, value=fee_val)
                c.alignment = Alignment(horizontal="right", vertical="center")
                c.font = bold_data_font
                c.border = thin_border
                col_pos += 1

            # Blank Date Cells (Empty by default, never automatically marked absent)
            for _ in dates:
                c = ws.cell(row=current_r, column=col_pos, value="")
                c.alignment = Alignment(horizontal="center", vertical="center")
                c.font = bold_data_font
                c.border = thin_border
                col_pos += 1

            # Dynamic Summary Formulas
            col_start_letter = get_column_letter(date_start_col_idx)
            col_end_letter = get_column_letter(date_end_col_idx)
            present_letter = get_column_letter(present_col_idx)
            total_letter = get_column_letter(total_col_idx)

            # Present Days Formula
            p_formula = f'=COUNTIF({col_start_letter}{current_r}:{col_end_letter}{current_r}, "P") + COUNTIF({col_start_letter}{current_r}:{col_end_letter}{current_r}, "p")'
            c = ws.cell(row=current_r, column=present_col_idx, value=p_formula)
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.font = Font(name="Arial", size=9, bold=True, color="166534")
            c.fill = summary_cell_fill
            c.border = thin_border

            # Total Marked Days Formula
            t_formula = (
                f'=COUNTIF({col_start_letter}{current_r}:{col_end_letter}{current_r}, "P") + COUNTIF({col_start_letter}{current_r}:{col_end_letter}{current_r}, "p") + '
                f'COUNTIF({col_start_letter}{current_r}:{col_end_letter}{current_r}, "A") + COUNTIF({col_start_letter}{current_r}:{col_end_letter}{current_r}, "a")'
            )
            c = ws.cell(row=current_r, column=total_col_idx, value=t_formula)
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.font = bold_data_font
            c.fill = summary_cell_fill
            c.border = thin_border

            # Attendance % Formula
            pct_formula = f'=IF({total_letter}{current_r}>0, ROUND(({present_letter}{current_r}/{total_letter}{current_r})*100, 1), 0.0)'
            c = ws.cell(row=current_r, column=pct_col_idx, value=pct_formula)
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.font = Font(name="Arial", size=9, bold=True, color="1E3A8A")
            c.fill = summary_cell_fill
            c.border = thin_border

            current_r += 1

        # Signatures Area
        current_r += 2
        ws.cell(row=current_r, column=2, value="Coordinator / Faculty Signature: _________________________").font = sub_font
        ws.cell(row=current_r, column=max(total_cols - 4, 4), value="Principal / Admin Stamp: _________________________").font = sub_font

        # Openpyxl Data Validation for 'P' and 'A'
        try:
            col_start_l = get_column_letter(date_start_col_idx)
            col_end_l = get_column_letter(date_end_col_idx)
            dv = DataValidation(type="list", formula1='"P,A"', allow_blank=True)
            ws.add_data_validation(dv)
            dv.add(f"{col_start_l}6:{col_end_l}{max(6, current_r - 3)}")
        except Exception:
            pass

        # Adjust column widths
        for col in ws.columns:
            max_len = 0
            c_letter = get_column_letter(col[0].column)
            for c in col:
                if c.row == 5 and c.value:
                    max_len = max(max_len, len(str(c.value)))
                elif c.row > 5 and c.value and not str(c.value).startswith("="):
                    max_len = max(max_len, len(str(c.value)))
            ws.column_dimensions[c_letter].width = max(max_len + 3, 10)

        # Print Setup: A4 Landscape
        ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0

        # Save workbook
        out_dir = Path(target_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        sanitized_batch = "".join(c if c.isalnum() else "_" for c in batch_name)
        target_path = out_dir / f"SIMS_Attendance_Register_{sanitized_batch}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        wb.save(str(target_path))
        LogService.info(f"Generated offline register Excel: {target_path}", context="AttendanceService")
        return target_path

    # ══════════════════════════════════════════════════════════════════════
    # OFFLINE REGISTER PARSING & RECONCILIATION (.xlsx)
    # ══════════════════════════════════════════════════════════════════════
    def parse_offline_register_excel(
        self,
        file_path: str | Path,
        expected_batch_id: Optional[int] = None,
    ) -> ExcelAttendanceImportPreviewDTO:
        """
        Parses an uploaded offline attendance register (.xlsx), identifies batch,
        students, and date columns, validates markings, and builds a complete diff
        distinguishing New vs Overwritten vs Skipped Blank cells before saving.
        """
        path = Path(file_path)
        if not path.is_file():
            raise ValidationError(f"Attendance register file not found: {path}")

        try:
            wb = openpyxl.load_workbook(str(path), data_only=True)
        except Exception as exc:
            LogService.error(f"Failed to open Excel workbook: {exc}", context="AttendanceService")
            raise ValidationError(f"Could not read Excel file: {exc}")

        ws = wb.active
        if not ws:
            raise ValidationError("Excel workbook contains no active sheets.")

        # 1. Identify Batch ID via Metadata
        detected_batch_id: Optional[int] = None
        for r_idx in range(1, 6):
            cell_v = ws.cell(row=r_idx, column=1).value
            if cell_v and "SIMS_REGISTER|" in str(cell_v):
                m = re.search(r"BATCH_ID=(\d+)", str(cell_v))
                if m:
                    detected_batch_id = int(m.group(1))
                    break

        batch_id = detected_batch_id or expected_batch_id
        if not batch_id:
            raise ValidationError("Could not detect Batch ID from attendance register metadata. Please select batch manually.")

        with self._tx():
            batch_info = self.repository.get_batch_by_id(batch_id)
            if not batch_info:
                raise ValidationError(f"Batch #{batch_id} not found in database.")

            batch_name = batch_info["batch_name"]
            course_name = batch_info["course_name"]
            enrolled_students = self.get_enrolled_students(batch_id)

        # Build student lookup maps for matching
        candidate_map = {s.candidate_number.strip().lower(): s for s in enrolled_students if s.candidate_number}
        name_map = {normalize_name(s.student_name): s for s in enrolled_students}
        id_map = {s.student_id: s for s in enrolled_students}

        # 2. Identify Headers and Date Columns in Row 5 (or Row 4-6 fallback)
        header_row_idx = 5
        date_col_map: Dict[int, str] = {}  # col_idx -> 'YYYY-MM-DD'

        for candidate_row in (5, 4, 6):
            temp_map = {}
            for col_idx in range(1, ws.max_column + 1):
                val = ws.cell(row=candidate_row, column=col_idx).value
                if not val:
                    continue
                # Date object
                if isinstance(val, (datetime, date)):
                    temp_map[col_idx] = val.strftime("%Y-%m-%d")
                    continue
                # Date string regex YYYY-MM-DD
                m = re.search(r"(\d{4}-\d{2}-\d{2})", str(val).strip())
                if m:
                    temp_map[col_idx] = m.group(1)

            if len(temp_map) > 0:
                header_row_idx = candidate_row
                date_col_map = temp_map
                break

        if not date_col_map:
            raise ValidationError("No valid date columns (YYYY-MM-DD) found in spreadsheet headers.")

        detected_dates = sorted(list(set(date_col_map.values())))

        # 3. Fetch existing records for these dates to identify overwrites
        with self._tx():
            existing_marks = self.repository.get_session_marks_for_dates(batch_id, detected_dates)

        # 4. Iterate over student rows
        diff_items: List[ExcelAttendanceCellDiffDTO] = []
        new_cnt = 0
        overwrite_cnt = 0
        unchanged_cnt = 0
        blank_cnt = 0
        invalid_cnt = 0
        error_msgs = []
        total_eval = 0

        for r_idx in range(header_row_idx + 1, ws.max_row + 1):
            c1 = ws.cell(row=r_idx, column=1).value
            c2 = ws.cell(row=r_idx, column=2).value
            c3 = ws.cell(row=r_idx, column=3).value

            # Stop on footer or completely empty row
            if not c1 and not c2 and not c3:
                continue
            if c2 and any(k in str(c2).lower() for k in ["signature", "stamp", "coordinator", "principal"]):
                break

            # Match student
            matched_student: Optional[BatchStudentDTO] = None
            if c2 and str(c2).strip().lower() in candidate_map:
                matched_student = candidate_map[str(c2).strip().lower()]
            elif c3 and normalize_name(str(c3)) in name_map:
                matched_student = name_map[normalize_name(str(c3))]
            elif c1 and str(c1).strip().isdigit() and int(str(c1).strip()) in id_map:
                matched_student = id_map[int(str(c1).strip())]

            if not matched_student:
                error_msgs.append(f"Row {r_idx}: Unmatched student '{c3}' (Candidate No: {c2})")
                continue

            # Evaluate each date cell
            for col_i, d_str in date_col_map.items():
                total_eval += 1
                cell_raw = ws.cell(row=r_idx, column=col_i).value

                # Invariant: Blank cells are NEVER marked absent. They are skipped.
                if cell_raw is None or str(cell_raw).strip() == "":
                    blank_cnt += 1
                    continue

                val_clean = str(cell_raw).strip().upper()

                # Convention evaluation: P / PRESENT / 1 / ✓ -> PRESENT, A / ABSENT / 0 / ✗ -> ABSENT
                if val_clean in ("P", "PRESENT", "1", "✓", "✔"):
                    status = "PRESENT"
                elif val_clean in ("A", "ABSENT", "0", "✗", "X"):
                    status = "ABSENT"
                else:
                    invalid_cnt += 1
                    diff_items.append(
                        ExcelAttendanceCellDiffDTO(
                            student_id=matched_student.student_id,
                            student_name=matched_student.student_name,
                            candidate_number=matched_student.candidate_number,
                            session_date=d_str,
                            mark=val_clean,
                            change_type="INVALID",
                            error_reason=f"Unrecognized attendance convention '{val_clean}' (Expected P or A)",
                        )
                    )
                    continue

                existing_st = existing_marks.get((matched_student.student_id, d_str))

                if existing_st is None:
                    change_type = "NEW"
                    new_cnt += 1
                elif existing_st == status:
                    change_type = "UNCHANGED"
                    unchanged_cnt += 1
                else:
                    change_type = "OVERWRITE"
                    overwrite_cnt += 1

                diff_items.append(
                    ExcelAttendanceCellDiffDTO(
                        student_id=matched_student.student_id,
                        student_name=matched_student.student_name,
                        candidate_number=matched_student.candidate_number,
                        session_date=d_str,
                        mark=status,
                        change_type=change_type,
                        existing_status=existing_st,
                    )
                )

        requires_pin = overwrite_cnt > 0

        return ExcelAttendanceImportPreviewDTO(
            file_path=str(path),
            batch_id=batch_id,
            batch_name=batch_name,
            course_name=course_name,
            detected_dates=detected_dates,
            total_cells_evaluated=total_eval,
            new_marks_count=new_cnt,
            overwrite_marks_count=overwrite_cnt,
            unchanged_marks_count=unchanged_cnt,
            skipped_blank_count=blank_cnt,
            invalid_cells_count=invalid_cnt,
            diff_items=diff_items,
            requires_admin_pin=requires_pin,
            error_messages=error_msgs,
        )

    # ══════════════════════════════════════════════════════════════════════
    # COMMIT OFFLINE REGISTER IMPORT
    # ══════════════════════════════════════════════════════════════════════
    def commit_offline_register_import(
        self,
        batch_id: int,
        import_preview: ExcelAttendanceImportPreviewDTO,
        admin_pin: Optional[str] = None,
        recorded_by: str = "admin",
    ) -> int:
        """
        Commits verified offline register import to the database within an atomic transaction.
        Enforces Admin PIN step-up verification if any historical sessions are overwritten.
        """
        # Step-up verification for overwrites
        if import_preview.requires_admin_pin:
            if not admin_pin or not self.verify_admin_pin(admin_pin):
                raise ValidationError("Administrator PIN is required to authorize overwriting existing attendance records.")

        # Filter items to commit (NEW and OVERWRITE only)
        items_to_save = [it for it in import_preview.diff_items if it.change_type in ("NEW", "OVERWRITE")]
        if not items_to_save:
            return 0

        # Group by date
        date_groups: Dict[str, List[ExcelAttendanceCellDiffDTO]] = {}
        for it in items_to_save:
            date_groups.setdefault(it.session_date, []).append(it)

        total_saved = 0
        with self._tx():
            for s_date, items in date_groups.items():
                session_id = self.repository.upsert_session(
                    batch_id=batch_id,
                    session_date=s_date,
                    mode=AttendanceMode.OFFLINE.value,
                    recorded_by=f"{recorded_by} (excel_import)",
                    remarks=f"Imported from offline register {Path(import_preview.file_path).name}",
                )

                prepared_records = [
                    {
                        "student_id": it.student_id,
                        "status": it.mark,
                        "marking_method": MarkingMethod.MANUAL_EDIT.value,
                        "confidence_score": 1.0,
                        "remarks": f"Excel Register ({it.change_type})",
                    }
                    for it in items
                ]

                self.repository.save_records(session_id, batch_id, prepared_records)
                total_saved += len(prepared_records)

        LogService.info(
            f"Successfully committed {total_saved} marks across {len(date_groups)} dates for batch {batch_id}",
            context="AttendanceService",
        )
        return total_saved

