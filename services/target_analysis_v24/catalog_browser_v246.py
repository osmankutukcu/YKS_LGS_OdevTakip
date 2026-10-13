# -*- coding: utf-8 -*-
"""V24.6: Kamuya açık program kataloğu için salt okunur, sayfalı tarayıcı.

V24.2 içe aktarma şemasını değiştirmez. Katalog satırları öğretmen tarafından
kontrol edilmiş olsa da resmî kaynaktan bağımsız doğrulanmış sayılmaz.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
import json
import sqlite3
import unicodedata
import math
from contextlib import closing

from .program_catalog_v242 import (
    CatalogError, ProgramRow, PROVENANCE, TYPES, SOURCES, _source_url,
)


@dataclass(frozen=True)
class CatalogPage:
    rows: tuple[ProgramRow, ...]
    total: int
    page: int
    page_size: int

    @property
    def pages(self) -> int:
        return max(1, (self.total + self.page_size - 1) // self.page_size)


def _searchable(value: str) -> str:
    # Python casefold('İ') -> 'i' + combining dot; normalize common
    # Turkish keyboard spellings so KİMYA and Kimya match.
    folded = unicodedata.normalize('NFKC', value).casefold()
    return folded.replace('i\u0307', 'i').replace('ı', 'i')


def _numeric_integrity(row: ProgramRow) -> None:
    for value, ceiling, integer in (
        (row.min_score, 600, False), (row.min_rank, 5_000_000, True),
        (row.tyt_net, 120, False), (row.second_net, 80, False),
    ):
        if value is None:
            continue
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value < 0 or value > ceiling
                or (integer and (not isinstance(value, int) or value == 0))):
            raise CatalogError('Katalog ölçütü geçersiz.')
    if row.source == 'OSYM' and (row.tyt_net is not None or row.second_net is not None):
        raise CatalogError('Kaynak türü ile net alanı uyuşmuyor.')
    if row.score_type == 'TYT' and row.second_net is not None:
        raise CatalogError('TYT programında ikinci sınav neti bulunamaz.')


def browse_catalog(db_path: str | Path, *, year: int, page: int = 0,
                   page_size: int = 100, query: str = '', score_type: str = '',
                   source: str = '') -> CatalogPage:
    """Read-only, deterministic pagination across all matching rows.

    Fail closed on corrupt data rather than displaying an unverified or
    mismatched program. All filtering is performed without changing schema.
    """
    if type(year) is not int or not 2018 <= year <= 2100:
        raise CatalogError('Katalog yılı geçersiz.')
    if type(page) is not int or page < 0:
        raise CatalogError('Sayfa numarası geçersiz.')
    if type(page_size) is not int or not 1 <= page_size <= 200:
        raise CatalogError('Sayfa boyutu geçersiz.')
    if not isinstance(query, str) or len(query) > 120:
        raise CatalogError('Arama metni geçersiz veya çok uzun.')
    if score_type and score_type not in TYPES:
        raise CatalogError('Puan türü geçersiz.')
    if source and source not in SOURCES:
        raise CatalogError('Kaynak filtresi geçersiz.')

    path = Path(db_path)
    if not path.is_file():
        return CatalogPage((), 0, 0, page_size)
    q = _searchable(query.strip())
    start = page * page_size
    found = 0
    visible: list[ProgramRow] = []
    uri = 'file:' + quote(str(path.resolve()), safe='/') + '?mode=ro'
    try:
        with closing(sqlite3.connect(uri, uri=True, timeout=4)) as conn:
            conn.execute('PRAGMA query_only=ON')
            cursor = conn.execute('''SELECT year, program_code, source, payload, source_label
                FROM program_reference_v242 WHERE year=? ORDER BY program_code,source''', (year,))
            for record_year, code, saved_source, payload, source_label in cursor:
                try:
                    obj = json.loads(payload)
                    row = ProgramRow(**obj)
                    if (type(record_year) is not int or row.year != record_year
                            or row.year != year or row.program_code != code
                            or row.source != saved_source or source_label != PROVENANCE):
                        raise CatalogError('Katalog kimliği veya kaynak etiketi uyuşmuyor.')
                    _source_url(row.source_url, row.program_code, row.year, row.source)
                    if row.score_type not in TYPES:
                        raise CatalogError('Katalog puan türü geçersiz.')
                    if not row.university or not row.program:
                        raise CatalogError('Katalog program adı eksik.')
                    _numeric_integrity(row)
                except (ValueError, TypeError, KeyError) as exc:
                    raise CatalogError('Katalogda bozuk veya tutarsız kayıt bulundu.') from exc
                if source and row.source != source:
                    continue
                if score_type and row.score_type != score_type:
                    continue
                if q and q not in _searchable(row.program_code + ' ' + row.university + ' ' + row.program):
                    continue
                if start <= found < start + page_size:
                    visible.append(row)
                found += 1
    except sqlite3.DatabaseError as exc:
        raise CatalogError('Katalog veritabanı okunamadı veya şeması tanınmıyor.') from exc
    # Kullanıcı veri filtreledikten sonra ileri sayfada kaldıysa, ekranda
    # 'boş' gösterip yanlış izlenim yaratma: son sayfaya güvenle yönlendir.
    last_page = max(0, (found - 1) // page_size)
    if page > last_page:
        return browse_catalog(path, year=year, page=last_page, page_size=page_size,
                              query=query, score_type=score_type, source=source)
    return CatalogPage(tuple(visible), found, page, page_size)
