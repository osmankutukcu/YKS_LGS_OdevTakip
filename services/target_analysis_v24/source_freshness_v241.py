# -*- coding: utf-8 -*-
"""V24.1: kamuya açık resmî kaynakların sürüm ve erişim kanıtı.

Bu kod program bazlı net/puan çıkarmaz. Öğrenci verisi göndermez veya saklamaz.
YÖK Atlas yıl bilgisi yalnızca açıklama cümlesinden okunur; rastgele 2026
rakamının HTML'de bulunması 2026 yerleştirme neti kanıtı değildir.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit

from .official_sources import official_source, is_allowlisted_url

_SCHEMA = 1
_SNAPSHOT_KEYS = frozenset({'schema', 'source', 'url', 'reference_year', 'checked_at', 'scope'})
_MAX_HTML = 1_000_000
_YOK_YEAR = re.compile(
    r"\b(20\d{2})\s*(?:[-‑– ]*)YKS(?:['’`]?(?:de|da|DE|DA))?\s+"
    r"(?:Merkez[îi]|merkez[îi])\s+Yerleştirme\b", re.IGNORECASE
)
_YOK_YEAR_ALT = re.compile(
    r"\b(20\d{2})\s*(?:[-‑– ]*)YKS\s*(?:sonuçlarına|yerleştirmesi|yerleştirme\s+sonuçlarına)", re.IGNORECASE
)


class SourceFreshnessError(ValueError):
    pass


def _validate_source(source: str, url: str) -> None:
    _, expected = official_source('YKS' if source == 'YKS' else 'LGS')
    if source not in ('YKS', 'LGS') or not is_allowlisted_url(url) or url != expected:
        raise SourceFreshnessError('Kaynak adresi resmî izin listesinde değil.')


def extract_publication_year(source: str, url: str, html: bytes | str) -> int | None:
    """Sadece belirli bir YÖK Atlas açıklama kalıbından yılı okur."""
    _validate_source(source, url)
    if source != 'YKS':
        return None  # MEB ana sayfası LGS taban/net verisi değildir.
    if isinstance(html, bytes):
        if len(html) > _MAX_HTML:
            raise SourceFreshnessError('Kaynak sayfa boyut sınırını aşıyor.')
        html = html.decode('utf-8', errors='replace')
    if len(html.encode('utf-8')) > _MAX_HTML:
        raise SourceFreshnessError('Kaynak sayfa boyut sınırını aşıyor.')
    # Dış HTML içindeki script ve stilin rastgele yıl metinlerini karıştırma.
    plain = re.sub(r'<(?:script|style)\b[^>]*>.*?</(?:script|style)>', ' ', html,
                   flags=re.IGNORECASE | re.DOTALL)
    plain = re.sub(r'<[^>]+>', ' ', plain)
    import html as html_mod
    plain = re.sub(r'\s+', ' ', html_mod.unescape(plain))
    hits = _YOK_YEAR.findall(plain)
    # Yeni biçimde yayımlanmış açık ifade dışında yıl çıkartmayız.
    if not hits:
        hits = _YOK_YEAR_ALT.findall(plain)
    valid = [int(year) for year in hits if 2018 <= int(year) <= datetime.now(timezone.utc).year]
    return max(valid) if valid else None


def create_snapshot(source: str, url: str, html: bytes | str, *,
                    fetched_at: datetime | None = None) -> dict:
    _validate_source(source, url)
    fetched_at = fetched_at or datetime.now(timezone.utc)
    if fetched_at.tzinfo is None:
        raise SourceFreshnessError('Zaman dilimi belirtilmelidir.')
    return {'schema': _SCHEMA, 'source': source, 'url': url,
            'reference_year': extract_publication_year(source, url, html),
            'checked_at': fetched_at.astimezone(timezone.utc).isoformat(),
            'scope': 'source_page_metadata_only'}


def validate_snapshot(data: dict, *, max_future_seconds: int = 300) -> dict:
    if not isinstance(data, dict) or data.get('schema') != _SCHEMA or set(data) != _SNAPSHOT_KEYS:
        raise SourceFreshnessError('Önbellek şeması tanınmıyor.')
    source, url = data.get('source'), data.get('url')
    _validate_source(source, url)
    if data.get('scope') != 'source_page_metadata_only':
        raise SourceFreshnessError('Kanıt kapsamı geçersiz.')
    ref_year = data.get('reference_year')
    if ref_year is not None and (type(ref_year) is not int or ref_year < 2018 or ref_year > datetime.now(timezone.utc).year):
        raise SourceFreshnessError('Kaynak yılı geçersiz.')
    try:
        checked_at = datetime.fromisoformat(data['checked_at'])
    except (TypeError, KeyError, ValueError) as exc:
        raise SourceFreshnessError('Kaynak kontrol tarihi geçersiz.') from exc
    if checked_at.tzinfo is None or checked_at.astimezone(timezone.utc) > datetime.now(timezone.utc) + timedelta(seconds=max_future_seconds):
        raise SourceFreshnessError('Kaynak zamanı doğrulanamadı.')
    return dict(data)


def cache_path(app_data_dir: str | Path) -> Path:
    return Path(app_data_dir) / 'public_source_metadata_v241.json'


def read_cache(path: str | Path, source: str) -> dict | None:
    """Önbellek güvenilir resmî hedef/net kanıtı değil, son kontrol kaydıdır."""
    try:
        p = Path(path)
        if not p.is_file() or p.stat().st_size > 16_384:
            return None
        records = json.loads(p.read_text(encoding='utf-8'))
        if not isinstance(records, dict) or records.get('schema') != _SCHEMA:
            return None
        snap = validate_snapshot(records.get(source))
        return snap if snap.get('source') == source else None
    except (OSError, ValueError, TypeError, KeyError, SourceFreshnessError):
        return None


def save_cache(path: str | Path, snapshot: dict) -> None:
    """Öğrenci verisi içermeyen sınırlı metadata atomik yazılır."""
    snap = validate_snapshot(snapshot)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if path.exists():
        for source in ('YKS', 'LGS'):
            item = read_cache(path, source)
            if item:
                existing[source] = item
    existing[snap['source']] = snap
    payload = {'schema': _SCHEMA, **existing}
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                dir=path.parent, prefix='.official-v241-', suffix='.tmp', delete=False) as f:
            tmp_path = f.name
            json.dump(payload, f, ensure_ascii=False, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def snapshot_description(snapshot: dict | None, selected_year: int, *,
                         offline: bool = False, max_age_days: int = 30, from_cache: bool = False) -> str:
    """Yıl uyuşması olsa bile sayısal hedef verisi doğrulanmış sayılmaz."""
    if not snapshot:
        return ('Çevrim dışı: daha önce kontrol edilen kaynak bulunamadı.' if offline
                else 'Resmî kaynağın içerik yılı henüz doğrulanmadı.')
    snap = validate_snapshot(snapshot)
    checked = datetime.fromisoformat(snap['checked_at'])
    age = datetime.now(timezone.utc) - checked.astimezone(timezone.utc)
    stale = age > timedelta(days=max_age_days)
    tag = ('Çevrim dışı, önbellek' if offline else
           'Son kaydedilen kaynak kontrolü' if from_cache else
           'Resmî sayfadan canlı kontrol')
    if stale:
        tag += ' (eski kontrol)'
    year = snap['reference_year']
    if year is None:
        msg = 'Sayfadan program/net yılı güvenilir biçimde belirlenemedi.'
    elif year != selected_year:
        msg = f'Sayfa açıklaması {year} verisine işaret ediyor; seçilen {selected_year} yılıyla eşleşmiyor.'
    else:
        msg = f'Sayfa açıklaması {year} yılına işaret ediyor.'
    return (f'{tag} ({checked.date().isoformat()}): {msg} '
            'Program kodlu net/puanlar bu işlemle doğrulanmadı; yerel hedef listesi resmî sayılmaz.')
