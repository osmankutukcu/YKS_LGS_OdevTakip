# -*- coding: utf-8 -*-
"""V3.5.55: Salt okunur ve kanıt düzeyi belirtilen sınav planlama verileri.

Konu başlığı sayısı ÖSYM/MEB tarafından yayımlanan sabit bir 'resmî konu sayısı'
DEĞİLDİR. Yerel müfredat tablosundaki benzersiz, boş olmayan kayıtları sayar.
Eski koçluk / ödev kayıtlarına hiçbir yazma işlemi yapmaz.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import json
import re
import sqlite3

# Dersleri bağlama göre seçiyoruz. Fizik / Kimya / Biyoloji vb. birleşik
# tablolardır; TYT / AYT ayrımları bu şemada garanti edilmez.
TRACK_TABLES = {
    'YKS': {
        'Sayısal (TYT + AYT)': ('tyt_matematik', 'problemler', 'ayt_matematik', 'geometri', 'fizik', 'kimya', 'biyoloji', 'turkce', 'paragraf'),
        'Eşit Ağırlık (TYT + AYT)': ('tyt_matematik', 'problemler', 'ayt_matematik', 'geometri', 'turkce', 'paragraf', 'edebiyat', 'tarih', 'cografya'),
        'Sözel (TYT + AYT)': ('turkce', 'paragraf', 'edebiyat', 'tarih', 'cografya', 'felsefe'),
        'TYT Odaklı': ('tyt_matematik', 'problemler', 'turkce', 'paragraf', 'fizik', 'kimya', 'biyoloji', 'tarih', 'cografya', 'felsefe'),
        'YDT / Dil (TYT + Yabancı Dil)': ('tyt_matematik', 'turkce', 'paragraf', 'tarih', 'cografya'),
    },
    'MSÜ': {'MSÜ / TYT Çalışma Havuzu': ('tyt_matematik', 'problemler', 'turkce', 'paragraf', 'fizik', 'kimya', 'biyoloji', 'tarih', 'cografya', 'felsefe')},
    'LGS': {'8. Sınıf Ders Havuzu': ('lgs_matematik', 'lgs_fen', 'lgs_turkce', 'lgs_inkilap', 'lgs_dinkulturu', 'lgs_ingilizce')},
}
COURSE_NAMES = {
 'tyt_matematik':'TYT Matematik', 'problemler':'Problemler', 'ayt_matematik':'AYT Matematik',
 'geometri':'Geometri', 'fizik':'Fizik (TYT/AYT karma)', 'kimya':'Kimya (TYT/AYT karma)',
 'biyoloji':'Biyoloji (TYT/AYT karma)', 'turkce':'Türkçe', 'paragraf':'Paragraf',
 'edebiyat':'Edebiyat', 'tarih':'Tarih', 'cografya':'Coğrafya', 'felsefe':'Felsefe',
 'lgs_matematik':'LGS Matematik', 'lgs_fen':'LGS Fen', 'lgs_turkce':'LGS Türkçe',
 'lgs_inkilap':'LGS İnkılap', 'lgs_dinkulturu':'LGS Din', 'lgs_ingilizce':'LGS İngilizce',
}

@dataclass(frozen=True)
class CourseCount:
    code: str
    title: str
    count: int

@dataclass(frozen=True)
class TrackCount:
    total: int
    courses: tuple[CourseCount, ...]
    missing: tuple[str, ...]
    note: str


def read_track_counts(db_path, exam: str) -> dict[str, TrackCount]:
    """Verilen SQLite dosyasını *read-only* aç; kayıt bulunamazsa sayı UYDURMA."""
    result = {}
    groups = TRACK_TABLES.get(exam, {})
    path = Path(db_path) if db_path else None
    if path is None or not path.is_file():
        return {key: TrackCount(0, (), tuple(codes), 'Yerel müfredat veritabanına erişilemiyor.') for key, codes in groups.items()}
    # URI kodlama özel karakterli Windows / macOS yolları için pathlib sağlar.
    try:
        con = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=2)
    except (OSError, sqlite3.Error):
        return {key: TrackCount(0, (), tuple(codes), 'Veritabanı salt okunur açılamadı.') for key, codes in groups.items()}
    try:
        known = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for name, courses in groups.items():
            counts, missing = [], []
            for code in courses:
                # Tablo kodları yalnızca yukarıdaki sabit, güvenli haritadan gelir.
                if code not in known or not re.fullmatch(r'[a-z_]+', code):
                    missing.append(COURSE_NAMES.get(code, code))
                    continue
                columns = {r[1] for r in con.execute(f'PRAGMA table_info("{code}")')}
                if 'konu' not in columns:
                    missing.append(COURSE_NAMES.get(code, code))
                    continue
                values = {str(r[0]).strip().casefold() for r in con.execute(f'SELECT konu FROM "{code}"') if str(r[0] or '').strip()}
                counts.append(CourseCount(code, COURSE_NAMES.get(code, code), len(values)))
            note = ('Yerel ders havuzundaki benzersiz başlıklardır; resmî sınav konu toplamı değildir. '
                    'Bazı tablolarda TYT-AYT veya konu-alt konu ayrımı bulunmayabilir; '
                    'birden fazla ders havuzundaki benzer konu adları çift sayılabilir.')
            if missing:
                note += ' Eksik ders tabloları nedeniyle katalog toplamı kısmi.'
            if exam == 'YKS' and 'YDT' in name:
                note += ' YDT yabancı dil kapsamı bu veritabanında bulunmadığı için hesaplanmadı.'
            result[name] = TrackCount(sum(c.count for c in counts), tuple(counts), tuple(missing), note)
    finally:
        con.close()
    return result

# Varsayılan planlama tarihleridir; sınav tarihleri hakkında iddia DEĞİLDİR.
# Resmî tarihler ÖSYM/MEB tarafından açıklandığında JSON'da doğrulanmış URL,
# durum=official ve tarih bilgisi güncellenmelidir.
SCENARIOS = {
    '2027': {
        'YKS': {'date': '2027-06-19', 'status': 'estimate', 'source_url': ''},
        'MSÜ': {'date': '2027-03-07', 'status': 'estimate', 'source_url': ''},
        'LGS': {'date': '2027-06-13', 'status': 'estimate', 'source_url': ''},
    }
}

def read_calendar(today: date | None = None, config_path=None) -> dict:
    """Resmî açıklama yoksa yalnız açıkça işaretli planlama senaryosunu göster."""
    today = today or date.today()
    path = Path(config_path) if config_path else Path(__file__).resolve().parent.parent / 'config' / 'exam_calendar_v3555.json'
    try:
        saved = json.loads(path.read_text(encoding='utf-8'))
        candidates = saved.get('years', {}) if isinstance(saved, dict) else {}
    except (ValueError, OSError, TypeError):
        candidates = SCENARIOS
    result = {}
    for key in ('YKS', 'MSÜ', 'LGS'):
        future = []
        for year, mapping in candidates.items():
            if not isinstance(mapping, dict):
                continue
            record = mapping.get(key, {})
            try:
                target = date.fromisoformat(record.get('date', ''))
            except (ValueError, AttributeError, TypeError):
                continue
            if target < today:
                continue
            status = record.get('status', 'estimate')
            url = str(record.get('source_url', ''))
            from urllib.parse import urlparse
            host = (urlparse(url).hostname or '').lower()
            # 'Resmî' etiketi ancak resmî alan adına açıkça bağlanan, tarihli
            # bir kayıt varsa kullanılabilir. URL'nin içeriği çevrimiçi doğrulanmış sayılmaz.
            official = status == 'official' and (host == 'osym.gov.tr' or host.endswith('.osym.gov.tr') or host == 'meb.gov.tr' or host.endswith('.meb.gov.tr'))
            future.append((target, official, url if official else ''))
        if future:
            target, official, url = min(future, key=lambda t:t[0])
            result[key] = {'date': target.isoformat(), 'days': (target-today).days,
                           'status': 'official' if official else 'estimate',
                           'source_url': url}
        else:
            result[key] = {'date': '', 'days': None, 'status': 'unknown', 'source_url': ''}
    return result


def plan_projection(remaining_topics: int, weekly_topics: int, buffer_days: int,
                    revision_days: int, remaining_days: int) -> dict:
    """Haftada X konu -> 7 gün / hafta. Revizyon dönemi korunarak marj hesapla."""
    from math import ceil
    remaining_topics = max(0, int(remaining_topics))
    weekly_topics = max(1, int(weekly_topics))
    days = max(0, int(remaining_days))
    buffer_days = max(0, int(buffer_days))
    revision_days = max(0, int(revision_days))
    work_days = max(0, days - buffer_days - revision_days)
    need_days = ceil(7 * remaining_topics / weekly_topics)
    return {'study_days': need_days, 'available_days': work_days,
            'reserve_days': days - buffer_days - need_days,
            'margin_before_revision': work_days - need_days,
            'required_weekly': ceil(7 * remaining_topics / work_days) if work_days else None,
            'feasible': need_days <= work_days}
