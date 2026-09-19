# ui/router.py

import flet as ft
from ui.screens.login import LoginScreen
from ui.screens.dashboard import DashboardScreen
from ui.screens.recovery import PasswordRecoveryScreen
from ui.screens.break_glass import BreakGlassClaimScreen, BreakGlassRemediationScreen
from core.security.auth import AuthService
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
        "/admissions",
        "/courses",
        "/fees",
        "/batch",
        "/settings",
        "/control-center",
    }

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.page.on_route_change = self.handle_route_change
        self.dashboard = None

    def request_navigation(self, route: str) -> None:
        """Sole owner of actual navigation requests triggered by child components."""
        if self.page.route != route:
            self.page.navigate(route)

    def handle_route_change(self, e: ft.RouteChangeEvent) -> None:
        route = e.route
        is_auth = AuthService.is_authenticated(self.page)
        session = AuthService._get_session(self.page)
        user_role = str(AuthService._session_get(session, "role", "") or "").strip().upper()

        target_route = route

        # 1. Logout Interception
        if target_route == "/logout":
            AuthService.logout(self.page)
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
            if self.page.views and self.page.views[-1].route == "/" and self.dashboard is not None:
                self.dashboard.mount_view(target_route)
            else:
                self.page.views.clear()
                if not self.dashboard:
                    self.dashboard = DashboardScreen(self.page, on_route_request=self.request_navigation)
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
