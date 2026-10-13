import sqlite3
from pathlib import Path
import pytest
from services.target_analysis_v24.student_target import read_saved_target


def test_student360_target_is_individual_and_read_only(tmp_path):
    db=tmp_path/'test.db'
    con=sqlite3.connect(db)
    con.execute('CREATE TABLE ogrenci(id INTEGER PRIMARY KEY,hedef_bolum TEXT,hedef_tyt REAL,hedef_ayt REAL,hedef_lgs REAL)')
    con.execute('INSERT INTO ogrenci VALUES (1,?,?,?,?)',('Tıp',90,55,0))
    con.execute('INSERT INTO ogrenci VALUES (2,?,?,?,?)',('Lise',0,0,75))
    con.commit();con.close()
    con=sqlite3.connect(f'file:{db}?mode=ro',uri=True)
    assert 'Tıp' in read_saved_target(con,1)
    assert 'Lise' not in read_saved_target(con,1)
    assert '75' in read_saved_target(con,2)
    with pytest.raises(ValueError): read_saved_target(con,0)
    assert con.execute('SELECT COUNT(*) FROM ogrenci').fetchone()[0]==2
    con.close()


def test_older_database_without_target_columns_safe():
    with sqlite3.connect(':memory:') as con:
        con.execute('CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, ad TEXT)')
        assert 'bulunmuyor' in read_saved_target(con,1)


def test_student360_uses_target_reader_but_not_write():
    r=Path(__file__).parents[1]/'ui'
    for name in ('student360_panel_v16.py','student_workspace_panel_v21.py'):
        txt=(r/name).read_text(encoding='utf-8')
        assert 'read_saved_target(con, sid)' in txt
        assert 'UPDATE ogrenci SET hedef' not in txt
