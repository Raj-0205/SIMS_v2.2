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
        return cls._state

    @classmethod
    def set_current_user(
        cls,
        user_id: Optional[int],
        username: Optional[str],
        role: Optional[str],
    ) -> None:
        state = cls._get_state()
        state.user_id = user_id
        state.username = username
        state.role = role

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
    def clear(cls) -> None:
        state = cls._get_state()
        state.user_id = None
        state.username = None
        state.role = None

    @classmethod
    @contextmanager
    def as_user(
        cls,
        user_id: Optional[int],
        username: Optional[str],
        role: Optional[str],
    ) -> Iterator[None]:
        """Context manager to execute a code block under an explicit actor identity."""
        prev_uid = cls.get_current_user_id()
        prev_uname = cls.get_current_username()
        prev_role = cls.get_current_role()

        cls.set_current_user(user_id, username, role)
        try:
            yield
        finally:
            cls.set_current_user(prev_uid, prev_uname, prev_role)
