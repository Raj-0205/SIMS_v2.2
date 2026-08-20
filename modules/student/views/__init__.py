# modules/student/views/__init__.py

from modules.student.views.student_home import StudentHome
from modules.student.views.student_form_modal import StudentFormModal
from modules.student.views.student_workspace_dialog import StudentWorkspaceDialog
from modules.student.views.student_detail_dialog import StudentDetailDialog
from modules.student.views.student_search_dialog import StudentSearchDialog

__all__ = [
    "StudentHome",
    "StudentFormModal",
    "StudentWorkspaceDialog",
    "StudentDetailDialog",
    "StudentSearchDialog",
]
