"""
core/utils/url_utils.py

Enterprise URL launching utilities for SIMS v2.2.
Safely opens external web URLs in the operating system's default browser
and safely handles Flet asynchronous Page.launch_url signatures without
triggering unawaited coroutine RuntimeWarnings.
"""
from __future__ import annotations
import inspect
import os
import shutil
import subprocess
import sys
import webbrowser
from typing import Any, Optional

__all__ = ["safe_open_url"]


import contextlib

@contextlib.contextmanager
def _silence_fd():
    """
    Suppresses OS-level stdout and stderr file descriptors to prevent
    spurious Linux zygote/browser IPC broken-pipe error noise in console.
    """
    devnull_fd = None
    saved_stdout = None
    saved_stderr = None
    try:
        devnull_fd = os.open(os.devnull, os.O_WRONLY)
        try:
            saved_stdout = os.dup(1)
            os.dup2(devnull_fd, 1)
        except Exception:
            pass
        try:
            saved_stderr = os.dup(2)
            os.dup2(devnull_fd, 2)
        except Exception:
            pass
        yield
    except Exception:
        yield
    finally:
        try:
            if saved_stdout is not None:
                os.dup2(saved_stdout, 1)
                os.close(saved_stdout)
        except Exception:
            pass
        try:
            if saved_stderr is not None:
                os.dup2(saved_stderr, 2)
                os.close(saved_stderr)
        except Exception:
            pass
        if devnull_fd is not None:
            try:
                os.close(devnull_fd)
            except Exception:
                pass


def safe_open_url(url: str, page: Optional[Any] = None) -> bool:
    """
    Safely opens a web URL in the system browser and notifies the Flet page/test mock.

    1. Launches in system default browser via webbrowser.open with suppressed zygote stderr.
    2. Notifies the page if page.launch_url exists.
    3. If page.launch_url returned a coroutine (Flet 0.85+ async launch_url on sync thread),
       closes the coroutine immediately to eliminate RuntimeWarning.
    """
    if not url or not str(url).strip():
        return False

    clean_url = str(url).strip()
    opened = False

    try:
        with _silence_fd():
            opened = webbrowser.open(clean_url)
    except Exception:
        try:
            if sys.platform.startswith("linux") and shutil.which("xdg-open"):
                subprocess.Popen(
                    ["xdg-open", clean_url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                opened = True
        except Exception:
            opened = False

    if page and hasattr(page, "launch_url") and callable(page.launch_url):
        try:
            res = page.launch_url(clean_url)
            if inspect.iscoroutine(res):
                res.close()
        except Exception:
            pass

    return opened
