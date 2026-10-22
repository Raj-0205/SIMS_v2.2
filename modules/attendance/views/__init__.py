# modules/attendance/views/__init__.py

from modules.attendance.views.attendance_home import AttendanceHome
from modules.attendance.views.offline_format_dialog import OfflineFormatDialog
from modules.attendance.views.offline_upload_modal import OfflineUploadModal

__all__ = [
    "AttendanceHome",
    "OfflineFormatDialog",
    "OfflineUploadModal",
]
