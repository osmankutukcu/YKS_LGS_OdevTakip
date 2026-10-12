"""Immutable data contract between student readers, coach assessment and UI."""
from dataclasses import dataclass


@dataclass(frozen=True)
class StudentOverview:
    student_id: int
    student_name: str
    homework_last30: str
    homework_sample: int
    homework_overdue: int
    homework_uncertainty: int
    exam_summary: str
    exam_evidence: str
    exam_explanation: str
    coaching_plan: str
    coaching_goals: int
    coaching_program_entries: int
    tracked_topics: int
    marked_topics: int
    source_warnings: tuple[str, ...] = ()
