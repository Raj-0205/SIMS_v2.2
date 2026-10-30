# modules/admission/views/payment_dialog.py

from __future__ import annotations
import os
import webbrowser
from typing import Callable, Optional
import flet as ft

from core.logger.service import LogService
from core.exceptions import ValidationError, ServiceError
from ui.themes.theme import AppTheme
from modules.admission.controller import AdmissionController
from modules.payments.controller import PaymentController
from modules.receipts.controller import ReceiptController
from modules.settings.service import SettingsService
from core.utils.upi_qr import generate_upi_qr_base64, build_upi_deep_link

__all__ = ["PaymentDialog"]


class PaymentDialog(ft.AlertDialog):
    """
    Enterprise Payment & Receipt Gateway Dialog.
    Supports:
      1. Direct Mode: Pre-populated for a specific admission / candidate.
      2. Universal Search Mode: Live autocomplete candidate search by name/number/mobile.
      3. Quick-amount shortcut chips with real-time remaining balance calculations.
      4. Multi-mode payment support (Cash, UPI with QR helper, Card, Bank, Cheque).
      5. Verification PIN security and instant receipt access.
    """

    def __init__(
        self,
        admission_id: Optional[int] = None,
        student_name: str = "",
        course_name: str = "",
        candidate_number: str = "",
        total_fee: float = 0.0,
        already_paid: float = 0.0,
        default_amount: float = 500.0,
        on_payment_completed: Optional[Callable[[int], None]] = None,
        on_payment_success: Optional[Callable[[int], None]] = None,
        page: Optional[ft.Page] = None,
        current_status: Optional[str] = None,
        mobile_number: Optional[str] = None,
    ) -> None:
        super().__init__(modal=True)

        self.admission_id = admission_id
        self.student_name = student_name or ""
        self.course_name = course_name or ""
        self.candidate_number = candidate_number or ""
        self.total_fee = float(total_fee or 0.0)
        self.already_paid = float(already_paid or 0.0)
        self.pending_balance = max(0.0, self.total_fee - self.already_paid)
        self.default_amount = float(default_amount or 500.0)
        self.on_payment_completed = on_payment_completed or on_payment_success or (lambda pid: None)
        self._root_page = page
        self.current_status = current_status
        self.mobile_number = mobile_number

        self.controller = AdmissionController()
        self.is_direct_mode = bool(self.admission_id)

        # Settings & UPI Configuration
        try:
            settings_svc = SettingsService()
            inst_profile = settings_svc.get_institute_profile()
            self.upi_id = inst_profile.get("upi_id") or "9271226772@yescred"
            self.upi_payee_name = inst_profile.get("upi_payee_name") or "Sudharm Infotech"
        except Exception:
            self.upi_id = "9271226772@yescred"
            self.upi_payee_name = "Sudharm Infotech"
        self._latest_upi_link: str = ""

        # If admission_id is provided but details are missing, fetch from DB
        if self.admission_id and (not self.student_name or self.total_fee <= 0 or not self.mobile_number):
            try:
                adm = self.controller.get_admission(self.admission_id)
                if adm:
                    if not self.student_name:
                        self.student_name = adm.student_name or ""
                    if not self.course_name:
                        self.course_name = adm.course_name or ""
                    if not self.candidate_number:
                        self.candidate_number = adm.admission_number or ""
                    if self.total_fee <= 0:
                        self.total_fee = float(adm.final_fee or 0.0)
                    if self.already_paid <= 0:
                        self.already_paid = float(adm.total_paid or 0.0)
                    self.pending_balance = max(0.0, self.total_fee - self.already_paid)
                    if not self.current_status:
                        self.current_status = adm.status.value if hasattr(adm.status, "value") else str(adm.status)
                    if not self.mobile_number:
                        self.mobile_number = adm.mobile_number
            except Exception as ex:
                LogService.warning(f"Could not load admission #{self.admission_id}: {ex}", context="PaymentDialog")

        # Title Control
        self.title_icon = ft.Icon(ft.Icons.PAYMENTS, color=AppTheme.SUCCESS, size=24)
        self.title_label = ft.Text(
            "Confirm Admission & Collect Payment" if self.admission_id else "Collect Payment Gateway",
            size=AppTheme.SIZE_H2,
            weight=ft.FontWeight.W_600,
        )
        self.title = ft.SelectionArea(
            content=ft.Row(
                controls=[
                    self.title_icon,
                    self.title_label,
                    ft.Container(
                        content=ft.Text("⚡ Instant Receipt", size=10, weight=ft.FontWeight.BOLD, color="#059669"),
                        bgcolor="#ECFDF5",
                        border=ft.Border.all(1, "#A7F3D0"),
                        border_radius=12,
                        padding=ft.Padding(8, 2, 8, 2),
                    ),
                ],
                spacing=AppTheme.PAD_SM,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )

        # Candidate Search Controls (for Universal Search Mode)
        self.search_input = ft.TextField(
            hint_text="Type candidate name, number (e.g. 2026-001), or mobile...",
            prefix_icon=ft.Icons.SEARCH,
            border_radius=AppTheme.RADIUS_MD,
            dense=True,
            on_change=self._handle_candidate_search_change,
        )
        self.search_results_container = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, height=180)
        self.search_mode_box = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Select Candidate for Payment Collection:", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_SECONDARY),
                    self.search_input,
                    self.search_results_container,
                ],
                spacing=8,
            ),
            visible=(self.admission_id is None),
        )

        # Candidate Details & Ledger Container (Direct Payment Mode)
        self.ledger_container = ft.Container()

        # Amount Input
        calc_default = min(self.default_amount, self.pending_balance) if self.pending_balance > 0 else self.default_amount
        hint_str = "Enter installment payment amount" if (self.already_paid > 0 or self.current_status == "CONFIRMED") else "Minimum ₹500 required for confirmation"
        self.amount_input = ft.TextField(
            label="Amount Paying Now (₹) *",
            value=f"{calc_default:.0f}",
            keyboard_type=ft.KeyboardType.NUMBER,
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_H3,
            prefix_icon=ft.Icons.CURRENCY_RUPEE,
            hint_text=hint_str,
            on_change=self._handle_amount_change,
        )

        # Quick-Amount Chips Container
        self.quick_chips_row = ft.Row(wrap=True, spacing=6)

        # Live Balance Projection Text
        self.balance_projection_text = ft.Text(
            "",
            size=AppTheme.SIZE_CAPTION,
            weight=ft.FontWeight.W_500,
            color=AppTheme.TEXT_SECONDARY,
        )

        # Payment Mode Dropdown
        self.mode_dropdown = ft.Dropdown(
            label="Payment Mode *",
            options=[
                ft.DropdownOption(key="CASH", text="Cash"),
                ft.DropdownOption(key="UPI", text="UPI / QR Code"),
                ft.DropdownOption(key="CARD", text="Debit / Credit Card"),
                ft.DropdownOption(key="NET_BANKING", text="Net Banking"),
                ft.DropdownOption(key="CHEQUE", text="Cheque"),
            ],
            value="CASH",
            border_radius=AppTheme.RADIUS_MD,
            on_select=self._handle_mode_change,
        )

        # Collector Dropdown
        collectors = self.controller.get_active_collectors()
        col_opts = [ft.DropdownOption(key=c["name"], text=c["name"]) for c in collectors]
        if not col_opts:
            col_opts = [ft.DropdownOption(key="Hemant Mahale (Sir)", text="Hemant Mahale (Sir)")]

        self.collector_dropdown = ft.Dropdown(
            label="Payment Received By *",
            options=col_opts,
            value=col_opts[0].key if col_opts else "Hemant Mahale (Sir)",
            border_radius=AppTheme.RADIUS_MD,
        )

        # Admin PIN Authorization Input
        self.pin_input = ft.TextField(
            label="Admin PIN Authorization *",
            hint_text="Enter 4-digit Admin PIN",
            password=True,
            can_reveal_password=True,
            border_radius=AppTheme.RADIUS_MD,
            prefix_icon=ft.Icons.LOCK,
            on_change=lambda _: self._clear_error(),
        )

        # Transaction Ref (optional)
        self.tx_ref_input = ft.TextField(
            label="Transaction Ref / UPI ID (Optional)",
            hint_text="e.g. UPI Ref / Bank UTR / Cheque No.",
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
        )

        # Live Dynamic UPI QR & Payment Card
        self.upi_qr_image = ft.Image(
            src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
            width=165,
            height=165,
            fit=ft.BoxFit.CONTAIN,
            border_radius=AppTheme.RADIUS_SM,
        )
        self.upi_amount_badge = ft.Text(
            f"₹{calc_default:,.2f}",
            size=18,
            weight=ft.FontWeight.BOLD,
            color="#059669",
        )
        self.upi_id_display = ft.Text(
            self.upi_id,
            size=11,
            weight=ft.FontWeight.W_600,
            color="#0369A1",
            selectable=True,
        )
        self.copy_upi_btn = ft.OutlinedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.COPY, size=13, color="#0284C7"),
                    ft.Text("Copy UPI", size=10, color="#0284C7", weight=ft.FontWeight.W_600),
                ],
                spacing=3,
            ),
            style=ft.ButtonStyle(
                padding=ft.Padding(6, 2, 6, 2),
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_SM),
            ),
            on_click=self._handle_copy_upi_id,
        )
        self.copy_link_btn = ft.OutlinedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.SHARE, size=13, color="#059669"),
                    ft.Text("Copy Link", size=10, color="#059669", weight=ft.FontWeight.W_600),
                ],
                spacing=3,
            ),
            style=ft.ButtonStyle(
                padding=ft.Padding(6, 2, 6, 2),
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_SM),
            ),
            on_click=self._handle_copy_upi_link,
        )

        self.upi_helper_container = ft.Container(
            content=ft.Column(
                controls=[
                    # Header: Payee info & verified badge
                    ft.Row(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.QR_CODE_2, color="#0284C7", size=20),
                                    ft.Text(f"Pay to: {self.upi_payee_name}", size=12, weight=ft.FontWeight.BOLD, color="#0F172A"),
                                ],
                                spacing=6,
                            ),
                            ft.Container(
                                content=ft.Row(
                                    controls=[
                                        ft.Icon(ft.Icons.VERIFIED, color="#059669", size=14),
                                        ft.Text("Verified Merchant", size=10, weight=ft.FontWeight.BOLD, color="#059669"),
                                    ],
                                    spacing=2,
                                ),
                                bgcolor="#ECFDF5",
                                border_radius=AppTheme.RADIUS_SM,
                                padding=ft.Padding(6, 2, 6, 2),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Divider(height=1, color="#E2E8F0"),
                    # QR Code + Amount Display
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=self.upi_qr_image,
                                bgcolor="#FFFFFF",
                                padding=ft.Padding(6, 6, 6, 6),
                                border=ft.Border.all(1, "#CBD5E1"),
                                border_radius=AppTheme.RADIUS_MD,
                            ),
                            ft.Column(
                                controls=[
                                    ft.Text("Scan with any UPI App", size=11, color=AppTheme.TEXT_SECONDARY),
                                    ft.Text("GPay • PhonePe • Paytm • BHIM", size=10, weight=ft.FontWeight.W_500, color="#475569"),
                                    ft.Container(height=4),
                                    ft.Text("Amount Encoded in QR:", size=10, color=AppTheme.TEXT_SECONDARY),
                                    self.upi_amount_badge,
                                    ft.Container(height=4),
                                    ft.Row(
                                        controls=[
                                            ft.Text("VPA:", size=11, color=AppTheme.TEXT_SECONDARY),
                                            self.upi_id_display,
                                        ],
                                        spacing=4,
                                    ),
                                    ft.Row(
                                        controls=[self.copy_upi_btn, self.copy_link_btn],
                                        spacing=6,
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Text(
                        "ℹ️ This QR code is dynamically custom-generated for the exact amount. Scanning locks this amount automatically.",
                        size=10,
                        color="#0369A1",
                        italic=True,
                    ),
                ],
                spacing=8,
            ),
            bgcolor="#F8FAFC",
            border=ft.Border.all(1, "#93C5FD"),
            border_radius=AppTheme.RADIUS_MD,
            padding=ft.Padding(12, 10, 12, 10),
            visible=False,
        )

        # Error Banner
        self.error_text = ft.Text("", color=AppTheme.DANGER, size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.W_500)
        self.error_container = ft.Container(
            content=ft.Row(
                controls=[ft.Icon(ft.Icons.ERROR_OUTLINE, color=AppTheme.DANGER, size=16), self.error_text],
                spacing=AppTheme.PAD_SM,
            ),
            bgcolor=AppTheme.DANGER_LIGHT,
            padding=ft.Padding(12, 8, 12, 8),
            border_radius=AppTheme.RADIUS_SM,
            visible=False,
        )

        # Action Buttons
        self.verify_btn_text = ft.Text("Verify & Confirm Payment", weight=ft.FontWeight.BOLD)
        self.verify_btn = ft.ElevatedButton(
            content=self.verify_btn_text,
            icon=ft.Icons.CHECK_CIRCLE,
            style=ft.ButtonStyle(
                bgcolor=AppTheme.SUCCESS,
                color=AppTheme.SURFACE,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
                padding=ft.Padding(14, 10, 14, 10),
            ),
            on_click=self.handle_confirm_payment,
        )

        self.cancel_btn = ft.TextButton(
            content=ft.Text("Cancel"),
            on_click=self.close_modal,
        )

        # Payment Form Wrapper
        self.payment_form_box = ft.Column(
            controls=[
                self.ledger_container,
                self.error_container,
                self.amount_input,
                self.quick_chips_row,
                self.balance_projection_text,
                ft.Row(controls=[self.mode_dropdown, self.collector_dropdown], spacing=AppTheme.PAD_SM),
                self.upi_helper_container,
                self.pin_input,
                self.tx_ref_input,
            ],
            spacing=AppTheme.PAD_MD,
            tight=True,
            visible=(self.admission_id is not None),
        )

        self.content = ft.Container(
            width=480,
            content=ft.SelectionArea(
                content=ft.Column(
                    controls=[
                        self.search_mode_box,
                        self.payment_form_box,
                    ],
                    spacing=8,
                    tight=True,
                ),
            ),
        )

        self.actions = [self.cancel_btn, self.verify_btn]
        self.actions_alignment = ft.MainAxisAlignment.END

        # Initial view build
        if self.admission_id:
            self._render_ledger_card()
            self._render_quick_chips()
            self._update_balance_projection()
            self._refresh_upi_qr(calc_default)
        else:
            self.verify_btn.visible = False
            self._populate_initial_candidates()

    def _render_ledger_card(self) -> None:
        """Renders the top candidate identity and 3-card balance ledger."""
        pct = (self.already_paid / self.total_fee * 100.0) if self.total_fee > 0 else 100.0
        pct = min(100.0, max(0.0, pct))

        change_btn = []
        change_btn.append(
            ft.TextButton(
                content=ft.Row([ft.Icon(ft.Icons.SWAP_HORIZ, size=14), ft.Text("Switch Candidate", size=11)], spacing=4),
                style=ft.ButtonStyle(padding=ft.Padding(4, 2, 4, 2)),
                on_click=self._handle_switch_candidate_click,
            )
        )

        self.balance_progress = ft.ProgressBar(value=pct / 100.0, color="#10B981", bgcolor="#E2E8F0", height=4)
        self.ledger_container.content = ft.Container(
            content=ft.Column(
                controls=[
                    # Candidate Header
                    ft.Row(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.CircleAvatar(
                                        content=ft.Text(self.student_name[:1].upper() if self.student_name else "S", weight=ft.FontWeight.BOLD, size=14),
                                        bgcolor=AppTheme.PRIMARY_LIGHT,
                                        color=AppTheme.PRIMARY,
                                        radius=16,
                                    ),
                                    ft.Column(
                                        controls=[
                                            ft.Text(self.student_name, weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_BODY, no_wrap=True),
                                            ft.Text(f"Candidate #{self.candidate_number}  •  {self.course_name}", size=11, color=AppTheme.TEXT_SECONDARY),
                                        ],
                                        spacing=1,
                                    ),
                                ],
                                spacing=8,
                            ),
                            ft.Row(controls=change_btn),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Divider(height=8),
                    # 3 Metric Cards
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Column(
                                    controls=[
                                        ft.Text("Total Course Fee", size=10, color=AppTheme.TEXT_SECONDARY),
                                        ft.Text(f"₹{self.total_fee:,.0f}", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                                    ],
                                    spacing=1,
                                ),
                                bgcolor=AppTheme.SURFACE,
                                border_radius=AppTheme.RADIUS_SM,
                                border=ft.Border.all(1, AppTheme.BORDER),
                                padding=ft.Padding(8, 6, 8, 6),
                                expand=True,
                            ),
                            ft.Container(
                                content=ft.Column(
                                    controls=[
                                        ft.Text("Total Paid", size=10, color=AppTheme.TEXT_SECONDARY),
                                        ft.Text(f"₹{self.already_paid:,.0f}", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color=AppTheme.SUCCESS),
                                    ],
                                    spacing=1,
                                ),
                                bgcolor=AppTheme.SURFACE,
                                border_radius=AppTheme.RADIUS_SM,
                                border=ft.Border.all(1, AppTheme.BORDER),
                                padding=ft.Padding(8, 6, 8, 6),
                                expand=True,
                            ),
                            ft.Container(
                                content=ft.Column(
                                    controls=[
                                        ft.Text("Pending Dues", size=10, color=AppTheme.TEXT_SECONDARY),
                                        ft.Text(f"₹{self.pending_balance:,.0f}", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color=AppTheme.DANGER if self.pending_balance > 0 else AppTheme.SUCCESS),
                                    ],
                                    spacing=1,
                                ),
                                bgcolor="#FEF2F2" if self.pending_balance > 0 else "#F0FDF4",
                                border_radius=AppTheme.RADIUS_SM,
                                border=ft.Border.all(1, "#FECACA" if self.pending_balance > 0 else "#BBF7D0"),
                                padding=ft.Padding(8, 6, 8, 6),
                                expand=True,
                            ),
                        ],
                        spacing=6,
                    ),
                    # Progress bar
                    self.balance_progress,
                ],
                spacing=6,
            ),
            bgcolor=AppTheme.SURFACE_VARIANT,
            padding=ft.Padding(12, 10, 12, 10),
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

    def _render_quick_chips(self) -> None:
        """Constructs quick-amount shortcut pill buttons."""
        chips = []
        presets = [500, 1000, 2000, 5000]
        for val in presets:
            if val <= self.pending_balance or self.pending_balance <= 0:
                chips.append(
                    ft.Container(
                        content=ft.Text(f"₹{val:,}", size=11, weight=ft.FontWeight.W_600, color="#059669"),
                        bgcolor="#ECFDF5",
                        border=ft.Border.all(1, "#A7F3D0"),
                        border_radius=AppTheme.RADIUS_SM,
                        padding=ft.Padding(8, 4, 8, 4),
                        ink=True,
                        on_click=lambda _, v=val: self._set_quick_amount(v),
                    )
                )

        if self.pending_balance > 0:
            chips.append(
                ft.Container(
                    content=ft.Text(f"Full Balance: ₹{self.pending_balance:,.0f}", size=11, weight=ft.FontWeight.BOLD, color="#2563EB"),
                    bgcolor="#EFF6FF",
                    border=ft.Border.all(1, "#BFDBFE"),
                    border_radius=AppTheme.RADIUS_SM,
                    padding=ft.Padding(8, 4, 8, 4),
                    ink=True,
                    on_click=lambda _: self._set_quick_amount(self.pending_balance),
                )
            )

        self.quick_chips_row.controls = chips

    def _refresh_upi_qr(self, amount: Optional[float] = None) -> None:
        """Regenerates the custom dynamic UPI QR code with the current amount and candidate details."""
        if amount is None:
            raw = (self.amount_input.value or "").strip()
            try:
                amount = float(raw) if raw else 0.0
            except ValueError:
                amount = 0.0

        amount = max(0.0, float(amount))
        cand_str = f"#{self.candidate_number}" if self.candidate_number else ""
        st_name = self.student_name.strip() if self.student_name else "Student"
        note = f"Fee - {st_name} {cand_str}".strip()

        try:
            b64_qr, link = generate_upi_qr_base64(
                upi_id=self.upi_id,
                payee_name=self.upi_payee_name,
                amount=amount,
                transaction_note=note,
                box_size=5,
                border=1,
            )
            self.upi_qr_image.src = f"data:image/png;base64,{b64_qr}"
            self.upi_amount_badge.value = f"₹{amount:,.2f}"
            self._latest_upi_link = link
        except Exception as ex:
            LogService.error(f"Failed to generate dynamic UPI QR: {ex}", context="PaymentDialog")

    def _handle_copy_upi_id(self, e: Optional[ft.ControlEvent] = None) -> None:
        p = self.safe_page
        if p:
            try:
                p.set_clipboard(self.upi_id)
                self.show_toast(f"UPI ID copied: {self.upi_id}", is_success=True)
            except Exception:
                pass

    def _handle_copy_upi_link(self, e: Optional[ft.ControlEvent] = None) -> None:
        p = self.safe_page
        if p and self._latest_upi_link:
            try:
                p.set_clipboard(self._latest_upi_link)
                self.show_toast("UPI payment link copied! Paste into WhatsApp or SMS.", is_success=True)
            except Exception:
                pass

    def show_toast(self, message: str, is_success: bool = True) -> None:
        p = self.safe_page
        if p:
            try:
                snack = ft.SnackBar(
                    content=ft.Text(message, color=AppTheme.SURFACE),
                    bgcolor=AppTheme.SUCCESS if is_success else AppTheme.DANGER,
                    duration=2500,
                )
                p.show_snack_bar(snack)
            except Exception:
                pass

    def _set_quick_amount(self, val: float) -> None:
        self.amount_input.value = f"{val:.0f}"
        self._clear_error()
        self._update_balance_projection()
        if (self.mode_dropdown.value or "") == "UPI":
            self._refresh_upi_qr(val)
        self._safe_update()

    def _handle_amount_change(self, e: ft.ControlEvent) -> None:
        self._clear_error()
        self._update_balance_projection()
        if (self.mode_dropdown.value or "") == "UPI":
            self._refresh_upi_qr()
        self._safe_update()

    def _update_balance_projection(self) -> None:
        raw_val = (self.amount_input.value or "").strip()
        try:
            amt = float(raw_val) if raw_val else 0.0
            rem = self.pending_balance - amt
            if rem == 0.0:
                self.balance_projection_text.value = "✨ Full settlement — Zero dues remaining upon confirmation!"
                self.balance_projection_text.color = AppTheme.SUCCESS
            elif rem > 0.0:
                self.balance_projection_text.value = f"Remaining balance after this payment: ₹{rem:,.2f}"
                self.balance_projection_text.color = AppTheme.TEXT_SECONDARY
            else:
                self.balance_projection_text.value = f"⚠️ Amount exceeds pending balance by ₹{-rem:,.2f}"
                self.balance_projection_text.color = AppTheme.DANGER
        except ValueError:
            self.balance_projection_text.value = "Enter a valid numeric amount."
            self.balance_projection_text.color = AppTheme.DANGER

    def _handle_mode_change(self, e: Optional[ft.ControlEvent] = None) -> None:
        mode = self.mode_dropdown.value or "CASH"
        if mode == "UPI":
            self.upi_helper_container.visible = True
            self._refresh_upi_qr()
            self.tx_ref_input.label = "Bank UTR / UPI Reference Number (12 digits) *"
            self.tx_ref_input.hint_text = "Enter 12-digit numeric UTR from payment app"
            self.tx_ref_input.helper_text = "Must be exactly 12 numeric digits (e.g. 430299887766)"
            self.tx_ref_input.max_length = 12
            self.tx_ref_input.input_filter = ft.NumbersOnlyInputFilter()
            self.tx_ref_input.keyboard_type = ft.KeyboardType.NUMBER
        elif mode == "NET_BANKING":
            self.upi_helper_container.visible = False
            self.tx_ref_input.label = "Bank UTR / Transaction Ref (12 digits) *"
            self.tx_ref_input.hint_text = "Enter 12-digit numeric Bank UTR Number"
            self.tx_ref_input.helper_text = "Must be exactly 12 numeric digits"
            self.tx_ref_input.max_length = 12
            self.tx_ref_input.input_filter = ft.NumbersOnlyInputFilter()
            self.tx_ref_input.keyboard_type = ft.KeyboardType.NUMBER
        else:
            self.upi_helper_container.visible = False
            self.tx_ref_input.label = "Transaction Ref / UPI ID (Optional)"
            self.tx_ref_input.hint_text = "e.g. Bank Ref / Cheque No."
            self.tx_ref_input.helper_text = None
            self.tx_ref_input.max_length = None
            self.tx_ref_input.input_filter = None
            self.tx_ref_input.keyboard_type = ft.KeyboardType.TEXT
        self._safe_update()

    def _handle_candidate_search_change(self, e: ft.ControlEvent) -> None:
        query = (self.search_input.value or "").strip()
        self._populate_candidates(query)

    def _populate_initial_candidates(self) -> None:
        self._populate_candidates("")

    def _populate_candidates(self, query: str) -> None:
        try:
            admissions, _ = self.controller.filter_admissions({"query": query, "limit": 6})
        except Exception:
            admissions = []

        if not admissions:
            self.search_results_container.controls = [
                ft.Container(
                    content=ft.Text("No active candidates found matching query.", size=12, color=AppTheme.TEXT_MUTED),
                    padding=ft.Padding(12, 16, 12, 16),
                    alignment=ft.Alignment(0, 0),
                )
            ]
        else:
            items = []
            for adm in admissions:
                due_color = AppTheme.DANGER if adm.pending_amount > 0 else AppTheme.SUCCESS
                items.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.CircleAvatar(
                                    content=ft.Text(adm.student_name[:1].upper() if adm.student_name else "S", weight=ft.FontWeight.BOLD, size=12),
                                    radius=14,
                                    bgcolor=AppTheme.PRIMARY_LIGHT,
                                    color=AppTheme.PRIMARY,
                                ),
                                ft.Column(
                                    controls=[
                                        ft.Text(f"{adm.student_name} (#{adm.admission_number})", size=12, weight=ft.FontWeight.BOLD, no_wrap=True),
                                        ft.Text(f"{adm.course_name}  •  {adm.mobile_number or '—'}", size=11, color=AppTheme.TEXT_SECONDARY),
                                    ],
                                    spacing=1,
                                    expand=True,
                                ),
                                ft.Container(
                                    content=ft.Text(f"Pending: ₹{adm.pending_amount:,.0f}", size=11, weight=ft.FontWeight.BOLD, color=due_color),
                                    bgcolor="#FEF2F2" if adm.pending_amount > 0 else "#ECFDF5",
                                    border_radius=AppTheme.RADIUS_SM,
                                    padding=ft.Padding(8, 3, 8, 3),
                                ),
                            ],
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        bgcolor=AppTheme.SURFACE,
                        border=ft.Border.all(1, AppTheme.BORDER),
                        border_radius=AppTheme.RADIUS_SM,
                        padding=ft.Padding(10, 8, 10, 8),
                        ink=True,
                        on_click=lambda _, a=adm: self._select_candidate(a),
                    )
                )
            self.search_results_container.controls = items
        self._safe_update()

    def _select_candidate(self, adm: Any) -> None:
        if isinstance(adm, int):
            self.admission_id = adm
            adm = self.controller.get_admission(adm)
        else:
            self.admission_id = adm.id
        self.is_direct_mode = True
        self.student_name = adm.student_name or ""
        self.course_name = adm.course_name or ""
        self.candidate_number = adm.admission_number or ""
        self.total_fee = float(adm.final_fee or 0.0)
        self.already_paid = float(adm.total_paid or 0.0)
        self.pending_balance = max(0.0, self.total_fee - self.already_paid)
        self.current_status = adm.status.value if hasattr(adm.status, "value") else str(adm.status)
        self.mobile_number = adm.mobile_number

        self.title_label.value = "Confirm Admission & Collect Payment"
        self.search_mode_box.visible = False
        self.payment_form_box.visible = True
        self.verify_btn.visible = True

        calc_default = min(self.default_amount, self.pending_balance) if self.pending_balance > 0 else self.default_amount
        self.amount_input.value = f"{calc_default:.0f}"

        self._render_ledger_card()
        self._render_quick_chips()
        self._update_balance_projection()
        if (self.mode_dropdown.value or "") == "UPI":
            self._refresh_upi_qr(calc_default)
        self._clear_error()
        self._safe_update()

    def _handle_switch_candidate_click(self, e: ft.ControlEvent) -> None:
        self.admission_id = None
        self.title_label.value = "Collect Payment Gateway"
        self.search_mode_box.visible = True
        self.payment_form_box.visible = False
        self.verify_btn.visible = False
        self.search_input.value = ""
        self._populate_candidates("")
        self._clear_error()
        self._safe_update()

    def _clear_error(self) -> None:
        self.error_container.visible = False
        self.error_text.value = ""

    def _show_error(self, msg: str) -> None:
        self.error_text.value = msg
        self.error_container.visible = True
        self.verify_btn.disabled = False
        self.verify_btn_text.value = "Verify & Confirm Payment"
        self._safe_update()

    @property
    def safe_page(self) -> Optional[ft.Page]:
        try:
            return self._root_page or self.page
        except (RuntimeError, AttributeError):
            return self._root_page or getattr(self, "_page", None)

    def _safe_update(self) -> None:
        p = self.safe_page
        if p:
            try:
                self.update()
            except RuntimeError:
                pass

    def close_modal(self, e: Optional[ft.ControlEvent] = None) -> None:
        p = self.safe_page
        if p:
            try:
                p.pop_dialog()
            except RuntimeError:
                pass

    def handle_confirm_payment(self, e: Optional[ft.ControlEvent] = None) -> None:
        self._clear_error()
        if not self.admission_id:
            self._show_error("Please select a candidate before proceeding.")
            return

        raw_amt = (self.amount_input.value or "").strip()
        pin = (self.pin_input.value or "").strip()
        mode = self.mode_dropdown.value or "CASH"
        collector = self.collector_dropdown.value or "Hemant Mahale (Sir)"
        tx_ref = (self.tx_ref_input.value or "").strip()

        try:
            amount = float(raw_amt)
        except ValueError:
            self._show_error("Please enter a valid numeric payment amount.")
            return

        if amount <= 0.0:
            self._show_error("Payment amount must be greater than zero.")
            return

        if amount > self.pending_balance:
            self._show_error(f"Payment amount (₹{amount:,.2f}) cannot exceed pending balance (₹{self.pending_balance:,.2f}).")
            return

        # Differentiate floor requirement: initial vs subsequent payment (SIMS-FIN-01)
        is_subsequent = (self.already_paid > 0.0 or self.current_status == "CONFIRMED")
        if not is_subsequent:
            if self.pending_balance >= 500.0 and amount < 500.0:
                self._show_error("Minimum payment of ₹500 is required to confirm admission.")
                return
        # Strong Payment Verification for UPI / Bank Payments
        if mode == "UPI":
            if not tx_ref:
                self._show_error("Bank UTR / UPI Reference Number is mandatory for UPI payments.")
                return
            if len(tx_ref) != 12 or not tx_ref.isdigit():
                self._show_error("Invalid UTR Reference: Bank UTR / UPI Reference Number must be exactly 12 numeric digits.")
                return
            dummy_refs = {
                "000000000000", "111111111111", "222222222222", "333333333333",
                "444444444444", "555555555555", "666666666666", "777777777777",
                "888888888888", "999999999999", "123456789012"
            }
            if tx_ref in dummy_refs:
                self._show_error(f"'{tx_ref}' is a dummy reference. Please enter the actual 12-digit UTR from your UPI payment app.")
                return
        elif mode == "NET_BANKING":
            if not tx_ref:
                self._show_error("Bank UTR / Reference Number is mandatory for Bank Transfer payments.")
                return
            if len(tx_ref) != 12 or not tx_ref.isdigit():
                self._show_error("Invalid UTR Reference: Bank UTR Number must be exactly 12 numeric digits.")
                return
            dummy_refs = {
                "000000000000", "111111111111", "222222222222", "333333333333",
                "444444444444", "555555555555", "666666666666", "777777777777",
                "888888888888", "999999999999", "123456789012"
            }
            if tx_ref in dummy_refs:
                self._show_error(f"'{tx_ref}' is a dummy reference. Please enter the actual 12-digit UTR from your bank transfer.")
                return

        if not pin:
            self._show_error("Admin authorization PIN is required.")
            return

        self.verify_btn.disabled = True
        self.verify_btn_text.value = "Processing..."
        self._safe_update()

        try:
            payment_id = self.controller.confirm_admission_with_payment(
                admission_id=self.admission_id,
                amount=amount,
                payment_mode=mode,
                admin_pin=pin,
                collector_name=collector,
                transaction_ref=tx_ref if tx_ref else None,
            )

            p = self.safe_page
            self.close_modal()

            # Display Official Fee Receipt Dialog immediately with PDF, WhatsApp, and Print options
            if p:
                def show_receipt():
                    try:
                        from modules.admission.views.receipt_dialog import ReceiptDialog
                        r_dto = ReceiptController().get_receipt_by_payment(payment_id)
                        if r_dto:
                            rec_dlg = ReceiptDialog(
                                receipt=r_dto,
                                student_name=self.student_name or "Student",
                                candidate_number=self.candidate_number or "",
                                course_name=self.course_name or "",
                                mobile_number=self.mobile_number,
                            )
                            p.show_dialog(rec_dlg)
                    except Exception as rex:
                        LogService.warning(f"Could not open receipt dialog: {rex}", context="PaymentDialog")

                # 1. Immediately launch Receipt Dialog
                show_receipt()

                # 2. Celebratory confirmation toast on safe_page (with shortcut to re-open receipt if dismissed)
                try:
                    p.show_snack_bar(
                        ft.SnackBar(
                            content=ft.Row([
                                ft.Icon(ft.Icons.CHECK_CIRCLE, color="#10B981"),
                                ft.Text(f"Payment of ₹{amount:,.0f} confirmed for {self.student_name}!"),
                            ], spacing=8),
                            action="View Receipt 📄",
                            on_action=lambda ev: show_receipt(),
                            duration=6000,
                        )
                    )
                except Exception:
                    pass

            self.on_payment_completed(payment_id)

        except (ValidationError, ServiceError) as ex:
            self._show_error(str(ex))
        except Exception as ex:
            LogService.error(f"Payment dialog confirmation error: {ex}", context=self.__class__.__name__)
            self._show_error("An unexpected error occurred during payment processing.")

