# tests/test_human_tester_ground_level.py

from __future__ import annotations
import hashlib
import hmac
import os
import sys
import unittest
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Optional
import flet as ft

PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.configuration.service import ConfigService
from core.database.engine import DatabaseEngine
from core.database.migration import MigrationEngine
from core.database.transaction import TransactionManager
from core.exceptions import (
    AuthenticationError,
    ConflictError,
    ForbiddenError,
    RateLimitExceededError,
    ValidationError,
)
from core.security.auth import AuthService
from core.security.authorization import AuthorizationService
from core.security.context import SecurityContext
from core.security.email_change import EmailChangeService
from core.security.otp import OTPPurpose, OTPService
from core.security.password_recovery import PasswordRecoveryService
from core.security.permissions import Permission, SecurityPermission
from core.security.recovery import BreakGlassService, RecoveryKeyService
from core.security.roles import Role
from infrastructure.notification.smtp_transport import SmtpTransport
from modules.settings.service import SettingsService
from modules.users.repository import UserRepository

from ui.router import AppRouter
from ui.screens.login import LoginScreen
from ui.screens.dashboard import DashboardScreen
from ui.screens.control_center import ControlCenterScreen
from ui.screens.recovery import PasswordRecoveryScreen
from ui.screens.break_glass import BreakGlassClaimScreen, BreakGlassRemediationScreen


class MockSessionStore:
    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def get(self, key: str) -> Any:
        return self._data.get(key)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def contains_key(self, key: str) -> bool:
        return key in self._data

    def pop(self, key: str, default: Any = None) -> Any:
        return self._data.pop(key, default)

    def clear(self) -> None:
        self._data.clear()


class MockFletSession:
    def __init__(self) -> None:
        self.store = MockSessionStore()

    def get(self, key: str) -> Any:
        return self.store.get(key)

    def set(self, key: str, value: Any) -> None:
        self.store.set(key, value)

    def pop(self, key: str, default: Any = None) -> Any:
        return self.store.pop(key, default)

    def clear(self) -> None:
        self.store.clear()


class MockRouteChangeEvent:
    def __init__(self, route: str) -> None:
        self.route = route


class MockFletPage:
    """Simulates Flet 0.85 Page for human-like end-to-end testing."""

    def __init__(self) -> None:
        self.session = MockFletSession()
        self.route = "/login"
        self.views: list[ft.View] = []
        self.dialog: Optional[ft.AlertDialog] = None
        self.on_route_change: Optional[Callable[[Any], None]] = None

    def navigate(self, route: str) -> None:
        self.route = route
        if self.on_route_change:
            self.on_route_change(MockRouteChangeEvent(route=route))

    def update(self) -> None:
        pass

    def open(self, dlg: ft.AlertDialog) -> None:
        self.dialog = dlg
        dlg.open = True
        try:
            dlg._page = self
        except Exception:
            pass

    def close(self, dlg: ft.AlertDialog) -> None:
        if self.dialog == dlg:
            dlg.open = False
            self.dialog = None

    def show_dialog(self, dlg: ft.AlertDialog) -> None:
        self.open(dlg)

    def pop_dialog(self) -> None:
        if self.dialog:
            self.dialog.open = False
            self.dialog = None


