# shared/utils/os_helper.py

from __future__ import annotations
import os
import platform
import subprocess
from pathlib import Path
from core.logger.service import LogService


def open_path_externally(target_path: str | Path) -> None:
    """
    Cross-platform file/directory opening utility.
    Uses 'open' on macOS, 'os.startfile' on Windows, and 'xdg-open' on Linux.
    """
    target_str = str(target_path)
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(target_str)
        elif system == "Darwin":
            subprocess.Popen(["open", target_str])
        else:
            subprocess.Popen(["xdg-open", target_str])
    except Exception as ex:
        LogService.warning(f"Failed to open path externally '{target_str}': {ex}", context="OSHelper")
