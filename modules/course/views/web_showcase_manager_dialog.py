# modules/course/views/web_showcase_manager_dialog.py

from __future__ import annotations
import webbrowser
from typing import Any, Callable, Dict, List, Optional
import flet as ft

from core.logger.service import LogService
from ui.themes.theme import AppTheme
from modules.course.showcase_adapter import (
    load_showcase_config,
    save_showcase_config,
    get_all_showcase_courses,
    sync_showcase_web_stores,
    add_course_to_recommended,
    remove_course_from_recommended,
    toggle_course_trending,
    toggle_course_web_visibility,
    set_course_section,
    TRACK_CONFIGS,
)
from modules.course.showcase_server import get_showcase_url

TRACK_OPTIONS = [
    ("flagship", "👑 Flagship IT & MS-CIT"),
    ("accounting", "📊 Accounting & Tally/Excel"),
    ("design", "🎨 Graphic, AutoCAD & 3D Design"),
    ("software", "💻 Coding & Python Programming"),
    ("emerging", "🤖 AI & Emerging Technologies"),
    ("hardware", "🛡️ Hardware, Networking & Cyber"),
    ("office", "📁 Back Office, MIS & Cloud"),
    ("frontoffice", "🗣️ English & Professional Skills"),
]


class WebShowcaseManagerDialog(ft.AlertDialog):
    """
    Administrator Web Showcase Content Management System (CMS).
    Allows full control over which courses appear in the Recommended section,
    trending tags, web sections/tracks, and website publishing.
    """

    def __init__(self, controller: Any, on_synced: Optional[Callable[[], None]] = None) -> None:
        super().__init__()
        self.controller = controller
        self.on_synced = on_synced
        self.modal = True

        self.config: Dict[str, Any] = load_showcase_config()
        self.all_courses: List[Dict[str, Any]] = get_all_showcase_courses(self.controller)

        self.active_tab_idx: int = 0
        self._init_ui()

    def _init_ui(self) -> None:
        self.title = ft.Row(
            controls=[
                ft.Icon(ft.Icons.DASHBOARD_CUSTOMIZE, color=AppTheme.PRIMARY, size=24),
                ft.Column(
                    controls=[
                        ft.Text("Web Showcase & Section CMS", size=AppTheme.SIZE_H3, weight=ft.FontWeight.BOLD, color=AppTheme.TEXT_PRIMARY),
                        ft.Text("Sudharm Infotech • MKCL Authorised Centre • Manage Web Sections & Recommended Courses", size=12, color=AppTheme.TEXT_SECONDARY),
                    ],
                    spacing=2,
                ),
            ],
            spacing=10,
        )

        # Tab Navigation
        self.tabs_row = ft.Row(
            controls=[
                ft.ElevatedButton(
                    "⭐ Recommended Section",
                    icon=ft.Icons.STAR,
                    bgcolor=AppTheme.PRIMARY if self.active_tab_idx == 0 else AppTheme.SURFACE,
                    color=AppTheme.SURFACE if self.active_tab_idx == 0 else AppTheme.TEXT_PRIMARY,
                    on_click=lambda _: self._switch_tab(0),
                ),
                ft.ElevatedButton(
                    "🏷️ Sections & Tracks",
                    icon=ft.Icons.CATEGORY,
                    bgcolor=AppTheme.PRIMARY if self.active_tab_idx == 1 else AppTheme.SURFACE,
                    color=AppTheme.SURFACE if self.active_tab_idx == 1 else AppTheme.TEXT_PRIMARY,
                    on_click=lambda _: self._switch_tab(1),
                ),
                ft.ElevatedButton(
                    "🔥 Trending & Visibility",
                    icon=ft.Icons.LOCAL_FIRE_DEPARTMENT,
                    bgcolor=AppTheme.PRIMARY if self.active_tab_idx == 2 else AppTheme.SURFACE,
                    color=AppTheme.SURFACE if self.active_tab_idx == 2 else AppTheme.TEXT_PRIMARY,
                    on_click=lambda _: self._switch_tab(2),
                ),
            ],
            spacing=8,
        )

        self.tab_container = ft.Container(
            content=self._build_tab_content(),
            width=920,
            height=500,
            padding=ft.Padding(12, 12, 12, 12),
        )

        self.content = ft.Column(
            controls=[
                self.tabs_row,
                ft.Divider(height=1, color=AppTheme.BORDER),
                self.tab_container,
            ],
            spacing=12,
            tight=True,
        )

        self.actions = [
            ft.OutlinedButton(
                "🌐 Open Webpage",
                icon=ft.Icons.OPEN_IN_BROWSER,
                on_click=self._handle_open_webpage,
            ),
            ft.ElevatedButton(
                "💾 Save & Sync to Webpage",
                icon=ft.Icons.SYNC,
                bgcolor=AppTheme.SUCCESS,
                color=AppTheme.SURFACE,
                on_click=self._handle_save_sync,
            ),
            ft.TextButton("Close", on_click=self._handle_close),
        ]
        self.actions_alignment = ft.MainAxisAlignment.END

    def _switch_tab(self, idx: int) -> None:
        self.active_tab_idx = idx
        self._init_ui()
        try:
            self.update()
        except Exception:
            pass

    def _build_tab_content(self) -> ft.Control:
        if self.active_tab_idx == 0:
            return self._build_recommended_tab()
        elif self.active_tab_idx == 1:
            return self._build_sections_tab()
        else:
            return self._build_trending_visibility_tab()

    def _build_recommended_tab(self) -> ft.Control:
        rec_ids = set(self.config.get("recommended_course_ids", []))
        rec_courses = [c for c in self.all_courses if c.get("id") in rec_ids]
        available_courses = [c for c in self.all_courses if c.get("id") not in rec_ids]

        # Add course picker
        self.add_course_dropdown = ft.Dropdown(
            label="Select Course to Add to Recommended Section",
            hint_text="Choose from available master courses...",
            options=[ft.DropdownOption(key=c.get("id"), text=f"{c.get('title')} ({c.get('code')})") for c in available_courses],
            expand=True,
            dense=True,
        )

        add_btn = ft.ElevatedButton(
            "➕ Add to Recommended",
            icon=ft.Icons.ADD,
            bgcolor=AppTheme.PRIMARY,
            color=AppTheme.SURFACE,
            on_click=self._handle_add_to_recommended,
        )

        add_bar = ft.Container(
            content=ft.Row(
                controls=[
                    self.add_course_dropdown,
                    add_btn,
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(8, 8, 8, 8),
            bgcolor=AppTheme.SURFACE_VARIANT,
            border_radius=8,
        )

        # List of recommended course rows
        rec_rows = []
        for c in rec_courses:
            cid = c.get("id")
            is_trending = cid in self.config.get("trending_course_ids", []) or cid == "ms-cit"
            badge_icon = "🔥 " if is_trending else "⭐ "

            row = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.DRAG_HANDLE, color=AppTheme.TEXT_MUTED, size=18),
                        ft.Column(
                            controls=[
                                ft.Text(f"{badge_icon}{c.get('title')}", weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_BODY, color=AppTheme.TEXT_PRIMARY),
                                ft.Text(f"Code: {c.get('code')} • Track: {c.get('category')} • Fee: {c.get('fee')}", size=12, color=AppTheme.TEXT_SECONDARY),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.ElevatedButton(
                            "❌ Remove",
                            icon=ft.Icons.DELETE_OUTLINE,
                            bgcolor=AppTheme.DANGER,
                            color=AppTheme.SURFACE,
                            on_click=lambda _, course_id=cid: self._handle_remove_recommended(course_id),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding(12, 10, 12, 10),
                border=ft.Border.all(1, AppTheme.BORDER),
                border_radius=8,
                bgcolor=AppTheme.SURFACE,
            )
            rec_rows.append(row)

        if not rec_rows:
            rec_rows.append(
                ft.Container(
                    content=ft.Text("No courses currently in Recommended section. Add courses using the selector above.", color=AppTheme.TEXT_MUTED),
                    padding=20,
                    alignment=ft.Alignment(0, 0),
                )
            )

        return ft.Column(
            controls=[
                ft.Text(f"Currently Showing {len(rec_courses)} Courses in Recommended Section", weight=ft.FontWeight.W_600, color=AppTheme.TEXT_PRIMARY),
                add_bar,
                ft.Column(controls=rec_rows, spacing=8, scroll=ft.ScrollMode.AUTO, expand=True),
            ],
            spacing=10,
            expand=True,
        )

    def _build_sections_tab(self) -> ft.Control:
        course_sections = self.config.get("course_sections", {})
        section_rows = []

        for c in self.all_courses:
            cid = c.get("id")
            current_track = course_sections.get(cid, c.get("track_id", "software"))

            dd = ft.Dropdown(
                options=[ft.DropdownOption(key=opt_id, text=opt_label) for opt_id, opt_label in TRACK_OPTIONS],
                value=current_track,
                dense=True,
                width=240,
                on_select=lambda e, course_id=cid: self._handle_section_change(course_id, e.control.value),
            )

            row = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Column(
                            controls=[
                                ft.Text(c.get("title"), weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_BODY, color=AppTheme.TEXT_PRIMARY),
                                ft.Text(f"Code: {c.get('code')} • Original Category: {c.get('category')}", size=12, color=AppTheme.TEXT_SECONDARY),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        dd,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding(10, 8, 10, 8),
                border=ft.Border.all(1, AppTheme.BORDER),
                border_radius=8,
                bgcolor=AppTheme.SURFACE,
            )
            section_rows.append(row)

        return ft.Column(
            controls=[
                ft.Text("Assign Courses to Specialized Career Tracks & Website Sections", weight=ft.FontWeight.W_600, color=AppTheme.TEXT_PRIMARY),
                ft.Column(controls=section_rows, spacing=6, scroll=ft.ScrollMode.AUTO, expand=True),
            ],
            spacing=10,
            expand=True,
        )

    def _build_trending_visibility_tab(self) -> ft.Control:
        trending_ids = set(self.config.get("trending_course_ids", []))
        hidden_ids = set(self.config.get("hidden_course_ids", []))

        item_rows = []
        for c in self.all_courses:
            cid = c.get("id")
            is_trending = cid in trending_ids or cid == "ms-cit"
            is_visible = cid not in hidden_ids

            trending_btn = ft.ElevatedButton(
                "🔥 Trending Active" if is_trending else "Mark Trending",
                icon=ft.Icons.WHATSHOT if is_trending else ft.Icons.LOCAL_FIRE_DEPARTMENT_OUTLINED,
                bgcolor=AppTheme.DANGER if is_trending else AppTheme.SURFACE,
                color=AppTheme.SURFACE if is_trending else AppTheme.TEXT_PRIMARY,
                on_click=lambda _, course_id=cid: self._handle_toggle_trending(course_id),
            )

            vis_btn = ft.ElevatedButton(
                "👁️ Published on Web" if is_visible else "🚫 Hidden on Web",
                icon=ft.Icons.VISIBILITY if is_visible else ft.Icons.VISIBILITY_OFF,
                bgcolor=AppTheme.SUCCESS if is_visible else AppTheme.WARNING,
                color=AppTheme.SURFACE,
                on_click=lambda _, course_id=cid: self._handle_toggle_visibility(course_id),
            )

            row = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Column(
                            controls=[
                                ft.Text(c.get("title"), weight=ft.FontWeight.BOLD, size=AppTheme.SIZE_BODY, color=AppTheme.TEXT_PRIMARY),
                                ft.Text(f"Code: {c.get('code')} • Duration: {c.get('duration')}", size=12, color=AppTheme.TEXT_SECONDARY),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        trending_btn,
                        vis_btn,
                    ],
                    spacing=8,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding(10, 8, 10, 8),
                border=ft.Border.all(1, AppTheme.BORDER),
                border_radius=8,
                bgcolor=AppTheme.SURFACE,
            )
            item_rows.append(row)

        return ft.Column(
            controls=[
                ft.Text("Manage High-Impact Badges (Trending Tag) and Web Publication Visibility", weight=ft.FontWeight.W_600, color=AppTheme.TEXT_PRIMARY),
                ft.Column(controls=item_rows, spacing=6, scroll=ft.ScrollMode.AUTO, expand=True),
            ],
            spacing=10,
            expand=True,
        )

    def _handle_add_to_recommended(self, e: ft.ControlEvent) -> None:
        val = self.add_course_dropdown.value
        if not val:
            return
        add_course_to_recommended(val)
        self.config = load_showcase_config()
        self._init_ui()
        try:
            self.update()
        except Exception:
            pass

    def _handle_remove_recommended(self, course_id: str) -> None:
        remove_course_from_recommended(course_id)
        self.config = load_showcase_config()
        self._init_ui()
        try:
            self.update()
        except Exception:
            pass

    def _handle_section_change(self, course_id: str, section_id: str) -> None:
        set_course_section(course_id, section_id)
        self.config = load_showcase_config()

    def _handle_toggle_trending(self, course_id: str) -> None:
        toggle_course_trending(course_id)
        self.config = load_showcase_config()
        self._init_ui()
        try:
            self.update()
        except Exception:
            pass

    def _handle_toggle_visibility(self, course_id: str) -> None:
        toggle_course_web_visibility(course_id)
        self.config = load_showcase_config()
        self._init_ui()
        try:
            self.update()
        except Exception:
            pass

    @property
    def safe_page(self) -> Optional[ft.Page]:
        try:
            custom = getattr(self, "_page", None)
            if custom:
                return custom
            return self.page
        except (RuntimeError, AttributeError):
            return getattr(self, "_page", None)

    def _handle_save_sync(self, e: ft.ControlEvent) -> None:
        result = sync_showcase_web_stores(self.controller)
        LogService.info(f"Showcase stores synchronized by administrator: {result}", context="WebShowcaseManager")
        p = self.safe_page
        if p:
            msg = f"Webpage synchronized successfully! {result.get('count', 0)} courses updated ({result.get('recommended', 0)} in Recommended)."
            p.snack_bar = ft.SnackBar(ft.Text(f"✅ {msg}"), bgcolor=AppTheme.SUCCESS)
            p.snack_bar.open = True
            try:
                p.update()
            except Exception:
                pass
        if self.on_synced:
            self.on_synced()

    def _handle_open_webpage(self, e: ft.ControlEvent) -> None:
        from core.utils.url_utils import safe_open_url
        url = get_showcase_url()
        p = self.safe_page
        safe_open_url(url, page=p)
        if p:
            p.snack_bar = ft.SnackBar(ft.Text(f"🌐 Opened: {url}"), bgcolor=AppTheme.PRIMARY)
            p.snack_bar.open = True
            try:
                p.update()
            except Exception:
                pass

    def _handle_close(self, e: ft.ControlEvent) -> None:
        self.open = False
        try:
            self.update()
        except Exception:
            pass
        p = self.safe_page
        if p:
            try:
                p.update()
            except Exception:
                pass
