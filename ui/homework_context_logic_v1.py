"""Homework context hub V1 pure helpers.

Absolutely no write access to SQLite, table items, checkbox state, network or settings.
For easy isolated testing independently of PyQt6.
"""
from __future__ import annotations
from dataclasses import dataclass
from urllib.parse import urlencode


@dataclass(frozen=True)
class CellSummary:
    book: str
    state: str  # 'locked', 'checked', 'empty'


@dataclass(frozen=True)
class TopicSummary:
    topic: str
    subject: str
    cells: tuple[CellSummary, ...]

    @property
    def locked(self) -> int:
        return sum(cell.state == 'locked' for cell in self.cells)

    @property
    def checked(self) -> int:
        return sum(cell.state == 'checked' for cell in self.cells)

    @property
    def empty(self) -> int:
        return sum(cell.state == 'empty' for cell in self.cells)


def summarize_topic(topic: str, subject: str, entries: list[tuple[str, bool, bool]]) -> TopicSummary:
    """Convert read-only (book, is_checked, is_user_checkable) triples to summary.

    The 3rd input represents editability according to the EXISTING Qt lock
    policy (flags and any applicable legacy color rule). This never changes it.
    """
    cells = tuple(CellSummary(book, 'locked' if not checkable else 'checked' if checked else 'empty')
                  for book, checked, checkable in entries)
    return TopicSummary(topic, subject, cells)


def official_resource_links(subject: str, topic: str) -> tuple[tuple[str, str, str], ...]:
    """Build read-only external resource destinations; NEVER embed student PII.

    Note: search URLs do not imply that an exact matching resource exists.
    """
    subject = ' '.join(str(subject or '').split())[:100]
    topic = ' '.join(str(topic or '').split())[:100]
    query = ' '.join(part for part in (subject, topic) if part).strip()
    base = (
        ('MEBİ - konu özeti, video ve denemeler', 'https://mebi.eba.gov.tr/',
         'MEBİ ana sayfasını açar; platform içindeki arama/giriş gerekebilir.'),
        ('OGM Materyal - resmi içerikler', 'https://ogmmateryal.eba.gov.tr/',
         'OGM Materyal portalını açar.'),
        ('ÖSYM - YKS soru ve cevapları', 'https://www.osym.gov.tr/SinavGrubu/Index/2',
         'ÖSYM YKS resmi duyuru ve soru kitapçıkları sayfasını açar.'),
    )
    if not topic:
        return base
    site_query = f'site:ogmmateryal.eba.gov.tr {query} soru bankası konu anlatımı'
    return base + (
        ('OGM içinde bu konuyu ara', 'https://www.google.com/search?' + urlencode({'q': site_query}),
         'Google üzerinde yalnızca OGM alan adına yönelik konu araması açar.'),
    )


def create_study_plan(lines: list[tuple[str, str]], daily_count: int, start_date) -> str:
    """Prepare read-only schedule text, independent of app/DB state.

    start_date supports datetime.date. This function does not assign/save homework.
    """
    import datetime
    if not 1 <= daily_count <= 30:
        raise ValueError('Günlük konu sayısı 1-30 arasında olmalı')
    if len(lines) > 3000:
        raise ValueError('En fazla 3000 konu planlanabilir')
    title = f'GÜVENLİ ÇALIŞMA PLANI • {len(lines)} konu • Ödevlere uygulanmadı'
    result = [title, '']
    days = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar']
    for offset in range(0, len(lines), daily_count):
        d = start_date + datetime.timedelta(days=offset // daily_count)
        result.append(f'{d.strftime("%d.%m.%Y")} {days[d.weekday()]}')
        for topic, book in lines[offset:offset + daily_count]:
            result.append(f'  ☐ {topic}  •  {book}')
        result.append('')
    result.append('Bilgi: Bu yalnızca önizlemedir; hiçbir checkbox, kayıt veya görev değiştirilmedi.')
    return '\n'.join(result)
