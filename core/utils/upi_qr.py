# core/utils/upi_qr.py

from __future__ import annotations
import io
import base64
import urllib.parse
from typing import Optional, Tuple
import qrcode
from qrcode.constants import ERROR_CORRECT_M

__all__ = ["generate_upi_qr_base64", "build_upi_deep_link"]


def build_upi_deep_link(
    upi_id: str,
    payee_name: str,
    amount: float,
    transaction_note: Optional[str] = None,
    currency: str = "INR",
) -> str:
    """
    Constructs an NPCI-compliant UPI deep link URL.
    Format: upi://pay?pa=<UPI_ID>&pn=<NAME>&am=<AMOUNT>&cu=<CURRENCY>&tn=<NOTE>
    """
    clean_upi = upi_id.strip()
    clean_name = payee_name.strip()
    amount_str = f"{max(0.0, float(amount)):.2f}"

    parts = [
        f"pa={urllib.parse.quote(clean_upi, safe='@')}",
        f"pn={urllib.parse.quote(clean_name)}",
        f"am={amount_str}",
        f"cu={currency.upper()}",
    ]
    if transaction_note and transaction_note.strip():
        parts.append(f"tn={urllib.parse.quote(transaction_note.strip())}")

    return f"upi://pay?{'&'.join(parts)}"


def generate_upi_qr_base64(
    upi_id: str,
    payee_name: str,
    amount: float,
    transaction_note: Optional[str] = None,
    currency: str = "INR",
    box_size: int = 6,
    border: int = 2,
) -> Tuple[str, str]:
    """
    Generates a high-contrast UPI QR code encoded in Base64 (PNG format).
    Returns a tuple of (base64_string, deep_link_url).
    """
    deep_link = build_upi_deep_link(
        upi_id=upi_id,
        payee_name=payee_name,
        amount=amount,
        transaction_note=transaction_note,
        currency=currency,
    )

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(deep_link)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    b64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return b64_str, deep_link
