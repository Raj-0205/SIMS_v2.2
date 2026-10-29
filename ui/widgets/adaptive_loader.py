# ui/widgets/adaptive_loader.py

from __future__ import annotations
from typing import Dict, Any, Optional
import flet as ft
from ui.themes.theme import AppTheme

__all__ = ["AdaptiveModuleLoader", "MODULE_ROUTE_METADATA"]

MODULE_ROUTE_METADATA: Dict[str, Dict[str, Any]] = {
    "/dashboard": {
        "title": "Enterprise Dashboard",
        "icon": ft.Icons.DASHBOARD,
        "description": "Aggregating real-time admissions, KPI statistics, and revenue...",
        "actions": [
            ("New Admission", ft.Icons.PERSON_ADD),
            ("Fee Reports", ft.Icons.ASSESSMENT),
            ("Theme Settings", ft.Icons.PALETTE),
        ],
    },
    "/enquiries": {
        "title": "Walk-ins & Enquiries",
        "icon": ft.Icons.SUPPORT_AGENT,
        "description": "Fetching candidate enquiries, lead categories, and follow-ups...",
        "actions": [
            ("New Walk-in", ft.Icons.ADD_CALL),
            ("Follow-up Pipeline", ft.Icons.EVENT_NOTE),
            ("Lead Conversion", ft.Icons.TRENDING_UP),
        ],
    },
    "/admissions": {
        "title": "Admissions Desk",
        "icon": ft.Icons.APP_REGISTRATION,
        "description": "Loading candidate registrations, fee agreements, and payment records...",
        "actions": [
            ("Register Candidate", ft.Icons.APP_REGISTRATION),
            ("Record Payment", ft.Icons.PAYMENTS),
            ("Print Application", ft.Icons.PRINT),
        ],
    },
    "/students": {
        "title": "Students Directory",
        "icon": ft.Icons.PEOPLE,
        "description": "Querying student master records, enrollments, and academic status...",
        "actions": [
            ("Search Directory", ft.Icons.SEARCH),
            ("Filter Status", ft.Icons.FILTER_LIST),
            ("Export Excel", ft.Icons.FILE_DOWNLOAD),
        ],
    },
    "/courses": {
        "title": "Course Master Catalog",
        "icon": ft.Icons.MENU_BOOK,
        "description": "Synchronizing course offerings, modules, and fee schemes...",
        "actions": [
            ("Add Course", ft.Icons.ADD),
            ("Fee Schemes", ft.Icons.ATTACH_MONEY),
            ("Web Showcase", ft.Icons.PREVIEW),
        ],
    },
    "/batch": {
        "title": "Batch Management",
        "icon": ft.Icons.GROUP_WORK,
        "description": "Loading active batches, class schedules, and student rosters...",
        "actions": [
            ("Create Batch", ft.Icons.GROUP_ADD),
            ("Assign Faculty", ft.Icons.CO_PRESENT),
            ("Batch Schedule", ft.Icons.SCHEDULE),
        ],
    },
    "/attendance": {
        "title": "Attendance Matrix",
        "icon": ft.Icons.CO_PRESENT,
        "description": "Fetching batch rosters, monthly sheets, and attendance logs...",
        "actions": [
            ("Daily Roster", ft.Icons.FACT_CHECK),
            ("Monthly Register", ft.Icons.CALENDAR_MONTH),
            ("Excel Import", ft.Icons.UPLOAD_FILE),
        ],
    },
    "/fees": {
        "title": "Fees & Reports",
        "icon": ft.Icons.MONETIZATION_ON,
        "description": "Calculating fee collections, drafts, and ledger balances...",
        "actions": [
            ("Collect Installment", ft.Icons.MONETIZATION_ON),
            ("Outstanding Dues", ft.Icons.WARNING_AMBER),
            ("Reconciliation", ft.Icons.RECEIPT_LONG),
        ],
    },
    "/settings": {
        "title": "System Settings",
        "icon": ft.Icons.SETTINGS,
        "description": "Loading system configuration, theme preferences, and security...",
        "actions": [
            ("Theme Gallery", ft.Icons.PALETTE),
            ("Database Backup", ft.Icons.BACKUP),
            ("User Security", ft.Icons.SECURITY),
        ],
    },
    "/control-center": {
        "title": "SIMS Control Center",
        "icon": ft.Icons.ADMIN_PANEL_SETTINGS,
        "description": "Verifying governance privileges and querying audit telemetry...",
        "actions": [
            ("Audit Logs", ft.Icons.QUERY_STATS),
            ("Security Policies", ft.Icons.SECURITY),
            ("Emergency Access", ft.Icons.LOCK_RESET),
        ],
    },
    "/about": {
        "title": "About SIMS v2.2",
        "icon": ft.Icons.SCHOOL,
        "description": "Preparing application specifications and profile...",
        "actions": [
            ("System Info", ft.Icons.INFO),
            ("License", ft.Icons.VERIFIED),
            ("ARP Group", ft.Icons.CORPORATE_FARE),
        ],
    },
}


