# ui/screens/break_glass.py

from __future__ import annotations
import flet as ft
from datetime import datetime, timezone
from typing import Optional

from core.exceptions import AuthenticationError, ValidationError
from core.security.recovery import BreakGlassService, RecoveryKeyService
from ui.themes.theme import AppTheme

__all__ = ["BreakGlassClaimScreen", "BreakGlassRemediationScreen"]


class BreakGlassClaimScreen(ft.Container):
    """
    Emergency Break-Glass Access Claim Screen.

    Provides high-entropy emergency recovery when normal authentication channels fail.
    Claims an exclusive 10-minute remediation lease upon verifying the 256-bit recovery key.
    """

    def __init__(self, page: ft.Page) -> None:
        super().__init__(
            expand=True,
            alignment=ft.Alignment.CENTER,
            bgcolor=AppTheme.BACKGROUND,
        )
        self._page = page

        self.username_field = ft.TextField(
            label="Administrator Username",
            value="administrator",
            prefix_icon=ft.Icons.PERSON_OUTLINE,
            width=360,
        )

        self.key_field = ft.TextField(
            label="Emergency Recovery Key",
            hint_text="SIMS-XXXX-XXXX-XXXX-... (52 chars)",
            prefix_icon=ft.Icons.KEY,
            text_size=13,
            width=360,
            autofocus=True,
            multiline=True,
            min_lines=2,
            max_lines=3,
        )

        self.status_message = ft.Text("", size=13, text_align=ft.TextAlign.CENTER, weight=ft.FontWeight.W_500)

        self.claim_btn = ft.ElevatedButton(
            content=ft.Text("Claim Emergency Access", weight=ft.FontWeight.BOLD),
            icon=ft.Icons.WARNING_AMBER,
            width=260,
            height=45,
            bgcolor=AppTheme.DANGER,
            color=ft.Colors.WHITE,
            on_click=self._handle_claim,
        )

        self.back_to_login_btn = ft.TextButton(
            content=ft.Text("← Cancel and Return to Sign In"),
            on_click=lambda _: self._page.navigate("/login"),
        )

        self.card_container = ft.Container(
            width=480,
            padding=AppTheme.PAD_LG,
            bgcolor=AppTheme.SURFACE,
            border_radius=AppTheme.RADIUS_LG,
            border=ft.Border.all(2, AppTheme.DANGER),
            content=ft.Column(
                tight=True,
                spacing=16,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.WARNING_ROUNDED, size=56, color=AppTheme.DANGER),
                    ft.Column(
                        controls=[
                            ft.Text("Emergency Break-Glass", size=22, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                            ft.Text("High-Entropy Disaster Recovery Access", size=13, color=AppTheme.DANGER, weight=ft.FontWeight.BOLD),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=2,
                    ),
                    ft.Container(
                        content=ft.Text(
                            "WARNING: Claiming Break-Glass grants a strictly monitored, 10-minute remediation lease. "
                            "Upon successful completion, your password will be reset, all active sessions will be terminated, "
                            "and this recovery key will be permanently consumed and rotated.",
                            size=12,
                            color=AppTheme.TEXT_SECONDARY,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        padding=ft.Padding(12, 8, 12, 8),
                        bgcolor=AppTheme.SURFACE_VARIANT,
                        border_radius=AppTheme.RADIUS_SM,
                    ),
                    self.username_field,
                    self.key_field,
                    self.status_message,
                    self.claim_btn,
                    self.back_to_login_btn,
                ],
            ),
        )
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

    def _handle_claim(self, e: ft.ControlEvent) -> None:
        username = (self.username_field.value or "").strip()
        raw_key = (self.key_field.value or "").strip()

        if not username:
            self._show_error("Please enter the administrator username.")
            return

        if not raw_key:
            self._show_error("Please enter the emergency recovery key.")
            return

        try:
            lease_info = BreakGlassService.claim_break_glass(
                username=username,
                submitted_recovery_key=raw_key,
            )
            # Store claimed lease in Flet session
            sess = getattr(self._page, "session", None)
            store = getattr(sess, "store", sess)
            if hasattr(store, "set"):
                store.set("break_glass_lease", lease_info)
            elif isinstance(store, dict):
                store["break_glass_lease"] = lease_info

            self._page.navigate("/recovery/remediate")
        except Exception as exc:
            self._show_error(str(exc))


class BreakGlassRemediationScreen(ft.Container):
    """
    Constrained Break-Glass Remediation Console.

    Accessible ONLY with a valid, active unexpired lease claimed via BreakGlassService.
    Permits updating credentials and forces mandatory viewing and confirmation of replacement recovery key.
    """

    def __init__(self, page: ft.Page) -> None:
        super().__init__(
            expand=True,
            alignment=ft.Alignment.CENTER,
            bgcolor=AppTheme.BACKGROUND,
        )
        self._page = page
        self.lease: Optional[dict] = None
        self.replacement_key: Optional[str] = None
        self.replacement_key_id: Optional[str] = None
        self.is_completed: bool = False

        # Form Controls
        self.lease_banner = ft.Text("", size=12, color=AppTheme.DANGER, weight=ft.FontWeight.BOLD)
        self.new_password_field = ft.TextField(
            label="New Administrator Password (min 8 chars)",
            password=True,
            can_reveal_password=True,
            width=360,
            prefix_icon=ft.Icons.LOCK_OUTLINE,
        )
        self.confirm_password_field = ft.TextField(
            label="Confirm New Password",
            password=True,
            can_reveal_password=True,
            width=360,
            prefix_icon=ft.Icons.LOCK_RESET,
        )
        self.new_email_field = ft.TextField(
            label="Emergency Contact Email (Optional Update)",
            hint_text="Leave blank to preserve current email",
            prefix_icon=ft.Icons.EMAIL_OUTLINED,
            width=360,
        )
        self.status_message = ft.Text("", size=13, text_align=ft.TextAlign.CENTER, weight=ft.FontWeight.W_500)

        self.commit_btn = ft.ElevatedButton(
            content=ft.Text("Commit Emergency Remediation", weight=ft.FontWeight.BOLD),
            icon=ft.Icons.SHIELD,
            width=280,
            height=45,
            bgcolor=AppTheme.DANGER,
            color=ft.Colors.WHITE,
            on_click=self._handle_remediation_commit,
        )

        self.cancel_btn = ft.TextButton(
            content=ft.Text("Cancel Emergency Lease & Exit"),
            on_click=self._handle_cancel_lease,
        )

        self.card_container = ft.Container(
            width=500,
            padding=AppTheme.PAD_LG,
            bgcolor=AppTheme.SURFACE,
            border_radius=AppTheme.RADIUS_LG,
            border=ft.Border.all(2, AppTheme.DANGER),
        )

        self._check_lease_and_render()
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

    def _check_lease_and_render(self) -> None:
        sess = getattr(self._page, "session", None)
        store = getattr(sess, "store", sess)
        lease_data = None
        if hasattr(store, "get"):
            lease_data = store.get("break_glass_lease")
        elif isinstance(store, dict):
            lease_data = store.get("break_glass_lease")

        if not lease_data or not lease_data.get("lease_granted"):
            self._page.navigate("/login")
            return

        self.lease = lease_data
        expires_at = self.lease.get("expires_at", "in 10 minutes")
        self.lease_banner.value = f"EXCLUSIVE REMEDIATION LEASE ACTIVE (Expires: {expires_at})"
        if self.lease.get("current_email"):
            self.new_email_field.value = self.lease["current_email"]

        self._render_form()

    def _render_form(self) -> None:
        if not self.is_completed:
            self.card_container.content = ft.Column(
                tight=True,
                spacing=16,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.ADMIN_PANEL_SETTINGS, size=52, color=AppTheme.DANGER),
                    ft.Column(
                        controls=[
                            ft.Text("Emergency Remediation Console", size=22, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                            self.lease_banner,
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=4,
                    ),
                    ft.Container(height=4),
                    self.new_password_field,
                    self.confirm_password_field,
                    self.new_email_field,
                    self.status_message,
                    self.commit_btn,
                    self.cancel_btn,
                ],
            )
        else:
            # Replacement key presentation ceremony
            self.card_container.content = ft.Column(
                tight=True,
                spacing=16,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.KEY, size=52, color=AppTheme.SUCCESS),
                    ft.Text("Remediation Complete", size=22, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                    ft.Text(
                        "Your credentials have been updated and previous sessions invalidated.",
                        size=13,
                        color=AppTheme.TEXT_SECONDARY,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(f"NEW RECOVERY KEY [{self.replacement_key_id}]", size=12, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_SECONDARY),
                                ft.Container(
                                    content=ft.Text(
                                        self.replacement_key or "",
                                        size=14,
                                        weight=ft.FontWeight.BOLD,
                                        font_family="monospace",
                                        color=AppTheme.PRIMARY,
                                        selectable=True,
                                    ),
                                    padding=12,
                                    bgcolor=AppTheme.SURFACE_VARIANT,
                                    border_radius=AppTheme.RADIUS_SM,
                                ),
                                ft.Text(
                                    "Save this key immediately in an encrypted vault. It will NOT be shown again.",
                                    size=12,
                                    color=AppTheme.DANGER,
                                    weight=ft.FontWeight.BOLD,
                                ),
                            ],
                            spacing=6,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=12,
                        border=ft.Border.all(1, AppTheme.BORDER),
                        border_radius=AppTheme.RADIUS_MD,
                    ),
                    ft.ElevatedButton(
                        content=ft.Text("I Have Saved My Recovery Key — Sign In", weight=ft.FontWeight.BOLD),
                        icon=ft.Icons.LOGIN,
                        width=320,
                        height=45,
                        bgcolor=AppTheme.PRIMARY,
                        color=ft.Colors.WHITE,
                        on_click=self._handle_finish,
                    ),
                ],
            )

    def _handle_remediation_commit(self, e: ft.ControlEvent) -> None:
        if not self.lease:
            self._show_error("No active remediation lease.")
            return

        pwd = self.new_password_field.value or ""
        confirm = self.confirm_password_field.value or ""
        new_email = (self.new_email_field.value or "").strip() or None

        if not pwd or len(pwd) < 8:
            self._show_error("New password must be at least 8 characters long.")
            return

        if pwd != confirm:
            self._show_error("Passwords do not match.")
            return

        try:
            res = BreakGlassService.remediate(
                key_id=int(self.lease["key_id"]),
                session_id=str(self.lease["session_id"]),
                session_nonce=str(self.lease["session_nonce"]),
                user_id=int(self.lease["user_id"]),
                new_password=pwd,
                new_email=new_email,
            )
            self.replacement_key = res["replacement_recovery_key"]
            self.replacement_key_id = res["replacement_key_identifier"]
            self.is_completed = True
            self._render_form()
            self._safe_update()
        except Exception as exc:
            self._show_error(str(exc))

    def _handle_cancel_lease(self, e: ft.ControlEvent) -> None:
        if self.lease:
            try:
                BreakGlassService.cancel_lease(
                    key_id=int(self.lease["key_id"]),
                    session_id=str(self.lease["session_id"]),
                )
            except Exception:
                pass

        sess = getattr(self._page, "session", None)
        store = getattr(sess, "store", sess)
        if hasattr(store, "set"):
            store.set("break_glass_lease", None)
        elif isinstance(store, dict):
            store.pop("break_glass_lease", None)

        self._page.navigate("/login")

    def _handle_finish(self, e: ft.ControlEvent) -> None:
        sess = getattr(self._page, "session", None)
        store = getattr(sess, "store", sess)
        if hasattr(store, "set"):
            store.set("break_glass_lease", None)
        elif isinstance(store, dict):
            store.pop("break_glass_lease", None)

        self._page.navigate("/login")
