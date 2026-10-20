# -*- coding: utf-8 -*-
"""V3557: deterministik, salt okunur öğrenci-bazlı haftalık sınav çalışma taslağı.

Bu modül öğrenciye ödev ATAMAZ veya konu durumunu değiştirmez. Her başlık
öğretmen tarafından doğrulanması gereken bir öneridir; resmî konu listesi değildir.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from contextlib import closing
from math import floor
import sqlite3

from services.student_exam_bridge_v3556 import _connection, _cols, _norm, _ALIAS_LOOKUP
from services.exam_planning_v3555 import TRACK_TABLES, COURSE_NAMES, read_calendar
from services.coaching_curriculum_bridge_v41 import read_scoped_topics


@dataclass(frozen=True)
class TopicDraft:
    course: str
    course_label: str
    topic: str
    evidence: str  # 'devam', 'çelişkili', 'durum bilinmiyor'


@dataclass(frozen=True)
class WeekDraft:
    week_number: int
    start: date
    end: date
    items: tuple[TopicDraft, ...]


@dataclass(frozen=True)
class WeeklyPlanDraft:
    student_id: int
    student_label: str
    exam: str
    track: str
    start: date
    study_end: date
    exam_date: date
    catalog_total: int
    teacher_marked_ready: int
    candidates: int
    planned: int
    unscheduled: int
    weeks: tuple[WeekDraft, ...]
    unplanned_items: tuple[TopicDraft, ...]
    warnings: tuple[str, ...]

    def to_text(self) -> str:
        lines = [f'{self.exam} — Öğrenciye Özel Haftalık Taslak (V3557)',
                 f'Öğrenci: {self.student_label} (#{self.student_id})',
                 f'Alan: {self.track}',
                 f'Kapsam: {self.catalog_total} yerel başlık; öğretmen işaretli hazır: {self.teacher_marked_ready}',
                 f'Çalışma önerisi: {self.planned} başlık; plan dışında kalan: {self.unscheduled}',
                 f'Çalışma aralığı: {self.start:%d.%m.%Y} – {self.study_end - timedelta(days=1):%d.%m.%Y}'
                 if self.study_end > self.start else 'Çalışma dönemi: ayrılabilir gün yok',
                 'UYARI: Taslaktır. Kayıt, ödev atama veya öğrenme kanıtı oluşturmaz.', '']
        for week in self.weeks:
            lines.append(f'{week.week_number}. hafta ({week.start:%d.%m.%Y} – {week.end:%d.%m.%Y})')
            for item in week.items:
                lines.append(f'  • {item.course_label} / {item.topic}  [{item.evidence}]')
            lines.append('')
        if self.unplanned_items:
            lines += [f'Plan dışında kalan {len(self.unplanned_items)} başlık (tempo / süre yetersiz):']
            lines += [f'  • {i.course_label} / {i.topic}  [{i.evidence}]' for i in self.unplanned_items]
        lines += ['', 'Kontrol notları:'] + ['- '+w for w in self.warnings]
        return '\n'.join(lines)


def _read_snapshot(db_path, student_id: int, exam: str, track: str):
    """Bir SQLite okuma anında kimlik + katalog + koçluk kanıtlarını eşleştir."""
    if type(student_id) is not int or student_id < 1:
        raise ValueError('Öğrenci kimliği geçersiz.')
    exam = str(exam or '').upper().strip()
    courses = TRACK_TABLES.get(exam, {}).get(track)
    if courses is None:
        raise ValueError('Sınav / alan seçimi geçersiz.')
    with closing(_connection(db_path)) as con:
        con.execute('BEGIN')
        cols = _cols(con, 'ogrenci')
        if not {'id','ad','soyad'} <= cols:
            raise ValueError('Öğrenci dizini bulunamadı.')
        group_expr = 'ana_grup' if 'ana_grup' in cols else "'' AS ana_grup"
        subgroup_expr = 'alt_grup' if 'alt_grup' in cols else "'' AS alt_grup"
        s = con.execute(f'SELECT id, ad, soyad, {group_expr}, {subgroup_expr} FROM ogrenci WHERE id=?',
                        (student_id,)).fetchone()
        if s is None:
            raise ValueError('Öğrenci bulunamadı; başka bir öğrenciye geçilmedi.')
        label = ' '.join(str(s[k] or '').strip() for k in ('ad','soyad')).strip() or str(student_id)
        group = str(s['ana_grup'] or '')
        subgroup = str(s['alt_grup'] or '')
        order = []
        missing = []
        for course in courses:
            if 'konu' not in _cols(con, course):
                missing.append(COURSE_NAMES.get(course, course))
                continue
            seen = set()
            for topic in read_scoped_topics(con, course, student_id=student_id,
                                             main_group=group, sub_group=subgroup):
                norm_topic = _norm(topic)
                if norm_topic and norm_topic not in seen:
                    order.append(((course, norm_topic), str(topic).strip()))
                    seen.add(norm_topic)
        course_set = set(courses)
        known_keys = {key for key, _ in order}
        states = {}
        unmatched = 0
        if {'ogrenci_id', 'ders_adi', 'konu_adi', 'durum'} <= _cols(con, 'koc_konu_takip'):
            for row in con.execute('SELECT ders_adi,konu_adi,durum FROM koc_konu_takip WHERE ogrenci_id=?',
                                   (student_id,)):
                code = _ALIAS_LOOKUP.get(_norm(row['ders_adi']))
                if code not in course_set:
                    continue
                key = (code, _norm(row['konu_adi']))
                if key not in known_keys:
                    unmatched += 1
                    continue
                states.setdefault(key, []).append(row['durum'])
        ready = 0
        # Unknown is considered a *study possibility*, not an achieved or failed topic.
        selected = []
        for key, title in order:
            values = states.get(key, [])
            flags = []
            for value in values:
                try:
                    flags.append(int(value) == 4)
                except (ValueError, TypeError, OverflowError):
                    flags.append(False)
            if flags and all(flags):
                ready += 1
                continue
            if flags and any(flags):
                evidence = 'çelişkili — öğretmen doğrulasın'
            elif flags:
                evidence = 'devam / tamamlanmadı'
            else:
                evidence = 'durum bilinmiyor'
            selected.append(TopicDraft(key[0], COURSE_NAMES.get(key[0], key[0]), title, evidence))
        notes = [
            'Konu başlıkları yerel ders havuzundan alınmıştır; resmî tekil sınav konu sayısı değildir.',
            '“Hazır” yalnızca Koçluk durum=4 işaretlemesidir, sınav başarısı kanıtı değildir.',
            'Ödevin yapılması konu tamamlanmış sayılmaz. Bilinmeyen durumlar çalışma taslağına alınır.',
        ]
        if missing:
            notes.append('Müfredat tabloları eksik: '+', '.join(missing)+'; taslak kısmi olabilir.')
        if unmatched:
            notes.append(f'{unmatched} Koçluk kaydı başlık/dersle birebir eşleşmedi; kullanılmadı.')
        if exam == 'YKS':
            notes.append('TYT / AYT birleşik derslerde kapsam ayrımı kesin olmayabilir.')
        if exam == 'YKS' and 'YDT' in track:
            notes.append('YDT yabancı dil kapsamı mevcut veri havuzunda tam temsil edilmeyebilir.')
        return label, len(order), ready, tuple(selected), notes


def build_weekly_plan(db_path, student_id: int, exam: str, track: str, *,
                      remaining_days: int, weekly_topics: int, buffer_days: int,
                      revision_days: int, as_of: date | None = None) -> WeeklyPlanDraft:
    """Gözden geçirme için üretilen taslak. Hiçbir SQL INSERT/UPDATE/DELETE yok.

    Haftalık kontenjanı son kısmi haftaya tam aktarmayarak aşırı yük vaadinden
    kaçınır. Bir dersin bütün konularını arka arkaya dizmek yerine dersler arasında
    dengeli rotasyon yapar; kesin bilimsel optimum olduğu iddia edilmez.
    """
    if any(type(x) is not int for x in (remaining_days, weekly_topics, buffer_days, revision_days)):
        raise ValueError('Gün ve tempo değerleri tam sayı olmalı.')
    if not 0 <= remaining_days <= 1500 or not 1 <= weekly_topics <= 40:
        raise ValueError('Süre veya haftalık kapasite geçersiz.')
    if not 0 <= buffer_days <= 365 or not 0 <= revision_days <= 365:
        raise ValueError('Aksama / tekrar süresi geçersiz.')
    exam = str(exam or '').upper().strip()
    start = as_of or date.today()
    if not isinstance(start, date):
        raise TypeError('Başlangıç günü geçersiz.')
    label, catalog_total, ready, candidates, warnings = _read_snapshot(db_path, student_id, exam, track)
    exam_date = start + timedelta(days=remaining_days)
    study_days = max(0, remaining_days - buffer_days - revision_days)
    study_end = start + timedelta(days=study_days)  # exclusive
    slots = []
    for n, offset in enumerate(range(0, study_days, 7), start=1):
        length = min(7, study_days - offset)
        count = weekly_topics if length == 7 else floor(weekly_topics * length / 7)
        slots.append((n, start + timedelta(days=offset),
                      start + timedelta(days=offset + length - 1), count))
    # Course round-robin, initial class order preserved, with started/conflict items
    # first within each course. Balanced across weeks, deterministic across runs.
    priority = {'çelişkili — öğretmen doğrulasın':0, 'devam / tamamlanmadı':1,
                'durum bilinmiyor':2}
    from collections import deque
    queues = {course: deque(sorted((it for it in candidates if it.course == course),
                                  key=lambda it: priority[it.evidence]))
              for course in TRACK_TABLES[exam][track]}
    scheduled = []
    weeks = []
    course_codes = list(queues)
    idx = 0
    for week_no, week_start, week_end, capacity in slots:
        current = []
        while len(current) < capacity and any(queues.values()):
            code = course_codes[idx % len(course_codes)]
            idx += 1
            if queues[code]:
                current.append(queues[code].popleft())
        if current:
            weeks.append(WeekDraft(week_no, week_start, week_end, tuple(current)))
            scheduled.extend(current)
    # Keep deterministic order for unscheduled topics: group and priority still visible.
    rest = tuple(it for code in course_codes for it in queues[code])
    if rest:
        warnings.append(f'{len(rest)} başlık mevcut haftalık tempo ve çalışma dönemi içine sığmadı. '
                        'Öğretmen süre/tempo düzenlemeli; otomatik aşırı yükleme yapılmadı.')
    if study_days == 0:
        warnings.append('Deneme kampı ve aksama payı sonrası yeni konular için süre kalmadı.')
    calendar = read_calendar(today=start).get(exam, {})
    if calendar.get('status') != 'official':
        warnings.append('Sınav tarihi resmî olarak doğrulanmış değildir; takvim bir çalışma senaryosudur.')
    if calendar.get('days') is not None and calendar.get('days') != remaining_days:
        warnings.append('Simülasyondaki kalan gün sayısı, takvimdeki senaryo günüyle farklı; lütfen kontrol edin.')
    warnings.append('Bu taslak Koçluk kanıtlarına göre hazırlanır; simülasyondaki manuel kalan başlık kaydırıcısını kullanmaz.')
    warnings.append('Bu plan sadece önizlemedir; herhangi bir sisteme kaydedilmez veya öğrenciye gönderilmez.')
    return WeeklyPlanDraft(student_id, label, exam, track, start, study_end, exam_date,
                           catalog_total, ready, len(candidates), len(scheduled), len(rest),
                           tuple(weeks), rest, tuple(warnings))
