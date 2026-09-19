# ui/screens/recovery.py

from __future__ import annotations
import flet as ft
from typing import Optional

from core.exceptions import AuthenticationError, ValidationError
from core.security.password_recovery import PasswordRecoveryService
from ui.themes.theme import AppTheme

__all__ = ["PasswordRecoveryScreen"]


class PasswordRecoveryScreen(ft.Container):
    """
    Administrator Self-Service Password Recovery Screen.

    Step 1: Identify Account (Username or Registered Email)
    Step 2: Enter 6-Digit Email OTP Challenge
    Step 3: Set New Strong Password (minimum 8 characters)
    """

    def __init__(self, page: ft.Page) -> None:
        super().__init__(
            expand=True,
            alignment=ft.Alignment.CENTER,
            bgcolor=AppTheme.BACKGROUND,
        )
        self._page = page

        # Workflow State
        self.step: int = 1  # 1: Identify, 2: OTP, 3: New Password, 4: Done
        self.challenge_token: Optional[str] = None
        self.masked_email: Optional[str] = None
        self.reset_token: Optional[str] = None

        # Step 1 Controls
        self.identifier_field = ft.TextField(
            label="Username or Email Address",
            autofocus=True,
            prefix_icon=ft.Icons.ACCOUNT_CIRCLE_OUTLINE,
            width=320,
            on_submit=self._handle_step1_submit,
        )
        self.step1_btn = ft.ElevatedButton(
            content=ft.Text("Send Recovery Code", weight=ft.FontWeight.BOLD),
            icon=ft.Icons.SEND,
            width=240,
            height=45,
            bgcolor=AppTheme.PRIMARY,
            color=ft.Colors.WHITE,
            on_click=self._handle_step1_submit,
        )

        # Step 2 Controls
        self.otp_info_text = ft.Text("", size=13, color=AppTheme.TEXT_SECONDARY, text_align=ft.TextAlign.CENTER)
        self.otp_field = ft.TextField(
            label="6-Digit Recovery Code",
            text_align=ft.TextAlign.CENTER,
            text_size=22,
            max_length=6,
            width=220,
            autofocus=True,
            keyboard_type=ft.KeyboardType.NUMBER,
            prefix_icon=ft.Icons.PASSWORD,
            on_submit=self._handle_step2_submit,
        )
        self.step2_btn = ft.ElevatedButton(
            content=ft.Text("Verify Code", weight=ft.FontWeight.BOLD),
            icon=ft.Icons.CHECK_CIRCLE,
            width=240,
            height=45,
            bgcolor=AppTheme.PRIMARY,
            color=ft.Colors.WHITE,
            on_click=self._handle_step2_submit,
        )

        # Step 3 Controls
        self.new_password_field = ft.TextField(
            label="New Password (min 8 characters)",
            password=True,
            can_reveal_password=True,
            width=320,
            prefix_icon=ft.Icons.LOCK_OUTLINE,
        )
        self.confirm_password_field = ft.TextField(
            label="Confirm New Password",
            password=True,
            can_reveal_password=True,
            width=320,
            prefix_icon=ft.Icons.LOCK_RESET,
            on_submit=self._handle_step3_submit,
        )
        self.step3_btn = ft.ElevatedButton(
            content=ft.Text("Update Password", weight=ft.FontWeight.BOLD),
            icon=ft.Icons.SAVE,
            width=240,
            height=45,
            bgcolor=AppTheme.PRIMARY,
            color=ft.Colors.WHITE,
            on_click=self._handle_step3_submit,
        )

        # Common Navigation
        self.back_to_login_btn = ft.TextButton(
            content=ft.Text("← Back to Sign In"),
            on_click=lambda _: self._page.navigate("/login"),
        )

        # Status Message
        self.status_message = ft.Text("", size=13, text_align=ft.TextAlign.CENTER, weight=ft.FontWeight.W_500)

        # Container Card
        self.card_container = ft.Container(
            width=440,
            padding=AppTheme.PAD_LG,
            bgcolor=AppTheme.SURFACE,
            border_radius=AppTheme.RADIUS_LG,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        self._render_view()
        self.content = self.card_container

    def _safe_update(self) -> None:
        try:
            self.update()
        except Exception:
            pass

    def _show_error(self, message: str) -> None:
        self.status_message.value = message
        self.status_message.color = AppTheme.DANGER
        self._safe_update()

    def _show_info(self, message: str) -> None:
        self.status_message.value = message
        self.status_message.color = AppTheme.PRIMARY_HOVER
        self._safe_update()

    def _render_view(self) -> None:
        if self.step == 1:
            self.card_container.content = ft.Column(
                tight=True,
                spacing=16,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.LOCK_RESET, size=52, color=AppTheme.PRIMARY),
                    ft.Column(
                        controls=[
                            ft.Text("Password Recovery", size=22, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                            ft.Text("Recover Administrator Account Access", size=13, color=AppTheme.TEXT_SECONDARY),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=2,
                    ),
                    ft.Container(height=4),
                    self.identifier_field,
                    self.status_message,
                    self.step1_btn,
                    self.back_to_login_btn,
                ],
            )
        elif self.step == 2:
            self.card_container.content = ft.Column(
                tight=True,
                spacing=16,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.MARK_EMAIL_READ, size=52, color=AppTheme.PRIMARY),
                    ft.Column(
                        controls=[
                            ft.Text("Enter Verification Code", size=22, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                            self.otp_info_text,
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=4,
                    ),
                    ft.Container(height=4),
                    self.otp_field,
                    self.status_message,
                    self.step2_btn,
                    self.back_to_login_btn,
                ],
            )
        elif self.step == 3:
            self.card_container.content = ft.Column(
                tight=True,
                spacing=16,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.VPN_KEY, size=52, color=AppTheme.PRIMARY),
                    ft.Column(
                        controls=[
                            ft.Text("Set New Password", size=22, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                            ft.Text("Choose a strong new password for your account", size=13, color=AppTheme.TEXT_SECONDARY),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=2,
                    ),
                    ft.Container(height=4),
                    self.new_password_field,
                    self.confirm_password_field,
                    self.status_message,
                    self.step3_btn,
                    self.back_to_login_btn,
                ],
            )
        else:
            self.card_container.content = ft.Column(
                tight=True,
                spacing=16,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.CHECK_CIRCLE, size=56, color=AppTheme.SUCCESS),
                    ft.Text("Password Successfully Reset", size=22, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                    ft.Text(
                        "Your Administrator password has been securely updated. All previous active sessions have been terminated.",
                        size=13,
                        color=AppTheme.TEXT_SECONDARY,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=8),
                    ft.ElevatedButton(
                        content=ft.Text("Sign In Now", weight=ft.FontWeight.BOLD),
                        icon=ft.Icons.LOGIN,
                        width=240,
                        height=45,
                        bgcolor=AppTheme.PRIMARY,
                        color=ft.Colors.WHITE,
                        on_click=lambda _: self._page.navigate("/login"),
                    ),
                ],
            )

    def _handle_step1_submit(self, e: ft.ControlEvent) -> None:
        query = (self.identifier_field.value or "").strip()
        if not query:
            self._show_error("Please enter your username or email address.")
            return

        try:
            res = PasswordRecoveryService.request_recovery(query)
            if res.get("challenge_token"):
                self.challenge_token = res["challenge_token"]
                self.masked_email = res.get("masked_email")
                self.step = 2
                self.otp_info_text.value = f"A recovery code was sent to {self.masked_email}."
                self.status_message.value = ""
                self._render_view()
                self._safe_update()
            else:
                # Anti-enumeration message
                self._show_info(res.get("message", "If a matching account exists, a recovery code has been sent."))
        except Exception as exc:
            self._show_error(str(exc))

    def _handle_step2_submit(self, e: ft.ControlEvent) -> None:
        code = (self.otp_field.value or "").strip()
        if not code or len(code) != 6 or not code.isdigit():
            self._show_error("Please enter a valid 6-digit numerical code.")
            return

        if not self.challenge_token:
            self._show_error("Recovery session expired. Please restart.")
            return

        try:
            token = PasswordRecoveryService.verify_recovery_otp(self.challenge_token, code)
            self.reset_token = token
            self.step = 3
            self.status_message.value = ""
            self._render_view()
            self._safe_update()
        except Exception as exc:
            self.otp_field.value = ""
            self._show_error(str(exc))

    def _handle_step3_submit(self, e: ft.ControlEvent) -> None:
        pwd = self.new_password_field.value or ""
        confirm = self.confirm_password_field.value or ""

        if not pwd or len(pwd) < 8:
            self._show_error("Password must be at least 8 characters long.")
            return

        if pwd != confirm:
            self._show_error("Passwords do not match.")
            return

        if not self.reset_token:
            self._show_error("Reset token expired. Please restart.")
            return

        try:
            PasswordRecoveryService.complete_password_reset(self.reset_token, pwd)
            self.step = 4
            self._render_view()
            self._safe_update()
        except Exception as exc:
            self._show_error(str(exc))
