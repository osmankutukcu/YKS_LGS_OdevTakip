# -*- coding: utf-8 -*-
"""V26.5: explicitly requested official-page metadata, no student data online.

Only fixed public sites from the existing allowlist are fetched. This is NOT
curriculum/achievement matching, AI training, independent fact verification,
or automatic research while teachers click their homework cells.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from services.coach_assistant_v1.shared_rules_v260 import fold


def requested_source(question: str) -> str | None:
    q = fold(question)
    if not any(term in q for term in (
        'resmi kaynak', 'guncel kaynak', 'internetten', 'online kaynak',
        'kaynaklari kontrol', 'meb', 'ogm', 'osym', 'kaynak guncel',
        'resmi site', 'guncel mufredat')):
        return None
    if 'osym' in q or 'sinav soru' in q:
        return 'osym'
    if 'ogm' in q:
        return 'ogm'
    return 'mebi'


def _recent_checked(snapshot, now):
    try:
        moment = datetime.fromisoformat(str(snapshot.get('checked_at') or ''))
        if moment.tzinfo is None:
            return False
        delta = now - moment.astimezone(timezone.utc)
        return timedelta(0) <= delta <= timedelta(hours=24)
    except (AttributeError, TypeError, ValueError, OverflowError):
        return False


def enrich_official_reference(answer, question: str, *, source_cache=None,
                              checker=None, now=None):
    """Only an explicit teacher query triggers a bounded public-page check.

    It never sends student id/name, topic, question text or DB content. Fetch
    gets only a fixed URL; offline failure returns clear inability rather than
    fabricated live information. Tests can inject fake checker/cache.
    """
    sid = requested_source(question)
    if sid is None or answer.title in ('Ders kapsamı uyuşmuyor', 'Ders adı belirsiz'):
        return answer
    from services.coach_assistant_v1.dialogue import CoachAnswer
    from services.coach_assistant_v1.official_sources_v127 import (
        SourceCache, check_source, catalog_entry,
    )
    catalogue = catalog_entry(sid)
    cache = source_cache if source_cache is not None else SourceCache()
    checker = checker if checker is not None else check_source
    now = now if now is not None else datetime.now(timezone.utc)
    snapshot = None
    origin = 'önbellek'
    try:
        snapshot = cache.get(sid)
    except (OSError, ValueError, TypeError):
        snapshot = None
    # A corrupted/mismatched cache is never accepted as a verified public page.
    if snapshot and (not isinstance(snapshot, dict)
                     or snapshot.get('source_id') != sid
                     or snapshot.get('url') != catalogue['url']
                     or snapshot.get('verified_science') is not False
                     or snapshot.get('automatic_action_allowed') is not False):
        snapshot = None
    if not snapshot or not _recent_checked(snapshot, now):
        origin = 'canlı site'
        try:
            fresh = checker(sid)
            if (not isinstance(fresh, dict) or fresh.get('url') != catalogue['url']
                or fresh.get('source_id') != sid or
                fresh.get('verified_science') is not False or
                fresh.get('automatic_action_allowed') is not False):
                raise ValueError('Resmî sayfa doğrulanamadı')
            snapshot = fresh
            try:
                cache.put(fresh)
            except (OSError, TypeError, ValueError):
                # Failed metadata cache must not affect student Q&A.
                pass
        except (ConnectionError, TimeoutError, OSError, ValueError, TypeError):
            if not snapshot:
                return CoachAnswer(
                    'Resmî kaynağa şu anda erişilemiyor',
                    f'{catalogue["name"]} sayfası güncel olarak doğrulanamadı. '
                    'Öğrencinin yerel koçluk analizleri bu nedenle değiştirilmedi. '
                    'İnternet geldiğinde yeniden deneyebilirsiniz.',
                    (f'Resmî adres: {catalogue["url"]}',
                     'Öğrenci bilgileri dışarı gönderilmedi.'), None)
            origin = 'eski önbellek (güncel değil)'
    title = ' '.join(str(snapshot.get('title') or catalogue['name']).split())[:140]
    checked_at = str(snapshot.get('checked_at') or 'belirsiz')[:32]
    return CoachAnswer(
        'Resmî kaynak durum kontrolü',
        f'{catalogue["name"]}: {title}. Sayfa meta verileri {origin} üzerinden kontrol edildi. '
        'Bu işlem yalnızca resmî sayfanın erişilebilir olduğunu ve görünen başlığını gösterir; '
        'müfredat eşleşmesini, pedagojik önerileri veya öğrencinin başarısını doğrulamaz.',
        (f'Kaynak: {catalogue["url"]}', f'Kontrol: {checked_at}',
         'Öğrenci adı, kayıtları ve soru metni siteye gönderilmedi.'),
        None,
    )
