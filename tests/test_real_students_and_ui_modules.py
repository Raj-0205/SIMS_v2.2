# tests/test_real_students_and_ui_modules.py
"""
End-to-End Real Student & UI Module Validation Suite.
Simulates real student enrollment, course & batch creation/editing,
admission confirmation, payment, receipt generation, workspace viewing,
reports, and destructive operations with full UI dialog verification.
"""

import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any
import flet as ft

os.environ["SIMS_ENV"] = "testing"

from core.configuration.service import ConfigService
from core.database.engine import DatabaseEngine
from core.database.migration import MigrationEngine
from core.security.context import SecurityContext
from core.security.roles import Role
from core.security.permissions import Permission
from core.exceptions import ForbiddenError, ValidationError

from modules.student.controller import StudentController
from modules.course.controller import CourseController
from modules.batch.controller import BatchController
from modules.admission.controller import AdmissionController
from modules.reports.controller import ReportsController
from modules.receipts.controller import ReceiptController

from modules.course.views.course_home import CourseHome
from modules.course.views.course_form_modal import CourseFormModal
from modules.course.views.course_detail_dialog import CourseDetailDialog
from modules.batch.views.batch_home import BatchHome
from modules.batch.views.batch_form_modal import BatchFormModal
from modules.student.views.student_home import StudentHome
from modules.student.views.student_form_modal import StudentFormModal
from modules.student.views.student_workspace_dialog import StudentWorkspaceDialog
from modules.admission.views.admission_home import AdmissionHome
from modules.admission.views.admission_form_modal import AdmissionFormModal
from modules.admission.views.admission_workspace_dialog import AdmissionWorkspaceDialog
from modules.admission.views.payment_dialog import PaymentDialog
from modules.admission.views.receipt_dialog import ReceiptDialog
from modules.reports.views.reports_home import ReportsHome


class RealMockSession:
    def __init__(self):
        self.store = {}

    def get(self, key: str, default=None):
        return self.store.get(key, default)

    def set(self, key: str, value):
        self.store[key] = value

    def remove(self, key: str):
        self.store.pop(key, None)

    def clear(self):
        self.store.clear()


class RealMockPage:
    def __init__(self):
        self.session = RealMockSession()
        self.dialog = None
        self.overlay = []
        self.views = []
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

    def open(self, dlg: ft.AlertDialog) -> None:
        self.show_dialog(dlg)

    def close(self, dlg: ft.AlertDialog) -> None:
        self.pop_dialog()

    def navigate(self, route: str) -> None:
        self.route = route


