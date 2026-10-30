"""
core/utils/image_utils.py

High-performance image validation and verification utilities.
Protects the Flet and Flutter rendering pipeline from crashing on corrupt,
truncated, or non-image files (such as test dummy text files).
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Optional, Union


def is_valid_image_bytes(data: Optional[bytes]) -> bool:
    """
    Verifies that the provided byte buffer starts with a known image signature
    and passes PIL verification if PIL is available.
    """
    if not data or len(data) < 16:
        return False

    # Magic byte checks
    is_jpeg = data.startswith(b"\xff\xd8\xff")
    is_png = data.startswith(b"\x89PNG")
    is_gif = data.startswith(b"GIF87a") or data.startswith(b"GIF89a")
    is_bmp = data.startswith(b"BM")
    is_webp = data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WEBP"

    if not (is_jpeg or is_png or is_gif or is_bmp or is_webp):
        return False

    try:
        from PIL import Image
        import io
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
        return True
    except Exception:
        return False


def is_valid_image_file(file_path: Optional[Union[str, Path]]) -> bool:
    """
    Returns True if file_path is an existing non-empty file on disk that contains
    a valid image header and passes PIL verification.
    Returns False safely without raising exceptions.
    """
    if not file_path:
        return False

    try:
        p = Path(file_path)
        if not p.is_file():
            return False

        file_size = p.stat().st_size
        if file_size < 16:
            return False

        # Read first 64 bytes for fast header inspection
        with open(p, "rb") as f:
            header = f.read(64)

        if len(header) < 16:
            return False

        is_jpeg = header.startswith(b"\xff\xd8\xff")
        is_png = header.startswith(b"\x89PNG")
        is_gif = header.startswith(b"GIF87a") or header.startswith(b"GIF89a")
        is_bmp = header.startswith(b"BM")
        is_webp = header.startswith(b"RIFF") and len(header) >= 12 and header[8:12] == b"WEBP"

        if not (is_jpeg or is_png or is_gif or is_bmp or is_webp):
            return False

        try:
            from PIL import Image
            with Image.open(p) as img:
                img.verify()
            return True
        except Exception:
            return False

    except Exception:
        return False
