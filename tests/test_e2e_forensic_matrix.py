# tests/test_e2e_forensic_matrix.py

import os
import sys
import time
import unittest
from pathlib import Path

# Ensure SIMS root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

import flet as ft
from core.startup.bootstrap import ApplicationBootstrapper
from ui.screens.dashboard import DashboardScreen, DashboardHome
from modules.student.views.student_home import StudentHome
from modules.admission.views.admission_home import AdmissionHome
from modules.course.views.course_home import CourseHome
from modules.reports.views.reports_home import ReportsHome
from modules.settings.views.settings_home import SettingsHome
from modules.admission.views.admission_form_modal import AdmissionFormModal
from modules.admission.views.admission_workspace_dialog import AdmissionWorkspaceDialog
from modules.admission.views.payment_dialog import PaymentDialog
from modules.admission.views.receipt_dialog import ReceiptDialog
from modules.student.views.student_workspace_dialog import StudentWorkspaceDialog
from modules.student.controller import StudentController
from modules.admission.controller import AdmissionController
from modules.reports.controller import ReportsController
from modules.settings.controller import SettingsController
from modules.course.controller import CourseController
from modules.receipts.controller import ReceiptController
from modules.admission.constants import AdmissionStatus
from shared.utils.formatting import format_whatsapp_url, format_file_size, format_title_case


