# -*- coding: utf-8 -*-
"""V24.1: online year proof and offline source metadata, without Qt."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import ast
import pytest

from services.target_analysis_v24.official_sources import official_source
from services.target_analysis_v24.source_freshness_v241 import (
    extract_publication_year, create_snapshot, validate_snapshot,
    snapshot_description, read_cache, save_cache, SourceFreshnessError, cache_path,
)

YOK = official_source('YKS-SAY')[1]
MEB = official_source('LGS')[1]

@pytest.mark.parametrize('html,year', [
    ("2025 YKS'de Merkezi Yerleştirme ile öğrenci alan", 2025),
    ("2025 YKS’de Merkezi Yerleştirme işlemleri", 2025),
    ("2025 YKS'de Merkezî Yerleştirme ile", 2025),
    ("2026-YKS sonuçlarına göre ... 2025 YKS'de Merkezi Yerleştirme", 2025),
    ('2026 için projeksiyon; 2025 verisi', None),
    ('<script>2026 YKS\'de Merkezi Yerleştirme</script> 2025 YKS\'de Merkezi Yerleştirme', 2025),
    ('İnternet sayfası erişilebilir ancak bilgi bulunamadı.', None),
])
def test_only_explicit_yok_explanation_identifies_year(html, year):
    assert extract_publication_year('YKS', YOK, html) == year


def test_meb_homepage_is_not_lgs_target_data():
    assert extract_publication_year('LGS', MEB, "2025 YKS'de Merkezi Yerleştirme") is None

@pytest.mark.parametrize('url', [
    'https://yokatlas.yok.gov.tr.evil.test/netler-tablo.php',
    'http://yokatlas.yok.gov.tr/netler-tablo.php',
    'https://yokatlas.yok.gov.tr/netler-tablo.php?student=123',
    'https://osym.gov.tr/2026-yks-yerlestirme-sonuclari-aciklandi',
])
def test_unexpected_remote_addresses_fail_closed(url):
    with pytest.raises(SourceFreshnessError):
        create_snapshot('YKS', url, '')


def test_large_page_cannot_be_persisted():
    with pytest.raises(SourceFreshnessError, match='boyut sınırını'):
        create_snapshot('YKS', YOK, b'X' * 1_000_001)


def test_live_snapshot_is_not_program_data():
    s=create_snapshot('YKS', YOK, "2025 YKS'de Merkezi Yerleştirme ile")
    assert s['reference_year'] == 2025
    assert s['scope'] == 'source_page_metadata_only'
    assert '2025' in snapshot_description(s, 2026)
    assert 'eşleşmiyor' in snapshot_description(s, 2026)
    assert 'doğrulanmadı' in snapshot_description(s, 2025)
    assert not set(s) & {'student_id', 'name', 'net', 'goal', 'student_name'}


def test_offline_cache_preserves_known_sources_without_student_data(tmp_path):
    p=cache_path(tmp_path)
    yok=create_snapshot('YKS',YOK,"2025 YKS'de Merkezi Yerleştirme ile")
    meb=create_snapshot('LGS',MEB,'2026 MEB sınavlar')
    save_cache(p,yok)
    save_cache(p,meb)
    assert read_cache(p,'YKS')['reference_year'] == 2025
    assert read_cache(p,'LGS')['reference_year'] is None
    assert 'Çevrim dışı' in snapshot_description(read_cache(p,'YKS'),2026,offline=True)
    data=p.read_text(encoding='utf-8')
    assert 'öğrenci' not in data.lower()
    assert 'student' not in data.lower()


def test_tampered_cache_is_rejected(tmp_path):
    p=cache_path(tmp_path)
    good=create_snapshot('YKS',YOK,"2025 YKS'de Merkezi Yerleştirme ile")
    good['url']='https://attacker.example/collect'
    p.write_text(json.dumps({'schema':1,'YKS':good}),encoding='utf-8')
    assert read_cache(p,'YKS') is None


def test_added_personal_field_in_cache_is_rejected():
    s=create_snapshot('YKS',YOK,"2025 YKS'de Merkezi Yerleştirme ile")
    s['student_name']='Do not store personal records'
    with pytest.raises(SourceFreshnessError): validate_snapshot(s)


def test_future_dated_cache_is_rejected():
    s=create_snapshot('YKS',YOK,"2025 YKS'de Merkezi Yerleştirme ile")
    s['checked_at']=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
    with pytest.raises(SourceFreshnessError):validate_snapshot(s)


def test_stale_data_never_described_as_fresh():
    s=create_snapshot('YKS',YOK,"2025 YKS'de Merkezi Yerleştirme ile",
                      fetched_at=datetime.now(timezone.utc)-timedelta(days=80))
    assert 'eski kontrol' in snapshot_description(s,2025,offline=True)


def test_missing_corrupt_cache_is_safe(tmp_path):
    p=tmp_path/'cache.json'
    assert read_cache(p,'YKS') is None
    p.write_text('broken',encoding='utf-8')
    assert read_cache(p,'YKS') is None


def test_ui_never_writes_official_numbers_into_students():
    path=Path(__file__).parents[1]/'ui'/'target_analysis_dialog.py'
    s=path.read_text(encoding='utf-8')
    tree=ast.parse(s)
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='TargetAnalysisDialog')
    a=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_complete_public_source_metadata')
    text=ast.get_source_segment(s,a)
    assert 'UPDATE ogrenci' not in text and 'save_cache' in text
    assert 'create_snapshot' in text
    assert 'self._official_manager.head(request)' in s
    assert 'self._official_manager.get(request)' in s


def test_source_info_does_not_infer_2026_yok_from_osym_release():
    body='''<h1>2026 YKS Yerleştirme Açıklandı</h1><p>2025 YKS'de Merkezi Yerleştirme ile ...</p>'''
    assert extract_publication_year('YKS',YOK,body)==2025
