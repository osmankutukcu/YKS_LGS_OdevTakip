# -*- coding: utf-8 -*-
"""V24.5 — Hedef analizinin yerel kaynak güvenilirliği (salt okunur).

Bu araç başarı/yerleşme olasılığı hesaplamaz; öğrenci verisi dışarı göndermez,
veritabanını oluşturmaz veya değiştirmez. Kaynak kataloglarının 'resmî'
olduğu sonucunu çıkarmaz. Sadece yerel verinin şema/kimlik/kanıt durumunu raporlar.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import quote
import json
import math
import sqlite3

from .program_catalog_v242 import PROVENANCE
from .source_freshness_v241 import read_cache


@dataclass(frozen=True)
class AuditFinding:
    level: str  # critical, warning, info
    code: str
    detail: str


@dataclass(frozen=True)
class GoalAudit:
    student_id: int
    checked_on: date
    target_set: bool
    trend_rows: int
    public_catalog_rows: int
    findings: tuple[AuditFinding, ...]

    @property
    def has_blocker(self) -> bool:
        return any(f.level == 'critical' for f in self.findings)


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    # Tablo isimleri sabittir; dışarıdan SQL yapı taşı alınmaz.
    return {str(row[1]) for row in conn.execute(f'PRAGMA table_info({table})')}


def _open_readonly(path: Path):
    uri = 'file:' + quote(str(path.resolve()), safe='/') + '?mode=ro'
    conn = sqlite3.connect(uri, uri=True, timeout=3)
    conn.execute('PRAGMA query_only=ON')
    return conn


def audit_goal_sources(main_db: str | Path, student_id: int, *,
                       trend_db: str | Path | None = None,
                       catalog_db: str | Path | None = None,
                       source_cache: str | Path | None = None,
                       selected_year: Optional[int] = None,
                       today: date | None = None) -> GoalAudit:
    """Yalnızca seçilen öğrenci ve kamuya açık kaynakların durumunu denetler.

    Eksik isteğe bağlı kaynaklar için yeni dosya yaratmaz. Şema tanınmıyorsa
    sessizce boş veri varsayılmaz. Sonuçlar öğrenci adları içermez.
    """
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('Denetim için seçili ve geçerli öğrenci kimliği gerekli.')
    if selected_year is not None and (type(selected_year) is not int or
                                      not 2018 <= selected_year <= datetime.now(timezone.utc).year):
        raise ValueError('Kaynak yılı geçersiz.')
    today = today or date.today()
    findings: list[AuditFinding] = []

    def note(level: str, code: str, detail: str):
        findings.append(AuditFinding(level, code, detail))

    target_set = False
    main = Path(main_db)
    if not main.is_file():
        note('critical', 'MAIN_DB_MISSING', 'Öğrenci veritabanı bulunamadı; hiçbir dosya oluşturulmadı.')
    else:
        try:
            with closing(_open_readonly(main)) as con:
                cols = _columns(con, 'ogrenci')
                needed = {'id', 'hedef_bolum', 'hedef_tyt', 'hedef_ayt', 'hedef_lgs'}
                if not needed.issubset(cols):
                    note('critical', 'TARGET_SCHEMA', 'Hedef alanları eksik; veritabanı şeması eski veya uyumsuz.')
                else:
                    result = con.execute('''SELECT hedef_bolum,hedef_tyt,hedef_ayt,hedef_lgs
                                            FROM ogrenci WHERE id=?''', (student_id,)).fetchone()
                    if result is None:
                        note('critical', 'STUDENT_NOT_FOUND', 'Seçilen öğrenci kimliği veritabanında yok.')
                    else:
                        target_set = bool(str(result[0] or '').strip())
                        if not target_set:
                            note('info', 'TARGET_NOT_SET', 'Bu öğrenci için kayıtlı hedef yok.')
                        for value, bound, name in zip(result[1:], (120, 80, 90), ('TYT', 'AYT/YDT', 'LGS')):
                            try:
                                n = float(value or 0)
                                if not math.isfinite(n) or n < 0 or n > bound:
                                    raise ValueError('aralık dışında')
                            except (ValueError, TypeError):
                                note('warning', 'TARGET_INVALID', f'{name} hedef neti geçerli aralıkta değil; hesap için güvenilir sayılmamalı.')
        except (sqlite3.Error, OSError) as exc:
            note('critical', 'MAIN_DB_UNREADABLE', 'Öğrenci veritabanı salt okunur şekilde açılamadı.')

    trends = 0
    if trend_db is not None:
        path = Path(trend_db)
        if not path.is_file():
            note('info', 'TREND_MISSING', 'Öğrenciye özel deneme geçmişi dosyası henüz yok.')
        else:
            try:
                with closing(_open_readonly(path)) as con:
                    needed = {'student_id', 'd', 'exam', 'alan', 'payload', 'source_key'}
                    if not needed.issubset(_columns(con, 'deneme_student_v24')):
                        note('warning', 'TREND_SCHEMA', 'Öğrenciye özel deneme geçmişi şeması bulunamadı.')
                    else:
                        # Sadece seçilen öğrencinin en fazla 500 satırını inceler.
                        trends = int(con.execute('''SELECT count(*) FROM deneme_student_v24
                                                    WHERE student_id=?''',(student_id,)).fetchone()[0])
                        if trends > 500:
                            note('warning', 'TREND_LIMIT', '500 üzeri kayıt var; ayrıntılı kontrol ilk 500 kayıtla sınırlı.')
                        data = con.execute('''SELECT d, payload FROM deneme_student_v24
                                              WHERE student_id=? ORDER BY id DESC LIMIT 500''',
                                           (student_id,)).fetchall()
                        corrupt = 0
                        for day_str, payload in data:
                            try:
                                date.fromisoformat(day_str)
                                value = json.loads(payload)
                                if not isinstance(value, dict):
                                    raise ValueError('sonuç nesne değil')
                            except (ValueError, TypeError, json.JSONDecodeError):
                                corrupt += 1
                        if corrupt:
                            note('warning', 'TREND_CORRUPT', f'Seçilen öğrencinin {corrupt} deneme geçmişi satırı okunamıyor.')
                        if trends == 0:
                            note('info', 'TREND_EMPTY', 'Bu öğrenci için kişiye özel trend kaydı yok.')
            except (sqlite3.Error, OSError):
                note('warning', 'TREND_UNREADABLE', 'Deneme geçmişi salt okunur şekilde açılamadı.')

    catalogs = 0
    if catalog_db is not None:
        path = Path(catalog_db)
        if not path.is_file():
            note('info', 'CATALOG_MISSING', 'Kamuya açık program kataloğu henüz oluşturulmadı.')
        else:
            try:
                with closing(_open_readonly(path)) as con:
                    needed = {'year', 'program_code', 'source', 'payload', 'source_label'}
                    if not needed.issubset(_columns(con, 'program_reference_v242')):
                        note('warning', 'CATALOG_SCHEMA', 'Program katalog şeması bulunamadı.')
                    else:
                        if selected_year is None:
                            catalogs = int(con.execute('SELECT count(*) FROM program_reference_v242').fetchone()[0])
                        else:
                            catalogs = int(con.execute('''SELECT count(*) FROM program_reference_v242
                                                         WHERE year=?''', (selected_year,)).fetchone()[0])
                        query = '''SELECT year,program_code,source,payload,source_label FROM program_reference_v242'''
                        params: tuple = ()
                        if selected_year is not None:
                            query += ' WHERE year=?'
                            params = (selected_year,)
                        query += ' ORDER BY year,program_code LIMIT 500'
                        mismatches = 0
                        for year, code, source, payload, label in con.execute(query, params):
                            try:
                                row = json.loads(payload)
                                if not isinstance(row, dict) or row.get('program_code') != code or row.get('year') != year or row.get('source') != source:
                                    mismatches += 1
                            except (ValueError, TypeError, json.JSONDecodeError):
                                mismatches += 1
                            if label != PROVENANCE:
                                mismatches += 1
                        if mismatches:
                            note('warning', 'CATALOG_MISMATCH', f'{mismatches} katalog kayıt alanı veya kaynak etiketi tutarsız.')
                        if catalogs > 500:
                            note('info', 'CATALOG_LIMIT', 'Katalogdaki ilk 500 satırın alanları kontrol edildi.')
                        if catalogs:
                            note('info', 'CATALOG_UNVERIFIED', 'Katalogdaki veriler öğretmen kontrollüdür; bağımsız resmî doğrulama yapılmış sayılmaz.')
                        else:
                            note('info', 'CATALOG_EMPTY', 'Seçili yıl için kataloğa alınmış program verisi yok.')
            except (sqlite3.Error, OSError):
                note('warning', 'CATALOG_UNREADABLE', 'Program kataloğu salt okunur şekilde açılamadı.')

    if source_cache is not None:
        path = Path(source_cache)
        if path.is_file():
            for src in ('YKS', 'LGS'):
                snapshot = read_cache(path, src)
                if snapshot:
                    try:
                        checked = datetime.fromisoformat(snapshot['checked_at']).date()
                        if (today - checked).days > 30:
                            note('warning', 'SOURCE_STALE', f'{src} sayfasının son kontrolü 30 günden eski.')
                        if selected_year is not None and src == 'YKS' and snapshot['reference_year'] != selected_year:
                            note('info', 'SOURCE_YEAR_DIFF', 'Kaynak sayfasının yayın yılı seçilen analiz yılıyla eşleşmiyor veya bilinmiyor.')
                    except (ValueError, TypeError, KeyError):
                        note('warning', 'SOURCE_DATE', f'{src} kaynak kontrol tarihi okunamadı.')
                else:
                    note('info', 'SOURCE_UNCONFIRMED', f'{src} için doğrulanabilir son kontrol bulunamadı.')
        else:
            note('info', 'SOURCE_CACHE_MISSING', 'Resmî sayfa kontrol önbelleği henüz yok.')

    return GoalAudit(student_id, today, target_set, trends, catalogs, tuple(findings))


def render_goal_audit(report: GoalAudit) -> str:
    """Öğrencinin kişisel adı/neti veya katalog satırı ifşa etmeyen kısa rapor."""
    lines = ['HEDEF ANALİZİ – VERİ GÜVENİLİRLİĞİ DENETİMİ',
             f'Kontrol: {report.checked_on.isoformat()}',
             f'Öğrenci ID: {report.student_id}',
             f'Kayıtlı hedef: {"Var" if report.target_set else "Yok"}',
             f'Kişiye özel trend kayıt sayısı: {report.trend_rows}',
             f'Program katalog satırı (seçilen yıl varsa filtrelenir): {report.public_catalog_rows}',
             '', 'BULGULAR']
    if report.findings:
        names = {'critical':'KRİTİK', 'warning':'UYARI', 'info':'BİLGİ'}
        lines.extend(f'• {names.get(f.level,"BİLGİ")} [{f.code}]: {f.detail}' for f in report.findings)
    else:
        lines.append('• Kontrol edilen alanlarda teknik tutarsızlık tespit edilmedi.')
    lines += ['', 'Bu denetim kaynak dosyalarını değiştirmez ve internet sorgusu yapmaz.',
              'Tutarlı kayıt, yerleşme olasılığı veya resmî verinin doğruluğu anlamına gelmez.']
    return '\n'.join(lines)
