"""Pure, student-safe alert decision. Never assumes scoped topics are errors."""
from dataclasses import dataclass

@dataclass(frozen=True)
class CoverageNotice:
    lesson: str
    warning_count: int
    heading: str

def coverage_notice(overview, lesson: str):
    if not overview or not overview.needs_attention:
        return None
    count = len(overview.problems)
    if count < 1 or not lesson:
        return None
    return CoverageNotice(lesson=lesson, warning_count=count,
       heading=f'{lesson}: {count} konu eşleşme uyarısı; mevcut ödev tikleri korunuyor.')
