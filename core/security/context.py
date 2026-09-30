# core/security/context.py

from __future__ import annotations
import threading
from contextlib import contextmanager
from typing import Optional, Iterator

__all__ = ["SecurityContext"]


class SecurityContext:
    """Thread-local security context with session-level fallback for Flet worker threads."""

    _state = threading.local()
    _fallback_user_id: Optional[int] = None
    _fallback_username: Optional[str] = None
    _fallback_role: Optional[str] = None
    _fallback_security_version: Optional[int] = None
    _fallback_security_stamp: Optional[str] = None

    @classmethod
    def _get_state(cls) -> threading.local:
        if not hasattr(cls._state, "user_id"):
            cls._state.user_id = None
            cls._state.username = None
            cls._state.role = None
            cls._state.security_version = None
            cls._state.security_stamp = None
            cls._state.is_set = False
        return cls._state

    @classmethod
    def set_current_user(
        cls,
        user_id: Optional[int],
        username: Optional[str],
        role: Optional[str],
        security_version: Optional[int] = None,
        security_stamp: Optional[str] = None,
    ) -> None:
        state = cls._get_state()
        state.user_id = user_id
        state.username = username
        state.role = role
        state.security_version = security_version
        state.security_stamp = security_stamp
        state.is_set = True

        cls._fallback_user_id = user_id
        cls._fallback_username = username
        cls._fallback_role = role
        cls._fallback_security_version = security_version
        cls._fallback_security_stamp = security_stamp

    @classmethod
    def get_current_user_id(cls) -> Optional[int]:
        state = cls._get_state()
        if getattr(state, "is_set", False):
            return state.user_id
        return cls._fallback_user_id

    @classmethod
    def get_current_username(cls) -> Optional[str]:
        state = cls._get_state()
        if getattr(state, "is_set", False):
            return state.username
        return cls._fallback_username

    @classmethod
    def get_current_role(cls) -> Optional[str]:
        state = cls._get_state()
        if getattr(state, "is_set", False):
            return state.role
        return cls._fallback_role

    @classmethod
    def get_current_security_version(cls) -> Optional[int]:
        state = cls._get_state()
        if getattr(state, "is_set", False):
            return state.security_version
        return cls._fallback_security_version

    @classmethod
    def get_current_security_stamp(cls) -> Optional[str]:
        state = cls._get_state()
        if getattr(state, "is_set", False):
            return state.security_stamp
        return cls._fallback_security_stamp

    @classmethod
    def current_user(cls) -> Any:
        uid = cls.get_current_user_id()
        if not uid:
            return None

        class _CurrentUser:
            def __init__(self, uid: int, username: Optional[str], role: Optional[str], version: Optional[int], stamp: Optional[str]):
                self.id = uid
                self.username = username
                self.role = role
                self.security_version = version
                self.security_stamp = stamp

            def __getitem__(self, key: str) -> Any:
                return getattr(self, key)

            def get(self, key: str, default: Any = None) -> Any:
                return getattr(self, key, default)

        return _CurrentUser(
            uid,
            cls.get_current_username(),
            cls.get_current_role(),
            cls.get_current_security_version(),
            cls.get_current_security_stamp(),
        )

    @classmethod
    def clear(cls) -> None:
        state = cls._get_state()
        state.user_id = None
        state.username = None
        state.role = None
        state.security_version = None
        state.security_stamp = None
        state.is_set = True

        cls._fallback_user_id = None
        cls._fallback_username = None
        cls._fallback_role = None
        cls._fallback_security_version = None
        cls._fallback_security_stamp = None

    @classmethod
    @contextmanager
    def as_user(
        cls,
        user_id: Optional[int],
        username: Optional[str],
        role: Optional[str],
        security_version: Optional[int] = None,
        security_stamp: Optional[str] = None,
    ) -> Iterator[None]:
        """Context manager to execute a code block under an explicit actor identity."""
        prev_uid = cls.get_current_user_id()
        prev_uname = cls.get_current_username()
        prev_role = cls.get_current_role()
        prev_ver = cls.get_current_security_version()
        prev_stamp = cls.get_current_security_stamp()

        cls.set_current_user(user_id, username, role, security_version, security_stamp)
        try:
            yield
        finally:
            cls.set_current_user(prev_uid, prev_uname, prev_role, prev_ver, prev_stamp)
