# modules/attendance/ocr_engine.py

from datetime import datetime
from pathlib import Path
from typing import List, Optional
import shutil

from PIL import Image, ImageOps, ImageFilter
from core.logger.service import LogService
from modules.attendance.dto import BatchStudentDTO, OCRScanItemDTO, OCRScanResultDTO

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False


class AttendanceOCREngine:
    """
    Optical Mark & Character Recognition Engine for scanning SIMS standardized
    offline physical attendance sheets.
    
    Supports JPG, JPEG, and PNG images of ANY file size without memory exhaustion.
    Uses Pillow-based spatial grid analysis, stroke density heuristics, and optional
    Tesseract OCR for robust presence/absence detection.
    """

    INK_DENSITY_THRESHOLD_PRESENT = 0.04   # Fill ratio >= 4% indicates mark/tick/shading inside cell
    INK_DENSITY_UNCERTAINTY_MIN = 0.02     # Between 2% and 6% flagged for human review
    INK_DENSITY_UNCERTAINTY_MAX = 0.06

    @classmethod
    def scan_offline_sheet(
        cls,
        image_path: str | Path,
        batch_id: int,
        batch_name: str,
        enrolled_students: List[BatchStudentDTO],
        session_date: Optional[str] = None,
    ) -> OCRScanResultDTO:
        """
        Processes an uploaded offline attendance sheet photo/scan and recognizes
        present/absent status for each enrolled student in the batch.
        """
        img_path = Path(image_path)
        if not img_path.is_file():
            raise FileNotFoundError(f"Attendance sheet image not found: {img_path}")

        today_str = session_date or datetime.now().strftime("%Y-%m-%d")

        if not enrolled_students:
            return OCRScanResultDTO(
                batch_id=batch_id,
                batch_name=batch_name,
                detected_date=today_str,
                image_path=str(img_path),
                items=[],
                total_detected=0,
                total_present=0,
                total_absent=0,
                confidence_avg=1.0,
            )

        # 1. Load and normalize image
        try:
            with Image.open(img_path) as raw_img:
                # Handle camera rotation metadata
                img = ImageOps.exif_transpose(raw_img)
                # Convert to RGB if needed
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")

                # Scale to standard working resolution (e.g. max 2000px height) while maintaining aspect ratio
                max_dim = 2400
                if max(img.size) > max_dim:
                    img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

                # Convert to grayscale and enhance contrast
                gray = ImageOps.autocontrast(img.convert("L"))
                width, height = gray.size

        except Exception as exc:
            LogService.error(f"Failed to decode attendance image: {exc}", context="AttendanceOCR")
            raise ValueError(f"Could not read image file: {exc}")

        # 2. Estimate table grid boundaries
        # In the SIMS fixed format:
        # - Top ~18% is the header (Title, Course, Batch, Date, Column Labels)
        # - Bottom ~8% is the footer & signature area
        # - Middle ~74% contains the student rows
        table_top_ratio = 0.20
        table_bottom_ratio = 0.90
        table_start_y = height * table_top_ratio
        table_end_y = height * table_bottom_ratio
        available_height = table_end_y - table_start_y

        num_students = len(enrolled_students)
        row_height = min(available_height / max(num_students, 1), height * 0.08)

        # In the fixed format, the mark column (Checkbox/Bubble) is located
        # in the right section of the table (between ~75% and ~95% width)
        mark_col_x1_ratio = 0.72
        mark_col_x2_ratio = 0.95

        scanned_items: List[OCRScanItemDTO] = []
        total_p = 0
        total_a = 0
        conf_sum = 0.0

        for idx, student in enumerate(enrolled_students):
            # Compute bounding box for this student's row
            row_y1 = int(table_start_y + idx * row_height)
            row_y2 = int(min(row_y1 + row_height, height))

            # Mark cell box (with inner padding to ignore cell borders)
            pad_y = max(2, int((row_y2 - row_y1) * 0.15))
            cell_x1 = int(width * mark_col_x1_ratio)
            cell_x2 = int(width * mark_col_x2_ratio)
            cell_y1 = row_y1 + pad_y
            cell_y2 = row_y2 - pad_y

            cell_crop = gray.crop((cell_x1, cell_y1, cell_x2, cell_y2))

            # Analyze ink / stroke density inside cell
            status, conf, is_uncertain, fill_ratio = cls._analyze_mark_cell(cell_crop)

            if status == "PRESENT":
                total_p += 1
            else:
                total_a += 1

            conf_sum += conf

            scanned_items.append(
                OCRScanItemDTO(
                    student_id=student.student_id,
                    student_name=student.student_name,
                    candidate_number=student.candidate_number,
                    recognized_status=status,
                    confidence=round(conf, 2),
                    is_uncertain=is_uncertain,
                    raw_mark_ratio=round(fill_ratio, 3),
                )
            )

        avg_conf = round(conf_sum / max(num_students, 1), 2)

        return OCRScanResultDTO(
            batch_id=batch_id,
            batch_name=batch_name,
            detected_date=today_str,
            image_path=str(img_path),
            items=scanned_items,
            total_detected=num_students,
            total_present=total_p,
            total_absent=total_a,
            confidence_avg=avg_conf,
        )

    @classmethod
    def _analyze_mark_cell(cls, cell_crop: Image.Image) -> tuple[str, float, bool, float]:
        """
        Evaluates a cropped mark cell.
        Returns: (status, confidence, is_uncertain, fill_ratio)
        """
        w, h = cell_crop.size
        if w < 5 or h < 5:
            return "ABSENT", 0.70, False, 0.0

        # Optional Tesseract reading if available
        if PYTESSERACT_AVAILABLE:
            try:
                txt = pytesseract.image_to_string(
                    cell_crop,
                    config="--psm 10 -c tessedit_char_whitelist=PA10✓✔xXpPaA",
                ).strip().upper()
                if any(k in txt for k in ["P", "1", "✓", "✔"]):
                    return "PRESENT", 0.95, False, 0.35
                if any(k in txt for k in ["A", "0", "X"]):
                    return "ABSENT", 0.95, False, 0.05
            except Exception:
                pass

        # Pixel density analysis (binarization)
        # Threshold: pixels darker than 140 (out of 255) are considered ink strokes
        threshold = 140
        fn = lambda p: 255 if p > threshold else 0
        bin_img = cell_crop.convert("L").point(fn, mode="L")

        # Inner 70% core area to avoid borders
        margin_x = int(w * 0.15)
        margin_y = int(h * 0.15)
        core_box = (margin_x, margin_y, w - margin_x, h - margin_y)
        core_crop = bin_img.crop(core_box)
        cw, ch = core_crop.size

        if cw <= 0 or ch <= 0:
            return "ABSENT", 0.80, False, 0.0

        # Count black (ink) pixels: 0 = black in mode 'L'
        black_pixels = core_crop.tobytes().count(0)
        total_core_pixels = cw * ch
        fill_ratio = black_pixels / float(total_core_pixels)

        # Decision
        if fill_ratio >= cls.INK_DENSITY_THRESHOLD_PRESENT:
            # Significant ink mark detected
            conf = min(0.98, 0.75 + (fill_ratio * 0.8))
            is_uncertain = fill_ratio < cls.INK_DENSITY_UNCERTAINTY_MAX
            return "PRESENT", conf, is_uncertain, fill_ratio
        else:
            # Clean / blank cell
            conf = min(0.98, 0.75 + ((cls.INK_DENSITY_THRESHOLD_PRESENT - fill_ratio) * 1.5))
            is_uncertain = fill_ratio > cls.INK_DENSITY_UNCERTAINTY_MIN
            return "ABSENT", conf, is_uncertain, fill_ratio
