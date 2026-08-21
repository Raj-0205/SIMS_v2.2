# modules/admission/views/admission_workspace_dialog.py

from __future__ import annotations
from typing import Callable, Optional
import flet as ft

from core.logger.service import LogService
from ui.themes.theme import AppTheme
from modules.admission.controller import AdmissionController
from modules.admission.constants import AdmissionStatus, ADMISSION_STATUS_COLORS
from modules.admission.dto import AdmissionWorkspaceDTO, AdmissionDTO
from modules.admission.views.payment_dialog import PaymentDialog
from modules.admission.views.receipt_dialog import ReceiptDialog
from modules.receipts.controller import ReceiptController

__all__ = ["AdmissionWorkspaceDialog"]


class AdmissionWorkspaceDialog(ft.AlertDialog):
    """
    360° Detail Workspace Dialog for an Admission record.
    Displays profile, enrollment, financial breakdown, payments, receipts, friends, and audit trail.
    """

    def __init__(
        self,
        admission_id: int,
        on_updated: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(modal=True)

        self.admission_id = admission_id
        self.on_updated = on_updated or (lambda: None)
        self.controller = AdmissionController()
        self.receipt_controller = ReceiptController()
        try:
            self.workspace_dto = self.controller.get_admission_workspace(self.admission_id)
        except Exception:
            self.workspace_dto = None
        self.active_tab_index: int = 0

        # Title Controls
        self.title_text = ft.Text("Admission Workspace", size=AppTheme.SIZE_H2, weight=ft.FontWeight.W_600)
        self.candidate_badge = ft.Container()
        self.status_badge = ft.Container()

        self.title = ft.Row(
            controls=[
                ft.Row(
                    controls=[self.title_text, self.candidate_badge, self.status_badge],
                    spacing=AppTheme.PAD_SM,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.IconButton(
                    icon=ft.Icons.CLOSE,
                    icon_size=18,
                    icon_color=AppTheme.TEXT_SECONDARY,
                    tooltip="Close Workspace",
                    on_click=self.close_dialog,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        # Tab Bar & Content Area
        self.tab_buttons_row = self._build_tab_bar()
        self.tab_content_area = ft.Container(
            content=self._build_active_tab_content(),
            expand=True,
            padding=ft.Padding(0, AppTheme.PAD_MD, 0, 0),
        )

        # Action Buttons
        is_cancelled = (self.workspace_dto.admission.status == "CANCELLED") if self.workspace_dto else False
        self.cancel_admission_btn = ft.OutlinedButton(
            content=ft.Text("Cancel Admission", color=AppTheme.DANGER),
            icon=ft.Icons.CANCEL_OUTLINED,
            style=ft.ButtonStyle(color=AppTheme.DANGER),
            on_click=self._handle_cancel_admission,
            visible=not is_cancelled,
        )
        self.pay_btn = ft.ElevatedButton(
            content=ft.Text("Collect Payment"),
            icon=ft.Icons.PAYMENTS,
            style=ft.ButtonStyle(bgcolor=AppTheme.SUCCESS, color=AppTheme.SURFACE),
            on_click=self._handle_collect_payment,
            visible=not is_cancelled,
        )
        self.close_btn = ft.TextButton(content=ft.Text("Close"), on_click=self.close_dialog)

        self.content = ft.Container(
            width=840,
            height=560,
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

        self.actions = [
            ft.Row(
                controls=[
                    self.cancel_admission_btn,
                    ft.Row(controls=[self.pay_btn, self.close_btn], spacing=AppTheme.PAD_SM),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                expand=True,
            )
        ]
        self.actions_alignment = ft.MainAxisAlignment.SPACE_BETWEEN

        self.load_data()

    def _build_tab_bar(self) -> ft.Row:
        tabs_spec = [
            (0, "Overview", ft.Icons.DASHBOARD_CUSTOMIZE),
            (1, "Payments & Installments", ft.Icons.PAYMENTS),
            (2, "Receipts", ft.Icons.RECEIPT_LONG),
            (3, "Confirmed Friends", ft.Icons.GROUP),
            (4, "History & Timeline", ft.Icons.HISTORY),
        ]

        buttons = []
        for idx, label, icon in tabs_spec:
            is_selected = (self.active_tab_index == idx)
            btn = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(icon, size=16, color=AppTheme.PRIMARY if is_selected else AppTheme.TEXT_SECONDARY),
                        ft.Text(label, size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.W_600 if is_selected else ft.FontWeight.NORMAL, color=AppTheme.PRIMARY if is_selected else AppTheme.TEXT_SECONDARY),
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding(12, 8, 12, 8),
                border_radius=AppTheme.RADIUS_SM,
                bgcolor=AppTheme.PRIMARY_LIGHT if is_selected else ft.Colors.TRANSPARENT,
                ink=True,
                on_click=lambda _, i=idx: self._switch_tab(i),
            )
            buttons.append(btn)

        return ft.Row(controls=buttons, spacing=AppTheme.PAD_XS)

    def _switch_tab(self, idx: int) -> None:
        self.active_tab_index = idx
        self.tab_buttons_row = self._build_tab_bar()
        self.tab_content_area.content = self._build_active_tab_content()
        self.content.content.controls[0] = self.tab_buttons_row
        self._safe_update()

    @property
    def safe_page(self) -> Optional[ft.Page]:
        try:
            return self.page
        except (RuntimeError, AttributeError):
            return getattr(self, "_page", None)

    def _safe_update(self) -> None:
        p = self.safe_page
        if p:
            try:
                self.update()
            except Exception:
                pass

    def load_data(self) -> None:
        try:
            self.workspace_dto = self.controller.get_admission_workspace(self.admission_id)
            adm = self.workspace_dto.admission

            # Update Header Badges
            self.title_text.value = f"Admission: {adm.student_name}"
            self.candidate_badge.content = ft.Text(
                f"Candidate #{adm.admission_number}",
                size=AppTheme.SIZE_CAPTION,
                weight=ft.FontWeight.BOLD,
                color=AppTheme.PRIMARY,
            )
            self.candidate_badge.bgcolor = AppTheme.PRIMARY_LIGHT
            self.candidate_badge.padding = ft.Padding(8, 4, 8, 4)
            self.candidate_badge.border_radius = AppTheme.RADIUS_SM

            color = ADMISSION_STATUS_COLORS.get(adm.status, AppTheme.PRIMARY)
            self.status_badge.content = ft.Text(
                adm.status,
                size=AppTheme.SIZE_CAPTION,
                weight=ft.FontWeight.BOLD,
                color=color,
            )
            self.status_badge.bgcolor = color + "1A"
            self.status_badge.padding = ft.Padding(8, 4, 8, 4)
            self.status_badge.border_radius = AppTheme.RADIUS_SM

            self.tab_content_area.content = self._build_active_tab_content()
            self._safe_update()
        except Exception as ex:
            LogService.error(f"Failed to load admission workspace: {ex}", context=self.__class__.__name__)

    def _build_active_tab_content(self) -> ft.Control:
        if not self.workspace_dto:
            return ft.Container(
                content=ft.ProgressRing(),
                alignment=ft.Alignment.CENTER,
                height=300,
            )

        if self.active_tab_index == 0:
            return self._build_overview_tab()
        elif self.active_tab_index == 1:
            return self._build_payments_tab()
        elif self.active_tab_index == 2:
            return self._build_receipts_tab()
        elif self.active_tab_index == 3:
            return self._build_friends_tab()
        elif self.active_tab_index == 4:
            return self._build_timeline_tab()
        return ft.Container()

    def _build_overview_tab(self) -> ft.Control:
        adm = self.workspace_dto.admission

        col1 = ft.Column(
            controls=[
                ft.Text("Student Information", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                self._info_row("Full Name", adm.student_name),
                self._info_row("Mobile Number", adm.mobile_number or "—"),
                self._info_row("Gender / DOB", f"{adm.gender or '—'}  |  {adm.dob or '—'}"),
                self._info_row("Mother's Name", adm.mother_name or "—"),
                self._info_row("Parent / Guardian", adm.parent_guardian_name or "—"),
                self._info_row("Aadhaar Number", adm.aadhaar_number or "—"),
                self._info_row("Village / City", adm.village or "—"),
                self._info_row("Address", adm.address or "—"),
            ],
            spacing=AppTheme.PAD_XS,
            expand=True,
        )

        col2 = ft.Column(
            controls=[
                ft.Text("Enrollment & Financials", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                self._info_row("Enrolled Course", adm.course_name),
                self._info_row("Assigned Batch", adm.batch_name or "Unassigned"),
                self._info_row("Academic Institution", adm.institution_name or "—"),
                self._info_row("Qualification", adm.qualification or "—"),
                self._info_row("Agreed Fee", f"₹{adm.agreed_fee:,.2f}"),
                self._info_row("Discount Applied", f"₹{adm.discount:,.2f}"),
                self._info_row("Final Payable Fee", f"₹{adm.final_fee:,.2f}"),
                self._info_row("Total Paid", f"₹{adm.total_paid:,.2f}", is_bold=True, val_color=AppTheme.SUCCESS),
                self._info_row("Pending Balance", f"₹{adm.pending_amount:,.2f}", is_bold=True, val_color=AppTheme.DANGER if adm.pending_amount > 0 else AppTheme.SUCCESS),
            ],
            spacing=AppTheme.PAD_XS,
            expand=True,
        )

        return ft.Column(
            controls=[
                ft.Row(controls=[col1, ft.VerticalDivider(width=1, color=AppTheme.BORDER), col2], spacing=AppTheme.PAD_MD),
            ],
            scroll=ft.ScrollMode.AUTO,
        )

    def _info_row(self, label: str, val: str, is_bold: bool = False, val_color: Optional[str] = None) -> ft.Row:
        return ft.Row(
            controls=[
                ft.Text(f"{label}:", size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.W_600, color=AppTheme.TEXT_SECONDARY, width=130),
                ft.Text(val, size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD if is_bold else ft.FontWeight.NORMAL, color=val_color or AppTheme.TEXT_PRIMARY),
            ],
            spacing=AppTheme.PAD_XS,
        )

    def _build_payments_tab(self) -> ft.Control:
        payments = self.workspace_dto.payments
        if not payments:
            return ft.Container(
                content=ft.Text("No payment transactions recorded yet.", size=AppTheme.SIZE_BODY, color=AppTheme.TEXT_MUTED),
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding(0, 40, 0, 40),
            )

        rows = []
        for p in payments:
            rows.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Text(p.formatted_installment, size=AppTheme.SIZE_CAPTION, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                                bgcolor=AppTheme.PRIMARY_LIGHT,
                                padding=ft.Padding(6, 3, 6, 3),
                                border_radius=AppTheme.RADIUS_SM,
                            ),
                            ft.Text(f"₹{p.amount:,.2f}", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color=AppTheme.SUCCESS),
                            ft.Text(f"Mode: {p.payment_mode}", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                            ft.Text(f"Date: {p.payment_date[:16]}", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED),
                            ft.Text(f"Collector: {p.collector_name or '—'}", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding(AppTheme.PAD_SM, AppTheme.PAD_SM, AppTheme.PAD_SM, AppTheme.PAD_SM),
                    border=ft.Border.all(1, AppTheme.BORDER),
                    border_radius=AppTheme.RADIUS_MD,
                )
            )

        return ft.Column(controls=rows, spacing=AppTheme.PAD_SM, scroll=ft.ScrollMode.AUTO)

    def _build_receipts_tab(self) -> ft.Control:
        receipts = self.workspace_dto.receipts
        if not receipts:
            return ft.Container(
                content=ft.Text("No receipts generated yet.", size=AppTheme.SIZE_BODY, color=AppTheme.TEXT_MUTED),
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding(0, 40, 0, 40),
            )

        rows = []
        for r in receipts:
            rows.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Column(
                                controls=[
                                    ft.Text(f"Receipt #{r.receipt_number}", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY),
                                    ft.Text(f"Issued: {r.receipt_date[:16]}  |  Installment 0{r.installment_number}", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED),
                                ],
                                spacing=2,
                            ),
                            ft.Text(f"Paid: ₹{r.amount_paid:,.2f}", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color=AppTheme.SUCCESS),
                            ft.Text(f"Pending: ₹{r.pending_amount:,.2f}", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                            ft.ElevatedButton(
                                content=ft.Text("View Receipt", size=AppTheme.SIZE_CAPTION),
                                icon=ft.Icons.PREVIEW,
                                on_click=lambda _, r_obj=r: self._open_receipt_dialog(r_obj),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding(AppTheme.PAD_SM, AppTheme.PAD_SM, AppTheme.PAD_SM, AppTheme.PAD_SM),
                    border=ft.Border.all(1, AppTheme.BORDER),
                    border_radius=AppTheme.RADIUS_MD,
                )
            )

        return ft.Column(controls=rows, spacing=AppTheme.PAD_SM, scroll=ft.ScrollMode.AUTO)

    def _build_friends_tab(self) -> ft.Control:
        friends = self.workspace_dto.confirmed_friends
        if not friends:
            return ft.Container(
                content=ft.Text("No confirmed friends linked to this student.", size=AppTheme.SIZE_BODY, color=AppTheme.TEXT_MUTED),
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding(0, 40, 0, 40),
            )

        rows = []
        for f in friends:
            rows.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.PERSON, size=20, color=AppTheme.PRIMARY),
                                    ft.Column(
                                        controls=[
                                            ft.Text(f"{f['first_name']} {f['last_name']}", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD),
                                            ft.Text(f"Village: {f.get('village', '—')}  |  Mobile: {f.get('mobile_number', '—')}", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED),
                                        ],
                                        spacing=2,
                                    ),
                                ],
                                spacing=AppTheme.PAD_SM,
                            ),
                            ft.Text(f"Linked: {f.get('friendship_date', '')[:10]}", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding(AppTheme.PAD_SM, AppTheme.PAD_SM, AppTheme.PAD_SM, AppTheme.PAD_SM),
                    border=ft.Border.all(1, AppTheme.BORDER),
                    border_radius=AppTheme.RADIUS_MD,
                )
            )

        return ft.Column(controls=rows, spacing=AppTheme.PAD_SM, scroll=ft.ScrollMode.AUTO)

    def _build_timeline_tab(self) -> ft.Control:
        timeline = self.workspace_dto.timeline
        rows = []
        for ev in timeline:
            color = AppTheme.PRIMARY if ev["event_type"] == "REGISTRATION" else (AppTheme.SUCCESS if ev["event_type"] == "PAYMENT" else AppTheme.SECONDARY)
            icon = ft.Icons.APP_REGISTRATION if ev["event_type"] == "REGISTRATION" else (ft.Icons.PAID if ev["event_type"] == "PAYMENT" else ft.Icons.RECEIPT)

            rows.append(
                ft.Row(
                    controls=[
                        ft.Icon(icon, size=18, color=color),
                        ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Text(ev["title"], size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD),
                                        ft.Text(ev["timestamp"][:16], size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED),
                                    ],
                                    spacing=AppTheme.PAD_SM,
                                ),
                                ft.Text(ev["description"], size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                    ],
                    spacing=AppTheme.PAD_SM,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                )
            )

        return ft.Column(controls=rows, spacing=AppTheme.PAD_MD, scroll=ft.ScrollMode.AUTO)

    def _open_receipt_dialog(self, receipt) -> None:
        p = self.safe_page
        if p:
            dlg = ReceiptDialog(
                receipt=receipt,
                student_name=self.workspace_dto.admission.student_name,
                candidate_number=self.workspace_dto.admission.admission_number,
                course_name=self.workspace_dto.admission.course_name,
            )
            p.dialog = dlg
            dlg.open = True
            p.update()

    def _handle_collect_payment(self, _=None) -> None:
        adm = self.workspace_dto.admission
        p = self.safe_page
        if p:
            dlg = PaymentDialog(
                admission_id=adm.id,
                student_name=adm.student_name,
                course_name=adm.course_name,
                candidate_number=adm.admission_number,
                total_fee=adm.final_fee,
                already_paid=adm.total_paid,
                default_amount=min(500.0, adm.pending_amount) if adm.pending_amount > 0 else 500.0,
                on_payment_success=self._on_payment_collected,
            )
            p.dialog = dlg
            dlg.open = True
            p.update()

    def _handle_cancel_admission(self, _=None) -> None:
        adm = self.workspace_dto.admission
        p = self.safe_page
        if not p:
            return

        reason_field = ft.TextField(
            label="Cancellation Reason *",
            hint_text="e.g. Personal reasons / student withdrawal",
            multiline=True,
            min_lines=2,
            max_lines=3,
            border_radius=AppTheme.RADIUS_MD,
            expand=True,
        )
        error_msg = ft.Text("", color=AppTheme.DANGER, size=AppTheme.SIZE_CAPTION, visible=False)

        def do_confirm_cancel(e):
            r = (reason_field.value or "").strip()
            if not r:
                error_msg.value = "Cancellation reason cannot be empty."
                error_msg.visible = True
                p.update()
                return
            try:
                self.controller.cancel_admission(adm.id, reason=r)
                cancel_dlg.open = False
                p.dialog = self
                self.open = True
                self.load_data()
                self.cancel_admission_btn.visible = False
                self.pay_btn.visible = False
                self.on_updated()
                p.update()
            except Exception as ex:
                error_msg.value = str(ex)
                error_msg.visible = True
                p.update()

        def do_close_cancel_dlg(e):
            cancel_dlg.open = False
            p.dialog = self
            self.open = True
            p.update()

        cancel_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Cancel Admission", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.DANGER),
            content=ft.Container(
                width=450,
                content=ft.Column(
                    controls=[
                        ft.Text(
                            f"Are you sure you want to cancel admission {adm.admission_number} ({adm.course_name}) for {adm.student_name}?\n\n"
                            "All recorded payments and receipts will be permanently preserved in the financial audit log.",
                            size=AppTheme.SIZE_BODY,
                            color=AppTheme.TEXT_SECONDARY,
                        ),
                        reason_field,
                        error_msg,
                    ],
                    spacing=AppTheme.PAD_SM,
                    tight=True,
                ),
            ),
            actions=[
                ft.TextButton("Keep Admission", on_click=do_close_cancel_dlg),
                ft.ElevatedButton(
                    "Confirm Cancellation",
                    style=ft.ButtonStyle(bgcolor=AppTheme.DANGER, color=AppTheme.SURFACE),
                    on_click=do_confirm_cancel,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        p.dialog = cancel_dlg
        cancel_dlg.open = True
        p.update()

    def _on_payment_collected(self) -> None:
        self.load_data()
        self.on_updated()

    def close_dialog(self, _=None) -> None:
        self.open = False
        p = self.safe_page
        if p:
            p.update()