class TestHumanTesterGroundLevel(unittest.TestCase):
    """
    Ground-Level Reality Testing Suite.
    Simulates real human tester interactions across all UI forms, buttons, inputs,
    dialogs, route navigation, and security workflows in SIMS v2.2.
    """

    admin_user = "admin"
    admin_pass = "AdminGround123!"
    admin_id: int = 1

    super_user = "administrator"
    super_pass = "SuperGround456!"
    super_email = "tester_super@groundlevel.local"
    super_id: int = 2

    dispatched_emails: list[dict[str, Any]] = []

    @classmethod
    def setUpClass(cls) -> None:
        ConfigService.initialize()
        if not DatabaseEngine.is_initialized():
            DatabaseEngine.initialize()
        MigrationEngine._is_initialized = False
        MigrationEngine.initialize()
        MigrationEngine.upgrade()

        # Capture emails in memory sink
        cls.dispatched_emails = []

        def test_sink(to_email: str, subject: str, body_text: str, body_html: Optional[str] = None) -> None:
            cls.dispatched_emails.append({
                "to": to_email,
                "subject": subject,
                "body_text": body_text,
                "body_html": body_html,
                "timestamp": datetime.now(timezone.utc),
            })

        SmtpTransport.set_test_sink(test_sink)

    @classmethod
    def tearDownClass(cls) -> None:
        SmtpTransport.clear_test_sink()
        SecurityContext.clear()

    def setUp(self) -> None:
        TestHumanTesterGroundLevel.dispatched_emails.clear()
        SecurityContext.clear()

        # Seed test users
        with DatabaseEngine.connection() as conn:
            conn.execute("DELETE FROM auth_recovery_keys")
            conn.execute("DELETE FROM auth_otp_challenges")
            conn.execute("DELETE FROM auth_email_change_requests")
            conn.execute("DELETE FROM auth_password_reset_tokens")
            conn.execute("DELETE FROM users")

            # Seed Admin (id=1)
            h_adm = AuthService.hash_password(self.admin_pass)
            conn.execute(
                """
                INSERT INTO users (id, username, password_hash, role, is_active, security_version, security_stamp)
                VALUES (1, 'admin', ?, 'ADMIN', 1, 1, 'stamp_admin_001');
                """,
                (h_adm,),
            )
            self.__class__.admin_id = 1

            # Seed Administrator (id=2)
            h_sup = AuthService.hash_password(self.super_pass)
            conn.execute(
                """
                INSERT INTO users (id, username, password_hash, role, email, is_active, security_version, security_stamp)
                VALUES (2, 'administrator', ?, 'ADMINISTRATOR', ?, 1, 1, 'stamp_administrator_001');
                """,
                (h_sup, self.super_email),
            )
            self.__class__.super_id = 2
            conn.commit()

        # Issue initial recovery key for administrator
        RecoveryKeyService.issue_recovery_key(self.super_id, send_email=False)

    def tearDown(self) -> None:
        SecurityContext.clear()

    def _get_user(self, user_id: int) -> dict[str, Any]:
        with DatabaseEngine.connection() as conn:
            c = conn.cursor()
            c.execute("SELECT id, username, password_hash, role, email, is_active, security_version, security_stamp FROM users WHERE id = ?", (user_id,))
            row = c.fetchone()
            if not row:
                raise RuntimeError(f"User {user_id} not found")
            return {
                "id": row[0],
                "username": row[1],
                "password_hash": row[2],
                "role": row[3],
                "email": row[4],
                "is_active": row[5],
                "security_version": row[6],
                "security_stamp": row[7],
            }

    def _get_user_by_username(self, username: str) -> dict[str, Any]:
        with DatabaseEngine.connection() as conn:
            c = conn.cursor()
            c.execute("SELECT id, username, password_hash, role, email, is_active, security_version, security_stamp FROM users WHERE username = ?", (username,))
            row = c.fetchone()
            if not row:
                raise RuntimeError(f"User {username} not found")
            return {
                "id": row[0],
                "username": row[1],
                "password_hash": row[2],
                "role": row[3],
                "email": row[4],
                "is_active": row[5],
                "security_version": row[6],
                "security_stamp": row[7],
            }

    def _get_latest_otp(self, purpose_keyword: str = "") -> str:
        with DatabaseEngine.connection() as conn:
            c = conn.cursor()
            if purpose_keyword:
                c.execute("SELECT otp_hash FROM auth_otp_challenges WHERE purpose LIKE ? ORDER BY id DESC LIMIT 1", (f"%{purpose_keyword}%",))
            else:
                c.execute("SELECT otp_hash FROM auth_otp_challenges ORDER BY id DESC LIMIT 1")
            row = c.fetchone()
            if not row:
                raise RuntimeError(f"No OTP challenge found in DB for keyword '{purpose_keyword}'.")
            otp_hash = row[0]

        salt, expected_digest = otp_hash.split("$", 1)
        salt_bytes = salt.encode("utf-8")
        for code in range(1_000_000):
            s_code = f"{code:06d}"
            digest = hashlib.sha256(salt_bytes + b":" + s_code.encode("utf-8")).hexdigest()
            if digest == expected_digest:
                return s_code
        raise RuntimeError("Failed to resolve OTP from hash.")

    # =========================================================================
    # JOURNEY 1: Operational Admin Human Login Journey
    # =========================================================================

    def test_journey_1_operational_admin_login(self) -> None:
        """Human Tester Journey 1: Operational Admin Logs In, Views Dashboard, and Logs Out."""
        page = MockFletPage()
        router = AppRouter(page)
        router.handle_route_change(MockRouteChangeEvent(route="/login"))

        self.assertEqual(len(page.views), 1)
        self.assertIsInstance(page.views[0].controls[0], LoginScreen)
        login_screen: LoginScreen = page.views[0].controls[0]

        # 1. Inspect initial UI state
        self.assertEqual(login_screen.current_step, 1)
        self.assertEqual(login_screen.role_selector.selected, ["ADMIN"])
        self.assertIn("Operational Account", login_screen.role_description_text.value)

        # 2. Human enters empty password
        login_screen.password_field.value = ""
        login_screen.handle_login_step1(None)
        self.assertEqual(login_screen.status_message.value, "Please enter your password.")

        # 3. Human enters wrong password
        login_screen.password_field.value = "WrongPassword999!"
        login_screen.handle_login_step1(None)
        self.assertEqual(login_screen.status_message.value, "Invalid username or password.")
        self.assertEqual(login_screen.password_field.value, "")

        # 4. Human enters correct operational Admin password
        login_screen.password_field.value = self.admin_pass
        login_screen.handle_login_step1(None)

        # Asserts successful single-tier login navigated to /dashboard
        self.assertEqual(page.route, "/dashboard")
        self.assertTrue(AuthService.is_authenticated(page))
        self.assertEqual(SecurityContext.get_current_role(), Role.ADMIN)

        # 5. Operational Admin attempts to access privileged /control-center
        router.handle_route_change(MockRouteChangeEvent(route="/control-center"))
        # Must be bounced back to /dashboard (Fail-closed authorization guard)
        self.assertEqual(page.route, "/dashboard")

        # 6. Operational Admin clicks Logout
        router.handle_route_change(MockRouteChangeEvent(route="/logout"))
        self.assertEqual(page.route, "/login")
        self.assertFalse(AuthService.is_authenticated(page))

    # =========================================================================
    # JOURNEY 2: Privileged Administrator 2FA Human Login Journey
    # =========================================================================

    def test_journey_2_privileged_administrator_2fa_login(self) -> None:
        """Human Tester Journey 2: Administrator selects role, completes Step 1 + Email OTP Step 2."""
        page = MockFletPage()
        router = AppRouter(page)
        router.handle_route_change(MockRouteChangeEvent(route="/login"))

        login_screen: LoginScreen = page.views[0].controls[0]

        # 1. Human switches role selector to ADMINISTRATOR
        login_screen.role_selector.selected = ["ADMINISTRATOR"]
        login_screen._on_role_intent_changed(None)

        self.assertIn("Privileged Governance", login_screen.role_description_text.value)
        self.assertEqual(login_screen.step1_btn.content.value, "Continue to Verification")

        # 2. Human enters wrong password
        login_screen.password_field.value = "WrongAdminPassword!"
        login_screen.handle_login_step1(None)
        self.assertEqual(login_screen.status_message.value, "Invalid username or password.")

        # 3. Human enters valid password
        login_screen.password_field.value = self.super_pass
        login_screen.handle_login_step1(None)

        # Asserts Step 2 (OTP) UI is rendered
        self.assertEqual(login_screen.current_step, 2)
        self.assertIsNotNone(login_screen.challenge_token)
        self.assertIn("@groundlevel.local", login_screen.otp_info_text.value)

        # 4. Human enters malformed OTP (non-digits or wrong length)
        login_screen.otp_field.value = "12abc"
        login_screen.handle_verify_otp(None)
        self.assertEqual(login_screen.status_message.value, "Please enter a valid 6-digit numerical code.")

        # 5. Human enters invalid 6-digit OTP
        login_screen.otp_field.value = "999999"
        login_screen.handle_verify_otp(None)
        self.assertIn("Incorrect verification code", login_screen.status_message.value)
        self.assertEqual(login_screen.otp_field.value, "")

        # 6. Human clicks Resend Code
        login_screen.handle_resend_otp(None)
        self.assertIn("A new verification code has been dispatched", login_screen.status_message.value)

        # 7. Human enters valid OTP
        valid_otp = self._get_latest_otp("LOGIN")
        login_screen.otp_field.value = valid_otp
        login_screen.handle_verify_otp(None)

        # Asserts successful verification navigated to /control-center
        self.assertEqual(page.route, "/control-center")
        self.assertTrue(AuthService.is_authenticated(page))
        self.assertEqual(SecurityContext.get_current_role(), Role.ADMINISTRATOR)

    # =========================================================================
    # JOURNEY 3: Administrator Control Center Governance & Dialog Ceremonies
    # =========================================================================

    def test_journey_3_control_center_governance_and_dialogs(self) -> None:
        """Human Tester Journey 3: Administrator exercises all Control Center modals and governance tools."""
        page = MockFletPage()
        router = AppRouter(page)

        # Authenticate as administrator
        user_dto = self._get_user(self.super_id)
        AuthService.login(page, user_dto)
        page.navigate("/control-center")

        self.assertEqual(page.route, "/control-center")
        control_center = ControlCenterScreen(page, on_navigate=router.request_navigation)

        # ---------------------------------------------------------------------
        # Ceremony 1: Reset Operational Admin Password Dialog
        # ---------------------------------------------------------------------
        control_center._show_reset_admin_password_dialog(None)
        self.assertIsNotNone(page.dialog)
        dlg: ft.AlertDialog = page.dialog

        # Extract dialog controls
        col = dlg.content.content
        reauth_field = col.controls[1]
        new_pwd_field = col.controls[2]
        otp_field = col.controls[3]
        msg_text = col.controls[4]
        send_btn = dlg.actions[1]
        confirm_btn = dlg.actions[2]

        # 1a. Submit empty
        send_btn.on_click(None)
        self.assertIn("Please enter both", msg_text.value)

        # 1b. Short new password (< 8 chars)
        reauth_field.value = self.super_pass
        new_pwd_field.value = "short"
        send_btn.on_click(None)
        self.assertIn("at least 8 characters", msg_text.value)

        # 1c. Invalid reauth password
        reauth_field.value = "WrongReauth123!"
        new_pwd_field.value = "BrandNewAdminPass2026!"
        send_btn.on_click(None)
        self.assertIn("Administrator re-authentication failed", msg_text.value)

        # 1d. Valid reauth -> Send OTP
        reauth_field.value = self.super_pass
        new_pwd_field.value = "BrandNewAdminPass2026!"
        send_btn.on_click(None)

        self.assertIn("Authorization OTP sent", msg_text.value)
        self.assertTrue(otp_field.visible)
        self.assertTrue(confirm_btn.visible)

        # 1e. Submit invalid OTP
        otp_field.value = "000000"
        confirm_btn.on_click(None)
        self.assertIn("Incorrect verification code", msg_text.value)

        # 1f. Submit valid OTP
        valid_otp = self._get_latest_otp("ADMIN_PASSWORD_RESET")
        otp_field.value = valid_otp
        confirm_btn.on_click(None)

        # Dialog should be closed
        self.assertIsNone(page.dialog)

        # Verify operational Admin password was updated in DB
        admin_rec = self._get_user_by_username("admin")
        self.assertTrue(AuthService.verify_password(admin_rec["password_hash"], "BrandNewAdminPass2026!"))

        # ---------------------------------------------------------------------
        # Ceremony 2: Change Administrator's Own Password Dialog
        # ---------------------------------------------------------------------
        control_center._show_change_password_dialog(None)
        self.assertIsNotNone(page.dialog)
        dlg2: ft.AlertDialog = page.dialog
        col2 = dlg2.content.content
        curr_p = col2.controls[0]
        new_p = col2.controls[1]
        conf_p = col2.controls[2]
        msg_p = col2.controls[3]
        update_btn = dlg2.actions[1]

        # 2a. Mismatched passwords
        curr_p.value = self.super_pass
        new_p.value = "SuperNewPass2026!"
        conf_p.value = "DifferentPass2026!"
        update_btn.on_click(None)
        self.assertIn("do not match", msg_p.value)

        # 2b. Wrong current password
        curr_p.value = "WrongCurrentPass!"
        new_p.value = "SuperNewPass2026!"
        conf_p.value = "SuperNewPass2026!"
        update_btn.on_click(None)
        self.assertIn("Current password is incorrect", msg_p.value)

        # 2c. Valid password change
        curr_p.value = self.super_pass
        new_p.value = "SuperNewPass2026!"
        conf_p.value = "SuperNewPass2026!"
        update_btn.on_click(None)

        self.assertIsNone(page.dialog)
        sup_rec = self._get_user(self.super_id)
        self.assertTrue(AuthService.verify_password(sup_rec["password_hash"], "SuperNewPass2026!"))
        self.__class__.super_pass = "SuperNewPass2026!"

        # ---------------------------------------------------------------------
        # Ceremony 3: Dual-Verification Email Update Dialog
        # ---------------------------------------------------------------------
        control_center._show_update_email_dialog(None)
        self.assertIsNotNone(page.dialog)
        dlg3: ft.AlertDialog = page.dialog
        col3 = dlg3.content.content
        email_in = col3.controls[1]
        c_otp_in = col3.controls[2]
        n_otp_in = col3.controls[3]
        msg_e = col3.controls[4]
        send_e_btn = dlg3.actions[1]
        fin_e_btn = dlg3.actions[2]

        # 3a. Invalid email format
        email_in.value = "invalid-email"
        send_e_btn.on_click(None)
        self.assertIn("valid email", msg_e.value)

        # 3b. Valid new email -> Send dual codes
        email_in.value = "new_gov_email@school.org"
        send_e_btn.on_click(None)
        self.assertIn("Verification codes sent", msg_e.value)
        self.assertTrue(c_otp_in.visible)
        self.assertTrue(n_otp_in.visible)
        self.assertTrue(fin_e_btn.visible)

        # 3c. Enter valid OTPs for current and new addresses
        c_otp_val = self._get_latest_otp("EMAIL_CHANGE_CURRENT")
        n_otp_val = self._get_latest_otp("EMAIL_CHANGE_NEW")

        c_otp_in.value = c_otp_val
        n_otp_in.value = n_otp_val
        fin_e_btn.on_click(None)

        self.assertIsNone(page.dialog)
        updated_rec = self._get_user(self.super_id)
        self.assertEqual(updated_rec["email"], "new_gov_email@school.org")

        # ---------------------------------------------------------------------
        # Ceremony 4: Emergency Recovery Key Rotation Dialog
        # ---------------------------------------------------------------------
        control_center._show_rotate_recovery_key_dialog(None)
        self.assertIsNotNone(page.dialog)
        dlg4: ft.AlertDialog = page.dialog
        rotate_action_btn = dlg4.actions[1]

        rotate_action_btn.on_click(None)

        body_texts = [c.value for c in dlg4.content.content.controls if isinstance(c, ft.Text)]
        self.assertTrue(any("Successfully" in t for t in body_texts))

        # Close dialog
        dlg4.actions[0].on_click(None)
        self.assertIsNone(page.dialog)

        # ---------------------------------------------------------------------
        # Ceremony 5: PIN Management Update
        # ---------------------------------------------------------------------
        # Set initial PIN in settings
        SettingsService().set_admin_pin("1234")

        # 5a. Invalid current PIN
        control_center.current_pin_field.value = "9999"
        control_center.new_pin_field.value = "5678"
        control_center._handle_pin_update(None)
        self.assertIn("Current Admin PIN is incorrect", control_center.pin_message_text.value)

        # 5b. Valid PIN update
        control_center.current_pin_field.value = "1234"
        control_center.new_pin_field.value = "5678"
        control_center._handle_pin_update(None)
        self.assertIn("successfully updated", control_center.pin_message_text.value)
        self.assertTrue(SettingsService().verify_admin_pin("5678"))

        # ---------------------------------------------------------------------
        # Ceremony 6: Telemetry Audit Refresh
        # ---------------------------------------------------------------------
        control_center.load_data()
        self.assertGreater(len(control_center.audit_table.rows), 0)

    # =========================================================================
    # JOURNEY 4: Self-Service Password Recovery Human Journey (/recovery)
    # =========================================================================

    def test_journey_4_self_service_password_recovery(self) -> None:
        """Human Tester Journey 4: Administrator navigates 3-step self-service recovery wizard."""
        page = MockFletPage()
        router = AppRouter(page)
        page.navigate("/recovery")

        self.assertEqual(len(page.views), 1)
        rec_screen: PasswordRecoveryScreen = page.views[0].controls[0]

        # 1. Step 1: Human enters non-existent identifier -> Uniform Anti-Enumeration response
        rec_screen.identifier_field.value = "non_existent_account_999@test.com"
        rec_screen._handle_step1_submit(None)
        self.assertEqual(rec_screen.step, 1)
        self.assertIn("If an Administrator account exists", rec_screen.status_message.value)

        # 2. Step 1: Human enters registered administrator username
        rec_screen.identifier_field.value = self.super_user
        rec_screen._handle_step1_submit(None)

        self.assertEqual(rec_screen.step, 2)
        self.assertIsNotNone(rec_screen.challenge_token)
        self.assertIn("@groundlevel.local", rec_screen.otp_info_text.value)

        # 3. Step 2: Human enters wrong OTP
        rec_screen.otp_field.value = "000000"
        rec_screen._handle_step2_submit(None)
        self.assertEqual(rec_screen.step, 2)
        self.assertIn("Incorrect verification code", rec_screen.status_message.value)

        # 4. Step 2: Human enters valid OTP
        valid_otp = self._get_latest_otp("PASSWORD_RESET")
        rec_screen.otp_field.value = valid_otp
        rec_screen._handle_step2_submit(None)

        self.assertEqual(rec_screen.step, 3)
        self.assertIsNotNone(rec_screen.reset_token)

        # 5. Step 3: Human enters mismatched passwords
        rec_screen.new_password_field.value = "NewRecoveredPass123!"
        rec_screen.confirm_password_field.value = "MismatchPass999!"
        rec_screen._handle_step3_submit(None)
        self.assertEqual(rec_screen.step, 3)
        self.assertEqual(rec_screen.status_message.value, "Passwords do not match.")

        # 6. Step 3: Human enters matching strong password
        rec_screen.new_password_field.value = "NewRecoveredPass123!"
        rec_screen.confirm_password_field.value = "NewRecoveredPass123!"
        rec_screen._handle_step3_submit(None)

        # Asserts Step 4 Success view
        self.assertEqual(rec_screen.step, 4)

        # Verify new password in DB
        sup_rec = self._get_user(self.super_id)
        self.assertTrue(AuthService.verify_password(sup_rec["password_hash"], "NewRecoveredPass123!"))

    # =========================================================================
    # JOURNEY 5: Emergency Break-Glass Disaster Recovery Human Journey
    # =========================================================================

    def test_journey_5_emergency_break_glass_disaster_recovery(self) -> None:
        """Human Tester Journey 5: Emergency Break-Glass Claim, 10-min lease, and credential remediation."""
        page = MockFletPage()
        router = AppRouter(page)

        # Issue fresh recovery key for administrator
        raw_key, key_id, _ = RecoveryKeyService.issue_recovery_key(self.super_id, send_email=False)

        # 1. Unauthenticated direct access to /recovery/remediate without lease must fail closed
        router.handle_route_change(MockRouteChangeEvent(route="/recovery/remediate"))
        self.assertEqual(page.route, "/login")

        # 2. Human navigates to /break-glass
        router.handle_route_change(MockRouteChangeEvent(route="/break-glass"))
        claim_screen: BreakGlassClaimScreen = page.views[0].controls[0]

        # 3. Human enters wrong recovery key
        claim_screen.username_field.value = self.super_user
        claim_screen.key_field.value = "SIMS-AAAA-BBBB-CCCC-DDDD-EEEE-FFFF-GGGG-HHHH-IIII-JJJJ-KKKK-LLLL"
        claim_screen._handle_claim(None)
        self.assertIn("Invalid recovery key", claim_screen.status_message.value)

        # 4. Human enters valid 52-char recovery key
        claim_screen.key_field.value = raw_key
        claim_screen._handle_claim(None)

        # Asserts navigated to /recovery/remediate with lease granted
        self.assertEqual(page.route, "/recovery/remediate")
        remediate_screen: BreakGlassRemediationScreen = page.views[0].controls[0]
        self.assertIsNotNone(remediate_screen.lease)
        self.assertTrue(remediate_screen.lease.get("lease_granted"))

        # 5. Human tests remediation form validation
        remediate_screen.new_password_field.value = "DisasterRecoveryPass2026!"
        remediate_screen.confirm_password_field.value = "MismatchPass!"
        remediate_screen._handle_remediation_commit(None)
        self.assertEqual(remediate_screen.status_message.value, "Passwords do not match.")

        # 6. Human commits valid remediation with new email
        remediate_screen.new_password_field.value = "DisasterRecoveryPass2026!"
        remediate_screen.confirm_password_field.value = "DisasterRecoveryPass2026!"
        remediate_screen.new_email_field.value = "disaster_recovered@school.org"
        remediate_screen._handle_remediation_commit(None)

        # Asserts replacement key ceremony screen rendered
        self.assertTrue(remediate_screen.is_completed)
        self.assertIsNotNone(remediate_screen.replacement_key)
        self.assertIsNotNone(remediate_screen.replacement_key_id)

        # 7. Human confirms "I Have Saved My Recovery Key"
        remediate_screen._handle_finish(None)
        self.assertEqual(page.route, "/login")

        # Asserts lease cleared from session
        self.assertIsNone(page.session.get("break_glass_lease"))

        # 8. Human verifies newly configured credentials work in Login
        sup_rec = self._get_user(self.super_id)
        self.assertTrue(AuthService.verify_password(sup_rec["password_hash"], "DisasterRecoveryPass2026!"))
        self.assertEqual(sup_rec["email"], "disaster_recovered@school.org")

    # =========================================================================
    # JOURNEY 6: Session Revocation & Fail-Closed Authorization Invariants
    # =========================================================================

    def test_journey_6_security_stamp_and_session_version_invalidation(self) -> None:
        """Human Tester Journey 6: Proves that password rotation instantly kills existing sessions."""
        page = MockFletPage()
        router = AppRouter(page)

        # Admin logs in
        user_dto = self._get_user(self.admin_id)
        AuthService.login(page, user_dto)
        self.assertTrue(AuthService.is_authenticated(page))

        # Admin rotates password in background (or Administrator resets it)
        AuthService.rotate_security_stamp(self.admin_id)

        # Now is_authenticated must return False due to version/stamp mismatch!
        self.assertFalse(AuthService.is_authenticated(page))

        # Accessing protected route kicks user back to /login
        router.handle_route_change(MockRouteChangeEvent(route="/dashboard"))
        self.assertEqual(page.route, "/login")


if __name__ == "__main__":
    unittest.main()
