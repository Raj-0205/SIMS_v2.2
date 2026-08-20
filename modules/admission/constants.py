# modules/admission/constants.py

from enum import Enum

__all__ = [
    "AdmissionStatus",
    "Qualification",
    "BloodGroup",
    "Gender",
    "ADMISSION_STATUS_COLORS",
]


class AdmissionStatus(str, Enum):
    """
    Official Business Contract for the Admission Lifecycle.
    Strictly decoupled from Student, Payment, and Batch entities.
    """
    DRAFT = "DRAFT"             # Form started or saved without minimum confirmation payment.
    REGISTERED = "REGISTERED"   # Form submitted with student & course details.
    CONFIRMED = "CONFIRMED"     # Admission finalized with minimum ₹500 payment.
    CANCELLED = "CANCELLED"     # Admission abandoned or refunded.
    COMPLETED = "COMPLETED"     # Course completed & finalized.


class Qualification(str, Enum):
    BELOW_9TH = "Below 9th"
    NINTH = "9th"
    TENTH = "10th"
    ELEVENTH = "11th"
    TWELFTH = "12th"
    UG = "UG"
    PG = "PG"
    DIPLOMA = "Diploma"
    ITI = "ITI"
    OTHER = "Other"


class BloodGroup(str, Enum):
    A_POS = "A+"
    A_NEG = "A-"
    B_POS = "B+"
    B_NEG = "B-"
    AB_POS = "AB+"
    AB_NEG = "AB-"
    O_POS = "O+"
    O_NEG = "O-"


class Gender(str, Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


ADMISSION_STATUS_COLORS: dict[str, str] = {
    AdmissionStatus.DRAFT.value: "#64748B",       # Slate Gray
    AdmissionStatus.REGISTERED.value: "#2563EB",  # Blue
    AdmissionStatus.CONFIRMED.value: "#16A34A",   # Green
    AdmissionStatus.CANCELLED.value: "#DC2626",   # Red
    AdmissionStatus.COMPLETED.value: "#7C3AED",   # Purple
}
