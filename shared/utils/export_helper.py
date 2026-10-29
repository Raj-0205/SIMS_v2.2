# shared/utils/export_helper.py

from __future__ import annotations
import inspect
import shutil
from pathlib import Path
from typing import Any, Callable, Optional

from core.logger.service import LogService
from shared.utils.file_dialog import pick_save_file_async
from shared.utils.os_helper import open_path_externally

__all__ = ["export_and_prompt_save"]


def _safe_notify(
    notify_fn: Optional[Callable[..., Any]],
    message: str,
    is_success: bool = False,
    is_error: bool = False,
) -> None:
    """Invokes the view's notification/toast callback adapting to any parameter signature."""
    if not notify_fn or not callable(notify_fn):
        return

    try:
        sig = inspect.signature(notify_fn)
        params = list(sig.parameters.keys())
        kwargs: dict[str, Any] = {}

        if "is_success" in params:
            kwargs["is_success"] = is_success
        if "is_error" in params:
            kwargs["is_error"] = is_error

        if kwargs:
            notify_fn(message, **kwargs)
        elif len(params) >= 3:
            # Assume (message, is_error, is_success) or (message, is_success, is_error)
            notify_fn(message, is_error, is_success)
        elif len(params) == 2:
            notify_fn(message, is_error)
        else:
            notify_fn(message)
    except Exception as ex:
        try:
            notify_fn(message)
        except Exception:
            LogService.warning(f"Failed to deliver notification '{message}': {ex}", context="ExportHelper")


def export_and_prompt_save(
    source_file_path: str | Path,
    dialog_title: str = "Save Exported File As",
    default_filename: Optional[str] = None,
    allowed_extensions: Optional[list[str]] = None,
    show_toast: Optional[Callable[..., Any]] = None,
    open_folder_on_success: bool = True,
    on_complete: Optional[Callable[[Optional[Path]], None]] = None,
) -> None:
    """
    Dual-Location Export Coordinator:
    1. Guarantees the generated file remains safely stored in its canonical SIMS internal folder
       (e.g., exports/admissions/..., exports/reports/..., exports/students/...).
    2. Spawns an asynchronous native OS file manager / Save File dialog letting the user
       choose their desired custom file location on their system (Desktop, USB drive, Documents, etc.).
    3. Copies the file to the user-chosen location upon selection and opens the parent directory.
    4. If the user cancels the dialog, informs the user that the file has been preserved in SIMS records.
    """
    src_path = Path(source_file_path).resolve()
    if not src_path.exists() or not src_path.is_file():
        LogService.error(f"Cannot save export: source file '{src_path}' does not exist on disk", context="ExportHelper")
        _safe_notify(show_toast, f"Export failed: file not found on disk ({src_path.name})", is_error=True)
        if on_complete:
            try:
                on_complete(None)
            except Exception:
                pass
        return

    fname = default_filename or src_path.name
    ext = src_path.suffix.lower()
    exts = allowed_extensions or ([ext] if ext else None)

    def _on_save_chosen(chosen_dest: Optional[Path]) -> None:
        if chosen_dest:
            try:
                target = Path(chosen_dest).resolve()
                if target.is_dir():
                    target = target / fname
                elif not target.suffix and ext:
                    target = target.with_suffix(ext)

                target.parent.mkdir(parents=True, exist_ok=True)

                if target != src_path:
                    shutil.copy2(src_path, target)

                LogService.info(
                    f"Export successfully saved to custom location '{target}' (archived in SIMS at '{src_path}')",
                    context="ExportHelper",
                )
                _safe_notify(
                    show_toast,
                    f"✓ Export saved to: {target.name} (Also archived in SIMS records)",
                    is_success=True,
                    is_error=False,
                )
                if open_folder_on_success:
                    open_path_externally(target.parent)

                if on_complete:
                    try:
                        on_complete(target)
                    except Exception as ex:
                        LogService.warning(f"on_complete callback error: {ex}", context="ExportHelper")
            except Exception as ex:
                LogService.error(
                    f"Failed to copy export to custom location '{chosen_dest}': {ex}",
                    context="ExportHelper",
                )
                _safe_notify(
                    show_toast,
                    f"Saved in SIMS records ({src_path.name}), but custom location copy failed: {ex}",
                    is_error=True,
                )
                if on_complete:
                    try:
                        on_complete(None)
                    except Exception:
                        pass
        else:
            # User dismissed or cancelled the dialog
            LogService.info(
                f"User dismissed custom location dialog. Export preserved in SIMS records at '{src_path}'",
                context="ExportHelper",
            )
            _safe_notify(
                show_toast,
                f"Export preserved in SIMS records: {src_path.name}",
                is_success=True,
                is_error=False,
            )
            if on_complete:
                try:
                    on_complete(None)
                except Exception:
                    pass

    pick_save_file_async(
        title=dialog_title,
        default_filename=fname,
        allowed_extensions=exts,
        fallback_to_downloads=False,
        on_result=_on_save_chosen,
    )
