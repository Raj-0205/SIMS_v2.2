# tests/test_e2e_admission_workflows.py

import time
import unittest
from core.startup.bootstrap import ApplicationBootstrapper
from core.exceptions import ValidationError, ConflictError
from modules.admission.controller import AdmissionController
from modules.admission.constants import AdmissionStatus
from modules.student.controller import StudentController
from modules.course.controller import CourseController


class TestE2EAdmissionWorkflows(unittest.TestCase):
    """
    End-to-End Workflow Verification adhering strictly to Directive Point 15:
    Workflow A: Clean new admission (Primary + Secondary contacts)
    Workflow B: Returning student new course (Reuses student profile)
    Workflow C: Sibling / Shared family contact (Same phone, different student)
    Workflow D: Duplicate active admission (Same student, same course -> Blocked)
    """

    @classmethod
    def setUpClass(cls):
        bootstrapper = ApplicationBootstrapper()
        bootstrapper._initialize_engines()

        cls.admission_ctrl = AdmissionController()
        cls.student_ctrl = StudentController()
        cls.course_ctrl = CourseController()

        courses, _ = cls.course_ctrl.list_courses(status="ACTIVE")
        if len(courses) < 2:
            cls.c1_id = cls.course_ctrl.create_course({"name": "MS-CIT Basic", "code": "MSCIT", "base_fee": 4500.0})
            cls.c2_id = cls.course_ctrl.create_course({"name": "Tally Prime", "code": "TALLY", "base_fee": 5500.0})
        else:
            cls.c1_id = courses[0].id
            cls.c2_id = courses[1].id

    def test_workflow_A_clean_new_admission(self):
        """Workflow A: Clean new admission -> Student created with Contact 1 and Contact 2, admission created."""
        ts = int(time.time() * 1000) % 10000000
        c1 = f"982{ts:07d}"
        c2 = f"983{ts:07d}"

        adm_id = self.admission_ctrl.create_admission({
            "course_id": self.c1_id,
            "first_name": "Tejas",
            "middle_name": "Kishor",
            "last_name": "Desale",
            "mobile_number": c1,
            "secondary_mobile": c2,
            "mother_name": "Sunita",
            "village": "Chandwad",
            "address": "Opposite Bus Stand",
            "photo_path": "uploads/photos/dummy.png",
            "status": AdmissionStatus.REGISTERED.value,
        })
        self.assertIsNotNone(adm_id)

        adm = self.admission_ctrl.get_admission(adm_id)
        self.assertEqual(adm.student_name, "Tejas Kishor Desale")
        self.assertEqual(adm.mobile_number, c1)
        self.assertEqual(adm.student_secondary_mobile, c2)

        # Verify Student Master record in DB
        st = self.student_ctrl.get_student(adm.student_id)
        self.assertEqual(st.first_name, "Tejas")
        self.assertEqual(st.last_name, "Desale")
        self.assertEqual(st.mobile_number, c1)
        self.assertEqual(st.secondary_mobile, c2)

    def test_workflow_B_returning_student_different_course(self):
        """Workflow B: Returning student different course -> Existing student detected, new admission created, same student_id linked."""
        ts = int(time.time() * 1000) % 10000000
        c1 = f"984{ts:07d}"
        c2 = f"985{ts:07d}"

        # 1. First enrollment in Course 1
        adm1_id = self.admission_ctrl.create_admission({
            "course_id": self.c1_id,
            "first_name": "Priyanka",
            "last_name": "Borse",
            "mobile_number": c1,
            "secondary_mobile": c2,
            "village": "Chandwad",
            "photo_path": "uploads/photos/dummy.png",
            "status": AdmissionStatus.CONFIRMED.value,
            "initial_payment_amount": 500.0,
            "payment_mode": "CASH",
            "admin_pin": "1234",
        })
        self.assertIsNotNone(adm1_id)
        adm1 = self.admission_ctrl.get_admission(adm1_id)
        original_student_id = adm1.student_id

        # 2. Check duplicate for Course 2
        dup_check = self.admission_ctrl.check_duplicate({
            "full_name": "Priyanka Borse",
            "contact1": c1,
            "contact2": c2,
            "course_id": self.c2_id,
        })
        self.assertTrue(dup_check.is_identity_match)
        self.assertEqual(dup_check.classification, "EXISTING_STUDENT_NEW_COURSE")
        self.assertTrue(dup_check.can_create_admission)
        self.assertEqual(dup_check.existing_student_id, original_student_id)

        # 3. Create second admission in Course 2 (either passing student_id or inline matching)
        adm2_id = self.admission_ctrl.create_admission({
            "course_id": self.c2_id,
            "student_id": original_student_id,
            "first_name": "Priyanka",
            "last_name": "Borse",
            "village": "Chandwad",
            "photo_path": "uploads/photos/dummy.png",
            "status": AdmissionStatus.REGISTERED.value,
        })
        self.assertIsNotNone(adm2_id)
        self.assertNotEqual(adm1_id, adm2_id)

        adm2 = self.admission_ctrl.get_admission(adm2_id)
        self.assertEqual(adm2.student_id, original_student_id)

        # Verify Student Workspace shows both admissions
        ws = self.student_ctrl.get_student_workspace(original_student_id)
        self.assertEqual(len(ws.admissions), 2)

    def test_workflow_C_sibling_shared_contact(self):
        """Workflow C: Sibling/shared contact -> Same mobile, different full name, succeeds as new independent student."""
        ts = int(time.time() * 1000) % 10000000
        parent_mobile = f"986{ts:07d}"
        alt_mobile = f"987{ts:07d}"

        # Sibling 1
        adm1_id = self.admission_ctrl.create_admission({
            "course_id": self.c1_id,
            "first_name": "Aditya",
            "middle_name": "Sunil",
            "last_name": "Chavan",
            "mobile_number": parent_mobile,
            "secondary_mobile": alt_mobile,
            "village": "Chandwad",
            "photo_path": "uploads/photos/dummy.png",
            "status": AdmissionStatus.REGISTERED.value,
        })
        self.assertIsNotNone(adm1_id)
        adm1 = self.admission_ctrl.get_admission(adm1_id)

        # Sibling 2 (Same parent mobile numbers, but different child name)
        dup_check = self.admission_ctrl.check_duplicate({
            "full_name": "Kavya Sunil Chavan",
            "contact1": parent_mobile,
            "contact2": alt_mobile,
            "course_id": self.c1_id,
        })
        self.assertFalse(dup_check.is_identity_match)
        self.assertEqual(dup_check.classification, "NONE")

        adm2_id = self.admission_ctrl.create_admission({
            "course_id": self.c1_id,
            "first_name": "Kavya",
            "middle_name": "Sunil",
            "last_name": "Chavan",
            "mobile_number": parent_mobile,
            "secondary_mobile": alt_mobile,
            "village": "Chandwad",
            "photo_path": "uploads/photos/dummy.png",
            "status": AdmissionStatus.REGISTERED.value,
        })
        self.assertIsNotNone(adm2_id)
        adm2 = self.admission_ctrl.get_admission(adm2_id)

        # Must be distinct student master entities
        self.assertNotEqual(adm1.student_id, adm2.student_id)
        st1 = self.student_ctrl.get_student(adm1.student_id)
        st2 = self.student_ctrl.get_student(adm2.student_id)
        self.assertEqual(st1.first_name, "Aditya")
        self.assertEqual(st2.first_name, "Kavya")
        self.assertEqual(st1.mobile_number, st2.mobile_number)

    def test_workflow_D_duplicate_active_admission_blocked(self):
        """Workflow D: Duplicate active admission -> Same student, same active course, blocked with clear error."""
        ts = int(time.time() * 1000) % 10000000
        c1 = f"988{ts:07d}"
        c2 = f"989{ts:07d}"

        # 1. Enrolled in Course 1
        adm_id = self.admission_ctrl.create_admission({
            "course_id": self.c1_id,
            "first_name": "Mayur",
            "last_name": "Khairnar",
            "mobile_number": c1,
            "secondary_mobile": c2,
            "village": "Chandwad",
            "photo_path": "uploads/photos/dummy.png",
            "status": AdmissionStatus.CONFIRMED.value,
            "initial_payment_amount": 500.0,
            "payment_mode": "CASH",
            "admin_pin": "1234",
        })
        self.assertIsNotNone(adm_id)

        # 2. Check duplicate for same course
        dup_check = self.admission_ctrl.check_duplicate({
            "full_name": "Mayur Khairnar",
            "contact1": c1,
            "contact2": c2,
            "course_id": self.c1_id,
        })
        self.assertTrue(dup_check.is_identity_match)
        self.assertEqual(dup_check.classification, "DUPLICATE_ACTIVE")
        self.assertFalse(dup_check.can_create_admission)

        # 3. Direct attempt to create duplicate active admission must raise ConflictError
        with self.assertRaises(ConflictError) as ctx:
            self.admission_ctrl.create_admission({
                "course_id": self.c1_id,
                "first_name": "Mayur",
                "last_name": "Khairnar",
                "mobile_number": c1,
                "secondary_mobile": c2,
                "village": "Chandwad",
                "photo_path": "uploads/photos/dummy.png",
                "status": AdmissionStatus.REGISTERED.value,
            })
        self.assertIn("already has an active", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
