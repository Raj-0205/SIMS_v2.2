# tests/test_enquiry_module.py

import pytest
from core.exceptions import ValidationError, NotFoundError
from modules.enquiry.controller import EnquiryController
from modules.enquiry.dto import CreateEnquiryDTO, UpdateEnquiryDTO, EnquiryFilterDTO
from modules.enquiry.service import EnquiryService


def test_enquiry_creation_and_10_digit_validation():
    service = EnquiryService()

    # Invalid mobile (less than 10 digits)
    with pytest.raises(ValidationError, match="10 digits"):
        service.create_enquiry(
            CreateEnquiryDTO(
                student_name="Rahul Sharma",
                mobile_number="987654321",  # 9 digits
            )
        )

    # Invalid mobile (more than 10 digits)
    with pytest.raises(ValidationError, match="10 digits"):
        service.create_enquiry(
            CreateEnquiryDTO(
                student_name="Rahul Sharma",
                mobile_number="98765432100",  # 11 digits
            )
        )

    # Valid 10-digit mobile
    enquiry_id = service.create_enquiry(
        CreateEnquiryDTO(
            student_name="Rahul Sharma",
            mobile_number="9876543210",
            village="Rampur",
            interested_course="CCC",
            notes="Interested in evening batch",
        )
    )
    assert enquiry_id > 0

    enquiry = service.get_enquiry(enquiry_id)
    assert enquiry.student_name == "Rahul Sharma"
    assert enquiry.mobile_number == "9876543210"
    assert enquiry.village == "Rampur"
    assert enquiry.status == "NEW"


def test_enquiry_update_and_status_transition():
    service = EnquiryService()
    enquiry_id = service.create_enquiry(
        CreateEnquiryDTO(
            student_name="Pooja Patel",
            mobile_number="9123456780",
            village="Navsari",
        )
    )

    # Update status to CONTACTED
    updated = service.update_enquiry(
        UpdateEnquiryDTO(
            id=enquiry_id,
            student_name="Pooja Patel",
            mobile_number="9123456780",
            village="Navsari",
            status="CONTACTED",
            notes="Called and scheduled counseling session",
        )
    )
    assert updated is True

    record = service.get_enquiry(enquiry_id)
    assert record.status == "CONTACTED"
    assert record.notes == "Called and scheduled counseling session"


def test_enquiry_conversion_draft():
    service = EnquiryService()
    enquiry_id = service.create_enquiry(
        CreateEnquiryDTO(
            student_name="Amit Kumar Verma",
            mobile_number="9988776655",
            village="Surat",
            interested_course="Tally Prime",
        )
    )

    draft = service.convert_to_admission_draft(enquiry_id)
    assert draft["first_name"] == "Amit"
    assert draft["last_name"] == "Verma"
    assert draft["mobile_number"] == "9988776655"
    assert draft["village"] == "Surat"
    assert draft["enquiry_id"] == enquiry_id


def test_enquiry_search_and_summary():
    ctrl = EnquiryController()
    unique_village = "Khadki_Enquiry_Test"

    ctrl.create_enquiry({
        "student_name": "Test Search Student 1",
        "mobile_number": "9000000001",
        "village": unique_village,
        "status": "NEW",
    })
    ctrl.create_enquiry({
        "student_name": "Test Search Student 2",
        "mobile_number": "9000000002",
        "village": unique_village,
        "status": "VISITED",
    })

    results, total = ctrl.list_enquiries(village=unique_village)
    assert total >= 2

    # Filter by status
    visited_results, v_total = ctrl.list_enquiries(village=unique_village, status="VISITED")
    assert v_total >= 1
    assert any(e.status == "VISITED" for e in visited_results)

    # Summary
    summary = ctrl.get_summary()
    assert summary.total >= 2
