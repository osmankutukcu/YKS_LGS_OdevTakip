# -*- coding: utf-8 -*-
"""V3.5.26 - Student portal read projections; no writes or automatic reconciliation.

The two homework tables are *not* row-for-row interchangeable. A linked
``odev_satir`` is displayed in preference to its ``odev`` parent. Independent
legacy rows (odev_id NULL) are retained. Multiple distinct child rows remain
distinct; they can represent legitimate work items. Cross-student links do
not suppress the original student's parent task.
"""
from __future__ import annotations
import sqlite3

_DONE = "('tamam','yapildi','yapıldı','bitti','done')"


def _homework_cte(con: sqlite3.Connection) -> str:
    """Return a student-scoped CTE that expects two student-id parameters.

    Older databases without the ``odev_id`` column are treated conservatively:
    without an explicit link we cannot safely deduplicate their rows.
    """
    cols = {str(r[1]) for r in con.execute('PRAGMA table_info(odev_satir)')}
    linked = ('AND NOT EXISTS (SELECT 1 FROM odev_satir s '
              'WHERE s.odev_id=o.id AND s.ogrenci_id=o.ogrenci_id)') if 'odev_id' in cols else ''
    return f"""
    WITH portal_tasks AS (
      SELECT s.ders AS ders, s.kitap AS kitap, s.konu AS konu,
             s.tarih AS tarih, LOWER(COALESCE(s.durum, 'devam')) AS durum,
             s.id AS row_id
        FROM odev_satir s WHERE s.ogrenci_id=?
      UNION ALL
      SELECT o.ders AS ders, o.kitap_ad AS kitap, o.konu_ad AS konu,
             NULL AS tarih, LOWER(COALESCE(o.durum, 'devam')) AS durum,
             o.id AS row_id
        FROM odev o WHERE o.ogrenci_id=? {linked}
    )
    """


def subject_progress(con: sqlite3.Connection, student_id: int) -> tuple[list[str], list[int]]:
    """Percent complete by lesson, with explicit link-based deduplication."""
    sql = _homework_cte(con) + f"""
    SELECT COALESCE(ders,'Genel'), COUNT(*),
           SUM(CASE WHEN durum IN {_DONE} THEN 1 ELSE 0 END)
      FROM portal_tasks
     GROUP BY COALESCE(ders,'Genel')
     ORDER BY COALESCE(ders,'Genel')
    """
    rows = con.execute(sql, (student_id, student_id)).fetchall()
    return ([str(r[0]) for r in rows],
            [int(100 * (r[2] or 0) / r[1]) if r[1] else 0 for r in rows])


def pending_homework(con: sqlite3.Connection, student_id: int, limit: int = 10) -> list[dict]:
    """Up to 10 pending rows; caller never mutates them."""
    if not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError('limit must be between 1 and 100')
    sql = _homework_cte(con) + f"""
    SELECT ders, kitap, konu, tarih FROM portal_tasks
     WHERE durum NOT IN {_DONE}
     ORDER BY COALESCE(tarih,'9999-99-99') ASC, row_id DESC
     LIMIT ?
    """
    return [dict(ders=r[0] or '-', kitap=r[1] or '-', konu=r[2] or '-',
                 tarih=r[3] or '-')
            for r in con.execute(sql, (student_id, student_id, limit)).fetchall()]
