# tests/test_payment_gateway_and_shortcuts.py
"""
Comprehensive Automated Test Suite for Payment Gateway & Shortcuts.
Validates:
1. Universal Search Mode vs Direct Pre-filled Mode in PaymentDialog.
2. Dynamic Quick-Amount Chips and Live Reactive Balance Projection.
3. Payment Modes & Interactive UPI QR Assistant.
4. Security PIN Verification and Celebration Receipt SnackBar.
5. Admission Module Shortcut Button & Row-Level Fast Action.
6. Fees Module Shortcut Button, Row-Level Quick Collect & Receipt Access.
"""

import os
import unittest
from typing import Optional, Any
import flet as ft

os.environ["SIMS_ENV"] = "testing"

from core.configuration.service import ConfigService
from core.database.engine import DatabaseEngine
from core.database.migration import MigrationEngine
from core.security.context import SecurityContext
from core.security.roles import Role

from modules.student.controller import StudentController
from modules.course.controller import CourseController
from modules.batch.controller import BatchController
from modules.admission.controller import AdmissionController
from modules.admission.views.admission_home import AdmissionHome
from modules.admission.views.payment_dialog import PaymentDialog
from modules.admission.views.receipt_dialog import ReceiptDialog
from modules.reports.views.reports_home import ReportsHome
from modules.reports.controller import ReportsController


class MockFletSession:
    def __init__(self):
        self._data = {}

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value: Any):
        self._data[key] = value

    def clear(self):
        self._data.clear()


class MockFletPage:
    def __init__(self):
        self.session = MockFletSession()
        self.dialog = None
        self.snack_bar = None
        self.overlay = []
        self.route = "/dashboard"
        self.width = 1280
        self.height = 800

    def update(self) -> None:
        pass

    def show_dialog(self, dlg: ft.AlertDialog) -> None:
        self.dialog = dlg
        dlg.open = True
        try:
            dlg._page = self
        except Exception:
            pass

    def pop_dialog(self) -> None:
        if self.dialog:
            self.dialog.open = False
            self.dialog = None

    def show_snack_bar(self, snack: ft.SnackBar) -> None:
        self.snack_bar = snack
        snack.open = True


