# tests/test_audit_fixes_and_invariants.py

import os
import unittest
import csv
from datetime import datetime
from openpyxl import load_workbook

from core.database.engine import DatabaseEngine
from core.database.migration import MigrationEngine
from core.configuration.service import ConfigService
from core.exceptions import ForbiddenError, ValidationError
from core.security.context import SecurityContext
from core.security.roles import Role
from core.security.recovery import RecoveryKeyService, _enforce_global_rate_limit, _GLOBAL_BREAK_GLASS_ATTEMPTS
from core.security.email_change import EmailChangeService
from core.security.audit import SecurityAuditRepository
from core.cache.fees_cache import FeesCacheManager
from infrastructure.excel.exporter import ExcelExporter
from modules.admission.service import AdmissionService
from modules.admission.dto import (
    AdmissionCreateDTO,
    AdmissionUpdateDTO,
    AdmissionStatus,
)
from modules.course.service import CourseService
from modules.course.dto import CourseCreateDTO, CourseUpdateDTO
from modules.student.service import StudentService
from modules.student.dto import StudentCreateDTO
from modules.reports.service import ReportsService


class TestAuditFixesAndInvariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ConfigService.initialize()
        DatabaseEngine.initialize()
        MigrationEngine.initialize()
        MigrationEngine.upgrade()
        cls.admission_service = AdmissionService()
        cls.course_service = CourseService()
        cls.student_service = StudentService()
        cls.report_service = ReportsService()
        cls.audit_repo = SecurityAuditRepository()

    def setUp(self):
        SecurityContext.clear()

    def tearDown(self):
        SecurityContext.clear()

    # -------------------------------------------------------------------------
    # 1. Formula Injection Sanitization (CWE-1236)
    # -------------------------------------------------------------------------
    def test_formula_injection_sanitization(self):
        malicious = ["=SUM(A1:A10)", "@cmd|' /C calc'!A0", "+malicious", "-malicious", "Normal Text", 123.45, None]
        sanitized = [ExcelExporter.sanitize_formula_injection(x) for x in malicious]
        self.assertEqual(sanitized[0], "'=SUM(A1:A10)")
        self.assertEqual(sanitized[1], "'@cmd|' /C calc'!A0")
        self.assertEqual(sanitized[2], "'+malicious")
        self.assertEqual(sanitized[3], "'-malicious")
        self.assertEqual(sanitized[4], "Normal Text")
        self.assertEqual(sanitized[5], "123.45")
        self.assertEqual(sanitized[6], "")

    def test_csv_and_excel_export_sanitization(self):
        columns = ["Name", "Fee", "Notes"]
        rows_data = [
            ["=cmd|' /C calc'!A0", 5000, "+Dangerous formula"]
        ]

        # CSV
        csv_path = "/tmp/test_sanitize_export.csv"
        ExcelExporter.export_to_csv(columns, rows_data, csv_path)
        with open(csv_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = list(reader)
            self.assertEqual(rows[1][0], "'=cmd|' /C calc'!A0")
            self.assertEqual(rows[1][2], "'+Dangerous formula")
        if os.path.exists(csv_path):
            os.remove(csv_path)

        # Excel
        excel_path = "/tmp/test_sanitize_export.xlsx"
        ExcelExporter.export_to_excel(columns, rows_data, excel_path)
        wb = load_workbook(excel_path)
        ws = wb.active
        found = False
        for r in range(1, 10):
            val = ws.cell(row=r, column=1).value
            if val == "'=cmd|' /C calc'!A0":
                found = True
                self.assertEqual(ws.cell(row=r, column=3).value, "'+Dangerous formula")
                break
        self.assertTrue(found, "Sanitized formula string must be present in exported Excel")
        if os.path.exists(excel_path):
            os.remove(excel_path)

    # -------------------------------------------------------------------------
    # 2. Security & Role Authorization Enforcements
    # -------------------------------------------------------------------------
    def test_recovery_key_rotation_authorization(self):
        # Operational ADMIN role lacks SECURITY_RECOVERY_MANAGE (requires ADMINISTRATOR)
        SecurityContext.set_current_user(user_id=999, username="admin_user", role=Role.ADMIN.value)
        with self.assertRaises(ForbiddenError):
            RecoveryKeyService.rotate_recovery_key(999, "UNAUTHORIZED_ROTATION")

    def test_break_glass_attempts_bounded(self):
        import time
        from core.security import recovery as recovery_mod
        now = time.time()
        recovery_mod._GLOBAL_BREAK_GLASS_ATTEMPTS.extend([now] * 50)
        try:
            recovery_mod._enforce_global_rate_limit()
        except Exception:
            pass
        # Must be bounded to max _GLOBAL_MAX_ATTEMPTS * 2 entries (20)
        self.assertLessEqual(len(recovery_mod._GLOBAL_BREAK_GLASS_ATTEMPTS), 25)

    def test_email_change_authorization_enforcement(self):
        # Operational ADMIN lacks SECURITY_EMAIL_UPDATE (requires ADMINISTRATOR)
        SecurityContext.set_current_user(user_id=888, username="admin_user", role=Role.ADMIN.value)
        with self.assertRaises(ForbiddenError):
            EmailChangeService.initiate_email_change(888, "new_admin@sudharmsims.local")

        with self.assertRaises(ForbiddenError):
            EmailChangeService.finalize_email_change("fake_request_token")

    def test_audit_logs_view_authorization(self):
        # Operational ADMIN role lacks SECURITY_AUDIT_VIEW (requires ADMINISTRATOR)
        SecurityContext.set_current_user(user_id=777, username="admin_user", role=Role.ADMIN.value)
        with self.assertRaises(ForbiddenError):
            self.audit_repo.get_recent_security_logs(limit=10)

        # ADMINISTRATOR holds SECURITY_AUDIT_VIEW
        SecurityContext.set_current_user(user_id=1, username="administrator", role=Role.ADMINISTRATOR.value)
        logs = self.audit_repo.get_recent_security_logs(limit=5)
        self.assertIsInstance(logs, list)

    # -------------------------------------------------------------------------
    # 3. Admission Upfront 100% Payment Auto-Transition to COMPLETED
    # -------------------------------------------------------------------------
    def test_admission_upfront_100_percent_payment_completes(self):
        SecurityContext.set_current_user(user_id=1, username="admin", role=Role.ADMINISTRATOR.value)

        # Create active course
        code = f"AUD{int(datetime.now().timestamp()) % 100000}"
        c_dto = CourseCreateDTO(code=code, name=f"Audit Course {code}", base_fee=4000.0)
        course_id = self.course_service.create_course(c_dto)

        # Create admission with 100% upfront payment (4000)
        adm_dto = AdmissionCreateDTO(
            first_name="FullPay",
            last_name="Student",
            mobile_number="9876543210",
            secondary_mobile="9876543219",
            village="Nashik",
            course_id=course_id,
            status=AdmissionStatus.CONFIRMED,
            initial_payment_amount=4000.0,
            agreed_fee=4000.0,
            photo_bytes=b"dummy_student_photo_bytes",
            admin_pin="1234",
            created_by=1,
        )
        adm_id = self.admission_service.create_admission(adm_dto)

        # Verify admission status is automatically COMPLETED
        adm = self.admission_service.get_admission(adm_id)
        self.assertEqual(adm.status, AdmissionStatus.COMPLETED.value)
        self.assertEqual(adm.total_paid, 4000.0)
        self.assertEqual(adm.pending_amount, 0.0)

    # -------------------------------------------------------------------------
    # 4. Admission Update Financial Invariants
    # -------------------------------------------------------------------------
    def test_admission_update_financial_invariants(self):
        SecurityContext.set_current_user(user_id=1, username="admin", role=Role.ADMINISTRATOR.value)

        code = f"INV{int(datetime.now().timestamp()) % 100000}"
        c_dto = CourseCreateDTO(code=code, name=f"Invariant Course {code}", base_fee=10000.0)
        course_id = self.course_service.create_course(c_dto)

        adm_dto = AdmissionCreateDTO(
            first_name="Invariant",
            last_name="Test",
            mobile_number="9876543211",
            secondary_mobile="9876543218",
            village="Nashik",
            course_id=course_id,
            status=AdmissionStatus.CONFIRMED,
            initial_payment_amount=3000.0,
            agreed_fee=10000.0,
            photo_bytes=b"dummy_student_photo_bytes",
            admin_pin="1234",
            created_by=1,
        )
        adm_id = self.admission_service.create_admission(adm_dto)

        # 1. Negative agreed fee rejected
        with self.assertRaises(ValidationError) as ctx:
            self.admission_service.update_admission(
                AdmissionUpdateDTO(id=adm_id, course_id=course_id, agreed_fee=-100.0, discount=0.0, status=AdmissionStatus.CONFIRMED)
            )
        self.assertIn("Agreed fee cannot be negative", str(ctx.exception))

        # 2. Negative discount rejected
        with self.assertRaises(ValidationError) as ctx:
            self.admission_service.update_admission(
                AdmissionUpdateDTO(id=adm_id, course_id=course_id, agreed_fee=10000.0, discount=-50.0, status=AdmissionStatus.CONFIRMED)
            )
        self.assertIn("Discount cannot be negative", str(ctx.exception))

        # 3. Discount > agreed fee rejected
        with self.assertRaises(ValidationError) as ctx:
            self.admission_service.update_admission(
                AdmissionUpdateDTO(id=adm_id, course_id=course_id, agreed_fee=10000.0, discount=12000.0, status=AdmissionStatus.CONFIRMED)
            )
        self.assertIn("Discount cannot exceed agreed fee", str(ctx.exception))

        # 4. Final fee < total_paid rejected (already paid 3000, final fee cannot be 2000)
        with self.assertRaises(ValidationError) as ctx:
            self.admission_service.update_admission(
                AdmissionUpdateDTO(id=adm_id, course_id=course_id, agreed_fee=5000.0, discount=3500.0, status=AdmissionStatus.CONFIRMED)
            )
        self.assertIn("cannot be less than total amount already paid", str(ctx.exception))

        # 5. Disallow marking COMPLETED when balance is pending
        with self.assertRaises(ValidationError) as ctx:
            self.admission_service.update_admission(
                AdmissionUpdateDTO(id=adm_id, course_id=course_id, agreed_fee=10000.0, discount=1000.0, status=AdmissionStatus.COMPLETED)
            )
        self.assertIn("Cannot mark admission as COMPLETED while a balance", str(ctx.exception))

        # 6. Disallow direct transition to CANCELLED via update_admission
        with self.assertRaises(ValidationError) as ctx:
            self.admission_service.update_admission(
                AdmissionUpdateDTO(id=adm_id, course_id=course_id, agreed_fee=10000.0, discount=0.0, status=AdmissionStatus.CANCELLED)
            )
        self.assertIn("Direct transition to CANCELLED via update is disallowed", str(ctx.exception))

        # 7. Auto-transition to COMPLETED if final fee is adjusted to equal total_paid
        self.admission_service.update_admission(
            AdmissionUpdateDTO(id=adm_id, course_id=course_id, agreed_fee=5000.0, discount=2000.0, status=AdmissionStatus.CONFIRMED)
        )
        updated = self.admission_service.get_admission(adm_id)
        self.assertEqual(updated.final_fee, 3000.0)
        self.assertEqual(updated.total_paid, 3000.0)
        self.assertEqual(updated.status, AdmissionStatus.COMPLETED.value)

    # -------------------------------------------------------------------------
    # 5. Cache Invalidation Integrations
    # -------------------------------------------------------------------------
    def test_cache_invalidation_on_course_and_friendship(self):
        SecurityContext.set_current_user(user_id=1, username="admin", role=Role.ADMINISTRATOR.value)

        # Course update invalidates cache
        code = f"CCH{int(datetime.now().timestamp()) % 100000}"
        c_dto = CourseCreateDTO(code=code, name=f"Cache Course {code}", base_fee=6000.0)
        cid = self.course_service.create_course(c_dto)

        v1 = FeesCacheManager.get_version()
        self.course_service.update_course(CourseUpdateDTO(id=cid, code=code, name=f"Cache Course Updated {code}"))
        v2 = FeesCacheManager.get_version()
        self.assertGreater(v2, v1)

        # Student friendship invalidates cache
        s1_dto = StudentCreateDTO(first_name="Fr1", last_name="Stud", mobile_number="9876543220", village="Nashik")
        s2_dto = StudentCreateDTO(first_name="Fr2", last_name="Stud", mobile_number="9876543221", village="Nashik")
        s1_id = self.student_service.create_student(s1_dto)
        s2_id = self.student_service.create_student(s2_dto)

        v3 = FeesCacheManager.get_version()
        self.student_service.add_student_friend(s1_id, s2_id)
        v4 = FeesCacheManager.get_version()
        self.assertGreater(v4, v3)

        self.student_service.remove_student_friend(s1_id, s2_id)
        v5 = FeesCacheManager.get_version()
        self.assertGreater(v5, v4)

    # -------------------------------------------------------------------------
    # 6. Report Candidate Sequence Parsing
    # -------------------------------------------------------------------------
    def test_report_c_seq_safe_formatting(self):
        dummy_rows = [
            {"admission_id": 1, "candidate_year": 2026, "candidate_sequence": "007", "agreed_fee": 5000, "discount": 0},
            {"admission_id": 2, "candidate_year": 2026, "candidate_sequence": "NON_NUMERIC_SEQ", "agreed_fee": 5000, "discount": 0},
            {"admission_id": 3, "candidate_year": 2026, "candidate_sequence": None, "agreed_fee": 5000, "discount": 0},
        ]
        mapped = self.report_service._map_report_rows(dummy_rows)
        self.assertEqual(len(mapped), 3)
        self.assertEqual(mapped[0]["admission_id"], "2026-007")
        self.assertEqual(mapped[1]["admission_id"], "2026-NON_NUMERIC_SEQ")
        self.assertEqual(mapped[2]["admission_id"], "2026-003")


if __name__ == "__main__":
    unittest.main()
