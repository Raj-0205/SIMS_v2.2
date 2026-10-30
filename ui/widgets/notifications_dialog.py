# ui/widgets/notifications_dialog.py

from __future__ import annotations
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
import flet as ft

from ui.themes.theme import AppTheme
from ui.widgets.hover_card import HoverCard
from ui.widgets.badge import StatusBadge
from modules.admission.activity_log_repository import ActivityLogRepository

__all__ = [
    "NotificationsDialog",
    "NotificationsScreenView",
    "open_notifications_dialog",
]


def _format_time_display(dt_str: str) -> str:
    """Formats 'YYYY-MM-DD HH:MM:SS' into friendly 12-hour time display."""
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%I:%M:%S %p")
    except Exception:
        return dt_str or ""


def _get_date_section_info(date_str: str) -> tuple[str, str]:
    """
    Returns (badge_label, full_formatted_date) for WhatsApp-style chat timeline.
    e.g. ('Today', 'Thursday, 29 October 2026')
         ('Yesterday', 'Wednesday, 28 October 2026')
         ('Tuesday', '27 October 2026')
    """
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return (date_str, date_str)

    today = datetime.now().date()
    if d == today:
        return ("Today", d.strftime("%A, %d %B %Y"))
    elif d == today - timedelta(days=1):
        return ("Yesterday", d.strftime("%A, %d %B %Y"))
    elif d > today - timedelta(days=7):
        return (d.strftime("%A"), d.strftime("%d %B %Y"))
    else:
        return (d.strftime("%d %B %Y"), d.strftime("%A, %d %B %Y"))


def _get_entity_icon(entity_type: str) -> str:
    ent = (entity_type or "").upper()
    if ent in ("ADMISSION", "ADMISSIONS"):
        return ft.Icons.HOW_TO_REG
    elif ent in ("STUDENT", "STUDENTS"):
        return ft.Icons.PERSON
    elif ent in ("PAYMENT", "PAYMENTS", "FEE", "FEES"):
        return ft.Icons.PAYMENTS
    elif ent in ("COURSE", "COURSES"):
        return ft.Icons.MENU_BOOK
    elif ent in ("BATCH", "BATCHES"):
        return ft.Icons.GROUP_WORK
    elif ent in ("ATTENDANCE",):
        return ft.Icons.CO_PRESENT
    elif ent in ("SECURITY", "AUTH"):
        return ft.Icons.SHIELD
    elif ent in ("SETTINGS", "SYSTEM"):
        return ft.Icons.SETTINGS
    return ft.Icons.NOTIFICATIONS


def _get_action_badge_variant(action: str) -> str:
    act = (action or "").upper()
    if any(k in act for k in ("CREATED", "SUCCESS", "COMPLETED", "ACTIVE", "CONFIRMED")):
        return "success"
    elif any(k in act for k in ("UPDATED", "CHANGED", "RECORDED", "INFO")):
        return "neutral"
    elif any(k in act for k in ("WARN", "OVERRIDE", "PENDING")):
        return "warning"
    elif any(k in act for k in ("FAIL", "DELETE", "DELETED", "INACTIVE", "ERROR", "DANGER")):
        return "danger"
    return "neutral"


def _build_date_separator(badge: str, full_date: str) -> ft.Control:
    """Builds a WhatsApp-style centered floating date badge separator."""
    label_text = f"{badge}  •  {full_date}" if badge != full_date else badge
    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.CALENDAR_MONTH, size=13, color=AppTheme.PRIMARY),
                            ft.Text(
                                label_text,
                                size=11,
                                weight=ft.FontWeight.BOLD,
                                color=AppTheme.TEXT_SECONDARY,
                            ),
                        ],
                        spacing=6,
                        tight=True,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    bgcolor=AppTheme.SURFACE_VARIANT,
                    padding=ft.Padding(16, 5, 16, 5),
                    border_radius=AppTheme.RADIUS_PILL,
                    border=ft.Border.all(1, AppTheme.BORDER),
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        padding=ft.Padding(0, 14, 0, 6),
    )


