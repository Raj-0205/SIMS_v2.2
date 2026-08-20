# modules/student/views/student_workspace_dialog.py

from __future__ import annotations
from typing import Callable, Optional
import flet as ft

from core.logger.service import LogService
from modules.student.controller import StudentController
from modules.student.dto import StudentDTO, StudentWorkspaceDTO
from modules.student.views.student_form_modal import StudentFormModal
from ui.themes.theme import AppTheme

__all__ = ["StudentWorkspaceDialog"]


class StudentWorkspaceDialog(ft.AlertDialog):
    """
    Comprehensive Student Operational Workspace.
    Provides deep student lifecycle visibility across 7 functional tabs:
    Overview, Admissions, Payments, Receipts, Documents, History, and Activity Logs.
    """

    def __init__(
        self,
        controller: StudentController,
        student_id: int,
        on_refresh_required: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__()

        self.controller = controller
        self.student_id = student_id
        self.on_refresh_required = on_refresh_required
        self.modal = True

        # Fetch full aggregate workspace data
        try:
            self.workspace_data: StudentWorkspaceDTO = self.controller.get_student_workspace(student_id)
        except Exception as ex:
            LogService.error(f"Failed to load workspace for student ID {student_id}: {ex}", context="StudentWorkspace")
            # Fallback
            student = self.controller.get_student(student_id)
            self.workspace_data = StudentWorkspaceDTO(student=student)

        self.active_tab_index: int = 0

        # Build UI Elements
        self.title = self._build_header()
        self.tab_buttons_row = self._build_tab_bar()
        self.tab_content_area = ft.Container(
            content=self._build_active_tab_content(),
            expand=True,
            padding=ft.Padding(left=0, top=AppTheme.PAD_MD, right=0, bottom=0),
        )

        self.content = ft.Container(
            width=880,
            height=580,
            content=ft.Column(
                controls=[
                    self.tab_buttons_row,
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    self.tab_content_area,
                ],
                spacing=0,
                expand=True,
            ),
        )

        self.actions = self._build_footer_actions()
        self.actions_alignment = ft.MainAxisAlignment.SPACE_BETWEEN

    def _safe_update(self) -> None:
        try:
            if self.page:
                self.update()
        except RuntimeError:
            pass

    def _build_header(self) -> ft.Container:
        student = self.workspace_data.student

        # Avatar initials
        initials = (
            f"{student.first_name[0] if student.first_name else ''}"
            f"{student.last_name[0] if student.last_name else ''}"
        ).upper() or "ST"

        avatar = ft.Container(
            width=54,
            height=54,
            bgcolor=AppTheme.PRIMARY,
            border_radius=AppTheme.RADIUS_PILL,
            alignment=ft.Alignment.CENTER,
            content=ft.Text(
                initials,
                size=20,
                weight=ft.FontWeight.BOLD,
                color=AppTheme.SURFACE,
            ),
        )

        # Status badge color
        status_text = student.status_label
        is_active = status_text in ("ACTIVE", "CONFIRMED", "ENROLLED")
        status_bg = AppTheme.SUCCESS_LIGHT if is_active else AppTheme.PRIMARY_LIGHT
        status_fg = AppTheme.SUCCESS if is_active else AppTheme.PRIMARY

        header_info = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(
                            student.display_name,
                            size=AppTheme.SIZE_H1,
                            weight=ft.FontWeight.BOLD,
                            color=AppTheme.TEXT_PRIMARY,
                        ),
                        ft.Container(
                            content=ft.Text(
                                status_text,
                                size=AppTheme.SIZE_CAPTION,
                                weight=ft.FontWeight.BOLD,
                                color=status_fg,
                            ),
                            bgcolor=status_bg,
                            padding=ft.Padding(left=8, top=3, right=8, bottom=3),
                            border_radius=AppTheme.RADIUS_SM,
                        ),
                    ],
                    spacing=AppTheme.PAD_SM,
                ),
                ft.Row(
                    controls=[
                        ft.Text(f"Student ID: #{student.id}", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY, weight=ft.FontWeight.W_500),
                        ft.Text("•", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED),
                        ft.Text(
                            f"Enrolled Course: {student.current_course or 'None'}",
                            size=AppTheme.SIZE_CAPTION,
                            color=AppTheme.PRIMARY if student.current_course else AppTheme.TEXT_SECONDARY,
                            weight=ft.FontWeight.BOLD if student.current_course else ft.FontWeight.NORMAL,
                        ),
                        ft.Text("•", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED),
                        ft.Text(f"Mobile: {student.mobile_number or 'Not provided'}", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                    ],
                    spacing=6,
                ),
            ],
            spacing=3,
        )

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Row(controls=[avatar, header_info], spacing=AppTheme.PAD_MD),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            padding=ft.Padding(left=0, top=0, right=0, bottom=AppTheme.PAD_SM),
        )

    def _build_tab_bar(self) -> ft.Row:
        tabs_spec = [
            (0, "Overview", ft.Icons.PERSON_OUTLINE),
            (1, f"Admissions ({len(self.workspace_data.admissions)})", ft.Icons.SCHOOL_OUTLINED),
            (2, "Payments", ft.Icons.PAYMENTS_OUTLINED),
            (3, "Receipts", ft.Icons.RECEIPT_LONG_OUTLINED),
            (4, "Documents", ft.Icons.FOLDER_OPEN_OUTLINED),
            (5, "History", ft.Icons.TIMELINE_OUTLINED),
            (6, "Activity Logs", ft.Icons.HISTORY_OUTLINED),
        ]

        buttons = []
        for idx, label, icon in tabs_spec:
            is_selected = (self.active_tab_index == idx)
            btn = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            icon,
                            size=16,
                            color=AppTheme.PRIMARY if is_selected else AppTheme.TEXT_SECONDARY,
                        ),
                        ft.Text(
                            label,
                            size=AppTheme.SIZE_CAPTION,
                            weight=ft.FontWeight.BOLD if is_selected else ft.FontWeight.W_500,
                            color=AppTheme.PRIMARY if is_selected else AppTheme.TEXT_SECONDARY,
                        ),
                    ],
                    spacing=6,
                ),
                padding=ft.Padding(left=12, top=8, right=12, bottom=8),
                border_radius=AppTheme.RADIUS_SM,
                bgcolor=AppTheme.PRIMARY_LIGHT if is_selected else ft.Colors.TRANSPARENT,
                on_click=lambda e, i=idx: self._switch_tab(i),
            )
            buttons.append(btn)

        return ft.Row(
            controls=buttons,
            spacing=4,
            scroll=ft.ScrollMode.AUTO,
        )

    def _switch_tab(self, index: int) -> None:
        self.active_tab_index = index
        self.tab_buttons_row.controls = self._build_tab_bar().controls
        self.tab_content_area.content = self._build_active_tab_content()
        self._safe_update()

    def _build_active_tab_content(self) -> ft.Control:
        if self.active_tab_index == 0:
            return self._build_overview_tab()
        elif self.active_tab_index == 1:
            return self._build_admissions_tab()
        elif self.active_tab_index == 2:
            return self._build_payments_tab()
        elif self.active_tab_index == 3:
            return self._build_receipts_tab()
        elif self.active_tab_index == 4:
            return self._build_documents_tab()
        elif self.active_tab_index == 5:
            return self._build_history_tab()
        else:
            return self._build_activity_logs_tab()

    # --- TAB 1: OVERVIEW ---
    def _build_overview_tab(self) -> ft.Container:
        student = self.workspace_data.student

        def info_row(label: str, value: str, icon: str) -> ft.Row:
            return ft.Row(
                controls=[
                    ft.Icon(icon, size=16, color=AppTheme.TEXT_SECONDARY),
                    ft.Text(f"{label}:", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.W_500, color=AppTheme.TEXT_SECONDARY, width=140),
                    ft.Text(value, size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                ],
                spacing=8,
            )

        personal_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Personal Information", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    info_row("Full Name", student.display_name, ft.Icons.PERSON),
                    info_row("Student ID", f"#{student.id}", ft.Icons.NUMBERS),
                    info_row("Mobile Number", student.mobile_number or "Not Provided", ft.Icons.PHONE),
                    info_row("Email Address", student.email or "Not Provided", ft.Icons.EMAIL),
                    info_row("Registration Date", student.created_at or "N/A", ft.Icons.CALENDAR_TODAY),
                ],
                spacing=AppTheme.PAD_SM,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=AppTheme.PAD_MD,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
            expand=True,
        )

        academic_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Academic & Admission Summary", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    info_row("Total Admissions", str(student.admissions_count), ft.Icons.SCHOOL),
                    info_row("Current Course", student.current_course or "Not Enrolled", ft.Icons.MENU_BOOK),
                    info_row("Admission Status", student.admission_status or "REGISTERED", ft.Icons.CHECK_CIRCLE_OUTLINE),
                    info_row("Latest Admission No.", student.latest_admission_number or (f"#{student.latest_admission_id}" if student.latest_admission_id else "None"), ft.Icons.BADGE),
                    info_row("Enrolled Date", student.latest_admission_date or "N/A", ft.Icons.EVENT),
                ],
                spacing=AppTheme.PAD_SM,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=AppTheme.PAD_MD,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
            expand=True,
        )

        notes_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Internal Notes", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    ft.Text(
                        "Student master record active in institute database. "
                        "All linked admissions, receipts, and documents are tracked under this master ID.",
                        size=AppTheme.SIZE_BODY,
                        color=AppTheme.TEXT_SECONDARY,
                    ),
                ],
                spacing=AppTheme.PAD_SM,
            ),
            bgcolor=AppTheme.SURFACE,
            padding=AppTheme.PAD_MD,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        return ft.Container(
            content=ft.ListView(
                controls=[
                    ft.Row(controls=[personal_card, academic_card], spacing=AppTheme.PAD_MD),
                    notes_card,
                ],
                spacing=AppTheme.PAD_MD,
                expand=True,
            ),
            expand=True,
        )

    # --- TAB 2: ADMISSIONS ---
    def _build_admissions_tab(self) -> ft.Container:
        admissions = self.workspace_data.admissions

        if not admissions:
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.SCHOOL_OUTLINED, size=54, color=AppTheme.TEXT_MUTED),
                        ft.Text("No Admissions Linked", size=AppTheme.SIZE_H2, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                        ft.Text(
                            "This student has not been enrolled in any course yet.\n"
                            "Use the Admissions module to link this student to courses.",
                            size=AppTheme.SIZE_BODY,
                            color=AppTheme.TEXT_SECONDARY,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=AppTheme.PAD_SM,
                ),
                alignment=ft.Alignment.CENTER,
                expand=True,
            )

        rows = []
        for adm in admissions:
            status_color = AppTheme.SUCCESS if adm.status in ("CONFIRMED", "REGISTERED") else AppTheme.PRIMARY
            adm_display = adm.admission_number if getattr(adm, "admission_number", None) else f"#{adm.admission_id}"
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(adm_display, weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(adm.course_name or "General Admission")),
                        ft.DataCell(ft.Text(adm.course_code or "—")),
                        ft.DataCell(ft.Text(adm.admission_date[:10] if len(adm.admission_date) >= 10 else adm.admission_date)),
                        ft.DataCell(
                            ft.Container(
                                content=ft.Text(adm.status, size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD, color=status_color),
                                bgcolor=AppTheme.SUCCESS_LIGHT if status_color == AppTheme.SUCCESS else AppTheme.PRIMARY_LIGHT,
                                padding=ft.Padding(left=6, top=2, right=6, bottom=2),
                                border_radius=AppTheme.RADIUS_SM,
                            )
                        ),
                    ]
                )
            )

        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Admission No.", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Course Name", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Code", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Admission Date", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Status", weight=ft.FontWeight.BOLD)),
            ],
            rows=rows,
            heading_row_color=AppTheme.SURFACE_VARIANT,
            column_spacing=24,
        )

        return ft.Container(
            content=ft.ListView(controls=[table], expand=True),
            bgcolor=AppTheme.SURFACE,
            padding=AppTheme.PAD_MD,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
            expand=True,
        )

    # --- TAB 3: PAYMENTS ---
    def _build_payments_tab(self) -> ft.Container:
        student = self.workspace_data.student
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Column(
                                    controls=[
                                        ft.Text("Total Course Fee", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                                        ft.Text(student.fee_display, size=AppTheme.SIZE_H2, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                                    ],
                                    spacing=2,
                                ),
                                bgcolor=AppTheme.PRIMARY_LIGHT,
                                padding=AppTheme.PAD_MD,
                                border_radius=AppTheme.RADIUS_MD,
                                expand=True,
                            ),
                            ft.Container(
                                content=ft.Column(
                                    controls=[
                                        ft.Text("Total Paid", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                                        ft.Text(student.paid_display, size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.SUCCESS),
                                    ],
                                    spacing=2,
                                ),
                                bgcolor=AppTheme.SUCCESS_LIGHT,
                                padding=AppTheme.PAD_MD,
                                border_radius=AppTheme.RADIUS_MD,
                                expand=True,
                            ),
                            ft.Container(
                                content=ft.Column(
                                    controls=[
                                        ft.Text("Pending Dues", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                                        ft.Text(student.pending_display, size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_SECONDARY),
                                    ],
                                    spacing=2,
                                ),
                                bgcolor=AppTheme.SURFACE_VARIANT,
                                padding=AppTheme.PAD_MD,
                                border_radius=AppTheme.RADIUS_MD,
                                expand=True,
                            ),
                        ],
                        spacing=AppTheme.PAD_MD,
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Icon(ft.Icons.RECEIPT_LONG, size=48, color=AppTheme.TEXT_MUTED),
                                ft.Text("No Transactions Recorded", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                                ft.Text(
                                    "Fee payments belong to Admissions and will appear here once recorded via the Finance Engine.",
                                    size=AppTheme.SIZE_BODY,
                                    color=AppTheme.TEXT_SECONDARY,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=AppTheme.PAD_SM,
                        ),
                        alignment=ft.Alignment.CENTER,
                        expand=True,
                        padding=AppTheme.PAD_XL,
                    ),
                ],
                spacing=AppTheme.PAD_MD,
                expand=True,
            ),
            expand=True,
        )

    # --- TAB 4: RECEIPTS ---
    def _build_receipts_tab(self) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.RECEIPT_LONG_OUTLINED, size=54, color=AppTheme.TEXT_MUTED),
                    ft.Text("No Receipts Issued", size=AppTheme.SIZE_H2, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                    ft.Text(
                        "Receipts are immutable financial documents generated sequentially upon payment confirmation.\n"
                        "Receipts for this student will appear here.",
                        size=AppTheme.SIZE_BODY,
                        color=AppTheme.TEXT_SECONDARY,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=AppTheme.PAD_SM,
            ),
            alignment=ft.Alignment.CENTER,
            expand=True,
        )

    # --- TAB 5: DOCUMENTS ---
    def _build_documents_tab(self) -> ft.Container:
        def doc_card(title: str, subtitle: str, icon: str) -> ft.Container:
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(icon, size=40, color=AppTheme.PRIMARY),
                        ft.Text(title, size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                        ft.Text(subtitle, size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                ),
                bgcolor=AppTheme.SURFACE,
                padding=AppTheme.PAD_LG,
                border_radius=AppTheme.RADIUS_MD,
                border=ft.Border.all(1, AppTheme.BORDER),
                width=180,
                alignment=ft.Alignment.CENTER,
            )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Student Documents & Media", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    ft.Row(
                        controls=[
                            doc_card("Photo", "Default Avatar", ft.Icons.ACCOUNT_BOX),
                            doc_card("Signature", "Not Uploaded", ft.Icons.DRAW),
                            doc_card("Aadhaar Card", "Not Uploaded", ft.Icons.BADGE),
                            doc_card("Certificate", "Not Issued", ft.Icons.WORKSPACE_PREMIUM),
                        ],
                        spacing=AppTheme.PAD_MD,
                    ),
                ],
                spacing=AppTheme.PAD_MD,
            ),
            padding=AppTheme.PAD_MD,
            expand=True,
        )

    # --- TAB 6: HISTORY TIMELINE ---
    def _build_history_tab(self) -> ft.Container:
        timeline = self.workspace_data.timeline

        if not timeline:
            return ft.Container(
                content=ft.Text("No history recorded.", color=AppTheme.TEXT_SECONDARY),
                alignment=ft.Alignment.CENTER,
                expand=True,
            )

        items = []
        for event in timeline:
            items.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.CHECK_CIRCLE if event.event_type == "REGISTRATION" else ft.Icons.SCHOOL,
                                size=20,
                                color=AppTheme.PRIMARY,
                            ),
                            ft.Column(
                                controls=[
                                    ft.Text(event.title, size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                                    ft.Text(event.description, size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.Text(event.timestamp, size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED),
                        ],
                        spacing=AppTheme.PAD_MD,
                    ),
                    padding=ft.Padding(left=12, top=10, right=12, bottom=10),
                    bgcolor=AppTheme.SURFACE,
                    border_radius=AppTheme.RADIUS_SM,
                    border=ft.Border.all(1, AppTheme.BORDER),
                )
            )

        return ft.Container(
            content=ft.ListView(controls=items, spacing=AppTheme.PAD_SM, expand=True),
            expand=True,
        )

    # --- TAB 7: ACTIVITY LOGS ---
    def _build_activity_logs_tab(self) -> ft.Container:
        student = self.workspace_data.student

        logs = [
            ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(student.created_at or "N/A", size=AppTheme.SIZE_CAPTION)),
                    ft.DataCell(ft.Text("Admin", weight=ft.FontWeight.W_500)),
                    ft.DataCell(ft.Text("STUDENT_CREATED", color=AppTheme.PRIMARY, weight=ft.FontWeight.BOLD)),
                    ft.DataCell(ft.Text(f"Student master record created for '{student.display_name}'.")),
                ]
            )
        ]

        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Timestamp", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("User", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Action", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Details", weight=ft.FontWeight.BOLD)),
            ],
            rows=logs,
            heading_row_color=AppTheme.SURFACE_VARIANT,
            column_spacing=24,
        )

        return ft.Container(
            content=ft.ListView(controls=[table], expand=True),
            bgcolor=AppTheme.SURFACE,
            padding=AppTheme.PAD_MD,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
            expand=True,
        )

    # --- FOOTER ACTIONS ---
    def _build_footer_actions(self) -> list[ft.Control]:
        edit_btn = ft.ElevatedButton(
            content=ft.Text("Edit Profile"),
            icon=ft.Icons.EDIT,
            style=ft.ButtonStyle(
                bgcolor=AppTheme.PRIMARY,
                color=AppTheme.SURFACE,
                shape=ft.RoundedRectangleBorder(radius=AppTheme.RADIUS_MD),
            ),
            on_click=self._handle_edit,
        )

        close_btn = ft.TextButton(
            content=ft.Text("Close Workspace"),
            style=ft.ButtonStyle(color=AppTheme.TEXT_SECONDARY),
            on_click=self.close_workspace,
        )

        return [
            ft.Row(controls=[edit_btn], spacing=AppTheme.PAD_SM),
            close_btn,
        ]

    def _handle_edit(self, e: ft.ControlEvent) -> None:
        """Opens Edit Modal over the workspace."""
        student = self.workspace_data.student

        def on_saved_refresh():
            # Refresh workspace data and reload
            self.workspace_data = self.controller.get_student_workspace(self.student_id)
            self.title = self._build_header()
            self.tab_content_area.content = self._build_active_tab_content()
            self._safe_update()
            if self.on_refresh_required:
                self.on_refresh_required()

        modal = StudentFormModal(
            controller=self.controller,
            on_saved=on_saved_refresh,
            student=student,
        )
        try:
            if self.page:
                self.page.show_dialog(modal)
        except RuntimeError:
            pass

    def close_workspace(self, e: Optional[ft.ControlEvent] = None) -> None:
        """Closes the workspace modal safely using Flet's pop_dialog."""
        try:
            if self.page:
                self.page.pop_dialog()
        except RuntimeError:
            pass
        if self.on_refresh_required:
            self.on_refresh_required()
