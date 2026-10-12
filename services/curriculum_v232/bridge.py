"""Safety-first read-only bridge for the legacy homework matrix.

The historic matrix writes *general-course* numeric topic IDs to `odev`.
Group/student topic IDs live in unrelated namespaces. This module NEVER
returns scoped IDs to the checkbox/write path: it only supplies a separate
teacher-facing preview and migration readiness diagnostics.

No CREATE/UPDATE/INSERT/DELETE, no implicit matching by fuzzy topic names.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from services.curriculum_v231 import effective_topics, topic_key


@dataclass(frozen=True)
class MatrixTopic:
    title: str
    source: str  # Genel / Grup / Öğrenci
    reference: str
    legacy_general_id: int | None
    status: str
    details: str


@dataclass(frozen=True)
class MatrixReview:
    lesson: str
    student_id: int
    rows: tuple[MatrixTopic, ...]
    warnings: tuple[str, ...]
    legacy_row_count: int
    scoped_only_count: int


def _general_rows(rows: Sequence) -> list[tuple[int, str]]:
    """Convert exactly the rows consumed by the old matrix, retaining order."""
    out: list[tuple[int, str]] = []
    for row in rows:
        try:
            topic_id = int(row['id'])
            title = str(row['konu'] or '').strip()
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise ValueError('Genel ders konu listesi uyumsuz; eskisi korunmalı.') from exc
        if topic_id <= 0 or not title:
            raise ValueError('Eski konu ID veya ad alanı eksik.')
        out.append((topic_id, title))
    return out


def inspect_matrix_topics(con, *, lesson: str, student_id: int, general_rows: Sequence) -> MatrixReview:
    """Compare scoped effective subjects with CURRENT existing matrix rows.

    The source general_rows are not modified/reordered. If the legacy rows
    diverge from the DB, report a warning; never guess or mutate IDs.
    """
    if not lesson or int(student_id) <= 0:
        raise ValueError('Öğrenci ve ders belirtilmeli.')
    legacy = _general_rows(general_rows)
    snapshot = effective_topics(con, ders=lesson, ogrenci_id=int(student_id))
    warnings = list(snapshot.warnings)

    id_to_name = {row.identity.row_id: row.name for row in snapshot.all_sources
                  if row.identity.scope == 'Genel'}
    if len(legacy) != len(id_to_name) or any(id_to_name.get(i) != name for i, name in legacy):
        warnings.append('Matristeki genel konu listesi ile güncel genel müfredat uyuşmuyor; kayıt eşleştirmesi yapılmadı.')

    by_name: dict[str, list[int]] = {}
    for tid, name in legacy:
        by_name.setdefault(topic_key(name), []).append(tid)
    rows: list[MatrixTopic] = []
    scoped_only_count = 0
    for view in snapshot.topics:
        topic = view.record
        ident = topic.identity
        candidates = by_name.get(topic_key(topic.name), [])
        # A name match to a general topic is NOT the scoped topic's storage ID.
        legacy_id = candidates[0] if len(candidates) == 1 else None
        if ident.scope == 'Genel' and legacy_id == ident.row_id and id_to_name.get(ident.row_id) == topic.name:
            status = 'Genel matriste kullanılabilir'
            explanation = 'Eski genel konu ID ile uyumlu; tik ve kayıt sistemi değişmez.'
        elif ident.scope == 'Genel':
            status = 'Kimlik denetimi gerekli'
            explanation = 'Genel konu adında/kimliğinde çakışma veya sürüm farklılığı var.'
        elif legacy_id is None:
            scoped_only_count += 1
            status = 'Yalnızca önizleme'
            explanation = 'Bu kapsamın güvenli ödev konu_ID bağlantısı yok; yeni tik satırı eklenmedi.'
        else:
            status = 'Kapsam farklı – yalnızca önizleme'
            explanation = (f'Genel matristeki {legacy_id} numaralı konu aynı adı taşıyor; '
                           'ancak grup/öğrenci konusunun kimliği bu ID değildir.')
        if view.overridden:
            explanation += f' {len(view.overridden)} alt öncelikli tanım gölgeleniyor.'
        rows.append(MatrixTopic(topic.name, ident.scope, ident.key, legacy_id, status, explanation))

    # Legacy general rows with ambiguous names must NOT disappear from any existing checkbox matrix.
    effective_general_ids = {r.legacy_general_id for r in rows if r.source == 'Genel'}
    for legacy_id, name in legacy:
        if legacy_id not in effective_general_ids and topic_key(name) in snapshot.ambiguous_keys:
            warnings.append(f'Genel matristeki “{name}” ({legacy_id}) aynı adlı başka konu ile çakışıyor; eski tik korunmalı.')
    if scoped_only_count:
        warnings.append(f'{scoped_only_count} kapsam özel konu henüz ana matriste tiklenebilir değildir.')
    return MatrixReview(lesson, int(student_id), tuple(rows), tuple(dict.fromkeys(warnings)),
                        len(legacy), scoped_only_count)