class NotificationsDialog(ft.AlertDialog):
    """
    Action History & Activity Notification Modal with WhatsApp-style Date Sections.
    Groups actions chronologically under date headers as the user scrolls.
    """

    def __init__(self, page: ft.Page):
        self._page = page
        self.repo = ActivityLogRepository()
        self.selected_filter: str = "ALL"
        self.search_term: str = ""
        self.show_today_only: bool = False
        self.all_logs: list[dict[str, Any]] = []

        self.list_container = ft.Column(
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        self.count_badge_text = ft.Text("0 Actions", size=11, weight=ft.FontWeight.BOLD, color=AppTheme.PRIMARY)
        self.count_badge = ft.Container(
            content=self.count_badge_text,
            bgcolor=AppTheme.PRIMARY_LIGHT,
            padding=ft.Padding(8, 2, 8, 2),
            border_radius=AppTheme.RADIUS_PILL,
        )

        self.search_box = ft.TextField(
            hint_text="Search actions, user, details, or date...",
            prefix_icon=ft.Icons.SEARCH,
            dense=True,
            content_padding=ft.Padding(10, 8, 10, 8),
            border_radius=AppTheme.RADIUS_MD,
            on_change=self._on_search_change,
            expand=True,
        )

        # Module quick filter buttons
        self.filter_row = ft.Row(
            controls=[
                self._make_filter_chip("All Actions", "ALL"),
                self._make_filter_chip("Admissions", "ADMISSION"),
                self._make_filter_chip("Payments", "PAYMENT"),
                self._make_filter_chip("Students", "STUDENT"),
                self._make_filter_chip("Security", "SECURITY"),
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=6,
        )

        today_str = datetime.now().strftime("%A, %d %B %Y")

        content_body = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Row([self.count_badge], spacing=6),
                            ft.Text(f"Activity History Timeline  •  {today_str}", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Row(
                        controls=[
                            self.search_box,
                            ft.IconButton(
                                icon=ft.Icons.REFRESH,
                                tooltip="Refresh Actions",
                                icon_color=AppTheme.PRIMARY,
                                on_click=lambda _: self.load_data(),
                            ),
                        ],
                        spacing=8,
                    ),
                    self.filter_row,
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    ft.Container(
                        content=self.list_container,
                        height=440,
                        width=660,
                    ),
                ],
                spacing=AppTheme.PAD_SM,
                tight=True,
            ),
            width=670,
            padding=AppTheme.PAD_SM,
        )

        def close_modal(e=None):
            self.open = False
            if hasattr(self._page, "pop_dialog"):
                try:
                    self._page.pop_dialog()
                except Exception:
                    pass
            elif hasattr(self._page, "dialog"):
                self._page.dialog = None
            try:
                self._page.update()
            except Exception:
                pass

        super().__init__(
            modal=True,
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.NOTIFICATIONS, color=AppTheme.PRIMARY, size=24),
                    ft.Text("Notifications — Daily Action History", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, selectable=True),
                ],
                spacing=AppTheme.PAD_SM,
            ),
            content=ft.SelectionArea(content=content_body),
            actions=[
                ft.OutlinedButton(
                    content=ft.Text("View Today Only" if not self.show_today_only else "View All History"),
                    icon=ft.Icons.FILTER_ALT_OUTLINED,
                    on_click=self._toggle_scope,
                ),
                ft.ElevatedButton(
                    content=ft.Text("Close"),
                    on_click=close_modal,
                    style=ft.ButtonStyle(bgcolor=AppTheme.PRIMARY, color=ft.Colors.WHITE),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        self.handle_cancel = close_modal
        self.close_dialog = close_modal

        self.load_data()

    def _make_filter_chip(self, label: str, filter_key: str) -> ft.Control:
        is_active = (self.selected_filter == filter_key)
        return ft.Container(
            content=ft.Text(
                label,
                size=12,
                weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL,
                color=AppTheme.SURFACE if is_active else AppTheme.TEXT_PRIMARY,
            ),
            bgcolor=AppTheme.PRIMARY if is_active else AppTheme.SURFACE_VARIANT,
            padding=ft.Padding(10, 4, 10, 4),
            border_radius=AppTheme.RADIUS_PILL,
            border=ft.Border.all(1, AppTheme.PRIMARY if is_active else AppTheme.BORDER),
            on_click=lambda _, fk=filter_key: self._on_filter_select(fk),
        )

    def _on_filter_select(self, filter_key: str) -> None:
        self.selected_filter = filter_key
        self.filter_row.controls = [
            self._make_filter_chip("All Actions", "ALL"),
            self._make_filter_chip("Admissions", "ADMISSION"),
            self._make_filter_chip("Payments", "PAYMENT"),
            self._make_filter_chip("Students", "STUDENT"),
            self._make_filter_chip("Security", "SECURITY"),
        ]
        self._render_logs()
        self._safe_update()

    def _on_search_change(self, e: ft.ControlEvent) -> None:
        self.search_term = (self.search_box.value or "").strip().lower()
        self._render_logs()
        self._safe_update()

    def _toggle_scope(self, e: ft.ControlEvent = None) -> None:
        self.show_today_only = not self.show_today_only
        btn: ft.OutlinedButton = self.actions[0]
        btn.content = ft.Text("View Today Only" if not self.show_today_only else "View All History")
        self.load_data()

    def load_data(self) -> None:
        try:
            if self.show_today_only:
                self.all_logs = self.repo.get_today_logs(limit=250)
            else:
                self.all_logs = self.repo.get_recent_logs(limit=300)
        except Exception:
            self.all_logs = []

        total_cnt = len(self.all_logs)
        today_cnt = self.repo.get_today_count()
        if self.show_today_only:
            self.count_badge_text.value = f"{total_cnt} Today"
        else:
            self.count_badge_text.value = f"{today_cnt} Today • {total_cnt} Total"
        self._render_logs()
        self._safe_update()

    def _render_logs(self) -> None:
        self.list_container.controls.clear()

        filtered = []
        for l in self.all_logs:
            ent = (l.get("entity_type") or "").upper()
            if self.selected_filter != "ALL" and ent != self.selected_filter:
                continue

            if self.search_term:
                details = str(l.get("details") or "").lower()
                action = str(l.get("action") or "").lower()
                actor = str(l.get("actor_name") or "").lower()
                created_at = str(l.get("created_at") or "").lower()
                if (self.search_term not in details and
                    self.search_term not in action and
                    self.search_term not in actor and
                    self.search_term not in ent.lower() and
                    self.search_term not in created_at):
                    continue

            filtered.append(l)

        if not filtered:
            msg = "No actions recorded yet today." if self.show_today_only else "No activity logs found."
            submsg = "Actions performed across admissions, payments, students, and settings will automatically appear here."
            self.list_container.controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.NOTIFICATIONS_NONE, size=48, color=AppTheme.TEXT_MUTED),
                            ft.Text(msg, size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_SECONDARY),
                            ft.Text(submsg, size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_MUTED, text_align=ft.TextAlign.CENTER),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                    ),
                    alignment=ft.Alignment.CENTER,
                    padding=ft.Padding(20, 60, 20, 40),
                )
            )
            return

        # ── Group actions by calendar date (WhatsApp style) ──
        logs_by_date: dict[str, list[dict[str, Any]]] = {}
        for item in filtered:
            created_at = item.get("created_at") or ""
            date_part = created_at.split(" ")[0] if " " in created_at else created_at
            if not date_part:
                date_part = datetime.now().strftime("%Y-%m-%d")
            if date_part not in logs_by_date:
                logs_by_date[date_part] = []
            logs_by_date[date_part].append(item)

        # Render each date section and its column of actions
        for date_str, actions in logs_by_date.items():
            badge, full_d = _get_date_section_info(date_str)
            # 1. Date Header Badge
            self.list_container.controls.append(_build_date_separator(badge, full_d))

            # 2. Actions list for that date
            for item in actions:
                ent_type = item.get("entity_type") or "SYSTEM"
                action = item.get("action") or "ACTION"
                actor = item.get("actor_name") or "SYSTEM"
                details = item.get("details") or "No details recorded"
                created_at = item.get("created_at") or ""
                time_display = _format_time_display(created_at)

                icon_name = _get_entity_icon(ent_type)
                badge_var = _get_action_badge_variant(action)

                card_row = ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Icon(icon_name, size=20, color=AppTheme.PRIMARY),
                                bgcolor=AppTheme.PRIMARY_LIGHT,
                                padding=ft.Padding(8, 8, 8, 8),
                                border_radius=AppTheme.RADIUS_SM,
                            ),
                            ft.Column(
                                controls=[
                                    ft.Row(
                                        controls=[
                                            ft.Text(f"{ent_type}", size=AppTheme.SIZE_BODY, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                                            StatusBadge(text=action, variant=badge_var),
                                            ft.Text(f"by {actor}", size=AppTheme.SIZE_CAPTION, color=AppTheme.TEXT_SECONDARY, weight=ft.FontWeight.W_500),
                                        ],
                                        spacing=8,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    ft.Text(
                                        details,
                                        size=13,
                                        color=AppTheme.TEXT_PRIMARY,
                                        weight=ft.FontWeight.NORMAL,
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.Text(
                                time_display,
                                size=11,
                                color=AppTheme.TEXT_SECONDARY,
                                weight=ft.FontWeight.W_500,
                            ),
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding(12, 10, 12, 10),
                    bgcolor=AppTheme.SURFACE,
                    border_radius=AppTheme.RADIUS_MD,
                    border=ft.Border.all(1, AppTheme.BORDER),
                )
                self.list_container.controls.append(card_row)

    def _safe_update(self) -> None:
        p = self._page
        if p:
            try:
                p.update()
            except Exception:
                pass


def open_notifications_dialog(page: ft.Page) -> NotificationsDialog:
    """Helper function to instantiate and display the Notifications Dialog on any page."""
    dlg = NotificationsDialog(page)
    page.dialog = dlg
    if hasattr(page, "show_dialog"):
        try:
            page.show_dialog(dlg)
        except Exception:
            dlg.open = True
            try:
                page.update()
            except Exception:
                pass
    else:
        dlg.open = True
        try:
            page.update()
        except Exception:
            pass
    return dlg


class NotificationsScreenView(ft.Container):
    """Full-page notifications view mounted inside ContentHost for /notifications route with date sections."""

    def __init__(self):
        self.repo = ActivityLogRepository()
        self.list_column = ft.Column(spacing=8, expand=True, scroll=ft.ScrollMode.AUTO)
        today_str = datetime.now().strftime("%A, %d %B %Y")

        content = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Column(
                            controls=[
                                ft.Text("Notifications — Action History Timeline", size=AppTheme.SIZE_H1, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                                ft.Text(f"Chronological record of actions performed across the institute  •  {today_str}", size=AppTheme.SIZE_BODY, color=AppTheme.TEXT_SECONDARY),
                            ],
                            spacing=2,
                        ),
                        ft.ElevatedButton(
                            "Refresh",
                            icon=ft.Icons.REFRESH,
                            style=ft.ButtonStyle(bgcolor=AppTheme.PRIMARY, color=AppTheme.SURFACE),
                            on_click=lambda _: self.load_data(),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Divider(height=1, color=AppTheme.BORDER),
                self.list_column,
            ],
            spacing=AppTheme.PAD_MD,
            expand=True,
        )

        super().__init__(
            content=ft.SelectionArea(content=content),
            padding=AppTheme.PAD_LG,
            expand=True,
        )

    def load_data(self) -> None:
        self.list_column.controls.clear()
        try:
            logs = self.repo.get_recent_logs(limit=300)
        except Exception:
            logs = []

        if not logs:
            self.list_column.controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.NOTIFICATIONS_NONE, size=54, color=AppTheme.TEXT_MUTED),
                            ft.Text("No actions performed yet.", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_SECONDARY),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                    ),
                    padding=ft.Padding(20, 80, 20, 40),
                )
            )
            return

        # Group actions by calendar date (WhatsApp style)
        logs_by_date: dict[str, list[dict[str, Any]]] = {}
        for item in logs:
            created_at = item.get("created_at") or ""
            date_part = created_at.split(" ")[0] if " " in created_at else created_at
            if not date_part:
                date_part = datetime.now().strftime("%Y-%m-%d")
            if date_part not in logs_by_date:
                logs_by_date[date_part] = []
            logs_by_date[date_part].append(item)

        for date_str, actions in logs_by_date.items():
            badge, full_d = _get_date_section_info(date_str)
            self.list_column.controls.append(_build_date_separator(badge, full_d))

            for item in actions:
                ent_type = item.get("entity_type") or "SYSTEM"
                action = item.get("action") or "ACTION"
                actor = item.get("actor_name") or "SYSTEM"
                details = item.get("details") or "No details recorded"
                created_at = item.get("created_at") or ""
                time_display = _format_time_display(created_at)

                self.list_column.controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(_get_entity_icon(ent_type), size=22, color=AppTheme.PRIMARY),
                                ft.Column(
                                    controls=[
                                        ft.Row(
                                            controls=[
                                                ft.Text(ent_type, weight=ft.FontWeight.BOLD),
                                                StatusBadge(text=action, variant=_get_action_badge_variant(action)),
                                                ft.Text(f"by {actor}", size=12, color=AppTheme.TEXT_SECONDARY),
                                            ],
                                            spacing=8,
                                        ),
                                        ft.Text(details, size=13),
                                    ],
                                    spacing=2,
                                    expand=True,
                                ),
                                ft.Text(time_display, size=12, color=AppTheme.TEXT_SECONDARY),
                            ],
                            spacing=12,
                        ),
                        padding=ft.Padding(14, 12, 14, 12),
                        bgcolor=AppTheme.SURFACE,
                        border_radius=AppTheme.RADIUS_MD,
                        border=ft.Border.all(1, AppTheme.BORDER),
                    )
                )
        try:
            self.update()
        except Exception:
            pass
