# tests/test_auth_dual_tier.py

from __future__ import annotations
import os
import sys
import unittest
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.configuration.service import ConfigService
from core.database.engine import DatabaseEngine
from core.database.migration import MigrationEngine
from core.database.transaction import TransactionManager
from core.exceptions import AuthenticationError, ForbiddenError, ValidationError
from core.security.audit import SecurityAuditRepository
from core.security.auth import AuthService
from core.security.authorization import AuthorizationService, ROLE_PERMISSIONS
from core.security.context import SecurityContext
from core.security.otp import OTPService
from core.security.permissions import Permission
from core.security.roles import Role
from infrastructure.notification.smtp_transport import SmtpTransport
from modules.batch.dto import BatchCreateDTO, BatchUpdateDTO
from modules.batch.service import BatchService
from modules.course.dto import CourseCreateDTO, CourseUpdateDTO
from modules.course.service import CourseService
from modules.settings.service import SettingsService
from modules.student.dto import StudentCreateDTO
from modules.student.service import StudentService
from modules.users.repository import UserRepository


class MockSessionStore:
    """Accurately mirrors flet.messaging.session.SessionStore."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def get(self, key: str) -> Any:
        # Flet SessionStore.get only takes 1 argument (key: str)
        return self._data.get(key)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def contains_key(self, key: str) -> bool:
        return key in self._data

    def clear(self) -> None:
        self._data.clear()


class MockFletSession:
    """Mock transient session for testing AuthService Flet interactions."""

    def __init__(self) -> None:
        self.store = MockSessionStore()

    def get(self, key: str) -> Any:
        return self.store.get(key)

    def set(self, key: str, value: Any) -> None:
        self.store.set(key, value)

    def clear(self) -> None:
        self.store.clear()


class MockFletPage:
    """Mock Flet Page for testing UI session flows."""

    def __init__(self) -> None:
        self.session = MockFletSession()
        self.route = "/login"

    def navigate(self, route: str) -> None:
        self.route = route


class TestDualTierAuthentication(unittest.TestCase):
    """
    Exhaustive Hostile Validation Suite for SIMS v2.2 Dual-Tier Authentication Architecture.
    """

    test_admin_username = "test_sec_admin"
    test_admin_password = "AdminPassword123!"
    test_admin_id: int = 0

    test_administrator_username = "test_sec_administrator"
    test_administrator_password = "AdministratorSecret456!"
    test_administrator_email = "admin_sec_test@sudharmsims.local"
    test_administrator_id: int = 0

    dispatched_emails: list[dict[str, Any]] = []

    @classmethod
    def setUpClass(cls) -> None:
        ConfigService.initialize()
        DatabaseEngine.initialize()
        MigrationEngine.initialize()
        MigrationEngine.upgrade()

        # Intercept outbound emails into memory sink
        cls.dispatched_emails = []

        def test_sink(to_email: str, subject: str, body_text: str, body_html: Optional[str]) -> None:
            cls.dispatched_emails.append(
                {
                    "to": to_email,
                    "subject": subject,
                    "body_text": body_text,
                    "body_html": body_html,
                }
            )

        SmtpTransport.set_test_sink(test_sink)

        # Create isolated test accounts
        admin_hash = AuthService.hash_password(cls.test_admin_password)
        administrator_hash = AuthService.hash_password(cls.test_administrator_password)

        with DatabaseEngine.connection() as conn:
            conn.execute(
                "DELETE FROM users WHERE username IN (?, ?);",
                (cls.test_admin_username, cls.test_administrator_username),
            )
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, email) VALUES (?, ?, ?, ?);",
                (cls.test_admin_username, admin_hash, Role.ADMIN.value, None),
            )
            cls.test_admin_id = cursor.lastrowid or 0

            cursor.execute(
                "INSERT INTO users (username, password_hash, role, email) VALUES (?, ?, ?, ?);",
                (cls.test_administrator_username, administrator_hash, Role.ADMINISTRATOR.value, cls.test_administrator_email),
            )
            cls.test_administrator_id = cursor.lastrowid or 0

    @classmethod
    def tearDownClass(cls) -> None:
        SmtpTransport.clear_test_sink()
        SecurityContext.clear()
        # Clean up test user rows and their challenges
        with DatabaseEngine.connection() as conn:
            conn.execute(
                "DELETE FROM auth_otp_challenges WHERE user_id IN (?, ?);",
                (cls.test_admin_id, cls.test_administrator_id),
            )
            conn.execute(
                "DELETE FROM users WHERE username IN (?, ?);",
                (cls.test_admin_username, cls.test_administrator_username),
            )
            conn.execute(
                "DELETE FROM activity_logs WHERE actor_name IN (?, ?);",
                (cls.test_admin_username, cls.test_administrator_username),
            )

    def setUp(self) -> None:
        self.page = MockFletPage()
        TestDualTierAuthentication.dispatched_emails.clear()
        SecurityContext.clear()
        with DatabaseEngine.connection() as conn:
            conn.execute(
                "UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE id IN (?, ?);",
                (self.test_admin_id, self.test_administrator_id),
            )

    # =========================================================================
    # 1. ADMIN AUTHENTICATION TESTS
    # =========================================================================

    def test_01_admin_login_success_no_otp(self) -> None:
        """Admin logs in directly with username and password, requiring zero OTP."""
        res = AuthService.authenticate(
            username=self.test_admin_username,
            password=self.test_admin_password,
            intended_role="ADMIN",
        )

        self.assertFalse(res["requires_otp"])
        self.assertEqual(res["redirect_route"], "/dashboard")
        self.assertEqual(res["user"]["username"], self.test_admin_username)
        self.assertEqual(res["user"]["role"], Role.ADMIN.value)
        # Zero OTP emails dispatched
        self.assertEqual(len(self.dispatched_emails), 0)

        # Login session verification
        AuthService.login(self.page, res["user"])
        self.assertTrue(AuthService.is_authenticated(self.page))
        self.assertEqual(self.page.session.store.get("role"), Role.ADMIN.value)
        self.assertEqual(SecurityContext.get_current_role(), Role.ADMIN.value)

    def test_02_admin_session_timeout_after_60_minutes(self) -> None:
        """Admin session expires after 60 minutes of inactivity."""
        res = AuthService.authenticate(
            username=self.test_admin_username,
            password=self.test_admin_password,
            intended_role="ADMIN",
        )
        AuthService.login(self.page, res["user"])

        # Simulate 30 minutes pass (within 60m threshold)
        now_ts = datetime.now(timezone.utc).timestamp()
        self.page.session.set("last_activity_timestamp", now_ts - (30 * 60))
        self.assertFalse(AuthService.check_session_timeout(self.page))
        self.assertTrue(AuthService.is_authenticated(self.page))

        # Simulate 61 minutes pass (beyond 60m threshold)
        self.page.session.set("last_activity_timestamp", now_ts - (61 * 60))
        self.assertTrue(AuthService.check_session_timeout(self.page))
        self.assertFalse(AuthService.is_authenticated(self.page))
        self.assertIsNone(SecurityContext.get_current_role())

    # =========================================================================
    # 2. ADMINISTRATOR AUTHENTICATION & EMAIL OTP TESTS
    # =========================================================================

    def test_03_administrator_step1_triggers_email_otp(self) -> None:
        """Administrator credentials trigger an Email OTP challenge and email dispatch."""
        res = AuthService.authenticate(
            username=self.test_administrator_username,
            password=self.test_administrator_password,
            intended_role="ADMINISTRATOR",
        )

        self.assertTrue(res["requires_otp"])
        self.assertIn("challenge_token", res)
        self.assertIn("masked_email", res)
        self.assertEqual(res["redirect_route"], "/control-center")

        # Verify email was dispatched via notification service
        self.assertEqual(len(self.dispatched_emails), 1)
        sent_mail = self.dispatched_emails[0]
        self.assertEqual(sent_mail["to"], self.test_administrator_email)
        self.assertIn("Administrator Verification Code", sent_mail["subject"])

        # Verify plain OTP is NOT in database
        with DatabaseEngine.connection() as conn:
            cursor = conn.execute("SELECT * FROM auth_otp_challenges WHERE challenge_token = ?;", (res["challenge_token"],))
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            challenge = dict(row)

        # Stored hash must be salted
        self.assertIn("$", challenge["otp_hash"])
        # Stored hash must NOT contain the plain 6-digit OTP directly
        extracted_otp = [word for word in sent_mail["body_text"].split() if word.isdigit() and len(word) == 6][0]
        self.assertNotIn(extracted_otp, challenge["otp_hash"])

    def test_04_administrator_step2_valid_otp_authenticates_to_control_center(self) -> None:
        """Valid OTP completes Administrator authentication and directs to /control-center."""
        res = AuthService.authenticate(
            username=self.test_administrator_username,
            password=self.test_administrator_password,
            intended_role="ADMINISTRATOR",
        )
        challenge_token = res["challenge_token"]
        plain_otp = [word for word in self.dispatched_emails[0]["body_text"].split() if word.isdigit() and len(word) == 6][0]

        verify_res = AuthService.verify_otp(challenge_token, plain_otp)
        self.assertEqual(verify_res["redirect_route"], "/control-center")
        self.assertEqual(verify_res["user"]["username"], self.test_administrator_username)

        # Login session verification
        AuthService.login(self.page, verify_res["user"])
        self.assertTrue(AuthService.is_authenticated(self.page))
        self.assertEqual(self.page.session.store.get("role"), Role.ADMINISTRATOR.value)
        self.assertEqual(SecurityContext.get_current_role(), Role.ADMINISTRATOR.value)

    def test_05_administrator_session_timeout_after_15_minutes(self) -> None:
        """Privileged Administrator session expires after 15 minutes of inactivity."""
        res = AuthService.authenticate(
            username=self.test_administrator_username,
            password=self.test_administrator_password,
            intended_role="ADMINISTRATOR",
        )
        plain_otp = [word for word in self.dispatched_emails[0]["body_text"].split() if word.isdigit() and len(word) == 6][0]
        verify_res = AuthService.verify_otp(res["challenge_token"], plain_otp)
        AuthService.login(self.page, verify_res["user"])

        # 10 minutes pass (within 15m threshold)
        now_ts = datetime.now(timezone.utc).timestamp()
        self.page.session.set("last_activity_timestamp", now_ts - (10 * 60))
        self.assertFalse(AuthService.check_session_timeout(self.page))
        self.assertTrue(AuthService.is_authenticated(self.page))

        # 16 minutes pass (exceeds 15m threshold)
        self.page.session.set("last_activity_timestamp", now_ts - (16 * 60))
        self.assertTrue(AuthService.check_session_timeout(self.page))
        self.assertFalse(AuthService.is_authenticated(self.page))
        self.assertIsNone(SecurityContext.get_current_role())

    # =========================================================================
    # 3. HOSTILE ATTACK SCENARIOS & INVARIANT VERIFICATIONS
    # =========================================================================

    def test_06_hostile_role_intent_mismatch_rejected(self) -> None:
        """
        MANDATORY CORRECTION #1:
        Selecting a role in UI that does not match users.role MUST be rejected.
        Never trust UI role selection.
        """
        # Administrator account attempting to log in with intent "ADMIN"
        with self.assertRaises(AuthenticationError) as ctx:
            AuthService.authenticate(
                username=self.test_administrator_username,
                password=self.test_administrator_password,
                intended_role="ADMIN",
            )
        self.assertIn("not authorized for the selected role", str(ctx.exception).lower())

        # Admin account attempting to log in with intent "ADMINISTRATOR"
        with self.assertRaises(AuthenticationError) as ctx:
            AuthService.authenticate(
                username=self.test_admin_username,
                password=self.test_admin_password,
                intended_role="ADMINISTRATOR",
            )
        self.assertIn("not authorized for the selected role", str(ctx.exception).lower())

    def test_07_hostile_wrong_otp_decrements_and_exhausts_attempts(self) -> None:
        """Submitting wrong OTP decrements attempt counter and locks challenge after 3 attempts."""
        res = AuthService.authenticate(
            username=self.test_administrator_username,
            password=self.test_administrator_password,
            intended_role="ADMINISTRATOR",
        )
        token = res["challenge_token"]

        # Attempt 1: Wrong code
        with self.assertRaises(AuthenticationError) as ctx:
            AuthService.verify_otp(token, "000000")
        self.assertIn("2 attempts remaining", str(ctx.exception))

        # Attempt 2: Wrong code
        with self.assertRaises(AuthenticationError) as ctx:
            AuthService.verify_otp(token, "111111")
        self.assertIn("1 attempt remaining", str(ctx.exception))

        # Attempt 3: Wrong code -> Exhausted
        with self.assertRaises(AuthenticationError) as ctx:
            AuthService.verify_otp(token, "222222")
        self.assertIn("maximum attempts", str(ctx.exception).lower())

        # Attempt 4: Even if correct code is now entered, challenge is already exhausted/consumed
        plain_otp = [word for word in self.dispatched_emails[0]["body_text"].split() if word.isdigit() and len(word) == 6][0]
        with self.assertRaises(AuthenticationError) as ctx:
            AuthService.verify_otp(token, plain_otp)
        self.assertTrue("maximum" in str(ctx.exception).lower() or "already" in str(ctx.exception).lower())

    def test_08_hostile_otp_replay_attack_blocked(self) -> None:
        """A single-use OTP cannot be replayed a second time."""
        res = AuthService.authenticate(
            username=self.test_administrator_username,
            password=self.test_administrator_password,
            intended_role="ADMINISTRATOR",
        )
        token = res["challenge_token"]
        plain_otp = [word for word in self.dispatched_emails[0]["body_text"].split() if word.isdigit() and len(word) == 6][0]

        # Use once
        verify_res = AuthService.verify_otp(token, plain_otp)
        self.assertEqual(verify_res["redirect_route"], "/control-center")

        # Replay attempt with same token and OTP
        with self.assertRaises(AuthenticationError) as ctx:
            AuthService.verify_otp(token, plain_otp)
        self.assertIn("already been used", str(ctx.exception).lower())

    def test_09_hostile_expired_otp_challenge_rejected(self) -> None:
        """Expired OTP challenges cannot be verified."""
        res = AuthService.authenticate(
            username=self.test_administrator_username,
            password=self.test_administrator_password,
            intended_role="ADMINISTRATOR",
        )
        token = res["challenge_token"]
        plain_otp = [word for word in self.dispatched_emails[0]["body_text"].split() if word.isdigit() and len(word) == 6][0]

        # Force challenge expiration into the past in the database
        past_str = (datetime.now(timezone.utc) - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
        with DatabaseEngine.connection() as conn:
            conn.execute("UPDATE auth_otp_challenges SET expires_at = ? WHERE challenge_token = ?;", (past_str, token))

        with self.assertRaises(AuthenticationError) as ctx:
            AuthService.verify_otp(token, plain_otp)
        self.assertIn("expired", str(ctx.exception).lower())

    def test_10_resend_otp_invalidates_previous_challenge(self) -> None:
        """Resending OTP creates a new challenge and invalidates the previous pending challenge."""
        res = AuthService.authenticate(
            username=self.test_administrator_username,
            password=self.test_administrator_password,
            intended_role="ADMINISTRATOR",
        )
        old_token = res["challenge_token"]
        old_otp = [word for word in self.dispatched_emails[0]["body_text"].split() if word.isdigit() and len(word) == 6][0]

        # Trigger resend
        resend_res = AuthService.resend_otp(old_token)
        new_token = resend_res["challenge_token"]
        self.assertNotEqual(old_token, new_token)
        new_otp = [word for word in self.dispatched_emails[1]["body_text"].split() if word.isdigit() and len(word) == 6][0]

        # Trying to verify old OTP on old token MUST fail (consumed/invalidated)
        with self.assertRaises(AuthenticationError):
            AuthService.verify_otp(old_token, old_otp)

        # Verifying new OTP on new token MUST succeed
        success_res = AuthService.verify_otp(new_token, new_otp)
        self.assertEqual(success_res["redirect_route"], "/control-center")

    def test_11_hostile_password_bruteforce_locks_account_after_5_attempts(self) -> None:
        """5 consecutive wrong password attempts trigger a 15-minute account lockout."""
        # 4 failed attempts
        for attempt in range(1, 5):
            with self.assertRaises(AuthenticationError) as ctx:
                AuthService.authenticate(self.test_admin_username, "WrongPassword!")
            self.assertIn("invalid username or password", str(ctx.exception).lower())

        # 5th failed attempt -> Locks account
        with self.assertRaises(AuthenticationError) as ctx:
            AuthService.authenticate(self.test_admin_username, "WrongPassword!")
        self.assertIn("locked", str(ctx.exception).lower())

        # 6th attempt with CORRECT password is still locked
        with self.assertRaises(AuthenticationError) as ctx:
            AuthService.authenticate(self.test_admin_username, self.test_admin_password)
        self.assertIn("locked", str(ctx.exception).lower())

    # =========================================================================
    # 4. LOCKED PERMISSION MATRIX (8 PRIVILEGES) ENFORCEMENT
    # =========================================================================

    def test_12_permission_matrix_admin_vs_administrator(self) -> None:
        """
        Verify the 8 locked permissions are exclusive to Administrator:
        1. PAYMENT_PIN_CHANGE
        2. STUDENT_DELETE
        3. COURSE_CREATE
        4. COURSE_MANAGE
        5. COURSE_DELETE
        6. BATCH_CREATE
        7. BATCH_MANAGE
        8. BATCH_DELETE
        """
        all_8 = {
            Permission.PAYMENT_PIN_CHANGE,
            Permission.STUDENT_DELETE,
            Permission.COURSE_CREATE,
            Permission.COURSE_MANAGE,
            Permission.COURSE_DELETE,
            Permission.BATCH_CREATE,
            Permission.BATCH_MANAGE,
            Permission.BATCH_DELETE,
        }

        # Administrator possesses all 8
        admin_privs = AuthorizationService.get_permissions_for_role(Role.ADMINISTRATOR.value)
        self.assertEqual(admin_privs, all_8)

        # Admin possesses ZERO of the 8 privileged permissions
        op_privs = AuthorizationService.get_permissions_for_role(Role.ADMIN.value)
        self.assertEqual(op_privs, set())

        # Fail closed on unknown roles
        self.assertEqual(AuthorizationService.get_permissions_for_role("ANONYMOUS"), set())
        self.assertEqual(AuthorizationService.get_permissions_for_role(None), set())

    def test_13_domain_service_enforcement_blocks_admin_allows_administrator(self) -> None:
        """
        Verify domain services strictly enforce Permission checks.
        Admin execution raises ForbiddenError; Administrator execution passes permission gate.
        """
        course_svc = CourseService()
        batch_svc = BatchService()
        student_svc = StudentService()
        settings_svc = SettingsService()

        # 1. Course Create: Admin blocked
        with SecurityContext.as_user(self.test_admin_id, self.test_admin_username, Role.ADMIN.value):
            with self.assertRaises(ForbiddenError):
                course_svc.create_course(CourseCreateDTO(code="T-BLOCKED", name="Blocked", base_fee=1000.0))

        # 2. Batch Create: Admin blocked
        with SecurityContext.as_user(self.test_admin_id, self.test_admin_username, Role.ADMIN.value):
            with self.assertRaises(ForbiddenError):
                batch_svc.create_batch(BatchCreateDTO(course_id=1, batch_name="Blocked Batch", timing="09:00", max_capacity=10))

        # 3. Student Delete: Admin blocked
        with SecurityContext.as_user(self.test_admin_id, self.test_admin_username, Role.ADMIN.value):
            with self.assertRaises(ForbiddenError):
                student_svc.delete_student(99999)

        # 4. Payment PIN Change: Admin blocked
        with SecurityContext.as_user(self.test_admin_id, self.test_admin_username, Role.ADMIN.value):
            with self.assertRaises(ForbiddenError):
                settings_svc.set_admin_pin(new_pin="9999")

        # 5. Course Create: Administrator allowed through permission gate (fails later on validation if bogus ID)
        with SecurityContext.as_user(self.test_administrator_id, self.test_administrator_username, Role.ADMINISTRATOR.value):
            # Checking permission check doesn't raise ForbiddenError
            AuthorizationService.enforce(Permission.COURSE_CREATE)
            AuthorizationService.enforce(Permission.BATCH_CREATE)
            AuthorizationService.enforce(Permission.STUDENT_DELETE)
            AuthorizationService.enforce(Permission.PAYMENT_PIN_CHANGE)

    # =========================================================================
    # 5. SECURITY AUDIT LOGGING
    # =========================================================================

    def test_14_security_audit_events_recorded_in_activity_logs(self) -> None:
        """Verify auth and security events are faithfully audited in activity_logs."""
        with DatabaseEngine.connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM activity_logs WHERE entity_type = 'SECURITY' ORDER BY created_at DESC LIMIT 20;"
            )
            recent_logs = [dict(r) for r in cursor.fetchall()]

        actions = [log["action"] for log in recent_logs]

        # Verify key security actions were captured
        self.assertTrue(any("LOGIN_SUCCESS" in a for a in actions))
        self.assertTrue(any("OTP_GENERATED" in a for a in actions))
        self.assertTrue(any("LOGIN_FAILURE" in a or "ACCOUNT_LOCKED" in a for a in actions))


if __name__ == "__main__":
    unittest.main()
