import os
import sys
from pathlib import Path

# Add workspace to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.configuration.service import ConfigService
from core.logger.service import LogService
from core.database.engine import DatabaseEngine
from core.database.migration import MigrationEngine

from modules.student.controller import StudentController
from modules.admission.controller import AdmissionController
from modules.payments.controller import PaymentController
from modules.receipts.controller import ReceiptController
from modules.settings.controller import SettingsController
from modules.reports.controller import ReportsController
from modules.course.controller import CourseController

def init_env():
    ConfigService.initialize()
    LogService.initialize()
    DatabaseEngine.initialize()
    MigrationEngine.initialize()
    MigrationEngine.upgrade()

def run_test():
    init_env()
    print("=== STARTING FULL END-TO-END FORENSIC VERIFICATION ===")

    student_ctrl = StudentController()
    admission_ctrl = AdmissionController()
    payment_ctrl = PaymentController()
    receipt_ctrl = ReceiptController()
    settings_ctrl = SettingsController()
    reports_ctrl = ReportsController()
    course_ctrl = CourseController()

    # 1. Check/Ensure courses exist
    courses, _ = course_ctrl.list_courses()
    if not courses:
        print("Creating test courses...")
        c1_id = course_ctrl.create_course({"name": "MS-CIT", "code": "MSCIT", "base_fee": 5000.0, "status": "ACTIVE"})
        c2_id = course_ctrl.create_course({"name": "Advanced Excel", "code": "ADVEXCEL", "base_fee": 4000.0, "status": "ACTIVE"})
        c3_id = course_ctrl.create_course({"name": "Python Programming", "code": "PYTHON", "base_fee": 6000.0, "status": "ACTIVE"})
    else:
        c1_id = courses[0].id
        c2_id = courses[1].id if len(courses) > 1 else courses[0].id

    print(f"Using Course 1 ID: {c1_id}, Course 2 ID: {c2_id}")

    # 2. Test Student Master Profile Creation
    mobile_test = f"9822{os.getpid() % 1000000:06d}"
    print(f"Creating Student Master Profile with mobile: {mobile_test}")

    student_payload = {
        "first_name": "anuj",
        "middle_name": "raj",
        "last_name": "pagar",
        "mother_name": "sunita",
        "parent_guardian_name": "raj pagar",
        "dob": "2004-05-15",
        "gender": "MALE",
        "mobile_number": mobile_test,
        "email": "anuj.pagar@example.com",
        "aadhaar_number": "123456789012",
        "village": "chandwad",
        "address": "near jio tower, sawargaon road",
        "qualification": "12th Standard (HSC)",
        "blood_group": "B+",
    }

    stud_id = student_ctrl.create_student(student_payload)
    assert stud_id > 0, "Student creation failed"
    st = student_ctrl.get_student(stud_id)
    print(f"✓ Student Created: #{st.id} - Name: {st.display_name}")
    assert st.first_name == "Anuj", f"Expected Anuj, got {st.first_name}"
    assert st.last_name == "Pagar", f"Expected Pagar, got {st.last_name}"
    assert st.village == "Chandwad", f"Expected Chandwad, got {st.village}"

    # 3. Test Student Master Notes & Friends
    print("Testing Student Notes...")
    student_ctrl.add_student_note(stud_id, "Candidate submitted scholarship inquiry.", "OPERATOR")
    student_ctrl.add_student_note(stud_id, "Submitted original 10th marksheet copy.", "ADMIN")
    notes = student_ctrl.get_student_notes(stud_id)
    print(f"✓ Student Notes count: {len(notes)}")
    assert len(notes) >= 2, "Notes failed to save"

    print("Testing Village Friends Link...")
    mobile_friend = f"9823{os.getpid() % 1000000:06d}"
    friend_id = student_ctrl.create_student({
        "first_name": "rohit",
        "last_name": "shinde",
        "mother_name": "kavita",
        "dob": "2004-08-20",
        "gender": "MALE",
        "mobile_number": mobile_friend,
        "aadhaar_number": "987654321098",
        "village": "chandwad",
    })
    student_ctrl.add_student_friend(stud_id, friend_id)
    w_data = student_ctrl.get_student_workspace(stud_id)
    print(f"✓ Student Friends count: {len(w_data.friends)}")
    assert len(w_data.friends) == 1, "Friend linking failed"

    # 4. Test Document Upload & 100 KB validation
    print("Testing Document Upload (< 100 KB)...")
    dummy_photo = b"JPEG_DATA_UNDER_100KB" * 50
    student_ctrl.upload_student_document(stud_id, "PHOTO", dummy_photo, "test_photo.jpg")
    st_after_doc = student_ctrl.get_student(stud_id)
    print(f"✓ Photo path: {st_after_doc.photo_path}")
    assert st_after_doc.photo_path is not None, "Photo upload failed"

    print("Testing Document Upload (> 100 KB rejection)...")
    huge_photo = b"X" * (105 * 1024)
    rejected = False
    try:
        student_ctrl.upload_student_document(stud_id, "PHOTO", huge_photo, "huge_photo.jpg")
    except Exception as ex:
        rejected = True
        print(f"✓ Correctly rejected oversized document: {ex}")
    assert rejected, "Oversized file was not rejected"

    # 5. Test Multiple Admissions for the Same Student Profile
    print("Testing 1st Admission (MS-CIT) for Anuj...")
    adm1_payload = {
        "student_id": stud_id,
        "course_id": c1_id,
        "status": "REGISTERED",
        "first_name": "Anuj",
        "last_name": "Pagar",
        "mother_name": "Sunita",
        "dob": "2004-05-15",
        "gender": "MALE",
        "mobile_number": mobile_test,
        "aadhaar_number": "123456789012",
        "village": "Chandwad",
        "agreed_fee": 5000.0,
        "discount": 500.0,
    }
    adm1_id = admission_ctrl.create_admission(adm1_payload)
    print(f"✓ 1st Admission Created: #{adm1_id}")

    print("Testing 1st Admission Confirmation with Payment (₹1,500)...")
    pay1_id = admission_ctrl.confirm_admission_with_payment(
        admission_id=adm1_id,
        amount=1500.0,
        payment_mode="UPI",
        admin_pin="1234",
        collector_name="Hemant Mahale (Sir)",
        transaction_ref="UPI/TEST/001",
    )
    print(f"✓ 1st Payment ID: #{pay1_id}")
    adm1 = admission_ctrl.get_admission(adm1_id)
    print(f"✓ 1st Admission Status: {adm1.status}, Paid: ₹{adm1.total_paid:,.2f}, Pending: ₹{adm1.pending_amount:,.2f}")
    assert adm1.status == "CONFIRMED", f"Expected CONFIRMED, got {adm1.status}"

    print("Testing 2nd Admission (Advanced Excel) for the SAME Anuj Pagar...")
    adm2_payload = {
        "student_id": stud_id,
        "course_id": c2_id,
        "status": "REGISTERED",
        "first_name": "Anuj",
        "last_name": "Pagar",
        "mother_name": "Sunita",
        "dob": "2004-05-15",
        "gender": "MALE",
        "mobile_number": mobile_test,
        "aadhaar_number": "123456789012",
        "village": "Chandwad",
        "agreed_fee": 4000.0,
        "discount": 0.0,
    }
    adm2_id = admission_ctrl.create_admission(adm2_payload)
    print(f"✓ 2nd Admission Created: #{adm2_id}")

    # Check Student Workspace: Student must have BOTH admissions
    w_data = student_ctrl.get_student_workspace(stud_id)
    print(f"✓ Total Admissions in Anuj's Profile: {len(w_data.admissions)}")
    assert len(w_data.admissions) == 2, f"Expected 2 admissions for student, got {len(w_data.admissions)}"

    # 6. Test 2nd Installment Payment for Admission 1
    print("Testing 2nd Installment Payment for Admission 1 (₹1,000)...")
    pay2_id = payment_ctrl.record_payment({
        "admission_id": adm1_id,
        "student_id": stud_id,
        "amount": 1000.0,
        "payment_mode": "CASH",
        "collector_name": "Hemant Mahale (Sir)",
        "remarks": "2nd installment cash",
    })
    print(f"✓ 2nd Payment ID: #{pay2_id}")
    adm1_updated = admission_ctrl.get_admission(adm1_id)
    print(f"✓ Updated Paid: ₹{adm1_updated.total_paid:,.2f}, Pending: ₹{adm1_updated.pending_amount:,.2f}")
    assert adm1_updated.total_paid == 2500.0, f"Expected 2500.0, got {adm1_updated.total_paid}"

    # 7. Test Admission Cancellation
    print("Testing Admission Cancellation on Admission 2...")
    admission_ctrl.cancel_admission(adm2_id, reason="Student postponed enrollment to next semester")
    adm2_cancelled = admission_ctrl.get_admission(adm2_id)
    print(f"✓ Admission 2 Status after cancel: {adm2_cancelled.status}")
    assert adm2_cancelled.status == "CANCELLED", f"Expected CANCELLED, got {adm2_cancelled.status}"

    # Verify Student Master profile is still intact
    st_check = student_ctrl.get_student(stud_id)
    assert st_check is not None, "Student profile was damaged"
    print(f"✓ Student Master Profile is completely intact: #{st_check.id}")

    # 8. Test Fees Report & 17 Columns CSV Export
    print("Testing Fees & Reports Module...")
    report_rows = reports_ctrl.get_admission_fees_report(search="Anuj")
    print(f"✓ Found {len(report_rows)} report row(s) for Anuj")
    assert len(report_rows) >= 2, f"Expected at least 2 admission rows, got {len(report_rows)}"

    r1 = [r for r in report_rows if r["admission_id"] == adm1.admission_number][0]
    print(f"✓ Report Row 1: Course: {r1['course_name']}, Total: ₹{r1['total_fees']:,.2f}, Inst 1: ₹{r1['inst1']:,.2f}, Inst 2: ₹{r1['inst2']:,.2f}, Paid: ₹{r1['total_paid']:,.2f}, Pending: ₹{r1['pending_fees']:,.2f}")
    assert r1["inst1"] == 1500.0, f"Expected Inst 1 = 1500, got {r1['inst1']}"
    assert r1["inst2"] == 1000.0, f"Expected Inst 2 = 1000, got {r1['inst2']}"
    assert r1["total_paid"] == 2500.0, f"Expected Total Paid = 2500, got {r1['total_paid']}"

    csv_path = reports_ctrl.export_fees_report_csv(report_rows)
    print(f"✓ Exported 17-column CSV: {csv_path}")
    csv_content = Path(csv_path).read_text()
    assert "1ST INSTALLMENT" in csv_content, "Missing 1ST INSTALLMENT column"
    assert "2ND INSTALLMENT" in csv_content, "Missing 2ND INSTALLMENT column"
    assert "FRIEND CONTACT NO" in csv_content, "Missing FRIEND CONTACT NO column"

    # 9. Test Exact Payment Amount Filtering
    print("Testing Exact Payment Amount Filtering (₹1,500)...")
    filtered_payments = reports_ctrl.filter_payments_by_amount(1500.0)
    print(f"✓ Found {len(filtered_payments)} payment(s) of exact amount ₹1,500")
    assert len(filtered_payments) >= 1, "Expected at least 1 payment of ₹1500"

    # 10. Test Educational Institutions Master (Settings)
    print("Testing Educational Institutions in Settings...")
    inst_name = f"SNJB College of Engineering {os.getpid()}"
    inst_id = settings_ctrl.create_institution(inst_name, "COLLEGE", "Chandwad")
    print(f"✓ Created Institution ID: {inst_id}")
    insts = settings_ctrl.list_institutions()
    assert any(i["id"] == inst_id for i in insts), "Institution not found in list"

    settings_ctrl.toggle_institution_status(inst_id)
    toggled_inst = [i for i in settings_ctrl.list_institutions() if i["id"] == inst_id][0]
    print(f"✓ Toggled Institution Active Status: {toggled_inst['is_active']}")
    assert toggled_inst["is_active"] == 0, "Failed to toggle status"

    print("\n=== ALL FORENSIC AUDIT TESTS PASSED WITH 100% INTEGRITY! ===")

if __name__ == "__main__":
    run_test()
