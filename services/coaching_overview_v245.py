# -*- coding: utf-8 -*-
"""V24.5: Read-only, source-labelled overview for the seven existing coaching tabs.

No DDL/DML, network, automatic homework, psychometric scores or inferred mastery.
Missing/broken sources are shown as unavailable, not silently reported as zero.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import sqlite3
from typing import Optional


@dataclass(frozen=True)
class Overview:
    student_id: int
    week_start: str
    heading: str
    line_one: str
    line_two: str
    recommendation: str
    target_tab: str | None
    provenance: str
    alerts: tuple[str, ...] = ()


def _exists(con: sqlite3.Connection, table: str) -> bool:
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def _valid_week(value: str) -> str:
    try:
        d = date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError('Hafta tarihi YYYY-AA-GG olmalı.') from None
    if d.weekday() != 0:
        raise ValueError('Hafta başlangıcı pazartesi olmalı.')
    return d.isoformat()


def _plan(con: sqlite3.Connection, student_id: int, week: str):
    if not _exists(con, 'koc_plan') or not _exists(con, 'koc_hedef'):
        return 'Plan verisi okunamıyor', None, None, ('Haftalık plan tabloları bulunamadı.',)
    plans = con.execute('SELECT id FROM koc_plan WHERE ogrenci_id=? AND baslangic_tarihi=? ORDER BY id',
                        (student_id, week)).fetchall()
    if len(plans) > 1:
        return 'Haftalık plan çakışıyor', None, None, ('Bu öğrenci ve hafta için birden çok plan var; kayıtlar birleştirilmedi.',)
    if not plans:
        return 'Bu hafta plan yok', None, None, ()
    pid = int(plans[0][0])
    row = con.execute('SELECT COUNT(*), COALESCE(SUM(hedef_soru),0), COALESCE(SUM(cozulen_soru),0) '
                      'FROM koc_hedef WHERE plan_id=?', (pid,)).fetchone()
    count, target, solved = (int(row[0]), int(row[1]), int(row[2]))
    if any(x < 0 for x in (target, solved)):
        return 'Haftalık hedef kaydı incelenmeli', pid, count, ('Negatif soru kayıtları görüldü.',)
    return f'Haftalık hedef: {solved}/{target} soru ({count} ders)', pid, count, ()


def _homework(con: sqlite3.Connection, student_id: int, today: date):
    if not (_exists(con, 'odev') or _exists(con, 'odev_satir')):
        return 'Ana ödev verisi okunamıyor', None, ('Ana ödev tabloları eksik.',)
    try:
        # Reuse the existing V5 mirrored-row handling; do not add raw legacy and new rows.
        from services.coach_evidence_v5 import _assignment_rows, DONE
        rows, coverage = _assignment_rows(con, student_id)
        completed = sum(r['durum'] in DONE for r in rows)
        open_rows = [r for r in rows if r['durum'] not in DONE]
        overdue = sum(bool(r['due'] and r['due'] < today) for r in open_rows)
        notes = (f"{coverage['mirrored']} eşleşen eski/yeni ödev satırı ikinci kez sayılmadı.",) if coverage['mirrored'] else ()
        return f'Ana ödev: {len(open_rows)} açık / {completed} tamam', overdue, notes
    except (sqlite3.Error, ValueError, KeyError, TypeError, ImportError) as exc:
        return 'Ana ödev verisi doğrulanamadı', None, (f'Ödev kaynağı: {type(exc).__name__}',)


def _program(con, pid):
    if pid is None:
        return 'Program: plan yok', False, ()
    if not _exists(con, 'koc_program'):
        return 'Program verisi okunamıyor', False, ('Ders programı tablosu bulunamadı.',)
    n = con.execute('SELECT COUNT(*) FROM koc_program WHERE plan_id=?', (pid,)).fetchone()[0]
    return f'Program: {n} kayıtlı blok', bool(n), ()


def _topics(con, sid):
    if not _exists(con, 'koc_konu_takip'):
        return 'Konu kaydı okunamıyor', ()
    # Count distinct teacher-labelled topics; book-specific rows must not inflate topic count.
    cols = {r[1] for r in con.execute('PRAGMA table_info(koc_konu_takip)')}
    if not {'ogrenci_id', 'ders_adi', 'konu_adi', 'durum'} <= cols:
        return 'Konu kaydı doğrulanamadı', ('Konu tablosu alanları eksik.',)
    row = con.execute('SELECT COUNT(*) FROM (SELECT ders_adi,konu_adi FROM koc_konu_takip '
                      'WHERE ogrenci_id=? AND durum>0 GROUP BY ders_adi,konu_adi)', (sid,)).fetchone()
    return f'Konu takibi: {row[0]} öğretmen işareti', ()


def _surveys(con, sid):
    # Never expose sensitive questionnaires in top-level previews.
    if not _exists(con, 'ogrenci_anket'):
        return 'Anket verisi okunamıyor', ('Anket tablosu bulunamadı.',)
    try:
        from services.survey_evidence_v7 import read_survey_evidence
        evidence = read_survey_evidence(con, sid)
        visible = sum(r.code not in {'exam_anxiety', 'sleep_energy'} for r in evidence.records)
        return f'Anket: {visible} çalışma kaydı', (('Bazı anket yanıtları doğrulanamadı.',) if evidence.malformed else ())
    except (sqlite3.Error, ValueError, KeyError, TypeError, ImportError):
        return 'Anket verisi okunamıyor', ('Anket kaynağı incelenmeli.',)


def _notes(con, sid):
    if not _exists(con, 'koc_plan'):
        return 'Görüşme notu okunamıyor', ()
    try:
        from services.coaching_safety_v244 import note_history
        items = note_history(con, sid)
        # Entries are *notes*, not verified meetings.
        return f'Görüşme notu: {len(items)} kayıt', ()
    except (sqlite3.Error, ValueError, KeyError, TypeError):
        return 'Görüşme notu doğrulanamadı', ('Görüşme kaynağı incelenmeli.',)


def _exams(con, sid):
    # Read both existing schemas but never sum potentially mirrored result counts.
    if not (_exists(con, 'deneme') or (_exists(con, 'denemeler') and _exists(con, 'deneme_sonuclari'))):
        return 'Deneme verisi okunamıyor', ('Deneme kaynak tabloları bulunamadı.',)
    recent = []
    try:
        if _exists(con, 'denemeler') and _exists(con, 'deneme_sonuclari'):
            cols = {r[1] for r in con.execute('PRAGMA table_info(deneme_sonuclari)')}
            ecol = {r[1] for r in con.execute('PRAGMA table_info(denemeler)')}
            if {'ogrenci_id', 'deneme_id'} <= cols and {'id', 'tarih'} <= ecol:
                row = con.execute('SELECT MAX(d.tarih) FROM deneme_sonuclari s '
                                  'JOIN denemeler d ON d.id=s.deneme_id WHERE s.ogrenci_id=?', (sid,)).fetchone()
                if row and row[0]: recent.append(('Yeni', str(row[0])[:10]))
        if _exists(con, 'deneme'):
            cols = {r[1] for r in con.execute('PRAGMA table_info(deneme)')}
            if {'ogrenci_id', 'tarih'} <= cols:
                row = con.execute('SELECT MAX(tarih) FROM deneme WHERE ogrenci_id=?',(sid,)).fetchone()
                if row and row[0]: recent.append(('Eski', str(row[0])[:10]))
    except sqlite3.Error:
        return 'Deneme verisi doğrulanamadı', ('Deneme kaynak yapısı incelenmeli.',)
    if not recent:
        return 'Deneme: sonuç kaydı görünmüyor', ()
    # Source only, no unsupported net/academic success statement.
    ordered = sorted(recent,key=lambda x:x[1],reverse=True)
    prefix = 'Deneme: son kayıt ' + ordered[0][1]
    if len(recent)>1:
        prefix += ' (iki kayıt biçimi)'
    return prefix, ()


def read_coaching_overview(con: sqlite3.Connection, student_id: int, week_start: str,
                           *, today: Optional[date] = None) -> Overview:
    """Pure SELECT-only overview; selected student and week mandatory."""
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('Geçerli öğrenci seçilmedi.')
    week = _valid_week(week_start)
    today = today or date.today()
    if not _exists(con, 'ogrenci'):
        raise ValueError('Öğrenci tablosu yok.')
    student = con.execute('SELECT id,ad,soyad FROM ogrenci WHERE id=?',(student_id,)).fetchone()
    if student is None:
        raise ValueError('Seçilen öğrenci bulunamadı.')
    name = ' '.join(str(x or '').strip() for x in (student[1], student[2])).strip()
    alerts = []
    plan, pid, goal_count, notes = _plan(con, student_id, week)
    alerts.extend(notes)
    hw, overdue, notes = _homework(con, student_id, today)
    alerts.extend(notes)
    program, scheduled, notes = _program(con, pid)
    alerts.extend(notes)
    topic, notes = _topics(con, student_id)
    alerts.extend(notes)
    survey, notes = _surveys(con, student_id)
    alerts.extend(notes)
    meeting, notes = _notes(con, student_id)
    alerts.extend(notes)
    exam, notes = _exams(con, student_id)
    alerts.extend(notes)
    if 'çakış' in plan:
        action, tab = 'Haftalık planda çakışma var; hedefleri inceleyin.', 'plan'
    elif overdue is not None and overdue > 0:
        action, tab = f'{overdue} gecikmiş açık ödev var; kontrol kayıtlarını doğrulayın.', 'student360'
    elif plan == 'Bu hafta plan yok':
        action, tab = 'Bu hafta için hedef planı oluşturabilirsiniz.', 'plan'
    elif pid is not None and scheduled is False:
        action, tab = 'Bu haftanın çalışma programı henüz kaydedilmemiş; inceleyebilirsiniz.', 'schedule'
    elif goal_count is None or overdue is None:
        action, tab = 'Bazı kaynaklar okunamadı; verileri ilgili sekmeden kontrol edin.', 'student360'
    else:
        action, tab = 'Acil işlem tespit edilmedi. Ölçülmüş öğrenmeyi denemelerden ayrıca inceleyin.', 'analysis'
    return Overview(student_id, week, f'{name} · {week} haftası',
                    f'{plan}    |    {hw}    |    {program}',
                    f'{exam}    |    {topic}    |    {survey}    |    {meeting}',
                    action, tab,
                    'Kaynaklar: Haftalık koçluk planı (seçili hafta); ana ödev (tüm açık/güncel durum); '
                    'denemeler (son kayıt); konu işareti, anket ve not arşivi (seçili öğrenci). '
                    'Ödev tamamlanması öğrenme veya sınav başarısı değildir.',
                    tuple(dict.fromkeys(alerts)))
