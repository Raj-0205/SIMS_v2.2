# infrastructure/pdf/exporter.py

from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence
import cairo

__all__ = ["PDFExporter"]


class PDFExporter:
    """
    Renders structured domain data into professional vector PDF reports using Cairo.
    Supports multi-page tables, headers, footers, and metadata.
    """

    # A4 Landscape Dimensions in Points (72 dpi)
    PAGE_WIDTH = 841.89
    PAGE_HEIGHT = 595.28
    MARGIN_LEFT = 40.0
    MARGIN_RIGHT = 40.0
    MARGIN_TOP = 45.0
    MARGIN_BOTTOM = 45.0

    @classmethod
    def export_table_pdf(
        cls,
        title: str,
        headers: Sequence[str],
        column_widths: Sequence[float],
        rows: Sequence[Sequence[Any]],
        output_path: Path | str,
        subtitle: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Path:
        """
        Renders a multi-page tabular PDF report.
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        surface = cairo.PDFSurface(str(path), cls.PAGE_WIDTH, cls.PAGE_HEIGHT)
        cr = cairo.Context(surface)

        content_width = cls.PAGE_WIDTH - cls.MARGIN_LEFT - cls.MARGIN_RIGHT
        total_col_weight = sum(column_widths)
        scaled_widths = [(w / total_col_weight) * content_width for w in column_widths]

        row_height = 20.0
        header_height = 24.0
        start_y = cls.MARGIN_TOP + 50.0
        max_y = cls.PAGE_HEIGHT - cls.MARGIN_BOTTOM - 20.0

        current_y = start_y
        page_number = 1
        total_rows = len(rows)

        def draw_page_decorations(page_num: int) -> None:
            # Header
            cr.save()
            cr.set_source_rgb(0.12, 0.23, 0.36)  # Deep Slate Navy
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(16.0)
            cr.move_to(cls.MARGIN_LEFT, cls.MARGIN_TOP)
            cr.show_text(title)

            # Subtitle / Timestamp
            cr.set_source_rgb(0.45, 0.50, 0.58)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(9.0)
            sub_text = subtitle or f"Generated on {datetime.now().strftime('%d-%b-%Y %H:%M:%S')} | Total Records: {total_rows}"
            cr.move_to(cls.MARGIN_LEFT, cls.MARGIN_TOP + 14.0)
            cr.show_text(sub_text)

            # Metadata info if present
            if metadata:
                meta_str = " | ".join(f"{k}: {v}" for k, v in metadata.items())
                cr.move_to(cls.MARGIN_LEFT, cls.MARGIN_TOP + 26.0)
                cr.show_text(meta_str)

            # Footer Divider & Page Number
            cr.set_line_width(0.5)
            cr.set_source_rgb(0.80, 0.83, 0.88)
            cr.move_to(cls.MARGIN_LEFT, cls.PAGE_HEIGHT - cls.MARGIN_BOTTOM + 5.0)
            cr.line_to(cls.PAGE_WIDTH - cls.MARGIN_RIGHT, cls.PAGE_HEIGHT - cls.MARGIN_BOTTOM + 5.0)
            cr.stroke()

            cr.set_source_rgb(0.50, 0.55, 0.60)
            cr.set_font_size(8.5)
            footer_text = f"SIMS v2.2 Enterprise ERP  •  Page {page_num}"
            cr.move_to(cls.MARGIN_LEFT, cls.PAGE_HEIGHT - cls.MARGIN_BOTTOM + 18.0)
            cr.show_text(footer_text)
            cr.restore()

        def draw_table_headers(y_pos: float) -> float:
            cr.save()
            # Header background
            cr.set_source_rgb(0.92, 0.94, 0.98)
            cr.rectangle(cls.MARGIN_LEFT, y_pos, content_width, header_height)
            cr.fill()

            # Header border
            cr.set_line_width(0.75)
            cr.set_source_rgb(0.75, 0.80, 0.88)
            cr.rectangle(cls.MARGIN_LEFT, y_pos, content_width, header_height)
            cr.stroke()

            # Text
            cr.set_source_rgb(0.15, 0.20, 0.30)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(9.5)

            cur_x = cls.MARGIN_LEFT
            for i, h in enumerate(headers):
                w = scaled_widths[i]
                cr.move_to(cur_x + 5.0, y_pos + 15.0)
                cr.show_text(str(h))
                cur_x += w

            cr.restore()
            return y_pos + header_height

        # Draw First Page Header
        draw_page_decorations(page_number)
        current_y = draw_table_headers(current_y)

        # Draw Data Rows
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(8.5)

        for row_idx, row in enumerate(rows):
            if current_y + row_height > max_y:
                # New Page
                surface.show_page()
                page_number += 1
                draw_page_decorations(page_number)
                current_y = draw_table_headers(start_y)
                cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
                cr.set_font_size(8.5)

            # Row background
            if row_idx % 2 == 1:
                cr.set_source_rgb(0.98, 0.98, 0.99)
                cr.rectangle(cls.MARGIN_LEFT, current_y, content_width, row_height)
                cr.fill()

            # Cell text & borders
            cur_x = cls.MARGIN_LEFT
            cr.set_source_rgb(0.20, 0.25, 0.30)

            for col_idx, cell in enumerate(row):
                w = scaled_widths[col_idx]
                cell_text = str(cell) if cell is not None else "—"
                # Truncate text if too long
                if len(cell_text) > 28:
                    cell_text = cell_text[:25] + "..."

                cr.move_to(cur_x + 5.0, current_y + 13.5)
                cr.show_text(cell_text)
                cur_x += w

            # Row bottom border
            cr.set_line_width(0.3)
            cr.set_source_rgb(0.88, 0.90, 0.93)
            cr.move_to(cls.MARGIN_LEFT, current_y + row_height)
            cr.line_to(cls.PAGE_WIDTH - cls.MARGIN_RIGHT, current_y + row_height)
            cr.stroke()

            current_y += row_height

        surface.finish()
        return path
