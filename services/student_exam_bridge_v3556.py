# -*- coding: utf-8 -*-
"""V3556: read-only Student360 / Coach / Homework -> exam planning evidence bridge.

All topic IDs are exact normalized lesson code + title. No fuzzy learning claim.
No students are persisted or sent to any external service by this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import closing
from datetime import date
from pathlib import Path
from typing import Optional
import sqlite3
import unicodedata
import re

from services.exam_planning_v3555 import TRACK_TABLES, COURSE_NAMES

# Only explicit, known legacy aliases are accepted. An unspecified 'Matematik'
# cannot safely mean TYT, AYT or LGS Matematik.
LESSON_ALIASES = {
    'tyt_matematik': ('tyt_matematik', 'TYT Matematik', '(TYT) Matematik', 'Matematik (TYT)'),
    'ayt_matematik': ('ayt_matematik', 'AYT Matematik', '(AYT) Matematik', 'Matematik (AYT)'),
    'lgs_matematik': ('lgs_matematik', 'LGS Matematik', '(LGS) Matematik', 'Matematik (LGS)'),
    'problemler': ('problemler', 'Problemler'),
    'geometri': ('geometri', 'Geometri'),
    'fizik': ('fizik', 'Fizik'),
    'kimya': ('kimya', 'Kimya'),
    'biyoloji': ('biyoloji', 'Biyoloji'),
    'turkce': ('turkce', 'Türkçe', 'Türkçe (TYT)', '(TYT) Türkçe', 'TYT Türkçe'),
    'paragraf': ('paragraf', 'Paragraf'),
    'edebiyat': ('edebiyat', 'Edebiyat', 'Türk Dili ve Edebiyatı'),
    'tarih': ('tarih', 'Tarih'),
    'cografya': ('cografya', 'Coğrafya', 'Cografya'),
    'felsefe': ('felsefe', 'Felsefe'),
    'lgs_fen': ('lgs_fen', 'LGS Fen', '(LGS) Fen', 'Fen Bilimleri (LGS)', 'LGS Fen Bilimleri'),
    'lgs_turkce': ('lgs_turkce', 'LGS Türkçe', '(LGS) Türkçe'),
    'lgs_inkilap': ('lgs_inkilap', 'LGS İnkılap', 'LGS İnkılap Tarihi', 'T.C. İnkılap Tarihi ve Atatürkçülük (LGS)'),
    'lgs_dinkulturu': ('lgs_dinkulturu', 'LGS Din', 'LGS Din Kültürü', '(LGS) Din Kültürü'),
    'lgs_ingilizce': ('lgs_ingilizce', 'LGS İngilizce', '(LGS) İngilizce'),
}


def _norm(value: object) -> str:
    value = unicodedata.normalize('NFKC', str(value or '').strip()).casefold()
    value = value.replace('\u0307', '')  # Turkish İ case-folding
    return ' '.join(value.split())


_ALIAS_LOOKUP: dict[str, str] = {}
for _code, _aliases in LESSON_ALIASES.items():
    for _alias in _aliases:
        _key = _norm(_alias)
        if _key in _ALIAS_LOOKUP and _ALIAS_LOOKUP[_key] != _code:
            raise RuntimeError('Belirsiz ders eş anlamlısı: ' + _alias)
        _ALIAS_LOOKUP[_key] = _code


def _connection(db_path):
    p = Path(db_path) if db_path else None
    if p is None or not p.is_file():
        raise FileNotFoundError('Öğrenci veritabanı bulunamadı.')
    con = sqlite3.connect(p.resolve().as_uri() + '?mode=ro', uri=True, timeout=3)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA query_only=ON')
    return con


def _cols(con, name: str) -> set[str]:
    if not re.fullmatch(r'[a-z_][a-z_0-9]*', name):
        return set()
    return {r['name'] for r in con.execute(f'PRAGMA table_info("{name}")')}


@dataclass(frozen=True)
class StudentListItem:
    id: int
    label: str


@dataclass(frozen=True)
class StudentTopicProgress:
    student_id: int
    student_label: str
    student_group: str
    exam: str
    track: str
    total: int
    completed: int
    in_progress: int
    unknown: int
    conflicts: int
    unmatched_records: int
    homework_total: int
    homework_completed: int
    homework_overdue: int
    notices: tuple[str, ...]

    @property
    def remaining_ceiling(self) -> int:
        """Conservative scenario: anything not explicitly marked done remains."""
        return max(0, self.total - self.completed)


def search_students(db_path, text: str = '', limit: int = 70) -> tuple[StudentListItem, ...]:
    """Search the local student register; bounded list, no hidden student fallback."""
    limit = min(100, max(1, int(limit)))
    try:
        con = _connection(db_path)
    except (OSError, sqlite3.Error):
        return ()
    try:
        cols = _cols(con, 'ogrenci')
        if not {'id', 'ad', 'soyad'} <= cols:
            return ()
        # Search is parameterized. Wildcards from input are escaped.
        needle = str(text or '').strip()[:80].replace('!', '!!').replace('%', '!%').replace('_', '!_')
        # Use id as a stable identity; students with identical names are distinct.
        select_group = 'ana_grup' if 'ana_grup' in cols else "'' AS ana_grup"
        rows = con.execute(f'''SELECT id,ad,soyad,{select_group} FROM ogrenci
            WHERE (? = '' OR (COALESCE(ad,'') || ' ' || COALESCE(soyad,'')) LIKE ? ESCAPE '!')
            ORDER BY ad COLLATE NOCASE, soyad COLLATE NOCASE, id LIMIT ?''',
                           (needle, '%' + needle + '%', limit)).fetchall()
        return tuple(StudentListItem(int(r['id']),
                    f"{str(r['ad'] or '').strip()} {str(r['soyad'] or '').strip()} · "
                    f"{str(r['ana_grup'] or 'Grup belirtilmemiş').strip()} (#{r['id']})") for r in rows)
    except (sqlite3.Error, ValueError):
        return ()
    finally:
        con.close()


def _read_homework(con, student_id: int, today: date) -> tuple[int, int, int]:
    """Reuse the existing deduplication bridge; failures do not block topic progress."""
    try:
        from services.coach_evidence_v5 import _assignment_rows, DONE
        rows, _ = _assignment_rows(con, student_id)
        return (len(rows), sum(1 for r in rows if r['durum'] in DONE),
                sum(1 for r in rows if r['durum'] not in DONE and r['due'] and r['due'] < today))
    except (ValueError, sqlite3.Error, KeyError, TypeError, ImportError):
        return (0, 0, 0)


def read_student_progress(db_path, student_id: int, exam: str, track: str, *,
                          as_of: Optional[date] = None) -> StudentTopicProgress:
    """Exact catalog match: status=4 is teacher-marked 'exam ready', not proof of mastery.

    Conflicting book-specific statuses invalidate a 'completed' inference.
    Silent cross-subject / fuzzy / empty-topic matches are forbidden.
    """
    exam = str(exam or '').upper()
    if exam not in TRACK_TABLES or track not in TRACK_TABLES[exam]:
        raise ValueError('Geçersiz sınav veya alan seçimi.')
    if not isinstance(student_id, int) or student_id < 1:
        raise ValueError('Geçerli bir öğrenci seçin.')
    today = as_of or date.today()
    with closing(_connection(db_path)) as con:
        con.execute("BEGIN")
        required = {'id', 'ad', 'soyad'}
        if not required <= _cols(con, 'ogrenci'):
            raise ValueError('Öğrenci tablosu eksik.')
        group_col = 'ana_grup' if 'ana_grup' in _cols(con, 'ogrenci') else "'' AS ana_grup"
        subgroup_col = 'alt_grup' if 'alt_grup' in _cols(con, 'ogrenci') else "'' AS alt_grup"
        s = con.execute(f'SELECT id,ad,soyad,{group_col},{subgroup_col} FROM ogrenci WHERE id=?',
                        (student_id,)).fetchone()
        if s is None:
            raise ValueError('Öğrenci bulunamadı; başka öğrencinin verisi kullanılmayacak.')
        group, subgroup = str(s['ana_grup'] or ''), str(s['alt_grup'] or '')
        label = ' '.join(x for x in (str(s['ad'] or '').strip(), str(s['soyad'] or '').strip()) if x)

        missing = []
        keys: set[tuple[str, str]] = set()
        # Coaching module includes group and student additions to the default curriculum.
        from services.coaching_curriculum_bridge_v41 import read_scoped_topics
        for course in TRACK_TABLES[exam][track]:
            if 'konu' not in _cols(con, course):
                missing.append(COURSE_NAMES.get(course, course))
                continue
            topics = read_scoped_topics(con, course, student_id=student_id,
                                        main_group=group, sub_group=subgroup)
            for topic in topics:
                if _norm(topic):
                    keys.add((course, _norm(topic)))
        # Records in the same student + course + normalized title are aggregated
        # across books. 4 is only counted if EVERY observed record says 4.
        statuses: dict[tuple[str, str], list[object]] = {}
        unmatched = 0
        coach_cols = _cols(con, 'koc_konu_takip')
        if {'ogrenci_id', 'ders_adi', 'konu_adi', 'durum'} <= coach_cols:
            rows = con.execute('SELECT ders_adi,konu_adi,durum FROM koc_konu_takip WHERE ogrenci_id=?',
                               (student_id,)).fetchall()
            allowed = set(TRACK_TABLES[exam][track])
            for r in rows:
                course = _ALIAS_LOOKUP.get(_norm(r['ders_adi']))
                topic = _norm(r['konu_adi'])
                if course is None or course not in allowed:
                    continue
                key = course, topic
                if key not in keys:
                    unmatched += 1
                    continue
                statuses.setdefault(key, []).append(r['durum'])
        completed = 0
        conflicts = 0
        in_progress = 0
        for values in statuses.values():
            try:
                ready = [int(s) == 4 for s in values]
            except (ValueError, TypeError):
                in_progress += 1
                continue
            if all(ready):
                completed += 1
            else:
                in_progress += 1
                if any(ready):
                    conflicts += 1
        unknown = len(keys) - len(statuses)
        hw_total, hw_done, hw_overdue = _read_homework(con, student_id, today)
        notices = ['Tamamlandı = Koçlukta öğretmenin durum 4 işaretlemesi; bağımsız sınav başarısı kanıtı değildir.',
                   'Ödev bitişi tamamlanan konuya eklenmez. Kayıtsız başlıklar temkinli biçimde çalışılacak kabul edilir.']
        if unknown:
            notices.append(f'{unknown} başlık için bu öğrenciye ait eşleşen Koçluk durumu bulunamadı.')
        if conflicts:
            notices.append(f'{conflicts} başlıkta birden fazla kitap/kayıt durumu çelişiyor; tamamlandı sayılmadı.')
        if unmatched:
            notices.append(f'{unmatched} Koçluk kaydı katalogla birebir eşleşmedi; otomatik aktarılmadı.')
        if missing:
            notices.append('Eksik müfredat tabloları: ' + ', '.join(missing) + '. Toplam kısmi olabilir.')
        if exam == 'YKS':
            notices.append('TYT/AYT birleşik derslerde kapsam ayrımı kesin değildir; sonuç resmî konu toplamı değildir.')
        if exam == 'YKS' and 'YDT' in track:
            notices.append('YDT yabancı dil çalışmaları mevcut havuzda kapsam dışıdır.')
        is_lgs_group = 'lgs' in _norm(group + ' ' + subgroup) or '8' in subgroup
        if exam == 'LGS' and not is_lgs_group:
            notices.append('Öğrenci grubunun LGS kapsamına uygunluğunu kontrol edin.')
        if exam in ('YKS', 'MSÜ') and is_lgs_group:
            notices.append('Öğrenci grubu LGS görünüyor. YKS/MSÜ alan seçimini kontrol edin.')
        return StudentTopicProgress(student_id, label or f'#{student_id}', group, exam, track,
                                   len(keys), completed, in_progress, unknown, conflicts, unmatched,
                                   hw_total, hw_done, hw_overdue, tuple(notices))
