# modules/attendance/constants.py

from enum import Enum


class AttendanceMode(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"


class AttendanceStatus(str, Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"


class MarkingMethod(str, Enum):
    TOGGLE = "TOGGLE"
    OCR_SCAN = "OCR_SCAN"
    MANUAL_EDIT = "MANUAL_EDIT"


class AttendanceHealth(str, Enum):
    EXCELLENT = "EXCELLENT"  # >= 85%
    GOOD = "GOOD"            # 75% - 84%
    AVERAGE = "AVERAGE"      # 60% - 74%
    CRITICAL = "CRITICAL"    # < 60%


AttendanceHealthStatus = AttendanceHealth


HEALTH_COLORS = {
    AttendanceHealth.EXCELLENT: "#059669",  # Emerald Green
    AttendanceHealth.GOOD: "#2563EB",       # Blue
    AttendanceHealth.AVERAGE: "#D97706",    # Amber
    AttendanceHealth.CRITICAL: "#DC2626",   # Red
}

HEALTH_BG_COLORS = {
    AttendanceHealth.EXCELLENT: "#ECFDF5",
    AttendanceHealth.GOOD: "#EFF6FF",
    AttendanceHealth.AVERAGE: "#FFFBEB",
    AttendanceHealth.CRITICAL: "#FEF2F2",
}
