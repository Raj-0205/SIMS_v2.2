# tests/test_enquiry_quick_walkin_and_followups.py

import pytest
from datetime import date, timedelta
from core.exceptions import ValidationError, NotFoundError
from modules.enquiry.controller import EnquiryController
from modules.enquiry.service import EnquiryService
from modules.enquiry.dto import (
    CreateEnquiryDTO,
    UpdateEnquiryDTO,
    CreateFollowUpDTO,
    EnquiryFilterDTO,
)
from modules.admission.views.admission_form_modal import AdmissionFormModal
from modules.admission.controller import AdmissionController


def test_quick_enquiry_creation_with_category_and_timing():
    ctrl = EnquiryController()

    # 1. Invalid Category should raise ValidationError
    with pytest.raises(ValidationError, match="Invalid category"):
        ctrl.create_enquiry({
            "student_name": "Test Invalid Cat",
            "mobile_number": "9876543210",
            "category": "SUPER_HOT",
        })

    # 2. Valid creation with HOT category and MORNING timing
    enq_id = ctrl.create_enquiry({
        "student_name": "Rohan Dilip Shinde",
        "mobile_number": "9822334455",
        "secondary_mobile": "9822334456",
        "village": "Chandwad",
        "gender": "MALE",
        "category": "HOT",
        "preferred_timing": "MORNING",
        "notes": "Very keen on joining Full Stack Web Dev batch",
        "counselor_name": "Counselor Priya",
    })
    assert enq_id > 0

    enq = ctrl.get_enquiry(enq_id)
    assert enq.student_name == "Rohan Dilip Shinde"
    assert enq.first_name == "Rohan"
    assert enq.last_name == "Shinde"
    assert enq.mobile_number == "9822334455"
    assert enq.secondary_mobile == "9822334456"
    assert enq.village == "Chandwad"
    assert enq.gender == "MALE"
    assert enq.category == "HOT"
    assert enq.preferred_timing == "MORNING"
    assert enq.status == "NEW"
    assert enq.notes == "Very keen on joining Full Stack Web Dev batch"


def test_follow_up_recording_and_timeline_history():
    ctrl = EnquiryController()

    enq_id = ctrl.create_enquiry({
        "student_name": "Kavita Ramesh Patil",
        "mobile_number": "9811223344",
        "village": "Vadner",
        "category": "WARM",
    })

    # 1. First follow-up call
    f1_id = ctrl.record_follow_up({
        "enquiry_id": enq_id,
        "call_type": "PHONE",
        "discussion_notes": "Discussed course syllabus and batch timings with mother.",
        "category_after_call": "WARM",
        "next_follow_up_date": (date.today() + timedelta(days=2)).isoformat(),
        "counselor_name": "Counselor Priya",
    })
    assert f1_id > 0

    # 2. Second follow-up visit (Student visited campus and is now HOT)
    f2_id = ctrl.record_follow_up({
        "enquiry_id": enq_id,
        "call_type": "WALK_IN",
        "discussion_notes": "Visited lab with father. Fixed admission date for tomorrow.",
        "category_after_call": "HOT",
        "next_follow_up_date": (date.today() + timedelta(days=1)).isoformat(),
        "counselor_name": "Counselor Priya",
    })
    assert f2_id > 0

    # 3. Verify timeline history in chronological order (newest first)
    timeline = ctrl.get_follow_ups(enq_id)
    assert len(timeline) == 2
    assert timeline[0].id == f2_id
    assert timeline[0].call_type == "WALK_IN"
    assert timeline[0].category_after_call == "HOT"
    assert "Visited lab" in timeline[0].discussion_notes

    assert timeline[1].id == f1_id
    assert timeline[1].call_type == "PHONE"

    # 4. Verify parent enquiry category & next_follow_up_date synced automatically
    parent = ctrl.get_enquiry(enq_id)
    assert parent.category == "HOT"
    assert parent.follow_up_date == (date.today() + timedelta(days=1)).isoformat()
    assert parent.status == "CONTACTED"


