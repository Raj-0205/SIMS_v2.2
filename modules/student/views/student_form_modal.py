# modules/student/views/student_form_modal.py

from __future__ import annotations
from typing import Callable, Optional
import flet as ft

from core.exceptions import ValidationError, ConflictError, ServiceError
from core.logger.service import LogService
from modules.student.controller import StudentController
from modules.student.dto import StudentDTO
from ui.themes.theme import AppTheme

__all__ = ["StudentFormModal"]


class StudentFormModal(ft.AlertDialog):
    """
    Unified Add/Edit Modal Dialog for Student entity.
    Supports form-level validations, live feedback, double-click protection,
    and clean conflict error handling without modal closure.
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

        # Modal Title
        title_text = "Edit Student Profile" if self.is_edit_mode else "Register New Student"
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

        # Form Input Fields
        self.first_name_input = ft.TextField(
            label="First Name *",
            hint_text="e.g. Rahul",
            value=student.first_name if student else "",
            autofocus=True,
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
        )

        self.last_name_input = ft.TextField(
            label="Last Name *",
            hint_text="e.g. Sharma",
            value=student.last_name if student else "",
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
        )

        self.mobile_input = ft.TextField(
            label="Mobile Number (Optional)",
            hint_text="10-digit mobile number",
            value=student.mobile_number or "" if student else "",
            keyboard_type=ft.KeyboardType.PHONE,
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
            prefix_icon=ft.Icons.PHONE,
        )

        self.email_input = ft.TextField(
            label="Email Address (Optional)",
            hint_text="e.g. student@example.com",
            value=student.email or "" if student else "",
            keyboard_type=ft.KeyboardType.EMAIL,
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
            prefix_icon=ft.Icons.EMAIL,
        )

        # Error / Notification Banner
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
        btn_label = "Update Student" if self.is_edit_mode else "Save Student"
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
            style=ft.ButtonStyle(
                color=AppTheme.TEXT_SECONDARY,
            ),
            on_click=self.close_modal,
        )

        # Modal Layout
        self.content = ft.Container(
            width=460,
            content=ft.Column(
                controls=[
                    self.error_container,
                    self.first_name_input,
                    self.last_name_input,
                    self.mobile_input,
                    self.email_input,
                ],
                spacing=AppTheme.PAD_MD,
                tight=True,
            ),
        )

        self.actions = [self.cancel_btn, self.submit_btn]
        self.actions_alignment = ft.MainAxisAlignment.END

    def _safe_update(self) -> None:
        """Safely updates control if mounted on page tree."""
        try:
            self.update()
        except RuntimeError:
            pass

    def _show_error(self, message: str) -> None:
        self.error_text.value = message
        self.error_container.visible = True
        self.submit_btn.disabled = False
        self.submit_btn_text.value = "Update Student" if self.is_edit_mode else "Save Student"
        self._safe_update()

    def _clear_error(self) -> None:
        self.error_text.value = ""
        self.error_container.visible = False

    def handle_submit(self, e: ft.ControlEvent) -> None:
        """Processes form submission with double-click protection and error handling."""
        self._clear_error()

        # UI-level validation
        first_name = (self.first_name_input.value or "").strip()
        last_name = (self.last_name_input.value or "").strip()
        mobile = (self.mobile_input.value or "").strip()
        email = (self.email_input.value or "").strip()

        if not first_name:
            self._show_error("First name is required.")
            return
        if not last_name:
            self._show_error("Last name is required.")
            return

        # Double-click lock: Set button state to saving
        self.submit_btn.disabled = True
        self.submit_btn_text.value = "Saving..."
        self._safe_update()

        payload = {
            "first_name": first_name,
            "last_name": last_name,
            "mobile_number": mobile if mobile else None,
            "email": email if email else None,
        }

        try:
            if self.is_edit_mode and self.student:
                self.controller.update_student(self.student.id, payload)
            else:
                self.controller.create_student(payload)

            # Success: Trigger parent refresh and close modal
            self.on_saved()
            self.close_modal()

        except (ValidationError, ConflictError, ServiceError) as ex:
            # Business / Validation Conflict (e.g. Duplicate Mobile HARD BLOCK)
            self._show_error(str(ex))
        except Exception as ex:
            LogService.error(
                f"Unexpected error during student form submission: {ex}",
                context=self.__class__.__name__,
            )
            self._show_error("An unexpected error occurred. Please try again.")

    def close_modal(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Closes the dialog safely."""
        self.open = False
        try:
            if self.page:
                self.page.pop_dialog()
        except RuntimeError:
            pass
