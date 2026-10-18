from __future__ import annotations
"""V38 salt okunur entegrasyon önizlemesi: canlı DB veya Qt olmadan test."""
import ast
import hashlib
from pathlib import Path
import sqlite3
import pytest
from services.curriculum_integration_audit_v38 import (
    inspect_group_curriculum, search_key, _normal_key
)

ROOT = Path(__file__).resolve().parents[1]


def constants():
    tree = ast.parse((ROOT / 'db.py').read_text(encoding='utf-8'))
    output = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in ('DEFAULT_GRUP_DERSLER', 'CURRICULUM_GROUPS'):
                output[node.targets[0].id] = ast.literal_eval(node.value)
    return output['DEFAULT_GRUP_DERSLER'], output['CURRICULUM_GROUPS']


@pytest.fixture

def tiny_db(tmp_path):
    db_path = tmp_path / 'pilot.sqlite'
    with sqlite3.connect(db_path) as c:
        c.executescript('''
            CREATE TABLE ders_tanimlari (id TEXT PRIMARY KEY,ad TEXT,grup TEXT,aktif INTEGER,ozel INTEGER,siralama INTEGER);
            CREATE TABLE ogrenci (id INTEGER PRIMARY KEY,ana_grup TEXT,alt_grup TEXT);
            CREATE TABLE grup_dersleri (grup_adi TEXT,ders_id TEXT);
            CREATE TABLE kitap (id INTEGER PRIMARY KEY,ders TEXT,ad TEXT);
            CREATE TABLE ogrenci_kitap (id INTEGER PRIMARY KEY,ogrenci_id INTEGER,ders TEXT,kitap_ad TEXT);
            CREATE TABLE odev (id INTEGER PRIMARY KEY,ogrenci_id INTEGER,ders TEXT);
            CREATE TABLE odev_satir (id INTEGER PRIMARY KEY,ogrenci_id INTEGER,ders TEXT);
            CREATE TABLE koc_konu_takip (id INTEGER PRIMARY KEY,ogrenci_id INTEGER,ders_adi TEXT);
            CREATE TABLE tyt_matematik (id INTEGER PRIMARY KEY,konu TEXT);
            CREATE TABLE fizik (id INTEGER PRIMARY KEY,konu TEXT);
            CREATE TABLE lgs_matematik (id INTEGER PRIMARY KEY,konu TEXT);
        ''')
        c.executemany('INSERT INTO ders_tanimlari VALUES(?,?,?,?,?,?)', [
            ('tyt_matematik','TYT Matematik','YKS',1,0,1),
            ('fizik','Fizik','Ara Sınıf',1,0,2),
            ('lgs_matematik','LGS Matematik','LGS',1,0,3),
            ('ozel_deneme','Özel Deneme','YKS',0,1,4),
        ])
        c.executemany('INSERT INTO ogrenci VALUES(?,?,?)', [
            (1,'YKS','12-say'), (2,'LGS','8.sınıf'),
        ])
        c.execute("INSERT INTO kitap(ders,ad) VALUES('tyt_matematik','Test Kitabı')")
        c.execute("INSERT INTO ogrenci_kitap(ogrenci_id,ders,kitap_ad) VALUES(1,'tyt_matematik','Test Kitabı')")
        c.execute("INSERT INTO odev(ogrenci_id,ders) VALUES(1,'tyt_matematik')")
        c.execute("INSERT INTO odev_satir(ogrenci_id,ders) VALUES(1,'fizik')")
        c.execute("INSERT INTO koc_konu_takip(ogrenci_id,ders_adi) VALUES(1,'Matematik (TYT)')")
        c.execute("INSERT INTO koc_konu_takip(ogrenci_id,ders_adi) VALUES(1,'Matematik')")
        c.execute("INSERT INTO koc_konu_takip(ogrenci_id,ders_adi) VALUES(2,'LGS Matematik')")
        c.executemany("INSERT INTO tyt_matematik(konu) VALUES(?)", [('Üslü Sayılar',),('Köklü Sayılar',)])
        c.execute("INSERT INTO fizik(konu) VALUES('Hız')")
        c.execute("INSERT INTO lgs_matematik(konu) VALUES('Oran')")
    return db_path


