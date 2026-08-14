# modules/admission/views/admission_form.py

import flet as ft
from modules.admission.controller import AdmissionController
from modules.student.controller import StudentController
from modules.student.views.student_search_dialog import StudentSearchDialog
from modules.student.dto import StudentSearchResultDTO
from modules.course.controller import CourseController
from modules.course.views.course_search_dialog import CourseSearchDialog
from modules.course.dto import CourseSearchResultDTO
from core.exceptions import ValidationError, ConflictError
from core.logger.service import LogService

__all__ = ["AdmissionForm"]


class AdmissionForm(ft.Column):
    """Fully functioning UI View for End-to-End Admission & Course Registration."""

    def __init__(self) -> None:
        super().__init__()
        
        # Controllers
        self.admission_controller = AdmissionController()
        self.student_controller = StudentController()
        self.course_controller = CourseController()
        
        # State
        self.selected_student_id: int | None = None
        self.selected_course_id: int | None = None
        
        # Dialogs
        self.student_search_dialog = StudentSearchDialog(
            controller=self.student_controller,
            on_student_selected=self.on_student_selected
        )
        self.course_search_dialog = CourseSearchDialog(
            controller=self.course_controller,
            on_course_selected=self.on_course_selected
        )
        
        # UI Structure
        self.header = ft.Text("Create New Admission", size=24, weight=ft.FontWeight.BOLD)
        
        # --- Student Section ---
        self.student_btn = ft.ElevatedButton(
            text="1. Select Student", icon=ft.icons.PERSON_SEARCH, on_click=self.open_student_dialog
        )
        self.student_display = ft.Text("No student selected.", italic=True, color=ft.colors.GREY_700)
        
        # --- Course Section ---
        self.course_btn = ft.ElevatedButton(
            text="2. Select Course", icon=ft.icons.MENU_BOOK, on_click=self.open_course_dialog, disabled=True
        )
        self.course_display = ft.Text("No course selected.", italic=True, color=ft.colors.GREY_700)
        
        # --- Submission ---
        self.register_btn = ft.ElevatedButton(
            text="3. Complete Registration", icon=ft.icons.APP_REGISTRATION, 
            on_click=self.handle_register, disabled=True
        )

        self.controls = [
            self.header,
            ft.Divider(),
            self.student_btn, self.student_display,
            ft.Divider(),
            self.course_btn, self.course_display,
            ft.Divider(),
            self.register_btn
        ]
        self.spacing = 15
        self.horizontal_alignment = ft.CrossAxisAlignment.START

    def open_student_dialog(self, e: ft.ControlEvent) -> None:
        self.page.dialog = self.student_search_dialog
        self.student_search_dialog.open = True
        self.page.update()

    def open_course_dialog(self, e: ft.ControlEvent) -> None:
        self.page.dialog = self.course_search_dialog
        self.course_search_dialog.open = True
        self.page.update()

    def on_student_selected(self, student: StudentSearchResultDTO) -> None:
        self.selected_student_id = student.id
        self.student_display.value = f"✅ Student: {student.display_name} (ID: {student.id})"
        self.student_display.color = ft.colors.GREEN_700
        self.student_display.italic = False
        
        # Unlock next step
        self.course_btn.disabled = False
        self.check_form_ready()
        self.update()

    def on_course_selected(self, course: CourseSearchResultDTO) -> None:
        self.selected_course_id = course.id
        self.course_display.value = f"✅ Course: {course.display_name} (ID: {course.id})"
        self.course_display.color = ft.colors.GREEN_700
        self.course_display.italic = False
        
        self.check_form_ready()
        self.update()

    def check_form_ready(self) -> None:
        """Enables the register button only when both dependencies are met."""
        self.register_btn.disabled = not (self.selected_student_id and self.selected_course_id)

    def show_message(self, message: str, is_error: bool = False) -> None:
        if not self.page: return
        color = ft.colors.ERROR if is_error else ft.colors.GREEN
        self.page.snack_bar = ft.SnackBar(content=ft.Text(message, color=ft.colors.WHITE), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    def handle_register(self, e: ft.ControlEvent) -> None:
        raw_data = {
            "student_id": self.selected_student_id,
            "course_id": self.selected_course_id
        }

        try:
            admission_id = self.admission_controller.create_admission(raw_data)
            self.show_message(f"Admission and Course linked successfully! (Admission ID: {admission_id})")
            
            # Reset UI
            self.selected_student_id = None
            self.selected_course_id = None
            self.student_display.value = "No student selected."
            self.course_display.value = "No course selected."
            self.student_display.color, self.course_display.color = ft.colors.GREY_700, ft.colors.GREY_700
            self.student_display.italic, self.course_display.italic = True, True
            self.course_btn.disabled, self.register_btn.disabled = True, True
            self.update()

        except (ValidationError, ConflictError) as ex:
            self.show_message(str(ex), is_error=True)
        except Exception as ex:
            LogService.error(f"Unexpected error in UI: {str(ex)}", context=self.__class__.__name__)
            self.show_message("An unexpected error occurred. Please try again.", is_error=True)