class TestPaymentGatewayAndShortcuts(unittest.TestCase):
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
        cls.reports_ctrl = ReportsController()

        # Seed test student, course, and admission with outstanding balance
        SecurityContext.set_current_user(user_id=2, username="administrator", role=Role.ADMINISTRATOR.value)

        # 1. Course
        course = cls.course_ctrl.get_course_by_code("PAY-GATEWAY-101")
        if not course:
            c_id = cls.course_ctrl.create_course({
                "code": "PAY-GATEWAY-101",
                "name": "Advanced Payment Systems",
                "category": "Finance",
                "duration": "2 Months",
                "status": "ACTIVE",
                "base_fee": 10000.0,
            })
            course = cls.course_ctrl.get_course(c_id)
        cls.test_course = course

        # 2. Batch
        batches = cls.batch_ctrl.list_batches_by_course(cls.test_course.id)
        if not batches:
            b_id = cls.batch_ctrl.create_batch({
                "batch_name": "Batch FinTech 01",
                "batch_code": "FIN01",
                "timing": "10:00 - 11:30",
                "course_id": cls.test_course.id,
                "start_date": "2026-11-01",
                "end_date": "2026-12-31",
                "max_capacity": 30,
                "status": "OPEN",
            })
            cls.test_batch = cls.batch_ctrl.get_batch(b_id)
        else:
            cls.test_batch = batches[0]

        # 3. Student
        student = cls.student_ctrl.get_by_mobile("9988776655")
        if not student:
            s_id = cls.student_ctrl.create_student({
                "first_name": "Rohan",
                "last_name": "Kulkarni",
                "mobile_number": "9988776655",
                "email": "rohan.kulkarni@example.com",
                "qualification": "B.Tech",
            })
            student = cls.student_ctrl.get_student(s_id)
        cls.test_student = student

        # 4. Admission with partial initial payment (₹4,000 paid out of ₹10,000; ₹6,000 pending)
        adms, _ = cls.adm_ctrl.filter_admissions({"query": "9988776655"})
        if not adms:
            adm_id = cls.adm_ctrl.create_admission({
                "student_id": cls.test_student.id,
                "first_name": "Rohan",
                "last_name": "Kulkarni",
                "mobile_number": "9988776655",
                "course_id": cls.test_course.id,
                "batch_id": cls.test_batch.id,
                "agreed_fee": 10000.0,
                "status": "REGISTERED",
                "photo_path": "uploads/photos/dummy.png",
            })
            cls.adm_ctrl.confirm_admission_with_payment(
                admission_id=adm_id,
                amount=4000.0,
                payment_mode="CASH",
                admin_pin="1234",
                collector_name="Admin",
            )
            cls.test_admission_id = adm_id
        else:
            cls.test_admission_id = adms[0].id

    def setUp(self):
        SecurityContext.set_current_user(user_id=2, username="administrator", role=Role.ADMINISTRATOR.value)
        self.page = MockFletPage()
        self.page.session.set("user_id", 2)
        self.page.session.set("role", Role.ADMINISTRATOR.value)

    # -------------------------------------------------------------------------
    # TEST 1: Direct Mode PaymentDialog (Pre-filled for Student)
    # -------------------------------------------------------------------------
    def test_01_direct_mode_payment_dialog_ledger_and_chips(self):
        """Validates Direct Mode initialization, 3-card balance ledger, quick-amount chips, and live remaining balance."""
        dlg = PaymentDialog(
            admission_id=self.test_admission_id,
            student_name="Rohan Kulkarni",
            course_name="Advanced Payment Systems",
            candidate_number="2026-099",
            total_fee=10000.0,
            already_paid=4000.0,
            page=self.page,
        )
        self.page.show_dialog(dlg)

        # Verify Header and Ledger
        self.assertEqual(dlg.is_direct_mode, True)
        self.assertEqual(dlg.student_name, "Rohan Kulkarni")
        self.assertEqual(dlg.total_fee, 10000.0)
        self.assertEqual(dlg.already_paid, 4000.0)
        self.assertEqual(dlg.pending_balance, 6000.0)
        self.assertAlmostEqual(dlg.balance_progress.value, 0.4, places=2)

        # Verify Quick Amount Chips presence
        self.assertGreaterEqual(len(dlg.quick_chips_row.controls), 3)

        # Test clicking quick chip for full balance (₹6,000)
        dlg._set_quick_amount(6000.0)
        self.assertEqual(dlg.amount_input.value, "6000")
        self.assertIn("Full settlement", dlg.balance_projection_text.value)

        # Test partial payment amount (₹2,500)
        dlg.amount_input.value = "2500"
        dlg._update_balance_projection()
        self.assertIn("Remaining balance", dlg.balance_projection_text.value)
        self.assertIn("₹3,500.00", dlg.balance_projection_text.value)

        # Test overpayment amount (₹8,000 against ₹6,000 pending)
        dlg.amount_input.value = "8000"
        dlg._update_balance_projection()
        self.assertIn("exceeds pending balance", dlg.balance_projection_text.value)

    # -------------------------------------------------------------------------
    # TEST 2: Universal Search Mode PaymentDialog (No admission_id provided)
    # -------------------------------------------------------------------------
    def test_02_universal_search_mode_and_candidate_selection(self):
        """Validates Universal Search Mode where user searches and picks a candidate dynamically."""
        dlg = PaymentDialog(admission_id=None, page=self.page)
        self.page.show_dialog(dlg)

        self.assertEqual(dlg.is_direct_mode, False)
        self.assertEqual(dlg.search_mode_box.visible, True)

        # Search for test student by mobile number
        dlg.search_input.value = "9988776655"
        dlg._populate_candidates("9988776655")

        # Results should contain Rohan Kulkarni
        self.assertGreaterEqual(len(dlg.search_results_container.controls), 1)

        # Simulate selecting candidate
        dlg._select_candidate(self.test_admission_id)
        self.assertEqual(dlg.admission_id, self.test_admission_id)
        adm = self.adm_ctrl.get_admission(self.test_admission_id)
        self.assertEqual(dlg.total_fee, float(adm.final_fee))
        self.assertEqual(dlg.student_name, adm.student_name)

    # -------------------------------------------------------------------------
    # TEST 3: Payment Modes & Reactive UPI Assistant Box
    # -------------------------------------------------------------------------
    def test_03_payment_modes_and_upi_assistant(self):
        """Validates mode selection switches, particularly UPI QR code and VPA helper visibility."""
        dlg = PaymentDialog(admission_id=self.test_admission_id, page=self.page)
        self.page.show_dialog(dlg)

        # Default mode is CASH -> UPI helper is hidden
        self.assertEqual(dlg.mode_dropdown.value, "CASH")
        self.assertEqual(dlg.upi_helper_container.visible, False)

        # Switch to UPI -> helper box becomes visible with VPA
        dlg.mode_dropdown.value = "UPI"
        dlg._handle_mode_change(None)
        self.assertEqual(dlg.upi_helper_container.visible, True)

        # Switch back to CHEQUE -> helper box hidden
        dlg.mode_dropdown.value = "CHEQUE"
        dlg._handle_mode_change(None)
        self.assertEqual(dlg.upi_helper_container.visible, False)

    # -------------------------------------------------------------------------
    # TEST 4: PIN Validation & Successful Payment Execution
    # -------------------------------------------------------------------------
    def test_04_payment_execution_pin_validation_and_receipt_toast(self):
        """Validates Admin/Staff PIN checks, execution, dialog dismissal, and celebratory receipt snackbar."""
        completed_pids = []

        dlg = PaymentDialog(
            admission_id=self.test_admission_id,
            page=self.page,
            on_payment_completed=lambda pid: completed_pids.append(pid),
        )
        self.page.show_dialog(dlg)

        # 1. Missing PIN validation
        dlg.amount_input.value = "1000.0"
        dlg.pin_input.value = ""
        dlg.handle_confirm_payment(None)
        self.assertEqual(dlg.error_container.visible, True)
        self.assertIn("PIN is required", dlg.error_text.value)

        # 2. Invalid PIN validation
        dlg.pin_input.value = "9999"
        dlg.handle_confirm_payment(None)
        self.assertEqual(dlg.error_container.visible, True)
        self.assertIn("Invalid", dlg.error_text.value)

        # 3. Valid PIN (1234)
        dlg.pin_input.value = "1234"
        dlg.mode_dropdown.value = "CASH"
        dlg.collector_dropdown.value = "Admin"
        dlg.handle_confirm_payment(None)

        # Verification: Receipt dialog immediately displayed, callback triggered, snackbar surfaced with receipt action
        self.assertIsNotNone(self.page.dialog)
        self.assertIsInstance(self.page.dialog, ReceiptDialog)
        self.assertEqual(len(completed_pids), 1)
        self.assertIsNotNone(self.page.dialog.pdf_btn)
        self.assertIsNotNone(self.page.dialog.whatsapp_btn)
        self.assertIsNotNone(self.page.dialog.print_btn)
        self.assertIsNotNone(self.page.snack_bar)
        self.assertEqual(self.page.snack_bar.action, "View Receipt 📄")

        # Verify receipt dialog can be closed and re-opened via the action callback
        self.page.dialog.close_modal()
        self.assertIsNone(self.page.dialog)
        self.page.snack_bar.on_action(None)
        self.assertIsNotNone(self.page.dialog)
        self.assertIsInstance(self.page.dialog, ReceiptDialog)

    # -------------------------------------------------------------------------
    # TEST 5: Admission Module Shortcut & Row Action
    # -------------------------------------------------------------------------
    def test_05_admission_module_shortcut_and_row_button(self):
        """Validates that AdmissionHome has the top 'Collect Payment' shortcut and row-level quick payment button."""
        adm_home = AdmissionHome()
        adm_home._root_page = self.page
        adm_home._page = self.page
        adm_home.did_mount()

        # 1. Top Header Collect Payment Button exists
        self.assertTrue(hasattr(adm_home, "collect_payment_btn"))
        self.assertIsInstance(adm_home.collect_payment_btn, (ft.ElevatedButton, ft.Button))
        self.assertIn("Payment Gateway", adm_home.collect_payment_btn.tooltip)

        # 2. Clicking top shortcut opens Universal Search PaymentDialog
        adm_home.handle_collect_payment(None)
        self.assertIsNotNone(self.page.dialog)
        self.assertIsInstance(self.page.dialog, PaymentDialog)
        self.assertEqual(self.page.dialog.is_direct_mode, False)
        self.page.pop_dialog()

        # 3. Row-level quick action opens Direct Mode PaymentDialog for admission
        adm_home.handle_collect_payment(self.test_admission_id)
        self.assertIsNotNone(self.page.dialog)
        self.assertIsInstance(self.page.dialog, PaymentDialog)
        self.assertEqual(self.page.dialog.is_direct_mode, True)
        self.assertEqual(self.page.dialog.admission_id, self.test_admission_id)
        self.page.pop_dialog()

    # -------------------------------------------------------------------------
    # TEST 6: Fees Module Shortcut, Row Action & Tab 2 Receipt Action
    # -------------------------------------------------------------------------
    def test_06_fees_module_shortcut_and_row_button(self):
        """Validates that ReportsHome (Fees Module) has header shortcut, row payment buttons, and receipt actions."""
        reports_home = ReportsHome()
        reports_home._root_page = self.page
        reports_home._page = self.page
        reports_home.did_mount()

        # 1. Top Header Collect Payment Button exists
        self.assertTrue(hasattr(reports_home, "collect_payment_btn"))
        self.assertIsInstance(reports_home.collect_payment_btn, (ft.FilledButton, ft.Button))
        self.assertEqual(reports_home.collect_payment_btn.content, "Collect Payment")

        # 2. Clicking top shortcut opens PaymentDialog
        reports_home.handle_collect_payment(None)
        self.assertIsNotNone(self.page.dialog)
        self.assertIsInstance(self.page.dialog, PaymentDialog)
        self.assertEqual(self.page.dialog.is_direct_mode, False)
        self.page.pop_dialog()

        # 3. Row action helper opens Pre-filled PaymentDialog
        mock_row = {
            "sr_no": 1,
            "admission_id_raw": self.test_admission_id,
            "admission_id": "2026-099",
            "name": "Rohan Kulkarni",
            "course_name": "Advanced Payment Systems",
            "total_fees": 10000.0,
            "total_paid": 5000.0,
            "pending_fees": 5000.0,
        }
        reports_home.handle_collect_payment_for_row(mock_row)
        self.assertIsNotNone(self.page.dialog)
        self.assertIsInstance(self.page.dialog, PaymentDialog)
        self.assertEqual(self.page.dialog.student_name, "Rohan Kulkarni")
        self.assertEqual(self.page.dialog.admission_id, self.test_admission_id)
        self.page.pop_dialog()

        # 4. Tab 2 Receipt handler opens ReceiptDialog
        from modules.payments.controller import PaymentController
        payments = PaymentController().get_payments_for_admission(self.test_admission_id)
        if payments:
            pid = payments[0].id
            reports_home.handle_view_receipt(pid)
            self.assertIsNotNone(self.page.dialog)
            self.assertIsInstance(self.page.dialog, ReceiptDialog)
            self.page.pop_dialog()


if __name__ == "__main__":
    unittest.main()
