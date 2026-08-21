# modules/admission/views/receipt_dialog.py

from __future__ import annotations
import os
import subprocess
import urllib.parse
import webbrowser
from typing import Optional
import flet as ft

from core.logger.service import LogService
from ui.themes.theme import AppTheme
from modules.receipts.controller import ReceiptController
from modules.receipts.dto import ReceiptDTO
from modules.settings.service import SettingsService

__all__ = ["ReceiptDialog"]


class ReceiptDialog(ft.AlertDialog):
    """
    Enterprise Receipt Viewer Dialog.
    Displays vector fee slip with Print, Export PDF, and WhatsApp actions.
    """

    def __init__(
        self,
        receipt: ReceiptDTO,
        student_name: str = "Student",
        candidate_number: str = "",
        course_name: str = "",
        mobile_number: Optional[str] = None,
    ) -> None:
        super().__init__(modal=True)

        self.receipt = receipt
        self.student_name = student_name
        self.candidate_number = candidate_number
        self.course_name = course_name
        self.mobile_number = mobile_number

        self.settings_service = SettingsService()
        profile = self.settings_service.get_institute_profile()

        # Dialog Title
        self.title = ft.Row(
            controls=[
                ft.Icon(ft.Icons.RECEIPT_LONG, color=AppTheme.PRIMARY, size=24),
                ft.Text("Official Fee Receipt", size=AppTheme.SIZE_H2, weight=ft.FontWeight.W_600),
            ],
            spacing=AppTheme.PAD_SM,
        )

        # Receipt Paper Preview Card
        self.content = ft.Container(
            width=500,
            bgcolor=AppTheme.SURFACE,
            padding=AppTheme.PAD_MD,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
            content=ft.Column(
                controls=[
                    # 1. Branding Header
                    ft.Column(
                        controls=[
                            ft.Text(profile.get("institute_name", "Sudharm Infotech"), size=AppTheme.SIZE_H2, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                            ft.Text(f"{profile.get('contact_person', 'Hemant Mahale')} • Mob: {profile.get('contact_mobile', '9271226772')} • ALC: {profile.get('alc_code', '57210242')}", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                            ft.Text(f"{profile.get('address_line1', '')} {profile.get('address_line2', '')}", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=2,
                    ),
                    ft.Divider(height=12),

                    # 2. Receipt Meta
                    ft.Row(
                        controls=[
                            ft.Text(f"Receipt No: {self.receipt.receipt_number}", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_BODY),
                            ft.Text(f"Date: {self.receipt.receipt_date[:16]}", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Divider(height=8),

                    # 3. Student & Course Info
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Row([ft.Text("Student Name:", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY), ft.Text(self.student_name, size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Row([ft.Text("Candidate No:", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY), ft.Text(self.candidate_number, size=AppTheme.SIZE_BODY, color=AppTheme.PRIMARY, weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Row([ft.Text("Enrolled Course:", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY), ft.Text(self.course_name, size=AppTheme.SIZE_BODY)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ],
                            spacing=4,
                        ),
                        bgcolor=AppTheme.SURFACE_VARIANT,
                        padding=AppTheme.PAD_SM,
                        border_radius=AppTheme.RADIUS_SM,
                    ),

                    # 4. Financial Table
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Text(f"Fee Payment ({self.receipt.formatted_installment})", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color=AppTheme.SUCCESS),
                                        ft.Text(f"₹{self.receipt.amount_paid:,.2f}", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.SUCCESS),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                ft.Divider(height=6),
                                ft.Row([ft.Text("Payment Mode:", size=AppTheme.SIZE_CAPTION), ft.Text(self.receipt.payment_mode, size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Row([ft.Text("Total Course Fee:", size=AppTheme.SIZE_CAPTION), ft.Text(f"₹{self.receipt.total_course_fee:,.2f}", size=AppTheme.SIZE_CAPTION)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Row([ft.Text("Total Paid Till Date:", size=AppTheme.SIZE_CAPTION), ft.Text(f"₹{self.receipt.total_paid_till_now:,.2f}", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Row([ft.Text("Remaining Balance:", size=AppTheme.SIZE_CAPTION), ft.Text(f"₹{self.receipt.pending_amount:,.2f}", size=AppTheme.SIZE_CAPTION, color=AppTheme.DANGER, weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Row([ft.Text("Collected By:", size=AppTheme.SIZE_CAPTION), ft.Text(self.receipt.collector_name, size=AppTheme.SIZE_CAPTION)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ],
                            spacing=4,
                        ),
                        bgcolor=AppTheme.SURFACE_VARIANT,
                        padding=AppTheme.PAD_SM,
                        border_radius=AppTheme.RADIUS_SM,
                    ),

                    ft.Text(
                        "Computer generated official receipt. Verified & audited in SIMS ERP.",
                        size=10,
                        color=AppTheme.TEXT_MUTED,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                spacing=AppTheme.PAD_SM,
                tight=True,
            ),
        )

        # Action Buttons
        self.print_btn = ft.OutlinedButton(
            content=ft.Text("Print", size=AppTheme.SIZE_CAPTION),
            icon=ft.Icons.PRINT,
            on_click=self.handle_print,
        )

        self.pdf_btn = ft.OutlinedButton(
            content=ft.Text("Export PDF", size=AppTheme.SIZE_CAPTION),
            icon=ft.Icons.PICTURE_AS_PDF,
            on_click=self.handle_export_pdf,
        )

        self.whatsapp_btn = ft.ElevatedButton(
            content=ft.Text("WhatsApp", size=AppTheme.SIZE_CAPTION, color=AppTheme.SURFACE),
            icon=ft.Icons.SEND,
            style=ft.ButtonStyle(bgcolor="#25D366"),
            on_click=self.handle_whatsapp,
        )

        self.close_btn = ft.TextButton(
            content=ft.Text("Close"),
            on_click=self.close_modal,
        )

        self.actions = [
            ft.Row(
                controls=[
                    self.print_btn,
                    self.pdf_btn,
                    self.whatsapp_btn,
                    self.close_btn,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                expand=True,
            )
        ]

    @property
    def safe_page(self) -> Optional[ft.Page]:
        try:
            return self.page
        except (RuntimeError, AttributeError):
            return getattr(self, "_page", None)

    def close_modal(self, e: Optional[ft.ControlEvent] = None) -> None:
        p = self.safe_page
        if p:
            try:
                p.pop_dialog()
            except RuntimeError:
                pass

    def handle_print(self, e: ft.ControlEvent) -> None:
        """Opens receipt PDF with system print / viewer."""
        if self.receipt.pdf_path and os.path.exists(self.receipt.pdf_path):
            try:
                subprocess.Popen(["xdg-open", self.receipt.pdf_path])
            except Exception:
                webbrowser.open(f"file://{os.path.abspath(self.receipt.pdf_path)}")

    def handle_export_pdf(self, e: ft.ControlEvent) -> None:
        """Opens the exported PDF file location."""
        if self.receipt.pdf_path and os.path.exists(self.receipt.pdf_path):
            try:
                subprocess.Popen(["xdg-open", self.receipt.pdf_path])
            except Exception:
                webbrowser.open(f"file://{os.path.abspath(self.receipt.pdf_path)}")

    def handle_whatsapp(self, e: ft.ControlEvent) -> None:
        """Opens WhatsApp Web / Desktop with pre-filled message and receipt details."""
        clean_mob = "".join(c for c in (self.mobile_number or "") if c.isdigit())
        if len(clean_mob) == 10:
            clean_mob = f"91{clean_mob}"

        msg = (
            f"Dear {self.student_name},\n"
            f"Thank you for your fee payment of Rs. {self.receipt.amount_paid:,.2f} for {self.course_name}.\n"
            f"Receipt No: {self.receipt.receipt_number}\n"
            f"Pending Balance: Rs. {self.receipt.pending_amount:,.2f}\n"
            f"- Sudharm Infotech, Chandwad"
        )
        encoded_msg = urllib.parse.quote(msg)
        wa_url = f"https://wa.me/{clean_mob}?text={encoded_msg}" if clean_mob else f"https://web.whatsapp.com/send?text={encoded_msg}"
        webbrowser.open(wa_url)
