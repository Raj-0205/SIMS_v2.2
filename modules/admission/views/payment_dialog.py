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

__all__ = ["PaymentDialog"]


class PaymentDialog(ft.AlertDialog):
    """
    Enterprise Payment & Receipt Authorization Dialog.
    Enforces ₹500 minimum payment for confirmation and verified Admin PIN.
    """

    def __init__(
        self,
        admission_id: int,
        student_name: str,
        course_name: str,
        candidate_number: str,
        total_fee: float,
        already_paid: float = 0.0,
        default_amount: float = 500.0,
        on_payment_completed: Optional[Callable[[int], None]] = None,
        on_payment_success: Optional[Callable[[int], None]] = None,
    ) -> None:
        super().__init__(modal=True)

        self.admission_id = admission_id
        self.student_name = student_name
        self.course_name = course_name
        self.candidate_number = candidate_number
        self.total_fee = total_fee
        self.already_paid = already_paid
        self.pending_balance = max(0.0, total_fee - already_paid)
        self.on_payment_completed = on_payment_completed or on_payment_success or (lambda pid: None)

        self.controller = AdmissionController()

        # Title
        self.title = ft.Row(
            controls=[
                ft.Icon(ft.Icons.PAYMENTS, color=AppTheme.SUCCESS, size=24),
                ft.Text("Confirm Admission & Collect Payment", size=AppTheme.SIZE_H2, weight=ft.FontWeight.W_600),
            ],
            spacing=AppTheme.PAD_SM,
        )

        # Candidate & Course Summary Card
        summary_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("Candidate:", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_BODY),
                            ft.Text(f"{self.student_name} ({self.candidate_number})", size=AppTheme.SIZE_BODY, color=AppTheme.PRIMARY),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Row(
                        controls=[
                            ft.Text("Course:", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_BODY),
                            ft.Text(self.course_name, size=AppTheme.SIZE_BODY),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Divider(height=8),
                    ft.Row(
                        controls=[
                            ft.Text("Total Course Fee:", size=AppTheme.SIZE_CAPTION),
                            ft.Text(f"₹{self.total_fee:,.2f}", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD),
                            ft.Text("Pending Balance:", size=AppTheme.SIZE_CAPTION),
                            ft.Text(f"₹{self.pending_balance:,.2f}", size=AppTheme.SIZE_CAPTION, color=AppTheme.DANGER, weight=ft.FontWeight.BOLD),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ],
                spacing=4,
            ),
            bgcolor=AppTheme.SURFACE_VARIANT,
            padding=ft.Padding(12, 10, 12, 10),
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        # Amount Input
        calc_default = min(default_amount, self.pending_balance) if self.pending_balance > 0 else default_amount
        self.amount_input = ft.TextField(
            label="Amount Paying Now (₹) *",
            value=f"{calc_default:.0f}",
            keyboard_type=ft.KeyboardType.NUMBER,
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_H3,
            prefix_icon=ft.Icons.CURRENCY_RUPEE,
            hint_text="Minimum ₹500 required for confirmation",
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
        )

        # Transaction Ref (optional)
        self.tx_ref_input = ft.TextField(
            label="Transaction Ref / UPI ID (Optional)",
            hint_text="e.g. UPI Ref / Bank UTR",
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
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

        self.content = ft.Container(
            width=480,
            content=ft.Column(
                controls=[
                    summary_card,
                    self.error_container,
                    self.amount_input,
                    ft.Row(controls=[self.mode_dropdown, self.collector_dropdown], spacing=AppTheme.PAD_SM),
                    self.pin_input,
                    self.tx_ref_input,
                ],
                spacing=AppTheme.PAD_MD,
                tight=True,
            ),
        )

        self.actions = [self.cancel_btn, self.verify_btn]
        self.actions_alignment = ft.MainAxisAlignment.END

    def _show_error(self, msg: str) -> None:
        self.error_text.value = msg
        self.error_container.visible = True
        self.verify_btn.disabled = False
        self.verify_btn_text.value = "Verify & Confirm Payment"
        self._safe_update()

    @property
    def safe_page(self) -> Optional[ft.Page]:
        try:
            return self.page
        except (RuntimeError, AttributeError):
            return getattr(self, "_page", None)

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

    def handle_confirm_payment(self, e: ft.ControlEvent) -> None:
        self.error_container.visible = False
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

        if amount < 500.0:
            self._show_error("Minimum payment of ₹500 is required to confirm admission.")
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

            self.close_modal()
            self.on_payment_completed(payment_id)

        except (ValidationError, ServiceError) as ex:
            self._show_error(str(ex))
        except Exception as ex:
            LogService.error(f"Payment dialog confirmation error: {ex}", context=self.__class__.__name__)
            self._show_error("An unexpected error occurred during payment processing.")
