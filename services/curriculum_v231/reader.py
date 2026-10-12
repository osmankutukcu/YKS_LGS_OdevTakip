"""Salt okunur, kapsam-aware müfredat listesi ve kaynak kimlikleri.

Do NOT silently synchronize/rename legacy homework rows. Legacy name-based
references may remain ambiguous even if an effective topic can be displayed.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from services.curriculum_v23.impact import topic_table, CurriculumSafetyError
from .identity import TopicIdentity, topic_key


@dataclass(frozen=True)
class TopicRecord:
    identity: TopicIdentity
    name: str
    target_questions: Optional[int]
    target_minutes: Optional[int]


@dataclass(frozen=True)
class TopicView:
    record: TopicRecord
    overridden: tuple[TopicIdentity, ...] = ()


@dataclass(frozen=True)
class CurriculumSnapshot:
    ders: str
    topics: tuple[TopicView, ...]
    warnings: tuple[str, ...]
    ambiguous_keys: tuple[str, ...]
    all_sources: tuple[TopicRecord, ...]


def _has_table(con, name):
    return bool(con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())


def _columns(con, name):
    return {r[1] for r in con.execute(f'PRAGMA table_info("{name}")')}


def _load(con, *, scope, ders, ana_grup='', alt_grup='', ogrenci_id=0):
    if scope == 'Genel':
        table = topic_table(con, 'Genel', ders)
        sql, args = f'SELECT id, konu, ort_soru, ort_sure FROM "{table}" ORDER BY id', ()
    elif scope == 'Grup':
        if not (ana_grup and alt_grup):
            raise CurriculumSafetyError('Eksik grup kimliği.')
        if not _has_table(con, 'grup_konu_duzen'):
            return []
        sql, args = ('SELECT id, konu, ort_soru, ort_sure FROM grup_konu_duzen '
                     'WHERE ders=? AND ana_grup=? AND alt_grup=? ORDER BY id'), (ders, ana_grup, alt_grup)
    else:
        if int(ogrenci_id) <= 0:
            raise CurriculumSafetyError('Öğrenci kimliği gerekli.')
        if not _has_table(con, 'ogrenci_konu_duzen'):
            return []
        sql, args = ('SELECT id, konu, ort_soru, ort_sure FROM ogrenci_konu_duzen '
                     'WHERE ders=? AND ogrenci_id=? ORDER BY id'), (ders, int(ogrenci_id))
    # Do not guess schema for a different student or another subject.
    cols = _columns(con, table if scope == 'Genel' else ('grup_konu_duzen' if scope == 'Grup' else 'ogrenci_konu_duzen'))
    if not {'id', 'konu', 'ort_soru', 'ort_sure'} <= cols:
        raise CurriculumSafetyError('Müfredat tablosu beklenen kolonları içermiyor.')
    result = []
    for row in con.execute(sql, args):
        name = str(row[1] or '').strip()
        if not name:
            continue
        identity = TopicIdentity(scope, ders, int(row[0]), ana_grup if scope == 'Grup' else '',
                                 alt_grup if scope == 'Grup' else '', int(ogrenci_id) if scope == 'Öğrenci' else 0)
        result.append(TopicRecord(identity, name, row[2], row[3]))
    return result


def _student_group(con, student_id):
    if not _has_table(con, 'ogrenci'):
        raise CurriculumSafetyError('Öğrenci tablosu bulunamadı.')
    cols = _columns(con, 'ogrenci')
    if not {'id', 'ana_grup', 'alt_grup'} <= cols:
        exists = con.execute('SELECT 1 FROM ogrenci WHERE id=?', (student_id,)).fetchone()
        if not exists:
            raise CurriculumSafetyError('Öğrenci bulunamadı; başka öğrenciye ait konu gösterilmiyor.')
        return ('', '')
    row = con.execute('SELECT ana_grup, alt_grup FROM ogrenci WHERE id=?', (student_id,)).fetchone()
    if row is None:
        raise CurriculumSafetyError('Öğrenci bulunamadı; başka öğrenciye ait konu gösterilmiyor.')
    return str(row[0] or '').strip(), str(row[1] or '').strip()


def effective_topics(con, *, ders: str, ogrenci_id: Optional[int] = None,
                     ana_grup: Optional[str] = None, alt_grup: Optional[str] = None) -> CurriculumSnapshot:
    """Genel < Grup < Öğrenci. Only confirmed scope is used.

    Missing group context does not fall back to arbitrary matches. Same-tier
    duplicate labels are excluded and flagged rather than silently overridden.
    No SQL writes or schema changes.
    """
    # Validating subject table before reading any dynamic SQL name is essential.
    topic_table(con, 'Genel', ders)
    warnings: list[str] = []
    aid = int(ogrenci_id) if ogrenci_id is not None else 0
    if aid < 0:
        raise CurriculumSafetyError('Geçerli öğrenci kimliği gerekli.')
    ag = str(ana_grup or '').strip()
    sub = str(alt_grup or '').strip()
    if aid:
        group_a, group_b = _student_group(con, aid)
        if ag and sub and (group_a and group_b) and (ag, sub) != (group_a, group_b):
            raise CurriculumSafetyError('Seçili grup öğrencinin kayıtlı grubuyla uyuşmuyor.')
        if ag or sub:
            if not (ag and sub):
                raise CurriculumSafetyError('Ana/alt grup birlikte belirtilmeli.')
        else:
            ag, sub = group_a, group_b
            if not (ag and sub):
                warnings.append('Öğrenci grubu kesin belirlenemedi; grup konuları eklenmedi.')
    elif bool(ag) != bool(sub):
        raise CurriculumSafetyError('Ana ve alt grup birlikte seçilmeli.')
    layers = [_load(con, scope='Genel', ders=ders)]
    if ag and sub:
        layers.append(_load(con, scope='Grup', ders=ders, ana_grup=ag, alt_grup=sub))
    if aid:
        layers.append(_load(con, scope='Öğrenci', ders=ders, ogrenci_id=aid))
    sources = tuple(item for layer in layers for item in layer)
    effective: dict[str, TopicRecord] = {}
    shadows: dict[str, list[TopicIdentity]] = {}
    ambiguous: set[str] = set()
    for layer in layers:
        tier: dict[str, list[TopicRecord]] = {}
        for item in layer:
            tier.setdefault(topic_key(item.name), []).append(item)
        for k, entries in tier.items():
            if len(entries) != 1 or k in ambiguous:
                ambiguous.add(k)
                effective.pop(k, None)
                warnings.append(f'Çakışan konu adı ({entries[0].identity.scope}): {entries[0].name}. Manuel inceleme gerekli.')
                continue
            item = entries[0]
            if k in effective:
                shadows.setdefault(k, []).append(effective[k].identity)
            effective[k] = item
    # Keep existing base order and append additional topics by layer; no alphabetical resort.
    ordering = {k: i for i, k in enumerate(dict.fromkeys(topic_key(x.name) for x in sources))}
    entries = tuple(TopicView(value, tuple(shadows.get(k, ()))) for k, value in
                    sorted(effective.items(), key=lambda p: ordering[p[0]]))
    return CurriculumSnapshot(ders, entries, tuple(warnings), tuple(sorted(ambiguous)), sources)
