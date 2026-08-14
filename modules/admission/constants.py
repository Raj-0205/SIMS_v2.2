# modules/admission/constants.py

from enum import Enum

__all__ = ["AdmissionStatus"]


class AdmissionStatus(str, Enum):
    """
    Official Business Contract for the Admission Lifecycle.
    Strictly decoupled from Student, Payment, and Batch entities.
    """
    DRAFT = "DRAFT"             # Form started, auto-saving. Not yet submitted.
    REGISTERED = "REGISTERED"   # Admission form submitted successfully.
    CONFIRMED = "CONFIRMED"     # Admission finalized. Ready for Batch allocation.
    CANCELLED = "CANCELLED"     # Admission abandoned or rejected.
