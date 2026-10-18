"""V24.3 – conservative, *read-only* subject/topic scoped refresh decisions.

Never assumes that a SQLite commit contains a student/subject/topic ID.
Only compares records in five explicitly owned per-student tables with
known subject columns. Other changes are treated as unknown and refreshed.
A changed subject can therefore be skipped ONLY when the bounded snapshot
proves it did not change. Missing schema, oversized data, invalid values,
unknown aliases, or new subscriptions ALWAYS trigger safe refresh.
No writes, triggers, cloud transport, persistent personal data or GUI imports.
"""
from __future__ import annotations
from dataclasses import dataclass
from collections import defaultdict
from hashlib import sha256
import sqlite3
import unicodedata
from services.student_change_scope_v242 import ScopeNotReliable,StudentDataChange

MAX_ROWS_PER_TABLE = 500
MAX_BYTES_PER_ROW = 1_000_000
# Student column, subject column, topic column (or None for book-wide records).
_SCOPED_TABLES = {
    'odev': ('ogrenci_id','ders','konu_ad'),
    'odev_satir': ('ogrenci_id','ders','konu'),
    'odev_takip': ('ogrenci_id','ders_adi','konu_adi'),
    'koc_konu_takip': ('ogrenci_id','ders_adi','konu_adi'),
    'koc_kitaplar': ('ogrenci_id','ders_adi',None),
}
# Strongly explicit aliases only. LGS mathematics must NEVER match TYT mathematics.
_ALIASES = {
    'matematik tyt':'tyt matematik','tyt matematik':'tyt matematik',
    'matematik ayt':'ayt matematik','ayt matematik':'ayt matematik',
    'matematik lgs':'lgs matematik','lgs matematik':'lgs matematik',
}

def course_key(value):
    if not isinstance(value,str) or not value.strip():return ''
    raw=' '.join(value.replace('İ','i').replace('I','ı').replace('_',' ').replace('(',' ').replace(')',' ').split()).casefold()
    return _ALIASES.get(unicodedata.normalize('NFC',raw),unicodedata.normalize('NFC',raw))

def topic_key(value):
    return unicodedata.normalize('NFC',' '.join(str(value or '').split()).casefold())

@dataclass(frozen=True)
class CourseRefreshDecision:
    refresh: bool
    subject: str
    changed_topics: tuple[str,...] = ()
    uncertain: bool = False
    reason: str = ''


def _course_snapshot(con: sqlite3.Connection, student_id: int, subject: str):
    if type(student_id) is not int or student_id <= 0 or not subject:
        raise ScopeNotReliable('student or subject selection unavailable')
    existing={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    result={}
    for table,(owner,subject_col,topic_col) in _SCOPED_TABLES.items():
        if table not in existing:continue
        cols={r[1] for r in con.execute(f'PRAGMA table_info("{table}")')}
        required={owner,subject_col}|({topic_col} if topic_col else set())
        if not required.issubset(cols):raise ScopeNotReliable(f'Unsupported {table} schema')
        # *Hard-coded* identifier allowlist; student ID is a bound parameter.
        rows=con.execute(f'SELECT * FROM "{table}" WHERE "{owner}"=? LIMIT ?',
                         (student_id,MAX_ROWS_PER_TABLE+1)).fetchall()
        if len(rows)>MAX_ROWS_PER_TABLE:raise ScopeNotReliable(f'{table}: data exceeds bound')
        descriptions=[x[1] for x in con.execute(f'PRAGMA table_info("{table}")')]
        si=descriptions.index(subject_col);ti=descriptions.index(topic_col) if topic_col else None
        grouped=defaultdict(list)
        for row in rows:
            c=course_key(row[si])
            if not c:raise ScopeNotReliable(f'{table}: row has no known subject')
            if c!=subject:continue
            if ti is not None:
                if row[ti] is None or not str(row[ti]).strip():
                    raise ScopeNotReliable(f'{table}: row has no topic')
                topic=topic_key(row[ti])
            else:
                topic='*'  # course-wide information; not a specific topic
            encoded=repr(tuple(row)).encode('utf8',errors='replace')
            if len(encoded)>MAX_BYTES_PER_ROW:raise ScopeNotReliable(f'{table}: oversized entry')
            grouped[topic].append(sha256(encoded).digest())
        for topic,hashes in grouped.items():
            result[(table,topic)]=sha256(b''.join(sorted(hashes))).hexdigest()
    return result

class CourseTopicScope:
    def __init__(self):self._baseline={}

    def baseline(self, con, sid, subject):
        key=course_key(subject)
        if not key:raise ScopeNotReliable('Course selection missing')
        self._baseline[(sid,key)]=_course_snapshot(con,sid,key)

    def on_commit(self, con, change:StudentDataChange, subject:str):
        """Only return `refresh=False` on positively proven unrelated-course changes."""
        key=course_key(subject)
        selected=(change.student_id,key)
        if not key:return CourseRefreshDecision(True,key,(),True,'No selected course')
        if change.uncertain or not change.tables:
            self._baseline.pop(selected,None)
            return CourseRefreshDecision(True,key,(),True,'Student scope unknown')
        # If a source with no assured subject changed, never suppress refresh.
        if set(change.tables)-set(_SCOPED_TABLES):
            self._baseline.pop(selected,None)
            return CourseRefreshDecision(True,key,(),True,'Unscoped source changed')
        try:
            before=self._baseline.get(selected)
            now=_course_snapshot(con,change.student_id,key)
            self._baseline[selected]=now
            if before is None:
                return CourseRefreshDecision(True,key,(),True,'No prior course baseline')
            keys={k for k in set(before)|set(now) if before.get(k)!=now.get(k)}
            if not keys:return CourseRefreshDecision(False,key)
            topics={topic for _,topic in keys if topic!='*'}
            unknown_topic=any(topic=='*' for _,topic in keys)
            return CourseRefreshDecision(True,key,tuple(sorted(topics)),unknown_topic,
                                         'Course data changed')
        except (sqlite3.Error,ScopeNotReliable,ValueError,MemoryError):
            self._baseline.pop(selected,None)
            return CourseRefreshDecision(True,key,(),True,'Course snapshot not reliable')
