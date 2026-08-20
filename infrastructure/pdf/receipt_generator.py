# infrastructure/pdf/receipt_generator.py

from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Optional
import cairo

__all__ = ["ReceiptPDFGenerator"]


class ReceiptPDFGenerator:
    """
    Renders official vector PDF fee payment receipts using Cairo.
    Follows official Sudharm Infotech enterprise branding and layout.
    """

    # A5 Portrait Dimensions in Points (72 dpi) - 419.53 x 595.28 pt
    PAGE_WIDTH = 419.53
    PAGE_HEIGHT = 595.28
    MARGIN_LEFT = 28.0
    MARGIN_RIGHT = 28.0
    MARGIN_TOP = 28.0
    MARGIN_BOTTOM = 28.0

    @classmethod
    def generate_receipt_pdf(
        cls,
        receipt_data: Mapping[str, Any],
        output_path: Path | str,
        institute_profile: Optional[Mapping[str, str]] = None,
    ) -> Path:
        """
        Generates an official vector PDF payment receipt.
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        surface = cairo.PDFSurface(str(path), cls.PAGE_WIDTH, cls.PAGE_HEIGHT)
        cr = cairo.Context(surface)

        profile = institute_profile or {}
        inst_name = profile.get("institute_name", "Sudharm Infotech")
        contact_person = profile.get("contact_person", "Hemant Mahale")
        contact_mob = profile.get("contact_mobile", "9271226772")
        alc_code = profile.get("alc_code", "57210242")
        addr1 = profile.get("address_line1", "Renuka Complex, 3rd Floor,")
        addr2 = profile.get("address_line2", "Opp. Market Yard, Chandwad - 423101")

        content_width = cls.PAGE_WIDTH - cls.MARGIN_LEFT - cls.MARGIN_RIGHT

        # ── Outer Border ──
        cr.set_source_rgb(0.85, 0.88, 0.92)
        cr.set_line_width(1.0)
        cr.rectangle(cls.MARGIN_LEFT - 6, cls.MARGIN_TOP - 6, content_width + 12, cls.PAGE_HEIGHT - cls.MARGIN_TOP - cls.MARGIN_BOTTOM + 12)
        cr.stroke()

        # ── 1. HEADER & BRANDING ──
        y = cls.MARGIN_TOP + 12.0
        
        # Center Name
        cr.set_source_rgb(0.12, 0.23, 0.36)  # Deep Navy
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(17.0)
        extents = cr.text_extents(inst_name)
        cr.move_to(cls.MARGIN_LEFT + (content_width - extents.width) / 2.0, y)
        cr.show_text(inst_name)

        # Contact & ALC Subtitle
        y += 15.0
        cr.set_source_rgb(0.35, 0.40, 0.48)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(9.0)
        sub1 = f"{contact_person}  •  Mob: {contact_mob}  •  ALC Code: {alc_code}"
        extents1 = cr.text_extents(sub1)
        cr.move_to(cls.MARGIN_LEFT + (content_width - extents1.width) / 2.0, y)
        cr.show_text(sub1)

        # Address
        y += 12.0
        sub2 = f"{addr1} {addr2}"
        extents2 = cr.text_extents(sub2)
        cr.move_to(cls.MARGIN_LEFT + (content_width - extents2.width) / 2.0, y)
        cr.show_text(sub2)

        # Receipt Title Badge
        y += 18.0
        badge_h = 20.0
        cr.set_source_rgb(0.15, 0.35, 0.65)
        cr.rectangle(cls.MARGIN_LEFT, y, content_width, badge_h)
        cr.fill()

        cr.set_source_rgb(1.0, 1.0, 1.0)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(10.5)
        title_text = "FEE PAYMENT RECEIPT"
        t_extents = cr.text_extents(title_text)
        cr.move_to(cls.MARGIN_LEFT + (content_width - t_extents.width) / 2.0, y + 14.0)
        cr.show_text(title_text)

        # ── 2. RECEIPT META BAR ──
        y += badge_h + 14.0
        receipt_no = str(receipt_data.get("receipt_number", "N/A"))
        raw_date = receipt_data.get("receipt_date") or datetime.now().strftime("%d-%b-%Y %I:%M %p")
        
        cr.set_source_rgb(0.20, 0.25, 0.32)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(9.5)
        cr.move_to(cls.MARGIN_LEFT, y)
        cr.show_text(f"Receipt No: {receipt_no}")

        d_text = f"Date: {raw_date}"
        d_extents = cr.text_extents(d_text)
        cr.move_to(cls.MARGIN_LEFT + content_width - d_extents.width, y)
        cr.show_text(d_text)

        # Divider
        y += 8.0
        cr.set_source_rgb(0.85, 0.88, 0.92)
        cr.set_line_width(0.8)
        cr.move_to(cls.MARGIN_LEFT, y)
        cr.line_to(cls.MARGIN_LEFT + content_width, y)
        cr.stroke()

        # ── 3. STUDENT & COURSE DETAILS ──
        y += 16.0
        student_name = str(receipt_data.get("student_name", "N/A"))
        student_id = str(receipt_data.get("student_id", "N/A"))
        adm_no = str(receipt_data.get("candidate_number") or receipt_data.get("admission_id", "N/A"))
        course_name = str(receipt_data.get("course_name", "N/A"))

        fields_left = [
            ("Student Name:", student_name),
            ("Student ID:", f"#{student_id}"),
        ]
        fields_right = [
            ("Candidate No:", adm_no),
            ("Course:", course_name),
        ]

        left_x = cls.MARGIN_LEFT
        mid_x = cls.MARGIN_LEFT + (content_width / 2.0) + 10.0

        for (label, val) in fields_left:
            cr.set_source_rgb(0.45, 0.50, 0.58)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(9.0)
            cr.move_to(left_x, y)
            cr.show_text(label)

            cr.set_source_rgb(0.12, 0.18, 0.25)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.move_to(left_x + 75.0, y)
            cr.show_text(val[:28])
            y += 14.0

        y -= 28.0  # Reset for right column
        for (label, val) in fields_right:
            cr.set_source_rgb(0.45, 0.50, 0.58)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(9.0)
            cr.move_to(mid_x, y)
            cr.show_text(label)

            cr.set_source_rgb(0.12, 0.18, 0.25)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.move_to(mid_x + 75.0, y)
            cr.show_text(val[:24])
            y += 14.0

        # ── 4. FINANCIAL BREAKDOWN TABLE ──
        y += 12.0
        tbl_h = 20.0
        cr.set_source_rgb(0.94, 0.96, 0.98)
        cr.rectangle(cls.MARGIN_LEFT, y, content_width, tbl_h)
        cr.fill()

        cr.set_source_rgb(0.20, 0.25, 0.35)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(9.0)
        cr.move_to(cls.MARGIN_LEFT + 8.0, y + 13.5)
        cr.show_text("Payment Description")

        cr.move_to(cls.MARGIN_LEFT + content_width - 80.0, y + 13.5)
        cr.show_text("Amount (INR)")

        # Table Rows
        total_fee = float(receipt_data.get("total_course_fee", 0.0))
        amount_paid = float(receipt_data.get("amount_paid", 0.0))
        total_paid = float(receipt_data.get("total_paid_till_now", amount_paid))
        pending_amt = float(receipt_data.get("pending_amount", max(0.0, total_fee - total_paid)))
        inst_no = int(receipt_data.get("installment_number", 1))
        pay_mode = str(receipt_data.get("payment_mode", "CASH")).upper()
        collector = str(receipt_data.get("collector_name", "Hemant Mahale (Sir)"))

        rows = [
            (f"Fee Payment (Installment {inst_no:02d}) via {pay_mode}", f"Rs. {amount_paid:,.2f}"),
            ("Total Course Agreed Fee", f"Rs. {total_fee:,.2f}"),
            ("Total Fee Paid Till Date", f"Rs. {total_paid:,.2f}"),
            ("Remaining Balance / Pending Amount", f"Rs. {pending_amt:,.2f}"),
        ]

        y += tbl_h
        for idx, (desc, amt_str) in enumerate(rows):
            y += 18.0
            # Highlight amount paid row
            if idx == 0:
                cr.set_source_rgb(0.92, 0.98, 0.94)  # Light Green
                cr.rectangle(cls.MARGIN_LEFT, y - 13.0, content_width, 18.0)
                cr.fill()
                cr.set_source_rgb(0.08, 0.50, 0.25)
                cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            else:
                cr.set_source_rgb(0.25, 0.30, 0.38)
                cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)

            cr.set_font_size(9.0)
            cr.move_to(cls.MARGIN_LEFT + 8.0, y)
            cr.show_text(desc)

            a_extents = cr.text_extents(amt_str)
            cr.move_to(cls.MARGIN_LEFT + content_width - a_extents.width - 8.0, y)
            cr.show_text(amt_str)

        # ── 5. COLLECTED BY & NOTES ──
        y += 26.0
        cr.set_source_rgb(0.45, 0.50, 0.58)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(8.5)
        cr.move_to(cls.MARGIN_LEFT, y)
        cr.show_text(f"Payment Received By: {collector}")

        y += 12.0
        cr.move_to(cls.MARGIN_LEFT, y)
        cr.show_text("Payment status: Confirmed & Audited in SIMS ERP.")

        # ── 6. SIGNATURE & STAMP BOX ──
        y += 35.0
        sig_x = cls.MARGIN_LEFT + content_width - 130.0
        cr.set_source_rgb(0.60, 0.65, 0.72)
        cr.set_line_width(0.8)
        cr.move_to(sig_x, y)
        cr.line_to(sig_x + 120.0, y)
        cr.stroke()

        cr.set_source_rgb(0.30, 0.35, 0.42)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(8.5)
        sig_text = "Authorized Signature"
        s_extents = cr.text_extents(sig_text)
        cr.move_to(sig_x + (120.0 - s_extents.width) / 2.0, y + 12.0)
        cr.show_text(sig_text)

        # ── 7. FOOTER NOTICE ──
        footer_y = cls.PAGE_HEIGHT - cls.MARGIN_BOTTOM
        cr.set_source_rgb(0.55, 0.60, 0.68)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(7.5)
        f_text = "This is an official computer-generated receipt from SIMS v2.2. Fees once paid are non-refundable."
        f_extents = cr.text_extents(f_text)
        cr.move_to(cls.MARGIN_LEFT + (content_width - f_extents.width) / 2.0, footer_y)
        cr.show_text(f_text)

        surface.finish()
        return path
