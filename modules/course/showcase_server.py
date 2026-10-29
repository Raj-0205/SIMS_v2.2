# modules/course/showcase_server.py

from __future__ import annotations
import atexit
import http.server
import os
import socket
import socketserver
import sys
import threading
from typing import Optional

from core.logger.service import LogService

DEFAULT_PORT = 8080
MAX_PORT_SEARCH = 20
SHOWCASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../course_showcase")
)

_server_instance: Optional[socketserver.TCPServer] = None
_server_thread: Optional[threading.Thread] = None
_server_port: Optional[int] = None
_lock = threading.Lock()


class _QuietHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """Clean HTTP request handler that serves files from course_showcase."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SHOWCASE_DIR, **kwargs)

    def log_message(self, format: str, *args) -> None:
        # Keep terminal clean; optionally log to LogService if debug enabled
        pass


def _is_port_in_use(port: int) -> bool:
    """Checks whether a local port is already bound."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def start_showcase_server(initial_port: int = DEFAULT_PORT) -> str:
    """
    Starts the SIMS Course Showcase web server in a background daemon thread.
    Returns the full local URL (e.g. 'http://localhost:8080/index.html').
    Idempotent: if already running, returns the existing active URL.
    """
    global _server_instance, _server_thread, _server_port

    with _lock:
        if _server_instance is not None and _server_port is not None:
            return f"http://localhost:{_server_port}/index.html"

        target_port = initial_port
        for p in range(initial_port, initial_port + MAX_PORT_SEARCH):
            try:
                # Allow address reuse to avoid TIME_WAIT socket locks
                class ReusableTCPServer(socketserver.TCPServer):
                    allow_reuse_address = True

                httpd = ReusableTCPServer(("127.0.0.1", p), _QuietHTTPHandler)
                _server_instance = httpd
                _server_port = p

                thread = threading.Thread(
                    target=httpd.serve_forever,
                    name=f"SIMS-ShowcaseServer-{p}",
                    daemon=True,
                )
                _server_thread = thread
                thread.start()

                url = f"http://localhost:{p}/index.html"
                LogService.info(f"Showcase Web Server active at {url}", context="ShowcaseServer")
                return url
            except OSError:
                continue

        # Fallback to direct file path if all network ports are blocked
        fallback_file = f"file://{os.path.join(SHOWCASE_DIR, 'index.html')}"
        LogService.warn("Could not bind port for showcase server, falling back to local file URI", context="ShowcaseServer")
        return fallback_file


def stop_showcase_server() -> None:
    """
    Gracefully shuts down the showcase web server and releases socket resources.
    Idempotent: safe to call repeatedly.
    """
    global _server_instance, _server_thread, _server_port
    with _lock:
        if _server_instance is not None:
            try:
                _server_instance.shutdown()
                try:
                    _server_instance.server_close()
                except Exception:
                    pass
                if not getattr(sys, "is_finalizing", lambda: False)():
                    try:
                        LogService.info(f"Showcase Web Server on port {_server_port} shut down.", context="ShowcaseServer")
                    except Exception:
                        pass
            except Exception as exc:
                if not getattr(sys, "is_finalizing", lambda: False)():
                    try:
                        LogService.warn(f"Error shutting down showcase server: {exc}", context="ShowcaseServer")
                    except Exception:
                        pass
            finally:
                _server_instance = None
                _server_thread = None
                _server_port = None


def get_showcase_url() -> str:
    """Returns the current active showcase URL or starts the server if not already running."""
    if _server_instance is not None and _server_port is not None:
        return f"http://localhost:{_server_port}/index.html"
    return start_showcase_server()


def is_showcase_server_running() -> bool:
    """Returns True if the showcase server instance is actively running."""
    return _server_instance is not None and _server_port is not None


# Ensure clean shutdown upon application termination
atexit.register(stop_showcase_server)
