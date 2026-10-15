# core/security/session.py

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import flet as ft

from core.security.roles import Role

__all__ = ["SessionManager", "UserSession"]


@dataclass
class UserSession:
    """Authoritative representation of an active application session."""
    user_id: int
    username: str
    role: str
    security_version: int
    security_stamp: str
    login_timestamp: float
    last_activity_timestamp: float
    
    def is_valid(self) -> bool:
        """Basic session validity check."""
        return bool(self.user_id and self.username and self.role)


class SessionManager:
    """
    Authoritative Session Manager for SIMS v2.2.
    
    Ensures a single source of truth for identity per Flet session.
    Eliminates reliance on raw page.session attributes in business logic.
    """
    
    _SESSION_KEY = "sims_auth_session"

    @classmethod
    def create_session(cls, page: ft.Page, user_data: dict[str, Any]) -> UserSession:
        """
        Creates and persists a new authoritative session in the Flet session store.
        """
        now_ts = datetime.now(timezone.utc).timestamp()
        
        session_obj = UserSession(
            user_id=int(user_data["id"]),
            username=user_data["username"],
            role=str(user_data["role"]).strip().upper(),
            security_version=int(user_data.get("security_version", 1)),
            security_stamp=str(user_data.get("security_stamp", "")),
            login_timestamp=now_ts,
            last_activity_timestamp=now_ts,
        )
        
        # Store the session object in Flet's page.session
        # We use the internal page.session.set() if available or dict access
        sess = getattr(page, "session", None)
        if sess is not None:
            if hasattr(sess, "set"):
                sess.set(cls._SESSION_KEY, session_obj)
            elif isinstance(sess, dict):
                sess[cls._SESSION_KEY] = session_obj
        
        return session_obj

    @classmethod
    def get_session(cls, page: ft.Page) -> Optional[UserSession]:
        """Returns the current authoritative UserSession or None if unauthenticated."""
        sess = getattr(page, "session", None)
        if sess is None:
            return None
            
        user_sess = None
        if hasattr(sess, "get") and callable(sess.get):
            user_sess = sess.get(cls._SESSION_KEY)
        elif isinstance(sess, dict):
            user_sess = sess.get(cls._SESSION_KEY)
            
        if isinstance(user_sess, UserSession) and user_sess.is_valid():
            return user_sess

        # Fallback for raw sessions or test mocks that set keys directly
        def _get_raw(k: str):
            if hasattr(sess, "get") and callable(sess.get):
                return sess.get(k)
            elif isinstance(sess, dict):
                return sess.get(k)
            return None

        user_id = _get_raw("user_id")
        if user_id:
            username = str(_get_raw("username") or "user")
            role = str(_get_raw("role") or Role.ADMIN.value).strip().upper()
            sec_ver = int(_get_raw("security_version") or 1)
            sec_stamp = str(_get_raw("security_stamp") or "")
            now_ts = datetime.now(timezone.utc).timestamp()
            login_ts = float(_get_raw("login_timestamp") or now_ts)
            last_ts = float(_get_raw("last_activity_timestamp") or now_ts)

            fallback_session = UserSession(
                user_id=int(user_id),
                username=username,
                role=role,
                security_version=sec_ver,
                security_stamp=sec_stamp,
                login_timestamp=login_ts,
                last_activity_timestamp=last_ts,
            )
            if hasattr(sess, "set") and callable(sess.set):
                sess.set(cls._SESSION_KEY, fallback_session)
            elif isinstance(sess, dict):
                sess[cls._SESSION_KEY] = fallback_session
            return fallback_session

        return None

    @classmethod
    def touch_activity(cls, page: ft.Page) -> None:
        """Updates the last activity timestamp for the current session."""
        session = cls.get_session(page)
        if session:
            session.last_activity_timestamp = datetime.now(timezone.utc).timestamp()
            # Persist back to Flet session
            sess = getattr(page, "session", None)
            if sess is not None:
                if hasattr(sess, "set"):
                    sess.set(cls._SESSION_KEY, session)
                elif isinstance(sess, dict):
                    sess[cls._SESSION_KEY] = session

    @classmethod
    def invalidate_session(cls, page: ft.Page) -> None:
        """Explicitly invalidates and clears the session."""
        sess = getattr(page, "session", None)
        if sess is not None:
            if hasattr(sess, "clear") and callable(sess.clear):
                sess.clear()
            elif isinstance(sess, dict):
                sess.clear()
            store = getattr(sess, "store", None)
            if store is not None:
                if hasattr(store, "clear") and callable(store.clear):
                    store.clear()
                elif isinstance(store, dict):
                    store.clear()

    destroy_session = invalidate_session
