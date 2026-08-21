# modules/student/views/student_form_modal.py

from __future__ import annotations
from typing import Callable, Optional
import flet as ft

from core.exceptions import ValidationError, ConflictError, ServiceError
from core.logger.service import LogService
from modules.student.controller import StudentController
from modules.student.dto import StudentDTO
from shared.utils.formatting import format_title_case
from ui.themes.theme import AppTheme

__all__ = ["StudentFormModal"]


class StudentFormModal(ft.AlertDialog):
    """
    Unified Add/Edit Modal Dialog for Student master entity.
    Supports comprehensive master data editing with validation and clean dialog lifecycle.
    """

    def __init__(
        self,
        controller: StudentController,
        on_saved: Callable[[], None],
        student: Optional[StudentDTO] = None,
    ) -> None:
        super().__init__()

        self.controller = controller
        self.on_saved = on_saved
        self.student = student
        self.is_edit_mode = student is not None

        self.modal = True

        title_text = "Edit Student Master Profile" if self.is_edit_mode else "Register New Student Master"
        self.title = ft.Row(
            controls=[
                ft.Icon(
                    ft.Icons.EDIT_NOTE if self.is_edit_mode else ft.Icons.PERSON_ADD,
                    color=AppTheme.PRIMARY,
                    size=24,
                ),
                ft.Text(
                    title_text,
                    size=AppTheme.SIZE_H2,
                    weight=ft.FontWeight.BOLD,
                    color=AppTheme.TEXT_PRIMARY,
                ),
            ],
            spacing=AppTheme.PAD_SM,
        )

        # ── Form Inputs ──
        self.first_name_input = ft.TextField(
            label="First Name *",
            hint_text="e.g. Rahul",
            value=student.first_name if student else "",
            autofocus=True,
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
            expand=True,
        )

        self.middle_name_input = ft.TextField(
            label="Father / Middle Name",
            hint_text="e.g. Shashikant",
            value=student.middle_name if student and student.middle_name else "",
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
            expand=True,
        )

        self.last_name_input = ft.TextField(
            label="Last Name / Surname *",
            hint_text="e.g. Patil",
            value=student.last_name if student else "",
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
            expand=True,
        )

        self.mother_name_input = ft.TextField(
            label="Mother's Name",
            hint_text="e.g. Sunita",
            value=student.mother_name if student and student.mother_name else "",
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
            expand=True,
        )

        self.dob_input = ft.TextField(
            label="Date of Birth",
            hint_text="YYYY-MM-DD",
            value=student.dob if student and student.dob else "",
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
            expand=True,
        )

        self.gender_dropdown = ft.Dropdown(
            label="Gender",
            options=[
                ft.DropdownOption(key="MALE", text="Male"),
                ft.DropdownOption(key="FEMALE", text="Female"),
                ft.DropdownOption(key="OTHER", text="Other"),
            ],
            value=student.gender.upper() if student and student.gender else "MALE",
            border_radius=AppTheme.RADIUS_MD,
            expand=True,
        )

        self.mobile_input = ft.TextField(
            label="Mobile Number *",
            hint_text="10-digit mobile number",
            value=student.mobile_number or "" if student else "",
            keyboard_type=ft.KeyboardType.PHONE,
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
            prefix_icon=ft.Icons.PHONE,
            expand=True,
        )

        self.email_input = ft.TextField(
            label="Email Address",
            hint_text="e.g. student@example.com",
            value=student.email or "" if student else "",
            keyboard_type=ft.KeyboardType.EMAIL,
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
            prefix_icon=ft.Icons.EMAIL,
            expand=True,
        )

        self.aadhaar_input = ft.TextField(
            label="Aadhaar Number (12 digits)",
            hint_text="e.g. 1234 5678 9012",
            value=student.aadhaar_number if student and student.aadhaar_number else "",
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
            expand=True,
        )

        self.parent_guardian_input = ft.TextField(
            label="Parent / Guardian Name",
            hint_text="e.g. Shashikant Patil",
            value=student.parent_guardian_name if student and student.parent_guardian_name else "",
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
            expand=True,
        )

        self.village_input = ft.TextField(
            label="Village / City",
            hint_text="e.g. Chandwad",
            value=student.village if student and student.village else "",
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
            expand=True,
        )

        self.address_input = ft.TextField(
            label="Residential Address",
            hint_text="e.g. Near Jio Tower, Sawargaon Road",
            value=student.address if student and student.address else "",
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
            expand=True,
        )

        self.qualification_input = ft.TextField(
            label="Highest Qualification",
            hint_text="e.g. 12th Pass / B.Com",
            value=student.qualification if student and student.qualification else "",
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
            expand=True,
        )

        self.blood_group_dropdown = ft.Dropdown(
            label="Blood Group",
            options=[
                ft.DropdownOption(key="A+", text="A+"),
                ft.DropdownOption(key="A-", text="A-"),
                ft.DropdownOption(key="B+", text="B+"),
                ft.DropdownOption(key="B-", text="B-"),
                ft.DropdownOption(key="O+", text="O+"),
                ft.DropdownOption(key="O-", text="O-"),
                ft.DropdownOption(key="AB+", text="AB+"),
                ft.DropdownOption(key="AB-", text="AB-"),
            ],
            value=student.blood_group if student and student.blood_group else None,
            border_radius=AppTheme.RADIUS_MD,
            expand=True,
        )

        # ── Error / Notification Banner ──
        self.error_text = ft.Text(
            value="",
            color=AppTheme.DANGER,
            size=AppTheme.SIZE_CAPTION,
            weight=ft.FontWeight.W_500,
        )
        self.error_container = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE, color=AppTheme.DANGER, size=16),
                    self.error_text,
                ],
                spacing=AppTheme.PAD_SM,
            ),
            bgcolor=AppTheme.DANGER_LIGHT,
            padding=ft.Padding(left=12, top=8, right=12, bottom=8),
            border_radius=AppTheme.RADIUS_SM,
            visible=False,
        )

        # Submit Button
        btn_label = "Update Profile" if self.is_edit_mode else "Save Student"
        btn_icon = ft.Icons.SAVE if self.is_edit_mode else ft.Icons.CHECK
        self.submit_btn_text = ft.Text(btn_label)
        self.submit_btn = ft.ElevatedButton(
            content=self.submit_btn_text,
            icon=btn_icon,
            style=ft.ButtonStyle(
                bgcolor=AppTheme.PRIMARY,
                color=AppTheme.SURFACE,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
            ),
            on_click=self.handle_submit,
        )

        self.cancel_btn = ft.TextButton(
            content=ft.Text("Cancel"),
            style=ft.ButtonStyle(color=AppTheme.TEXT_SECONDARY),
            on_click=self.close_modal,
        )

        # Modal Layout
        self.content = ft.Container(
            width=700,
            content=ft.Column(
                controls=[
                    self.error_container,
                    ft.Row(controls=[self.first_name_input, self.middle_name_input, self.last_name_input], spacing=AppTheme.PAD_SM),
                    ft.Row(controls=[self.mother_name_input, self.dob_input, self.gender_dropdown], spacing=AppTheme.PAD_SM),
                    ft.Row(controls=[self.mobile_input, self.email_input, self.aadhaar_input], spacing=AppTheme.PAD_SM),
                    ft.Row(controls=[self.parent_guardian_input, self.village_input], spacing=AppTheme.PAD_SM),
                    self.address_input,
                    ft.Row(controls=[self.qualification_input, self.blood_group_dropdown], spacing=AppTheme.PAD_SM),
                ],
                spacing=AppTheme.PAD_SM,
                tight=True,
                scroll=ft.ScrollMode.AUTO,
            ),
        )

        self.actions = [self.cancel_btn, self.submit_btn]
        self.actions_alignment = ft.MainAxisAlignment.END

    def _safe_update(self) -> None:
        try:
            if self.page:
                self.update()
        except RuntimeError:
            pass

    def _show_error(self, message: str) -> None:
        self.error_text.value = message
        self.error_container.visible = True
        self.submit_btn.disabled = False
        self.submit_btn_text.value = "Update Profile" if self.is_edit_mode else "Save Student"
        self._safe_update()

    def _clear_error(self) -> None:
        self.error_text.value = ""
        self.error_container.visible = False

    def handle_submit(self, e: ft.ControlEvent) -> None:
        self._clear_error()

        first_name = format_title_case(self.first_name_input.value)
        middle_name = format_title_case(self.middle_name_input.value)
        last_name = format_title_case(self.last_name_input.value)
        mother_name = format_title_case(self.mother_name_input.value)
        parent_guardian = format_title_case(self.parent_guardian_input.value)
        village = format_title_case(self.village_input.value)
        address = format_title_case(self.address_input.value)
        mobile = (self.mobile_input.value or "").strip()
        email = (self.email_input.value or "").strip().lower()
        aadhaar = (self.aadhaar_input.value or "").strip()
        dob = (self.dob_input.value or "").strip()
        gender = self.gender_dropdown.value
        qualification = (self.qualification_input.value or "").strip()
        blood_group = self.blood_group_dropdown.value

        if not first_name:
            self._show_error("First name is required.")
            return
        if not last_name:
            self._show_error("Last name is required.")
            return
        if not mobile:
            self._show_error("Mobile number is required.")
            return

        self.submit_btn.disabled = True
        self.submit_btn_text.value = "Saving..."
        self._safe_update()

        payload = {
            "first_name": first_name,
            "middle_name": middle_name or None,
            "last_name": last_name,
            "mother_name": mother_name or None,
            "parent_guardian_name": parent_guardian or None,
            "dob": dob or None,
            "gender": gender or None,
            "aadhaar_number": aadhaar or None,
            "village": village or None,
            "address": address or None,
            "qualification": qualification or None,
            "blood_group": blood_group or None,
            "mobile_number": mobile,
            "email": email if email else None,
        }

        try:
            if self.is_edit_mode and self.student:
                self.controller.update_student(self.student.id, payload)
            else:
                self.controller.create_student(payload)

            self.close_modal()
            self.on_saved()

        except (ValidationError, ConflictError, ServiceError) as ex:
            self._show_error(str(ex))
        except Exception as ex:
            LogService.error(f"Unexpected error in student form: {ex}", context=self.__class__.__name__)
            self._show_error("An unexpected error occurred. Please try again.")

    def close_modal(self, e: Optional[ft.ControlEvent] = None) -> None:
        try:
            if self.page:
                self.page.pop_dialog()
        except RuntimeError:
            pass
