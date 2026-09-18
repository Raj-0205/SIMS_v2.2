# ui/screens/login.py

from __future__ import annotations
import flet as ft
from typing import Optional

from core.exceptions import AuthenticationError
from core.configuration.service import ConfigService
from core.security.auth import AuthService
from core.security.roles import Role
from ui.themes.theme import AppTheme

__all__ = ["LoginScreen"]


class LoginScreen(ft.Container):
    """
    Dual-tier Enterprise Authentication UI for SIMS v2.2.

    Step 1: Role Intent Selection (Admin vs Administrator) + Username + Argon2id Password
    Step 2: Mandatory 6-Digit Email OTP Challenge Verification for Administrator accounts
    """

    def __init__(self, page: ft.Page) -> None:
        super().__init__(
            expand=True,
            alignment=ft.Alignment.CENTER,
            bgcolor=AppTheme.BACKGROUND,
        )
        self._page = page

        # State tracking
        self.current_step: int = 1  # 1: Credentials, 2: OTP
        self.challenge_token: Optional[str] = None
        self.masked_email: Optional[str] = None
        self.authenticated_user_id: Optional[int] = None
        self.pending_username: Optional[str] = None

        # Step 1 Controls
        self.role_selector = ft.SegmentedButton(
            selected=["ADMIN"],
            allow_multiple_selection=False,
            segments=[
                ft.Segment(
                    value="ADMIN",
                    label=ft.Text("Admin"),
                    icon=ft.Icon(ft.Icons.PERSON),
                ),
                ft.Segment(
                    value="ADMINISTRATOR",
                    label=ft.Text("Administrator"),
                    icon=ft.Icon(ft.Icons.SHIELD),
                ),
            ],
            on_change=self._on_role_intent_changed,
        )

        self.role_description_text = ft.Text(
            "Account: admin • Operational Account",
            size=12,
            color=AppTheme.TEXT_SECONDARY,
            text_align=ft.TextAlign.CENTER,
        )

        self.password_field = ft.TextField(
            label="Password",
            password=True,
            can_reveal_password=True,
            autofocus=True,
            prefix_icon=ft.Icons.LOCK_OUTLINE,
            on_submit=self.handle_login_step1,
        )

        self.step1_btn = ft.ElevatedButton(
            content=ft.Text("Sign In as Admin", weight=ft.FontWeight.BOLD),
            icon=ft.Icons.LOGIN,
            width=240,
            height=45,
            bgcolor=AppTheme.PRIMARY,
            color=ft.Colors.WHITE,
            on_click=self.handle_login_step1,
        )

        # Step 2 (OTP) Controls
        self.otp_info_text = ft.Text(
            "",
            size=13,
            color=AppTheme.TEXT_SECONDARY,
            text_align=ft.TextAlign.CENTER,
        )

        self.otp_field = ft.TextField(
            label="6-Digit Verification Code",
            text_align=ft.TextAlign.CENTER,
            text_size=22,
            max_length=6,
            width=220,
            autofocus=True,
            keyboard_type=ft.KeyboardType.NUMBER,
            prefix_icon=ft.Icons.PASSWORD,
            on_submit=self.handle_verify_otp,
        )

        self.verify_otp_btn = ft.ElevatedButton(
            content=ft.Text("Verify & Access", weight=ft.FontWeight.BOLD),
            icon=ft.Icons.VERIFIED_USER,
            width=240,
            height=45,
            bgcolor=AppTheme.PRIMARY,
            color=ft.Colors.WHITE,
            on_click=self.handle_verify_otp,
        )

        self.resend_otp_btn = ft.TextButton(
            content=ft.Text("Resend Verification Code"),
            icon=ft.Icons.SEND,
            on_click=self.handle_resend_otp,
        )

        self.back_to_step1_btn = ft.TextButton(
            content=ft.Text("← Back to Sign In"),
            on_click=self._reset_to_step1,
        )

        # Feedback banner
        self.status_message = ft.Text(
            "",
            size=13,
            text_align=ft.TextAlign.CENTER,
            weight=ft.FontWeight.W_500,
        )

        self.card_container = ft.Container(
            width=420,
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

    def _on_role_intent_changed(self, e: ft.ControlEvent) -> None:
        selected = next(iter(self.role_selector.selected), "ADMIN")
        if selected == "ADMINISTRATOR":
            self.role_description_text.value = "Account: administrator • Privileged Governance (Email OTP Required)"
            self.step1_btn.content = ft.Text("Continue to Verification", weight=ft.FontWeight.BOLD)
        else:
            self.role_description_text.value = "Account: admin • Operational Account"
            self.step1_btn.content = ft.Text("Sign In as Admin", weight=ft.FontWeight.BOLD)

        self.password_field.value = ""
        self.status_message.value = ""
        self._safe_update()

    def _show_error(self, message: str) -> None:
        self.status_message.value = message
        self.status_message.color = AppTheme.DANGER
        self._safe_update()

    def _show_info(self, message: str) -> None:
        self.status_message.value = message
        self.status_message.color = AppTheme.PRIMARY_HOVER
        self._safe_update()

    def _render_view(self) -> None:
        if self.current_step == 1:
            self.card_container.content = ft.Column(
                tight=True,
                spacing=16,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(
                        ft.Icons.SECURITY,
                        size=56,
                        color=AppTheme.PRIMARY,
                    ),
                    ft.Column(
                        controls=[
                            ft.Text("Sudharm SIMS", size=22, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                            ft.Text("Sign in to your account", size=13, color=AppTheme.TEXT_SECONDARY),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=2,
                    ),
                    ft.Container(height=4),
                    self.role_selector,
                    self.role_description_text,
                    ft.Container(height=6),
                    self.password_field,
                    self.status_message,
                    self.step1_btn,
                ],
            )
        else:
            self.card_container.content = ft.Column(
                tight=True,
                spacing=16,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(
                        ft.Icons.MARK_EMAIL_READ,
                        size=56,
                        color=AppTheme.PRIMARY,
                    ),
                    ft.Column(
                        controls=[
                            ft.Text("Two-Step Verification", size=22, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                            self.otp_info_text,
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=4,
                    ),
                    ft.Container(height=6),
                    self.otp_field,
                    self.status_message,
                    self.verify_otp_btn,
                    self.resend_otp_btn,
                    self.back_to_step1_btn,
                ],
            )

    def handle_login_step1(self, e: ft.ControlEvent) -> None:
        """Step 1: Authenticates credentials against DB and handles dual-tier flow."""
        self.status_message.value = ""
        password = self.password_field.value or ""
        selected_intent = next(iter(self.role_selector.selected), "ADMIN")
        username = "admin" if selected_intent == "ADMIN" else "administrator"

        if not password:
            self._show_error("Please enter your password.")
            return

        try:
            auth_result = AuthService.authenticate(
                username=username,
                password=password,
                intended_role=selected_intent,
            )
        except AuthenticationError as exc:
            self.password_field.value = ""
            self._show_error(str(exc))
            return
        except Exception as exc:
            self._show_error(f"Authentication system error: {str(exc)}")
            return

        if not auth_result.get("requires_otp"):
            # Normal Admin Flow -> Login & Navigate to /dashboard
            AuthService.login(self._page, auth_result["user"])
            self._page.navigate(auth_result.get("redirect_route", "/dashboard"))
        else:
            # Privileged Administrator Flow -> Advance to Step 2 (OTP)
            self.challenge_token = auth_result["challenge_token"]
            self.masked_email = auth_result["masked_email"]
            self.authenticated_user_id = auth_result["user_id"]
            self.pending_username = auth_result["username"]

            self.current_step = 2
            self.otp_info_text.value = f"A one-time verification code was sent to {self.masked_email}."
            self.otp_field.value = ""
            if ConfigService.app().environment == "development":
                self.status_message.value = "Dev Mode: Verification code saved to exports/notifications/dev_email_outbox.log"
                self.status_message.color = AppTheme.PRIMARY_HOVER
            else:
                self.status_message.value = ""
            self._render_view()
            self._safe_update()

    def handle_verify_otp(self, e: ft.ControlEvent) -> None:
        """Step 2: Verifies submitted 6-digit OTP code."""
        self.status_message.value = ""
        submitted_code = (self.otp_field.value or "").strip()

        if not submitted_code or len(submitted_code) != 6 or not submitted_code.isdigit():
            self._show_error("Please enter a valid 6-digit numerical code.")
            return

        if not self.challenge_token:
            self._show_error("Verification session expired. Please return to login.")
            return

        try:
            res = AuthService.verify_otp(
                challenge_token=self.challenge_token,
                submitted_otp=submitted_code,
            )
            # Authenticate Administrator in session
            AuthService.login(self._page, res["user"])
            # Navigate to Control Center
            self._page.navigate(res.get("redirect_route", "/control-center"))
        except AuthenticationError as exc:
            self.otp_field.value = ""
            self._show_error(str(exc))
        except Exception as exc:
            self._show_error(f"Verification error: {str(exc)}")

    def handle_resend_otp(self, e: ft.ControlEvent) -> None:
        """Requests a fresh OTP code and email dispatch."""
        if not self.challenge_token:
            self._show_error("Verification session expired. Please return to login.")
            return

        try:
            res = AuthService.resend_otp(self.challenge_token)
            self.challenge_token = res["challenge_token"]
            self.masked_email = res["masked_email"]
            self.otp_field.value = ""
            self._show_info(f"A new verification code has been dispatched to {self.masked_email}.")
        except Exception as exc:
            self._show_error(f"Failed to resend code: {str(exc)}")

    def _reset_to_step1(self, e: ft.ControlEvent) -> None:
        """Resets view back to Step 1 credentials form."""
        self.current_step = 1
        self.challenge_token = None
        self.masked_email = None
        self.password_field.value = ""
        self.status_message.value = ""
        self._render_view()
        self._safe_update()
