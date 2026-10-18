from __future__ import annotations
"""V39 ders seçimi: gerçek uygulama DB'sini değiştirmeyen sentetik regresyon testleri."""
import hashlib
import sqlite3
from pathlib import Path
import pytest
from services.lesson_catalog_v39 import (
    read_lesson_options, resolve_lesson_code, inspect_lesson_identities, token_key
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def trial_db(tmp_path):
    path = tmp_path / 'lessons.sqlite'
    with sqlite3.connect(path) as c:
        c.executescript('''
        CREATE TABLE ders_tanimlari (id TEXT PRIMARY KEY,ad TEXT,grup TEXT,aktif INTEGER,ozel INTEGER,siralama INTEGER);
        CREATE TABLE kitap (id INTEGER PRIMARY KEY, ders TEXT, ad TEXT);
        CREATE TABLE ogrenci_kitap (id INTEGER PRIMARY KEY, ders TEXT, ogrenci_id INTEGER);
        CREATE TABLE odev (id INTEGER PRIMARY KEY, ders TEXT);
        CREATE TABLE odev_satir (id INTEGER PRIMARY KEY, ders TEXT);
        CREATE TABLE koc_konu_takip (id INTEGER PRIMARY KEY, ders_adi TEXT);
        ''')
        c.executemany('INSERT INTO ders_tanimlari VALUES(?,?,?,?,?,?)', [
            ('tyt_matematik', 'TYT Matematik', 'YKS', 1, 0, 1),
            ('ayt_matematik', 'AYT Matematik', 'YKS', 1, 0, 2),
            ('fizik', 'Fizik', 'Ara Sınıf', 0, 0, 3),
            ('ozel_kurs', 'Kurs İçin Özel', 'YKS', 1, 1, 4),
            ('lgs_fen', 'LGS Fen', 'LGS', 1, 0, 5),
            ('ozel_kapali', 'Kapatılmış Ders', 'YKS', 0, 1, 6),
        ])
        c.execute("INSERT INTO kitap(ders,ad) VALUES('fizik','Fizik Soru Bankası')")
        c.execute("INSERT INTO ogrenci_kitap(ders,ogrenci_id) VALUES('ozel_kurs',1)")
        c.execute("INSERT INTO odev(ders) VALUES('ozel_kurs')")
        c.execute("INSERT INTO odev_satir(ders) VALUES('tarihi_ders')")
        c.executemany('INSERT INTO koc_konu_takip(ders_adi) VALUES(?)', [
            ('Matematik (TYT)',), ('Matematik',), ('Matematik (AYT)',),
            ('TYT Matematik',), ('Kurs İçin Özel',), ('Bilinmeyen',)
        ])
    return path


def read(path, legacy=('tyt_matematik', 'ayt_matematik', 'fizik', 'lgs_fen')):
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as con:
        return read_lesson_options(con, legacy=legacy,
                                   history_sources=('kitap', 'odev', 'odev_satir'))


def test_active_and_custom_options(trial_db):
    opts = read(trial_db)
    assert 'ozel_kurs' in {o.code for o in opts}
    assert next(o for o in opts if o.code == 'tyt_matematik').label.startswith('TYT Matematik')
    assert next(o for o in opts if o.code == 'ozel_kurs').name == 'Kurs İçin Özel'


def test_historic_inactive_and_ghost_codes_visible(trial_db):
    opts = read(trial_db)
    assert next(o for o in opts if o.code == 'fizik').active is False
    assert next(o for o in opts if o.code == 'fizik').historic
    assert next(o for o in opts if o.code == 'tarihi_ders').catalogued is False
    assert 'ozel_kapali' not in {o.code for o in opts}
    assert len({o.code for o in opts}) == len(opts)


def test_book_only_catalog_retains_book_past(trial_db):
    with sqlite3.connect(trial_db) as con:
        opts = read_lesson_options(con, legacy=['fizik'], history_sources=['kitap'])
    assert 'fizik' in {o.code for o in opts}
    assert 'tarihi_ders' not in {o.code for o in opts}


def test_case_unicode_and_strict_alias(trial_db):
    opts = read(trial_db)
    assert resolve_lesson_code('TYT MATEMATİK', opts) == 'tyt_matematik'
    assert resolve_lesson_code('Matematik (TYT)', opts) == 'tyt_matematik'
    assert resolve_lesson_code('Matematik (AYT)', opts) == 'ayt_matematik'
    assert resolve_lesson_code('Matematik', opts) is None
    assert resolve_lesson_code('fizik', opts) == 'fizik'
    assert resolve_lesson_code('Kurs İçin Özel', opts) == 'ozel_kurs'
    assert resolve_lesson_code('Bilinmeyen', opts) is None
    assert token_key('IŞIK') == token_key('ışık')


def test_exact_label_round_trip(trial_db):
    opts = read(trial_db)
    assert all(resolve_lesson_code(opt.label, opts) == opt.code for opt in opts)


def test_collision_does_not_guess(tmp_path):
    db = tmp_path / 'collision.db'
    with sqlite3.connect(db) as c:
        c.execute('CREATE TABLE ders_tanimlari(id TEXT,ad TEXT,aktif INT,siralama INT)')
        c.executemany('INSERT INTO ders_tanimlari VALUES(?,?,1,1)',
                      [('test_a','Test Ders'),('test_b','Ders Test')])
        opts = read_lesson_options(c)
    assert resolve_lesson_code('Test Ders', opts) is None  # aynı token seti: belirsiz
    assert resolve_lesson_code('test_a', opts) == 'test_a'


def test_coaching_uncertain_remains_uncertain(trial_db):
    with sqlite3.connect(trial_db) as con:
        snap = inspect_lesson_identities(con, legacy=['tyt_matematik'])
    matches = dict(snap.coaching_counts)
    assert matches['tyt_matematik'] == 2
    assert matches['ayt_matematik'] == 1
    assert matches['ozel_kurs'] == 1
    assert dict(snap.unresolved_coaching) == {'Bilinmeyen': 1, 'Matematik': 1}
    assert snap.total_coaching == 6
    assert snap.legacy_codes == ('tarihi_ders',)


def test_readonly_does_not_modify_bytes(trial_db):
    before = hashlib.sha256(trial_db.read_bytes()).hexdigest()
    with sqlite3.connect(f'file:{trial_db}?mode=ro', uri=True) as con:
        con.execute('PRAGMA query_only=ON')
        inspect_lesson_identities(con, legacy=['tyt_matematik'])
    assert hashlib.sha256(trial_db.read_bytes()).hexdigest() == before


def test_schema_without_catalog_falls_back_to_legacy(tmp_path):
    path = tmp_path/'old.db'
    with sqlite3.connect(path) as con:
        con.execute('CREATE TABLE odev_satir(ders TEXT)')
        con.execute("INSERT INTO odev_satir VALUES('ozel_eski')")
        opts = read_lesson_options(con, legacy=['tyt_matematik'], history_sources=['odev_satir'])
    assert [x.code for x in opts] == ['tyt_matematik','ozel_eski']


def test_absent_data_table_is_tolerated(tmp_path):
    path = tmp_path/'old.db'
    with sqlite3.connect(path) as con:
        options = read_lesson_options(con, legacy=['lgs_fen'], history_sources=['odev'])
    assert [x.code for x in options] == ['lgs_fen']


def test_untrusted_history_sources_rejected(tmp_path):
    with sqlite3.connect(':memory:') as con:
        with pytest.raises(ValueError):
            read_lesson_options(con, history_sources=['ogrenci; DROP TABLE ders_tanimlari'])


def test_book_report_store_codes_not_display_labels():
    book_src = (ROOT/'ui'/'book_dialog.py').read_text(encoding='utf-8')
    report_src = (ROOT/'ui'/'reports.py').read_text(encoding='utf-8')
    assert 'addItem(option.label, option.code)' in book_src
    assert 'self.cmbDers.currentData()' in book_src
    assert 'self.cmbDers.currentText()' in book_src  # only legacy fallback
    assert 'it.setData(0x0100, option.code)' in report_src
    assert 'out.append(str(it.data(0x0100)))' in report_src


def test_protected_homework_and_control_code_unchanged():
    import json
    expected = json.loads((ROOT/'tests'/'v37_protected_core_hashes.json').read_text())
    for rel, digest in expected.items():
        assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest() == digest
