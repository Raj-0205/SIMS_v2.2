# core/security/context.py

from __future__ import annotations
import threading
from contextlib import contextmanager
from typing import Optional, Iterator, Any, Callable

__all__ = ["SecurityContext", "UserIdentity"]


class UserIdentity:
    """Immutable user identity representation."""

    def __init__(
        self,
        user_id: int,
        username: str,
        role: str,
        security_version: Optional[int] = None,
        security_stamp: Optional[str] = None,
    ):
        self._id = user_id
        self._user_id = user_id
        self._username = username
        self._role = role
        self._security_version = security_version
        self._security_stamp = security_stamp

    @property
    def id(self) -> int:
        return self._id

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @property
    def role(self) -> str:
        return self._role

    @property
    def security_version(self) -> Optional[int]:
        return self._security_version

    @property
    def security_stamp(self) -> Optional[str]:
        return self._security_stamp

    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __repr__(self) -> str:
        return f"<UserIdentity id={self.user_id} username='{self.username}' role='{self.role}'>"


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
    def set_identity(cls, identity: UserIdentity) -> None:
        """Sets the security context from an existing UserIdentity instance."""
        cls.set_current_user(
            user_id=identity.user_id,
            username=identity.username,
            role=identity.role,
            security_version=identity.security_version,
            security_stamp=identity.security_stamp,
        )

    @classmethod
    def current_user(cls) -> Optional[UserIdentity]:
        uid = cls.get_current_user_id()
        if not uid:
            return None

        return UserIdentity(
            user_id=uid,
            username=cls.get_current_username() or "",
            role=cls.get_current_role() or "",
            security_version=cls.get_current_security_version(),
            security_stamp=cls.get_current_security_stamp(),
        )

    @classmethod
    def get_current_user(cls) -> Optional[UserIdentity]:
        """Convenience alias for current_user()."""
        return cls.current_user()

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

    @classmethod
    def capture_context(cls) -> dict[str, Any]:
        """Captures the current security identity into a transportable dictionary."""
        return {
            "user_id": cls.get_current_user_id(),
            "username": cls.get_current_username(),
            "role": cls.get_current_role(),
            "security_version": cls.get_current_security_version(),
            "security_stamp": cls.get_current_security_stamp(),
        }

    @classmethod
    def run_in_context(cls, context_dict: dict[str, Any], fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Executes a callable inside the given captured context."""
        with cls.as_user(
            user_id=context_dict.get("user_id"),
            username=context_dict.get("username"),
            role=context_dict.get("role"),
            security_version=context_dict.get("security_version"),
            security_stamp=context_dict.get("security_stamp"),
        ):
            return fn(*args, **kwargs)

    @classmethod
    def wrap_worker(cls, fn: Callable[..., Any]) -> Callable[..., Any]:
        """Wraps a worker function so it inherits the security context across threads."""
        ctx = cls.capture_context()

        def _wrapped(*args: Any, **kwargs: Any) -> Any:
            return cls.run_in_context(ctx, fn, *args, **kwargs)

        return _wrapped