class AdaptiveModuleLoader(ft.Container):
    """
    Adaptive Module Loading Screen.

    Provides a smooth, continuous indeterminate animation during module switching.
    Runs adaptively as long as the database is querying and loading data.
    Features Figma-inspired liquid color combinations, fluid indeterminate progress,
    and visible action button previews so new users can clearly anticipate module capabilities.
    Once database preparation is complete, ContentHost transitions seamlessly to the target view.
    """

    def __init__(
        self,
        route: str,
        title: Optional[str] = None,
        icon: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        self.route = route
        meta = MODULE_ROUTE_METADATA.get(
            route,
            {
                "title": "Module Workspace",
                "icon": ft.Icons.LAYERS,
                "description": "Loading workspace and preparing data from database...",
                "actions": [
                    ("Action Controls", ft.Icons.TOUCH_APP),
                    ("Data View", ft.Icons.TABLE_CHART),
                    ("Export", ft.Icons.DOWNLOAD),
                ],
            },
        )

        self.display_title = title or meta["title"]
        self.display_icon = icon or meta["icon"]
        self.display_desc = description or meta["description"]
        self.display_actions = meta.get("actions", [])

        # Figma Liquid Color Palette
        liquid_cobalt = "#4361EE"
        liquid_cyan = "#38BDF8"
        liquid_bg_tint = "#EEF2FF"

        # Central Hero Card Controls
        icon_bubble = ft.Container(
            content=ft.Icon(self.display_icon, color=ft.Colors.WHITE, size=26),
            bgcolor=liquid_cobalt,
            padding=ft.Padding(12, 12, 12, 12),
            border_radius=AppTheme.RADIUS_MD,
            shadow=[
                ft.BoxShadow(
                    spread_radius=1,
                    blur_radius=12,
                    color="#4361EE40",
                    offset=ft.Offset(0, 4),
                )
            ],
        )

        progress_spinner = ft.ProgressRing(
            width=32,
            height=32,
            stroke_width=3.2,
            color=liquid_cyan,
        )

        title_text = ft.Text(
            f"Loading {self.display_title}",
            size=AppTheme.SIZE_H2,
            weight=ft.FontWeight.BOLD,
            color=AppTheme.TEXT_PRIMARY,
        )

        desc_text = ft.Text(
            self.display_desc,
            size=AppTheme.SIZE_BODY,
            color=AppTheme.TEXT_SECONDARY,
        )

        progress_bar = ft.ProgressBar(
            width=460,
            height=4.0,
            color=liquid_cobalt,
            bgcolor=liquid_bg_tint if not AppTheme.is_dark() else AppTheme.SURFACE_VARIANT,
            border_radius=2,
        )

        status_pulse_row = ft.Row(
            controls=[
                ft.Container(
                    width=9,
                    height=9,
                    border_radius=5,
                    bgcolor=AppTheme.SUCCESS,
                    shadow=[
                        ft.BoxShadow(
                            spread_radius=1,
                            blur_radius=6,
                            color="#10B98188",
                        )
                    ],
                ),
                ft.Text(
                    "Connecting to database • Synchronizing data...",
                    size=AppTheme.SIZE_CAPTION,
                    color=AppTheme.TEXT_MUTED,
                    weight=ft.FontWeight.W_500,
                ),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # High-visibility action pill buttons preview for new users
        action_pills = []
        for act_name, act_icon in self.display_actions:
            pill = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(act_icon, size=13, color=liquid_cobalt),
                        ft.Text(
                            act_name,
                            size=11,
                            weight=ft.FontWeight.BOLD,
                            color=AppTheme.TEXT_PRIMARY,
                        ),
                    ],
                    spacing=5,
                    tight=True,
                ),
                padding=ft.Padding(10, 5, 12, 5),
                border_radius=AppTheme.RADIUS_PILL,
                bgcolor=AppTheme.SURFACE,
                border=ft.Border.all(1.2, "#D5DCF0"),
                shadow=[
                    ft.BoxShadow(
                        blur_radius=6,
                        color="#4361EE14",
                        offset=ft.Offset(0, 2),
                    )
                ],
            )
            action_pills.append(pill)

        action_preview_section = ft.Column(
            controls=[
                ft.Divider(height=14, color=AppTheme.BORDER),
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.AUTO_AWESOME, size=13, color=liquid_cobalt),
                        ft.Text(
                            "Module Action Controls (Ready on load):",
                            size=10,
                            weight=ft.FontWeight.BOLD,
                            color=AppTheme.TEXT_SECONDARY,
                        ),
                    ],
                    spacing=4,
                ),
                ft.Row(
                    controls=action_pills,
                    spacing=AppTheme.PAD_SM,
                    wrap=True,
                ),
            ],
            spacing=4,
            tight=True,
        )

        central_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[icon_bubble, progress_spinner],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(height=AppTheme.PAD_XS),
                    title_text,
                    desc_text,
                    ft.Container(height=AppTheme.PAD_SM),
                    progress_bar,
                    status_pulse_row,
                    action_preview_section,
                ],
                spacing=6,
                tight=True,
            ),
            width=500,
            padding=ft.Padding(26, 22, 26, 22),
            bgcolor=AppTheme.SURFACE,
            border_radius=AppTheme.RADIUS_LG,
            border=ft.Border.all(1.2, AppTheme.BORDER),
            shadow=[
                ft.BoxShadow(
                    blur_radius=24,
                    spread_radius=1,
                    color="#4361EE18",
                    offset=ft.Offset(0, 8),
                ),
                ft.BoxShadow(
                    blur_radius=8,
                    spread_radius=0,
                    color="#0000000A",
                    offset=ft.Offset(0, 2),
                ),
            ],
            animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT),
        )

        # Skeleton Preview Layout (Reflects modular ERP layout structure)
        skeleton_kpis = ft.Row(
            controls=[
                self._make_skeleton_card(expand=True),
                self._make_skeleton_card(expand=True),
                self._make_skeleton_card(expand=True),
                self._make_skeleton_card(expand=True),
            ],
            spacing=AppTheme.PAD_MD,
        )

        skeleton_toolbar = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        width=320,
                        height=36,
                        bgcolor=AppTheme.SURFACE_VARIANT,
                        border_radius=AppTheme.RADIUS_MD,
                        border=ft.Border.all(1, AppTheme.BORDER),
                    ),
                    ft.Container(
                        width=140,
                        height=36,
                        bgcolor=AppTheme.SURFACE_VARIANT,
                        border_radius=AppTheme.RADIUS_MD,
                        border=ft.Border.all(1, AppTheme.BORDER),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            padding=ft.Padding(0, AppTheme.PAD_SM, 0, AppTheme.PAD_SM),
        )

        skeleton_table = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        height=36,
                        bgcolor=AppTheme.SURFACE_VARIANT,
                        border_radius=ft.BorderRadius(AppTheme.RADIUS_MD, AppTheme.RADIUS_MD, 0, 0),
                    ),
                    ft.Divider(height=1, color=AppTheme.BORDER),
                    self._make_skeleton_row(),
                    self._make_skeleton_row(),
                    self._make_skeleton_row(),
                ],
                spacing=0,
                tight=True,
            ),
            bgcolor=AppTheme.SURFACE,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
            expand=True,
        )

        # Stack central adaptive loader over muted skeleton structure
        super().__init__(
            content=ft.Stack(
                controls=[
                    ft.Column(
                        controls=[
                            skeleton_kpis,
                            skeleton_toolbar,
                            skeleton_table,
                        ],
                        spacing=AppTheme.PAD_MD,
                        expand=True,
                        opacity=0.45,
                    ),
                    ft.Container(
                        content=central_card,
                        alignment=ft.Alignment(0, -0.15),
                        expand=True,
                    ),
                ],
                expand=True,
            ),
            expand=True,
            padding=ft.Padding(AppTheme.PAD_LG, AppTheme.PAD_MD, AppTheme.PAD_LG, AppTheme.PAD_MD),
            bgcolor=AppTheme.BACKGROUND,
            alignment=ft.Alignment(0, 0),
        )

    def _make_skeleton_card(self, expand: bool = True) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(width=100, height=12, bgcolor=AppTheme.SURFACE_VARIANT, border_radius=4),
                    ft.Container(width=60, height=20, bgcolor=AppTheme.SURFACE_VARIANT, border_radius=4),
                    ft.Container(width=80, height=10, bgcolor=AppTheme.SURFACE_VARIANT, border_radius=4),
                ],
                spacing=8,
            ),
            padding=ft.Padding(18, 14, 18, 14),
            bgcolor=AppTheme.SURFACE,
            border_radius=AppTheme.RADIUS_MD,
            border=ft.Border.all(1, AppTheme.BORDER),
            expand=expand,
        )

    def _make_skeleton_row(self) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(width=100, height=14, bgcolor=AppTheme.SURFACE_VARIANT, border_radius=4),
                    ft.Container(width=180, height=14, bgcolor=AppTheme.SURFACE_VARIANT, border_radius=4),
                    ft.Container(width=140, height=14, bgcolor=AppTheme.SURFACE_VARIANT, border_radius=4),
                    ft.Container(width=90, height=14, bgcolor=AppTheme.SURFACE_VARIANT, border_radius=4),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            padding=ft.Padding(16, 12, 16, 12),
            border=ft.Border(bottom=ft.BorderSide(1, AppTheme.BORDER)),
        )
