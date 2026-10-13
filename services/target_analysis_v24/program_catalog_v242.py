# -*- coding: utf-8 -*-
"""V24.2: Öğretmen onaylı kamuya açık YKS program referans kataloğu.

Kritik ayrım: HTTPS resmî alan adı, CSV satırının resmî veri olduğunu
KANITLAMAZ. Bu modül ağdan veri kazımaz, öğrenci verisi yazmaz, otomatik
net/sıralama üretmez. Ayrı bir SQLite kataloğu kullanır.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit, parse_qs
import csv
import io
import json
import os
import re
import sqlite3

SCHEMA = 1
MAX_BYTES = 2_000_000
MAX_ROWS = 10_000
PROVENANCE = 'teacher_reviewed_external_not_independently_verified'
COLUMNS = ('year', 'program_code', 'university', 'program', 'score_type',
           'source', 'source_url', 'min_score', 'min_rank', 'tyt_net', 'second_net')
SOURCES = ('YOK_ATLAS', 'OSYM')
TYPES = ('SAY', 'EA', 'SOZ', 'DIL', 'TYT')
_VALID_URL_CHARS = re.compile(r'^[0-9]{8,12}$')

class CatalogError(ValueError):
    pass

@dataclass(frozen=True)
class ProgramRow:
    year: int
    program_code: str
    university: str
    program: str
    score_type: str
    source: str
    source_url: str
    min_score: Optional[float]
    min_rank: Optional[int]
    tyt_net: Optional[float]
    second_net: Optional[float]

@dataclass(frozen=True)
class PreparedCatalog:
    rows: tuple[ProgramRow, ...]
    sha256: str
    year: int
    source_label: str = PROVENANCE


def _source_url(value: str, code: str, year: int, source: str) -> str:
    """URL'nin şeması, alan adı, yolu ve sorgusu birlikte denetlenir."""
    try:
        url = urlsplit(value)
        host = url.hostname
        if (url.scheme != 'https' or url.username or url.password or url.port is not None
                or url.fragment or not host or url.netloc != host):
            raise CatalogError('Resmî kaynak adresi güvenli değil.')
        if source == 'YOK_ATLAS':
            if year != 2025:
                raise CatalogError('YÖK Atlas bu şablonda yalnızca 2025 yayın yılı ile kabul edilir; başka yıl doğrulanmadı.')
            if host != 'yokatlas.yok.gov.tr' or url.path not in ('/lisans.php', '/onlisans.php'):
                raise CatalogError('YÖK Atlas için program sayfasının tam bağlantısı gerekir.')
            params = parse_qs(url.query, keep_blank_values=True)
            if set(params) != {'y'} or params['y'] != [code]:
                raise CatalogError('YÖK Atlas bağlantısındaki program kodu uyuşmuyor.')
        elif source == 'OSYM':
            # Yalnızca 2026 resmî merkezi yerleştirme istatistik sayfası.
            # Başka yılların ve alt tabloların adresleri ayrıca doğrulanmalıdır.
            if (host not in ('osym.gov.tr', 'www.osym.gov.tr')
                or url.path != '/2026-yks-yerlestirme-sonuclarina-iliskin-sayisal-bilgiler'
                or url.query or year != 2026):
                raise CatalogError('ÖSYM için izinli 2026 kaynak sayfası/yılı kullanılmalı.')
        else:
            raise CatalogError('Kaynak türü tanınmıyor.')
    except ValueError as exc:
        if isinstance(exc, CatalogError):
            raise
        raise CatalogError('Kaynak adresi geçersiz.') from exc
    return value


def _number(v: str, title: str, limit: float, *, integer: bool = False):
    v = (v or '').strip()
    if not v:
        return None
    if len(v) > 24 or re.search(r'[^0-9,.]', v):
        raise CatalogError(f'{title} sayısal biçimi geçersiz.')
    # CSV sayılarında binlik ayırıcı kabul edilmez, TR ondalık virgül olabilir.
    if v.count(',') + v.count('.') > 1:
        raise CatalogError(f'{title}: sayı biçimi belirsiz.')
    if integer and ('.' in v or ',' in v):
        raise CatalogError(f'{title} tam sayı olmalı.')
    try:
        n = Decimal(v.replace(',', '.'))
    except InvalidOperation as exc:
        raise CatalogError(f'{title} sayısal değil.') from exc
    if not n.is_finite() or n < 0 or n > Decimal(str(limit)):
        raise CatalogError(f'{title} geçerli aralıkta değil.')
    if integer:
        if n == 0:
            raise CatalogError(f'{title} sıfır olamaz.')
        return int(n)
    return float(n)


