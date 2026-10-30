from typing import Any
import flet as ft
from ui.screens.login import LoginScreen
from ui.screens.dashboard import DashboardScreen, ErrorRecoveryView
from ui.screens.recovery import PasswordRecoveryScreen
from ui.screens.break_glass import BreakGlassClaimScreen, BreakGlassRemediationScreen
from core.security.auth import AuthService
from core.security.context import SecurityContext
from core.security.session import SessionManager
from core.security.roles import Role

__all__ = ["AppRouter"]


class AppRouter:
    """
    The ultimate route gatekeeper.
    Enforces Fail-Closed logic, whitelists protected routes, and handles logouts.
    """

    PROTECTED_ROUTES = {
        "/dashboard",
        "/students",
        "/attendance",
        "/admissions",
        "/enquiries",
        "/courses",
        "/fees",
        "/batch",
        "/settings",
        "/control-center",
        "/about",
        "/notifications",
    }

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.page.on_route_change = self.handle_route_change
        self.page.on_error = self.handle_global_error
        self.page.on_keyboard_event = self.handle_keyboard_event
        self.dashboard = None
        self._route_history: list[str] = []

    def _get_active_dialog(self) -> Optional[Any]:
        """Returns the topmost open dialog from page._dialogs or page.dialog."""
        if hasattr(self.page, "_dialogs") and hasattr(self.page._dialogs, "controls"):
            dlg = next((d for d in reversed(self.page._dialogs.controls) if getattr(d, "open", False)), None)
            if dlg:
                return dlg
        if hasattr(self.page, "dialog") and self.page.dialog and getattr(self.page.dialog, "open", False):
            return self.page.dialog
        return None

    def handle_keyboard_event(self, e: Any) -> None:
        """Global keyboard shortcut router for enterprise workflow ergonomics."""
        key = str(getattr(e, "key", "")).lower()

        # F11: Toggle Fullscreen
        if key == "f11":
            try:
                if hasattr(self.page, "window") and hasattr(self.page.window, "full_screen"):
                    self.page.window.full_screen = not self.page.window.full_screen
                elif hasattr(self.page, "window_full_screen"):
                    self.page.window_full_screen = not getattr(self.page, "window_full_screen", False)
                self.page.update()
            except Exception:
                pass
            return

        # ESC: Close active popup/dialog ONLY. Never navigate away or close background work!
        if key in ("escape", "esc"):
            dlg = self._get_active_dialog()
            if dlg:
                if hasattr(dlg, "handle_escape") and callable(dlg.handle_escape):
                    try:
                        if dlg.handle_escape():
                            return
                    except Exception:
                        pass
                try:
                    if hasattr(dlg, "handle_cancel") and callable(dlg.handle_cancel):
                        dlg.handle_cancel(None)
                    elif hasattr(dlg, "close_modal") and callable(dlg.close_modal):
                        dlg.close_modal(None)
                    elif hasattr(dlg, "close_dialog") and callable(dlg.close_dialog):
                        dlg.close_dialog(None)
                    elif hasattr(dlg, "close_workspace") and callable(dlg.close_workspace):
                        dlg.close_workspace(None)
                    elif hasattr(dlg, "on_dismiss") and callable(dlg.on_dismiss):
                        dlg.on_dismiss(None)
                    elif hasattr(self.page, "pop_dialog"):
                        self.page.pop_dialog()
                    else:
                        dlg.open = False
                        self.page.update()
                    return
                except Exception:
                    pass
            elif hasattr(self.page, "pop_dialog"):
                try:
                    self.page.pop_dialog()
                except Exception:
                    pass

            # If no popup is open, do NOTHING. Preserve active background work and current route.
            return

        # ENTER: Trigger active modal submit / primary action
        if key in ("enter", "numpad enter", "return"):
            dlg = self._get_active_dialog()
            if dlg:
                if hasattr(dlg, "handle_enter") and callable(dlg.handle_enter):
                    try:
                        if dlg.handle_enter():
                            return
                    except Exception:
                        pass
                for attr in ("handle_submit", "handle_save", "handle_confirm", "on_confirm", "primary_action"):
                    action = getattr(dlg, attr, None)
                    if callable(action):
                        try:
                            action(None)
                            return
                        except Exception:
                            pass
                for btn_attr in ("submit_btn", "save_btn", "confirm_btn", "upload_btn"):
                    btn = getattr(dlg, btn_attr, None)
                    if btn and getattr(btn, "on_click", None) and not getattr(btn, "disabled", False):
                        try:
                            btn.on_click(None)
                            return
                        except Exception:
                            pass


    def handle_global_error(self, e: Any) -> None:
        """Global exception barrier. Prevents blank screen crashes and provides a Back-Step button."""
        import logging
        err_msg = str(getattr(e, "data", e) or "An unexpected UI error occurred.")
        logging.getLogger("sims.ui").error(f"Global UI Error trapped by Router: {err_msg}")

        # Safely dismiss stuck dialogs
        try:
            if hasattr(self.page, "dialog") and self.page.dialog:
                self.page.dialog.open = False
                self.page.dialog = None
            if hasattr(self.page, "pop_dialog"):
                self.page.pop_dialog()
        except Exception:
            pass

        # If dashboard is active, mount the recovery view in its content host
        if self.dashboard and hasattr(self.dashboard, "content_host"):
            current_route = self.page.route or "/dashboard"
            recovery_view = ErrorRecoveryView(
                route=current_route,
                error_message=err_msg,
                on_retry=lambda: self.dashboard.mount_view(current_route),
                on_back=self.go_back,
                on_dashboard=lambda: self.request_navigation("/dashboard"),
            )
            self.dashboard.content_host.mount(recovery_view)
            try:
                self.page.update()
            except Exception:
                pass
        else:
            fallback_view = ft.View(
                route="/error",
                controls=[
                    ErrorRecoveryView(
                        route=self.page.route or "/error",
                        error_message=err_msg,
                        on_retry=lambda: self.request_navigation("/dashboard"),
                        on_back=self.go_back,
                        on_dashboard=lambda: self.request_navigation("/dashboard"),
                    )
                ],
                padding=0,
            )
            self.page.views.clear()
            self.page.views.append(fallback_view)
            try:
                self.page.update()
            except Exception:
                pass

    def request_navigation(self, route: str) -> None:
        """Sole owner of actual navigation requests triggered by child components."""
        if self.page.route != route:
            self.page.navigate(route)

    def go_back(self) -> None:
        """Navigates back to the previous valid route in the history stack."""
        if len(self._route_history) > 1:
            self._route_history.pop()  # remove current route
            prev_route = self._route_history.pop()  # pop previous route so request_navigation will re-push it
            self.request_navigation(prev_route)
        else:
            session = AuthService._get_session(self.page)
            user_role = str(AuthService._session_get(session, "role", "") or "").strip().upper()
            fallback = "/control-center" if user_role == Role.ADMINISTRATOR.value else "/dashboard"
            self.request_navigation(fallback)

    def handle_route_change(self, e: ft.RouteChangeEvent) -> None:
        route = e.route
        user_sess = SessionManager.get_session(self.page)
        if user_sess and user_sess.is_valid():
            is_auth = True
            SecurityContext.set_current_user(
                user_sess.user_id,
                user_sess.username,
                user_sess.role,
                user_sess.security_version,
                user_sess.security_stamp,
            )
            user_role = str(user_sess.role).strip().upper()
        else:
            is_auth = AuthService.is_authenticated(self.page)
            session = AuthService._get_session(self.page)
            user_role = str(AuthService._session_get(session, "role", "") or "").strip().upper()
            if is_auth and session:
                user_id = AuthService._session_get(session, "user_id")
                username = AuthService._session_get(session, "username")
                role = AuthService._session_get(session, "role")
                sec_ver = AuthService._session_get(session, "security_version")
                sec_stamp = AuthService._session_get(session, "security_stamp")
                SecurityContext.set_current_user(user_id, username, role, sec_ver, sec_stamp)
            else:
                SecurityContext.clear()

        target_route = route

        # 1. Logout Interception
        if target_route == "/logout":
            AuthService.logout(self.page)
            SessionManager.destroy_session(self.page)
            SecurityContext.clear()
            target_route = "/login"
            is_auth = False

        # 2. Authorization Guard (Fail-Closed)
        if target_route == "/control-center":
            if not is_auth:
                target_route = "/login"
            elif user_role != Role.ADMINISTRATOR.value:
                target_route = "/dashboard"
        elif target_route in self.PROTECTED_ROUTES:
            if not is_auth:
                target_route = "/login"
        elif target_route == "/login":
            if is_auth:
                target_route = "/control-center" if user_role == Role.ADMINISTRATOR.value else "/dashboard"
        elif target_route in ("/recovery", "/break-glass"):
            if is_auth:
                target_route = "/control-center" if user_role == Role.ADMINISTRATOR.value else "/dashboard"
        elif target_route == "/recovery/remediate":
            # Must hold an active break-glass lease
            lease_data = None
            sess = getattr(self.page, "session", None)
            store = getattr(sess, "store", sess)
            if hasattr(store, "get"):
                lease_data = store.get("break_glass_lease")
            elif isinstance(store, dict):
                lease_data = store.get("break_glass_lease")
            if not lease_data or not lease_data.get("lease_granted"):
                target_route = "/login"
        else:
            # 3. Unknown route fallback
            default_home = "/control-center" if user_role == Role.ADMINISTRATOR.value else "/dashboard"
            target_route = default_home if is_auth else "/login"

        # 4. Redirect & Loop Prevention
        if target_route != route:
            self.page.navigate(target_route)
            return

        # 5. View Mounting
        if target_route == "/login":
            self.dashboard = None
            self._route_history.clear()
            if not self.page.views or self.page.views[-1].route != "/login":
                self.page.views.clear()
                self.page.views.append(ft.View(route="/login", controls=[LoginScreen(self.page)]))
        elif target_route == "/recovery":
            self.dashboard = None
            self.page.views.clear()
            self.page.views.append(ft.View(route="/recovery", controls=[PasswordRecoveryScreen(self.page)]))
        elif target_route == "/break-glass":
            self.dashboard = None
            self.page.views.clear()
            self.page.views.append(ft.View(route="/break-glass", controls=[BreakGlassClaimScreen(self.page)]))
        elif target_route == "/recovery/remediate":
            self.dashboard = None
            self.page.views.clear()
            self.page.views.append(ft.View(route="/recovery/remediate", controls=[BreakGlassRemediationScreen(self.page)]))
        else:
            if not self._route_history or self._route_history[-1] != target_route:
                self._route_history.append(target_route)

            if self.page.views and self.page.views[-1].route == "/" and self.dashboard is not None:
                self.dashboard.mount_view(target_route)
            else:
                self.page.views.clear()
                if not self.dashboard:
                    self.dashboard = DashboardScreen(
                        self.page,
                        on_route_request=self.request_navigation,
                        on_back_request=self.go_back,
                    )
                self.dashboard.mount_view(target_route)
                self.page.views.append(
                    ft.View(
                        route="/",
                        controls=[self.dashboard],
                        padding=0,
                        can_pop=False,
                    )
                )

        self.page.update()
