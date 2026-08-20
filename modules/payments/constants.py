# modules/payments/constants.py

from enum import Enum

__all__ = ["PaymentMode"]


class PaymentMode(str, Enum):
    CASH = "CASH"
    UPI = "UPI"
    CARD = "CARD"
    NET_BANKING = "NET_BANKING"
    CHEQUE = "CHEQUE"