def _text(v: str, title: str, maxlen: int = 160) -> str:
    v = (v or '').strip()
    if not v or len(v) > maxlen or any(ord(c) < 32 for c in v):
        raise CatalogError(f'{title} eksik, bozuk veya çok uzun.')
    # Excel formülü ve metin enjeksiyonuna benzeyen girdiler kullanılmaz.
    if v.startswith(('=', '+', '-', '@')):
        raise CatalogError(f'{title} şüpheli başlangıç karakteri içeriyor.')
    return v


def prepare_csv_bytes(content: bytes, *, expected_year: int) -> PreparedCatalog:
    if not isinstance(content, bytes) or len(content) > MAX_BYTES or not content:
        raise CatalogError('CSV boş veya boyut sınırını aşıyor (2 MB).')
    try:
        decoded = content.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise CatalogError('CSV UTF-8 kodlamasında olmalıdır.') from exc
    if '\x00' in decoded:
        raise CatalogError('CSV ikili veri içeriyor.')
    try:
        sep = csv.Sniffer().sniff(decoded[:2048], delimiters=',;\t').delimiter
    except csv.Error:
        sep = ';'
    reader = csv.DictReader(io.StringIO(decoded, newline=''), delimiter=sep)
    if reader.fieldnames is None or tuple(reader.fieldnames) != COLUMNS:
        raise CatalogError('CSV sütun sırası beklenen şablonla birebir aynı olmalı: ' + ';'.join(COLUMNS))
    if type(expected_year) is not int or not 2018 <= expected_year <= datetime.now(timezone.utc).year:
        raise CatalogError('Seçilen yıl geçersiz.')
    out, unique = [], set()
    for n, raw in enumerate(reader, start=2):
        if n > MAX_ROWS + 1:
            raise CatalogError('En fazla 10.000 program kaydı içe aktarılabilir.')
        if None in raw or any(v is None for v in raw.values()):
            raise CatalogError(f'{n}. satırda sütun sayısı yanlış.')
        try:
            year_text = raw['year'].strip()
            if year_text != str(expected_year):
                raise CatalogError('Satır yılı, ekranda seçilen yılla eşleşmiyor.')
            code = _text(raw['program_code'], 'Program kodu', 12)
            if not _VALID_URL_CHARS.fullmatch(code):
                raise CatalogError('Program kodu 8–12 haneli sayısal metin olmalıdır.')
            university = _text(raw['university'], 'Üniversite')
            program = _text(raw['program'], 'Program adı')
            score_type = _text(raw['score_type'], 'Puan türü', 3).upper()
            source = _text(raw['source'], 'Kaynak türü', 10).upper()
            if score_type not in TYPES or source not in SOURCES:
                raise CatalogError('Puan veya kaynak türü tanınmıyor.')
            url = _source_url(_text(raw['source_url'], 'Kaynak bağlantısı', 400), code, expected_year, source)
            score = _number(raw['min_score'], 'Taban puan', 600)
            rank = _number(raw['min_rank'], 'Taban sıra', 5_000_000, integer=True)
            tyt = _number(raw['tyt_net'], 'TYT net', 120)
            second = _number(raw['second_net'], 'AYT/YDT net', 80)
            if score is None and rank is None and tyt is None and second is None:
                raise CatalogError('En az bir sayısal ölçüt gerekli.')
            if source == 'OSYM' and (tyt is not None or second is not None):
                raise CatalogError('ÖSYM taban puan tablosuna son yerleşen netleri eklenemez.')
            if score_type == 'TYT' and second is not None:
                raise CatalogError('TYT programında AYT/YDT neti bulunamaz.')
            key = (expected_year, code, source)
            if key in unique:
                raise CatalogError('Dosyada yinelenen program kodu/kaynak var.')
            unique.add(key)
            out.append(ProgramRow(expected_year, code, university, program, score_type,
                                  source, url, score, rank, tyt, second))
        except CatalogError as exc:
            raise CatalogError(f'{n}. satır: {exc}') from exc
    if not out:
        raise CatalogError('CSV veri satırı içermiyor.')
    return PreparedCatalog(tuple(out), sha256(content).hexdigest(), expected_year)


def _connect(db_path: str | Path):
    # Öğrenci DB'si değil, yalnızca kamuya açık program referansları.
    conn = sqlite3.connect(str(db_path), timeout=5)
    conn.execute('PRAGMA busy_timeout=5000')
    return conn


