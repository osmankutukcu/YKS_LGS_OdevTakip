"""V39 — ortak, salt-okunur ders seçimi sözleşmesi.

Dersin ekrandaki adı ile veritabanı kimliğini ayırır. Hiçbir veriyi
oluşturmaz / güncellemez; geçmiş kodları silmez veya birleştirmez.
PyQt ve uygulama db.py modülünden bağımsızdır.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import sqlite3
import unicodedata
from typing import Iterable, Optional


@dataclass(frozen=True)
class LessonOption:
    code: str
    name: str
    active: bool = True
    historic: bool = False
    catalogued: bool = True

    @property
    def label(self) -> str:
        if not self.catalogued:
            return f"{self.code} (eski kayıt)"
        if not self.active:
            return f"{self.name} (pasif) · {self.code}"
        return self.name if self.name == self.code else f"{self.name} · {self.code}"


def token_key(text: str) -> tuple[str, ...]:
    """Yalnızca kesin token kümelerini eşleştirir; genel 'Matematik' ≠ TYT Matematik."""
    s = unicodedata.normalize('NFKD', str(text or '').casefold().replace('ı', 'i'))
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    return tuple(sorted(re.findall(r'[a-z0-9]+', s)))


def _present_tables(con: sqlite3.Connection) -> set[str]:
    return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def read_lesson_options(con: sqlite3.Connection, *, legacy: Iterable[str] = (),
                        history_sources: Iterable[str] = (),
                        always_include: Iterable[str] = ()) -> tuple[LessonOption, ...]:
    """Katalog + eski kodlar; listede gösterilen metin hiçbir zaman DB'ye yazılmaz.

    `history_sources` yalnızca sabit izinli tablolardır (kitap, ogrenci_kitap,
    odev, odev_satir). Pasif ders varsa, sadece geçmişte kullanılmışsa veya
    `always_include` içinde ise görüntülenir. DB şeması eksikse eski ders listesi
    olduğu gibi kullanılabilir; mevcut bağlantı/yazma işlemi yapılmaz.
    """
    permitted = {'kitap', 'ogrenci_kitap', 'odev', 'odev_satir'}
    sources = tuple(history_sources)
    if set(sources) - permitted:
        raise ValueError('İzin verilmeyen geçmiş ders kaynağı.')
    tables = _present_tables(con)
    history: set[str] = {str(x) for x in always_include if str(x).strip()}
    for table in sources:
        if table not in tables:
            continue
        cols = {r[1] for r in con.execute(f'PRAGMA table_info("{table}")')}
        if 'ders' not in cols:
            continue
        for row in con.execute(
            f'SELECT DISTINCT ders FROM "{table}" WHERE ders IS NOT NULL AND trim(ders)<>\'\''
        ):
            history.add(str(row[0]))

    catalog = []
    if 'ders_tanimlari' in tables:
        cols = {r[1] for r in con.execute('PRAGMA table_info("ders_tanimlari")')}
        if {'id', 'ad', 'aktif', 'siralama'} <= cols:
            catalog = [LessonOption(str(row[0]), str(row[1] or row[0]),
                                    bool(row[2]), str(row[0]) in history)
                       for row in con.execute(
                           'SELECT id,ad,aktif FROM ders_tanimlari ORDER BY siralama,id')]
    result = []
    seen = set()
    for entry in catalog:
        seen.add(entry.code)
        if entry.active or entry.historic:
            result.append(entry)
    # Önce veritabanı kayıtlı kodları, sonra eski sabit listesini kullan;
    # pasif katalog dersleri yanlışlıkla sabit listeden tekrar ekleme.
    for code in list(dict.fromkeys(str(x) for x in legacy)) + sorted(history):
        if not code or code in seen:
            continue
        seen.add(code)
        result.append(LessonOption(code, code, active=True,
                                   historic=code in history, catalogued=False))
    return tuple(result)


def resolve_lesson_code(value: str, options: Iterable[LessonOption]) -> Optional[str]:
    """Tek anlamlı ID/etiket eşleştirmesi; tahminle bir dersin koduna gitmez."""
    options = tuple(options)
    source = str(value or '').strip()
    if not source:
        return None
    # UI etiketi yeniden giriş olarak verilirse de eski (code) değer döner.
    exact_ids = [opt.code for opt in options if source.casefold() == opt.code.casefold()]
    if len(set(exact_ids)) == 1:
        return exact_ids[0]
    # Label'da ID varsa bilerek tam eşleştirme kullan.
    exact_labels = [opt.code for opt in options if source == opt.label]
    if len(set(exact_labels)) == 1:
        return exact_labels[0]
    candidate_key = token_key(source)
    if not candidate_key:
        return None
    matched = {opt.code for opt in options if candidate_key in
               (token_key(opt.code), token_key(opt.name))}
    return next(iter(matched)) if len(matched) == 1 else None

@dataclass(frozen=True)
class IdentityCheck:
    options: tuple[LessonOption, ...]
    coaching_counts: tuple[tuple[str, int], ...]
    unresolved_coaching: tuple[tuple[str, int], ...]
    total_coaching: int
    legacy_codes: tuple[str, ...]


def inspect_lesson_identities(con: sqlite3.Connection, *, legacy: Iterable[str] = ()) -> IdentityCheck:
    """Tüm modüller için ders kimliği farklarını yalnızca okur.

    Koçlukta belirsiz veya katalog dışı adlar tahminle aktarılmaz.
    """
    options = read_lesson_options(
        con, legacy=legacy, history_sources=('kitap', 'ogrenci_kitap', 'odev', 'odev_satir'))
    existing = _present_tables(con)
    grouped: dict[str, int] = {}
    failed: dict[str, int] = {}
    total = 0
    if 'koc_konu_takip' in existing:
        columns = {r[1] for r in con.execute('PRAGMA table_info("koc_konu_takip")')}
        if 'ders_adi' in columns:
            for label, count in con.execute(
                'SELECT ders_adi,COUNT(*) FROM koc_konu_takip GROUP BY ders_adi'
            ):
                count = int(count)
                total += count
                text = str(label or '')
                found = resolve_lesson_code(text, options)
                if found is None:
                    failed[text] = failed.get(text, 0) + count
                else:
                    grouped[found] = grouped.get(found, 0) + count
    legacy_codes = tuple(sorted(x.code for x in options if not x.catalogued and x.historic))
    return IdentityCheck(
        options=options, coaching_counts=tuple(sorted(grouped.items())),
        unresolved_coaching=tuple(sorted(failed.items())),
        total_coaching=total, legacy_codes=legacy_codes)
