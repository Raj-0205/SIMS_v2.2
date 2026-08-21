# shared/utils/formatters.py

from __future__ import annotations
import re
from typing import Optional

__all__ = ["format_title_case", "normalize_indian_mobile"]

def format_title_case(value: Optional[str]) -> str:
    """
    Capitalizes the first letter of each word in human name/place text.
    Examples:
        'anuj raj pagar' -> 'Anuj Raj Pagar'
        'chandwad' -> 'Chandwad'
        'near jio tower, sawargaon road' -> 'Near Jio Tower, Sawargaon Road'
    Does NOT affect emails, phone numbers, codes, or URLs.
    """
    if not value or not isinstance(value, str):
        return ""
    clean = " ".join(value.strip().split())
    if not clean:
        return ""
    
    # Capitalize words separated by spaces or hyphens, preserving punctuation
    def cap_match(match: re.Match) -> str:
        word = match.group(0)
        return word.capitalize()

    return re.sub(r"[a-zA-Z0-9]+", cap_match, clean)


def normalize_indian_mobile(mobile: Optional[str]) -> str:
    """
    Normalizes mobile numbers into 10-digit clean string or 91XXXXXXXXXX for WhatsApp.
    """
    if not mobile:
        return ""
    digits = re.sub(r"\D", "", str(mobile))
    if len(digits) == 12 and digits.startswith("91"):
        return digits[2:]
    if len(digits) == 10:
        return digits
    return digits
