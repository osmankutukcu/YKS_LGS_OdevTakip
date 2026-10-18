# -*- coding: utf-8 -*-
"""V26.5: one compact same-student decision and explicit public-source checking."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import ast

import pytest

from services.coach_assistant_v1.dialogue import CoachAnswer
from services.coach_assistant_v1.decision_hub_v265 import coordinate_answer
from services.coach_assistant_v1.public_reference_v265 import (
    requested_source, enrich_official_reference,
)


def existing_answer():
    return CoachAnswer('Mevcut koçluk modüllerinin ortak değerlendirmesi',
                       'Öncelikle kısa bağımsız yoklama öneriliyor.', (
        'Öğrenci geneli: 52 tamamlanan, 22 açık ödev',
        'Adaptif Koçluk (LGS Türkçe / Fiilimsiler): Kısa tanılama yap [Kaynak: V25]',
        'Adaptif Koçluk tekrar bilgisi (LGS Türkçe)',
        'Öğrenme: V26.2 güncel ölçümler',
        'Akıllı Ödev Sihirbazı: geçmiş ödev/deneme; öğrenme puanı değildir',
        'Öğrenci 360°: güncel kontrol kayıtları',
        'Kapsam kontrolü: Öğrenci 360 52 ve Sihirbaz 49; sayılar birleştirilmedi.',
        'Veri eksikliği: deneme ölçümleri okunamadı',
    ), 'btnOgrenme')


def test_cross_module_returns_single_action_with_unique_source_types():
    a = coordinate_answer(existing_answer(), 'Tüm sistemler birlikte ne diyor?',
                          student_id=7, lesson_scope='LGS Türkçe')
    assert a.action_target == 'btnOgrenme'
    assert a.message.count('Öncelikle kısa bağımsız yoklama') == 1
    assert 'Ödev tamamlama, öğrenme ölçümü değildir' in a.message
    assert 'Seçili ders: LGS Türkçe' in a.message
    assert sum('Adaptif Koçluk' in x for x in a.evidence) == 1
    assert any('Kapsam kontrolü' in x for x in a.evidence)
    assert any('Veri eksikliği' in x for x in a.evidence)
    assert len(a.evidence) <= 6


def test_regular_question_unchanged():
    a = existing_answer()
    assert coordinate_answer(a, 'Hangi konu?', student_id=7, lesson_scope='LGS Türkçe') is a


def test_scope_rejection_stays_rejected():
    a = CoachAnswer('Ders kapsamı uyuşmuyor', 'Bu ders değil', ('Ders',), None)
    assert coordinate_answer(a, 'Tüm sistemler birlikte?', student_id=7) is a


def test_invalid_student_never_falls_back_to_first_student():
    with pytest.raises(ValueError):
        coordinate_answer(existing_answer(), 'Bütün modüller?', student_id=0)
    with pytest.raises(ValueError):
        coordinate_answer(existing_answer(), 'Bütün modüller?', student_id=True)


def test_message_is_bounded_and_preserves_teacher_approval():
    a = CoachAnswer('Mevcut koçluk modüllerinin ortak değerlendirmesi',
                    'Kanıt. ' * 120, ('Öğrenme: özet',), 'btnKontrol')
    out = coordinate_answer(a, 'Modüller ne diyor?', student_id=3)
    assert len(out.message) < 750
    assert 'öğretmen onayına tabidir' in out.message
    assert out.action_target == a.action_target


def test_online_selection_requires_explicit_keyword():
    assert requested_source('Fiilimsilerde öncelik ne?') is None
    assert requested_source('ÖSYM resmî kaynakları güncel mi?') == 'osym'
    assert requested_source('OGM resmi kaynak kontrolü') == 'ogm'
    assert requested_source('MEBİ resmi kaynakları kontrol et') == 'mebi'


class FakeCache:
    def __init__(self, existing=None):
        self.existing = existing
        self.puts = []
    def get(self, sid):
        return self.existing
    def put(self, snapshot):
        self.puts.append(snapshot)


def snapshot(sid='mebi', checked_at='2026-10-18T00:00:00+00:00'):
    from services.coach_assistant_v1.official_sources_v127 import SOURCES
    return {'source_id': sid, 'url': SOURCES[sid]['url'],
            'title': 'Kamuya açık sayfa', 'checked_at': checked_at,
            'verified_science': False, 'automatic_action_allowed': False}


def test_normal_coaching_never_fetches_public_site():
    def checker(*args):
        raise AssertionError('Normal öğretmen sorusu internet isteği yapmamalı')
    a = CoachAnswer('Öncelik', 'Ölçüm gerekli', ('V25',), 'btnOgrenme')
    assert enrich_official_reference(a, 'Öğrencinin önceliği?', checker=checker) is a


def test_fresh_cache_does_not_fetch_and_does_not_claim_curriculum_validated():
    date = datetime(2026, 10, 18, tzinfo=timezone.utc)
    cache = FakeCache(snapshot(checked_at='2026-10-18T00:00:00+00:00'))
    def no_fetch(sid):
        raise AssertionError('Taze sayfa önbelleği yeniden okunmamalı')
    a = CoachAnswer('Güncel kaynak doğrulaması gerekli', 'Eski açıklama', (), None)
    result = enrich_official_reference(a, 'MEB resmî kaynak güncel mi?',
                                       source_cache=cache, checker=no_fetch, now=date)
    assert 'Resmî kaynak' in result.title
    assert 'müfredat eşleşmesini' in result.message
    assert not cache.puts
    assert all('7' not in s for s in result.evidence)


def test_explicit_request_uses_allowlisted_url_only():
    cache = FakeCache()
    date = datetime(2026, 10, 18, tzinfo=timezone.utc)
    hits = []
    def checker(sid):
        hits.append(sid)
        return snapshot(sid)
    a = CoachAnswer('Kaynak', 'Veri yok', (), None)
    result = enrich_official_reference(a, 'ÖSYM kaynağını kontrol et; öğrenci 991',
                                       source_cache=cache, checker=checker, now=date)
    assert hits == ['osym']
    assert '991' not in str(result)
    assert cache.puts and cache.puts[0]['source_id'] == 'osym'
    assert result.action_target is None


def test_offline_without_cache_is_honest_and_no_fabrication():
    def fail(_):
        raise ConnectionError('network unavailable')
    a = CoachAnswer('Kaynak', 'Yok', (), None)
    result = enrich_official_reference(a, 'MEB resmî kaynakları kontrol et',
                                       source_cache=FakeCache(), checker=fail)
    assert 'erişilemiyor' in result.title
    assert 'güncel olarak doğrulanamadı' in result.message
    assert 'Öğrenci bilgileri dışarı gönderilmedi' in str(result.evidence)


def test_stale_cache_is_not_presented_as_live():
    old = snapshot(checked_at='2025-10-18T00:00:00+00:00')
    def fail(_):
        raise ConnectionError('offline')
    a = CoachAnswer('Kaynak', 'Yok', (), None)
    result = enrich_official_reference(a, 'MEB kaynağı güncel mi?',
                                       source_cache=FakeCache(old), checker=fail,
                                       now=datetime(2026,10,18,tzinfo=timezone.utc))
    assert 'eski önbellek (güncel değil)' in result.message


def test_malformed_fetched_record_rejected():
    a = CoachAnswer('Kaynak', 'Yok', (), None)
    invalid = lambda sid: dict(snapshot(sid), url='https://untrusted.example/private')
    r = enrich_official_reference(a, 'MEB kaynağı güncel mi?',
                                  source_cache=FakeCache(), checker=invalid)
    assert 'erişilemiyor' in r.title


def test_static_invariants_keep_forms_and_popup_design():
    root = Path(__file__).resolve().parents[1]
    hub = (root/'services/coach_assistant_v1/decision_hub_v265.py').read_text('utf8')
    online = (root/'services/coach_assistant_v1/public_reference_v265.py').read_text('utf8')
    ui = (root/'ui/coach_dialogue_v121.py').read_text('utf8')
    for code in (hub, online, ui):
        ast.parse(code)
    for s in ('UPDATE odev', 'DELETE FROM odev', 'INSERT INTO odev', 'CREATE TABLE'):
        assert s not in hub and s not in online
    assert 'self.setFixedWidth(430)' in ui
    assert 'self.setFixedHeight(405)' in ui
    assert 'coordinate_answer(result, self.question' in ui
    assert 'enrich_official_reference(result, self.question)' in ui


def test_corrupted_cache_cannot_claim_a_different_site_is_official():
    a = CoachAnswer('Kaynak', 'Yok', (), None)
    corrupted = dict(snapshot(), url='https://untrusted.example/private')
    invoked = []
    def checker(sid):
        invoked.append(sid)
        return snapshot(sid)
    result = enrich_official_reference(a, 'MEB resmî kaynaklarını kontrol et',
                                       source_cache=FakeCache(corrupted), checker=checker)
    assert invoked == ['mebi']
    assert 'untrusted' not in str(result)
