"""V24.2: Doğrulanmamış resmî kaynak aktarımının katı kontrolleri."""
import ast
import csv
import io
import json
import sqlite3
from pathlib import Path

import pytest
from services.target_analysis_v24.program_catalog_v242 import (
    CatalogError, COLUMNS, prepare_csv_bytes, preview_import, apply_import,
    list_programs, catalog_db_path, PROVENANCE,
)

URL = 'https://yokatlas.yok.gov.tr/lisans.php?y=104210100'
OSYM = 'https://www.osym.gov.tr/2026-yks-yerlestirme-sonuclarina-iliskin-sayisal-bilgiler'


def make_csv(**change):
    obj = dict(year='2025', program_code='104210100', university='Örnek Üniversite',
               program='Fizik Öğretmenliği', score_type='SAY', source='YOK_ATLAS',
               source_url=URL, min_score='386,25', min_rank='60342',
               tyt_net='', second_net='')
    obj.update(change)
    f = io.StringIO()
    writer = csv.DictWriter(f, fieldnames=COLUMNS, delimiter=';', lineterminator='\n')
    writer.writeheader()
    writer.writerow(obj)
    return f.getvalue().encode('utf-8-sig')


def prep(**changes):
    return prepare_csv_bytes(make_csv(**changes), expected_year=2025)


def test_parse_official_shape_but_unverified():
    p = prep()
    assert p.rows[0].min_score == 386.25
    assert p.rows[0].min_rank == 60342
    assert p.rows[0].program_code == '104210100'
    assert p.rows[0].tyt_net is None
    assert p.source_label == PROVENANCE


def test_preview_no_database_creation(tmp_path):
    path = catalog_db_path(tmp_path)
    assert preview_import(path, prep()) == {'new': 1, 'same': 0, 'conflict': 0}
    assert not path.exists()


def test_transaction_and_list(tmp_path):
    path = catalog_db_path(tmp_path)
    p = prep()
    preview = preview_import(path, p)
    assert apply_import(path, p, approved_hash=p.sha256, expected_stats=preview)['new'] == 1
    rows = list_programs(path, year=2025)
    assert len(rows) == 1 and rows[0].program == 'Fizik Öğretmenliği'
    assert list_programs(path, year=2025, score_type='EA') == []
    assert len(list_programs(path, year=2025, query='öğretmenliği')) == 1
    with sqlite3.connect(path) as c:
        assert c.execute('select count(*) from program_import_log_v242').fetchone()[0] == 1
        assert set(x[0] for x in c.execute('select name from sqlite_master where type="table"')) >= {
            'program_import_log_v242', 'program_reference_v242'}


def test_reimport_idempotent(tmp_path):
    p = prep()
    path = catalog_db_path(tmp_path)
    apply_import(path, p, approved_hash=p.sha256, expected_stats=preview_import(path, p))
    preview = preview_import(path, p)
    assert preview == {'new': 0, 'same': 1, 'conflict': 0}
    stats = apply_import(path, p, approved_hash=p.sha256, expected_stats=preview)
    assert stats['new'] == 0 and len(list_programs(path, year=2025)) == 1


def test_different_value_conflict_no_write(tmp_path):
    path = catalog_db_path(tmp_path)
    p = prep()
    apply_import(path, p, approved_hash=p.sha256, expected_stats=preview_import(path, p))
    changed = prep(min_score='400')
    stats = preview_import(path, changed)
    assert stats['conflict'] == 1
    with pytest.raises(CatalogError, match='Çelişkili'):
        apply_import(path, changed, approved_hash=changed.sha256, expected_stats=stats)
    assert list_programs(path, year=2025)[0].min_score == 386.25


def test_stale_preview_stops_entire_file(tmp_path):
    path = catalog_db_path(tmp_path)
    p = prep()
    preview = preview_import(path, p)
    q = prep(min_score='400')
    apply_import(path, q, approved_hash=q.sha256, expected_stats=preview_import(path, q))
    with pytest.raises(CatalogError, match='Önizlemeden sonra'):
        apply_import(path, p, approved_hash=p.sha256, expected_stats=preview)
    assert len(list_programs(path, year=2025)) == 1


def test_hash_approval_fail_closed(tmp_path):
    p = prep()
    with pytest.raises(CatalogError, match='onayı'):
        apply_import(catalog_db_path(tmp_path), p, approved_hash='0'*64, expected_stats={'new':1,'same':0,'conflict':0})
    assert not catalog_db_path(tmp_path).exists()


@pytest.mark.parametrize('url', [
    'http://yokatlas.yok.gov.tr/lisans.php?y=104210100',
    'https://yokatlas.yok.gov.tr.evil.test/lisans.php?y=104210100',
    'https://evil.test/?y=104210100',
    'https://yokatlas.yok.gov.tr/lisans.php?y=104210101',
    'https://yokatlas.yok.gov.tr/lisans.php?y=104210100&student=4',
    'https://yokatlas.yok.gov.tr/lisans.php?y=104210100#x',
    'https://username@yokatlas.yok.gov.tr/lisans.php?y=104210100',
    'https://yokatlas.yok.gov.tr:443/lisans.php?y=104210100',
    'https://yokatlas.yok.gov.tr/lisans-bolum.php?y=104210100',
])
def test_reject_url_mismatch_and_redirect_like_strings(url):
    with pytest.raises(CatalogError):
        prep(source_url=url)


