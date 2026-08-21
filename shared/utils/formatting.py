# shared/utils/formatting.py

from __future__ import annotations
import re
import urllib.parse
from typing import Optional

__all__ = [
    "format_title_case",
    "normalize_mobile",
    "format_whatsapp_number",
    "format_whatsapp_url",
    "format_currency",
    "format_file_size",
]


def format_title_case(value: Optional[str]) -> str:
    """
    Capitalizes the first letter of each word in a string, preserving commas and spacing.
    Example:
        'anuj raj pagar' -> 'Anuj Raj Pagar'
        'near jio tower, sawargaon road' -> 'Near Jio Tower, Sawargaon Road'
        'chandwad' -> 'Chandwad'
    """
    if not value:
        return ""
    
    words = value.strip().split()
    capitalized_words = []
    for word in words:
        if not word:
            continue
        capitalized_words.append(word.capitalize())
    
    return " ".join(capitalized_words)


def normalize_mobile(mobile_number: Optional[str]) -> str:
    """
    Normalizes mobile numbers into a standard 10-digit format.
    Strips spaces, hyphens, and +91/91 country prefixes.
    """
    if not mobile_number:
        return ""
    clean = re.sub(r"[\s\-\(\)\+]", "", str(mobile_number).strip())
    if clean.startswith("91") and len(clean) == 12:
        clean = clean[2:]
    return clean


normalize_indian_mobile = normalize_mobile


def format_whatsapp_number(mobile_number: Optional[str]) -> str:
    """
    Returns normalized 12-digit Indian mobile number for WhatsApp (91XXXXXXXXXX).
    """
    clean = normalize_mobile(mobile_number)
    if len(clean) == 10:
        return f"91{clean}"
    return clean


def format_whatsapp_url(mobile_number: Optional[str], message: Optional[str] = None) -> str:
    """
    Generates a wa.me URL for the mobile number and optional pre-filled message.
    """
    wa_num = format_whatsapp_number(mobile_number)
    if not wa_num:
        return "https://web.whatsapp.com"
    
    if message:
        encoded_msg = urllib.parse.quote(message)
        return f"https://wa.me/{wa_num}?text={encoded_msg}"
    return f"https://wa.me/{wa_num}"


def format_currency(amount: Optional[float | int]) -> str:
    """Formats numeric amount as Indian Rupees (e.g. ₹4,500.00)."""
    if amount is None:
        return "₹0.00"
    return f"₹{float(amount):,.2f}"


def format_file_size(size_bytes: int) -> str:
    """Formats file size into human-readable KB/MB string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
