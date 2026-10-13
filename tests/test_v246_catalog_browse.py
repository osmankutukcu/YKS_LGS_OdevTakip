"""V24.6 – Katalogun bütün kayıtlarında güvenli gezinme/filtreleme."""
import ast
import csv
import io
import hashlib
import sqlite3
from pathlib import Path

import pytest

from services.target_analysis_v24.catalog_browser_v246 import browse_catalog
from services.target_analysis_v24.program_catalog_v242 import (
    CatalogError, COLUMNS, apply_import, preview_import, prepare_csv_bytes,
)

URL = 'https://yokatlas.yok.gov.tr/lisans.php?y={code}'


def prepare_many(count=320):
    target = io.StringIO()
    w = csv.DictWriter(target, fieldnames=COLUMNS, delimiter=';', lineterminator='\n')
    w.writeheader()
    for i in range(count):
        code = str(100000000 + i)
        w.writerow(dict(year='2025', program_code=code,
                        university='Örnek Üniversite',
                        program='Fizik' if i % 2 == 0 else 'Kimya',
                        score_type='SAY' if i % 2 == 0 else 'EA',
                        source='YOK_ATLAS', source_url=URL.format(code=code),
                        min_score='310', min_rank='10320', tyt_net='', second_net=''))
    return prepare_csv_bytes(target.getvalue().encode('utf-8-sig'), expected_year=2025)


def seeded(tmp_path, count=320):
    path = tmp_path / 'catalog.sqlite'
    prepared = prepare_many(count)
    stats = preview_import(path, prepared)
    apply_import(path, prepared, approved_hash=prepared.sha256, expected_stats=stats)
    return path


def test_empty_catalog_stays_missing(tmp_path):
    path = tmp_path / 'not_created.sqlite'
    p = browse_catalog(path, year=2025)
    assert not p.rows and p.total == 0 and p.pages == 1 and not path.exists()


def test_browse_all_320_programs_not_only_first_250(tmp_path):
    path = seeded(tmp_path)
    a = browse_catalog(path, year=2025, page=0)
    b = browse_catalog(path, year=2025, page=1)
    c = browse_catalog(path, year=2025, page=2)
    d = browse_catalog(path, year=2025, page=3)
    assert (len(a.rows),len(b.rows),len(c.rows),len(d.rows)) == (100,100,100,20)
    assert a.total == b.total == c.total == d.total == 320
    assert len({r.program_code for p in (a,b,c,d) for r in p.rows}) == 320
    assert a.rows[0].program_code == '100000000'
    assert d.rows[-1].program_code == '100000319'


def test_search_filters_on_full_catalog_and_pages(tmp_path):
    path = seeded(tmp_path)
    result = browse_catalog(path,year=2025,query='KİMYA',score_type='EA',page_size=40,page=2)
    assert result.total == 160 and len(result.rows) == 40 and result.pages == 4
    assert all(row.program == 'Kimya' and row.score_type == 'EA' for row in result.rows)
    assert browse_catalog(path,year=2025,score_type='SAY',page_size=80).total == 160
    assert browse_catalog(path,year=2025,source='OSYM').total == 0
    assert browse_catalog(path,year=2026).total == 0
    assert browse_catalog(path,year=2025,query='100000319').total == 1


def test_out_of_range_page_clamps_without_data_loss(tmp_path):
    path = seeded(tmp_path,11)
    out = browse_catalog(path,year=2025,page=9000,page_size=10)
    assert out.page == 1 and len(out.rows) == 1 and out.total == 11


@pytest.mark.parametrize('kwargs', [
    {'year': 2025, 'page': -1}, {'year': 2025, 'page': 1.5},
    {'year': 2025, 'page_size': 0}, {'year': 2025, 'page_size': 1000},
    {'year': 2025, 'source': 'FAKE'}, {'year': 2025, 'score_type': 'X'},
    {'year': 2025, 'query': 'x'*121}, {'year': '2025'},
])
def test_invalid_filters_rejected(tmp_path,kwargs):
    with pytest.raises(CatalogError): browse_catalog(tmp_path/'none.sqlite',**kwargs)


def test_catalog_browse_is_readonly(tmp_path):
    path = seeded(tmp_path)
    digest = lambda: hashlib.sha256(path.read_bytes()).hexdigest()
    before = digest()
    browse_catalog(path,year=2025,page=3)
    browse_catalog(path,year=2025,query='Fizik',source='YOK_ATLAS')
    assert digest() == before


def test_tampered_identity_fails_closed(tmp_path):
    path = seeded(tmp_path,1)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE program_reference_v242 SET program_code='999999999'")
    with pytest.raises(CatalogError): browse_catalog(path,year=2025)


def test_tampered_provenance_fails_closed(tmp_path):
    path = seeded(tmp_path,1)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE program_reference_v242 SET source_label='official'")
    with pytest.raises(CatalogError): browse_catalog(path,year=2025)


def test_corrupt_payload_fails_closed(tmp_path):
    path = seeded(tmp_path,1)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE program_reference_v242 SET payload='not json'")
    with pytest.raises(CatalogError): browse_catalog(path,year=2025)


def test_ui_preserves_existing_import_and_paginates_catalog():
    path = Path(__file__).parents[1] / 'ui' / 'official_program_catalog_v242.py'
    text = path.read_text(encoding='utf-8')
    ast.parse(text)
    assert 'browse_catalog(' in text
    assert 'catalog_page_size = 100' in text
    assert 'self.page_size = 200' in text
    assert 'self.catalog_page_index' in text
    assert 'def _apply(self):' in text
    assert 'apply_import(self.catalog_path' in text
    assert 'self.approve.isChecked()' in text
    assert 'self.catalog_page_index = 0' in text


def test_tampered_numeric_limits_fail_closed(tmp_path):
    path = seeded(tmp_path,1)
    with sqlite3.connect(path) as db:
        item = db.execute('SELECT payload FROM program_reference_v242').fetchone()[0]
        import json
        row = json.loads(item)
        row['min_rank'] = 999999999
        db.execute('UPDATE program_reference_v242 SET payload=?', (json.dumps(row),))
    with pytest.raises(CatalogError): browse_catalog(path,year=2025)