class TestRealStudentsAndUIModules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ConfigService.initialize(force_reload=True)
        if not DatabaseEngine.is_initialized():
            DatabaseEngine.initialize()
        MigrationEngine._is_initialized = False
        MigrationEngine.initialize()
        MigrationEngine.upgrade()

        cls.stud_ctrl = StudentController()
        cls.course_ctrl = CourseController()
        cls.batch_ctrl = BatchController()
        cls.adm_ctrl = AdmissionController()
        cls.reports_ctrl = ReportsController()
        cls.receipt_ctrl = ReceiptController()

        # Idempotent pre-cleanup of test records
        with DatabaseEngine.connection() as conn:
            conn.execute("DELETE FROM activity_logs WHERE entity_type = 'COURSE' AND entity_id IN (SELECT id FROM courses WHERE code IN ('TEST-AUTOMATION', 'TEST-FULLSTACK'));")
            conn.execute("DELETE FROM receipts WHERE student_id IN (SELECT id FROM students WHERE mobile_number = '9823456789');")
            conn.execute("DELETE FROM payments WHERE student_id IN (SELECT id FROM students WHERE mobile_number = '9823456789');")
            conn.execute("DELETE FROM admission_courses WHERE admission_id IN (SELECT id FROM admissions WHERE student_id IN (SELECT id FROM students WHERE mobile_number = '9823456789'));")
            conn.execute("DELETE FROM admissions WHERE student_id IN (SELECT id FROM students WHERE mobile_number = '9823456789');")
            conn.execute("DELETE FROM students WHERE mobile_number = '9823456789';")
            conn.execute("DELETE FROM batches WHERE course_id IN (SELECT id FROM courses WHERE code IN ('TEST-AUTOMATION', 'TEST-FULLSTACK'));")
            conn.execute("DELETE FROM courses WHERE code IN ('TEST-AUTOMATION', 'TEST-FULLSTACK');")

    def setUp(self):
        SecurityContext.clear()
        self.page = RealMockPage()

    def test_01_course_home_ui_and_dialog_open(self):
        """Verify CourseHome renders, opens CourseFormModal and CourseDetailDialog via show_dialog."""
        SecurityContext.set_current_user(user_id=2, username="administrator", role=Role.ADMINISTRATOR.value)
        self.page.session.set("user_id", 2)
        self.page.session.set("role", Role.ADMINISTRATOR.value)

        course_home = CourseHome()
        course_home._root_page = self.page
        course_home._page = self.page
        course_home.did_mount()

        # Verify initial courses rendered
        self.assertGreaterEqual(len(course_home.cards_grid.controls), 1)

        # 1. Open Add Course Modal
        course_home._handle_add_course(None)
        self.assertIsNotNone(self.page.dialog)
        self.assertIsInstance(self.page.dialog, CourseFormModal)

        # Fill and save modal
        modal: CourseFormModal = self.page.dialog
        modal.code_input.value = "TEST-AUTOMATION"
        modal.name_input.value = "Automation Scripting Lab"
        modal.category_dropdown.value = "Programming"
        modal.fee_input.value = "7500.0"
        modal.duration_input.value = "3 Months"
        modal.handle_save(None)

        # Dialog should be popped
        self.assertIsNone(self.page.dialog)

        # Fetch created course
        created = self.course_ctrl.get_course_by_code("TEST-AUTOMATION")
        self.assertIsNotNone(created)
        self.assertEqual(created.name, "Automation Scripting Lab")

        # 2. Open Edit Course Modal
        course_home._handle_edit_course(created)
        self.assertIsNotNone(self.page.dialog)
        self.assertIsInstance(self.page.dialog, CourseFormModal)
        modal = self.page.dialog
        modal.name_input.value = "Automation Scripting & AI"
        modal.handle_save(None)
        self.assertIsNone(self.page.dialog)

        # 3. Open Course Detail Dialog
        course_home._handle_view_details(created.id)
        self.assertIsNotNone(self.page.dialog)
        self.assertIsInstance(self.page.dialog, CourseDetailDialog)
        detail_dlg: CourseDetailDialog = self.page.dialog
        self.assertEqual(detail_dlg.course.name, "Automation Scripting & AI")
        detail_dlg.close_dialog()
        self.assertIsNone(self.page.dialog)

    def test_02_batch_home_ui_and_creation(self):
        """Verify BatchHome renders, launches BatchFormModal, and links to course."""
        SecurityContext.set_current_user(user_id=2, username="administrator", role=Role.ADMINISTRATOR.value)
        self.page.session.set("user_id", 2)
        self.page.session.set("role", Role.ADMINISTRATOR.value)

        batch_home = BatchHome()
        batch_home._root_page = self.page
        batch_home._page = self.page
        batch_home.did_mount()

        # Find our course
        course = self.course_ctrl.get_course_by_code("TEST-AUTOMATION")
        self.assertIsNotNone(course)

        # Open Batch Modal
        batch_home.handle_new_batch(None)
        self.assertIsNotNone(self.page.dialog)
        self.assertIsInstance(self.page.dialog, BatchFormModal)

        modal: BatchFormModal = self.page.dialog
        modal.course_dropdown.value = str(course.id)
        modal.name_input.value = "Batch Alpha (09:00 - 10:30)"
        modal.code_input.value = "ALPHA"
        modal.timing_input.value = "09:00 AM - 10:30 AM"
        modal.capacity_input.value = "20"
        modal.handle_save(None)

        self.assertIsNone(self.page.dialog)

        # Verify batch exists in DB
        batches = self.batch_ctrl.list_batches_by_course(course.id)
        self.assertGreaterEqual(len(batches), 1)
        self.assertEqual(batches[0].batch_name, "Batch Alpha (09:00 - 10:30)")

    def test_03_real_student_registration_and_workspace(self):
        """Register a real student via StudentFormModal and inspect in StudentWorkspaceDialog."""
        SecurityContext.set_current_user(user_id=1, username="admin", role=Role.ADMIN.value)
        self.page.session.set("user_id", 1)
        self.page.session.set("role", Role.ADMIN.value)

        student_home = StudentHome()
        student_home._root_page = self.page
        student_home._page = self.page
        student_home.did_mount()

        # Open Student Form Modal
        student_home.handle_new_student(None)
        self.assertIsNotNone(self.page.dialog)
        self.assertIsInstance(self.page.dialog, StudentFormModal)

        modal: StudentFormModal = self.page.dialog
        modal.first_name_input.value = "Amit"
        modal.middle_name_input.value = "Suresh"
        modal.last_name_input.value = "Shinde"
        modal.mobile_input.value = "9823456789"
        modal.mother_name_input.value = "Sunita"
        modal.village_input.value = "Chandwad"
        modal.address_input.value = "Near Shivaji Chowk"
        modal.qualification_input.value = "B.Com"
        modal.handle_save(None)

        self.assertIsNone(self.page.dialog)

        # Retrieve student
        st = self.stud_ctrl.get_by_mobile("9823456789")
        self.assertIsNotNone(st)
        self.assertEqual(st.first_name, "Amit")
        self.assertEqual(st.last_name, "Shinde")

        # Open Student Workspace Dialog
        student_home.handle_open_workspace(st.id)
        self.assertIsNotNone(self.page.dialog)
        self.assertIsInstance(self.page.dialog, StudentWorkspaceDialog)
        ws: StudentWorkspaceDialog = self.page.dialog
        self.assertEqual(ws.student_dto.first_name, "Amit")
        ws.close_workspace()
        self.assertIsNone(self.page.dialog)

    def test_04_real_admission_payment_receipt_pipeline(self):
        """End-to-end test: Admission Creation -> Fee Payment -> Receipt PDF -> Workspace -> Reports."""
        SecurityContext.set_current_user(user_id=1, username="admin", role=Role.ADMIN.value)
        self.page.session.set("user_id", 1)
        self.page.session.set("role", Role.ADMIN.value)

        student = self.stud_ctrl.get_by_mobile("9823456789")
        course = self.course_ctrl.get_course_by_code("TEST-AUTOMATION")
        batches = self.batch_ctrl.list_batches_by_course(course.id)
        batch = batches[0]

        adm_home = AdmissionHome()
        adm_home._root_page = self.page
        adm_home._page = self.page
        adm_home.did_mount()

        # 0. Test AdmissionFormModal opening and closing from AdmissionHome
        adm_home.handle_new_admission(None)
        self.assertIsNotNone(self.page.dialog)
        self.assertIsInstance(self.page.dialog, AdmissionFormModal)
        modal: AdmissionFormModal = self.page.dialog
        modal.close_modal()
        self.assertIsNone(self.page.dialog)

        # 1. Create Admission through AdmissionController
        adm_payload = {
            "student_id": student.id,
            "course_id": course.id,
            "batch_id": batch.id,
            "status": "REGISTERED",
            "agreed_fee": 7500.0,
            "discount": 500.0,
            "photo_path": "uploads/photos/dummy.png",
        }
        adm_id = self.adm_ctrl.create_admission(adm_payload)
        self.assertIsNotNone(adm_id)

        # 2. Confirm Admission with Payment & Receipt Generation
        payment_id = self.adm_ctrl.confirm_admission_with_payment(
            admission_id=adm_id,
            amount=3000.0,
            payment_mode="UPI",
            admin_pin="1234",
            collector_name="Hemant Mahale (Sir)",
            transaction_ref="430299887711",
        )
        self.assertGreater(payment_id, 0)

        # Verify receipt exists and has PDF path
        receipt = self.receipt_ctrl.get_receipt_by_payment(payment_id)
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt.amount_paid, 3000.0)
        self.assertIsNotNone(receipt.pdf_path)

        adm = self.adm_ctrl.get_admission(adm_id)

        # 3. Test ReceiptDialog
        receipt_dlg = ReceiptDialog(
            receipt=receipt,
            student_name=adm.student_name,
            candidate_number=adm.admission_number,
            course_name=course.name,
            mobile_number=student.mobile_number,
        )
        self.page.show_dialog(receipt_dlg)
        self.assertIsNotNone(self.page.dialog)
        receipt_dlg.close_modal()
        self.assertIsNone(self.page.dialog)

        # 4. Test 2nd Installment Payment via PaymentDialog
        pay_dlg = PaymentDialog(
            admission_id=adm_id,
            student_name=adm.student_name,
            course_name=course.name,
            candidate_number=adm.admission_number,
            total_fee=7000.0,
            already_paid=3000.0,
            default_amount=2000.0,
            page=self.page,
            current_status="CONFIRMED",
        )
        self.page.show_dialog(pay_dlg)
        self.assertIsNotNone(self.page.dialog)
        pay_dlg.amount_input.value = "2000.0"
        pay_dlg.pin_input.value = "1234"
        pay_dlg.mode_dropdown.value = "CASH"
        pay_dlg.handle_confirm_payment(None)
        # Should pop payment dialog and display receipt dialog
        self.assertIsNotNone(self.page.dialog)
        self.assertIsInstance(self.page.dialog, ReceiptDialog)
        self.page.dialog.close_modal()
        self.assertIsNone(self.page.dialog)

        # Verify updated admission balance
        adm = self.adm_ctrl.get_admission(adm_id)
        self.assertEqual(adm.total_paid, 5000.0)
        self.assertEqual(adm.pending_fee, 2000.0)

        # 5. Open Admission Workspace Dialog
        adm_home.open_admission_workspace(adm_id)
        self.assertIsNotNone(self.page.dialog)
        self.assertIsInstance(self.page.dialog, AdmissionWorkspaceDialog)
        adm_ws: AdmissionWorkspaceDialog = self.page.dialog
        self.assertEqual(adm_ws.admission.id, adm_id)
        adm_ws.close_dialog()
        self.assertIsNone(self.page.dialog)

        # 6. Verify Reports Integration (17 columns, paginated)
        rep_res = self.reports_ctrl.get_admission_fees_report_paginated(search="Amit", page=1, page_size=10)
        self.assertGreaterEqual(rep_res["total_count"], 1)
        matching_row = [r for r in rep_res["rows"] if "Amit" in r["name"]][0]
        self.assertEqual(matching_row["inst1"], 3000.0)
        self.assertEqual(matching_row["inst2"], 2000.0)
        self.assertEqual(matching_row["total_paid"], 5000.0)
        self.assertEqual(matching_row["pending_fees"], 2000.0)

    def test_05_administrator_destructive_operations(self):
        """Verify Administrator can cascade-delete student and admission, while Admin is blocked."""
        # 1. Check Admin is blocked
        SecurityContext.set_current_user(user_id=1, username="admin", role=Role.ADMIN.value)
        student = self.stud_ctrl.get_by_mobile("9823456789")
        self.assertIsNotNone(student)

        with self.assertRaises(ForbiddenError):
            self.stud_ctrl.delete_student(student.id)

        # 2. Check Administrator is authorized
        SecurityContext.set_current_user(user_id=2, username="administrator", role=Role.ADMINISTRATOR.value)
        impact = self.stud_ctrl.get_deletion_impact(student.id)
        self.assertEqual(impact["admissions"], 1)
        self.assertEqual(impact["payments"], 2)
        self.assertEqual(impact["receipts"], 2)
        self.assertEqual(impact["payments_total"], 5000.0)

        # Cascade delete student
        self.stud_ctrl.delete_student(student.id)

        # Verify completely deleted from database (no orphans)
        with self.assertRaises(ValidationError):
            self.stud_ctrl.get_student(student.id)
        self.assertIsNone(self.stud_ctrl.get_by_mobile("9823456789"))
        from modules.payments.controller import PaymentController
        pay_ctrl = PaymentController()
        payments = pay_ctrl.get_payments_for_student(student.id)
        self.assertEqual(len(payments), 0)

        # 3. Clean up test batch and test course so they NEVER leak into database
        course = self.course_ctrl.get_course_by_code("TEST-AUTOMATION") or self.course_ctrl.get_course_by_code("TEST-FULLSTACK")
        with DatabaseEngine.connection() as conn:
            conn.execute("DELETE FROM batches WHERE course_id IN (SELECT id FROM courses WHERE code IN ('TEST-AUTOMATION', 'TEST-FULLSTACK'));")
            conn.execute("DELETE FROM courses WHERE code IN ('TEST-AUTOMATION', 'TEST-FULLSTACK');")
            conn.execute("DELETE FROM activity_logs WHERE entity_type = 'COURSE' AND entity_id IN (SELECT id FROM courses WHERE code IN ('TEST-AUTOMATION', 'TEST-FULLSTACK'));")
        import modules.course.showcase_adapter as showcase_adapter
        showcase_adapter.sync_showcase_web_stores(self.course_ctrl)


if __name__ == "__main__":
    unittest.main()
