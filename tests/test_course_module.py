# tests/test_course_module.py

import os
import sys
import time
import unittest

# Ensure SIMS root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from core.startup.bootstrap import ApplicationBootstrapper
from core.exceptions import ValidationError, ConflictError
from core.security.context import SecurityContext
from modules.course.controller import CourseController
from modules.course.constants import CourseStatus
from modules.course.dto import (
    CourseDTO,
    CourseCreateDTO,
    CourseUpdateDTO,
    CourseFeeChangeDTO,
    CourseSearchResultDTO,
)
from modules.course.views.course_home import CourseHome
from modules.course.views.course_search_dialog import CourseSearchDialog
from modules.admission.controller import AdmissionController
from modules.student.controller import StudentController
from modules.settings.service import SettingsService
from modules.admission.activity_log_repository import ActivityLogRepository
from modules.batch.controller import BatchController


class TestCourseModule(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        bootstrapper = ApplicationBootstrapper()
        bootstrapper._initialize_engines()

    def setUp(self):
        SecurityContext.set_current_user(1, "admin", "ADMINISTRATOR")
        self.course_ctrl = CourseController()
        self.admission_ctrl = AdmissionController()
        self.student_ctrl = StudentController()
        self.batch_ctrl = BatchController()
        self.settings_svc = SettingsService()
        self.activity_repo = ActivityLogRepository()

        # Ensure default PIN is known
        self.test_pin = "1234"

    def test_01_create_valid_course(self):
        """Verify standard course creation with valid metadata."""
        code = f"TEST-CRS-{int(time.time() * 1000) % 100000}"
        payload = {
            "code": code,
            "name": "Test Automated Course",
            "category": "Testing",
            "duration": "1 Month",
            "base_fee": 3500.0,
            "status": "ACTIVE",
            "description": "Integration test created course.",
        }
        course_id = self.course_ctrl.create_course(payload)
        self.assertIsNotNone(course_id)
        self.assertGreater(course_id, 0)

        # Retrieve and verify
        course = self.course_ctrl.get_course(course_id)
        self.assertEqual(course.code, code)
        self.assertEqual(course.name, "Test Automated Course")
        self.assertEqual(course.base_fee, 3500.0)
        self.assertEqual(course.status, CourseStatus.ACTIVE)
        self.assertTrue(course.is_active)

    def test_02_invalid_course_input(self):
        """Verify validation failure on blank code, short name, or invalid status."""
        with self.assertRaises(ValidationError):
            self.course_ctrl.create_course({"code": "", "name": "Valid Name", "base_fee": 1000.0})

        with self.assertRaises(ValidationError):
            self.course_ctrl.create_course({"code": "X", "name": "Valid Name", "base_fee": 1000.0})

        with self.assertRaises(ValidationError):
            self.course_ctrl.create_course({"code": "VALIDCODE", "name": "A", "base_fee": 1000.0})

    def test_03_duplicate_code_rejection(self):
        """Verify case-insensitive unique code collision detection."""
        code = f"DUP-CODE-{int(time.time() * 1000) % 100000}"
        self.course_ctrl.create_course({"code": code, "name": "Original Course", "base_fee": 2000.0})

        # Attempt to insert same code in lowercase
        with self.assertRaises(ConflictError):
            self.course_ctrl.create_course({"code": code.lower(), "name": "Duplicate Course", "base_fee": 2000.0})

    def test_04_negative_fee_rejection(self):
        """Verify rejection of negative base fee."""
        code = f"NEG-FEE-{int(time.time() * 1000) % 100000}"
        with self.assertRaises(ValidationError):
            self.course_ctrl.create_course({"code": code, "name": "Negative Fee Course", "base_fee": -500.0})

    def test_05_zero_fee_allowed(self):
        """Verify ₹0.0 (Free/Sponsored) course is valid."""
        code = f"ZERO-FEE-{int(time.time() * 1000) % 100000}"
        course_id = self.course_ctrl.create_course({"code": code, "name": "Free Workshop", "base_fee": 0.0})
        course = self.course_ctrl.get_course(course_id)
        self.assertEqual(course.base_fee, 0.0)

    def test_06_update_course_metadata(self):
        """Verify update of non-financial descriptors."""
        code = f"UPD-CRS-{int(time.time() * 1000) % 100000}"
        cid = self.course_ctrl.create_course({"code": code, "name": "Initial Name", "base_fee": 4000.0})

        update_payload = {
            "code": code,
            "name": "Updated Name Full",
            "category": "Development",
            "duration": "3 Months",
            "description": "Updated syllabus",
            "status": "ACTIVE",
        }
        self.course_ctrl.update_course(cid, update_payload)

        updated = self.course_ctrl.get_course(cid)
        self.assertEqual(updated.name, "Updated Name Full")
        self.assertEqual(updated.duration, "3 Months")
        self.assertEqual(updated.category, "Development")
        self.assertEqual(updated.base_fee, 4000.0)  # Preserved

    def test_07_duplicate_update_code_conflict(self):
        """Verify update collision with another existing course code."""
        code1 = f"C1-{int(time.time() * 1000) % 100000}"
        code2 = f"C2-{int(time.time() * 1000) % 100000}"
        cid1 = self.course_ctrl.create_course({"code": code1, "name": "Course One", "base_fee": 1000.0})
        cid2 = self.course_ctrl.create_course({"code": code2, "name": "Course Two", "base_fee": 2000.0})

        # Try to rename Course 2 to Code 1
        with self.assertRaises(ConflictError):
            self.course_ctrl.update_course(cid2, {"code": code1, "name": "Course Two Renamed", "base_fee": 2000.0})

    def test_08_course_search(self):
        """Verify search by code and name with minimum query length."""
        code = f"SEARCH-{int(time.time() * 1000) % 100000}"
        self.course_ctrl.create_course({"code": code, "name": "Specialized Quantum Computing", "base_fee": 9000.0})

        # Query too short
        self.assertEqual(self.course_ctrl.search_courses("S"), [])

        # Search by code
        results_code = self.course_ctrl.search_courses(code[:6])
        self.assertTrue(any(r.code == code for r in results_code))

        # Search by partial name
        results_name = self.course_ctrl.search_courses("Quantum")
        self.assertTrue(any(r.code == code for r in results_name))

    def test_09_category_filter_and_listing(self):
        """Verify dynamic category listing and filtered queries."""
        cats = self.course_ctrl.get_categories()
        self.assertIsInstance(cats, list)
        self.assertTrue(len(cats) > 0)

        # Filter by first category
        first_cat = cats[0]
        courses, count = self.course_ctrl.list_courses(category=first_cat)
        self.assertTrue(all(c.category.lower() == first_cat.lower() for c in courses))
        self.assertEqual(len(courses), count)

    def test_10_status_filter_and_toggle(self):
        """Verify status filtering and toggle helper."""
        code = f"TOGGLE-{int(time.time() * 1000) % 100000}"
        cid = self.course_ctrl.create_course({"code": code, "name": "Toggle Test Course", "base_fee": 1000.0, "status": "ACTIVE"})

        # Toggle to INACTIVE
        new_status = self.course_ctrl.toggle_status(cid)
        self.assertEqual(new_status, CourseStatus.INACTIVE)

        inactive_courses, _ = self.course_ctrl.list_courses(status="INACTIVE")
        self.assertTrue(any(c.id == cid for c in inactive_courses))

        # Toggle back to ACTIVE
        new_status2 = self.course_ctrl.toggle_status(cid)
        self.assertEqual(new_status2, CourseStatus.ACTIVE)

    def test_11_pagination_and_count(self):
        """Verify pagination slices and count integrity."""
        total_count = self.course_ctrl.count_courses()
        p1_courses, count = self.course_ctrl.list_courses(limit=5, offset=0)
        self.assertLessEqual(len(p1_courses), 5)
        self.assertEqual(count, total_count)

    def test_12_delete_blocked_by_linked_admissions(self):
        """Verify ConflictError when deleting a course referenced in admission_courses."""
        code = f"ADM-CRS-{int(time.time() * 1000) % 100000}"
        cid = self.course_ctrl.create_course({"code": code, "name": "Admission Linked Course", "base_fee": 2500.0})

        unique_mob = f"988{int(time.time() * 1000) % 10000000:07d}"
        sid = self.student_ctrl.create_student({
            "first_name": "CourseLinked",
            "last_name": "Student",
            "mobile_number": unique_mob,
            "village": "Chandwad",
        })
        self.admission_ctrl.create_admission({
            "course_id": cid,
            "student_id": sid,
            "first_name": "CourseLinked",
            "last_name": "Student",
            "mobile_number": unique_mob,
            "village": "Chandwad",
            "agreed_fee": 2500.0,
            "status": "DRAFT",
        })

        with self.assertRaises(ConflictError):
            self.course_ctrl.delete_course(cid)

    def test_13_delete_blocked_by_linked_batches(self):
        """Verify ConflictError when deleting a course with associated batches."""
        code = f"BATCH-CRS-{int(time.time() * 1000) % 100000}"
        cid = self.course_ctrl.create_course({"code": code, "name": "Batch Linked Course", "base_fee": 2500.0})

        # Create batch under this course
        batch_id = self.batch_ctrl.create_batch({
            "course_id": cid,
            "batch_name": "Morning Cohort A",
            "timing": "08:00 AM - 09:00 AM",
            "max_capacity": 15,
            "status": "OPEN",
        })
        self.assertIsNotNone(batch_id)

        with self.assertRaises(ConflictError):
            self.course_ctrl.delete_course(cid)

    def test_14_delete_unlinked_course_success(self):
        """Verify deletion of a newly created, unlinked course."""
        code = f"DEL-CRS-{int(time.time() * 1000) % 100000}"
        cid = self.course_ctrl.create_course({"code": code, "name": "Temporary Course", "base_fee": 1000.0})
        self.course_ctrl.delete_course(cid)

        with self.assertRaises(ValidationError):
            self.course_ctrl.get_course(cid)

    def test_15_valid_fee_change_with_admin_pin(self):
        """Verify authorized fee revision updates base_fee and records fee history."""
        code = f"FEE-CHG-{int(time.time() * 1000) % 100000}"
        cid = self.course_ctrl.create_course({"code": code, "name": "Fee Revision Course", "base_fee": 4000.0})

        payload = {
            "new_fee": 4800.0,
            "reason": "Annual tariff adjustment 2026",
            "admin_pin": self.test_pin,
        }
        self.course_ctrl.change_institute_fee(
            course_id=cid,
            raw_data=payload,
            user_id=1,
            username="admin",
        )

        updated = self.course_ctrl.get_course(cid)
        self.assertEqual(updated.base_fee, 4800.0)

        # Check fee history
        history = self.course_ctrl.get_fee_history(cid)
        self.assertGreaterEqual(len(history), 1)
        latest = history[0]
        self.assertEqual(latest.old_fee, 4000.0)
        self.assertEqual(latest.new_fee, 4800.0)
        self.assertEqual(latest.reason, "Annual tariff adjustment 2026")
        self.assertEqual(latest.changed_by_username, "admin")

    def test_16_invalid_pin_rejection(self):
        """Verify fee change fails and rejects when wrong PIN is supplied."""
        code = f"BAD-PIN-{int(time.time() * 1000) % 100000}"
        cid = self.course_ctrl.create_course({"code": code, "name": "Bad PIN Course", "base_fee": 3000.0})

        payload = {
            "new_fee": 3500.0,
            "reason": "Unauthorized attempt",
            "admin_pin": "9999",  # Invalid PIN
        }
        with self.assertRaises(ValidationError):
            self.course_ctrl.change_institute_fee(
                course_id=cid,
                raw_data=payload,
                user_id=1,
                username="admin",
            )

        # Fee must remain unchanged
        course = self.course_ctrl.get_course(cid)
        self.assertEqual(course.base_fee, 3000.0)

    def test_17_invalid_reason_rejection(self):
        """Verify fee change rejected if reason is blank or too short."""
        code = f"NO-RSN-{int(time.time() * 1000) % 100000}"
        cid = self.course_ctrl.create_course({"code": code, "name": "No Reason Course", "base_fee": 3000.0})

        with self.assertRaises(ValidationError):
            self.course_ctrl.change_institute_fee(
                course_id=cid,
                raw_data={"new_fee": 3500.0, "reason": "ab", "admin_pin": self.test_pin},
            )

    def test_18_same_fee_rejection_no_op(self):
        """Verify fee change rejected if new_fee equals current base_fee."""
        code = f"SAME-FEE-{int(time.time() * 1000) % 100000}"
        cid = self.course_ctrl.create_course({"code": code, "name": "Same Fee Course", "base_fee": 5000.0})

        with self.assertRaises(ValidationError):
            self.course_ctrl.change_institute_fee(
                course_id=cid,
                raw_data={"new_fee": 5000.0, "reason": "No real change", "admin_pin": self.test_pin},
            )

    def test_19_historical_agreed_fee_invariant(self):
        """
        CRITICAL INVARIANT: Changing course base_fee NEVER alters past admissions.
        """
        code = f"SNAP-{int(time.time() * 1000) % 100000}"
        cid = self.course_ctrl.create_course({"code": code, "name": "Snapshot Test Course", "base_fee": 6000.0})

        # Create student and admission snapshotting base_fee = 6000.0
        unique_mob = f"987{int(time.time() * 1000) % 10000000:07d}"
        sid = self.student_ctrl.create_student({
            "first_name": "FeeSnapshot",
            "last_name": "Student",
            "mobile_number": unique_mob,
            "village": "Chandwad",
        })

        adm_id = self.admission_ctrl.create_admission({
            "course_id": cid,
            "student_id": sid,
            "first_name": "FeeSnapshot",
            "last_name": "Student",
            "mobile_number": unique_mob,
            "village": "Chandwad",
            "agreed_fee": 6000.0,
            "discount": 500.0,
            "status": "DRAFT",
        })
        self.assertIsNotNone(adm_id)

        # Now revise Course Institute Fee to ₹7,500
        self.course_ctrl.change_institute_fee(
            course_id=cid,
            raw_data={"new_fee": 7500.0, "reason": "Fee increase for 2027", "admin_pin": self.test_pin},
            username="admin",
        )

        # Verify course base_fee changed to 7500
        updated_course = self.course_ctrl.get_course(cid)
        self.assertEqual(updated_course.base_fee, 7500.0)

        # Verify historical admission agreed_fee is STILL 6000.0 and discount is 500.0
        adm = self.admission_ctrl.get_admission(adm_id)
        self.assertEqual(adm.agreed_fee, 6000.0)
        self.assertEqual(adm.discount, 500.0)
        self.assertEqual(adm.final_fee, 5500.0)

    def test_20_activity_log_recorded_on_fee_change(self):
        """Verify activity_logs receives a COURSE / FEE_CHANGED entry."""
        code = f"ACT-LOG-{int(time.time() * 1000) % 100000}"
        cid = self.course_ctrl.create_course({"code": code, "name": "Activity Log Test", "base_fee": 2000.0})

        self.course_ctrl.change_institute_fee(
            course_id=cid,
            raw_data={"new_fee": 2800.0, "reason": "Inflation adjustment", "admin_pin": self.test_pin},
            user_id=1,
            username="admin",
        )

        with self.course_ctrl.service.unit_of_work():
            logs = self.activity_repo.get_logs_for_entity("COURSE", cid)
        self.assertTrue(any(l["action"] == "FEE_CHANGED" for l in logs))

    def test_21_operational_summary_metrics(self):
        """Verify get_operational_summary accurately counts batches and enrollments."""
        code = f"OPS-SUM-{int(time.time() * 1000) % 100000}"
        cid = self.course_ctrl.create_course({"code": code, "name": "Ops Summary Course", "base_fee": 1000.0})

        summary_empty = self.course_ctrl.get_operational_summary(cid)
        self.assertEqual(summary_empty.batch_count, 0)
        self.assertEqual(summary_empty.total_admissions_count, 0)

        # Add a batch
        self.batch_ctrl.create_batch({
            "course_id": cid,
            "batch_name": "Evening Batch 1",
            "timing": "05:00 PM - 06:00 PM",
            "max_capacity": 20,
            "status": "OPEN",
        })

        summary_with_batch = self.course_ctrl.get_operational_summary(cid)
        self.assertEqual(summary_with_batch.batch_count, 1)
        self.assertEqual(summary_with_batch.active_batch_count, 1)

    def test_22_overall_summary_kpis(self):
        """Verify get_overall_summary returns total, active, inactive, and enrollments."""
        overall = self.course_ctrl.get_overall_summary()
        self.assertIn("total_courses", overall)
        self.assertIn("active_courses", overall)
        self.assertIn("inactive_courses", overall)
        self.assertIn("total_enrollments", overall)
        self.assertGreater(overall["total_courses"], 0)

    def test_23_course_search_dialog_compatibility(self):
        """Verify CourseSearchDialog initializes and returns valid CourseSearchResultDTO."""
        selected_results = []
        dialog = CourseSearchDialog(
            controller=self.course_ctrl,
            on_course_selected=lambda dto: selected_results.append(dto),
        )
        self.assertIsNotNone(dialog)
        self.assertEqual(dialog.search_input.label, "Search by Code or Name")

    def test_24_course_home_view_mounting(self):
        """Verify CourseHome mounts without error and displays cards."""
        view = CourseHome()
        self.assertIsNotNone(view)
        self.assertEqual(len(view.controls), 6)
        view.refresh_data()
        self.assertGreater(len(view.cards_grid.controls), 0)


if __name__ == "__main__":
    unittest.main()
