"""V16 student overview: read-only adapters, no database migrations or writes."""
from .reader import read_student_overview
from .models import StudentOverview

__all__ = ['read_student_overview', 'StudentOverview']
