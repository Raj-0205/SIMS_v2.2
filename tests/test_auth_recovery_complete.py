# tests/test_auth_recovery_complete.py

from __future__ import annotations
import os
import sys
import unittest
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

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
from modules.users.repository import UserRepository


class MockSessionStore:
    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def get(self, key: str) -> Any:
        return self._data.get(key)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def contains_key(self, key: str) -> bool:
        return key in self._data

    def clear(self) -> None:
        self._data.clear()


class MockFletSession:
    def __init__(self) -> None:
        self.store = MockSessionStore()

    def get(self, key: str) -> Any:
        return self.store.get(key)

    def set(self, key: str, value: Any) -> None:
        self.store.set(key, value)

    def clear(self) -> None:
        self.store.clear()


class MockFletPage:
    def __init__(self) -> None:
        self.session = MockFletSession()
        self.route = "/login"

    def navigate(self, route: str) -> None:
        self.route = route


class TestAuthRecoveryComplete(unittest.TestCase):
    """
    Comprehensive Hostile Validation Suite for SIMS v2.2
    Authentication, Authorization, Emergency Break-Glass & Recovery Architecture.
    """

    admin_username = "test_rec_admin"
    admin_password = "AdminPassword123!"
    admin_id: int = 0

    administrator_username = "test_rec_administrator"
    administrator_password = "AdministratorSecret456!"
    administrator_email = "recovery_admin@sudharmsims.local"
    administrator_id: int = 0

    dispatched_emails: list[dict[str, Any]] = []

    @classmethod
    def setUpClass(cls) -> None:
        ConfigService.initialize()
        DatabaseEngine.initialize()
        MigrationEngine.initialize()
        MigrationEngine.upgrade()

        # Capture emails in memory sink
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
        admin_hash = AuthService.hash_password(cls.admin_password)
        administrator_hash = AuthService.hash_password(cls.administrator_password)

        with DatabaseEngine.connection() as conn:
            conn.execute(
                "DELETE FROM users WHERE username IN (?, ?);",
                (cls.admin_username, cls.administrator_username),
            )
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO users (username, password_hash, role, email, security_version, security_stamp)
                VALUES (?, ?, ?, ?, 1, 'stamp_admin_001');
                """,
                (cls.admin_username, admin_hash, Role.ADMIN.value, None),
            )
            cls.admin_id = cursor.lastrowid or 0

            cursor.execute(
                """
                INSERT INTO users (username, password_hash, role, email, security_version, security_stamp)
                VALUES (?, ?, ?, ?, 1, 'stamp_administrator_001');
                """,
                (cls.administrator_username, administrator_hash, Role.ADMINISTRATOR.value, cls.administrator_email),
            )
            cls.administrator_id = cursor.lastrowid or 0

    @classmethod
    def tearDownClass(cls) -> None:
        SmtpTransport.clear_test_sink()
        SecurityContext.clear()
        with DatabaseEngine.connection() as conn:
            conn.execute(
                "DELETE FROM auth_recovery_keys WHERE user_id IN (?, ?);",
                (cls.admin_id, cls.administrator_id),
            )
            conn.execute(
                "DELETE FROM auth_password_reset_tokens WHERE user_id IN (?, ?);",
                (cls.admin_id, cls.administrator_id),
            )
            conn.execute(
                "DELETE FROM auth_email_change_requests WHERE user_id IN (?, ?);",
                (cls.admin_id, cls.administrator_id),
            )
            conn.execute(
                "DELETE FROM auth_otp_challenges WHERE user_id IN (?, ?);",
                (cls.admin_id, cls.administrator_id),
            )
            conn.execute(
                "DELETE FROM users WHERE username IN (?, ?);",
                (cls.admin_username, cls.administrator_username),
            )
            conn.execute(
                "DELETE FROM activity_logs WHERE actor_name IN (?, ?);",
                (cls.admin_username, cls.administrator_username),
            )

    def setUp(self) -> None:
        self.page = MockFletPage()
        TestAuthRecoveryComplete.dispatched_emails.clear()
        SecurityContext.clear()
        BreakGlassService.reset_global_rate_limit()
        with DatabaseEngine.connection() as conn:
            conn.execute(
                """
                UPDATE users
                SET failed_login_attempts = 0, locked_until = NULL,
                    failed_break_glass_attempts = 0, break_glass_locked_until = NULL
                WHERE id IN (?, ?);
                """,
                (self.admin_id, self.administrator_id),
            )

    # -------------------------------------------------------------------------
    # 1. Recovery Key Representation, Entropy & Formatting
    # -------------------------------------------------------------------------

    def test_01_recovery_key_format_and_entropy(self) -> None:
        formatted_key, raw_key, key_identifier = RecoveryKeyService.generate_recovery_key()

        # Check raw key is exactly 52 Base32 characters
        self.assertEqual(len(raw_key), 52)
        # Check formatted key has prefix SIMS-
        self.assertTrue(formatted_key.startswith("SIMS-"))
        # Check formatting: SIMS- + 13 groups of 4 = 5 + 52 + 12 hyphens = 69 characters
        parts = formatted_key.split("-")
        self.assertEqual(parts[0], "SIMS")
        self.assertEqual(len(parts), 14)  # "SIMS" + 13 blocks of 4 chars
        for block in parts[1:]:
            self.assertEqual(len(block), 4)

        # Validation
        self.assertTrue(RecoveryKeyService.validate_format(formatted_key))
        self.assertTrue(RecoveryKeyService.validate_format(raw_key))

        # Rejection of bad formatting
        self.assertFalse(RecoveryKeyService.validate_format("SIMS-SHORT"))
        self.assertFalse(RecoveryKeyService.validate_format("BAD-PREFIX-" + "A" * 52))
        self.assertFalse(RecoveryKeyService.validate_format("SIMS-" + "0" * 52))  # 0 is invalid Crockford Base32

    def test_02_recovery_key_hashing_and_dummy_timing(self) -> None:
        formatted_key, raw_key, _ = RecoveryKeyService.generate_recovery_key()
        h = RecoveryKeyService.hash_recovery_key(raw_key)
        self.assertTrue(h.startswith("$argon2id$"))

        self.assertTrue(RecoveryKeyService.verify_recovery_key(raw_key, h))
        self.assertFalse(RecoveryKeyService.verify_recovery_key("SIMS-" + "B" * 52, h))

        # Dummy timing verification does not crash
        res = RecoveryKeyService.verify_dummy_key(raw_key)
        self.assertFalse(res)

    # -------------------------------------------------------------------------
    # 2. Administrator-Controlled Admin Password Reset Ceremony
    # -------------------------------------------------------------------------

    def test_03_admin_reset_requires_administrator_role(self) -> None:
        # 1. Anonymous actor
        with self.assertRaises(ForbiddenError):
            AuthService.initiate_admin_password_reset("anyPass")

        # 2. Admin actor (cannot reset own password via administrator ceremony)
        SecurityContext.set_current_user(
            user_id=self.admin_id,
            username=self.admin_username,
            role=Role.ADMIN.value,
        )
        with self.assertRaises(ForbiddenError):
            AuthService.initiate_admin_password_reset("anyPass")

    def test_04_admin_reset_wrong_reauthentication_password(self) -> None:
        SecurityContext.set_current_user(
            user_id=self.administrator_id,
            username=self.administrator_username,
            role=Role.ADMINISTRATOR.value,
        )
        with self.assertRaises(AuthenticationError) as ctx:
            AuthService.initiate_admin_password_reset("WrongPassword!")
        self.assertIn("re-authentication failed", str(ctx.exception))

    def test_05_admin_reset_otp_generation_and_verification(self) -> None:
        SecurityContext.set_current_user(
            user_id=self.administrator_id,
            username=self.administrator_username,
            role=Role.ADMINISTRATOR.value,
        )

        res = AuthService.initiate_admin_password_reset(self.administrator_password)
        self.assertIn("challenge_token", res)
        challenge_token = res["challenge_token"]

        # Check outbound email
        self.assertEqual(len(self.dispatched_emails), 1)
        self.assertEqual(self.dispatched_emails[0]["to"], self.administrator_email)
        self.assertIn("Admin Password Reset", self.dispatched_emails[0]["subject"])

        # Fetch valid OTP from outbound email
        email_msg = self.dispatched_emails[-1]
        otp_code = [w for w in email_msg["body_text"].split() if w.isdigit() and len(w) == 6][0]

        # Verify challenge purpose in database
        with DatabaseEngine.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT purpose FROM auth_otp_challenges WHERE challenge_token = ?;",
                (challenge_token,),
            )
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], OTPPurpose.ADMIN_PASSWORD_RESET.value)

        # Invalid OTP fails
        with self.assertRaises(AuthenticationError):
            AuthService.complete_admin_password_reset(challenge_token, "000000", "newAdminPass88!", target_admin_username=self.admin_username)

        # Valid OTP succeeds
        complete_res = AuthService.complete_admin_password_reset(challenge_token, otp_code, "newAdminPass88!", target_admin_username=self.admin_username)
        self.assertTrue(complete_res.get("success"))

        # Re-using the same OTP challenge fails (single-use)
        with self.assertRaises(AuthenticationError):
            AuthService.complete_admin_password_reset(challenge_token, otp_code, "newAdminPass88!", target_admin_username=self.admin_username)

    def test_06_admin_reset_success_and_session_invalidation(self) -> None:
        # Record initial admin security_version and stamp
        with DatabaseEngine.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT security_version, security_stamp FROM users WHERE id = ?;", (self.admin_id,))
            init_version, init_stamp = cursor.fetchone()

        SecurityContext.set_current_user(
            user_id=self.administrator_id,
            username=self.administrator_username,
            role=Role.ADMINISTRATOR.value,
        )

        init_res = AuthService.initiate_admin_password_reset(self.administrator_password)
        token = init_res["challenge_token"]

        email_msg = self.dispatched_emails[-1]
        otp_code = [w for w in email_msg["body_text"].split() if w.isdigit() and len(w) == 6][0]

        AuthService.complete_admin_password_reset(token, otp_code, "freshAdminPassword999!", target_admin_username=self.admin_username)

        # Verify admin row was updated
        with DatabaseEngine.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT security_version, security_stamp, password_hash FROM users WHERE id = ?;", (self.admin_id,))
            new_version, new_stamp, new_hash = cursor.fetchone()

        self.assertGreater(new_version, init_version)
        self.assertNotEqual(new_stamp, init_stamp)
        self.assertTrue(AuthService.verify_password(new_hash, "freshAdminPassword999!"))

    # -------------------------------------------------------------------------
    # 3. Emergency Break-Glass Lifecycle & Lease Semantics
    # -------------------------------------------------------------------------

    def test_07_break_glass_nonexistent_user_anti_enumeration(self) -> None:
        formatted_key, raw_key, _ = RecoveryKeyService.generate_recovery_key()
        with self.assertRaises(AuthenticationError) as ctx:
            BreakGlassService.claim_break_glass("unknown_super_admin", raw_key)
        self.assertIn("Invalid recovery key or user does not exist", str(ctx.exception))

    def test_08_break_glass_invalid_key_and_lockout(self) -> None:
        # Provision an initial key for the administrator
        key_id, raw_key, formatted_key = RecoveryKeyService.provision_initial_key(self.administrator_id)

        # 3 failed attempts
        for attempt in range(1, 4):
            with self.assertRaises(AuthenticationError):
                BreakGlassService.claim_break_glass(self.administrator_username, "SIMS-" + "W" * 52)

        # Check failed attempts in DB
        with DatabaseEngine.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT failed_break_glass_attempts, break_glass_locked_until FROM users WHERE id = ?;",
                (self.administrator_id,),
            )
            failed_count, locked_until = cursor.fetchone()
            self.assertEqual(failed_count, 3)
            self.assertIsNotNone(locked_until)

        # 4th attempt triggers rate limit lockout
        with self.assertRaises(RateLimitExceededError):
            BreakGlassService.claim_break_glass(self.administrator_username, formatted_key)

        # Reset lockout for following tests
        with DatabaseEngine.connection() as conn:
            conn.execute(
                "UPDATE users SET failed_break_glass_attempts = 0, break_glass_locked_until = NULL WHERE id = ?;",
                (self.administrator_id,),
            )

    def test_09_break_glass_atomic_lease_claim(self) -> None:
        key_id, raw_key, formatted_key = RecoveryKeyService.provision_initial_key(self.administrator_id)

        lease = BreakGlassService.claim_break_glass(self.administrator_username, formatted_key)
        self.assertTrue(lease["lease_granted"])
        self.assertEqual(lease["user_id"], self.administrator_id)
        self.assertEqual(lease["key_id"], key_id)
        self.assertIsNotNone(lease["session_id"])
        self.assertIsNotNone(lease["session_nonce"])

        # Check DB state is PENDING_REMEDIATION with lease attributes
        with DatabaseEngine.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT status, pending_session_id, pending_started_at, pending_expires_at FROM auth_recovery_keys WHERE id = ?;",
                (key_id,),
            )
            status, pending_sid, started, expires = cursor.fetchone()
            self.assertEqual(status, "PENDING_REMEDIATION")
            self.assertEqual(pending_sid, lease["session_id"])
            self.assertIsNotNone(started)
            self.assertIsNotNone(expires)

    def test_10_break_glass_concurrent_claim_blocked(self) -> None:
        key_id, raw_key, formatted_key = RecoveryKeyService.provision_initial_key(self.administrator_id)

        # Claim 1
        lease1 = BreakGlassService.claim_break_glass(self.administrator_username, formatted_key)
        self.assertTrue(lease1["lease_granted"])

        # Claim 2 concurrently should fail closed
        with self.assertRaises(RateLimitExceededError) as ctx:
            BreakGlassService.claim_break_glass(self.administrator_username, formatted_key)
        self.assertIn("active emergency lease", str(ctx.exception))

    def test_11_break_glass_lease_cancellation(self) -> None:
        key_id, raw_key, formatted_key = RecoveryKeyService.provision_initial_key(self.administrator_id)

        lease = BreakGlassService.claim_break_glass(self.administrator_username, formatted_key)
        self.assertTrue(lease["lease_granted"])

        # Explicit cancel
        BreakGlassService.cancel_lease(key_id, lease["session_id"])

        # DB state returned to ACTIVE
        with DatabaseEngine.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT status, pending_session_id FROM auth_recovery_keys WHERE id = ?;",
                (key_id,),
            )
            status, pending_sid = cursor.fetchone()
            self.assertEqual(status, "ACTIVE")
            self.assertIsNone(pending_sid)

        # Now can be claimed again
        lease2 = BreakGlassService.claim_break_glass(self.administrator_username, formatted_key)
        self.assertTrue(lease2["lease_granted"])

    def test_12_break_glass_expired_lease_reclaim(self) -> None:
        key_id, raw_key, formatted_key = RecoveryKeyService.provision_initial_key(self.administrator_id)

        lease1 = BreakGlassService.claim_break_glass(self.administrator_username, formatted_key)

        # Force expiry in the past
        past_time = (datetime.now(timezone.utc) - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
        with DatabaseEngine.connection() as conn:
            conn.execute(
                "UPDATE auth_recovery_keys SET pending_expires_at = ? WHERE id = ?;",
                (past_time, key_id),
            )

        # Subsequent claim should safely reclaim the expired lease
        lease2 = BreakGlassService.claim_break_glass(self.administrator_username, formatted_key)
        self.assertTrue(lease2["lease_granted"])
        self.assertNotEqual(lease1["session_id"], lease2["session_id"])

    def test_13_break_glass_remediation_four_way_validation(self) -> None:
        key_id, raw_key, formatted_key = RecoveryKeyService.provision_initial_key(self.administrator_id)
        lease = BreakGlassService.claim_break_glass(self.administrator_username, formatted_key)

        sid = lease["session_id"]
        nonce = lease["session_nonce"]
        uid = lease["user_id"]

        # 1. Invalid key_id
        with self.assertRaises(AuthenticationError):
            BreakGlassService.remediate(99999, sid, nonce, uid, "NewAdminPass1234!")

        # 2. Invalid session_id
        with self.assertRaises(AuthenticationError):
            BreakGlassService.remediate(key_id, "wrong_sid", nonce, uid, "NewAdminPass1234!")

        # 3. Invalid session_nonce
        with self.assertRaises(AuthenticationError):
            BreakGlassService.remediate(key_id, sid, "wrong_nonce", uid, "NewAdminPass1234!")

        # 4. Expired lease
        past_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        with DatabaseEngine.connection() as conn:
            conn.execute(
                "UPDATE auth_recovery_keys SET pending_expires_at = ? WHERE id = ?;",
                (past_time, key_id),
            )

        with self.assertRaises(AuthenticationError) as ctx:
            BreakGlassService.remediate(key_id, sid, nonce, uid, "NewAdminPass1234!")
        self.assertIn("lease has expired", str(ctx.exception))

    def test_14_break_glass_remediation_success_and_rotation(self) -> None:
        key_id, raw_key, formatted_key = RecoveryKeyService.provision_initial_key(self.administrator_id)
        lease = BreakGlassService.claim_break_glass(self.administrator_username, formatted_key)

        # Perform valid remediation
        rem_res = BreakGlassService.remediate(
            key_id=key_id,
            session_id=lease["session_id"],
            session_nonce=lease["session_nonce"],
            user_id=self.administrator_id,
            new_password="NewDisasterRecoveredPass999!",
            new_email="emergency_new@sudharmsims.local",
        )

        self.assertTrue(rem_res["remediation_completed"])
        self.assertIn("replacement_recovery_key", rem_res)
        self.assertTrue(rem_res["replacement_recovery_key"].startswith("SIMS-"))

        # Verify old key is CONSUMED
        with DatabaseEngine.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status, consumed_at FROM auth_recovery_keys WHERE id = ?;", (key_id,))
            old_status, consumed_at = cursor.fetchone()
            self.assertEqual(old_status, "CONSUMED")
            self.assertIsNotNone(consumed_at)

            # Verify replacement key is ACTIVE
            cursor.execute(
                "SELECT id, status, key_identifier FROM auth_recovery_keys WHERE user_id = ? AND status = 'ACTIVE';",
                (self.administrator_id,),
            )
            new_row = cursor.fetchone()
            self.assertIsNotNone(new_row)
            self.assertEqual(new_row[2], rem_res["replacement_key_identifier"])

            # Verify email was updated
            cursor.execute("SELECT email FROM users WHERE id = ?;", (self.administrator_id,))
            self.assertEqual(cursor.fetchone()[0], "emergency_new@sudharmsims.local")

        # Verify old password no longer works, new password works
        with DatabaseEngine.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT password_hash FROM users WHERE id = ?;", (self.administrator_id,))
            pwd_hash = cursor.fetchone()[0]
        self.assertTrue(AuthService.verify_password(pwd_hash, "NewDisasterRecoveredPass999!"))
        self.assertFalse(AuthService.verify_password(pwd_hash, self.administrator_password))

    # -------------------------------------------------------------------------
    # 4. Dual-Verification Email Change Flow
    # -------------------------------------------------------------------------

    def test_15_email_change_invalid_format_and_collision(self) -> None:
        SecurityContext.set_current_user(
            user_id=self.administrator_id,
            username=self.administrator_username,
            role=Role.ADMINISTRATOR.value,
        )

        # 1. Invalid email
        with self.assertRaises(ValidationError):
            EmailChangeService.request_email_change(self.administrator_id, "not-an-email")

        # 2. Collision with self
        with self.assertRaises(ValidationError):
            EmailChangeService.request_email_change(self.administrator_id, "EMERGENCY_NEW@SUDHARMSIMS.LOCAL")

    def test_16_email_change_dual_otp_verification_and_finalize(self) -> None:
        # Reset administrator email to a known baseline
        with DatabaseEngine.connection() as conn:
            conn.execute(
                "UPDATE users SET email = 'initial_admin@sudharmsims.local' WHERE id = ?;",
                (self.administrator_id,),
            )

        SecurityContext.set_current_user(
            user_id=self.administrator_id,
            username=self.administrator_username,
            role=Role.ADMINISTRATOR.value,
        )

        new_email = "verified_change@sudharmsims.local"
        req = EmailChangeService.request_email_change(self.administrator_id, new_email)
        req_token = req["request_token"]

        # Emails sent to both current and new
        self.assertGreaterEqual(len(self.dispatched_emails), 2)
        recipients = [m["to"] for m in self.dispatched_emails]
        self.assertIn("initial_admin@sudharmsims.local", recipients)
        self.assertIn("verified_change@sudharmsims.local", recipients)

        # Retrieve OTP codes from dispatched emails
        curr_email_msg = next(m for m in self.dispatched_emails if m["to"] == "initial_admin@sudharmsims.local")
        new_email_msg = next(m for m in self.dispatched_emails if m["to"] == "verified_change@sudharmsims.local")
        curr_otp = [w for w in curr_email_msg["body_text"].split() if w.isdigit() and len(w) == 6][0]
        new_otp = [w for w in new_email_msg["body_text"].split() if w.isdigit() and len(w) == 6][0]

        # Verify current OTP
        curr_res = EmailChangeService.verify_email_otp(req_token, "current", curr_otp)
        self.assertTrue(curr_res["current_verified"])
        self.assertFalse(curr_res["both_verified"])

        # Finalizing before new OTP verified fails
        with self.assertRaises(ValidationError):
            EmailChangeService.finalize_email_change(req_token)

        # Verify new OTP
        new_res = EmailChangeService.verify_email_otp(req_token, "new", new_otp)
        self.assertTrue(new_res["new_verified"])
        self.assertTrue(new_res["both_verified"])

        # Finalize succeeds
        fin_res = EmailChangeService.finalize_email_change(req_token)
        self.assertTrue(fin_res["finalized"])
        self.assertEqual(fin_res["new_email"], new_email)

        # Verify user record updated and session invalidated
        with DatabaseEngine.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT email FROM users WHERE id = ?;", (self.administrator_id,))
            self.assertEqual(cursor.fetchone()[0], new_email)

    def test_17_email_change_cancellation(self) -> None:
        SecurityContext.set_current_user(
            user_id=self.administrator_id,
            username=self.administrator_username,
            role=Role.ADMINISTRATOR.value,
        )
        req = EmailChangeService.request_email_change(self.administrator_id, "cancel_test@sudharmsims.local")
        token = req["request_token"]

        EmailChangeService.cancel_email_change(token)

        with DatabaseEngine.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM auth_email_change_requests WHERE request_token = ?;", (token,))
            self.assertEqual(cursor.fetchone()[0], "CANCELLED")

        # Verifying against cancelled request fails
        with self.assertRaises(ValidationError):
            EmailChangeService.verify_email_otp(token, "current", "123456")

    # -------------------------------------------------------------------------
    # 5. Self-Service Password Recovery for Administrators
    # -------------------------------------------------------------------------

    def test_18_password_recovery_anti_enumeration(self) -> None:
        # Nonexistent user
        res = PasswordRecoveryService.request_recovery("non_existent_user_9999")
        self.assertIn("message", res)
        # Does not return challenge_token to client
        self.assertIsNone(res.get("challenge_token"))

        # Admin user (not Administrator) should also receive anti-enumeration message
        res_admin = PasswordRecoveryService.request_recovery(self.admin_username)
        self.assertIsNone(res_admin.get("challenge_token"))

    def test_19_password_recovery_otp_and_reset_token(self) -> None:
        # Set administrator email
        with DatabaseEngine.connection() as conn:
            conn.execute(
                "UPDATE users SET email = 'self_service@sudharmsims.local' WHERE id = ?;",
                (self.administrator_id,),
            )

        res = PasswordRecoveryService.request_recovery(self.administrator_username)
        self.assertIsNotNone(res.get("challenge_token"))
        token = res["challenge_token"]

        # Extract OTP from dispatched email
        recovery_email_msg = self.dispatched_emails[-1]
        otp_code = [w for w in recovery_email_msg["body_text"].split() if w.isdigit() and len(w) == 6][0]

        # Verify OTP generates single-use reset_token
        reset_token = PasswordRecoveryService.verify_recovery_otp(token, otp_code)
        self.assertIsNotNone(reset_token)

        # Complete reset
        fin = PasswordRecoveryService.complete_password_reset(reset_token, "BrandNewSelfServicePass888!")
        self.assertTrue(fin["success"])

        # Re-using reset token fails
        with self.assertRaises(AuthenticationError):
            PasswordRecoveryService.complete_password_reset(reset_token, "BrandNewSelfServicePass888!")

    # -------------------------------------------------------------------------
    # 6. Session Authority & Instant Invalidation
    # -------------------------------------------------------------------------

    def test_20_session_invalidation_security_version(self) -> None:
        # Update user's password so login succeeds
        fresh_hash = AuthService.hash_password("LoginTestPass123!")
        with DatabaseEngine.connection() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ?, security_version = 1, security_stamp = 'valid_stamp' WHERE id = ?;",
                (fresh_hash, self.admin_id),
            )

        # Login to populate Flet session
        user_dto = AuthService.login(self.page, self.admin_username, "LoginTestPass123!")
        self.assertIsNotNone(user_dto)
        self.assertTrue(AuthService.is_authenticated(self.page))

        # Bump security_version in database
        with DatabaseEngine.connection() as conn:
            conn.execute("UPDATE users SET security_version = security_version + 1 WHERE id = ?;", (self.admin_id,))

        # Immediate invalidation check
        self.assertFalse(AuthService.is_authenticated(self.page))

    def test_21_session_invalidation_security_stamp(self) -> None:
        fresh_hash = AuthService.hash_password("LoginTestPass456!")
        with DatabaseEngine.connection() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ?, security_version = 1, security_stamp = 'orig_stamp' WHERE id = ?;",
                (fresh_hash, self.admin_id),
            )

        user_dto = AuthService.login(self.page, self.admin_username, "LoginTestPass456!")
        self.assertIsNotNone(user_dto)
        self.assertTrue(AuthService.is_authenticated(self.page))

        # Rotate security_stamp in database
        with DatabaseEngine.connection() as conn:
            conn.execute("UPDATE users SET security_stamp = 'rotated_stamp_xyz' WHERE id = ?;", (self.admin_id,))

        # Immediate invalidation check
        self.assertFalse(AuthService.is_authenticated(self.page))

    # -------------------------------------------------------------------------
    # 7. Credential Management & Governance
    # -------------------------------------------------------------------------

    def test_22_password_change_self_service(self) -> None:
        current_pwd = "ChangeSelfPass123!"
        new_pwd = "ChangedNewPass789!"
        with DatabaseEngine.connection() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?;",
                (AuthService.hash_password(current_pwd), self.admin_id),
            )

        # Wrong current password fails
        with self.assertRaises(AuthenticationError):
            AuthService.change_password(self.admin_id, "WrongCurrent!", new_pwd)

        # Too short new password fails
        with self.assertRaises(ValidationError):
            AuthService.change_password(self.admin_id, current_pwd, "short")

        # Success updates password and increments version
        res = AuthService.change_password(self.admin_id, current_pwd, new_pwd)
        self.assertTrue(res["success"])

        with DatabaseEngine.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT password_hash FROM users WHERE id = ?;", (self.admin_id,))
            pwd_hash = cursor.fetchone()[0]
        self.assertTrue(AuthService.verify_password(pwd_hash, new_pwd))

    def test_23_recovery_key_rotation_by_administrator(self) -> None:
        # Administrator rotates their recovery key
        rot = RecoveryKeyService.rotate_recovery_key(self.administrator_id, "ADMIN_DASHBOARD_ROTATION")
        self.assertIn("raw_recovery_key", rot)
        self.assertIn("formatted_recovery_key", rot)
        self.assertTrue(rot["formatted_recovery_key"].startswith("SIMS-"))

        # Verify only 1 active key exists
        with DatabaseEngine.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM auth_recovery_keys WHERE user_id = ? AND status = 'ACTIVE';",
                (self.administrator_id,),
            )
            self.assertEqual(cursor.fetchone()[0], 1)

    def test_24_delivery_telemetry_recording(self) -> None:
        key_id, raw_key, formatted_key = RecoveryKeyService.provision_initial_key(self.administrator_id)

        RecoveryKeyService.record_delivery_status(key_id, "UI_SHOWN")
        with DatabaseEngine.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT delivery_status, delivered_at FROM auth_recovery_keys WHERE id = ?;", (key_id,))
            status, delivered_at = cursor.fetchone()
            self.assertEqual(status, "UI_SHOWN")
            self.assertIsNotNone(delivered_at)

    def test_25_normalized_email_unique_index(self) -> None:
        with DatabaseEngine.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT email FROM users WHERE id = ?;", (self.administrator_id,))
            current_email = cursor.fetchone()[0]
            # Inserting email that differs only in casing should trigger UNIQUE constraint
            with self.assertRaises(Exception):
                cursor.execute(
                    """
                    INSERT INTO users (username, password_hash, role, email)
                    VALUES ('collision_user', 'hash', 'ADMIN', ?);
                    """,
                    (current_email.upper(),),
                )

    def test_26_break_glass_rate_limit_reset_on_remediation(self) -> None:
        key_id, raw_key, formatted_key = RecoveryKeyService.provision_initial_key(self.administrator_id)

        # Register 1 failed attempt
        with self.assertRaises(AuthenticationError):
            BreakGlassService.claim_break_glass(self.administrator_username, "SIMS-" + "W" * 52)

        # Successful claim & remediate
        lease = BreakGlassService.claim_break_glass(self.administrator_username, formatted_key)
        BreakGlassService.remediate(
            key_id=key_id,
            session_id=lease["session_id"],
            session_nonce=lease["session_nonce"],
            user_id=self.administrator_id,
            new_password="PostLockoutPass1234!",
        )

        with DatabaseEngine.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT failed_break_glass_attempts FROM users WHERE id = ?;", (self.administrator_id,))
            self.assertEqual(cursor.fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
