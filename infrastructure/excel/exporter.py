# infrastructure/excel/exporter.py

from __future__ import annotations
import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

try:
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

__all__ = ["ExcelExporter"]


class ExcelExporter:
    """
    Exports structured data into Microsoft Excel (.xlsx) and clean CSV formats.
    Provides professional typography, Navy Blue ERP styling, auto-fitted column widths,
    numeric/currency alignment, mobile number preservation, and automated totals rows.
    """

    @classmethod
    def export_to_csv(
        cls,
        headers: Sequence[str],
        rows: Sequence[Sequence[Any]],
        output_path: Path | str,
        metadata: Optional[Mapping[str, Any]] = None,
        include_metadata_comments: bool = False,
    ) -> Path:
        """
        Writes data to a clean UTF-8 with BOM CSV file for universal spreadsheet compatibility.
        Headers start on Row 1 for seamless data import without column offset.
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, mode="w", newline="", encoding="utf-8-sig") as csvfile:
            writer = csv.writer(csvfile, quoting=csv.QUOTE_ALL)

            if include_metadata_comments and metadata:
                for k, v in metadata.items():
                    writer.writerow([f"# {k}: {v}"])
                writer.writerow([])

            # Primary header row
            writer.writerow(list(headers))

            # Data rows
            for row in rows:
                clean_row = []
                for cell in row:
                    if cell is None:
                        clean_row.append("")
                    else:
                        clean_row.append(str(cell))
                writer.writerow(clean_row)

        return path

    @classmethod
    def export_to_excel(
        cls,
        headers: Sequence[str],
        rows: Sequence[Sequence[Any]],
        output_path: Path | str,
        sheet_name: str = "Report",
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        include_totals: bool = True,
    ) -> Path:
        """
        Generates a professionally styled Microsoft Excel (.xlsx) workbook with:
        - Institute branding header
        - Bold Navy Blue (#1E3A8A) column headers with white text
        - Auto-fitted column widths
        - Alternating row striping (#F8FAFC)
        - Data-type aware alignment (Numbers right, Dates/Codes center, Names left)
        - Native currency formatting (allowing Excel SUM and calculations)
        - Text-preserved mobile numbers (preventing scientific notation / truncated zeros)
        - Bold Summary / Totals Row
        """
        if not HAS_OPENPYXL:
            # Fallback to CSV if openpyxl is not present
            csv_path = Path(output_path).with_suffix(".csv")
            return cls.export_to_csv(headers, rows, csv_path, metadata)

        path = Path(output_path)
        if path.suffix.lower() != ".xlsx":
            path = path.with_suffix(".xlsx")
        path.parent.mkdir(parents=True, exist_ok=True)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = sheet_name[:31]  # Excel limits sheet names to 31 chars

        # --- Theme Styling Constants ---
        NAVY_HEADER_FILL = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        ZEBRA_FILL = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
        TOTALS_FILL = PatternFill(start_color="EFF6FF", end_color="EFF6FF", fill_type="solid")

        FONT_TITLE = Font(name="Calibri", size=15, bold=True, color="1E3A8A")
        FONT_SUBTITLE = Font(name="Calibri", size=10, italic=True, color="64748B")
        FONT_HEADER = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        FONT_BODY = Font(name="Calibri", size=11, color="0F172A")
        FONT_TOTALS = Font(name="Calibri", size=11, bold=True, color="1E3A8A")

        BORDER_THIN = Border(
            left=Side(style="thin", color="E2E8F0"),
            right=Side(style="thin", color="E2E8F0"),
            top=Side(style="thin", color="E2E8F0"),
            bottom=Side(style="thin", color="E2E8F0"),
        )
        BORDER_TOTALS = Border(
            left=Side(style="thin", color="CBD5E1"),
            right=Side(style="thin", color="CBD5E1"),
            top=Side(style="thin", color="1E3A8A"),
            bottom=Side(style="double", color="1E3A8A"),
        )

        ALIGN_LEFT = Alignment(horizontal="left", vertical="center")
        ALIGN_CENTER = Alignment(horizontal="center", vertical="center")
        ALIGN_RIGHT = Alignment(horizontal="right", vertical="center")
        ALIGN_HEADER = Alignment(horizontal="center", vertical="center", wrap_text=True)

        current_row = 1
        num_cols = max(len(headers), 1)

        # 1. Optional Title Banner
        if title:
            ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=num_cols)
            title_cell = ws.cell(row=current_row, column=1, value=title)
            title_cell.font = FONT_TITLE
            title_cell.alignment = ALIGN_LEFT
            ws.row_dimensions[current_row].height = 26
            current_row += 1

            sub = subtitle or f"Generated on: {datetime.now().strftime('%d-%b-%Y at %I:%M %p')}"
            ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=num_cols)
            sub_cell = ws.cell(row=current_row, column=1, value=sub)
            sub_cell.font = FONT_SUBTITLE
            sub_cell.alignment = ALIGN_LEFT
            ws.row_dimensions[current_row].height = 18
            current_row += 1

            # Blank spacer
            current_row += 1

        # 2. Header Row
        header_row_idx = current_row
        ws.row_dimensions[header_row_idx].height = 28

        # Identify column categories for intelligent formatting
        currency_col_indices: set[int] = set()
        mobile_col_indices: set[int] = set()
        date_col_indices: set[int] = set()
        code_col_indices: set[int] = set()

        for col_idx, h in enumerate(headers, start=1):
            cell = ws.cell(row=header_row_idx, column=col_idx, value=str(h).strip())
            cell.font = FONT_HEADER
            cell.fill = NAVY_HEADER_FILL
            cell.alignment = ALIGN_HEADER
            cell.border = BORDER_THIN

            h_upper = str(h).upper()
            if any(term in h_upper for term in ("FEE", "AMOUNT", "INSTALLMENT", "PAID", "PENDING", "DISCOUNT")):
                currency_col_indices.add(col_idx)
            elif any(term in h_upper for term in ("MOB", "PHONE", "CONTACT", "AADHAAR")):
                mobile_col_indices.add(col_idx)
            elif any(term in h_upper for term in ("DATE", "DOB")):
                date_col_indices.add(col_idx)
            elif any(term in h_upper for term in ("SR.NO", "ID", "STATUS", "CODE", "YEAR", "GENDER")):
                code_col_indices.add(col_idx)

        current_row += 1
        data_start_row = current_row

        # Track numeric column sums for summary row
        column_sums: dict[int, float] = {c: 0.0 for c in currency_col_indices}
        has_any_numeric_value = False

        # 3. Data Rows
        for row_idx, row in enumerate(rows):
            ws.row_dimensions[current_row].height = 20
            is_odd = row_idx % 2 == 1
            row_fill = ZEBRA_FILL if is_odd else None

            for col_idx, raw_val in enumerate(row, start=1):
                cell = ws.cell(row=current_row, column=col_idx)
                cell.font = FONT_BODY
                cell.border = BORDER_THIN
                if row_fill:
                    cell.fill = row_fill

                if raw_val is None:
                    cell.value = "—"
                    cell.alignment = ALIGN_CENTER
                    continue

                # Currency / Financial parsing
                if col_idx in currency_col_indices:
                    num_val = cls._parse_numeric(raw_val)
                    if num_val is not None:
                        cell.value = num_val
                        cell.number_format = '"₹"#,##0.00'
                        cell.alignment = ALIGN_RIGHT
                        column_sums[col_idx] += num_val
                        has_any_numeric_value = True
                    else:
                        cell.value = str(raw_val)
                        cell.alignment = ALIGN_RIGHT if str(raw_val) != "—" else ALIGN_CENTER

                # Mobile & Identity numbers (explicit text preservation)
                elif col_idx in mobile_col_indices:
                    clean_str = str(raw_val).strip()
                    cell.value = clean_str
                    cell.number_format = "@"
                    cell.alignment = ALIGN_CENTER

                # Date / Timestamp
                elif col_idx in date_col_indices:
                    cell.value = str(raw_val)[:10] if str(raw_val) else "—"
                    cell.alignment = ALIGN_CENTER

                # Codes, Sequence Numbers, Status
                elif col_idx in code_col_indices:
                    if isinstance(raw_val, (int, float)) and "SR.NO" in str(headers[col_idx - 1]).upper():
                        cell.value = int(raw_val)
                    else:
                        cell.value = str(raw_val)
                    cell.alignment = ALIGN_CENTER

                # General text (Names, Addresses, Notes, Courses)
                else:
                    cell.value = str(raw_val)
                    cell.alignment = ALIGN_LEFT

            current_row += 1

        data_end_row = current_row - 1

        # 4. Summary / Totals Row
        if include_totals and rows and has_any_numeric_value:
            ws.row_dimensions[current_row].height = 24
            totals_row_idx = current_row

            # Find first non-numeric column to place the "TOTAL" label
            first_curr_col = min(currency_col_indices) if currency_col_indices else 1
            label_col = max(1, first_curr_col - 1)

            for col_idx in range(1, num_cols + 1):
                cell = ws.cell(row=totals_row_idx, column=col_idx)
                cell.font = FONT_TOTALS
                cell.fill = TOTALS_FILL
                cell.border = BORDER_TOTALS

                if col_idx == label_col:
                    cell.value = "TOTAL / SUMMARY"
                    cell.alignment = ALIGN_RIGHT
                elif col_idx in currency_col_indices:
                    col_letter = get_column_letter(col_idx)
                    cell.value = f"=SUM({col_letter}{data_start_row}:{col_letter}{data_end_row})"
                    cell.number_format = '"₹"#,##0.00'
                    cell.alignment = ALIGN_RIGHT
                else:
                    cell.value = ""

            current_row += 1

        # 5. Auto-Fit Column Widths
        for col_idx in range(1, num_cols + 1):
            col_letter = get_column_letter(col_idx)
            max_len = 0
            for r in range(header_row_idx, current_row):
                val = ws.cell(row=r, column=col_idx).value
                if val:
                    # Treat formulas as ~12 chars
                    v_str = str(val) if not str(val).startswith("=") else "₹ 999,999.00"
                    max_len = max(max_len, len(v_str))

            # Set padded width, with minimum 12 and maximum 50
            ws.column_dimensions[col_letter].width = min(max(max_len + 4, 12), 50)

        # 6. Freeze Panes below header
        ws.freeze_panes = ws.cell(row=header_row_idx + 1, column=1)

        wb.save(path)
        return path

    @staticmethod
    def _parse_numeric(val: Any) -> Optional[float]:
        """Extracts float value from numeric or formatted currency string."""
        if isinstance(val, (int, float)):
            return float(val)
        if not val or not isinstance(val, str):
            return None
        clean = re.sub(r"[^\d.-]", "", val)
        if not clean or clean in ("-", "."):
            return None
        try:
            return float(clean)
        except ValueError:
            return None
