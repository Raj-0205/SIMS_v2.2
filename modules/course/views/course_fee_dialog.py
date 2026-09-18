# modules/course/views/course_fee_dialog.py

from __future__ import annotations
from typing import Callable, Optional
import flet as ft

from core.logger.service import LogService
from core.exceptions import ValidationError, ConflictError, ServiceError
from ui.themes.theme import AppTheme
from modules.course.controller import CourseController
from modules.course.dto import CourseDTO

__all__ = ["CourseFeeDialog"]


class CourseFeeDialog(ft.AlertDialog):
    """
    Authorized Institute Course Fee Revision Dialog.
    Enforces Admin PIN step-up authentication, reason validation, and no-op rejection.
    """

    def __init__(
        self,
        course: CourseDTO,
        on_fee_updated: Optional[Callable[[int], None]] = None,
        page: Optional[ft.Page] = None,
    ) -> None:
        super().__init__(modal=True)

        self.course = course
        self.on_fee_updated = on_fee_updated or (lambda cid: None)
        self._root_page = page
        self.controller = CourseController()

        # Dialog Header
        self.title = ft.Row(
            controls=[
                ft.Icon(ft.Icons.LOCK, color=AppTheme.PRIMARY, size=24),
                ft.Text(
                    "Change Institute Course Fee",
                    size=AppTheme.SIZE_H2,
                    weight=ft.FontWeight.W_600,
                    color=AppTheme.TEXT_PRIMARY,
                ),
            ],
            spacing=AppTheme.PAD_SM,
        )

        # Course Summary Box
        summary_box = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("Course:", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_BODY),
                            ft.Text(f"{self.course.name} ({self.course.code})", size=AppTheme.SIZE_BODY, color=AppTheme.PRIMARY, weight=ft.FontWeight.W_600),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Row(
                        controls=[
                            ft.Text("Current Institute Fee:", size=AppTheme.SIZE_BODY),
                            ft.Text(
                                f"₹{self.course.base_fee:,.2f}",
                                size=AppTheme.SIZE_BODY,
                                weight=ft.FontWeight.BOLD,
                                color=AppTheme.SUCCESS,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ],
                spacing=4,
            ),
            bgcolor=AppTheme.SURFACE_VARIANT,
            padding=ft.Padding(14, 10, 14, 10),
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        # Explanatory Notice
        notice_box = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.INFO_OUTLINE, color=AppTheme.PRIMARY, size=18),
                    ft.Text(
                        "This changes the default fee for NEW admissions. "
                        "Existing admission fees remain unchanged.",
                        size=AppTheme.SIZE_CAPTION,
                        color=AppTheme.TEXT_SECONDARY,
                        expand=True,
                    ),
                ],
                spacing=8,
            ),
            bgcolor=AppTheme.PRIMARY_LIGHT,
            padding=ft.Padding(10, 8, 10, 8),
            border_radius=AppTheme.RADIUS_SM,
        )

        # New Fee Input
        self.new_fee_input = ft.TextField(
            label="New Institute Fee (₹) *",
            hint_text="e.g. 5000",
            keyboard_type=ft.KeyboardType.NUMBER,
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
            prefix_icon=ft.Icons.CURRENCY_RUPEE,
            autofocus=True,
        )

        # Reason Input
        self.reason_input = ft.TextField(
            label="Reason for Revision *",
            hint_text="e.g. Annual fee adjustment 2026, Updated curriculum",
            multiline=True,
            min_lines=2,
            max_lines=3,
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
        )

        # Admin PIN Input
        self.pin_input = ft.TextField(
            label="Administrator PIN *",
            hint_text="Enter 4-digit Admin PIN",
            password=True,
            can_reveal_password=True,
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
            prefix_icon=ft.Icons.PASSWORD,
        )

        # Error Container
        self.error_text = ft.Text("", color=AppTheme.DANGER, size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.W_500)
        self.error_container = ft.Container(
            content=self.error_text,
            visible=False,
            padding=ft.Padding(8, 4, 8, 4),
        )

        self.content = ft.Container(
            content=ft.Column(
                controls=[
                    summary_box,
                    notice_box,
                    self.new_fee_input,
                    self.reason_input,
                    self.pin_input,
                    self.error_container,
                ],
                spacing=AppTheme.PAD_MD,
                tight=True,
            ),
            width=480,
            padding=ft.Padding(0, 8, 0, 0),
        )

        # Action Buttons
        self.submit_btn = ft.ElevatedButton(
            content=ft.Text("Authorize & Update Fee"),
            icon=ft.Icons.CHECK_CIRCLE,
            bgcolor=AppTheme.PRIMARY,
            color=AppTheme.SURFACE,
            on_click=self.handle_submit,
        )
        self.cancel_btn = ft.TextButton(
            content=ft.Text("Cancel"),
            on_click=self.close_dialog,
        )
        self.actions = [self.cancel_btn, self.submit_btn]

    def _show_error(self, message: str) -> None:
        self.error_text.value = f"⚠ {message}"
        self.error_container.visible = True
        self.update()

    def handle_submit(self, e: ft.ControlEvent) -> None:
        """Validates inputs and commits authorized fee change."""
        self.error_container.visible = False
        raw_fee = self.new_fee_input.value
        raw_reason = self.reason_input.value
        raw_pin = self.pin_input.value

        if not raw_fee or not raw_fee.strip():
            self._show_error("New Institute Fee is required.")
            return

        try:
            fee_val = float(raw_fee.strip())
        except ValueError:
            self._show_error("Please enter a valid numeric fee amount.")
            return

        if fee_val < 0.0:
            self._show_error("Institute Fee cannot be negative.")
            return

        if abs(fee_val - self.course.base_fee) < 0.001:
            self._show_error("New fee cannot be identical to the current fee.")
            return

        if not raw_reason or len(raw_reason.strip()) < 3:
            self._show_error("Please provide a valid reason (minimum 3 characters).")
            return

        if not raw_pin or not raw_pin.strip():
            self._show_error("Administrator PIN is required.")
            return

        # Resolve actor identity from SecurityContext or session if available
        from core.security.context import SecurityContext
        from core.security.auth import AuthService

        actor_username = SecurityContext.get_current_username() or "Administrator"
        actor_user_id = SecurityContext.get_current_user_id()
        if (not actor_username or actor_username == "Administrator") and self._root_page:
            sess = AuthService._get_session(self._root_page)
            sess_user = AuthService._session_get(sess, "username")
            if sess_user:
                actor_username = str(sess_user)
            sess_uid = AuthService._session_get(sess, "user_id")
            if sess_uid is not None:
                try:
                    actor_user_id = int(sess_uid)
                except (ValueError, TypeError):
                    pass

        payload = {
            "new_fee": fee_val,
            "reason": raw_reason.strip(),
            "admin_pin": raw_pin.strip(),
        }

        try:
            self.submit_btn.disabled = True
            self.update()

            self.controller.change_institute_fee(
                course_id=self.course.id,
                raw_data=payload,
                user_id=actor_user_id,
                username=actor_username,
            )

            LogService.info(
                f"Fee revision successful for Course #{self.course.id}.",
                context=self.__class__.__name__,
            )

            self.on_fee_updated(self.course.id)
            self.close_dialog()

        except (ValidationError, ConflictError, ServiceError) as exc:
            self.submit_btn.disabled = False
            self._show_error(str(exc))
        except Exception as exc:
            self.submit_btn.disabled = False
            self._show_error(f"Unexpected error: {exc}")

    def close_dialog(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Closes the modal safely using Flet's pop_dialog."""
        try:
            if self.page:
                self.page.pop_dialog()
            elif self._root_page:
                self._root_page.pop_dialog()
        except RuntimeError:
            pass
