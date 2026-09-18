# tests/test_admission_identity_duplicate.py

import time
import unittest
from core.startup.bootstrap import ApplicationBootstrapper
from core.exceptions import ValidationError, ConflictError
from modules.admission.controller import AdmissionController
from modules.admission.constants import AdmissionStatus
from modules.admission.dto import DuplicateCheckDTO
from modules.student.controller import StudentController
from modules.course.controller import CourseController
from modules.payments.controller import PaymentController


class TestAdmissionIdentityDuplicate(unittest.TestCase):
    """
    Comprehensive test suite verifying canonical identity matching, contact data modeling,
    multi-case admission classification, and duplicate prevention invariants.
    Strictly adheres to Directive Point 14 (Cases 1-13).
    """

    @classmethod
    def setUpClass(cls):
        bootstrapper = ApplicationBootstrapper()
        bootstrapper._initialize_engines()

        cls.admission_ctrl = AdmissionController()
        cls.student_ctrl = StudentController()
        cls.course_ctrl = CourseController()
        cls.payment_ctrl = PaymentController()

        courses, _ = cls.course_ctrl.list_courses(status="ACTIVE")
        if len(courses) < 2:
            cls.c1_id = cls.course_ctrl.create_course({"name": "Test Course Alpha", "code": "TCA", "base_fee": 5000.0})
            cls.c2_id = cls.course_ctrl.create_course({"name": "Test Course Beta", "code": "TCB", "base_fee": 6000.0})
        else:
            cls.c1_id = courses[0].id
            cls.c2_id = courses[1].id

    def _unique_mobiles(self):
        ts = int(time.time() * 1000) % 10000000
        m1 = f"982{ts:07d}"
        m2 = f"983{(ts + 1):07d}"
        return m1, m2

    def test_01_same_normalized_name_same_mobile_matches_identity(self):
        """Rule 1: Same normalized full name + primary mobile matches -> Identity match."""
        m1, m2 = self._unique_mobiles()
        s_id = self.student_ctrl.create_student({
            "first_name": "Rohan",
            "middle_name": "Ramesh",
            "last_name": "Gupta",
            "mobile_number": m1,
            "secondary_mobile": m2,
            "village": "Chandwad",
        })
        self.assertIsNotNone(s_id)

        res = self.admission_ctrl.check_duplicate({
            "full_name": "Rohan Ramesh Gupta",
            "contact1": m1,
            "contact2": "9841112233",
            "course_id": self.c1_id,
        })
        self.assertTrue(res.is_identity_match)
        self.assertEqual(res.existing_student_id, s_id)
        self.assertEqual(res.matched_mobile, m1)

    def test_02_same_normalized_name_second_mobile_matches_identity(self):
        """Rule 2: Same normalized full name + second mobile matches -> Identity match."""
        m1, m2 = self._unique_mobiles()
        s_id = self.student_ctrl.create_student({
            "first_name": "Pooja",
            "middle_name": "Sanjay",
            "last_name": "Shinde",
            "mobile_number": m1,
            "secondary_mobile": m2,
            "village": "Chandwad",
        })
        self.assertIsNotNone(s_id)

        # Query where contact 1 does not match, but contact 2 matches student secondary mobile
        m_other = f"985{int(time.time() * 1000) % 10000000:07d}"
        res = self.admission_ctrl.check_duplicate({
            "full_name": "Pooja Sanjay Shinde",
            "contact1": m_other,
            "contact2": m2,
            "course_id": self.c1_id,
        })
        self.assertTrue(res.is_identity_match)
        self.assertEqual(res.existing_student_id, s_id)
        self.assertEqual(res.matched_mobile, m2)

    def test_03_same_normalized_name_no_mobile_matches_no_identity_match(self):
        """Rule 3: Same normalized full name + no mobile matches -> No identity match."""
        m1, m2 = self._unique_mobiles()
        s_id = self.student_ctrl.create_student({
            "first_name": "Nikhil",
            "middle_name": "Arun",
            "last_name": "Jadhav",
            "mobile_number": m1,
            "secondary_mobile": m2,
            "village": "Chandwad",
        })
        self.assertIsNotNone(s_id)

        # Completely different contacts
        res = self.admission_ctrl.check_duplicate({
            "full_name": "Nikhil Arun Jadhav",
            "contact1": "9890001122",
            "contact2": "9890003344",
            "course_id": self.c1_id,
        })
        self.assertFalse(res.is_identity_match)
        self.assertEqual(res.classification, "NONE")

    def test_04_different_name_same_mobile_no_identity_match_shared_contact(self):
        """Rule 4: Different name + same mobile -> No identity match (shared family contact allowed)."""
        m1, m2 = self._unique_mobiles()
        s_id = self.student_ctrl.create_student({
            "first_name": "Vikas",
            "middle_name": "Dinkar",
            "last_name": "More",
            "mobile_number": m1,
            "secondary_mobile": m2,
            "village": "Chandwad",
        })
        self.assertIsNotNone(s_id)

        # Sibling or family member with different first name sharing same parent numbers
        res = self.admission_ctrl.check_duplicate({
            "full_name": "Sneha Dinkar More",
            "contact1": m1,
            "contact2": m2,
            "course_id": self.c1_id,
        })
        self.assertFalse(res.is_identity_match)
        self.assertEqual(res.classification, "NONE")

    def test_05_different_name_different_mobile_no_match(self):
        """Rule 5: Different name + different mobile -> No match."""
        m1, m2 = self._unique_mobiles()
        res = self.admission_ctrl.check_duplicate({
            "full_name": "Completely Unseen Student Name",
            "contact1": m1,
            "contact2": m2,
            "course_id": self.c1_id,
        })
        self.assertFalse(res.is_identity_match)
        self.assertEqual(res.classification, "NONE")

    def test_06_different_spacing_capitalization_normalizes_and_matches(self):
        """Rule 6: Different spacing and capitalization normalizes and matches identity."""
        m1, m2 = self._unique_mobiles()
        s_id = self.student_ctrl.create_student({
            "first_name": "Aniket",
            "middle_name": "Kishor",
            "last_name": "Wagh",
            "mobile_number": m1,
            "secondary_mobile": m2,
            "village": "Chandwad",
        })
        self.assertIsNotNone(s_id)

        # Messy input with irregular casing and extra spaces
        res = self.admission_ctrl.check_duplicate({
            "full_name": "   ANIKET    kishor   WAGH  ",
            "contact1": f" +91 {m1[:5]}-{m1[5:]} ",
            "contact2": m2,
            "course_id": self.c1_id,
        })
        self.assertTrue(res.is_identity_match)
        self.assertEqual(res.existing_student_id, s_id)

    def test_07_only_one_mobile_validation_failure(self):
        """Rule 7: Only one mobile provided during inline admission -> Validation failure."""
        m1, _ = self._unique_mobiles()
        with self.assertRaises(ValidationError) as ctx:
            self.admission_ctrl.create_admission({
                "course_id": self.c1_id,
                "first_name": "Single",
                "last_name": "Mobile",
                "mobile_number": m1,
                "secondary_mobile": None,
                "village": "Chandwad",
            })
        self.assertIn("Both Contact 1 (primary) and Contact 2 (secondary)", str(ctx.exception))

    def test_08_two_identical_mobiles_validation_failure(self):
        """Rule 8: Two identical mobiles (Contact 1 == Contact 2) -> Validation failure."""
        m1, _ = self._unique_mobiles()
        with self.assertRaises(ValidationError) as ctx:
            self.admission_ctrl.create_admission({
                "course_id": self.c1_id,
                "first_name": "Identical",
                "last_name": "Mobile",
                "mobile_number": m1,
                "secondary_mobile": m1,
                "village": "Chandwad",
            })
        self.assertIn("Secondary mobile cannot be identical to primary", str(ctx.exception))

    def test_09_invalid_mobile_validation_failure(self):
        """Rule 9: Invalid mobile format -> Validation failure."""
        m1, _ = self._unique_mobiles()
        # Invalid primary mobile (too short / starts with invalid digit)
        with self.assertRaises(ValidationError) as ctx1:
            self.admission_ctrl.create_admission({
                "course_id": self.c1_id,
                "first_name": "Invalid",
                "last_name": "Mobile",
                "mobile_number": "1234567890",
                "secondary_mobile": m1,
                "village": "Chandwad",
            })
        self.assertIn("Primary mobile must be a valid 10-digit Indian mobile number", str(ctx1.exception))

        # Invalid secondary mobile
        with self.assertRaises(ValidationError) as ctx2:
            self.admission_ctrl.create_admission({
                "course_id": self.c1_id,
                "first_name": "Invalid",
                "last_name": "Mobile",
                "mobile_number": m1,
                "secondary_mobile": "555123",
                "village": "Chandwad",
            })
        self.assertIn("Secondary mobile must be a valid 10-digit Indian mobile number", str(ctx2.exception))

    def test_10_same_student_same_active_course_blocked(self):
        """Rule 10: Same student + same active course -> Duplicate active blocked."""
        m1, m2 = self._unique_mobiles()
        # Create student and confirm admission in course 1
        adm_id = self.admission_ctrl.create_admission({
            "course_id": self.c1_id,
            "first_name": "Active",
            "last_name": "Enrolled",
            "mobile_number": m1,
            "secondary_mobile": m2,
            "village": "Chandwad",
            "photo_path": "uploads/photos/dummy.png",
            "status": AdmissionStatus.CONFIRMED.value,
            "initial_payment_amount": 500.0,
            "payment_mode": "CASH",
            "admin_pin": "1234",
        })
        self.assertIsNotNone(adm_id)

        # Check duplicate for the same course
        res = self.admission_ctrl.check_duplicate({
            "full_name": "Active Enrolled",
            "contact1": m1,
            "contact2": m2,
            "course_id": self.c1_id,
        })
        self.assertTrue(res.is_identity_match)
        self.assertEqual(res.classification, "DUPLICATE_ACTIVE")
        self.assertFalse(res.can_create_admission)

        # Creation attempt must be blocked by ConflictError
        with self.assertRaises(ConflictError) as ctx:
            self.admission_ctrl.create_admission({
                "course_id": self.c1_id,
                "first_name": "Active",
                "last_name": "Enrolled",
                "mobile_number": m1,
                "secondary_mobile": m2,
                "village": "Chandwad",
                "status": AdmissionStatus.REGISTERED.value,
            })
        self.assertIn("already has an active", str(ctx.exception))

    def test_11_same_student_different_course_allowed(self):
        """Rule 11: Same student + different course -> New admission allowed."""
        m1, m2 = self._unique_mobiles()
        adm1_id = self.admission_ctrl.create_admission({
            "course_id": self.c1_id,
            "first_name": "MultiCourse",
            "last_name": "Student",
            "mobile_number": m1,
            "secondary_mobile": m2,
            "village": "Chandwad",
            "photo_path": "uploads/photos/dummy.png",
            "status": AdmissionStatus.CONFIRMED.value,
            "initial_payment_amount": 500.0,
            "payment_mode": "CASH",
            "admin_pin": "1234",
        })
        self.assertIsNotNone(adm1_id)

        # Check duplicate for Course 2 (different course)
        res = self.admission_ctrl.check_duplicate({
            "full_name": "MultiCourse Student",
            "contact1": m1,
            "contact2": m2,
            "course_id": self.c2_id,
        })
        self.assertTrue(res.is_identity_match)
        self.assertEqual(res.classification, "EXISTING_STUDENT_NEW_COURSE")
        self.assertTrue(res.can_create_admission)

        # New admission creation must succeed and reuse existing student profile
        adm2_id = self.admission_ctrl.create_admission({
            "course_id": self.c2_id,
            "first_name": "MultiCourse",
            "last_name": "Student",
            "mobile_number": m1,
            "secondary_mobile": m2,
            "village": "Chandwad",
            "photo_path": "uploads/photos/dummy.png",
            "status": AdmissionStatus.REGISTERED.value,
        })
        self.assertIsNotNone(adm2_id)
        self.assertNotEqual(adm1_id, adm2_id)

        adm1 = self.admission_ctrl.get_admission(adm1_id)
        adm2 = self.admission_ctrl.get_admission(adm2_id)
        self.assertEqual(adm1.student_id, adm2.student_id)

    def test_12_same_student_completed_old_admission_readmission_allowed(self):
        """Rule 12: Same student + completed old admission -> Re-admission allowed."""
        m1, m2 = self._unique_mobiles()
        adm_id = self.admission_ctrl.create_admission({
            "course_id": self.c1_id,
            "first_name": "Alumni",
            "last_name": "Graduate",
            "mobile_number": m1,
            "secondary_mobile": m2,
            "village": "Chandwad",
            "photo_path": "uploads/photos/dummy.png",
            "status": AdmissionStatus.REGISTERED.value,
        })
        # Transition admission to COMPLETED
        self.admission_ctrl.update_admission(adm_id, {"status": AdmissionStatus.COMPLETED.value})

        res = self.admission_ctrl.check_duplicate({
            "full_name": "Alumni Graduate",
            "contact1": m1,
            "contact2": m2,
            "course_id": self.c1_id,
        })
        self.assertTrue(res.is_identity_match)
        self.assertEqual(res.classification, "EXISTING_STUDENT_READMISSION")
        self.assertTrue(res.can_create_admission)

    def test_13_same_student_draft_offers_resume(self):
        """Rule 13: Same student + draft -> Offer resume draft."""
        m1, m2 = self._unique_mobiles()
        draft_id = self.admission_ctrl.create_admission({
            "course_id": self.c1_id,
            "first_name": "Draft",
            "last_name": "Applicant",
            "mobile_number": m1,
            "secondary_mobile": m2,
            "village": "Chandwad",
            "status": AdmissionStatus.DRAFT.value,
        })
        self.assertIsNotNone(draft_id)

        res = self.admission_ctrl.check_duplicate({
            "full_name": "Draft Applicant",
            "contact1": m1,
            "contact2": m2,
            "course_id": self.c1_id,
        })
        self.assertTrue(res.is_identity_match)
        self.assertEqual(res.classification, "EXISTING_DRAFT")
        self.assertFalse(res.can_create_admission)
        self.assertEqual(res.draft_admission_id, draft_id)


if __name__ == "__main__":
    unittest.main()
