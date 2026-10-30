# modules/admission/views/batch_assignment_dialog.py

from __future__ import annotations
from typing import Callable, Optional
import flet as ft

from core.logger.service import LogService
from core.exceptions import ValidationError, ServiceError
from modules.admission.controller import AdmissionController
from modules.admission.dto import AdmissionDTO
from modules.batch.service import BatchService
from ui.themes.theme import AppTheme

__all__ = ["BatchAssignmentDialog"]


class BatchAssignmentDialog(ft.AlertDialog):
    """
    Modern modal dialog for:
    1. Allocating a batch to an unallocated / unassigned candidate.
    2. Switching an existing student from Batch A to Batch B.
    Enforces course-level batch filtering, live seat capacity inspection, and audit logging.
    """

    def __init__(
        self,
        admission_id: int,
        on_updated: Optional[Callable[[], None]] = None,
        page: Optional[ft.Page] = None,
    ) -> None:
        super().__init__()

        self.admission_id = admission_id
        self.on_updated = on_updated
        self._root_page = page
        self.modal = True

        self.adm_controller = AdmissionController()
        self.batch_service = BatchService()

        # Load admission info
        try:
            self.admission: Optional[AdmissionDTO] = self.adm_controller.get_admission(self.admission_id)
        except Exception as ex:
            LogService.error(f"Failed to fetch admission #{admission_id} for batch assignment: {ex}", context="BatchAssignmentDialog")
            self.admission = None

        is_currently_allocated = bool(self.admission and self.admission.batch_id)
        action_verb = "Switch Batch" if is_currently_allocated else "Assign Batch"

        self.title = ft.SelectionArea(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        ft.Icons.SWAP_HORIZ if is_currently_allocated else ft.Icons.CLASS_,
                        color=AppTheme.PRIMARY,
                        size=24,
                    ),
                    ft.Column(
                        controls=[
                            ft.Text(action_verb, size=AppTheme.SIZE_H2, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                            ft.Text(
                                "Allocate unassigned student or change class timing",
                                size=AppTheme.SIZE_CAPTION,
                                color=AppTheme.TEXT_SECONDARY,
                            ),
                        ],
                        spacing=2,
                    ),
                ],
                spacing=AppTheme.PAD_SM,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        # ── Error / Alert Banner ──
        self.error_banner = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE, size=18, color=AppTheme.DANGER),
                    ft.Text("", size=AppTheme.SIZE_CAPTION, color=AppTheme.DANGER, expand=True),
                ],
                spacing=AppTheme.PAD_XS,
            ),
            bgcolor=AppTheme.DANGER_LIGHT,
            padding=ft.Padding(10, 8, 10, 8),
            border_radius=AppTheme.RADIUS_SM,
            visible=False,
        )

        # ── Student / Course Summary Card ──
        stud_name = self.admission.student_name if self.admission else f"Admission #{self.admission_id}"
        cand_num = self.admission.admission_number if self.admission else "—"
        course_name = self.admission.course_name if self.admission else "—"
        curr_batch_name = self.admission.batch_name if (self.admission and self.admission.batch_name) else "Unallocated (No Batch)"

        self.summary_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("Student:", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_SECONDARY, width=90),
                            ft.Text(stud_name, size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                            ft.Container(
                                content=ft.Text(f"#{cand_num}", size=11, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                                bgcolor=AppTheme.PRIMARY_LIGHT,
                                padding=ft.Padding(6, 2, 6, 2),
                                border_radius=AppTheme.RADIUS_SM,
                            ),
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        controls=[
                            ft.Text("Course:", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_SECONDARY, width=90),
                            ft.Text(course_name, size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_PRIMARY),
                        ],
                        spacing=6,
                    ),
                    ft.Row(
                        controls=[
                            ft.Text("Current Batch:", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_SECONDARY, width=90),
                            ft.Container(
                                content=ft.Text(
                                    curr_batch_name,
                                    size=11,
                                    weight=ft.FontWeight.BOLD,
                                    color=AppTheme.SUCCESS if is_currently_allocated else AppTheme.WARNING,
                                ),
                                bgcolor=AppTheme.SUCCESS_LIGHT if is_currently_allocated else AppTheme.WARNING_LIGHT,
                                padding=ft.Padding(6, 2, 6, 2),
                                border_radius=AppTheme.RADIUS_SM,
                            ),
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=6,
            ),
            bgcolor=AppTheme.SURFACE_VARIANT,
            padding=ft.Padding(12, 10, 12, 10),
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        # ── Target Batch Dropdown ──
        self.batch_dropdown = ft.Dropdown(
            label="Select New Batch *",
            options=self._load_batch_options(),
            value=str(self.admission.batch_id) if (self.admission and self.admission.batch_id) else "NONE",
            text_size=AppTheme.SIZE_BODY,
            border_radius=AppTheme.RADIUS_MD,
            border_color=AppTheme.BORDER,
            focused_border_color=AppTheme.PRIMARY,
            on_select=self._on_batch_selected,
            expand=True,
        )

        # ── Capacity & Timing Details Card ──
        self.capacity_info_card = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.PEOPLE_ALT_OUTLINED, size=16, color=AppTheme.PRIMARY),
                    ft.Text("", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_PRIMARY, expand=True),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=ft.Padding(10, 8, 10, 8),
            border_radius=AppTheme.RADIUS_SM,
            border=ft.Border.all(1, AppTheme.BORDER),
            visible=False,
        )

        self.content = ft.Container(
            content=ft.Column(
                controls=[
                    self.error_banner,
                    self.summary_card,
                    ft.Text("Target Allocation", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_SECONDARY),
                    self.batch_dropdown,
                    self.capacity_info_card,
                ],
                spacing=AppTheme.PAD_SM,
                tight=True,
            ),
            width=500,
        )

        # ── Footer Actions ──
        self.cancel_btn = ft.TextButton(
            content=ft.Text("Cancel"),
            on_click=self.close_dialog,
        )
        self.save_btn = ft.ElevatedButton(
            content=ft.Text(f"Save {action_verb}"),
            icon=ft.Icons.CHECK,
            style=ft.ButtonStyle(
                bgcolor=AppTheme.PRIMARY,
                color=AppTheme.SURFACE,
                padding=ft.Padding(16, 10, 16, 10),
            ),
            on_click=self._handle_save,
        )

        self.actions = [self.cancel_btn, self.save_btn]
        self.actions_alignment = ft.MainAxisAlignment.END

        # Initial evaluation of selected batch capacity
        if self.admission and self.admission.batch_id:
            self._update_capacity_display(self.admission.batch_id)

    @property
    def safe_page(self) -> Optional[ft.Page]:
        try:
            return self._root_page or getattr(self, "page", None)
        except (RuntimeError, AttributeError):
            return self._root_page

    def _safe_update(self) -> None:
        p = self.safe_page
        if p:
            try:
                self.update()
            except Exception:
                pass

    def _show_error(self, message: str) -> None:
        row: ft.Row = self.error_banner.content
        row.controls[1].value = message
        self.error_banner.visible = True
        self._safe_update()

    def _clear_error(self) -> None:
        self.error_banner.visible = False
        self._safe_update()

    def _load_batch_options(self) -> list[ft.DropdownOption]:
        options = [ft.DropdownOption(key="NONE", text="— Unassign / Mark Unallocated —")]

        if not self.admission:
            return options

        try:
            batches, _ = self.batch_service.list_batches(limit=200)
            course_id = self.admission.course_id if self.admission else None

            # Prioritize matching course batches first, followed by other active batches
            matching_course_batches = []
            other_batches = []

            for b in batches:
                status_str = b.status.value if hasattr(b.status, "value") else str(b.status).upper()
                if status_str in ("OPEN", "ACTIVE"):
                    if course_id and b.course_id == course_id:
                        matching_course_batches.append(b)
                    else:
                        other_batches.append(b)

            all_eligible = matching_course_batches + other_batches

            for b in all_eligible:
                # Capacity lookup
                try:
                    cap = self.batch_service.get_capacity_summary(b.id)
                    cap_text = f"{cap.enrolled_count}/{cap.max_capacity} filled ({cap.available_capacity} left)"
                except Exception:
                    cap_text = f"Max: {b.max_capacity}"

                timing_text = f" | {b.timing}" if b.timing else ""
                is_diff_course = (course_id and b.course_id != course_id)
                course_tag = f"[{b.course_name}] " if (is_diff_course and getattr(b, "course_name", None)) else ""
                options.append(
                    ft.DropdownOption(
                        key=str(b.id),
                        text=f"{course_tag}{b.batch_name}{timing_text}  [{cap_text}]",
                    )
                )
        except Exception as ex:
            LogService.error(f"Failed to load batch options: {ex}", context="BatchAssignmentDialog")

        return options

    def _on_batch_selected(self, e: ft.ControlEvent) -> None:
        self._clear_error()
        val = self.batch_dropdown.value
        if not val or val == "NONE":
            self.capacity_info_card.visible = False
            self._safe_update()
            return

        try:
            batch_id = int(val)
            self._update_capacity_display(batch_id)
        except (ValueError, TypeError):
            self.capacity_info_card.visible = False
            self._safe_update()

    def _update_capacity_display(self, batch_id: int) -> None:
        try:
            cap = self.batch_service.get_capacity_summary(batch_id)
            row: ft.Row = self.capacity_info_card.content
            if cap.available_capacity <= 0:
                row.controls[0].name = ft.Icons.WARNING_AMBER
                row.controls[0].color = AppTheme.DANGER
                row.controls[1].value = f"⚠️ Batch is FULL ({cap.enrolled_count}/{cap.max_capacity} enrolled). Seats depleted."
                row.controls[1].color = AppTheme.DANGER
                self.capacity_info_card.bgcolor = AppTheme.DANGER_LIGHT
            else:
                row.controls[0].name = ft.Icons.CHECK_CIRCLE_OUTLINE
                row.controls[0].color = AppTheme.SUCCESS
                row.controls[1].value = f"Available Seats: {cap.available_capacity} of {cap.max_capacity} remaining (Enrolled: {cap.enrolled_count})"
                row.controls[1].color = AppTheme.SUCCESS
                self.capacity_info_card.bgcolor = AppTheme.SUCCESS_LIGHT

            self.capacity_info_card.visible = True
            self._safe_update()
        except Exception as ex:
            LogService.warning(f"Could not load capacity for batch #{batch_id}: {ex}", context="BatchAssignmentDialog")
            self.capacity_info_card.visible = False
            self._safe_update()

    def _handle_save(self, e: ft.ControlEvent) -> None:
        self._clear_error()
        val = self.batch_dropdown.value
        new_batch_id: Optional[int] = None
        if val and val != "NONE":
            try:
                new_batch_id = int(val)
            except ValueError:
                self._show_error("Please select a valid batch option.")
                return

        # Check if already assigned to this exact batch
        curr_batch_id = self.admission.batch_id if self.admission else None
        if new_batch_id == curr_batch_id:
            self._show_error("Student is already assigned to this batch. Please select a different batch to switch.")
            return

        self.save_btn.disabled = True
        self.save_btn.content = ft.Row(
            controls=[ft.ProgressRing(width=16, height=16, stroke_width=2, color=AppTheme.SURFACE), ft.Text("Updating...")],
            spacing=6,
            tight=True,
        )
        self._safe_update()

        try:
            self.adm_controller.reassign_batch(self.admission_id, new_batch_id)
            LogService.info(f"Successfully reassigned admission #{self.admission_id} to batch ID {new_batch_id}", context="BatchAssignmentDialog")

            # Close modal
            p = self.safe_page
            self.open = False
            if p:
                if hasattr(p, "pop_dialog"):
                    try:
                        p.pop_dialog()
                    except Exception:
                        pass
                # Toast notification
                batch_text = "unallocated" if not new_batch_id else "new batch"
                p.show_snack_bar(
                    ft.SnackBar(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.CHECK_CIRCLE, color=AppTheme.SUCCESS),
                                ft.Text(f"Student successfully moved to {batch_text}!", color=AppTheme.SURFACE, weight=ft.FontWeight.BOLD),
                            ],
                            spacing=AppTheme.PAD_SM,
                        ),
                        bgcolor=AppTheme.PRIMARY,
                        duration=3000,
                    )
                )

            if self.on_updated:
                self.on_updated()

        except ValidationError as vex:
            self._show_error(str(vex))
            self.save_btn.disabled = False
            self.save_btn.content = ft.Text("Save Batch Assignment")
            self._safe_update()
        except Exception as ex:
            LogService.error(f"Error reassigning batch: {ex}", context="BatchAssignmentDialog")
            self._show_error(f"Failed to update batch: {ex}")
            self.save_btn.disabled = False
            self.save_btn.content = ft.Text("Save Batch Assignment")
            self._safe_update()

    def close_dialog(self, e: Optional[ft.ControlEvent] = None) -> None:
        p = self.safe_page
        self.open = False
        if p and hasattr(p, "pop_dialog"):
            try:
                p.pop_dialog()
            except Exception:
                pass
        self._safe_update()
