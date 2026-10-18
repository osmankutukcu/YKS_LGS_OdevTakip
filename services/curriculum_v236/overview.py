"""Read-only teacher overview. No migration, checkbox writes, or curriculum renaming.

Uses the EXISTING V23.2 identity bridge and V23.3 task ledger. Main matrix
and scoped assignments remain separate namespaces; totals are never merged.
"""
from __future__ import annotations
from dataclasses import dataclass
from services.curriculum_v232 import inspect_matrix_topics
from services.curriculum_v233 import list_assignments


@dataclass(frozen=True)
class ScopedTotals:
    open_count: int = 0
    completed_count: int = 0
    cancelled_count: int = 0


def count_scoped_tasks(assignments) -> ScopedTotals:
    records = tuple(assignments)
    return ScopedTotals(
        sum(x.status == 'devam' for x in records),
        sum(x.status == 'tamam' for x in records),
        sum(x.status == 'iptal' for x in records),
    )


@dataclass(frozen=True)
class CoverageOverview:
    student_id: int
    student_label: str
    group_label: str
    lesson: str
    review: object
    general_count: int
    group_count: int
    personal_count: int
    extra_count: int
    matrix_match_count: int
    problems: tuple[str, ...]
    scoped_tasks: ScopedTotals

    @property
    def needs_attention(self) -> bool:
        return bool(self.problems)

    @property
    def teacher_message(self) -> str:
        if self.problems:
            return f'{len(self.problems)} kontrol notu var. Konu kimliklerini gözden geçirin; mevcut ödev tikleri korunuyor.'
        if self.extra_count or self.group_count or self.personal_count:
            return ('Ana konu matrisi korunuyor. Grup/öğrenciye özel tanımlar ayrı kimlikle izleniyor; '
                    'özel ödevler ayrıca takip ediliyor.')
        return 'Konu tanımları mevcut matrisle uyumlu görünüyor; şu anda işlem gerekmiyor.'


def read_coverage_overview(con, *, lesson: str, student_id: int, general_rows) -> CoverageOverview:
    """Only SELECT; checks current student + one lesson, including scoped ledger.

    Caller controls the connection. No CREATE or PRAGMA; works with query_only.
    """
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('Geçerli öğrenci kimliği gerekli.')
    row = con.execute('SELECT ad,soyad,ana_grup,alt_grup FROM ogrenci WHERE id=?', (student_id,)).fetchone()
    if not row:
        raise ValueError('Öğrenci bulunamadı; başka öğrenciye ait bilgi gösterilmedi.')
    name = ' '.join(str(p or '').strip() for p in (row[0], row[1])).strip()
    group = ' / '.join(str(p or '').strip() for p in (row[2], row[3]) if str(p or '').strip())
    review = inspect_matrix_topics(con, lesson=lesson, student_id=student_id, general_rows=general_rows)
    records = list_assignments(con, student_id=student_id, lesson=lesson)
    problems = list(review.warnings)
    # Warnings from an expected separated scoped-topic are informational,
    # not a broken legacy matrix. Identity mismatch is always a problem.
    problems = [p for p in problems if not ('henüz ana matriste tiklenebilir değildir' in p)]
    for item in review.rows:
        if item.status == 'Kimlik denetimi gerekli':
            problems.append(f'Kimlik kontrolü: {item.title}')
    return CoverageOverview(
        student_id=student_id,
        student_label=name or f'Öğrenci #{student_id}',
        group_label=group,
        lesson=lesson,
        review=review,
        general_count=review.legacy_row_count,
        group_count=sum(x.source == 'Grup' for x in review.rows),
        personal_count=sum(x.source == 'Öğrenci' for x in review.rows),
        extra_count=review.scoped_only_count,
        matrix_match_count=sum(x.status == 'Genel matriste kullanılabilir' for x in review.rows),
        problems=tuple(dict.fromkeys(problems)),
        scoped_tasks=count_scoped_tasks(records),
    )
