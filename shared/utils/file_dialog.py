# shared/utils/file_dialog.py

from __future__ import annotations
import os
import platform
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Callable, Optional
from core.logger.service import LogService

__all__ = [
    "pick_file",
    "pick_save_file",
    "pick_file_async",
    "pick_save_file_async",
    "cancel_active_picker",
]

_active_picker_proc: Optional[subprocess.Popen] = None
_picker_lock = threading.Lock()


def cancel_active_picker() -> None:
    """Terminates any active OS file picker subprocess immediately to prevent background hang."""
    global _active_picker_proc
    with _picker_lock:
        if _active_picker_proc is not None:
            try:
                _active_picker_proc.terminate()
            except Exception:
                pass
            _active_picker_proc = None


def pick_file(title: str = "Select File", allowed_extensions: Optional[list[str]] = None) -> Optional[Path]:
    """
    Cross-platform desktop file selection dialog.
    Supports Linux (zenity --modal/kdialog), Windows (PowerShell System.Windows.Forms), and macOS (osascript).
    Returns Path of selected file or None if cancelled.
    """
    global _active_picker_proc
    sys_name = platform.system()

    if sys_name == "Linux":
        if shutil.which("zenity"):
            filter_arg = ""
            if allowed_extensions:
                ext_patterns = " ".join([f"*.{ext.lstrip('.')} *.{ext.lstrip('.').upper()}" for ext in allowed_extensions])
                filter_arg = f"--file-filter=Allowed Files ({ext_patterns}) | {ext_patterns}"
            cmd = ["zenity", "--file-selection", "--modal", f"--title={title}"]
            if filter_arg:
                cmd.append(filter_arg)
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                with _picker_lock:
                    _active_picker_proc = proc
                stdout, _ = proc.communicate()
                with _picker_lock:
                    _active_picker_proc = None

                selected = (stdout or "").strip()
                if selected and Path(selected).is_file():
                    return Path(selected)
            except Exception as ex:
                LogService.warning(f"Zenity file picker failed: {ex}", context="FileDialog")
            finally:
                with _picker_lock:
                    _active_picker_proc = None
        elif shutil.which("kdialog"):
            cmd = ["kdialog", "--getopenfilename", ".", f"--title={title}"]
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                with _picker_lock:
                    _active_picker_proc = proc
                stdout, _ = proc.communicate()
                with _picker_lock:
                    _active_picker_proc = None

                selected = (stdout or "").strip()
                if selected and Path(selected).is_file():
                    return Path(selected)
            except Exception as ex:
                LogService.warning(f"Kdialog file picker failed: {ex}", context="FileDialog")
            finally:
                with _picker_lock:
                    _active_picker_proc = None

    elif sys_name == "Windows":
        filter_str = "All Files (*.*)|*.*"
        if allowed_extensions:
            ext_patterns = ";".join([f"*.{ext.lstrip('.')}" for ext in allowed_extensions])
            filter_str = f"Allowed Files ({ext_patterns})|{ext_patterns}|All Files (*.*)|*.*"
        ps_script = f"""
        Add-Type -AssemblyName System.Windows.Forms
        $dlg = New-Object System.Windows.Forms.OpenFileDialog
        $dlg.Title = '{title}'
        $dlg.Filter = '{filter_str}'
        if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{
            Write-Output $dlg.FileName
        }}
        """
        try:
            proc = subprocess.Popen(
                ["powershell", "-NoProfile", "-Command", ps_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            with _picker_lock:
                _active_picker_proc = proc
            stdout, _ = proc.communicate()
            with _picker_lock:
                _active_picker_proc = None

            selected = (stdout or "").strip()
            if selected and Path(selected).is_file():
                return Path(selected)
        except Exception as ex:
            LogService.warning(f"Windows PowerShell file dialog failed: {ex}", context="FileDialog")
        finally:
            with _picker_lock:
                _active_picker_proc = None

    elif sys_name == "Darwin":
        osa_script = f'POSIX path of (choose file with prompt "{title}")'
        try:
            proc = subprocess.Popen(
                ["osascript", "-e", osa_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            with _picker_lock:
                _active_picker_proc = proc
            stdout, _ = proc.communicate()
            with _picker_lock:
                _active_picker_proc = None

            selected = (stdout or "").strip()
            if selected and Path(selected).is_file():
                return Path(selected)
        except Exception as ex:
            LogService.warning(f"macOS osascript file dialog failed: {ex}", context="FileDialog")
        finally:
            with _picker_lock:
                _active_picker_proc = None

    return None


def pick_save_file(
    title: str = "Save File As",
    default_filename: str = "document.jpg",
    allowed_extensions: Optional[list[str]] = None,
    fallback_to_downloads: bool = False,
) -> Optional[Path]:
    """
    Cross-platform desktop save file dialog.
    Supports Linux (zenity --modal/kdialog), Windows (PowerShell System.Windows.Forms), and macOS (osascript).
    Returns Path of chosen save destination or None if cancelled.
    """
    global _active_picker_proc
    sys_name = platform.system()
    default_dir = Path.home() / "Downloads"
    if not default_dir.exists():
        default_dir = Path.home()
    initial_path = default_dir / default_filename

    if sys_name == "Linux":
        if shutil.which("zenity"):
            filter_arg = ""
            if allowed_extensions:
                ext_patterns = " ".join([f"*.{ext.lstrip('.')} *.{ext.lstrip('.').upper()}" for ext in allowed_extensions])
                filter_arg = f"--file-filter=Allowed Files ({ext_patterns}) | {ext_patterns}"
            cmd = [
                "zenity",
                "--file-selection",
                "--save",
                "--modal",
                "--confirm-overwrite",
                f"--title={title}",
                f"--filename={str(initial_path)}",
            ]
            if filter_arg:
                cmd.append(filter_arg)
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                with _picker_lock:
                    _active_picker_proc = proc
                stdout, _ = proc.communicate()
                with _picker_lock:
                    _active_picker_proc = None

                if proc.returncode != 0:
                    return None
                selected = (stdout or "").strip()
                if selected:
                    p = Path(selected)
                    if allowed_extensions and not p.suffix:
                        first_ext = allowed_extensions[0]
                        p = p.with_suffix(first_ext if first_ext.startswith(".") else f".{first_ext}")
                    return p
            except Exception as ex:
                LogService.warning(f"Zenity save file picker failed: {ex}", context="FileDialog")
            finally:
                with _picker_lock:
                    _active_picker_proc = None
        elif shutil.which("kdialog"):
            filter_pattern = "*"
            if allowed_extensions:
                filter_pattern = " ".join([f"*.{ext.lstrip('.')}" for ext in allowed_extensions])
            cmd = ["kdialog", "--getsavefilename", str(initial_path), filter_pattern, f"--title={title}"]
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                with _picker_lock:
                    _active_picker_proc = proc
                stdout, _ = proc.communicate()
                with _picker_lock:
                    _active_picker_proc = None

                if proc.returncode != 0:
                    return None
                selected = (stdout or "").strip()
                if selected:
                    return Path(selected)
            except Exception as ex:
                LogService.warning(f"Kdialog save file picker failed: {ex}", context="FileDialog")
            finally:
                with _picker_lock:
                    _active_picker_proc = None

    elif sys_name == "Windows":
        filter_str = "All Files (*.*)|*.*"
        if allowed_extensions:
            ext_patterns = ";".join([f"*.{ext.lstrip('.')}" for ext in allowed_extensions])
            filter_str = f"Allowed Files ({ext_patterns})|{ext_patterns}|All Files (*.*)|*.*"
        ps_script = f"""
        Add-Type -AssemblyName System.Windows.Forms
        $dlg = New-Object System.Windows.Forms.SaveFileDialog
        $dlg.Title = '{title}'
        $dlg.FileName = '{default_filename}'
        $dlg.InitialDirectory = '{str(default_dir)}'
        $dlg.Filter = '{filter_str}'
        $dlg.OverwritePrompt = $true
        if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{
            Write-Output $dlg.FileName
        }}
        """
        try:
            proc = subprocess.Popen(
                ["powershell", "-NoProfile", "-Command", ps_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            with _picker_lock:
                _active_picker_proc = proc
            stdout, _ = proc.communicate()
            with _picker_lock:
                _active_picker_proc = None

            selected = (stdout or "").strip()
            if selected:
                return Path(selected)
        except Exception as ex:
            LogService.warning(f"Windows PowerShell save file dialog failed: {ex}", context="FileDialog")
        finally:
            with _picker_lock:
                _active_picker_proc = None

    elif sys_name == "Darwin":
        osa_script = f'POSIX path of (choose file name with prompt "{title}" default name "{default_filename}" default location (path to downloads folder))'
        try:
            proc = subprocess.Popen(
                ["osascript", "-e", osa_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            with _picker_lock:
                _active_picker_proc = proc
            stdout, _ = proc.communicate()
            with _picker_lock:
                _active_picker_proc = None

            selected = (stdout or "").strip()
            if selected:
                return Path(selected)
        except Exception as ex:
            LogService.warning(f"macOS osascript save file dialog failed: {ex}", context="FileDialog")
        finally:
            with _picker_lock:
                _active_picker_proc = None

    if fallback_to_downloads:
        return initial_path

    return None


def pick_file_async(
    title: str = "Select File",
    allowed_extensions: Optional[list[str]] = None,
    on_result: Optional[Callable[[Optional[Path]], None]] = None,
) -> threading.Thread:
    """
    Non-blocking desktop file selection dialog executed in a daemon worker thread.
    Prevents UI freezing and delivers selected path to on_result callback.
    """
    def _worker():
        res = pick_file(title=title, allowed_extensions=allowed_extensions)
        if on_result:
            try:
                on_result(res)
            except Exception as ex:
                LogService.warning(f"pick_file_async callback failed: {ex}", context="FileDialog")

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return t


def pick_save_file_async(
    title: str = "Save File As",
    default_filename: str = "document.jpg",
    allowed_extensions: Optional[list[str]] = None,
    fallback_to_downloads: bool = False,
    on_result: Optional[Callable[[Optional[Path]], None]] = None,
) -> threading.Thread:
    """Non-blocking desktop save file dialog executed in a daemon worker thread."""
    def _worker():
        res = pick_save_file(
            title=title,
            default_filename=default_filename,
            allowed_extensions=allowed_extensions,
            fallback_to_downloads=fallback_to_downloads,
        )
        if on_result:
            try:
                on_result(res)
            except Exception as ex:
                LogService.warning(f"pick_save_file_async callback failed: {ex}", context="FileDialog")

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return t


