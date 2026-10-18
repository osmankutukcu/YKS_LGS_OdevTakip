# -*- coding: utf-8 -*-
"""V28 fast, optional teacher observations for a selected homework row.

Neither a checkbox nor task completion is learning evidence. Only explicit
teacher actions create/change notes. No INSERT/UPDATE/DELETE in legacy tables.
"""
from __future__ import annotations
from datetime import date, timedelta

# Keep fixed reason codes so translations/UI changes never corrupt stored data.
CHOICES = (
    ('difficulty', 'Zorlandı; neden henüz net değil'),
    ('concept', 'Konu/kazanım anlaşılmadı'),
    ('time', 'Zaman yetmedi'),
    ('attention', 'Dikkat veya işlem hatası'),
    ('workload', 'İş yükü fazla geldi'),
    ('ask', 'Öğrenciye sorulacak'),
    ('easy', 'Kolay geldi (öğretmen gözlemi)'),
)
LABELS = dict(CHOICES)

SCHEMA = '''
CREATE TABLE IF NOT EXISTS adaptive_quick_note_v28 (
  id INTEGER PRIMARY KEY,
  student_id INTEGER NOT NULL REFERENCES ogrenci(id) ON DELETE CASCADE,
  homework_id INTEGER REFERENCES odev(id) ON DELETE SET NULL,
  lesson TEXT NOT NULL,
  topic TEXT NOT NULL,
  reason_code TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'teacher_one_click',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(student_id,homework_id),
  CHECK(reason_code IN ('difficulty','concept','time','attention','workload','ask','easy'))
);
CREATE INDEX IF NOT EXISTS idx_adapt_quick_note_v28_student_time
  ON adaptive_quick_note_v28(student_id,updated_at DESC);
'''


def ensure_schema(con):
    """Lazy creation only on the first explicit quick-note write."""
    con.executescript(SCHEMA)
    con.commit()


def _owned_homework(con, student_id, homework_id):
    """Must match BOTH the homework owner and its parent cluster owner."""
    row = con.execute('''SELECT o.ders AS lesson, o.konu_ad AS topic
      FROM odev o JOIN odev_kume k ON k.id=o.kume_id
      WHERE o.id=? AND o.ogrenci_id=? AND k.ogrenci_id=?''',
      (int(homework_id), int(student_id), int(student_id))).fetchone()
    if row is None:
        raise ValueError('Ödev bu öğrenciye ait değil veya artık mevcut değil.')
    return row


def set_note(con, student_id, homework_id, code):
    """Single explicit teacher action, replaces prior note for that homework.

    `None` means remove only the quick note; homework record is untouched.
    No implicit observation from the check state, save event, or non-completion.
    """
    student_id, homework_id = int(student_id), int(homework_id)
    if code is not None and code not in LABELS:
        raise ValueError('Tanımlı olmayan hızlı gözlem.')
    row = _owned_homework(con, student_id, homework_id)
    # Only the optional table is created, on demand. No old table migration.
    if code is not None:
        if not _table_exists(con):
            ensure_schema(con)
        with con:
            con.execute('''INSERT INTO adaptive_quick_note_v28
              (student_id,homework_id,lesson,topic,reason_code)
              VALUES(?,?,?,?,?)
              ON CONFLICT(student_id,homework_id) DO UPDATE SET
                lesson=excluded.lesson,topic=excluded.topic,
                reason_code=excluded.reason_code,updated_at=CURRENT_TIMESTAMP''',
              (student_id,homework_id,str(row['lesson'] or ''),str(row['topic'] or ''),code))
        return LABELS[code]
    if _table_exists(con):
        with con:
            con.execute('''DELETE FROM adaptive_quick_note_v28
              WHERE student_id=? AND homework_id=?''', (student_id,homework_id))
    return None


def _table_exists(con):
    return bool(con.execute('''SELECT 1 FROM sqlite_master
        WHERE type='table' AND name='adaptive_quick_note_v28' ''').fetchone())


def recent_notes(con, student_id, *, today=None, days=14, limit=12):
    """Strictly read-only, bounded, one-index query; safe for legacy databases."""
    sid = int(student_id)
    if not _table_exists(con):
        return []
    if not con.execute('SELECT 1 FROM ogrenci WHERE id=?',(sid,)).fetchone():
        raise ValueError('Öğrenci bulunamadı.')
    today = date.fromisoformat(str(today)[:10]) if today else date.today()
    start = (today-timedelta(days=max(0,min(int(days),365)))).isoformat()
    end = max(today, date.today()).isoformat()
    rows = con.execute('''SELECT student_id,homework_id,lesson,topic,
       reason_code,updated_at FROM adaptive_quick_note_v28
       WHERE student_id=? AND substr(updated_at,1,10)>=? AND substr(updated_at,1,10)<=?
       ORDER BY updated_at DESC,id DESC LIMIT ?''',
       (sid,start,end,max(1,min(int(limit),30)))).fetchall()
    return [{'student_id':int(r['student_id']),
             'homework_id':r['homework_id'],
             'lesson':r['lesson'],'topic':r['topic'],
             'code':r['reason_code'],
             'label':LABELS.get(r['reason_code'],'Tanımsız gözlem'),
             'updated_at':r['updated_at']} for r in rows]