def test_category_summary_and_today_follow_up_queue():
    ctrl = EnquiryController()
    today_str = date.today().isoformat()
    yesterday_str = (date.today() - timedelta(days=1)).isoformat()

    # Create distinct categories
    e_hot = ctrl.create_enquiry({
        "student_name": "Test Hot Student",
        "mobile_number": "9870001111",
        "category": "HOT",
        "follow_up_date": today_str,
    })
    e_cold = ctrl.create_enquiry({
        "student_name": "Test Cold Student",
        "mobile_number": "9870002222",
        "category": "COLD",
        "follow_up_date": yesterday_str,  # Overdue
    })
    e_lost = ctrl.create_enquiry({
        "student_name": "Test Lost Student",
        "mobile_number": "9870003333",
        "category": "LOST",
        "loss_reason": "Fees Too High",
    })

    summary = ctrl.get_category_summary()
    assert summary.total >= 3
    assert summary.hot >= 1
    assert summary.cold >= 1
    assert summary.lost >= 1
    assert summary.today_follow_ups >= 1
    assert summary.overdue_follow_ups >= 1

    # Verify filtering by Category works
    hot_leads, h_tot = ctrl.list_enquiries(category="HOT")
    assert any(e.id == e_hot for e in hot_leads)
    assert all(e.category == "HOT" for e in hot_leads)

    # Verify filtering by Today's follow-up works
    today_leads, t_tot = ctrl.list_enquiries(follow_up_filter="TODAY")
    assert any(e.id == e_hot for e in today_leads)


def test_admission_search_and_autofill_and_conversion():
    ctrl = EnquiryController()

    enq_id = ctrl.create_enquiry({
        "student_name": "Kishor Pandurang More",
        "mobile_number": "9866554433",
        "secondary_mobile": "9866554434",
        "village": "Rahuri",
        "gender": "MALE",
        "category": "HOT",
        "notes": "Walk-in registration candidate",
    })
    enq = ctrl.get_enquiry(enq_id)

    # 1. Search for Admission modal
    results = ctrl.search_for_admission("Kishor")
    assert any(r.id == enq_id for r in results)

    # 2. Simulate AdmissionFormModal applying the enquiry profile
    # (Testing apply_enquiry_profile logic and field mappings)
    modal = AdmissionFormModal()
    modal.apply_enquiry_profile(enq)

    assert modal.initial_enquiry_id == enq_id
    assert modal.first_name_input.value == "Kishor"
    assert modal.last_name_input.value == "More"
    assert modal.mobile_input.value == "9866554433"
    assert modal.secondary_mobile_input.value == "9866554434"
    assert modal.village_input.value == "Rahuri"
    assert modal.gender_dropdown.value == "MALE"

    # 3. Perform conversion to admission with a valid admission ID (respecting Foreign Key)
    adm_ctrl = AdmissionController()
    adms, _ = adm_ctrl.filter_admissions({"limit": 1})
    if adms:
        valid_admission_id = adms[0].id
    else:
        from modules.course.controller import CourseController
        courses, _ = CourseController().list_courses(status="ACTIVE")
        cid = courses[0].id if courses else 1
        valid_admission_id = adm_ctrl.create_admission({
            "course_id": cid,
            "first_name": "Test",
            "last_name": "EnquiryAdm",
            "mobile_number": "9866554499",
            "secondary_mobile": "9866554498",
            "village": "Rahuri",
            "status": "DRAFT",
        })

    success = ctrl.service.mark_converted(enq_id, valid_admission_id)
    assert success is True

    # 4. Verify converted state
    converted_enq = ctrl.get_enquiry(enq_id)
    assert converted_enq.status == "CONVERTED"
    assert converted_enq.category == "CONVERTED"
    assert converted_enq.converted_admission_id == valid_admission_id

    # 5. Converted enquiry should no longer appear in search_for_admission()
    remaining = ctrl.search_for_admission("Kishor")
    assert not any(r.id == enq_id for r in remaining)


def test_enquiry_form_modal_edit_pipeline_and_category_retention():
    """Validates that EnquiryFormModal contains category, timing, loss reason controls and saves them correctly."""
    from modules.enquiry.views.enquiry_form_modal import EnquiryFormModal
    import flet as ft

    ctrl = EnquiryController()
    enq_id = ctrl.create_enquiry({
        "student_name": "Suresh Namdeo Jagtap",
        "mobile_number": "9855443322",
        "category": "HOT",
        "preferred_timing": "MORNING",
        "village": "Manmad",
    })
    enquiry = ctrl.get_enquiry(enq_id)

    # 1. Instantiate edit modal
    modal = EnquiryFormModal(enquiry=enquiry)
    assert modal.is_edit_mode is True
    assert hasattr(modal, "category_dropdown")
    assert hasattr(modal, "timing_dropdown")
    assert hasattr(modal, "loss_reason_input")
    assert modal.category_dropdown.value == "HOT"
    assert modal.timing_dropdown.value == "MORNING"

    # 2. Modify in modal and simulate save
    modal.category_dropdown.value = "LOST"
    modal._on_category_changed(None)
    assert modal.loss_reason_input.visible is True
    modal.loss_reason_input.value = "Fees Too High"
    modal.timing_dropdown.value = "EVENING"

    saved_flag = []
    modal.on_saved = lambda: saved_flag.append(True)
    modal._on_save_clicked(None)

    assert len(saved_flag) == 1
    updated = ctrl.get_enquiry(enq_id)
    assert updated.category == "LOST"
    assert updated.preferred_timing == "EVENING"
    assert updated.loss_reason == "Fees Too High"