def snapshot(path, group):
    defaults, standard = constants()
    return inspect_group_curriculum(path, group, group_defaults=defaults, standard_groups=standard)


def test_default_group_uses_shared_contract_and_preserves_file(tiny_db):
    before = hashlib.sha256(tiny_db.read_bytes()).hexdigest()
    res = snapshot(tiny_db, '12-say')
    after = hashlib.sha256(tiny_db.read_bytes()).hexdigest()
    assert before == after
    assert res.student_count == 1 and res.main_group == 'YKS'
    assert res.assignment_mode == 'Varsayılan'
    tyt = next(r for r in res.rows if r.lesson_id == 'tyt_matematik')
    assert tyt.assigned and tyt.active and tyt.topic_count == 2
    assert (tyt.pool_books, tyt.assigned_books, tyt.homework, tyt.coaching_topics) == (1,1,1,1)
    assert any('Matematik (1)' in x for x in res.warnings)
    assert any('otomatik' in x.lower() for x in res.notices)


def test_lgs_students_are_not_counted_as_yks(tiny_db):
    result = snapshot(tiny_db, '8.sınıf')
    tyt = next(r for r in result.rows if r.lesson_id == 'tyt_matematik')
    lgs = next(r for r in result.rows if r.lesson_id == 'lgs_matematik')
    assert not tyt.assigned and tyt.assigned_books == 0 and tyt.homework == 0
    assert lgs.assigned and lgs.coaching_topics == 1


def test_custom_mapping_disabled_and_unknown_lesson_are_not_silently_used(tiny_db):
    with sqlite3.connect(tiny_db) as c:
        c.executemany('INSERT INTO grup_dersleri VALUES(?,?)', [
            ('12-say','fizik'), ('12-say','kayip_kod'), ('12-say','ozel_deneme')
        ])
    result = snapshot(tiny_db, '12-say')
    assert result.assignment_mode == 'Gruba özel'
    assert next(r for r in result.rows if r.lesson_id == 'fizik').assigned
    assert not next(r for r in result.rows if r.lesson_id == 'ozel_deneme').assigned
    assert any('kayip_kod' in warning for warning in result.warnings)
    assert any('ozel_deneme' in notice for notice in result.notices)
    assert any('grup dersleri dışında' in notice.lower() for notice in result.notices)


def test_missing_db_cannot_create_file(tmp_path):
    path = tmp_path / 'not_exists.sqlite'
    with pytest.raises(FileNotFoundError):
        snapshot(path, '12-say')
    assert not path.exists()


def test_missing_catalog_fails_closed(tmp_path):
    path = tmp_path / 'legacy.sqlite'
    with sqlite3.connect(path) as c:
        c.execute('CREATE TABLE ogrenci (id INTEGER PRIMARY KEY,alt_grup TEXT)')
    with pytest.raises(ValueError, match='Ders veya öğrenci tabloları'):
        snapshot(path,'8.sınıf')


def test_aliases_are_conservative_and_turkish_search_is_robust():
    assert _normal_key('Matematik (TYT)') == _normal_key('TYT Matematik')
    assert _normal_key('Matematik') != _normal_key('TYT Matematik')
    assert search_key('FİZİK') == search_key('fizik')
    assert search_key('IŞIK') == search_key('ışık')


def test_ui_added_in_separate_file_without_homework_writes():
    src = (ROOT/'ui'/'curriculum_page.py').read_text()
    assert 'Bağlantı Kontrolü' in src
    assert 'self.tab_integration.refresh()' in src
    widget_src = (ROOT/'ui'/'curriculum_integration_page_v38.py').read_text()
    assert 'set_lessons_for_group(' not in widget_src
    assert 'update_lesson_status(' not in widget_src
    assert 'DELETE FROM' not in widget_src


def test_v37_untouched_core_guard_remains():
    import json
    expected = json.loads((ROOT/'tests'/'v37_protected_core_hashes.json').read_text())
    for path, h in expected.items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == h
