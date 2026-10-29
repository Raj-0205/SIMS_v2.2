# modules/course/views/__init__.py

from modules.course.views.course_home import CourseHome
from modules.course.views.course_showcase_view import CourseShowcaseView
from modules.course.views.web_showcase_manager_dialog import WebShowcaseManagerDialog
from modules.course.views.course_finder_view import CourseFinderView

__all__ = ["CourseHome", "CourseShowcaseView", "WebShowcaseManagerDialog", "CourseFinderView"]