class TestE2EForensicMatrix(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Initialize Application Engine, Logging, and Database
        bootstrapper = ApplicationBootstrapper()
        bootstrapper._initialize_engines()

    def setUp(self):
        self.student_ctrl = StudentController()
        self.admission_ctrl = AdmissionController()
        self.reports_ctrl = ReportsController()
        self.settings_ctrl = SettingsController()
        self.course_ctrl = CourseController()
        self.receipt_ctrl = ReceiptController()

    # ----------------------------------------------------
    # MATRIX A: DASHBOARD ROUTING
    # ----------------------------------------------------
    def test_A_dashboard_routing(self):
        """Verify that /dashboard does NOT mount ReportsHome and correct views mount for each route."""
        # Create a mock page and navigation callback
        class MockPage:
            def __init__(self):
                self.route = "/dashboard"
                self.session = {}

        page = MockPage()
        current_nav = []
        dashboard = DashboardScreen(page=page, on_route_request=lambda r: current_nav.append(r))

        # 1. Mount /dashboard
        dashboard.mount_view("/dashboard")
        mounted = dashboard.content_host.content
        self.assertNotIsInstance(mounted, ReportsHome, "REGRESSION: /dashboard must NEVER mount ReportsHome!")
        self.assertIsInstance(mounted, DashboardHome)


        # 2. Mount /students
        dashboard.mount_view("/students")
        self.assertIsInstance(dashboard.content_host.content, StudentHome)

        # 3. Mount /admissions
        dashboard.mount_view("/admissions")
        self.assertIsInstance(dashboard.content_host.content, AdmissionHome)

        # 4. Mount /courses
        dashboard.mount_view("/courses")
        self.assertIsInstance(dashboard.content_host.content, CourseHome)

        # 5. Mount /fees
        dashboard.mount_view("/fees")
        self.assertIsInstance(dashboard.content_host.content, ReportsHome)

        # 6. Mount /settings
        dashboard.mount_view("/settings")
        self.assertIsInstance(dashboard.content_host.content, SettingsHome)

    # ----------------------------------------------------
    # MATRIX B: ADMISSION WORKFLOW
    # ----------------------------------------------------
    def test_B_admission_workflow_and_modals(self):
        """Verify New Admission constructor, search, draft, confirm, payment, receipt."""
        # 1. Test AdmissionFormModal instantiation (no constructor exception)
        modal = AdmissionFormModal(on_saved=lambda: None)
        self.assertIsNotNone(modal)
        self.assertEqual(modal.content.width, 960)

        # 2. Create Student Master record
        ts = int(time.time() * 1000) % 10000000
        unique_mob = f"976{ts:07d}"
        s_payload = {
            "first_name": "Saurabh",
            "middle_name": "Vijay",
            "last_name": "Deshmukh",
            "mother_name": "Kavita",
            "dob": "2002-08-20",
            "gender": "MALE",
            "mobile_number": unique_mob,
            "aadhaar_number": f"223344{ts % 1000000:06d}",
            "village": "Chandwad",
            "address": "Near Market Yard, Chandwad",
            "qualification": "12th Pass",
            "blood_group": "A+",
        }
        student_id = self.student_ctrl.create_student(s_payload)
        self.assertIsNotNone(student_id)

        # 3. Test Existing Student Auto-fill in AdmissionFormModal
        modal._select_existing_student(student_id)
        self.assertEqual(modal.first_name_input.value, "Saurabh")
        self.assertEqual(modal.middle_name_input.value, "Vijay")
        self.assertEqual(modal.last_name_input.value, "Deshmukh")
        self.assertEqual(modal.mother_name_input.value, "Kavita")
        self.assertEqual(modal.village_input.value, "Chandwad")
        self.assertEqual(modal.banner_text.value, "✓ Student information auto-filled")

        # 4. Create Draft Admission
        courses, _ = self.course_ctrl.list_courses()
        self.assertTrue(len(courses) > 0)
        c1 = courses[0]

        adm_payload = {
            "course_id": c1.id,
            "student_id": student_id,
            "first_name": "Saurabh",
            "last_name": "Deshmukh",
            "mother_name": "Kavita",
            "dob": "2002-08-20",
            "gender": "MALE",
            "mobile_number": unique_mob,
            "aadhaar_number": f"223344{ts % 1000000:06d}",
            "village": "Chandwad",
            "qualification": "12th Pass",
            "photo_path": "uploads/photos/dummy_photo.jpg",
            "agreed_fee": c1.base_fee,
            "discount": 0.0,
            "status": AdmissionStatus.REGISTERED.value,
        }
        adm_id = self.admission_ctrl.create_admission(adm_payload)
        self.assertIsNotNone(adm_id)

        # 5. Confirm Admission & Collect Payment (>= ₹500)
        pay_id = self.admission_ctrl.confirm_admission_with_payment(
            admission_id=adm_id,
            amount=1000.0,
            payment_mode="CASH",
            admin_pin="1234",
            collector_name="Hemant Mahale (Sir)",
        )
        self.assertIsNotNone(pay_id)

        # 6. Verify PaymentDialog and ReceiptDialog instantiation without constructor mismatch
        adm = self.admission_ctrl.get_admission(adm_id)
        p_dialog = PaymentDialog(
            admission_id=adm_id,
            student_name=adm.student_name,
            course_name=adm.course_name,
            candidate_number=adm.admission_number,
            total_fee=adm.final_fee,
            already_paid=adm.total_paid,
            on_payment_success=lambda pid: None,
            on_payment_completed=lambda pid: None,
        )
        self.assertIsNotNone(p_dialog)

        receipts = self.receipt_ctrl.get_receipts_for_admission(adm_id)
        self.assertTrue(len(receipts) > 0)
        r_dialog = ReceiptDialog(
            receipt=receipts[-1],
            student_name=adm.student_name,
            candidate_number=adm.admission_number,
            course_name=adm.course_name,
            mobile_number=adm.mobile_number,
        )
        self.assertIsNotNone(r_dialog)

    # ----------------------------------------------------
    # MATRIX C: MULTIPLE ADMISSIONS (STUDENT != ADMISSION)
    # ----------------------------------------------------
    def test_C_multiple_admissions_for_one_student(self):
        """Verify one student master profile can have 2 or 3 separate admissions across courses."""
        ts = int(time.time() * 1000) % 10000000
        unique_mob = f"982{ts:07d}"
        s_payload = {
            "first_name": "Pooja",
            "middle_name": "Ramesh",
            "last_name": "Shinde",
            "mother_name": "Sunita",
            "dob": "2003-11-12",
            "gender": "FEMALE",
            "mobile_number": unique_mob,
            "aadhaar_number": f"334455{ts % 1000000:06d}",
            "village": "Chandwad",
            "qualification": "B.Com",
        }
        student_id = self.student_ctrl.create_student(s_payload)
        self.assertIsNotNone(student_id)

        courses, _ = self.course_ctrl.list_courses()
        self.assertGreaterEqual(len(courses), 2)
        c1, c2 = courses[0], courses[1]

        # Admission 1
        a1_payload = {
            "course_id": c1.id,
            "student_id": student_id,
            "first_name": "Pooja",
            "last_name": "Shinde",
            "dob": "2003-11-12",
            "gender": "FEMALE",
            "mobile_number": unique_mob,
            "aadhaar_number": f"334455{ts % 1000000:06d}",
            "agreed_fee": c1.base_fee,
            "status": AdmissionStatus.DRAFT.value,
        }
        adm1_id = self.admission_ctrl.create_admission(a1_payload)
        self.assertIsNotNone(adm1_id)

        # Admission 2 for the SAME student
        a2_payload = {
            "course_id": c2.id,
            "student_id": student_id,
            "first_name": "Pooja",
            "last_name": "Shinde",
            "dob": "2003-11-12",
            "gender": "FEMALE",
            "mobile_number": unique_mob,
            "aadhaar_number": f"334455{ts % 1000000:06d}",
            "agreed_fee": c2.base_fee,
            "status": AdmissionStatus.DRAFT.value,
        }
        adm2_id = self.admission_ctrl.create_admission(a2_payload)
        self.assertIsNotNone(adm2_id)
        self.assertNotEqual(adm1_id, adm2_id)

        # Check that Student Master is still ONE record and contains both admissions
        ws = self.student_ctrl.get_student_workspace(student_id)
        self.assertEqual(ws.student.id, student_id)
        self.assertEqual(len(ws.admissions), 2)

    # ----------------------------------------------------
    # MATRIX D: STUDENT WORKSPACE & TRANSACTION INTEGRITY
    # ----------------------------------------------------
    def test_D_student_workspace_notes_and_friends(self):
        """Verify notes, friends, document operations execute within unit_of_work without transaction errors."""
        ts = int(time.time() * 1000) % 10000000
        s1_id = self.student_ctrl.create_student({
            "first_name": "Nikhil",
            "last_name": "Ahire",
            "mobile_number": f"973{ts:07d}",
            "village": "Chandwad",
        })
        s2_id = self.student_ctrl.create_student({
            "first_name": "Prathamesh",
            "last_name": "Borse",
            "mobile_number": f"974{ts:07d}",
            "village": "Chandwad",
        })

        # 1. Add Internal Note
        self.student_ctrl.add_student_note(s1_id, "Student requested evening batch timings.", actor_name="ADMIN")
        notes = self.student_ctrl.get_student_notes(s1_id)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["details"], "Student requested evening batch timings.")

        # 2. Add and Remove Village Friend
        self.student_ctrl.add_student_friend(s1_id, s2_id)
        ws1 = self.student_ctrl.get_student_workspace(s1_id)
        self.assertEqual(len(ws1.friends), 1)
        self.assertEqual(ws1.friends[0]["id"], s2_id)

        self.student_ctrl.remove_student_friend(s1_id, s2_id)
        ws1_after = self.student_ctrl.get_student_workspace(s1_id)
        self.assertEqual(len(ws1_after.friends), 0)

        # 3. Test Student Workspace Dialog instantiation
        dialog = StudentWorkspaceDialog(controller=self.student_ctrl, student_id=s1_id)
        self.assertIsNotNone(dialog)


if __name__ == "__main__":
    unittest.main()
