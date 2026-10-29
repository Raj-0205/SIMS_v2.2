# modules/student/__init__.py
from modules.student.controller import StudentController
from modules.student.service import StudentService
from modules.student.repository import StudentRepository

__all__ = ["StudentController", "StudentService", "StudentRepository"]
