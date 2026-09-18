# modules/course/views/course_detail_dialog.py

from __future__ import annotations
from typing import Callable, Optional
import flet as ft

from core.logger.service import LogService
from core.exceptions import ValidationError, ConflictError, ServiceError
from ui.themes.theme import AppTheme
from modules.course.controller import CourseController
from modules.course.dto import CourseDTO, CourseFeeHistoryDTO, CourseOperationalSummaryDTO
from modules.course.views.course_fee_dialog import CourseFeeDialog
from modules.course.views.course_form_modal import CourseFormModal

__all__ = ["CourseDetailDialog"]


class CourseDetailDialog(ft.AlertDialog):
    """
    Comprehensive Course Detail Workspace Dialog.
    Displays course profile, institute fee, fee revision history, operations, and admin actions.
    """

    def __init__(
        self,
        course_id: int,
        on_course_mutated: Optional[Callable[[], None]] = None,
        page: Optional[ft.Page] = None,
    ) -> None:
        super().__init__(modal=True)

        self.course_id = course_id
        self.on_course_mutated = on_course_mutated or (lambda: None)
        self._root_page = page
        self.controller = CourseController()

        self.course: CourseDTO = self.controller.get_course(self.course_id)
        self.summary: CourseOperationalSummaryDTO = self.controller.get_operational_summary(self.course_id)
        self.fee_history: list[CourseFeeHistoryDTO] = self.controller.get_fee_history(self.course_id)

        # Dialog Title & Header
        status_color = AppTheme.SUCCESS if self.course.is_active else AppTheme.TEXT_MUTED
        status_text = "ACTIVE" if self.course.is_active else "INACTIVE"

        self.title = ft.Row(
            controls=[
                ft.Icon(ft.Icons.SCHOOL, color=AppTheme.PRIMARY, size=26),
                ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Text(
                                    self.course.name,
                                    size=AppTheme.SIZE_H2,
                                    weight=ft.FontWeight.BOLD,
                                    color=AppTheme.TEXT_PRIMARY,
                                ),
                                ft.Container(
                                    content=ft.Text(self.course.code, size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                                    bgcolor=AppTheme.PRIMARY_LIGHT,
                                    padding=ft.Padding(8, 2, 8, 2),
                                    border_radius=AppTheme.RADIUS_SM,
                                ),
                                ft.Container(
                                    content=ft.Text(f"● {status_text}", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD, color=status_color),
                                    bgcolor=AppTheme.SURFACE_VARIANT,
                                    padding=ft.Padding(8, 2, 8, 2),
                                    border_radius=AppTheme.RADIUS_SM,
                                    border=ft.Border.all(1, AppTheme.BORDER),
                                ),
                            ],
                            spacing=AppTheme.PAD_SM,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Text(f"Category: {self.course.category}  |  Duration: {self.course.duration or 'Self-paced'}", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                    ],
                    spacing=2,
                ),
            ],
            spacing=AppTheme.PAD_SM,
        )

        # Build Body Content
        self.content = ft.Container(
            content=self._build_body(),
            width=650,
            height=500,
            padding=ft.Padding(0, 8, 0, 0),
        )

        # Action Buttons
        self.actions = [
            ft.TextButton(content=ft.Text("Close"), on_click=self.close_dialog),
        ]

    def _build_body(self) -> ft.Control:
        """Constructs all workspace panels."""
        # 1. Pricing Box
        pricing_box = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text("Institute Admission Fee", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY, weight=ft.FontWeight.W_500),
                            ft.Text(f"₹{self.course.base_fee:,.2f}", size=22, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                            ft.Text("Default fee for new admissions", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED, italic=True),
                        ],
                        spacing=2,
                    ),
                    ft.ElevatedButton(
                        content=ft.Text("Change Fee"),
                        icon=ft.Icons.LOCK,
                        bgcolor=AppTheme.PRIMARY,
                        color=AppTheme.SURFACE,
                        on_click=self._handle_change_fee_click,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=AppTheme.SURFACE_VARIANT,
            padding=ft.Padding(16, 12, 16, 12),
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        # 2. Operational Metrics
        operational_metrics = ft.Row(
            controls=[
                self._metric_tile("Total Batches", str(self.summary.batch_count), ft.Icons.GROUP_WORK),
                self._metric_tile("Active Batches", str(self.summary.active_batch_count), ft.Icons.CHECK_CIRCLE_OUTLINE),
                self._metric_tile("Total Enrollments", str(self.summary.total_admissions_count), ft.Icons.APP_REGISTRATION),
            ],
            spacing=AppTheme.PAD_SM,
        )

        # 3. Description Box
        desc_text = self.course.description or "No additional syllabus notes or description provided for this course."
        desc_box = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Course Overview & Syllabus Highlights", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD),
                    ft.Text(desc_text, size=AppTheme.SIZE_BODY, color=AppTheme.TEXT_SECONDARY),
                ],
                spacing=4,
            ),
            padding=ft.Padding(4, 0, 4, 0),
        )

        # 4. Fee Audit History List
        fee_history_list = ft.ListView(
            spacing=6,
            height=130,
            controls=self._build_fee_history_rows(),
        )

        history_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("Fee Revision Audit History", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD),
                            ft.Text(f"{len(self.fee_history)} revisions", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    fee_history_list,
                ],
                spacing=6,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=ft.Padding(12, 8, 12, 8),
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        # 5. Administrative Toolbar
        status_btn_text = "Deactivate Course" if self.course.is_active else "Activate Course"
        status_btn_icon = ft.Icons.PAUSE_CIRCLE if self.course.is_active else ft.Icons.PLAY_CIRCLE
        status_btn_color = AppTheme.WARNING if self.course.is_active else AppTheme.SUCCESS

        admin_toolbar = ft.Row(
            controls=[
                ft.OutlinedButton(
                    content=ft.Text("Edit Details"),
                    icon=ft.Icons.EDIT,
                    on_click=self._handle_edit_click,
                ),
                ft.OutlinedButton(
                    content=ft.Text(status_btn_text),
                    icon=status_btn_icon,
                    on_click=self._handle_toggle_status_click,
                ),
                ft.OutlinedButton(
                    content=ft.Text("Delete"),
                    icon=ft.Icons.DELETE_OUTLINE,
                    on_click=self._handle_delete_click,
                    disabled=(self.summary.total_admissions_count > 0 or self.summary.batch_count > 0),
                    tooltip="Cannot delete course with associated admissions or batches." if (self.summary.total_admissions_count > 0 or self.summary.batch_count > 0) else "Delete unlinked course",
                ),
            ],
            spacing=AppTheme.PAD_SM,
        )

        return ft.Column(
            controls=[
                pricing_box,
                operational_metrics,
                desc_box,
                history_section,
                ft.Divider(height=8),
                admin_toolbar,
            ],
            spacing=AppTheme.PAD_MD,
            scroll=ft.ScrollMode.AUTO,
        )

    def _metric_tile(self, label: str, value: str, icon: str) -> ft.Control:
        return ft.Container(
            expand=True,
            content=ft.Row(
                controls=[
                    ft.Icon(icon, color=AppTheme.PRIMARY, size=20),
                    ft.Column(
                        controls=[
                            ft.Text(value, size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                            ft.Text(label, size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                        ],
                        spacing=0,
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=AppTheme.SURFACE_VARIANT,
            padding=ft.Padding(10, 8, 10, 8),
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

    def _build_fee_history_rows(self) -> list[ft.Control]:
        if not self.fee_history:
            return [
                ft.Container(
                    content=ft.Text("No fee revision history recorded for this course.", color=AppTheme.TEXT_MUTED, size=AppTheme.SIZE_CAPTION, italic=True),
                    padding=ft.Padding(8, 8, 8, 8),
                )
            ]

        rows = []
        for h in self.fee_history:
            rows.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.HISTORY, size=16, color=AppTheme.TEXT_MUTED),
                            ft.Text(f"₹{h.old_fee:,.0f} → ₹{h.new_fee:,.0f}", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                            ft.Text(f"Reason: {h.reason}", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY, no_wrap=True, expand=True),
                            ft.Text(f"By: {h.changed_by_username}", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED),
                            ft.Text(h.changed_at[:10] if len(h.changed_at) >= 10 else h.changed_at, size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding(6, 4, 6, 4),
                    bgcolor=AppTheme.SURFACE_VARIANT,
                    border_radius=AppTheme.RADIUS_SM,
                )
            )
        return rows

    def _handle_change_fee_click(self, e: ft.ControlEvent) -> None:
        target_page = self.page or self._root_page
        if not target_page:
            return

        def on_updated(cid: int) -> None:
            # Refresh local course state
            self.course = self.controller.get_course(self.course_id)
            self.fee_history = self.controller.get_fee_history(self.course_id)
            self.content = ft.Container(
                content=self._build_body(),
                width=650,
                height=500,
                padding=ft.Padding(0, 8, 0, 0),
            )
            self.update()
            self.on_course_mutated()

        fee_diag = CourseFeeDialog(course=self.course, on_fee_updated=on_updated, page=target_page)
        target_page.open(fee_diag)

    def _handle_edit_click(self, e: ft.ControlEvent) -> None:
        target_page = self.page or self._root_page
        if not target_page:
            return

        def on_saved(cid: int) -> None:
            self.course = self.controller.get_course(self.course_id)
            self.content = ft.Container(
                content=self._build_body(),
                width=650,
                height=500,
                padding=ft.Padding(0, 8, 0, 0),
            )
            self.update()
            self.on_course_mutated()

        modal = CourseFormModal(course=self.course, on_saved=on_saved, page=target_page)
        target_page.open(modal)

    def _handle_toggle_status_click(self, e: ft.ControlEvent) -> None:
        try:
            new_status = self.controller.toggle_status(self.course_id)
            self.course = self.controller.get_course(self.course_id)
            self.content = ft.Container(
                content=self._build_body(),
                width=650,
                height=500,
                padding=ft.Padding(0, 8, 0, 0),
            )
            self.update()
            self.on_course_mutated()
        except Exception as exc:
            LogService.error(f"Status toggle failed: {exc}", context=self.__class__.__name__)

    def _handle_delete_click(self, e: ft.ControlEvent) -> None:
        try:
            self.controller.delete_course(self.course_id)
            self.close_dialog()
            self.on_course_mutated()
        except Exception as exc:
            LogService.error(f"Delete failed: {exc}", context=self.__class__.__name__)

    def close_dialog(self, e: Optional[ft.ControlEvent] = None) -> None:
        try:
            if self.page:
                self.page.pop_dialog()
            elif self._root_page:
                self._root_page.pop_dialog()
        except RuntimeError:
            pass
