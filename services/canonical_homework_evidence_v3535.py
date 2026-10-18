# -*- coding: utf-8 -*-
"""V3.5.35: conservative, read-only canonical homework observations.

Sources are not interchangeable: child rows linked through odev_id replace
that parent *only*, unlinked children are independent unless their group
contains unlinked legacy rows (ambiguous overlap -> quarantine group).
No writes, status changes, messages, inferred mastery, or student reattribution.
Call within an existing coherent SQLite read transaction / query_only connection.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
import sqlite3

from services.daily_coach_v10 import parse_day

DONE = frozenset(('tamam', 'tamamlandi', 'tamamlandı', 'yapildi', 'yapıldı', 'bitti', 'ok', 'done'))
OPEN = frozenset(('devam', 'bekliyor', 'beklemede', 'acik', 'açık', 'eksik', 'todo', 'kısmi', 'kismi', 'yarim', 'yarım', 'kaldı'))
INACTIVE = frozenset(('silindi', 'aktarildi', 'aktarıldı', 'iptal', 'iptal edildi'))
_TABLES = {'ogrenci', 'odev_kume', 'odev', 'odev_satir'}


def _table_columns(con):
    names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not _TABLES <= names:
        raise sqlite3.OperationalError('Required student/homework source missing')
    cols = {t: {r[1] for r in con.execute('PRAGMA table_info(' + t + ')')} for t in _TABLES}
    mandatory = {
        'ogrenci': {'id', 'ad', 'soyad', 'aktif'},
        'odev_kume': {'id', 'ogrenci_id', 'bitis_tarihi'},
        'odev': {'id', 'ogrenci_id', 'kume_id', 'durum'},
        'odev_satir': {'id', 'ogrenci_id', 'kume_id', 'durum'},
    }
    if any(not required <= cols[name] for name, required in mandatory.items()):
        raise sqlite3.OperationalError('Required ownership/status fields unavailable')
    return cols


def _read(con, table, columns, optional):
    statement = ','.join(col if col in columns else ('NULL AS ' + col) for col in optional)
    cursor = con.execute('SELECT ' + statement + ' FROM ' + table)
    return [dict(zip(optional, values)) for values in cursor.fetchall()]


def _sid(value):
    return value if type(value) is int and value > 0 else None


def _flag(blocked, *ids):
    for sid in ids:
        sid = _sid(sid)
        if sid is not None:
            blocked.add(sid)


def scan_canonical_homework(con: sqlite3.Connection, *, today: date | None = None,
                            max_cards: int = 5, focus_student_id: int | None = None) -> dict:
    """Conservative same-snapshot reconciliation for LOCAL students only.

    Result never carries contact details. Mixed groups with unlinked legacy and
    child rows cannot be assumed duplicate OR distinct; their entire group is
    omitted from action counts, and its owner does not receive priority advice.
    """
    day = today or date.today()
    if not isinstance(day, date):
        raise ValueError('today must be a date')
    max_cards = max(1, min(10, int(max_cards)))
    if focus_student_id is not None and (type(focus_student_id) is not int or focus_student_id <= 0):
        raise ValueError("focus_student_id must identify one student")
    cols = _table_columns(con)
    students = _read(con, 'ogrenci', cols['ogrenci'], ('id', 'ad', 'soyad', 'aktif'))
    active = {r['id']: ' '.join(str(r[k] or '').strip() for k in ('ad', 'soyad')).strip()[:100]
              for r in students if _sid(r['id']) is not None and r['aktif'] == 1}
    if focus_student_id is not None and focus_student_id not in active:
        raise ValueError("Student is not active or not present")
    groups = {r['id']: r for r in _read(con, 'odev_kume', cols['odev_kume'],
              ('id', 'ogrenci_id', 'bitis_tarihi')) if _sid(r['id']) is not None}
    primary = _read(con, 'odev', cols['odev'],
                    ('id', 'ogrenci_id', 'kume_id', 'durum', 'ders'))
    children = _read(con, 'odev_satir', cols['odev_satir'],
                     ('id', 'ogrenci_id', 'kume_id', 'odev_id', 'durum', 'ders', 'silindi', 'aktarildi'))
    parents = {r['id']: r for r in primary if _sid(r['id']) is not None}
    blocked = set()
    ambiguous_groups = set()
    rejected_rows = 0
    linked_ids = set()
    by_group_primary = defaultdict(set)
    by_group_unlinked = defaultdict(set)
    candidates = []

    def owner(row, parent=None):
        """Return (student, group, due) or mark both implicated owners unsafe."""
        nonlocal rejected_rows
        sid = _sid(row.get('ogrenci_id'))
        group_id = row.get('kume_id')
        if group_id is None and parent is not None:
            group_id = parent.get('kume_id')  # explicit, verified child->parent link
        g = groups.get(group_id) if _sid(group_id) is not None else None
        g_owner = _sid(g['ogrenci_id']) if g else None
        if parent is not None and (sid != _sid(parent.get('ogrenci_id')) or
                                   (row.get('kume_id') is not None and row['kume_id'] != parent.get('kume_id'))):
            _flag(blocked, sid, parent.get('ogrenci_id'), g_owner)
            rejected_rows += 1
            return None
        if group_id is not None and (g is None or sid is None or g_owner != sid):
            _flag(blocked, sid, g_owner, parent.get('ogrenci_id') if parent else None)
            rejected_rows += 1
            return None
        if sid is None or sid not in active:
            rejected_rows += 1
            return None
        return sid, group_id, parse_day(g['bitis_tarihi']) if g else None

    for r in primary:
        linked = owner(r)
        if linked:
            by_group_primary[linked[:2]].add(r['id'])
            candidates.append(('odev', r, linked))

    for r in children:
        ref = r.get('odev_id')
        parent = parents.get(ref) if ref is not None else None
        if ref is not None and parent is None:
            _flag(blocked, r.get('ogrenci_id'), groups.get(r.get('kume_id'), {}).get('ogrenci_id'))
            rejected_rows += 1
            continue
        linked = owner(r, parent=parent)
        if linked is None:
            continue
        sid, gid, due = linked
        if ref is not None:
            linked_ids.add(ref)
        elif gid is not None:
            by_group_unlinked[(sid, gid)].add(r['id'])
        candidates.append(('odev_satir', r, linked))

    # Both legacy parent(s) and independent child row(s) in the same group:
    # absent explicit odev_id, similarity of lesson/topic is NOT deduplication proof.
    for group_key in by_group_primary.keys() & by_group_unlinked.keys():
        ambiguous_groups.add(group_key)
        blocked.add(group_key[0])

    included = defaultdict(list)
    inactive_shadow = 0
    sources = defaultdict(int)
    excluded = 0
    undated = 0
    unknown_status = 0
    for table, row, (sid, gid, due) in candidates:
        if sid in blocked:
            excluded += 1
            continue
        if table == 'odev' and row['id'] in linked_ids:
            excluded += 1    # explicit, safe shadow; distinct child rows retained
            continue
        if table == 'odev_satir' and (row.get('silindi') in (1, '1', True) or
                                      row.get('aktarildi') in (1, '1', True)):
            excluded += 1
            inactive_shadow += 1
            continue
        status = str(row.get('durum') or 'devam').strip().lower()
        if status in INACTIVE:
            excluded += 1
            continue
        if status not in DONE and status not in OPEN:
            unknown_status += 1
            excluded += 1
            continue
        if due is None:
            undated += 1
        sources[table] += 1
        included[sid].append((status in DONE, due, str(row.get('ders') or '')[:80]))

    # Optional per-student projection: built from the SAME canonical inclusions,
    # not a second legacy query or a truncated institution-wide top-N queue.
    # Keep default result shape unchanged for all existing V3.5.35 consumers.
    focus = None
    if focus_student_id is not None:
        sid = focus_student_id
        if sid in blocked:
            focus = {'student_id': sid, 'state': 'LINK_REVIEW',
                     'canonical_tasks': None, 'completed_tasks': None,
                     'overdue_open_tasks': None, 'undated_tasks': None,
                     'top_overdue_lesson': None}
        else:
            tasks = included.get(sid, ())
            overdue = [t for t in tasks if not t[0] and t[1] is not None and t[1] < day]
            lesson_counts = defaultdict(int)
            for _, _, subject in overdue:
                lesson_counts[subject or 'Ders belirtilmedi'] += 1
            top_lesson = sorted(lesson_counts, key=lambda x: (-lesson_counts[x], x))[0] if lesson_counts else None
            focus = {'student_id': sid, 'state': 'PARTIAL_COVERAGE' if any(t[1] is None for t in tasks) else 'OBSERVED',
                     'canonical_tasks': len(tasks),
                     'completed_tasks': sum(t[0] for t in tasks),
                     'overdue_open_tasks': len(overdue),
                     'undated_tasks': sum(t[1] is None for t in tasks),
                     'top_overdue_lesson': top_lesson}
    queue = []
    total_overdue, total_complete, total_tasks = 0, 0, 0
    for sid in sorted(set(active) - blocked):
        tasks = included.get(sid, [])
        total_tasks += len(tasks)
        total_complete += sum(done for done, _, _ in tasks)
        overdue = [t for t in tasks if not t[0] and t[1] is not None and t[1] < day]
        if overdue:
            total_overdue += len(overdue)
            breakdown = defaultdict(int)
            for _, _, subject in overdue:
                breakdown[subject or 'Ders belirtilmedi'] += 1
            top_lesson = sorted(breakdown, key=lambda s: (-breakdown[s], s))[0]
            queue.append({'student_id': sid, 'name': active[sid], 'overdue_open': len(overdue),
                          'lesson': top_lesson,
                          'basis': 'Açık, teslim tarihi geçmiş; öğrenci ve küme bağlantısı doğrulanmış ödev kanıtı',
                          'action': 'Öğrenciyle gerçek durumu doğrulayın; gerekiyorsa telafi planı önerin.',
                          'requires_teacher_approval': True})
    queue.sort(key=lambda r: (-r['overdue_open'], r['student_id']))
    partial = bool(blocked or ambiguous_groups or rejected_rows or undated or unknown_status or inactive_shadow)
    result = {
        'state': 'PARTIAL_COVERAGE' if partial else 'OBSERVED',
        'as_of': day.isoformat(),
        'scope': 'active_students_in_this_local_sqlite_only',
        'active_students': len(active),
        'evaluated_students': len(active.keys() - blocked),
        'ownership_or_ambiguity_review_students': len(blocked & active.keys()),
        'excluded_student_ids': sorted(blocked & active.keys()),
        'ambiguous_legacy_modern_groups': len(ambiguous_groups),
        'rejected_rows': rejected_rows,
        'excluded_or_shadow_rows': excluded,
        'undated_count': undated,
        'unknown_status_count': unknown_status,
        'canonical_tasks': total_tasks,
        'completed_tasks': total_complete,
        'overdue_open_tasks': total_overdue,
        'overdue_students': len(queue),
        'priority_cards': queue[:max_cards],
        'priority_total': len(queue),
        'source_counts': {'odev': sources['odev'], 'odev_satir': sources['odev_satir']},
        'dedup_rule': 'Explicit verified odev_satir.odev_id shadows its parent only; independent child items stay distinct.',
        'limited_by': 'Local DB and recognized due dates; no cross-device sync, exams, learning or mastery inferred.',
        'not_mastery_or_risk_diagnosis': True,
        'remote_verified': False,
        'no_automatic_write': True,
    }

    if focus is not None:
        # Global partial coverage may be due to OTHER students. The focused
        # student's count stays scoped, while the global warning stays visible.
        result['focus_student'] = focus
    return result
