# shared/utils/file_dialog.py

from __future__ import annotations
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Optional
from core.logger.service import LogService


def pick_file(title: str = "Select File", allowed_extensions: Optional[list[str]] = None) -> Optional[Path]:
    """
    Cross-platform desktop file selection dialog.
    Supports Linux (zenity/kdialog), Windows (PowerShell System.Windows.Forms), and macOS (osascript).
    Returns Path of selected file or None if cancelled.
    """
    sys_name = platform.system()

    if sys_name == "Linux":
        if shutil.which("zenity"):
            filter_arg = ""
            if allowed_extensions:
                ext_patterns = " ".join([f"*.{ext.lstrip('.')} *.{ext.lstrip('.').upper()}" for ext in allowed_extensions])
                filter_arg = f"--file-filter=Allowed Files ({ext_patterns}) | {ext_patterns}"
            cmd = ["zenity", "--file-selection", f"--title={title}"]
            if filter_arg:
                cmd.append(filter_arg)
            try:
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                selected = res.stdout.strip()
                if selected and Path(selected).is_file():
                    return Path(selected)
            except Exception as ex:
                LogService.warning(f"Zenity file picker failed: {ex}", context="FileDialog")
        elif shutil.which("kdialog"):
            cmd = ["kdialog", "--getopenfilename", ".", f"--title={title}"]
            try:
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                selected = res.stdout.strip()
                if selected and Path(selected).is_file():
                    return Path(selected)
            except Exception as ex:
                LogService.warning(f"Kdialog file picker failed: {ex}", context="FileDialog")

    elif sys_name == "Windows":
        filter_str = "All Files (*.*)|*.*"
        if allowed_extensions:
            ext_patterns = ";".join([f"*.{ext.lstrip('.')}" for ext in allowed_extensions])
            filter_str = f"Allowed Files ({ext_patterns})|{ext_patterns}|All Files (*.*)|*.*"
        ps_script = f"""
        Add-Type -AssemblyName System.Windows.Forms
         = New-Object System.Windows.Forms.OpenFileDialog
        .Title = '{title}'
        .Filter = '{filter_str}'
        if (.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{{{
            Write-Output .FileName
        }}}}
        """
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            selected = res.stdout.strip()
            if selected and Path(selected).is_file():
                return Path(selected)
        except Exception as ex:
            LogService.warning(f"Windows PowerShell file dialog failed: {ex}", context="FileDialog")

    elif sys_name == "Darwin":
        osa_script = f'POSIX path of (choose file with prompt "{title}")'
        try:
            res = subprocess.run(
                ["osascript", "-e", osa_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            selected = res.stdout.strip()
            if selected and Path(selected).is_file():
                return Path(selected)
        except Exception as ex:
            LogService.warning(f"macOS osascript file dialog failed: {ex}", context="FileDialog")

    return None