def _ensure_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS program_reference_v242 (
        year INTEGER NOT NULL, program_code TEXT NOT NULL, source TEXT NOT NULL,
        payload TEXT NOT NULL, imported_at TEXT NOT NULL, source_label TEXT NOT NULL,
        PRIMARY KEY (year,program_code,source))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS program_import_log_v242 (
        id INTEGER PRIMARY KEY, source_hash TEXT NOT NULL, year INTEGER NOT NULL,
        row_count INTEGER NOT NULL, imported_at TEXT NOT NULL,
        source_label TEXT NOT NULL)''')


def _canonical_row(row: ProgramRow):
    return json.dumps(asdict(row), ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _existing_rows(conn, prepared: PreparedCatalog):
    return {(int(y), str(c), str(s)): str(p) for y, c, s, p in conn.execute(
        'SELECT year,program_code,source,payload FROM program_reference_v242 WHERE year=?',
        (prepared.year,)).fetchall()}


def preview_import(db_path: str | Path, prepared: PreparedCatalog) -> dict:
    """Yeni/kayıtlı/çakışan sayıları sadece okur. DB mevcut değilse 0 sayılır."""
    if not isinstance(prepared, PreparedCatalog) or not prepared.rows:
        raise CatalogError('Önizleme hazırlanmadı.')
    if not Path(db_path).exists():
        existing = {}
    else:
        with closing(_connect(db_path)) as conn:
            try:
                existing = _existing_rows(conn, prepared)
            except sqlite3.OperationalError as exc:
                raise CatalogError('Katalog şeması tanınmıyor.') from exc
    stats = {'new': 0, 'same': 0, 'conflict': 0}
    for row in prepared.rows:
        present = existing.get((row.year, row.program_code, row.source))
        stats['new' if present is None else 'same' if present == _canonical_row(row) else 'conflict'] += 1
    return stats


def apply_import(db_path: str | Path, prepared: PreparedCatalog, *, approved_hash: str,
                 expected_stats: dict):
    """Onaylanan SHA ve önizleme değişirse veya eski kayda çarparsa TAM geri al."""
    if (not isinstance(prepared, PreparedCatalog) or approved_hash != prepared.sha256 or
            sorted(expected_stats) != ['conflict', 'new', 'same']):
        raise CatalogError('Öğretmen onayı/önizleme uyuşmuyor.')
    if expected_stats['conflict']:
        raise CatalogError('Çelişkili eski kayıtlar var; otomatik üzerine yazma kapalı.')
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(db_path)
    try:
        conn.execute('BEGIN IMMEDIATE')
        _ensure_schema(conn)
        actual = _existing_rows(conn, prepared)
        stats = {'new': 0, 'same': 0, 'conflict': 0}
        for row in prepared.rows:
            present = actual.get((row.year, row.program_code, row.source))
            stats['new' if present is None else 'same' if present == _canonical_row(row) else 'conflict'] += 1
        if stats != expected_stats or stats['conflict']:
            raise CatalogError('Önizlemeden sonra katalog değişti; tekrar inceleyin.')
        now = datetime.now(timezone.utc).isoformat()
        for row in prepared.rows:
            conn.execute('''INSERT OR IGNORE INTO program_reference_v242
                (year,program_code,source,payload,imported_at,source_label)
                VALUES (?,?,?,?,?,?)''', (row.year, row.program_code, row.source,
                         _canonical_row(row), now, PROVENANCE))
        conn.execute('''INSERT INTO program_import_log_v242
            (source_hash, year, row_count, imported_at, source_label)
            VALUES (?,?,?,?,?)''', (prepared.sha256, prepared.year, stats['new'], now, PROVENANCE))
        conn.commit()
        return stats
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_programs(db_path: str | Path, *, year: int, score_type: str = '', query: str = '', limit: int = 250):
    if not Path(db_path).exists():
        return []
    if score_type and score_type not in TYPES:
        raise CatalogError('Puan türü geçersiz.')
    if type(year) is not int or not 2018 <= year <= datetime.now(timezone.utc).year:
        raise CatalogError('Yıl geçersiz.')
    with closing(_connect(db_path)) as conn:
        try:
            rows = conn.execute('''SELECT payload FROM program_reference_v242
                WHERE year=? ORDER BY program_code,source''', (year,)).fetchall()
        except sqlite3.OperationalError as exc:
            raise CatalogError('Katalog şeması tanınmıyor.') from exc
    out = []
    q = query.casefold().strip()[:100]
    for (payload,) in rows:
        try:
            data = json.loads(payload)
            row = ProgramRow(**data)
            _source_url(row.source_url, row.program_code, row.year, row.source)
            if score_type and score_type != row.score_type:
                continue
            if q and q not in (row.program_code + ' ' + row.university + ' ' + row.program).casefold():
                continue
            out.append(row)
        except (ValueError, TypeError, KeyError, CatalogError) as exc:
            raise CatalogError('Katalog kaydı bozuk veya kaynak adresi değişmiş.') from exc
        if len(out) >= limit:
            break
    return out


def catalog_db_path(app_data_dir: str | Path) -> Path:
    return Path(app_data_dir) / 'public_program_catalog_v242.sqlite'
