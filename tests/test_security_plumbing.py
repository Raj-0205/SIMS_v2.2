# tests/test_security_plumbing.py
import pytest
import flet as ft
from unittest.mock import MagicMock
from concurrent.futures import ThreadPoolExecutor

from core.security.session import SessionManager, UserSession
from core.security.context import SecurityContext
from ui.router import AppRouter

class MockPage:
    """Mock Flet Page with a session store."""
    def __init__(self):
        self.session = {}
        self.route = ""
        self.views = []
        self.on_route_change = None

    def navigate(self, route):
        self.route = route

    def update(self):
        pass

def create_mock_session(page, user_id, username, role):
    """Helper to seed a session into a mock page."""
    session = UserSession(
        user_id=user_id,
        username=username,
        role=role,
        security_version=1,
        security_stamp="stamp123",
        login_timestamp=100.0,
        last_activity_timestamp=100.0,
    )
    # Mock SessionManager's storage logic
    page.session["sims_auth_session"] = session
    return session

def test_router_synchronizes_context_on_route_change():
    """Verify that AppRouter populates SecurityContext from session on route change."""
    page = MockPage()
    router = AppRouter(page)

    # 1. Unauthenticated state
    router.handle_route_change(MagicMock(route="/dashboard"))
    assert SecurityContext.get_current_user_id() is None

    # 2. Authenticated state (User A)
    create_mock_session(page, 1, "admin", "ADMIN")
    router.handle_route_change(MagicMock(route="/dashboard"))
    assert SecurityContext.get_current_user_id() == 1
    assert SecurityContext.get_current_username() == "admin"

    # 3. Authenticated state (User B)
    # Simulating a different page/session
    page_b = MockPage()
    create_mock_session(page_b, 2, "staff", "STAFF")
    router_b = AppRouter(page_b)
    router_b.handle_route_change(MagicMock(route="/dashboard"))
    assert SecurityContext.get_current_user_id() == 2
    assert SecurityContext.get_current_username() == "staff"

def test_router_clears_context_on_logout():
    """Verify that SecurityContext is cleared during the logout route."""
    page = MockPage()
    create_mock_session(page, 1, "admin", "ADMIN")
    router = AppRouter(page)

    # Setup initial context
    router.handle_route_change(MagicMock(route="/dashboard"))
    assert SecurityContext.get_current_user_id() == 1

    # Trigger logout
    router.handle_route_change(MagicMock(route="/logout"))
    assert SecurityContext.get_current_user_id() is None

def test_worker_inherits_synchronized_context():
    """Verify that workers spawned during a synchronized request inherit the identity."""
    page = MockPage()
    create_mock_session(page, 1, "admin", "ADMIN")
    router = AppRouter(page)

    # Synchronize context
    router.handle_route_change(MagicMock(route="/dashboard"))

    def worker_task():
        return SecurityContext.get_current_user_id()

    wrapped = SecurityContext.wrap_worker(worker_task)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(wrapped)
        result = future.result()

    assert result == 1

def test_fail_closed_on_empty_session():
    """Verify that an empty session explicitly clears the context."""
    page = MockPage()
    router = AppRouter(page)

    # First, set a manual context to see if it's cleared
    SecurityContext.set_current_user(99, "ghost", "GHOST")

    # Trigger route change with no session
    router.handle_route_change(MagicMock(route="/dashboard"))

    assert SecurityContext.get_current_user_id() is None
