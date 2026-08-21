# modules/admission/views/admission_form_modal.py

from __future__ import annotations
from datetime import datetime
from pathlib import Path
import re
import subprocess
from typing import Callable, Optional, Any
import flet as ft

from core.logger.service import LogService
from core.exceptions import ValidationError, ConflictError, ServiceError
from modules.admission.controller import AdmissionController
from modules.admission.constants import AdmissionStatus, Qualification, BloodGroup, Gender
from modules.admission.dto import AdmissionDTO, FriendSuggestionDTO
from modules.admission.views.payment_dialog import PaymentDialog
from modules.admission.views.receipt_dialog import ReceiptDialog
from modules.student.controller import StudentController
from modules.course.controller import CourseController
from modules.batch.controller import BatchController
from modules.receipts.controller import ReceiptController
from shared.utils.formatting import format_title_case, format_file_size
from ui.themes.theme import AppTheme

__all__ = ["AdmissionFormModal"]


class AdmissionFormModal(ft.AlertDialog):
    """
    Spacious Horizontal Rectangular Desktop Admission Workspace Modal.
    Structured in clear logical sequence:
    SECTION 1: Student Mode (Register New Student vs Select Existing Student with autofill)
    SECTION 2: Personal Details (Names, Mother, DOB, Gender, Mobile, Parent, Aadhaar)
    SECTION 3: Location (Village, Address) & Village Friend Suggestions (Max 3)
    SECTION 4: Academic & Institution (Qualification, School/College Master, Blood Group)
    SECTION 5: Course & Dynamic Batch Allocation
    SECTION 6: Documents (Real File Pickers with <= 100KB validation)
    SECTION 7: Fees & Actions (Save Draft ₹0 vs Confirm Admission & Continue to Payment >= ₹500)
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
        title_str = "Edit Admission Record" if self.is_edit_mode else "New Student Admission Workspace"
        self.title = ft.Row(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.APP_REGISTRATION, color=AppTheme.PRIMARY, size=24),
                        ft.Text(title_str, size=AppTheme.SIZE_H2, weight=ft.FontWeight.BOLD),
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

        # ── Top AirDrop Notification Toast Banner ──
        self.banner_text = ft.Text("", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.W_500)
        self.banner_icon = ft.Icon(ft.Icons.INFO, size=18)
        self.banner_container = ft.Container(
            content=ft.Row([self.banner_icon, self.banner_text], spacing=AppTheme.PAD_SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding(14, 8, 14, 8),
            border_radius=AppTheme.RADIUS_MD,
            visible=False,
        )

        # ── Mode Switcher & Existing Student Search ──
        self.mode_segmented_btn = ft.SegmentedButton(
            selected=[self.enrollment_mode],
            allow_multiple_selection=False,
            segments=[
                ft.Segment(value="new", label=ft.Text("Register New Student", size=AppTheme.SIZE_BODY), icon=ft.Icon(ft.Icons.PERSON_ADD, size=16)),
                ft.Segment(value="existing", label=ft.Text("Select Existing Student", size=AppTheme.SIZE_BODY), icon=ft.Icon(ft.Icons.PERSON_SEARCH, size=16)),
            ],
            on_change=self._on_mode_change,
            visible=not self.is_edit_mode,
        )

        self.student_search_input = ft.TextField(
            label="Search Existing Student Profile",
            hint_text="Type student name, mobile number, or student ID...",
            prefix_icon=ft.Icons.SEARCH,
            border_radius=AppTheme.RADIUS_MD,
            visible=False,
            on_change=self._on_student_search_change,
            expand=True,
        )
        self.student_search_results = ft.Column(spacing=2, scroll=ft.ScrollMode.AUTO, height=120, visible=False)

        # ── SECTION 1: Personal Details ──
        self.first_name_input = ft.TextField(
            label="First Name *",
            hint_text="e.g. Rahul",
            border_radius=AppTheme.RADIUS_MD,
            value=admission.first_name if admission else "",
            expand=True,
        )
        self.middle_name_input = ft.TextField(
            label="Middle / Father's Name",
            hint_text="e.g. Shashikant",
            border_radius=AppTheme.RADIUS_MD,
            value=admission.middle_name if admission else "",
            expand=True,
        )
        self.last_name_input = ft.TextField(
            label="Surname / Last Name *",
            hint_text="e.g. Patil",
            border_radius=AppTheme.RADIUS_MD,
            value=admission.last_name if admission else "",
            expand=True,
        )

        self.mother_name_input = ft.TextField(
            label="Mother's Name *",
            hint_text="e.g. Sunita",
            border_radius=AppTheme.RADIUS_MD,
            value=admission.mother_name if admission else "",
            expand=True,
        )
        self.dob_input = ft.TextField(
            label="Date of Birth *",
            hint_text="YYYY-MM-DD",
            border_radius=AppTheme.RADIUS_MD,
            value=admission.dob if admission else "2005-01-01",
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
        )

        self.mobile_input = ft.TextField(
            label="Mobile Number *",
            hint_text="10-digit mobile number",
            border_radius=AppTheme.RADIUS_MD,
            value=admission.mobile_number if admission else "",
            keyboard_type=ft.KeyboardType.PHONE,
            prefix_icon=ft.Icons.PHONE,
            expand=True,
        )
        self.parent_name_input = ft.TextField(
            label="Parent / Guardian Name",
            hint_text="e.g. Shashikant Patil",
            border_radius=AppTheme.RADIUS_MD,
            value=admission.parent_guardian_name if admission else "",
            expand=True,
        )
        self.aadhaar_input = ft.TextField(
            label="Aadhaar Number (12 digits) *",
            hint_text="e.g. 1234 5678 9012",
            border_radius=AppTheme.RADIUS_MD,
            value=admission.aadhaar_number if admission else "",
            keyboard_type=ft.KeyboardType.NUMBER,
            prefix_icon=ft.Icons.FINGERPRINT,
            expand=True,
        )

        # ── SECTION 2: Location Details & Friends ──
        self.village_input = ft.TextField(
            label="Village / City *",
            hint_text="e.g. Chandwad",
            border_radius=AppTheme.RADIUS_MD,
            value=admission.village if admission else "Chandwad",
            on_change=lambda _: self._on_village_changed(),
            expand=True,
        )
        self.address_input = ft.TextField(
            label="Residential Address",
            hint_text="e.g. Near Jio Tower, Sawargaon Road",
            border_radius=AppTheme.RADIUS_MD,
            value=admission.address if admission else "",
            expand=True,
        )

        self.friends_container = ft.Row(wrap=True, spacing=6)
        self.friends_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Village Friend Matching (Same Village / Peer Suggestions - Max 3)", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                    self.friends_container,
                ],
                spacing=4,
            ),
            bgcolor=AppTheme.SURFACE_VARIANT,
            padding=ft.Padding(10, 8, 10, 8),
            border_radius=AppTheme.RADIUS_SM,
            visible=False,
        )

        # ── SECTION 3: Qualification & Institution ──
        qual_options = [ft.DropdownOption(key=q.value, text=q.value) for q in Qualification]
        self.qualification_dropdown = ft.Dropdown(
            label="Highest Qualification *",
            options=qual_options,
            value=admission.qualification if admission else Qualification.HSC_12TH.value,
            border_radius=AppTheme.RADIUS_MD,
            expand=True,
            on_select=self._on_qualification_changed,
        )
        self.qual_other_input = ft.TextField(
            label="Specify Qualification",
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
            label="Blood Group",
            options=bg_options,
            value=admission.blood_group if (admission and admission.blood_group) else "O+",
            width=130,
            border_radius=AppTheme.RADIUS_MD,
        )

        # ── SECTION 4: Course & Batch ──
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
            label="Select Batch",
            options=[ft.DropdownOption(key="NONE", text="No Batch Assigned (Allocate Later)")],
            value=str(admission.batch_id) if (admission and admission.batch_id) else "NONE",
            border_radius=AppTheme.RADIUS_MD,
            expand=True,
        )

        # ── SECTION 5: Documents (Real File Pickers & 100 KB validation) ──
        self.photo_info_text = ft.Text(self.photo_filename or "No photo selected (Max 100 KB)", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY)
        self.photo_picker_btn = ft.OutlinedButton(
            content=ft.Text("Choose Photo (Explorer)"),
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

        self.sig_info_text = ft.Text(self.signature_filename or "No signature selected (Max 100 KB)", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY)
        self.sig_picker_btn = ft.OutlinedButton(
            content=ft.Text("Choose Signature (Explorer)"),
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

        # ── SECTION 6: Fee Calculation & Actions ──
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

        # Buttons
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

        # Build Main Workspace Layout
        self._build_content_layout()

    def _build_content_layout(self) -> None:
        # Left Column: Personal & Location
        left_col = ft.Column(
            controls=[
                ft.Text("1. PERSONAL DETAILS", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_H3, color=AppTheme.PRIMARY),
                ft.Row([self.first_name_input, self.middle_name_input, self.last_name_input], spacing=AppTheme.PAD_SM),
                ft.Row([self.mother_name_input, self.dob_input, self.gender_dropdown], spacing=AppTheme.PAD_SM),
                ft.Row([self.mobile_input, self.parent_name_input, self.aadhaar_input], spacing=AppTheme.PAD_SM),
                ft.Divider(height=1, color=AppTheme.BORDER),
                ft.Text("2. LOCATION & VILLAGE MATCHING", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_H3, color=AppTheme.PRIMARY),
                ft.Row([self.village_input, self.address_input], spacing=AppTheme.PAD_SM),
                self.friends_card,
            ],
            spacing=AppTheme.PAD_SM,
            expand=True,
        )

        # Right Column: Academic, Course, Documents & Fees
        right_col = ft.Column(
            controls=[
                ft.Text("3. ACADEMIC & INSTITUTION", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_H3, color=AppTheme.PRIMARY),
                ft.Row([self.qualification_dropdown, self.institution_dropdown, self.blood_group_dropdown], spacing=AppTheme.PAD_SM),
                self.qual_other_input,
                ft.Divider(height=1, color=AppTheme.BORDER),
                ft.Text("4. COURSE & BATCH", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_H3, color=AppTheme.PRIMARY),
                ft.Row([self.course_dropdown, self.batch_dropdown], spacing=AppTheme.PAD_SM),
                ft.Divider(height=1, color=AppTheme.BORDER),
                ft.Text("5. DOCUMENTS (MAX: 100 KB)", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_H3, color=AppTheme.PRIMARY),
                ft.Row(
                    controls=[
                        ft.Column([ft.Text("Student Photo *", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD), ft.Row([self.photo_picker_btn, self.photo_clear_btn]), self.photo_info_text], spacing=2),
                        ft.Column([ft.Text("Student Signature", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD), ft.Row([self.sig_picker_btn, self.sig_clear_btn]), self.sig_info_text], spacing=2),
                    ],
                    spacing=AppTheme.PAD_LG,
                ),
                ft.Divider(height=1, color=AppTheme.BORDER),
                ft.Text("6. FEE SUMMARY", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_H3, color=AppTheme.PRIMARY),
                ft.Row(
                    controls=[
                        ft.Column([ft.Text("Course Fee", size=AppTheme.SIZE_CAPTION), self.base_fee_text], spacing=2),
                        self.discount_input,
                        ft.Column([ft.Text("Final Payable Fee", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD), self.final_fee_text], spacing=2),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            ],
            spacing=AppTheme.PAD_SM,
            expand=True,
        )

        self.content = ft.Container(
            width=960,
            height=660,
            content=ft.Column(
                controls=[
                    self.banner_container,
                    ft.Row(controls=[self.mode_segmented_btn, self.student_search_input], spacing=AppTheme.PAD_SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    self.student_search_results,
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    ft.Row(controls=[left_col, ft.VerticalDivider(width=1, color=AppTheme.BORDER), right_col], expand=True, spacing=AppTheme.PAD_MD),
                ],
                spacing=AppTheme.PAD_SM,
                expand=True,
            ),
        )

        self.actions = [self.save_draft_btn, self.cancel_btn, self.confirm_pay_btn]
        self.actions_alignment = ft.MainAxisAlignment.SPACE_BETWEEN

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

    def _show_toast(self, msg: str, is_error: bool = False, is_success: bool = False) -> None:
        self.banner_text.value = msg
        self.banner_text.color = AppTheme.DANGER if is_error else (AppTheme.SUCCESS if is_success else AppTheme.PRIMARY)
        self.banner_icon.name = ft.Icons.ERROR_OUTLINE if is_error else (ft.Icons.CHECK_CIRCLE if is_success else ft.Icons.INFO)
        self.banner_icon.color = AppTheme.DANGER if is_error else (AppTheme.SUCCESS if is_success else AppTheme.PRIMARY)
        self.banner_container.bgcolor = AppTheme.DANGER_LIGHT if is_error else (AppTheme.SUCCESS_LIGHT if is_success else AppTheme.PRIMARY_LIGHT)
        self.banner_container.border = ft.Border.all(1, AppTheme.DANGER if is_error else (AppTheme.SUCCESS if is_success else AppTheme.PRIMARY))
        self.banner_container.visible = True
        self._safe_update()

    def _show_error(self, msg: str) -> None:
        self._show_toast(msg, is_error=True)

    def _show_success(self, msg: str) -> None:
        self._show_toast(msg, is_success=True)

    def _on_mode_change(self, e: ft.ControlEvent) -> None:
        selected_list = list(e.control.selected)
        mode = selected_list[0] if selected_list else "new"
        self.enrollment_mode = mode
        is_existing = (mode == "existing")
        self.student_search_input.visible = is_existing
        self.student_search_results.visible = is_existing
        if not is_existing:
            self.selected_student_id = None
        self._safe_update()

    def _on_student_search_change(self, e: ft.ControlEvent) -> None:
        query = (e.control.value or "").strip()
        if len(query) < 2:
            self.student_search_results.controls.clear()
            self._safe_update()
            return

        results = self.student_controller.search_students(query)
        tiles = []
        for s in results[:6]:
            tiles.append(
                ft.ListTile(
                    title=ft.Text(s.display_name, size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD),
                    subtitle=ft.Text(f"Mobile: {s.mobile_number or 'N/A'} • Village: {s.village or 'Chandwad'} • ID: #{s.id}", size=AppTheme.SIZE_CAPTION),
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
        self.village_input.value = st.village or "Chandwad"
        self.address_input.value = st.address or ""
        if st.qualification:
            qual_keys = [q.value for q in Qualification]
            if st.qualification in qual_keys:
                self.qualification_dropdown.value = st.qualification
            else:
                self.qualification_dropdown.value = Qualification.OTHER.value
                self.qual_other_input.value = st.qualification
                self.qual_other_input.visible = True
        if st.blood_group:
            self.blood_group_dropdown.value = st.blood_group.upper()

        if st.photo_path and Path(st.photo_path).exists():
            self.photo_filename = st.photo_path
            self.photo_info_text.value = f"Existing: {Path(st.photo_path).name}"
            self.photo_clear_btn.visible = True

        if st.signature_path and Path(st.signature_path).exists():
            self.signature_filename = st.signature_path
            self.sig_info_text.value = f"Existing: {Path(st.signature_path).name}"
            self.sig_clear_btn.visible = True

        self.student_search_results.controls.clear()
        self.student_search_input.value = f"{st.display_name} (ID: #{st.id})"
        self._load_friend_suggestions()
        self._show_success("✓ Existing student information loaded")
        self._safe_update()

    def _on_village_changed(self) -> None:
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
            discount = float(self.discount_input.value or 0.0)
        except ValueError:
            discount = 0.0
        final_fee = max(0.0, self.base_course_fee - discount)
        self.final_fee_text.value = f"₹{final_fee:,.2f}"
        self._safe_update()

    def _load_friend_suggestions(self) -> None:
        village = (self.village_input.value or "").strip()
        if not village:
            self.friends_card.visible = False
            self._safe_update()
            return

        gender = self.gender_dropdown.value
        suggestions = self.controller.get_suggested_friends(
            village=village,
            exclude_student_id=self.selected_student_id or 0,
            gender=gender,
        )
        self.suggested_friends = suggestions
        if not suggestions:
            self.friends_card.visible = False
            self._safe_update()
            return

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

    # ── Real File Pickers (<= 100 KB) ──
    def _trigger_photo_picker(self, e: ft.ControlEvent) -> None:
        try:
            result = subprocess.run(
                ["zenity", "--file-selection", "--title=Select Student Photo (Max 100 KB)", "--file-filter=Images (*.jpg *.jpeg *.png) | *.jpg *.jpeg *.png *.JPG *.JPEG *.PNG"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            selected_path = result.stdout.strip()
            if not selected_path or not Path(selected_path).is_file():
                return

            p = Path(selected_path)
            raw_bytes = p.read_bytes()
            if len(raw_bytes) > self.MAX_FILE_SIZE_BYTES:
                self._show_error(f"Photo size ({len(raw_bytes) / 1024:.1f} KB) exceeds the maximum allowed limit of 100 KB.")
                return

            self.photo_bytes = raw_bytes
            self.photo_filename = p.name
            self.photo_info_text.value = f"Selected: {p.name} ({format_file_size(len(raw_bytes))})"
            self.photo_clear_btn.visible = True
            self._show_success(f"✓ Photo selected: {p.name} ({format_file_size(len(raw_bytes))})")
        except Exception as ex:
            LogService.error(f"Photo picker error: {ex}", context="AdmissionFormModal")
            self._show_error(f"Photo picker error: {ex}")

    def _clear_photo(self, e: ft.ControlEvent) -> None:
        self.photo_bytes = None
        self.photo_filename = None
        self.photo_info_text.value = "No photo selected (Max 100 KB)"
        self.photo_clear_btn.visible = False
        self._safe_update()

    def _trigger_signature_picker(self, e: ft.ControlEvent) -> None:
        try:
            result = subprocess.run(
                ["zenity", "--file-selection", "--title=Select Student Signature (Max 100 KB)", "--file-filter=Images (*.jpg *.jpeg *.png) | *.jpg *.jpeg *.png *.JPG *.JPEG *.PNG"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            selected_path = result.stdout.strip()
            if not selected_path or not Path(selected_path).is_file():
                return

            p = Path(selected_path)
            raw_bytes = p.read_bytes()
            if len(raw_bytes) > self.MAX_FILE_SIZE_BYTES:
                self._show_error(f"Signature size ({len(raw_bytes) / 1024:.1f} KB) exceeds the maximum allowed limit of 100 KB.")
                return

            self.signature_bytes = raw_bytes
            self.signature_filename = p.name
            self.sig_info_text.value = f"Selected: {p.name} ({format_file_size(len(raw_bytes))})"
            self.sig_clear_btn.visible = True
            self._show_success(f"✓ Signature selected: {p.name} ({format_file_size(len(raw_bytes))})")
        except Exception as ex:
            LogService.error(f"Signature picker error: {ex}", context="AdmissionFormModal")
            self._show_error(f"Signature picker error: {ex}")

    def _clear_signature(self, e: ft.ControlEvent) -> None:
        self.signature_bytes = None
        self.signature_filename = None
        self.sig_info_text.value = "No signature selected (Max 100 KB)"
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

        first_name = format_title_case(self.first_name_input.value)
        middle_name = format_title_case(self.middle_name_input.value)
        last_name = format_title_case(self.last_name_input.value)
        mother_name = format_title_case(self.mother_name_input.value)
        parent_name = format_title_case(self.parent_name_input.value)
        village = format_title_case(self.village_input.value)
        address = format_title_case(self.address_input.value)

        return {
            "course_id": course_id,
            "batch_id": batch_id,
            "student_id": self.selected_student_id,
            "first_name": first_name,
            "middle_name": middle_name or None,
            "last_name": last_name,
            "mother_name": mother_name or None,
            "dob": (self.dob_input.value or "").strip(),
            "gender": self.gender_dropdown.value,
            "mobile_number": (self.mobile_input.value or "").strip(),
            "email": "",
            "aadhaar_number": (self.aadhaar_input.value or "").strip(),
            "parent_guardian_name": parent_name or None,
            "village": village or "Chandwad",
            "address": address or None,
            "qualification": self.qualification_dropdown.value,
            "qualification_other": (self.qual_other_input.value or "").strip() if self.qual_other_input.visible else None,
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
