# ui/screens/control_center.py

from __future__ import annotations
from datetime import datetime
from typing import Callable, Optional
import flet as ft

from core.database.engine import DatabaseEngine
from core.database.migration import MigrationEngine
from core.exceptions import AuthenticationError, ForbiddenError, ValidationError
from core.security.auth import AuthService
from core.security.context import SecurityContext
from core.security.email_change import EmailChangeService
from core.security.recovery import RecoveryKeyService
from core.security.roles import Role
from modules.admission.activity_log_repository import ActivityLogRepository
from modules.settings.service import SettingsService
from modules.users.repository import UserRepository
from ui.themes.theme import AppTheme

__all__ = ["ControlCenterScreen"]


class ControlCenterScreen(ft.Container):
    """
    Dedicated SIMS Control Center.

    Exclusive landing and governance workspace for Administrator accounts.
    Displays security audit telemetry, privileged system status, and security controls.
    """

    def __init__(self, page: ft.Page, on_navigate: Optional[Callable[[str], None]] = None) -> None:
        super().__init__(
            expand=True,
            padding=ft.Padding(AppTheme.PAD_LG, AppTheme.PAD_MD, AppTheme.PAD_LG, AppTheme.PAD_MD),
            bgcolor=AppTheme.BACKGROUND,
        )
        self._page = page
        self.on_navigate = on_navigate or (lambda route: None)
        self.settings_service = SettingsService()
        self.activity_repo = ActivityLogRepository()

        # Audit Table
        self.audit_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Timestamp", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Action", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Actor", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Details", weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
            heading_row_color=AppTheme.SURFACE_VARIANT,
            border=ft.Border.all(1, AppTheme.BORDER),
            border_radius=AppTheme.RADIUS_MD,
        )

        # PIN management fields
        self.current_pin_field = ft.TextField(
            label="Current PIN",
            password=True,
            can_reveal_password=True,
            width=180,
            text_size=14,
        )
        self.new_pin_field = ft.TextField(
            label="New PIN (min 4 digits)",
            password=True,
            can_reveal_password=True,
            width=200,
            text_size=14,
        )
        self.pin_message_text = ft.Text("", size=13)

        self._build_ui()

    def _build_ui(self) -> None:
        username = SecurityContext.get_current_username() or "Administrator"

        header_card = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.ADMIN_PANEL_SETTINGS, size=32, color=AppTheme.PRIMARY),
                                    ft.Text("SIMS Control Center", size=24, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                                    ft.Container(
                                        content=ft.Text("PRIVILEGED MODE", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                        bgcolor=AppTheme.PRIMARY,
                                        padding=ft.Padding(8, 3, 8, 3),
                                        border_radius=AppTheme.RADIUS_SM,
                                    ),
                                ],
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Text(
                                f"Authenticated as: {username} • Full System Governance & Security Authority",
                                size=AppTheme.SIZE_BODY,
                                color=AppTheme.TEXT_SECONDARY,
                            ),
                        ],
                        spacing=4,
                    ),
                    ft.Row(
                        controls=[
                            ft.OutlinedButton(
                                content=ft.Text("Standard Dashboard"),
                                icon=ft.Icons.DASHBOARD,
                                on_click=lambda _: self.on_navigate("/dashboard"),
                            ),
                            ft.ElevatedButton(
                                content=ft.Text("Refresh Telemetry"),
                                icon=ft.Icons.REFRESH,
                                on_click=lambda _: self.load_data(),
                            ),
                        ],
                        spacing=10,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=AppTheme.PAD_MD,
            bgcolor=AppTheme.SURFACE,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        # Quick Actions Card
        quick_actions = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Privileged Governance Shortcuts", size=16, weight=ft.FontWeight.BOLD),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    ft.Row(
                        controls=[
                            ft.ElevatedButton(
                                content=ft.Text("Courses & Fees"),
                                icon=ft.Icons.MENU_BOOK,
                                on_click=lambda _: self.on_navigate("/courses"),
                            ),
                            ft.ElevatedButton(
                                content=ft.Text("Batch Scheduling"),
                                icon=ft.Icons.GROUP_WORK,
                                on_click=lambda _: self.on_navigate("/batch"),
                            ),
                            ft.ElevatedButton(
                                content=ft.Text("Student Registry"),
                                icon=ft.Icons.PEOPLE,
                                on_click=lambda _: self.on_navigate("/students"),
                            ),
                            ft.ElevatedButton(
                                content=ft.Text("General Settings"),
                                icon=ft.Icons.SETTINGS,
                                on_click=lambda _: self.on_navigate("/settings"),
                            ),
                        ],
                        spacing=12,
                        wrap=True,
                    ),
                ],
                spacing=12,
            ),
            padding=AppTheme.PAD_MD,
            bgcolor=AppTheme.SURFACE,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        # Security & Credential Governance Section
        security_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.SECURITY, size=20, color=AppTheme.PRIMARY),
                            ft.Text("Security & Credential Governance", size=16, weight=ft.FontWeight.BOLD),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Text(
                        "Manage Administrator security credentials, authorize Admin operational password resets, "
                        "update authentication email, or rotate your emergency Break-Glass recovery key.",
                        size=AppTheme.SIZE_CAPTION,
                        color=AppTheme.TEXT_SECONDARY,
                    ),
                    ft.Row(
                        controls=[
                            ft.ElevatedButton(
                                content=ft.Text("Reset Admin Password"),
                                icon=ft.Icons.LOCK_RESET,
                                on_click=self._show_reset_admin_password_dialog,
                            ),
                            ft.ElevatedButton(
                                content=ft.Text("Change My Password"),
                                icon=ft.Icons.PASSWORD,
                                on_click=self._show_change_password_dialog,
                            ),
                            ft.ElevatedButton(
                                content=ft.Text("Update Auth Email"),
                                icon=ft.Icons.MARK_EMAIL_READ,
                                on_click=self._show_update_email_dialog,
                            ),
                            ft.ElevatedButton(
                                content=ft.Text("Rotate Recovery Key"),
                                icon=ft.Icons.VPN_KEY,
                                on_click=self._show_rotate_recovery_key_dialog,
                            ),
                        ],
                        spacing=12,
                        wrap=True,
                    ),
                ],
                spacing=10,
            ),
            padding=AppTheme.PAD_MD,
            bgcolor=AppTheme.SURFACE,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        # PIN Management Section
        pin_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.LOCK_RESET, size=20, color=AppTheme.PRIMARY),
                            ft.Text("Payment & Authorization PIN Management", size=16, weight=ft.FontWeight.BOLD),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Text(
                        "Manage the 4-digit administrative authorization PIN used to approve payment confirmations and fee revisions.",
                        size=AppTheme.SIZE_CAPTION,
                        color=AppTheme.TEXT_SECONDARY,
                    ),
                    ft.Row(
                        controls=[
                            self.current_pin_field,
                            self.new_pin_field,
                            ft.ElevatedButton(
                                content=ft.Text("Update PIN"),
                                icon=ft.Icons.CHECK,
                                on_click=self._handle_pin_update,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=12,
                    ),
                    self.pin_message_text,
                ],
                spacing=10,
            ),
            padding=AppTheme.PAD_MD,
            bgcolor=AppTheme.SURFACE,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        # Audit Logs Section
        audit_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.SECURITY, size=20, color=AppTheme.PRIMARY),
                            ft.Text("Security & Authentication Audit Trail", size=16, weight=ft.FontWeight.BOLD),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(
                        content=self.audit_table,
                        border_radius=AppTheme.RADIUS_MD,
                    ),
                ],
                spacing=12,
            ),
            padding=AppTheme.PAD_MD,
            bgcolor=AppTheme.SURFACE,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        self.content = ft.ListView(
            controls=[
                header_card,
                ft.Container(height=12),
                quick_actions,
                ft.Container(height=12),
                security_section,
                ft.Container(height=12),
                pin_section,
                ft.Container(height=12),
                audit_section,
            ],
            spacing=0,
            expand=True,
        )

    def _open_dialog(self, dlg: ft.AlertDialog) -> None:
        p = self._page
        if not p:
            return
        if hasattr(p, "show_dialog"):
            p.show_dialog(dlg)
        elif hasattr(p, "open"):
            p.open(dlg)
        else:
            p.dialog = dlg
            dlg.open = True
            p.update()

    def _close_dialog(self, dlg: ft.AlertDialog) -> None:
        p = self._page
        if not p:
            return
        if hasattr(p, "pop_dialog"):
            p.pop_dialog()
        elif hasattr(p, "close"):
            p.close(dlg)
        else:
            dlg.open = False
            p.update()

    def _show_reset_admin_password_dialog(self, e: ft.ControlEvent) -> None:
        """Dialog workflow for resetting operational Admin password with OTP authorization."""
        admin_id = SecurityContext.get_current_user_id()
        if not admin_id:
            return

        reauth_pwd = ft.TextField(label="Administrator Password (Re-Authentication)", password=True, can_reveal_password=True)
        new_pwd = ft.TextField(label="New Admin Password (min 8 chars)", password=True, can_reveal_password=True)
        otp_field = ft.TextField(label="6-Digit Authorization OTP", max_length=6, text_align=ft.TextAlign.CENTER, visible=False)
        msg_text = ft.Text("", size=12)

        challenge_data = {"token": None, "new_pwd": None}

        def on_send_otp(_):
            msg_text.value = ""
            if not reauth_pwd.value or not new_pwd.value:
                msg_text.value = "Please enter both Administrator password and new Admin password."
                msg_text.color = AppTheme.DANGER
                dlg.update()
                return

            if len(new_pwd.value) < 8:
                msg_text.value = "New Admin password must be at least 8 characters long."
                msg_text.color = AppTheme.DANGER
                dlg.update()
                return

            try:
                res = AuthService.initiate_admin_password_reset(admin_id, reauth_pwd.value)
                challenge_data["token"] = res["challenge_token"]
                challenge_data["new_pwd"] = new_pwd.value

                reauth_pwd.visible = False
                new_pwd.visible = False
                otp_field.visible = True
                send_btn.visible = False
                confirm_btn.visible = True
                msg_text.value = f"Authorization OTP sent to {res['masked_email']}."
                msg_text.color = AppTheme.PRIMARY_HOVER
                dlg.update()
            except Exception as exc:
                msg_text.value = str(exc)
                msg_text.color = AppTheme.DANGER
                dlg.update()

        def on_confirm_reset(_):
            msg_text.value = ""
            otp_val = (otp_field.value or "").strip()
            if not otp_val or len(otp_val) != 6:
                msg_text.value = "Please enter a valid 6-digit OTP code."
                msg_text.color = AppTheme.DANGER
                dlg.update()
                return

            try:
                AuthService.complete_admin_password_reset(
                    administrator_user_id=admin_id,
                    challenge_token=challenge_data["token"],
                    submitted_otp=otp_val,
                    new_admin_password=challenge_data["new_pwd"],
                )
                self._close_dialog(dlg)
                self.load_data()
            except Exception as exc:
                msg_text.value = str(exc)
                msg_text.color = AppTheme.DANGER
                dlg.update()

        send_btn = ft.ElevatedButton("Send Authorization OTP", on_click=on_send_otp)
        confirm_btn = ft.ElevatedButton("Confirm & Reset Admin Password", on_click=on_confirm_reset, visible=False)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Reset Operational Admin Password", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=420,
                content=ft.Column(
                    controls=[
                        ft.Text("This ceremony requires Administrator re-authentication and email OTP authorization.", size=12, color=AppTheme.TEXT_SECONDARY),
                        reauth_pwd,
                        new_pwd,
                        otp_field,
                        msg_text,
                    ],
                    spacing=12,
                    tight=True,
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: self._close_dialog(dlg)),
                send_btn,
                confirm_btn,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._open_dialog(dlg)

    def _show_change_password_dialog(self, e: ft.ControlEvent) -> None:
        """Dialog for Administrator changing their own password."""
        user_id = SecurityContext.get_current_user_id()
        if not user_id:
            return

        curr_pwd = ft.TextField(label="Current Password", password=True, can_reveal_password=True)
        new_pwd = ft.TextField(label="New Password (min 8 chars)", password=True, can_reveal_password=True)
        confirm_pwd = ft.TextField(label="Confirm New Password", password=True, can_reveal_password=True)
        msg_text = ft.Text("", size=12)

        def do_change(_):
            if not curr_pwd.value or not new_pwd.value:
                msg_text.value = "Please complete all password fields."
                msg_text.color = AppTheme.DANGER
                dlg.update()
                return

            if new_pwd.value != confirm_pwd.value:
                msg_text.value = "New passwords do not match."
                msg_text.color = AppTheme.DANGER
                dlg.update()
                return

            try:
                AuthService.change_password(user_id, curr_pwd.value, new_pwd.value)
                self._close_dialog(dlg)
                self.load_data()
            except Exception as exc:
                msg_text.value = str(exc)
                msg_text.color = AppTheme.DANGER
                dlg.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Change Administrator Password", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=400,
                content=ft.Column(
                    controls=[curr_pwd, new_pwd, confirm_pwd, msg_text],
                    spacing=12,
                    tight=True,
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: self._close_dialog(dlg)),
                ft.ElevatedButton("Update Password", on_click=do_change),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._open_dialog(dlg)

    def _show_update_email_dialog(self, e: ft.ControlEvent) -> None:
        """Dialog workflow for dual-verification email update."""
        user_id = SecurityContext.get_current_user_id()
        if not user_id:
            return

        new_email = ft.TextField(label="New Email Address", hint_text="e.g. admin@school.edu")
        curr_otp = ft.TextField(label="Current Email Verification OTP", max_length=6, visible=False)
        new_otp = ft.TextField(label="New Email Verification OTP", max_length=6, visible=False)
        msg_text = ft.Text("", size=12)

        state = {"req_token": None, "curr_token": None, "new_token": None}

        def on_send_codes(_):
            email_val = (new_email.value or "").strip()
            if not email_val or "@" not in email_val:
                msg_text.value = "Please enter a valid email address."
                msg_text.color = AppTheme.DANGER
                dlg.update()
                return

            try:
                res = EmailChangeService.initiate_email_change(user_id, email_val)
                state["req_token"] = res["request_token"]
                state["curr_token"] = res["current_challenge_token"]
                state["new_token"] = res["new_challenge_token"]

                new_email.visible = False
                send_codes_btn.visible = False
                curr_otp.visible = True
                new_otp.visible = True
                finalize_btn.visible = True
                msg_text.value = "Verification codes sent to both current and new email addresses."
                msg_text.color = AppTheme.PRIMARY_HOVER
                dlg.update()
            except Exception as exc:
                msg_text.value = str(exc)
                msg_text.color = AppTheme.DANGER
                dlg.update()

        def on_finalize(_):
            c_val = (curr_otp.value or "").strip()
            n_val = (new_otp.value or "").strip()
            if not c_val or not n_val:
                msg_text.value = "Both verification codes must be entered."
                msg_text.color = AppTheme.DANGER
                dlg.update()
                return

            try:
                EmailChangeService.verify_current_email_otp(state["req_token"], state["curr_token"], c_val)
                EmailChangeService.verify_new_email_otp(state["req_token"], state["new_token"], n_val)
                EmailChangeService.finalize_email_change(state["req_token"])
                self._close_dialog(dlg)
                self.load_data()
            except Exception as exc:
                msg_text.value = str(exc)
                msg_text.color = AppTheme.DANGER
                dlg.update()

        send_codes_btn = ft.ElevatedButton("Send Verification Codes", on_click=on_send_codes)
        finalize_btn = ft.ElevatedButton("Verify & Finalize Email Change", on_click=on_finalize, visible=False)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Update Authentication Email", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=420,
                content=ft.Column(
                    controls=[
                        ft.Text("Dual verification is required to update your registered email.", size=12, color=AppTheme.TEXT_SECONDARY),
                        new_email,
                        curr_otp,
                        new_otp,
                        msg_text,
                    ],
                    spacing=12,
                    tight=True,
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: self._close_dialog(dlg)),
                send_codes_btn,
                finalize_btn,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._open_dialog(dlg)

    def _show_rotate_recovery_key_dialog(self, e: ft.ControlEvent) -> None:
        """Dialog for rotating Break-Glass emergency recovery key."""
        user_id = SecurityContext.get_current_user_id()
        if not user_id:
            return

        body_column = ft.Column(
            controls=[
                ft.Text(
                    "Rotating your Break-Glass Recovery Key will permanently revoke any active key. "
                    "A new 256-bit emergency key will be generated and dispatched to your email.",
                    size=13,
                    color=AppTheme.TEXT_SECONDARY,
                ),
            ],
            spacing=12,
            tight=True,
        )

        def do_rotate(_):
            try:
                key, key_id, deliv = RecoveryKeyService.issue_recovery_key(user_id, send_email=True)
                body_column.controls = [
                    ft.Text("New Recovery Key Generated Successfully", weight=ft.FontWeight.BOLD, color=AppTheme.SUCCESS),
                    ft.Text(f"Identifier: {key_id} • Email Delivery: {deliv}", size=12, color=AppTheme.TEXT_SECONDARY),
                    ft.Container(
                        content=ft.Text(key, size=13, weight=ft.FontWeight.BOLD, font_family="monospace", selectable=True),
                        padding=10,
                        bgcolor=AppTheme.SURFACE_VARIANT,
                        border_radius=AppTheme.RADIUS_SM,
                    ),
                    ft.Text("Store this key securely in an encrypted vault. It cannot be recovered later.", size=12, color=AppTheme.DANGER),
                ]
                rotate_btn.visible = False
                dlg.update()
                self.load_data()
            except Exception as exc:
                body_column.controls.append(ft.Text(f"Failed to rotate key: {exc}", color=AppTheme.DANGER, size=12))
                dlg.update()

        rotate_btn = ft.ElevatedButton("Rotate Key Now", on_click=do_rotate, style=ft.ButtonStyle(bgcolor=AppTheme.DANGER, color=ft.Colors.WHITE))

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Rotate Emergency Recovery Key", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=460,
                content=body_column,
            ),
            actions=[
                ft.TextButton("Close", on_click=lambda _: self._close_dialog(dlg)),
                rotate_btn,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._open_dialog(dlg)

    def _handle_pin_update(self, e: ft.ControlEvent) -> None:
        curr_pin = self.current_pin_field.value or ""
        new_pin = self.new_pin_field.value or ""

        try:
            self.settings_service.set_admin_pin(new_pin=new_pin, current_pin=curr_pin)
            self.pin_message_text.value = "Authorization PIN successfully updated."
            self.pin_message_text.color = AppTheme.SUCCESS
            self.current_pin_field.value = ""
            self.new_pin_field.value = ""
        except Exception as exc:
            self.pin_message_text.value = f"Failed to update PIN: {str(exc)}"
            self.pin_message_text.color = AppTheme.DANGER

        if self.page:
            self.update()

    def load_data(self) -> None:
        """Fetch and populate security audit trail logs."""
        try:
            logs = self.activity_repo.get_recent_logs(limit=25)
            # Filter or prioritize SECURITY events
            rows = []
            for log in logs:
                action = str(log.get("action", ""))
                is_sec = log.get("entity_type") == "SECURITY"
                badge_color = (
                    AppTheme.SUCCESS
                    if "SUCCESS" in action or "VERIFIED" in action
                    else (AppTheme.DANGER if "FAILURE" in action or "BLOCKED" in action or "LOCKED" in action else AppTheme.PRIMARY)
                )

                rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(str(log.get("created_at", "")))),
                            ft.DataCell(
                                ft.Container(
                                    content=ft.Text(
                                        action,
                                        size=12,
                                        weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.WHITE if is_sec else AppTheme.TEXT_PRIMARY,
                                    ),
                                    bgcolor=badge_color if is_sec else AppTheme.SURFACE_VARIANT,
                                    padding=ft.Padding(6, 2, 6, 2),
                                    border_radius=AppTheme.RADIUS_SM,
                                )
                            ),
                            ft.DataCell(ft.Text(str(log.get("actor_name", "SYSTEM")))),
                            ft.DataCell(ft.Text(str(log.get("details", "") or "—"))),
                        ]
                    )
                )
            self.audit_table.rows = rows
            if self.page:
                self.update()
        except Exception:
            pass
