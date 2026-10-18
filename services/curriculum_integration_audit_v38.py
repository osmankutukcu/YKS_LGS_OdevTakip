# -*- coding: utf-8 -*-
from __future__ import annotations
"""V38: Müfredat/kitap/ödev/koçluk bağlantılarının SALT OKUNUR önizlemesi.

Bu modül veri taşımıyor, ders eşleştirmesi yazmıyor, hiç bir tablo oluşturmuyor.
Ödev Takip / Ödev Kontrol formlarının mevcut sorgularını veya davranışlarını değiştirmez.
"""
from collections import Counter
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
import re
import sqlite3
import unicodedata



@dataclass(frozen=True)
class LessonImpact:
    lesson_id: str
    name: str
    active: bool
    assigned: bool
    topic_count: int | None
    pool_books: int
    assigned_books: int
    homework: int
    homework_rows: int
    coaching_topics: int


@dataclass(frozen=True)
class CurriculumImpactSnapshot:
    group: str
    main_group: str
    student_count: int
    assignment_mode: str
    rows: tuple[LessonImpact, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)
    notices: tuple[str, ...] = field(default_factory=tuple)


def search_key(value):
    """Türkçe karakterleri korumalı alt-dize filtresi için normalize et."""
    normalized = unicodedata.normalize('NFKD', str(value or '').casefold().replace('ı', 'i'))
    return ''.join(char for char in normalized if not unicodedata.combining(char))


def _normal_key(value):
    """Ders etiketi varyantlarının katı kelime tabanlı karşılaştırması.

    TYT Matematik / Matematik (TYT) eşleşir; Matematik tek başına TYT/AYT
    gibi farklı derslerle ASLA otomatik ilişkilendirilmez.
    """
    value = unicodedata.normalize('NFKD', str(value or '').casefold().replace('ı', 'i'))
    value = ''.join(c for c in value if not unicodedata.combining(c))
    return tuple(sorted(re.findall(r'[a-z0-9]+', value)))


def _existing_tables(con):
    return {str(row[0]) for row in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}


def _subject_counts(con, tables, table, col, group=None):
    """İzin verilen tablo/sütunlardan bir defalık toplu sayım."""
    columns = {
        'kitap': ('ders', 'ad'),
        'ogrenci_kitap': ('ders', 'ogrenci_id'),
        'odev': ('ders', 'ogrenci_id'),
        'odev_satir': ('ders', 'ogrenci_id'),
        'koc_konu_takip': ('ders_adi', 'ogrenci_id'),
    }
    if table not in tables or col != columns.get(table, ('', ''))[0]:
        return {}
    if group is None:
        sql = f'SELECT t.{col}, COUNT(*) FROM "{table}" t GROUP BY t.{col}'
        params = ()
    else:
        if 'ogrenci' not in tables or columns[table][1] != 'ogrenci_id':
            return {}
        sql = (f'SELECT t.{col}, COUNT(*) FROM "{table}" t '
               f'JOIN ogrenci s ON s.id=t.ogrenci_id '
               f'WHERE s.alt_grup=? GROUP BY t.{col}')
        params = (group,)
    return {str(name or ''): int(count) for name, count in con.execute(sql, params)}


