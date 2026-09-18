# ui/screens/control_center.py

from __future__ import annotations
from datetime import datetime
from typing import Callable, Optional
import flet as ft

from core.database.engine import DatabaseEngine
from core.database.migration import MigrationEngine
from core.security.context import SecurityContext
from core.security.roles import Role
from modules.admission.activity_log_repository import ActivityLogRepository
from modules.settings.service import SettingsService
from ui.themes.theme import AppTheme

__all__ = ["ControlCenterScreen"]


class ControlCenterScreen(ft.Container):
    """
    Dedicated SIMS Control Center.

    Exclusive landing and governance workspace for Administrator accounts.
    Displays security audit telemetry, privileged system status, and security controls.
    """

    def __init__(self, page: ft.Page, on_navigate: Optional[Callable[[str], None]] = None) -> None:
        super().__init__(
            expand=True,
            padding=ft.Padding(AppTheme.PAD_LG, AppTheme.PAD_MD, AppTheme.PAD_LG, AppTheme.PAD_MD),
            bgcolor=AppTheme.BACKGROUND,
        )
        self._page = page
        self.on_navigate = on_navigate or (lambda route: None)
        self.settings_service = SettingsService()
        self.activity_repo = ActivityLogRepository()

        # Audit Table
        self.audit_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Timestamp", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Action", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Actor", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Details", weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
            heading_row_color=AppTheme.SURFACE_VARIANT,
            border=ft.Border.all(1, AppTheme.BORDER),
            border_radius=AppTheme.RADIUS_MD,
        )

        # PIN management fields
        self.current_pin_field = ft.TextField(
            label="Current PIN",
            password=True,
            can_reveal_password=True,
            width=180,
            text_size=14,
        )
        self.new_pin_field = ft.TextField(
            label="New PIN (min 4 digits)",
            password=True,
            can_reveal_password=True,
            width=200,
            text_size=14,
        )
        self.pin_message_text = ft.Text("", size=13)

        self._build_ui()

    def _build_ui(self) -> None:
        username = SecurityContext.get_current_username() or "Administrator"

        header_card = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.ADMIN_PANEL_SETTINGS, size=32, color=AppTheme.PRIMARY),
                                    ft.Text("SIMS Control Center", size=24, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                                    ft.Container(
                                        content=ft.Text("PRIVILEGED MODE", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                        bgcolor=AppTheme.PRIMARY,
                                        padding=ft.Padding(8, 3, 8, 3),
                                        border_radius=AppTheme.RADIUS_SM,
                                    ),
                                ],
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Text(
                                f"Authenticated as: {username} • Full System Governance & Security Authority",
                                size=AppTheme.SIZE_BODY,
                                color=AppTheme.TEXT_SECONDARY,
                            ),
                        ],
                        spacing=4,
                    ),
                    ft.Row(
                        controls=[
                            ft.OutlinedButton(
                                content=ft.Text("Standard Dashboard"),
                                icon=ft.Icons.DASHBOARD,
                                on_click=lambda _: self.on_navigate("/dashboard"),
                            ),
                            ft.ElevatedButton(
                                content=ft.Text("Refresh Telemetry"),
                                icon=ft.Icons.REFRESH,
                                on_click=lambda _: self.load_data(),
                            ),
                        ],
                        spacing=10,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=AppTheme.PAD_MD,
            bgcolor=AppTheme.SURFACE,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        # Quick Actions Card
        quick_actions = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Privileged Governance Shortcuts", size=16, weight=ft.FontWeight.BOLD),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    ft.Row(
                        controls=[
                            ft.ElevatedButton(
                                content=ft.Text("Courses & Fees"),
                                icon=ft.Icons.MENU_BOOK,
                                on_click=lambda _: self.on_navigate("/courses"),
                            ),
                            ft.ElevatedButton(
                                content=ft.Text("Batch Scheduling"),
                                icon=ft.Icons.GROUP_WORK,
                                on_click=lambda _: self.on_navigate("/batch"),
                            ),
                            ft.ElevatedButton(
                                content=ft.Text("Student Registry"),
                                icon=ft.Icons.PEOPLE,
                                on_click=lambda _: self.on_navigate("/students"),
                            ),
                            ft.ElevatedButton(
                                content=ft.Text("General Settings"),
                                icon=ft.Icons.SETTINGS,
                                on_click=lambda _: self.on_navigate("/settings"),
                            ),
                        ],
                        spacing=12,
                        wrap=True,
                    ),
                ],
                spacing=12,
            ),
            padding=AppTheme.PAD_MD,
            bgcolor=AppTheme.SURFACE,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        # PIN Management Section
        pin_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.LOCK_RESET, size=20, color=AppTheme.PRIMARY),
                            ft.Text("Payment & Authorization PIN Management", size=16, weight=ft.FontWeight.BOLD),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Text(
                        "Manage the 4-digit administrative authorization PIN used to approve payment confirmations and fee revisions.",
                        size=AppTheme.SIZE_CAPTION,
                        color=AppTheme.TEXT_SECONDARY,
                    ),
                    ft.Row(
                        controls=[
                            self.current_pin_field,
                            self.new_pin_field,
                            ft.ElevatedButton(
                                content=ft.Text("Update PIN"),
                                icon=ft.Icons.CHECK,
                                on_click=self._handle_pin_update,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=12,
                    ),
                    self.pin_message_text,
                ],
                spacing=10,
            ),
            padding=AppTheme.PAD_MD,
            bgcolor=AppTheme.SURFACE,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        # Audit Logs Section
        audit_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.SECURITY, size=20, color=AppTheme.PRIMARY),
                            ft.Text("Security & Authentication Audit Trail", size=16, weight=ft.FontWeight.BOLD),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(
                        content=self.audit_table,
                        border_radius=AppTheme.RADIUS_MD,
                    ),
                ],
                spacing=12,
            ),
            padding=AppTheme.PAD_MD,
            bgcolor=AppTheme.SURFACE,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
        )

        self.content = ft.ListView(
            controls=[
                header_card,
                ft.Container(height=12),
                quick_actions,
                ft.Container(height=12),
                pin_section,
                ft.Container(height=12),
                audit_section,
            ],
            spacing=0,
            expand=True,
        )

    def _handle_pin_update(self, e: ft.ControlEvent) -> None:
        curr_pin = self.current_pin_field.value or ""
        new_pin = self.new_pin_field.value or ""

        try:
            self.settings_service.set_admin_pin(new_pin=new_pin, current_pin=curr_pin)
            self.pin_message_text.value = "Authorization PIN successfully updated."
            self.pin_message_text.color = AppTheme.SUCCESS
            self.current_pin_field.value = ""
            self.new_pin_field.value = ""
        except Exception as exc:
            self.pin_message_text.value = f"Failed to update PIN: {str(exc)}"
            self.pin_message_text.color = AppTheme.DANGER

        if self.page:
            self.update()

    def load_data(self) -> None:
        """Fetch and populate security audit trail logs."""
        try:
            logs = self.activity_repo.get_recent_logs(limit=25)
            # Filter or prioritize SECURITY events
            rows = []
            for log in logs:
                action = str(log.get("action", ""))
                is_sec = log.get("entity_type") == "SECURITY"
                badge_color = (
                    AppTheme.SUCCESS
                    if "SUCCESS" in action or "VERIFIED" in action
                    else (AppTheme.DANGER if "FAILURE" in action or "BLOCKED" in action or "LOCKED" in action else AppTheme.PRIMARY)
                )

                rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(str(log.get("created_at", "")))),
                            ft.DataCell(
                                ft.Container(
                                    content=ft.Text(
                                        action,
                                        size=12,
                                        weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.WHITE if is_sec else AppTheme.TEXT_PRIMARY,
                                    ),
                                    bgcolor=badge_color if is_sec else AppTheme.SURFACE_VARIANT,
                                    padding=ft.Padding(6, 2, 6, 2),
                                    border_radius=AppTheme.RADIUS_SM,
                                )
                            ),
                            ft.DataCell(ft.Text(str(log.get("actor_name", "SYSTEM")))),
                            ft.DataCell(ft.Text(str(log.get("details", "") or "—"))),
                        ]
                    )
                )
            self.audit_table.rows = rows
            if self.page:
                self.update()
        except Exception:
            pass
