# modules/payments/views/payment_refund_dialog.py

from __future__ import annotations
from typing import Callable, Optional, Any
import flet as ft

from core.logger.service import LogService
from core.exceptions import ValidationError, ForbiddenError, ServiceError
from modules.payments.controller import PaymentController
from modules.payments.dto import PaymentDTO
from ui.themes.theme import AppTheme

__all__ = ["PaymentRefundDialog"]


class PaymentRefundDialog(ft.AlertDialog):
    """
    Administrator-exclusive dialog for reversing/refunding an accidental or erroneous payment.
    Enforces Administrator role, PIN authorization, voiding of linked receipts, ledger restoration,
    and automatic sequential installment re-numbering.
    """

    def __init__(
        self,
        payment: PaymentDTO,
        student_name: str,
        admission_number: str,
        on_refunded: Optional[Callable[[dict[str, Any]], None]] = None,
        page: Optional[ft.Page] = None,
    ) -> None:
        super().__init__()

        self.payment = payment
        self.student_name = student_name
        self.admission_number = admission_number
        self.on_refunded = on_refunded
        self._root_page = page
        self.modal = True

        self.controller = PaymentController()

        # ── Header ──
        self.title = ft.SelectionArea(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.UNDO, color=AppTheme.DANGER, size=24),
                    ft.Column(
                        controls=[
                            ft.Text("Payment Refund & Reversal", size=AppTheme.SIZE_H2, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                            ft.Text(
                                "Administrator Financial Governance — Reversal & Ledger Correction",
                                size=AppTheme.SIZE_CAPTION,
                                color=AppTheme.TEXT_SECONDARY,
                            ),
                        ],
                        spacing=2,
                    ),
                ],
                spacing=AppTheme.PAD_SM,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        # ── Error / Alert Banner ──
        self.error_banner = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE, size=18, color=AppTheme.DANGER),
                    ft.Text("", size=AppTheme.SIZE_CAPTION, color=AppTheme.DANGER, expand=True),
                ],
                spacing=AppTheme.PAD_XS,
            ),
            bgcolor=AppTheme.DANGER_LIGHT,
            padding=ft.Padding(10, 8, 10, 8),
            border_radius=AppTheme.RADIUS_SM,
            visible=False,
        )

        # ── Critical Warning Callout ──
        self.warning_callout = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.WARNING_AMBER, size=18, color=AppTheme.DANGER),
                            ft.Text("Financial Reversal Warning", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD, color=AppTheme.DANGER),
                        ],
                        spacing=6,
                    ),
                    ft.Text(
                        f"Reversing this transaction will void the issued receipt, remove the payment record, "
                        f"and restore ₹{self.payment.amount:,.2f} to the student's pending balance. "
                        f"This action is restricted to the Administrator and is logged in the permanent audit trail.",
                        size=11,
                        color=AppTheme.TEXT_PRIMARY,
                    ),
                ],
                spacing=4,
            ),
            bgcolor=AppTheme.DANGER_LIGHT,
            padding=ft.Padding(12, 10, 12, 10),
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.DANGER),
        )

        # ── Payment Details Card ──
        tx_ref_text = f"UTR: {self.payment.transaction_ref}" if self.payment.transaction_ref else "No UTR recorded"
        date_str = str(self.payment.payment_date or "")[:16]

        self.details_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("Student:", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_SECONDARY, width=80),
                            ft.Text(self.student_name, size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                            ft.Container(
                                content=ft.Text(f"#{self.admission_number}", size=11, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                                bgcolor=AppTheme.PRIMARY_LIGHT,
                                padding=ft.Padding(6, 2, 6, 2),
                                border_radius=AppTheme.RADIUS_SM,
                            ),
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        controls=[
                            ft.Text("Amount:", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_SECONDARY, width=80),
                            ft.Text(f"₹{self.payment.amount:,.2f}", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color=AppTheme.DANGER),
                            ft.Container(
                                content=ft.Text(f"Installment #{self.payment.installment_number}", size=11, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                                bgcolor=AppTheme.PRIMARY_LIGHT,
                                padding=ft.Padding(6, 2, 6, 2),
                                border_radius=AppTheme.RADIUS_SM,
                            ),
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        controls=[
                            ft.Text("Details:", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_SECONDARY, width=80),
                            ft.Text(f"Mode: {self.payment.payment_mode}  |  {tx_ref_text}  |  {date_str}", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                        ],
                        spacing=6,
                    ),
                ],
                spacing=6,
            ),
            bgcolor=AppTheme.SURFACE_VARIANT,
            padding=ft.Padding(12, 10, 12, 10),
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        # ── Mandatory Reason Field ──
        self.reason_input = ft.TextField(
            label="Reason for Refund / Accidental Correction *",
            hint_text="e.g. Credited to wrong student by mistake / Cash returned",
            multiline=True,
            min_lines=2,
            max_lines=3,
            text_size=AppTheme.SIZE_BODY,
            border_radius=AppTheme.RADIUS_MD,
            border_color=AppTheme.BORDER,
            focused_border_color=AppTheme.DANGER,
        )

        # ── Administrator Security PIN ──
        self.admin_pin_input = ft.TextField(
            label="Administrator Security PIN *",
            hint_text="Enter 4-digit PIN",
            password=True,
            can_reveal_password=True,
            keyboard_type=ft.KeyboardType.NUMBER,
            width=220,
            text_size=AppTheme.SIZE_BODY,
            border_radius=AppTheme.RADIUS_MD,
            border_color=AppTheme.BORDER,
            focused_border_color=AppTheme.DANGER,
        )

        self.content = ft.Container(
            content=ft.Column(
                controls=[
                    self.error_banner,
                    self.warning_callout,
                    self.details_card,
                    self.reason_input,
                    self.admin_pin_input,
                ],
                spacing=AppTheme.PAD_SM,
                tight=True,
            ),
            width=500,
        )

        # ── Actions ──
        self.cancel_btn = ft.TextButton(
            content=ft.Text("Cancel"),
            on_click=self.close_dialog,
        )
        self.refund_btn = ft.ElevatedButton(
            content=ft.Text("Confirm Refund & Reverse"),
            icon=ft.Icons.UNDO,
            style=ft.ButtonStyle(
                bgcolor=AppTheme.DANGER,
                color=AppTheme.SURFACE,
                padding=ft.Padding(16, 10, 16, 10),
            ),
            on_click=self._handle_confirm_refund,
        )

        self.actions = [self.cancel_btn, self.refund_btn]
        self.actions_alignment = ft.MainAxisAlignment.END

    @property
    def safe_page(self) -> Optional[ft.Page]:
        try:
            return self._root_page or getattr(self, "page", None)
        except (RuntimeError, AttributeError):
            return self._root_page

    def _safe_update(self) -> None:
        p = self.safe_page
        if p:
            try:
                self.update()
            except Exception:
                pass

    def _show_error(self, message: str) -> None:
        row: ft.Row = self.error_banner.content
        row.controls[1].value = message
        self.error_banner.visible = True
        self._safe_update()

    def _clear_error(self) -> None:
        self.error_banner.visible = False
        self._safe_update()

    def _handle_confirm_refund(self, e: ft.ControlEvent) -> None:
        self._clear_error()

        reason = self.reason_input.value.strip() if self.reason_input.value else ""
        if not reason or len(reason) < 3:
            self._show_error("Please provide a valid explanation for the refund (at least 3 characters).")
            return

        pin = self.admin_pin_input.value.strip() if self.admin_pin_input.value else ""
        if not pin:
            self._show_error("Administrator Security PIN is required.")
            return

        self.refund_btn.disabled = True
        self.refund_btn.content = ft.Row(
            controls=[
                ft.ProgressRing(width=16, height=16, stroke_width=2, color=AppTheme.SURFACE),
                ft.Text("Processing Refund..."),
            ],
            spacing=6,
            tight=True,
        )
        self._safe_update()

        try:
            result = self.controller.refund_payment(
                payment_id=self.payment.id,
                reason=reason,
                admin_pin=pin,
            )
            LogService.info(
                f"Successfully refunded payment #{self.payment.id} for student {self.student_name}: {result}",
                context="PaymentRefundDialog",
            )

            p = self.safe_page
            self.open = False
            if p:
                if hasattr(p, "pop_dialog"):
                    try:
                        p.pop_dialog()
                    except Exception:
                        pass
                p.show_snack_bar(
                    ft.SnackBar(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.CHECK_CIRCLE, color=AppTheme.SUCCESS),
                                ft.Text(
                                    f"Payment of ₹{self.payment.amount:,.2f} refunded! Student balance restored.",
                                    color=AppTheme.SURFACE,
                                    weight=ft.FontWeight.BOLD,
                                ),
                            ],
                            spacing=AppTheme.PAD_SM,
                        ),
                        bgcolor=AppTheme.PRIMARY,
                        duration=4000,
                    )
                )

            if self.on_refunded:
                self.on_refunded(result)

        except (ValidationError, ForbiddenError) as err:
            self._show_error(str(err))
            self.refund_btn.disabled = False
            self.refund_btn.content = ft.Text("Confirm Refund & Reverse")
            self._safe_update()
        except Exception as ex:
            LogService.error(f"Refund failure: {ex}", context="PaymentRefundDialog")
            self._show_error(f"Refund failed: {ex}")
            self.refund_btn.disabled = False
            self.refund_btn.content = ft.Text("Confirm Refund & Reverse")
            self._safe_update()

    def close_dialog(self, e: Optional[ft.ControlEvent] = None) -> None:
        p = self.safe_page
        self.open = False
        if p and hasattr(p, "pop_dialog"):
            try:
                p.pop_dialog()
            except Exception:
                pass
        self._safe_update()
