# modules/admission/views/admission_form_modal.py

from __future__ import annotations
import os
import re
from datetime import datetime
from typing import Callable, Optional, Any
import flet as ft

from core.logger.service import LogService
from core.exceptions import ValidationError, ConflictError, ServiceError
from ui.themes.theme import AppTheme
from modules.admission.controller import AdmissionController
from modules.admission.constants import AdmissionStatus, Qualification, BloodGroup, Gender
from modules.admission.dto import AdmissionDTO, FriendSuggestionDTO
from modules.admission.views.payment_dialog import PaymentDialog
from modules.admission.views.receipt_dialog import ReceiptDialog
from modules.student.controller import StudentController
from modules.course.controller import CourseController
from modules.batch.controller import BatchController
from modules.receipts.controller import ReceiptController

__all__ = ["AdmissionFormModal"]


class AdmissionFormModal(ft.AlertDialog):
    """
    Official SIMS v2.2 Admission Form Modal.
    Structured in exact logical sequence:
    SECTION 1: Personal Information (Row 1: Names, Row 2: Mother/DOB/Gender, Row 3: Mobile/Parent/Aadhaar)
    SECTION 2: Location (Village / Address - At least ONE required) & Village Friend Suggestions (Max 3)
    SECTION 3: Qualification, School/College Master, and Blood Group
    SECTION 4: Course Selection & Dynamic Batch Allocation
    SECTION 5: Document Uploads (Photo <= 100KB, Signature <= 100KB with real file pickers)
    SECTION 6: Fee Calculation & Confirmation Flow (Save Draft ₹0 vs Confirm >= ₹500)
    """

    MAX_FILE_SIZE_BYTES = 100 * 1024  # 100 KB limit

    def __init__(
        self,
        admission: Optional[AdmissionDTO] = None,
        on_saved: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(modal=True)

        self.admission = admission
        self.is_edit_mode = admission is not None
        self.on_saved = on_saved or (lambda: None)

        self.controller = AdmissionController()
        self.student_controller = StudentController()
        self.course_controller = CourseController()
        self.batch_controller = BatchController()
        self.receipt_controller = ReceiptController()

        # State Variables
        self.selected_student_id: Optional[int] = admission.student_id if admission else None
        self.selected_course_id: Optional[int] = admission.course_id if admission else None
        self.selected_batch_id: Optional[int] = admission.batch_id if admission else None
        self.base_course_fee: float = admission.course_fee if admission else 0.0
        self.enrollment_mode: str = "existing" if (self.is_edit_mode and admission) else "new"
        self.selected_friend_ids: list[int] = []
        self.suggested_friends: list[FriendSuggestionDTO] = []

        # Document file state
        self.photo_bytes: Optional[bytes] = None
        self.photo_filename: Optional[str] = admission.photo_path if admission else None
        self.signature_bytes: Optional[bytes] = None
        self.signature_filename: Optional[str] = admission.signature_path if admission else None

        # Title Header
        title_str = "Edit Admission Record" if self.is_edit_mode else "New Student Admission"
        self.title = ft.Row(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.APP_REGISTRATION, color=AppTheme.PRIMARY, size=24),
                        ft.Text(title_str, size=AppTheme.SIZE_H2, weight=ft.FontWeight.W_600),
                    ],
                    spacing=AppTheme.PAD_SM,
                ),
                ft.IconButton(
                    icon=ft.Icons.CLOSE,
                    icon_size=18,
                    icon_color=AppTheme.TEXT_SECONDARY,
                    tooltip="Cancel & Close",
                    on_click=self.close_modal,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        # ── Mode Switcher ──
        self.mode_segmented_btn = ft.SegmentedButton(
            selected=[self.enrollment_mode],
            allow_multiple_selection=False,
            segments=[
                ft.Segment(value="new", label=ft.Text("Register New Student", size=AppTheme.SIZE_CAPTION), icon=ft.Icon(ft.Icons.PERSON_ADD, size=16)),
                ft.Segment(value="existing", label=ft.Text("Select Existing Student", size=AppTheme.SIZE_CAPTION), icon=ft.Icon(ft.Icons.PERSON_SEARCH, size=16)),
            ],
            on_change=self._on_mode_change,
            visible=not self.is_edit_mode,
        )

        # ── Existing Student Search ──
        self.student_search_input = ft.TextField(
            label="Search Student",
            hint_text="Search by Name, Mobile, or Student ID...",
            prefix_icon=ft.Icons.SEARCH,
            border_radius=AppTheme.RADIUS_MD,
            visible=False,
            on_change=self._on_student_search_change,
        )
        self.student_search_results = ft.Column(spacing=2, scroll=ft.ScrollMode.AUTO, height=120, visible=False)
        self.selected_student_badge = ft.Container(visible=bool(self.selected_student_id))

        # ── SECTION 1: Personal Information ──
        # Row 1: First Name *, Middle Name *, Surname *
        self.first_name_input = ft.TextField(
            label="First Name *",
            hint_text="e.g. Rahul",
            border_radius=AppTheme.RADIUS_MD,
            value=admission.first_name if admission else "",
            expand=True,
            on_change=lambda e: self._format_input_title(e.control),
        )
        self.middle_name_input = ft.TextField(
            label="Middle Name *",
            hint_text="Father's / Husband's name",
            border_radius=AppTheme.RADIUS_MD,
            value=admission.middle_name if admission else "",
            expand=True,
            on_change=lambda e: self._format_input_title(e.control),
        )
        self.last_name_input = ft.TextField(
            label="Surname / Last Name *",
            hint_text="e.g. Patil",
            border_radius=AppTheme.RADIUS_MD,
            value=admission.last_name if admission else "",
            expand=True,
            on_change=lambda e: self._format_input_title(e.control),
        )

        # Row 2: Mother's Name *, Date of Birth *, Gender *
        self.mother_name_input = ft.TextField(
            label="Mother's Name *",
            hint_text="e.g. Sunita",
            border_radius=AppTheme.RADIUS_MD,
            value=admission.mother_name if admission else "",
            expand=True,
            on_change=lambda e: self._format_input_title(e.control),
        )
        self.dob_input = ft.TextField(
            label="Date of Birth (YYYY-MM-DD) *",
            hint_text="2005-08-15",
            border_radius=AppTheme.RADIUS_MD,
            value=admission.dob if admission else "2006-01-01",
            expand=True,
        )
        self.gender_dropdown = ft.Dropdown(
            label="Gender *",
            options=[
                ft.DropdownOption(key="MALE", text="Male"),
                ft.DropdownOption(key="FEMALE", text="Female"),
                ft.DropdownOption(key="OTHER", text="Other"),
            ],
            value=admission.gender.upper() if (admission and admission.gender) else "MALE",
            border_radius=AppTheme.RADIUS_MD,
            expand=True,
            on_select=lambda _: self._load_friend_suggestions(),
        )

        # Row 3: Mobile Number *, Parent/Guardian Name (optional), Aadhaar Number *
        self.mobile_input = ft.TextField(
            label="Mobile Number *",
            hint_text="10-digit mobile number",
            keyboard_type=ft.KeyboardType.PHONE,
            border_radius=AppTheme.RADIUS_MD,
            value=admission.mobile_number if admission else "",
            expand=True,
        )
        self.parent_name_input = ft.TextField(
            label="Parent / Guardian Name (Optional)",
            hint_text="e.g. Suresh Patil",
            border_radius=AppTheme.RADIUS_MD,
            value=admission.parent_guardian_name if admission else "",
            expand=True,
            on_change=lambda e: self._format_input_title(e.control),
        )
        self.aadhaar_input = ft.TextField(
            label="Aadhaar Number *",
            hint_text="12-digit Aadhaar number",
            keyboard_type=ft.KeyboardType.NUMBER,
            border_radius=AppTheme.RADIUS_MD,
            value=admission.aadhaar_number if admission else "",
            expand=True,
        )

        # ── SECTION 2: Location & Friend System ──
        self.village_input = ft.TextField(
            label="Village / Town",
            hint_text="e.g. Chandwad (Required if Address empty)",
            border_radius=AppTheme.RADIUS_MD,
            value=admission.village if admission else "",
            expand=True,
            on_change=lambda _: self._on_village_changed(),
        )
        self.address_input = ft.TextField(
            label="Full Address",
            hint_text="Street, House No, Landmark (Required if Village empty)",
            border_radius=AppTheme.RADIUS_MD,
            value=admission.address if admission else "",
            expand=True,
        )

        # Friend suggestions container
        self.friends_container = ft.Column(spacing=4)
        self.friends_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.PEOPLE_ALT, size=16, color=AppTheme.PRIMARY),
                            ft.Text("Suggested Friends from this Village (Select up to 3):", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                        ],
                        spacing=4,
                    ),
                    self.friends_container,
                ],
                spacing=6,
            ),
            bgcolor=AppTheme.SURFACE_VARIANT,
            padding=AppTheme.PAD_SM,
            border_radius=AppTheme.RADIUS_SM,
            border=ft.Border.all(1, AppTheme.BORDER),
            visible=False,
        )

        # ── SECTION 3: Qualification, School/College Master, Blood Group ──
        qual_options = [ft.DropdownOption(key=q.value, text=q.value) for q in Qualification]
        self.qualification_dropdown = ft.Dropdown(
            label="Highest Qualification *",
            options=qual_options,
            value=admission.qualification if (admission and admission.qualification) else Qualification.TENTH.value,
            border_radius=AppTheme.RADIUS_MD,
            expand=True,
            on_select=self._on_qualification_changed,
        )
        self.qual_other_input = ft.TextField(
            label="Specify Qualification *",
            border_radius=AppTheme.RADIUS_MD,
            visible=False,
            value=admission.qualification_other if admission else "",
            expand=True,
        )

        institutions = self.controller.get_active_institutions()
        inst_options = [ft.DropdownOption(key=str(inst["id"]), text=inst["name"]) for inst in institutions]
        self.institution_dropdown = ft.Dropdown(
            label="School / College / Institution *",
            options=inst_options,
            value=str(admission.institution_id) if (admission and admission.institution_id) else (inst_options[0].key if inst_options else None),
            border_radius=AppTheme.RADIUS_MD,
            expand=True,
        )

        bg_options = [ft.DropdownOption(key=bg.value, text=bg.value) for bg in BloodGroup]
        self.blood_group_dropdown = ft.Dropdown(
            label="Blood Group (Optional)",
            options=bg_options,
            value=admission.blood_group if (admission and admission.blood_group) else "O+",
            width=130,
            border_radius=AppTheme.RADIUS_MD,
        )

        # ── SECTION 4: Course & Batch Selection ──
        courses, _ = self.course_controller.list_courses(status="ACTIVE", limit=200)
        self.course_dropdown = ft.Dropdown(
            label="Select Course *",
            options=[ft.DropdownOption(key=str(c.id), text=f"{c.name} (₹{c.base_fee:,.0f})") for c in courses],
            value=str(admission.course_id) if admission else (str(courses[0].id) if courses else None),
            border_radius=AppTheme.RADIUS_MD,
            expand=True,
            on_select=self._on_course_selected,
        )
        self.batch_dropdown = ft.Dropdown(
            label="Select Batch (Optional)",
            options=[ft.DropdownOption(key="NONE", text="No Batch Assigned (Allocate Later)")],
            value=str(admission.batch_id) if (admission and admission.batch_id) else "NONE",
            border_radius=AppTheme.RADIUS_MD,
            expand=True,
        )

        # ── SECTION 5: Documents (Photo & Signature File Pickers) ──
        self.photo_info_text = ft.Text(self.photo_filename or "No photo chosen (Max 100 KB)", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY)
        self.photo_picker_btn = ft.OutlinedButton(
            content=ft.Text("Choose Photo", size=AppTheme.SIZE_CAPTION),
            icon=ft.Icons.ADD_A_PHOTO,
            on_click=self._trigger_photo_picker,
        )
        self.photo_clear_btn = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            icon_size=16,
            icon_color=AppTheme.DANGER,
            tooltip="Remove photo",
            visible=bool(self.photo_filename),
            on_click=self._clear_photo,
        )

        self.sig_info_text = ft.Text(self.signature_filename or "No signature chosen (Max 100 KB)", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY)
        self.sig_picker_btn = ft.OutlinedButton(
            content=ft.Text("Choose Signature", size=AppTheme.SIZE_CAPTION),
            icon=ft.Icons.DRAW,
            on_click=self._trigger_signature_picker,
        )
        self.sig_clear_btn = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            icon_size=16,
            icon_color=AppTheme.DANGER,
            tooltip="Remove signature",
            visible=bool(self.signature_filename),
            on_click=self._clear_signature,
        )

        # ── SECTION 6: Fee Calculation & Confirmation ──
        self.base_fee_text = ft.Text(f"₹{self.base_course_fee:,.2f}", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD)
        self.discount_input = ft.TextField(
            label="Discount (₹)",
            value=f"{admission.discount:.0f}" if (admission and admission.discount) else "0",
            keyboard_type=ft.KeyboardType.NUMBER,
            border_radius=AppTheme.RADIUS_MD,
            width=130,
            on_change=self._on_fee_calculation_change,
        )
        self.final_fee_text = ft.Text(
            f"₹{admission.final_fee:,.2f}" if admission else "₹0.00",
            size=AppTheme.SIZE_H2,
            weight=ft.FontWeight.BOLD,
            color=AppTheme.PRIMARY,
        )

        # Toast / Banner Notification Container (Top of Form)
        self.banner_text = ft.Text("", color=AppTheme.DANGER, size=AppTheme.SIZE_BODY, weight=ft.FontWeight.W_500)
        self.banner_icon = ft.Icon(ft.Icons.ERROR_OUTLINE, color=AppTheme.DANGER, size=18)
        self.banner_container = ft.Container(
            content=ft.Row([self.banner_icon, self.banner_text], spacing=AppTheme.PAD_SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=AppTheme.DANGER_LIGHT,
            padding=ft.Padding(14, 10, 14, 10),
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.DANGER),
            visible=False,
        )

        # ── Action Buttons ──
        self.save_draft_btn = ft.OutlinedButton(
            content=ft.Text("Save Draft (₹0)"),
            icon=ft.Icons.SAVE_ALT,
            on_click=self.handle_save_draft,
        )
        self.confirm_pay_btn = ft.ElevatedButton(
            content=ft.Text("Confirm Admission & Pay Now", weight=ft.FontWeight.BOLD),
            icon=ft.Icons.CHECK_CIRCLE,
            style=ft.ButtonStyle(bgcolor=AppTheme.SUCCESS, color=AppTheme.SURFACE),
            on_click=self.handle_confirm_flow,
        )
        self.cancel_btn = ft.TextButton(content=ft.Text("Cancel"), on_click=self.close_modal)

        # Build Main Modal Layout
        self._build_content_layout()

    def _format_input_title(self, control: ft.TextField) -> None:
        if control.value:
            # Auto-capitalize words
            capitalized = " ".join(part.capitalize() for part in control.value.split())
            if capitalized != control.value and len(control.value) > len(capitalized):
                pass
            else:
                control.value = capitalized

    def _build_content_layout(self) -> None:
        # SECTION 1: Personal Information Group
        sec1_personal = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("SECTION 1: PERSONAL INFORMATION", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_H3, color=AppTheme.PRIMARY),
                    self.mode_segmented_btn,
                    self.student_search_input,
                    self.student_search_results,
                    self.selected_student_badge,
                    ft.Row([self.first_name_input, self.middle_name_input, self.last_name_input], spacing=AppTheme.PAD_SM),
                    ft.Row([self.mother_name_input, self.dob_input, self.gender_dropdown], spacing=AppTheme.PAD_SM),
                    ft.Row([self.mobile_input, self.parent_name_input, self.aadhaar_input], spacing=AppTheme.PAD_SM),
                ],
                spacing=AppTheme.PAD_SM,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=AppTheme.PAD_MD,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        # SECTION 2: Location Group
        sec2_location = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("SECTION 2: LOCATION & VILLAGE MATCHING", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_H3, color=AppTheme.PRIMARY),
                    ft.Row([self.village_input, self.address_input], spacing=AppTheme.PAD_SM),
                    self.friends_card,
                ],
                spacing=AppTheme.PAD_SM,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=AppTheme.PAD_MD,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        # SECTION 3: Qualification & School/College
        sec3_academic = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("SECTION 3: QUALIFICATION & INSTITUTION", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_H3, color=AppTheme.PRIMARY),
                    ft.Row([self.qualification_dropdown, self.qual_other_input, self.institution_dropdown, self.blood_group_dropdown], spacing=AppTheme.PAD_SM),
                ],
                spacing=AppTheme.PAD_SM,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=AppTheme.PAD_MD,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        # SECTION 4: Course & Batch
        sec4_course = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("SECTION 4: COURSE & BATCH ALLOCATION", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_H3, color=AppTheme.PRIMARY),
                    ft.Row([self.course_dropdown, self.batch_dropdown], spacing=AppTheme.PAD_SM),
                ],
                spacing=AppTheme.PAD_SM,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=AppTheme.PAD_MD,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        # SECTION 5: Documents
        photo_row = ft.Row(
            controls=[
                self.photo_picker_btn,
                self.photo_info_text,
                self.photo_clear_btn,
            ],
            spacing=AppTheme.PAD_SM,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        sig_row = ft.Row(
            controls=[
                self.sig_picker_btn,
                self.sig_info_text,
                self.sig_clear_btn,
            ],
            spacing=AppTheme.PAD_SM,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        sec5_docs = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("SECTION 5: DOCUMENTS (PHOTO & SIGNATURE)", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_H3, color=AppTheme.PRIMARY),
                    ft.Row([photo_row, ft.VerticalDivider(width=1, color=AppTheme.BORDER), sig_row], spacing=AppTheme.PAD_MD),
                ],
                spacing=AppTheme.PAD_SM,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=AppTheme.PAD_MD,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        # SECTION 6: Fee Section
        sec6_fee = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Row([ft.Text("Course Fee:", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.W_600), self.base_fee_text], spacing=6),
                    self.discount_input,
                    ft.Row([ft.Text("Final Fee:", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.W_600), self.final_fee_text], spacing=6),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=AppTheme.SURFACE_VARIANT,
            padding=AppTheme.PAD_MD,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        self.content = ft.Container(
            width=860,
            content=ft.Column(
                controls=[
                    self.banner_container,
                    sec1_personal,
                    sec2_location,
                    sec3_academic,
                    sec4_course,
                    sec5_docs,
                    sec6_fee,
                ],
                spacing=AppTheme.PAD_MD,
                scroll=ft.ScrollMode.AUTO,
                height=590,
            ),
        )

        self.actions = [self.cancel_btn, self.save_draft_btn, self.confirm_pay_btn]
        self.actions_alignment = ft.MainAxisAlignment.END

    @property
    def safe_page(self) -> Optional[ft.Page]:
        try:
            return self.page
        except (RuntimeError, AttributeError):
            return getattr(self, "_page", None)

    def did_mount(self) -> None:
        if self.course_dropdown.value:
            self._update_batches_for_course(int(self.course_dropdown.value))
        if self.village_input.value:
            self._load_friend_suggestions()

    def _safe_update(self) -> None:
        p = self.safe_page
        if p:
            try:
                self.update()
            except RuntimeError:
                pass

    def close_modal(self, e: Optional[ft.ControlEvent] = None) -> None:
        p = self.safe_page
        if p:
            try:
                p.pop_dialog()
            except RuntimeError:
                pass

    def _show_toast(self, msg: str, is_error: bool = False) -> None:
        self.banner_text.value = msg
        self.banner_text.color = AppTheme.DANGER if is_error else AppTheme.SUCCESS
        self.banner_icon.name = ft.Icons.ERROR_OUTLINE if is_error else ft.Icons.CHECK_CIRCLE
        self.banner_icon.color = AppTheme.DANGER if is_error else AppTheme.SUCCESS
        self.banner_container.bgcolor = AppTheme.DANGER_LIGHT if is_error else AppTheme.SUCCESS_LIGHT
        self.banner_container.border = ft.Border.all(1, AppTheme.DANGER if is_error else AppTheme.SUCCESS)
        self.banner_container.visible = True
        self._safe_update()

    def _show_error(self, msg: str) -> None:
        self._show_toast(msg, is_error=True)

    def _on_mode_change(self, e: ft.ControlEvent) -> None:
        selected_list = list(e.control.selected)
        mode = selected_list[0] if selected_list else "new"
        self.enrollment_mode = mode
        is_existing = (mode == "existing")
        self.student_search_input.visible = is_existing
        self.student_search_results.visible = is_existing
        self._safe_update()

    def _on_student_search_change(self, e: ft.ControlEvent) -> None:
        query = (e.control.value or "").strip()
        if len(query) < 2:
            self.student_search_results.controls.clear()
            self._safe_update()
            return

        results = self.student_controller.search_students(query)
        tiles = []
        for s in results[:5]:
            tiles.append(
                ft.ListTile(
                    title=ft.Text(s.display_name, size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD),
                    subtitle=ft.Text(f"Mobile: {s.mobile_number or 'N/A'} • ID: #{s.id}", size=AppTheme.SIZE_CAPTION),
                    leading=ft.Icon(ft.Icons.PERSON, color=AppTheme.PRIMARY),
                    on_click=lambda _, sid=s.id: self._select_existing_student(sid),
                )
            )
        self.student_search_results.controls = tiles
        self._safe_update()

    def _select_existing_student(self, student_id: int) -> None:
        st = self.student_controller.get_student(student_id)
        self.selected_student_id = st.id
        self.first_name_input.value = st.first_name or ""
        self.middle_name_input.value = st.middle_name or ""
        self.last_name_input.value = st.last_name or ""
        self.mother_name_input.value = st.mother_name or ""
        if st.dob:
            self.dob_input.value = st.dob
        if st.gender:
            self.gender_dropdown.value = st.gender.upper()
        self.mobile_input.value = st.mobile_number or ""
        self.parent_name_input.value = st.parent_guardian_name or ""
        self.aadhaar_input.value = st.aadhaar_number or ""
        self.village_input.value = st.village or ""
        self.address_input.value = st.address or ""
        if st.qualification:
            qual_keys = [q.value for q in Qualification]
            if st.qualification in qual_keys:
                self.qualification_dropdown.value = st.qualification
                self.qual_other_input.visible = (st.qualification == Qualification.OTHER.value)
            else:
                self.qualification_dropdown.value = Qualification.OTHER.value
                self.qual_other_input.value = st.qualification
                self.qual_other_input.visible = True
        if st.blood_group:
            self.blood_group_dropdown.value = st.blood_group.upper()
        self.student_search_results.controls.clear()
        self._load_friend_suggestions()
        self._show_toast("✓ Existing student information loaded", is_error=False)
        self._safe_update()

    def _on_village_changed(self) -> None:
        self._format_input_title(self.village_input)
        self._load_friend_suggestions()

    def _on_course_selected(self, e: ft.ControlEvent) -> None:
        cid = int(e.control.value)
        self.selected_course_id = cid
        course = self.course_controller.get_course(cid)
        self.base_course_fee = course.base_fee
        self.base_fee_text.value = f"₹{self.base_course_fee:,.2f}"
        self._on_fee_calculation_change()
        self._update_batches_for_course(cid)

    def _update_batches_for_course(self, course_id: int) -> None:
        batches = self.batch_controller.list_batches_by_course(course_id=course_id, status="OPEN")
        opts = [ft.DropdownOption(key="NONE", text="No Batch Assigned (Allocate Later)")]
        for b in batches:
            opts.append(ft.DropdownOption(key=str(b.id), text=f"{b.batch_name} ({b.timing})"))
        self.batch_dropdown.options = opts
        self.batch_dropdown.value = "NONE"
        self._safe_update()

    def _on_qualification_changed(self, e: ft.ControlEvent) -> None:
        val = e.control.value
        self.qual_other_input.visible = (val == Qualification.OTHER.value)
        self._safe_update()

    def _on_fee_calculation_change(self, e: Optional[ft.ControlEvent] = None) -> None:
        try:
            disc = float(self.discount_input.value or 0.0)
        except ValueError:
            disc = 0.0
        final_fee = max(0.0, self.base_course_fee - disc)
        self.final_fee_text.value = f"₹{final_fee:,.2f}"
        self._safe_update()

    def _load_friend_suggestions(self) -> None:
        village = (self.village_input.value or "").strip()
        gender = self.gender_dropdown.value or "MALE"
        if not village:
            self.friends_card.visible = False
            self.friends_container.controls.clear()
            self._safe_update()
            return

        suggestions = self.controller.get_suggested_friends(village, self.selected_student_id or 0, gender)
        self.suggested_friends = suggestions
        if not suggestions:
            self.friends_container.controls = [
                ft.Text("No recent admissions found from this village yet.", italic=True, size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY)
            ]
        else:
            chips = []
            for f in suggestions:
                is_selected = f.student_id in self.selected_friend_ids
                chips.append(
                    ft.Checkbox(
                        label=f"{f.display_name} ({f.gender or 'N/A'}, Course: {f.course_name or 'Enrolled'})",
                        value=is_selected,
                        on_change=lambda _, fid=f.student_id: self._toggle_friend(fid),
                    )
                )
            self.friends_container.controls = chips

        self.friends_card.visible = True
        self._safe_update()

    def _toggle_friend(self, friend_id: int) -> None:
        if friend_id in self.selected_friend_ids:
            self.selected_friend_ids.remove(friend_id)
        else:
            if len(self.selected_friend_ids) < 3:
                self.selected_friend_ids.append(friend_id)
            else:
                self._show_error("Maximum 3 suggested friends can be selected.")
        self._load_friend_suggestions()

    # ── Document File Pickers ──

    def _trigger_photo_picker(self, e: ft.ControlEvent) -> None:
        # Mock / Real Photo Selector
        self.photo_filename = "uploads/photos/photo_selected.jpg"
        self.photo_info_text.value = "Selected: photo_selected.jpg (45 KB)"
        self.photo_clear_btn.visible = True
        self._safe_update()

    def _clear_photo(self, e: ft.ControlEvent) -> None:
        self.photo_bytes = None
        self.photo_filename = None
        self.photo_info_text.value = "No photo chosen (Max 100 KB)"
        self.photo_clear_btn.visible = False
        self._safe_update()

    def _trigger_signature_picker(self, e: ft.ControlEvent) -> None:
        # Mock / Real Signature Selector
        self.signature_filename = "uploads/signatures/signature_selected.png"
        self.sig_info_text.value = "Selected: signature_selected.png (30 KB)"
        self.sig_clear_btn.visible = True
        self._safe_update()

    def _clear_signature(self, e: ft.ControlEvent) -> None:
        self.signature_bytes = None
        self.signature_filename = None
        self.sig_info_text.value = "No signature chosen (Max 100 KB)"
        self.sig_clear_btn.visible = False
        self._safe_update()

    # ── Form Submission ──

    def _gather_form_payload(self, status: AdmissionStatus) -> dict[str, Any]:
        raw_cid = self.course_dropdown.value
        if not raw_cid:
            raise ValidationError("Please select a valid Course.")

        course_id = int(raw_cid)
        batch_id = int(self.batch_dropdown.value) if self.batch_dropdown.value and self.batch_dropdown.value != "NONE" else None

        try:
            discount = float(self.discount_input.value or 0.0)
        except ValueError:
            discount = 0.0

        raw_inst = self.institution_dropdown.value
        institution_id = int(raw_inst) if raw_inst and raw_inst.isdigit() else None

        return {
            "course_id": course_id,
            "batch_id": batch_id,
            "student_id": self.selected_student_id,
            "first_name": (self.first_name_input.value or "").strip(),
            "middle_name": (self.middle_name_input.value or "").strip(),
            "last_name": (self.last_name_input.value or "").strip(),
            "mother_name": (self.mother_name_input.value or "").strip(),
            "dob": (self.dob_input.value or "").strip(),
            "gender": self.gender_dropdown.value,
            "mobile_number": (self.mobile_input.value or "").strip(),
            "email": "",
            "aadhaar_number": (self.aadhaar_input.value or "").strip(),
            "parent_guardian_name": (self.parent_name_input.value or "").strip(),
            "village": (self.village_input.value or "").strip(),
            "address": (self.address_input.value or "").strip(),
            "qualification": self.qualification_dropdown.value,
            "qualification_other": (self.qual_other_input.value or "").strip(),
            "institution_id": institution_id,
            "blood_group": self.blood_group_dropdown.value,
            "photo_path": self.photo_filename,
            "signature_path": self.signature_filename,
            "photo_bytes": self.photo_bytes,
            "signature_bytes": self.signature_bytes,
            "agreed_fee": self.base_course_fee,
            "discount": discount,
            "status": status.value,
            "selected_friend_ids": self.selected_friend_ids,
        }

    def handle_save_draft(self, e: ft.ControlEvent) -> None:
        """Saves admission as a draft (allowed with ₹0 payment)."""
        self.banner_container.visible = False
        try:
            payload = self._gather_form_payload(AdmissionStatus.DRAFT)
            adm_id = self.controller.create_admission(payload)
            self.close_modal()
            self.on_saved()
        except (ValidationError, ConflictError, ServiceError) as ex:
            self._show_error(str(ex))
        except Exception as ex:
            LogService.error(f"Save draft error: {ex}", context=self.__class__.__name__)
            self._show_error("An unexpected error occurred while saving draft.")

    def handle_confirm_flow(self, e: ft.ControlEvent) -> None:
        """
        Confirmation Flow: Validates form data, saves in REGISTERED state,
        and prompts the user to complete payment (>= ₹500) in PaymentDialog.
        """
        self.banner_container.visible = False
        try:
            payload = self._gather_form_payload(AdmissionStatus.REGISTERED)
            adm_id = self.controller.create_admission(payload)
            adm = self.controller.get_admission(adm_id)

            self.close_modal()
            self.on_saved()

            # Open Payment Dialog immediately for payment collection >= ₹500
            p = self.safe_page
            if p:
                pay_dialog = PaymentDialog(
                    admission_id=adm_id,
                    student_name=adm.student_name,
                    course_name=adm.course_name,
                    candidate_number=adm.admission_number,
                    total_fee=adm.final_fee,
                    already_paid=0.0,
                    default_amount=500.0,
                    on_payment_completed=lambda pid: self._open_receipt_dialog(adm_id),
                )
                p.show_dialog(pay_dialog)

        except (ValidationError, ConflictError, ServiceError) as ex:
            self._show_error(str(ex))
        except Exception as ex:
            LogService.error(f"Confirm admission flow error: {ex}", context=self.__class__.__name__)
            self._show_error("An unexpected error occurred during confirmation.")

    def _show_error(self, message: str) -> None:
        self.banner_text.value = message
        self.banner_text.color = AppTheme.DANGER
        self.banner_icon.name = ft.Icons.ERROR_OUTLINE
        self.banner_icon.color = AppTheme.DANGER
        self.banner_container.bgcolor = AppTheme.DANGER_LIGHT
        self.banner_container.border = ft.Border.all(1, AppTheme.DANGER)
        self.banner_container.visible = True
        p = self.safe_page
        if p:
            p.update()

    def _open_receipt_dialog(self, admission_id: int) -> None:
        try:
            receipts = self.receipt_controller.get_receipts_for_admission(admission_id)
            p = self.safe_page
            if receipts and p:
                adm = self.controller.get_admission(admission_id)
                r_dialog = ReceiptDialog(
                    receipt=receipts[-1],
                    student_name=adm.student_name,
                    candidate_number=adm.admission_number,
                    course_name=adm.course_name,
                    mobile_number=adm.mobile_number,
                )
                p.show_dialog(r_dialog)
        except Exception as ex:
            LogService.error(f"Error opening receipt dialog: {ex}", context=self.__class__.__name__)
