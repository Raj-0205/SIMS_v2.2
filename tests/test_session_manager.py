import pytest
import flet as ft
from core.security.session import SessionManager, UserSession
from core.security.roles import Role

class MockPage:
    def __init__(self):
        self.session = {}

def test_session_lifecycle():
    page = MockPage()
    user_data = {
        "id": 1,
        "username": "admin",
        "role": Role.ADMIN.value,
        "security_version": 1,
        "security_stamp": "stamp123"
    }
    
    # Test Creation
    session = SessionManager.create_session(page, user_data)
    assert isinstance(session, UserSession)
    assert session.username == "admin"
    assert session.role == "ADMIN"
    
    # Test Retrieval
    retrieved = SessionManager.get_session(page)
    assert retrieved == session
    
    # Test Invalidation
    SessionManager.invalidate_session(page)
    assert SessionManager.get_session(page) is None

def test_session_role_normalization():
    page = MockPage()
    user_data = {
        "id": 2,
        "username": "superuser",
        "role": " administrator ",
        "security_version": 1,
        "security_stamp": "stamp456"
    }
    
    session = SessionManager.create_session(page, user_data)
    assert session.role == "ADMINISTRATOR"

def test_session_isolation():
    page1 = MockPage()
    page2 = MockPage()
    
    user1 = {"id": 1, "username": "u1", "role": "ADMIN", "security_version": 1, "security_stamp": "s1"}
    user2 = {"id": 2, "username": "u2", "role": "ADMINISTRATOR", "security_version": 1, "security_stamp": "s2"}
    
    SessionManager.create_session(page1, user1)
    SessionManager.create_session(page2, user2)
    
    assert SessionManager.get_session(page1).username == "u1"
    assert SessionManager.get_session(page2).username == "u2"
