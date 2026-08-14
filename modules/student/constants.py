# modules/student/constants.py

from enum import Enum

__all__ = ["StudentStatus"]


class StudentStatus(str, Enum):
    """
    TODO (Owner Decision):
    Student lifecycle and statuses will be finalized during
    the Admission Module domain design.
    No temporary placeholders are allowed here to prevent accidental business logic.
    """
    pass


# TODO (Commit #TBD): Introduce AdmissionStatus Enum in the Admission Module.
# The exact states and transitions will be explicitly designed and frozen by the Product Owner.
