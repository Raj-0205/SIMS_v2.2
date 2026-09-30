# modules/batch/views/batch_form_modal.py

from __future__ import annotations
from typing import Callable, Optional
import flet as ft

from core.logger.service import LogService
from core.exceptions import ValidationError, ConflictError, ServiceError
from ui.themes.theme import AppTheme
from modules.batch.controller import BatchController
from modules.batch.constants import BatchStatus
from modules.batch.dto import BatchDTO
from modules.course.controller import CourseController

__all__ = ["BatchFormModal"]


class BatchFormModal(ft.AlertDialog):
    """
    Modal dialog for creating a new batch or updating an existing batch.
    Validates course selection, unique batch name, timing, positive capacity,
    and valid ISO dates.
    """

    def __init__(
        self,
        batch: Optional[BatchDTO] = None,
        on_saved: Optional[Callable[[int], None]] = None,
        preselected_course_id: Optional[int] = None,
    ) -> None:
        super().__init__(modal=True)

        self.batch = batch
        self.is_edit = batch is not None
        self.on_saved = on_saved or (lambda bid: None)
        self.preselected_course_id = preselected_course_id
        self.controller = BatchController()
        self.course_controller = CourseController()

        # Dialog Title
        title_text = "Edit Batch" if self.is_edit else "Create New Batch"
        icon_name = ft.Icons.EDIT if self.is_edit else ft.Icons.GROUP_ADD
        self.title = ft.Row(
            controls=[
                ft.Icon(icon_name, color=AppTheme.PRIMARY, size=24),
                ft.Text(
                    title_text,
                    size=AppTheme.SIZE_H2,
                    weight=ft.FontWeight.W_600,
                    color=AppTheme.TEXT_PRIMARY,
                ),
            ],
            spacing=AppTheme.PAD_SM,
        )

        # 1. Course Dropdown
        courses, _ = self.course_controller.list_courses(limit=200)
        course_options = [
            ft.DropdownOption(key=str(c.id), text=f"{c.name} ({c.code})") for c in courses
        ]
        selected_course = str(self.batch.course_id) if self.batch else (
            str(self.preselected_course_id) if self.preselected_course_id else (
                course_options[0].key if course_options else None
            )
        )

        self.course_dropdown = ft.Dropdown(
            label="Course *",
            options=course_options,
            value=selected_course,
            border_radius=AppTheme.RADIUS_MD,
            disabled=self.is_edit,  # Course locked in edit mode to preserve relational integrity
        )

        # 2. Batch Name
        self.name_input = ft.TextField(
            label="Batch Name *",
            hint_text="e.g. Morning Batch A, FastTrack Weekend",
            value=self.batch.batch_name if self.batch else "",
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
            autofocus=not self.is_edit,
        )

        # 3. Batch Code (Optional)
        self.code_input = ft.TextField(
            label="Batch Code",
            hint_text="e.g. BAT-2026-01",
            value=self.batch.batch_code if self.batch and self.batch.batch_code else "",
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
            capitalization=ft.TextCapitalization.CHARACTERS,
        )

        # 4. Timing
        self.timing_input = ft.TextField(
            label="Timing *",
            hint_text="e.g. 09:00 AM - 10:30 AM, 04:00 PM - 05:30 PM",
            value=self.batch.timing if self.batch else "",
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
        )

        # 5. Max Capacity
        self.capacity_input = ft.TextField(
            label="Max Student Capacity *",
            hint_text="30",
            value=str(self.batch.max_capacity) if self.batch else "30",
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        # 6. Status Dropdown
        status_options = [
            ft.DropdownOption(key=s.value, text=s.value) for s in BatchStatus
        ]
        initial_status = self.batch.status.value if self.batch else BatchStatus.OPEN.value
        self.status_dropdown = ft.Dropdown(
            label="Batch Status *",
            options=status_options,
            value=initial_status,
            border_radius=AppTheme.RADIUS_MD,
        )

        # 7. Start & End Dates
        self.start_date_input = ft.TextField(
            label="Start Date",
            hint_text="YYYY-MM-DD",
            value=self.batch.start_date if self.batch and self.batch.start_date else "",
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
        )

        self.end_date_input = ft.TextField(
            label="End Date",
            hint_text="YYYY-MM-DD",
            value=self.batch.end_date if self.batch and self.batch.end_date else "",
            border_radius=AppTheme.RADIUS_MD,
            text_size=AppTheme.SIZE_BODY,
        )

        # Error notification banner
        self.error_text = ft.Text("", size=AppTheme.SIZE_CAPTION, color=AppTheme.DANGER)
        self.error_banner = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE, size=16, color=AppTheme.DANGER),
                    self.error_text,
                ],
                spacing=8,
            ),
            padding=ft.Padding(8, 6, 8, 6),
            bgcolor=AppTheme.DANGER_LIGHT,
            border_radius=AppTheme.RADIUS_SM,
            visible=False,
        )

        # Assemble Form Content
        self.content = ft.Container(
            width=580,
            content=ft.Column(
                controls=[
                    self.error_banner,
                    self.course_dropdown,
                    ft.Row(
                        controls=[
                            ft.Container(self.name_input, expand=2),
                            ft.Container(self.code_input, expand=1),
                        ],
                        spacing=AppTheme.PAD_SM,
                    ),
                    ft.Row(
                        controls=[
                            ft.Container(self.timing_input, expand=2),
                            ft.Container(self.capacity_input, expand=1),
                        ],
                        spacing=AppTheme.PAD_SM,
                    ),
                    self.status_dropdown,
                    ft.Row(
                        controls=[
                            ft.Container(self.start_date_input, expand=1),
                            ft.Container(self.end_date_input, expand=1),
                        ],
                        spacing=AppTheme.PAD_SM,
                    ),
                ],
                spacing=AppTheme.PAD_MD,
                tight=True,
            ),
            padding=ft.Padding(0, AppTheme.PAD_SM, 0, AppTheme.PAD_SM),
        )

        # Actions
        self.cancel_btn = ft.TextButton("Cancel", on_click=self.close_dialog)
        self.save_btn = ft.ElevatedButton(
            "Update Batch" if self.is_edit else "Create Batch",
            icon=ft.Icons.SAVE,
            style=ft.ButtonStyle(bgcolor=AppTheme.PRIMARY, color=AppTheme.SURFACE),
            on_click=self.handle_save,
        )

        self.actions = [self.cancel_btn, self.save_btn]
        self.actions_alignment = ft.MainAxisAlignment.END

    def show_error(self, message: str) -> None:
        self.error_text.value = message
        self.error_banner.visible = True
        try:
            self.update()
        except RuntimeError:
            pass

    def clear_error(self) -> None:
        self.error_banner.visible = False
        try:
            self.update()
        except RuntimeError:
            pass

    def handle_save(self, e: ft.ControlEvent) -> None:
        self.clear_error()

        course_id_str = self.course_dropdown.value
        if not course_id_str:
            self.show_error("Please select a course.")
            return

        batch_name = (self.name_input.value or "").strip()
        if not batch_name or len(batch_name) < 2:
            self.show_error("Batch name must be at least 2 characters.")
            return

        timing = (self.timing_input.value or "").strip()
        if not timing:
            self.show_error("Batch timing is required.")
            return

        raw_cap = (self.capacity_input.value or "").strip()
        try:
            capacity = int(raw_cap)
            if capacity <= 0:
                self.show_error("Max capacity must be greater than 0.")
                return
        except ValueError:
            self.show_error("Max capacity must be a valid number.")
            return

        payload = {
            "course_id": int(course_id_str),
            "batch_name": batch_name,
            "batch_code": (self.code_input.value or "").strip() or None,
            "timing": timing,
            "max_capacity": capacity,
            "status": self.status_dropdown.value or "OPEN",
            "start_date": (self.start_date_input.value or "").strip() or None,
            "end_date": (self.end_date_input.value or "").strip() or None,
        }

        try:
            if self.is_edit and self.batch:
                self.controller.update_batch(self.batch.id, payload)
                batch_id = self.batch.id
            else:
                batch_id = self.controller.create_batch(payload)

            self.close_dialog()
            self.on_saved(batch_id)
        except (ValidationError, ConflictError, ServiceError) as ex:
            self.show_error(str(ex))
        except Exception as ex:
            LogService.error(f"Unexpected error saving batch: {ex}", context=self.__class__.__name__)
            self.show_error(f"Failed to save batch: {ex}")

    @property
    def safe_page(self) -> Optional[ft.Page]:
        try:
            return getattr(self, "_root_page", None) or self.page or getattr(self, "_page", None)
        except (RuntimeError, AttributeError):
            return getattr(self, "_root_page", None) or getattr(self, "_page", None)

    def close_dialog(self, _=None) -> None:
        p = self.safe_page
        if p:
            try:
                p.pop_dialog()
            except RuntimeError:
                pass