def inspect_group_curriculum(db_path, group, *, group_defaults, standard_groups):
    """Seçili gruptaki mevcut bağlantıların önizlemesi, SQLite mode=ro.

    `get_conn()` çağrılmaz; SQL veri yazan bir işlem çalıştırılmaz.
    Kayıp/eksik şemada uydurulmuş sayılar yerine açıklayıcı hata/uyarı döner.
    """
    group = str(group or '').strip()
    if not group:
        raise ValueError('Önce bir öğrenci grubu seçin.')
    path = Path(db_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError('Veritabanı bulunamadı; bağlantı kontrolü yapılamadı.')

    uri = path.as_uri() + '?mode=ro'
    with closing(sqlite3.connect(uri, uri=True, timeout=5)) as con:
        con.execute('PRAGMA query_only=ON')
        con.execute('BEGIN')  # Tutarlı, salt okunur anlık görüntü
        tables = _existing_tables(con)
        if 'ders_tanimlari' not in tables or 'ogrenci' not in tables:
            raise ValueError('Ders veya öğrenci tabloları bulunamadığı için analiz gösterilemiyor.')
        subjects = [dict(zip(('id', 'ad', 'grup', 'aktif', 'ozel', 'siralama'), rec))
                    for rec in con.execute(
                        'SELECT id,ad,grup,aktif,ozel,siralama FROM ders_tanimlari '
                        'ORDER BY siralama,id')]
        if not subjects:
            raise ValueError('Ders kataloğu boş. Müfredat ekranında dersleri kontrol edin.')

        warnings = []
        notices = []
        count = int(con.execute('SELECT COUNT(*) FROM ogrenci WHERE alt_grup=?',
                                (group,)).fetchone()[0])
        main = con.execute(
            "SELECT ana_grup FROM ogrenci WHERE alt_grup=? "
            "AND trim(coalesce(ana_grup,'')) <> '' "
            'GROUP BY ana_grup ORDER BY count(*) DESC LIMIT 1', (group,)
        ).fetchone()
        if main:
            main_group = str(main[0])
        else:
            main_group = next((m for m, groups in standard_groups.items()
                               if group in groups), 'YKS')
        if count == 0:
            notices.append('Bu grupta kayıtlı öğrenci bulunmuyor; öğrenciye bağlı sayılar 0 olacaktır.')
        if 'grup_dersleri' in tables:
            assigned = {str(r[0]) for r in con.execute(
                'SELECT ders_id FROM grup_dersleri WHERE grup_adi=?', (group,))}
        else:
            assigned = set()
            warnings.append('Grup ders eşleştirme tablosu bulunamadı; varsayılanlar gösteriliyor.')
        custom = bool(assigned)
        intended = assigned if custom else set(group_defaults.get(
            main_group, group_defaults['YKS']))
        catalog = {str(row['id']): row for row in subjects}
        active = {key for key, row in catalog.items() if row['aktif']}
        effective = intended & active
        mode = 'Gruba özel' if custom else 'Varsayılan'
        unknown = intended - set(catalog)
        if unknown:
            warnings.append('Grup eşleştirmesinde katalogda bulunmayan ders kodları: '
                            + ', '.join(sorted(unknown)[:8]))
        disabled = intended - active - unknown
        if disabled:
            notices.append('Gruba atanmış ancak pasif olduğu için yeni ders listesinde gizlenen dersler: '
                           + ', '.join(sorted(disabled)[:8]))

        pool = _subject_counts(con, tables, 'kitap', 'ders')
        assigned_books = _subject_counts(con, tables, 'ogrenci_kitap', 'ders', group)
        homework = _subject_counts(con, tables, 'odev', 'ders', group)
        homework_rows = _subject_counts(con, tables, 'odev_satir', 'ders', group)
        coaching = _subject_counts(con, tables, 'koc_konu_takip', 'ders_adi', group)
        # Not: koçlukta görünen adlar kullanılır. Sadece tam kelime kümesi
        # aynıysa eşleştirilir; farklı müfredatları tahminle birleştirmeyiz.
        aliases = {}
        ambiguous = set()
        for rec in subjects:
            for value in (rec['id'], rec['ad']):
                k = _normal_key(value)
                if k in aliases and aliases[k] != rec['id']:
                    ambiguous.add(k)
                aliases[k] = rec['id']
        coach_totals = Counter()
        unmapped_coach = Counter()
        for name, n in coaching.items():
            key = _normal_key(name)
            if key in aliases and key not in ambiguous:
                coach_totals[aliases[key]] += n
            else:
                unmapped_coach[name] += n
        if unmapped_coach:
            warnings.append(
                'Koçlukta ders kataloğuyla kesin eşleşmeyen başlıklar var '
                '(otomatik değiştirilmedi): ' +
                ', '.join(f'{name} ({count})' for name, count in
                          sorted(unmapped_coach.items())[:6])
            )

        available = set(catalog)
        historic_unknown = (set(pool) | set(assigned_books) | set(homework) |
                            set(homework_rows)) - available - {''}
        if historic_unknown:
            warnings.append('Kitap/ödev kayıtlarında katalogda olmayan ders kodları: ' +
                            ', '.join(sorted(historic_unknown)[:8]))
        if any(t not in tables for t in ('kitap', 'ogrenci_kitap', 'odev',
                                        'odev_satir', 'koc_konu_takip')):
            absent = [t for t in ('kitap', 'ogrenci_kitap', 'odev',
                                  'odev_satir', 'koc_konu_takip') if t not in tables]
            warnings.append('Bazı veri kaynakları bulunamadı; ilgili sayılar eksik olabilir: '
                            + ', '.join(absent))

        rows = []
        for rec in subjects:
            lid = str(rec['id'])
            topic_count = None
            if re.fullmatch(r'[a-z][a-z0-9_]{0,79}', lid) and lid in tables:
                cols = {c[1] for c in con.execute(f'PRAGMA table_info("{lid}")')}
                if 'konu' in cols:
                    topic_count = int(con.execute(f'SELECT COUNT(*) FROM "{lid}"').fetchone()[0])
            rows.append(LessonImpact(
                lesson_id=lid, name=str(rec['ad']), active=bool(rec['aktif']),
                assigned=lid in effective, topic_count=topic_count,
                pool_books=pool.get(lid, 0), assigned_books=assigned_books.get(lid, 0),
                homework=homework.get(lid, 0), homework_rows=homework_rows.get(lid, 0),
                coaching_topics=coach_totals.get(lid, 0),
            ))
            if lid in effective and topic_count is None:
                warnings.append(f'{rec["ad"]}: konu tablosu veya konu sütunu bulunamadı.')
        outside = [item.name for item in rows if not item.assigned and
                   (item.assigned_books or item.homework or item.homework_rows or item.coaching_topics)]
        if outside:
            notices.append('Grup dersleri dışında geçmiş öğrenci kaydı görünen dersler '
                           '(silinmez, otomatik taşınmaz): ' + ', '.join(outside[:8]))
        notices.append('Kitap havuzu ve konu sayısı ders genelindedir; öğrenciye tanımlı kitap, '
                       'ödev ve koçluk sayıları seçili gruptadır.')
        notices.append('Ödev ve ödev_satir kayıtları iki ayrı kaynaktır; sayıları birbirine ekleyerek '
                       'toplam ödev kabul etmeyin.')
        notices.append('Bu ekran yalnızca okur; geçmiş kayıtları silmez, dersleri yeniden adlandırmaz, '
                       'eşleştirme veya otomatik senkronizasyon yapmaz.')
        return CurriculumImpactSnapshot(
            group=group, main_group=main_group, student_count=count,
            assignment_mode=mode, rows=tuple(rows),
            warnings=tuple(warnings), notices=tuple(notices)
        )
