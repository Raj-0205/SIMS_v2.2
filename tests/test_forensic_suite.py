# tests/test_forensic_suite.py

import os
import sys
import time
import unittest

# Ensure SIMS root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from core.startup.bootstrap import ApplicationBootstrapper
from shared.utils.formatting import format_title_case, normalize_mobile, format_whatsapp_number, format_whatsapp_url, format_file_size
from modules.student.controller import StudentController
from modules.admission.controller import AdmissionController
from modules.reports.controller import ReportsController
from modules.settings.controller import SettingsController
from modules.course.controller import CourseController
from modules.admission.constants import AdmissionStatus


class TestForensicSuite(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Initialize Application Environment and Database
        bootstrapper = ApplicationBootstrapper()
        bootstrapper._initialize_engines()

    def setUp(self):
        self.student_ctrl = StudentController()
        self.admission_ctrl = AdmissionController()
        self.reports_ctrl = ReportsController()
        self.settings_ctrl = SettingsController()
        self.course_ctrl = CourseController()

    def test_01_formatters(self):
        """Verify title case and mobile number normalization."""
        self.assertEqual(format_title_case("rahul shashikant patil"), "Rahul Shashikant Patil")
        self.assertEqual(format_title_case("near jio tower, sawargaon road"), "Near Jio Tower, Sawargaon Road")
        self.assertEqual(normalize_mobile("919876543210"), "9876543210")
        self.assertEqual(format_whatsapp_number("9876543210"), "919876543210")
        self.assertEqual(format_whatsapp_url("9876543210"), "https://wa.me/919876543210")
        self.assertEqual(format_file_size(102400), "100.0 KB")

    def test_02_student_not_equal_admission(self):
        """Verify student master profile separation and multi-admission capability."""
        unique_mob = f"998{int(time.time()) % 10000000:07d}"
        s_payload = {
            "first_name": "Forensic",
            "middle_name": "Test",
            "last_name": "Student",
            "mother_name": "Sunita",
            "dob": "2004-05-15",
            "gender": "MALE",
            "mobile_number": unique_mob,
            "aadhaar_number": f"112233{int(time.time()) % 1000000:06d}",
            "village": "Chandwad",
            "address": "College Road",
            "qualification": "12th Pass",
            "blood_group": "B+",
        }
        student_id = self.student_ctrl.create_student(s_payload)
        self.assertIsNotNone(student_id)

        # Retrieve student
        student = self.student_ctrl.get_student(student_id)
        self.assertEqual(student.first_name, "Forensic")
        self.assertEqual(student.mobile_number, unique_mob)

        # Get Course ID
        courses, _ = self.course_ctrl.list_courses()
        self.assertTrue(len(courses) > 0)
        c1 = courses[0]

        # Create 1st Admission for Student
        a1_payload = {
            "course_id": c1.id,
            "student_id": student_id,
            "first_name": "Forensic",
            "last_name": "Student",
            "mother_name": "Sunita",
            "dob": "2004-05-15",
            "gender": "MALE",
            "mobile_number": unique_mob,
            "village": "Chandwad",
            "qualification": "12th Pass",
            "agreed_fee": c1.base_fee,
            "discount": 0.0,
            "status": AdmissionStatus.DRAFT.value,
        }
        adm1_id = self.admission_ctrl.create_admission(a1_payload)
        self.assertIsNotNone(adm1_id)

        # Create 2nd Admission for SAME Student (e.g. 2nd Course) if another course exists
        if len(courses) > 1:
            c2 = courses[1]
            a2_payload = dict(a1_payload)
            a2_payload["course_id"] = c2.id
            a2_payload["agreed_fee"] = c2.base_fee
            adm2_id = self.admission_ctrl.create_admission(a2_payload)
            self.assertIsNotNone(adm2_id)
            self.assertNotEqual(adm1_id, adm2_id)

        # Check Student Workspace multi-admission array
        ws = self.student_ctrl.get_student_workspace(student_id)
        self.assertGreaterEqual(len(ws.admissions), 1)
        self.assertEqual(ws.student.id, student_id)

    def test_03_payment_and_installment_flow(self):
        """Verify payment collection and multi-installment receipts."""
        unique_mob = f"987{int(time.time() + 1) % 10000000:07d}"
        courses, _ = self.course_ctrl.list_courses()
        c1 = courses[0]

        a_payload = {
            "course_id": c1.id,
            "first_name": "Payment",
            "last_name": "Tester",
            "mother_name": "Rekha",
            "dob": "2003-01-01",
            "gender": "FEMALE",
            "mobile_number": unique_mob,
            "aadhaar_number": "998877665544",
            "village": "Chandwad",
            "qualification": "HSC",
            "photo_path": "uploads/photos/dummy.png",
            "agreed_fee": 5000.0,
            "discount": 500.0,
            "status": AdmissionStatus.REGISTERED.value,
        }
        adm_id = self.admission_ctrl.create_admission(a_payload)
        adm = self.admission_ctrl.get_admission(adm_id)
        self.assertEqual(adm.final_fee, 4500.0)

        # Collect 1st Payment
        pay1_id = self.admission_ctrl.confirm_admission_with_payment(
            admission_id=adm_id,
            amount=1500.0,
            payment_mode="CASH",
            admin_pin="1234",
            collector_name="Hemant Mahale (Sir)",
        )
        self.assertIsNotNone(pay1_id)

        # Check Admission Workspace
        aws = self.admission_ctrl.get_admission_workspace(adm_id)
        self.assertEqual(aws.admission.total_paid, 1500.0)
        self.assertEqual(aws.admission.pending_amount, 3000.0)
        self.assertEqual(len(aws.payments), 1)

    def test_04_reports_and_csv(self):
        """Verify report generation and 17-column CSV output."""
        rpt = self.reports_ctrl.get_admission_fees_report()
        self.assertIsInstance(rpt, list)
        if rpt:
            first = rpt[0]
            expected_keys = [
                "sr_no", "course_name", "admission_date", "admission_id", "name", "mob_no",
                "admission_status", "total_fees", "inst1", "inst2", "inst3", "inst4",
                "total_paid", "pending_fees", "address", "friend_name", "friend_mobile"
            ]
            for k in expected_keys:
                self.assertIn(k, first)

            csv_file = self.reports_ctrl.export_fees_report_csv(rpt)
            self.assertTrue(csv_file.exists())

    def test_05_institution_master(self):
        """Verify school/college educational institution master operations."""
        insts = self.settings_ctrl.list_institutions()
        self.assertIsInstance(insts, list)
        self.assertGreater(len(insts), 0)


if __name__ == "__main__":
    unittest.main()