@pytest.mark.parametrize('changes', [
    {'year':'2026'}, {'program_code':'abc'}, {'program_code':'104210100.0'},
    {'university':'=HYPERLINK(123)'}, {'program':''},
    {'score_type':'YKS'}, {'source':'OTHER'},
    {'min_rank':'1.2'}, {'min_rank':'-1'}, {'min_score':'NaN'},
    {'min_score':'610'}, {'tyt_net':'121'}, {'second_net':'81'},
    {'min_score':'', 'min_rank':'', 'tyt_net':'', 'second_net':''},
    {'source_url':'https://osym.gov.tr/2026-yks-yerlestirme-sonuclarina-iliskin-sayisal-bilgiler'},
    {'score_type':'TYT', 'second_net':'20'},
])
def test_bad_rows_fail_atomic(changes):
    with pytest.raises(CatalogError):
        prep(**changes)


def test_osym_2026_only_and_no_inferred_nets():
    p = prepare_csv_bytes(make_csv(year='2026', source='OSYM', source_url=OSYM,
                                    tyt_net='', second_net=''), expected_year=2026)
    assert p.rows[0].year == 2026
    with pytest.raises(CatalogError):
        prepare_csv_bytes(make_csv(year='2026', source='OSYM', source_url=OSYM,tyt_net='71'), expected_year=2026)
    with pytest.raises(CatalogError):
        prepare_csv_bytes(make_csv(source='OSYM',source_url=OSYM),expected_year=2025)


def test_no_student_fields_and_no_legacy_changes():
    assert not set(COLUMNS) & {'student_id', 'ogrenci_id', 'ad', 'soyad'}
    path = Path(__file__).parents[1]/'ui'/'target_analysis_dialog.py'
    text = path.read_text(encoding='utf-8')
    ast.parse(text)
    assert 'def _open_program_catalog_v242' in text
    assert 'def _select_catalog_program_v242' in text
    chunk = text.split('    def _select_catalog_program_v242',1)[1].split('    def _official_cache_file',1)[0]
    assert 'UPDATE ogrenci' not in chunk
    assert 'self.inp_goal_1.clear()' in chunk


def test_bad_csv_structure_and_size():
    with pytest.raises(CatalogError):prepare_csv_bytes(b'hello,world\n1,2',expected_year=2025)
    with pytest.raises(CatalogError):prepare_csv_bytes(b'X'*2_000_001,expected_year=2025)
    with pytest.raises(CatalogError):prepare_csv_bytes(make_csv()[:-4],expected_year=2024)


def test_no_duplicate_identifiers():
    content = make_csv()
    line = content.decode('utf-8-sig').splitlines()[1]
    with pytest.raises(CatalogError,match='yinelenen'):
        prepare_csv_bytes(content+((line+'\n').encode()),expected_year=2025)


def test_partial_duplicate_batch_is_atomic(tmp_path):
    path = catalog_db_path(tmp_path)
    p=prep()
    apply_import(path, p, approved_hash=p.sha256, expected_stats=preview_import(path,p))
    b=make_csv().decode('utf-8-sig')
    first, line=b.split('\n')[:2]
    nextline=line.replace('104210100','104210101').replace('386,25','380,00').replace('Fizik Öğretmenliği','Kimya Öğretmenliği')
    mixed=prepare_csv_bytes((first+'\n'+line.replace('386,25','400')+'\n'+nextline+'\n').encode(),expected_year=2025)
    stats=preview_import(path,mixed)
    assert stats == {'new': 1, 'same': 0, 'conflict': 1}
    with pytest.raises(CatalogError):
        apply_import(path,mixed,approved_hash=mixed.sha256,expected_stats=stats)
    assert len(list_programs(path,year=2025))==1


@pytest.mark.parametrize('year', [2024, 2026])
def test_yok_atlas_year_not_yet_evidenced(year):
    with pytest.raises(CatalogError, match='2025 yayın yılı'):
        prepare_csv_bytes(make_csv(year=str(year)), expected_year=year)


def test_catalog_read_connections_are_explicitly_closed(tmp_path, monkeypatch):
    """SQLite context manager alone does not close handles (important on Windows)."""
    import services.target_analysis_v24.program_catalog_v242 as catalog
    path = catalog_db_path(tmp_path)
    p = prep()
    apply_import(path, p, approved_hash=p.sha256,
                 expected_stats=preview_import(path, p))
    real_connect = catalog._connect
    connections = []

    class TrackedConnection:
        def __init__(self, connection):
            self.connection = connection
            self.closed = False

        def execute(self, *args, **kwargs):
            return self.connection.execute(*args, **kwargs)

        def close(self):
            self.closed = True
            self.connection.close()

    def tracked_connect(db_path):
        instance = TrackedConnection(real_connect(db_path))
        connections.append(instance)
        return instance

    monkeypatch.setattr(catalog, '_connect', tracked_connect)
    assert preview_import(path, p)['same'] == 1
    assert len(list_programs(path, year=2025)) == 1
    assert len(connections) == 2
    assert all(connection.closed for connection in connections)


def test_catalog_ui_pagination_and_teacher_confirmation_structure():
    source = (Path(__file__).parents[1] / 'ui' / 'official_program_catalog_v242.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    method_names = {node.name for klass in ast.walk(tree) if isinstance(klass, ast.ClassDef)
                    for node in klass.body if isinstance(node, ast.FunctionDef)}
    assert {'_show_page', '_move_page', '_apply', '_selected'}.issubset(method_names)
    assert 'self.page_size = 200' in source
    assert 'TÜM CSV satırlarını' in source
    assert 'self.prepared.rows[start:start + self.page_size]' in source
