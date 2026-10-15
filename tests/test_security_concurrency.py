# tests/test_security_concurrency.py
"""
Concurrency and Authorization Test Suite for SIMS v2.2.
Validates DEF-004 (Concurrency-safe SecurityContext with zero process-global fallbacks)
and DEF-013 (SettingsService service-layer authorization).
"""

import os
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

os.environ["SIMS_ENV"] = "testing"

from core.configuration.service import ConfigService
from core.database.engine import DatabaseEngine
from core.database.migration import MigrationEngine
from core.security.context import SecurityContext, UserIdentity
from core.security.roles import Role
from core.security.permissions import Permission
from core.security.authorization import AuthorizationService
from core.exceptions import ForbiddenError
from modules.settings.service import SettingsService


class TestSecurityConcurrencyAndAuthorization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ConfigService.initialize(force_reload=True)
        if not DatabaseEngine.is_initialized():
            DatabaseEngine.initialize()
        MigrationEngine._is_initialized = False
        MigrationEngine.initialize()
        MigrationEngine.upgrade()
        cls.settings_service = SettingsService()

    def setUp(self):
        SecurityContext.clear()

    def tearDown(self):
        SecurityContext.clear()

    def test_01_user_identity_immutability_and_access(self):
        """UserIdentity provides both property and mapping access without mutation."""
        ident = UserIdentity(
            user_id=1,
            username="admin",
            role="ADMIN",
            security_version=2,
            security_stamp="stamp-123",
        )
        self.assertEqual(ident.id, 1)
        self.assertEqual(ident.user_id, 1)
        self.assertEqual(ident.username, "admin")
        self.assertEqual(ident.role, "ADMIN")
        self.assertEqual(ident["role"], "ADMIN")
        self.assertEqual(ident.get("role"), "ADMIN")
        self.assertEqual(ident.security_version, 2)
        self.assertEqual(ident.security_stamp, "stamp-123")

    def test_02_concurrency_isolation_between_threads(self):
        """
        Prove Request A (ADMIN) and Request B (ADMINISTRATOR) running concurrently
        in separate threads never leak identity to each other.
        """
        results = {}

        def thread_a_worker():
            # User A is ADMIN
            SecurityContext.set_current_user(user_id=1, username="admin_user", role=Role.ADMIN.value)
            time.sleep(0.05)  # Allow thread B to run and set its identity
            # Thread A must still see ADMIN
            results["thread_a_role"] = SecurityContext.get_current_role()
            results["thread_a_uid"] = SecurityContext.get_current_user_id()
            results["thread_a_uname"] = SecurityContext.get_current_username()

        def thread_b_worker():
            # User B is ADMINISTRATOR
            SecurityContext.set_current_user(user_id=14, username="super_admin", role=Role.ADMINISTRATOR.value)
            time.sleep(0.05)
            # Thread B must still see ADMINISTRATOR
            results["thread_b_role"] = SecurityContext.get_current_role()
            results["thread_b_uid"] = SecurityContext.get_current_user_id()
            results["thread_b_uname"] = SecurityContext.get_current_username()

        with ThreadPoolExecutor(max_workers=2) as executor:
            fut_a = executor.submit(thread_a_worker)
            fut_b = executor.submit(thread_b_worker)
            fut_a.result()
            fut_b.result()

        # Thread A was completely isolated
        self.assertEqual(results["thread_a_role"], Role.ADMIN.value)
        self.assertEqual(results["thread_a_uid"], 1)
        self.assertEqual(results["thread_a_uname"], "admin_user")

        # Thread B was completely isolated
        self.assertEqual(results["thread_b_role"], Role.ADMINISTRATOR.value)
        self.assertEqual(results["thread_b_uid"], 14)
        self.assertEqual(results["thread_b_uname"], "super_admin")

        # Main thread has zero ambient identity (no process-global leakage)
        self.assertIsNone(SecurityContext.get_current_role())
        self.assertIsNone(SecurityContext.get_current_user_id())

    def test_03_worker_thread_propagation_via_wrap_worker(self):
        """Prove that wrap_worker explicitly propagates caller identity to worker threads."""
        SecurityContext.set_current_user(user_id=14, username="admin_lead", role=Role.ADMINISTRATOR.value)

        def background_task(x: int, y: int) -> dict:
            # Inside worker thread: verify identity survived
            return {
                "sum": x + y,
                "role": SecurityContext.get_current_role(),
                "uid": SecurityContext.get_current_user_id(),
                "uname": SecurityContext.get_current_username(),
            }

        wrapped_task = SecurityContext.wrap_worker(background_task)

        # Clear context on main thread before running worker
        SecurityContext.clear()
        self.assertIsNone(SecurityContext.get_current_role())

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(wrapped_task, 10, 20)
            res = future.result()

        self.assertEqual(res["sum"], 30)
        self.assertEqual(res["role"], Role.ADMINISTRATOR.value)
        self.assertEqual(res["uid"], 14)
        self.assertEqual(res["uname"], "admin_lead")

    def test_04_unauthenticated_fails_closed(self):
        """Unauthenticated executions without identity must fail closed on privileged operations."""
        SecurityContext.clear()
        self.assertIsNone(SecurityContext.get_current_role())

        # Attempting privileged enforcement must raise ForbiddenError
        with self.assertRaises(ForbiddenError):
            AuthorizationService.enforce(Permission.STUDENT_DELETE)

        with self.assertRaises(ForbiddenError):
            AuthorizationService.enforce(Permission.SETTINGS_MANAGE)

    def test_05_settings_authorization_def_013(self):
        """
        Verify DEF-013:
        ADMIN role attempting save_institute_profile() is DENIED with ForbiddenError.
        ADMINISTRATOR role is ALLOWED.
        """
        test_profile = {
            "institute_name": "Sudharm Verified Academy",
            "contact_person": "Hemant Mahale",
            "contact_mobile": "9271226772",
        }

        # 1. As ADMIN -> Must be rejected at service layer
        with SecurityContext.as_user(user_id=1, username="admin", role=Role.ADMIN.value):
            with self.assertRaises(ForbiddenError) as ctx:
                self.settings_service.save_institute_profile(test_profile)
            self.assertIn("requires elevated Administrator privileges", str(ctx.exception))

        # 2. As ADMINISTRATOR -> Must succeed
        with SecurityContext.as_user(user_id=14, username="administrator", role=Role.ADMINISTRATOR.value):
            self.settings_service.save_institute_profile(test_profile)
            updated = self.settings_service.get_institute_profile()
            self.assertEqual(updated["institute_name"], "Sudharm Verified Academy")

        # 3. Context manager cleaned up identity
        self.assertIsNone(SecurityContext.get_current_role())


if __name__ == "__main__":
    unittest.main()
