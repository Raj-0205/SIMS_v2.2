# core/security/context.py

from __future__ import annotations
import threading
from contextlib import contextmanager
from typing import Optional, Iterator

__all__ = ["SecurityContext"]


class SecurityContext:
    """Thread-local security context for the currently executing actor."""

    _state = threading.local()

    @classmethod
    def _get_state(cls) -> threading.local:
        if not hasattr(cls._state, "user_id"):
            cls._state.user_id = None
            cls._state.username = None
            cls._state.role = None
            cls._state.security_version = None
            cls._state.security_stamp = None
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

    @classmethod
    def get_current_user_id(cls) -> Optional[int]:
        return getattr(cls._get_state(), "user_id", None)

    @classmethod
    def get_current_username(cls) -> Optional[str]:
        return getattr(cls._get_state(), "username", None)

    @classmethod
    def get_current_role(cls) -> Optional[str]:
        return getattr(cls._get_state(), "role", None)

    @classmethod
    def get_current_security_version(cls) -> Optional[int]:
        return getattr(cls._get_state(), "security_version", None)

    @classmethod
    def get_current_security_stamp(cls) -> Optional[str]:
        return getattr(cls._get_state(), "security_stamp", None)

    @classmethod
    def current_user(cls) -> Any:
        state = cls._get_state()
        uid = getattr(state, "user_id", None)
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
            getattr(state, "username", None),
            getattr(state, "role", None),
            getattr(state, "security_version", None),
            getattr(state, "security_stamp", None),
        )

    @classmethod
    def clear(cls) -> None:
        state = cls._get_state()
        state.user_id = None
        state.username = None
        state.role = None
        state.security_version = None
        state.security_stamp = None

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
