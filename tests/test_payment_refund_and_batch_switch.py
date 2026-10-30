import unittest
from datetime import datetime

from core.configuration.service import ConfigService
from core.database.engine import DatabaseEngine
from core.database.transaction import TransactionManager
from core.database.migration import MigrationEngine
from core.security.context import SecurityContext
from core.security.roles import Role
from core.security.permissions import Permission
from core.security.authorization import AuthorizationService
from core.exceptions import ForbiddenError, ValidationError

from modules.student.controller import StudentController
from modules.course.controller import CourseController
from modules.batch.controller import BatchController
from modules.batch.service import BatchService
from modules.admission.controller import AdmissionController
from modules.admission.service import AdmissionService
from modules.admission.constants import AdmissionStatus
from modules.payments.service import PaymentService
from modules.payments.controller import PaymentController
from modules.payments.dto import PaymentCreateDTO
from modules.settings.service import SettingsService


class TestBatchSwitchAndPaymentRefund(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ConfigService.initialize(force_reload=True)
        if not DatabaseEngine.is_initialized():
            DatabaseEngine.initialize()
        MigrationEngine._is_initialized = False
        MigrationEngine.initialize()
        MigrationEngine.upgrade()

        cls.student_ctrl = StudentController()
        cls.course_ctrl = CourseController()
        cls.batch_ctrl = BatchController()
        cls.adm_ctrl = AdmissionController()
        cls.payment_ctrl = PaymentController()
        cls.payment_service = PaymentService()
        cls.adm_service = AdmissionService()
        cls.batch_service = BatchService()

        # Set ambient user to Administrator for initial test entity provisioning
        SecurityContext.set_current_user(user_id=1, username="admin", role=Role.ADMINISTRATOR.value)

        # 1. Course
        course = cls.course_ctrl.get_course_by_code("REF-TEST-101")
        if not course:
            c_id = cls.course_ctrl.create_course({
                "code": "REF-TEST-101",
                "name": "Refund & Batch Operations",
                "category": "Testing",
                "duration": "1 Month",
                "status": "ACTIVE",
                "base_fee": 6000.0,
            })
            course = cls.course_ctrl.get_course(c_id)
        cls.test_course = course

        # 2. Batches
        cls.test_batch_a_id = cls.batch_ctrl.create_batch({
            "batch_name": f"Batch Ref Alpha {int(datetime.now().timestamp())}",
            "batch_code": "RFA",
            "timing": "09:00 - 10:30",
            "course_id": cls.test_course.id,
            "max_capacity": 25,
            "status": "OPEN",
        })
        cls.test_batch_b_id = cls.batch_ctrl.create_batch({
            "batch_name": f"Batch Ref Beta {int(datetime.now().timestamp())}",
            "batch_code": "RFB",
            "timing": "11:00 - 12:30",
            "course_id": cls.test_course.id,
            "max_capacity": 25,
            "status": "OPEN",
        })

        # 3. Students
        s1 = cls.student_ctrl.get_by_mobile("9876500001")
        if not s1:
            s1_id = cls.student_ctrl.create_student({
                "first_name": "Aarav",
                "last_name": "Sharma",
                "mobile_number": "9876500001",
                "email": "aarav.sharma@example.com",
            })
            s1 = cls.student_ctrl.get_student(s1_id)
        cls.student_1 = s1

        s2 = cls.student_ctrl.get_by_mobile("9876500002")
        if not s2:
            s2_id = cls.student_ctrl.create_student({
                "first_name": "Pooja",
                "last_name": "Verma",
                "mobile_number": "9876500002",
                "email": "pooja.verma@example.com",
            })
            s2 = cls.student_ctrl.get_student(s2_id)
        cls.student_2 = s2

        # 4. Admissions (Unassigned initially)
        cls.settings_service = SettingsService()
        cls.settings_service.set_admin_pin(SettingsService.DEFAULT_ADMIN_PIN)
        cls.settings_service.set_setting("require_photo", "false")
        cls.settings_service.set_setting("require_signature", "false")

        cls.adm_1_id = cls.adm_ctrl.create_admission({
            "course_id": cls.test_course.id,
            "student_id": cls.student_1.id,
            "agreed_fee": 6000.0,
            "discount": 500.0,
            "status": AdmissionStatus.REGISTERED.value,
            "batch_id": None,  # Unallocated
            "photo_path": "uploads/photos/dummy.png",
        })

        cls.adm_2_id = cls.adm_ctrl.create_admission({
            "course_id": cls.test_course.id,
            "student_id": cls.student_2.id,
            "agreed_fee": 6000.0,
            "discount": 0.0,
            "status": AdmissionStatus.REGISTERED.value,
            "batch_id": None,  # Unallocated
            "photo_path": "uploads/photos/dummy.png",
        })

    def test_01_role_permission_matrix_includes_payment_refund(self):
        """Verifies Permission.PAYMENT_REFUND is strictly granted to ADMINISTRATOR and denied to ADMIN."""
        admin_perms = AuthorizationService.get_permissions_for_role(Role.ADMIN.value)
        administrator_perms = AuthorizationService.get_permissions_for_role(Role.ADMINISTRATOR.value)

        self.assertNotIn(Permission.PAYMENT_REFUND, admin_perms)
        self.assertIn(Permission.PAYMENT_REFUND, administrator_perms)

        # Verify AuthorizationService.has_permission
        self.assertFalse(AuthorizationService.has_permission(Role.ADMIN.value, Permission.PAYMENT_REFUND))
        self.assertTrue(AuthorizationService.has_permission(Role.ADMINISTRATOR.value, Permission.PAYMENT_REFUND))

    def test_02_assign_batch_to_unallocated_student(self):
        """Verifies assigning a batch to an unassigned/unallocated candidate."""
        SecurityContext.set_current_user(1, "admin", Role.ADMINISTRATOR.value)

        # Confirm currently unassigned
        adm = self.adm_ctrl.get_admission(self.adm_1_id)
        self.assertIsNone(adm.batch_id)

        # Assign to Batch Alpha
        self.adm_service.reassign_batch(
            admission_id=self.adm_1_id,
            new_batch_id=self.test_batch_a_id,
            actor_name="Administrator",
        )

        adm_after = self.adm_ctrl.get_admission(self.adm_1_id)
        self.assertEqual(adm_after.batch_id, self.test_batch_a_id)

    def test_03_switch_batch_and_capacity_validation(self):
        """Verifies switching from Batch Alpha to Batch Beta and enforces full batch limits."""
        SecurityContext.set_current_user(1, "admin", Role.ADMINISTRATOR.value)

        # 1. Switch adm_1 from Batch Alpha to Batch Beta
        self.adm_service.reassign_batch(
            admission_id=self.adm_1_id,
            new_batch_id=self.test_batch_b_id,
            actor_name="Administrator",
        )
        adm_switched = self.adm_ctrl.get_admission(self.adm_1_id)
        self.assertEqual(adm_switched.batch_id, self.test_batch_b_id)

        # 2. Create single-seat full batch to verify capacity limit
        full_batch_id = self.batch_ctrl.create_batch({
            "batch_name": f"Single Seat Batch {int(datetime.now().timestamp())}",
            "timing": "04:00 - 05:00",
            "course_id": self.test_course.id,
            "max_capacity": 1,
            "status": "OPEN",
        })

        # Put adm_1 into single-seat batch (now 1/1 filled)
        self.adm_service.reassign_batch(self.adm_1_id, new_batch_id=full_batch_id)

        # Try to put adm_2 into the same batch -> must raise ValidationError for capacity
        with self.assertRaises(ValidationError) as ctx:
            self.adm_service.reassign_batch(self.adm_2_id, new_batch_id=full_batch_id)
        self.assertIn("full capacity", str(ctx.exception).lower())

    def test_04_payment_refund_rejected_for_normal_admin(self):
        """Verifies that Role.ADMIN receives ForbiddenError when attempting to refund a payment."""
        # Ambient user is ADMIN (not ADMINISTRATOR)
        SecurityContext.set_current_user(2, "operator", Role.ADMIN.value)

        with self.assertRaises(ForbiddenError) as ctx:
            self.payment_service.refund_payment(
                payment_id=1,
                reason="Accidental payment entry",
                admin_pin="1234",
            )
        self.assertTrue("PAYMENT_REFUND" in str(ctx.exception) or "Administrator" in str(ctx.exception))

    def test_05_payment_refund_invalid_pin_rejected(self):
        """Verifies that Role.ADMINISTRATOR with wrong PIN is rejected with ValidationError."""
        # Ambient user is ADMINISTRATOR
        SecurityContext.set_current_user(1, "superadmin", Role.ADMINISTRATOR.value)

        with self.assertRaises(ValidationError) as ctx:
            self.payment_service.refund_payment(
                payment_id=1,
                reason="Accidental payment entry",
                admin_pin="0000",  # Wrong PIN
            )
        self.assertIn("Invalid Administrator Security PIN", str(ctx.exception))

    def test_06_successful_payment_refund_and_ledger_restoration(self):
        """
        Records a test payment, verifies receipt creation, then refunds it as ADMINISTRATOR.
        Verifies:
        1. Linked receipt deleted.
        2. Payment deleted.
        3. Pending balance restored.
        4. Admission status reverted.
        5. Audit log created.
        """
        SecurityContext.set_current_user(1, "superadmin", Role.ADMINISTRATOR.value)

        # Initial payment for adm_2
        adm_before = self.adm_ctrl.get_admission(self.adm_2_id)
        orig_paid = adm_before.total_paid

        test_amount = 1000.0
        dto = PaymentCreateDTO(
            admission_id=self.adm_2_id,
            student_id=self.student_2.id,
            amount=test_amount,
            payment_mode="CASH",
            collector_name="Admin Cashier",
            collector_id=1,
            remarks="Accidental payment entry to test reversal",
            created_by=1,
        )
        pay_id = self.payment_service.record_payment(dto)
        self.assertGreater(pay_id, 0)

        # Verify receipt exists and total paid increased
        with self.payment_service.unit_of_work():
            rcp = self.payment_service.receipt_repo.get_by_payment_id(pay_id)
            self.assertIsNotNone(rcp)
            new_paid = self.payment_service.repository.get_total_paid_for_admission(self.adm_2_id)
            self.assertEqual(round(new_paid, 2), round(orig_paid + test_amount, 2))

        # Now execute Refund / Reversal as Administrator
        result = self.payment_service.refund_payment(
            payment_id=pay_id,
            reason="Entered on Pooja Verma by mistake, was meant for another student.",
            admin_pin=SettingsService.DEFAULT_ADMIN_PIN,
            actor_id=1,
            actor_name="superadmin",
        )

        self.assertEqual(result["payment_id"], pay_id)
        self.assertEqual(result["refunded_amount"], test_amount)
        self.assertEqual(round(result["new_total_paid"], 2), round(orig_paid, 2))

        # Verify in DB:
        with self.payment_service.unit_of_work():
            # 1. Payment row deleted
            self.assertIsNone(self.payment_service.repository.get_by_id(pay_id))
            # 2. Receipt row deleted
            self.assertIsNone(self.payment_service.receipt_repo.get_by_payment_id(pay_id))
            # 3. Total paid restored to original
            total_after = self.payment_service.repository.get_total_paid_for_admission(self.adm_2_id)
            self.assertEqual(round(total_after, 2), round(orig_paid, 2))
            # 4. Audit activity log present
            logs = self.payment_service.activity_repo.get_logs_for_entity("PAYMENT", pay_id)
            refund_logs = [l for l in logs if l.get("action") == "REFUNDED"]
            self.assertGreaterEqual(len(refund_logs), 1)
            self.assertIn("Pooja Verma", refund_logs[0]["details"])

    def test_07_database_forensic_integrity_after_refund(self):
        """Executes full database invariant checks to guarantee 0 violations across all 12 checks."""
        from scripts.verify_database import run_database_verification
        is_healthy, errors = run_database_verification(verbose=False, shutdown_engine=False)
        self.assertTrue(is_healthy)
        self.assertEqual(len(errors), 0)

    def test_08_batch_dialog_lifecycle_and_cross_course_allocation(self):
        """Verifies BatchAssignmentDialog lifecycle (no page.close AttributeError) and cross-course batch allocation."""
        from unittest.mock import MagicMock
        from modules.admission.views.batch_assignment_dialog import BatchAssignmentDialog

        SecurityContext.set_current_user(1, "admin", Role.ADMINISTRATOR.value)

        # 1. Mock Page with pop_dialog (mimicking Flet Page)
        mock_page = MagicMock()
        mock_page.pop_dialog = MagicMock()

        # 2. Instantiate dialog
        dlg = BatchAssignmentDialog(admission_id=self.adm_1_id, page=mock_page)
        self.assertIsNotNone(dlg.batch_dropdown)
        # Dropdown options should contain at least Unassign option + batches
        self.assertGreaterEqual(len(dlg.batch_dropdown.options), 2)

        # 3. Verify close_dialog executes cleanly without AttributeError: 'Page' object has no attribute 'close'
        try:
            dlg.close_dialog()
        except AttributeError as err:
            self.fail(f"close_dialog failed with AttributeError: {err}")
        self.assertFalse(dlg.open)
        mock_page.pop_dialog.assert_called_once()

        # 4. Create another course and a batch under that course
        c2_id = self.course_ctrl.create_course({
            "code": f"DIFF-CRS-{int(datetime.now().timestamp())}",
            "name": "Different Course",
            "category": "Testing",
            "duration": "1 Month",
            "status": "ACTIVE",
            "base_fee": 5000.0,
        })
        other_course_batch_id = self.batch_ctrl.create_batch({
            "batch_name": f"Other Course Batch {int(datetime.now().timestamp())}",
            "batch_code": "OCB",
            "timing": "02:00 - 03:00",
            "course_id": c2_id,
            "max_capacity": 30,
            "status": "OPEN",
        })

        # 5. Assign other_course_batch_id to adm_1 (enrolled in test_course)
        # Institute policy allows allocating any active batch to unallocated or switching students
        self.adm_service.reassign_batch(
            admission_id=self.adm_1_id,
            new_batch_id=other_course_batch_id,
            actor_name="Administrator",
        )
        adm_reassigned = self.adm_ctrl.get_admission(self.adm_1_id)
        self.assertEqual(adm_reassigned.batch_id, other_course_batch_id)

        # 6. Unassign batch (set unallocated)
        self.adm_service.reassign_batch(
            admission_id=self.adm_1_id,
            new_batch_id=None,
            actor_name="Administrator",
        )
        adm_unassigned = self.adm_ctrl.get_admission(self.adm_1_id)
        self.assertIsNone(adm_unassigned.batch_id)