def test_quick_enquiry_modal_flexible_callbacks_and_scroll():
    """Validates QuickEnquiryModal accommodates 0-arg & 1-arg callbacks and enables scrolling."""
    from modules.enquiry.views.quick_enquiry_modal import QuickEnquiryModal
    import flet as ft

    # 1. 0-arg callback
    called_zero = []
    modal_zero = QuickEnquiryModal(on_saved=lambda: called_zero.append("0-arg"))
    modal_zero.name_input.value = "Rahul Sane"
    modal_zero.mobile_input.value = "9822114477"
    if modal_zero.courses_list:
        modal_zero.course_dropdown.value = str(modal_zero.courses_list[0].id)
    else:
        modal_zero.courses_list = [type("C", (), {"id": 1, "name": "Basic", "code": "B1"})()]
        modal_zero.course_dropdown.options = [ft.dropdown.Option("1", "Basic")]
        modal_zero.course_dropdown.value = "1"

    success = modal_zero.handle_save()
    assert success is True
    assert len(called_zero) == 1

    # 2. 1-arg callback
    called_one = []
    modal_one = QuickEnquiryModal(on_saved=lambda eid: called_one.append(eid))
    modal_one.name_input.value = "Pooja Jadhav"
    modal_one.mobile_input.value = "9822114488"
    modal_one.course_dropdown.options = [ft.dropdown.Option("1", "Basic")]
    modal_one.course_dropdown.value = "1"
    modal_one.courses_list = [type("C", (), {"id": 1, "name": "Basic", "code": "B1"})()]

    success2 = modal_one.handle_save()
    assert success2 is True
    assert len(called_one) == 1
    assert called_one[0] > 0

    # 3. Verify scroll and max-height constraints
    inner_col = modal_zero.content.content
    assert inner_col.scroll == ft.ScrollMode.AUTO
    assert modal_zero.content.height == 500


def test_enquiry_home_responsive_layout_and_frozen_header():
    """Validates EnquiryHome uses ResponsiveRow for KPIs, wrap on action bars, and frozen stationary header architecture."""
    from modules.enquiry.views.enquiry_home import EnquiryHome
    import flet as ft

    home = EnquiryHome()
    # 1. Verify col_specs and stationary header
    assert hasattr(home, "col_specs")
    assert len(home.col_specs) == 6
    assert hasattr(home, "header_table")
    assert hasattr(home, "data_table")
    assert home.header_table.heading_row_height == 42
    assert home.data_table.heading_row_height == 0
    assert home.data_table.divider_thickness == 0

    # 2. Verify controls_panel has ResponsiveRow for KPIs
    kpis_control = home.controls_panel.controls[0]
    assert isinstance(kpis_control, ft.ResponsiveRow)
    assert home.card_today.col == {"xs": 12, "sm": 6, "md": 4, "lg": 2}
    assert home.card_hot.col == {"xs": 12, "sm": 6, "md": 4, "lg": 2}

    # 3. Verify filter row has wrap=True
    filter_row = home.controls_panel.controls[1]
    assert filter_row.wrap is True

    # 4. Render rows and check column spacing & synchronization
    home._render_table_rows()
    assert home.header_table.column_spacing == home.data_table.column_spacing
    assert home.header_table.horizontal_margin == home.data_table.horizontal_margin


def test_defensive_cascade_delete_enquiry():
    """Verifies that deleting an enquiry safely purges associated follow-ups without FK violations."""
    ctrl = EnquiryController()
    enq_id = ctrl.create_enquiry({
        "student_name": "Deletion Test Candidate",
        "mobile_number": "9812345678",
        "category": "WARM",
    })

    # Add 2 follow-ups
    f1 = ctrl.record_follow_up({
        "enquiry_id": enq_id,
        "call_type": "PHONE",
        "discussion_notes": "Initial contact made",
    })
    f2 = ctrl.record_follow_up({
        "enquiry_id": enq_id,
        "call_type": "PHONE",
        "discussion_notes": "Second contact made",
    })

    assert len(ctrl.get_follow_ups(enq_id)) == 2

    # Delete enquiry
    deleted = ctrl.delete_enquiry(enq_id)
    assert deleted is True

    # Confirm enquiry no longer exists
    with pytest.raises(NotFoundError):
        ctrl.get_enquiry(enq_id)

    # Confirm follow-ups are purged
    remaining_follow_ups = ctrl.get_follow_ups(enq_id)
    assert len(remaining_follow_ups) == 0
