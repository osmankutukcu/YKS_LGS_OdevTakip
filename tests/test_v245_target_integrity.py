"""V24.5: okuma/kimlik/yerleşim; gerçek öğrenci verisi kullanılmaz."""
from __future__ import annotations
import json
import hashlib
import sqlite3
from datetime import date
from pathlib import Path
import pytest

from services.target_analysis_v24.integrity_audit_v245 import audit_goal_sources, render_goal_audit
from services.target_analysis_v24.history_location_v245 import resolve_history_location
from services.target_analysis_v24.program_catalog_v242 import PROVENANCE


def setup_main(tmp_path):
    path=tmp_path/'main.db'
    con=sqlite3.connect(path)
    con.executescript('''
      CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, hedef_bolum TEXT,
        hedef_tyt REAL, hedef_ayt REAL, hedef_lgs REAL);
      INSERT INTO ogrenci VALUES (1,'Tıp',75,40,0);
      INSERT INTO ogrenci VALUES (2,'Mimarlık',65,35,0);
    ''')
    con.commit();con.close()
    return path


def setup_trend(tmp_path):
    path=tmp_path/'deneme_history.db'
    con=sqlite3.connect(path)
    con.executescript('''
      CREATE TABLE deneme_student_v24(id INTEGER PRIMARY KEY,
        student_id INTEGER, d TEXT, exam TEXT, alan TEXT, payload TEXT,source_key TEXT);
      INSERT INTO deneme_student_v24 VALUES (1,1,'2026-10-01','YKS','SAY','{"net": 42}','exam_1');
      INSERT INTO deneme_student_v24 VALUES (2,2,'2026-10-01','YKS','EA','{"net": 12}','exam_2');
    ''')
    con.commit();con.close()
    return path


def setup_catalog(tmp_path, bad=False):
    p=tmp_path/'catalog.db'
    con=sqlite3.connect(p)
    con.execute('''CREATE TABLE program_reference_v242(
      year INTEGER,program_code TEXT,source TEXT,payload TEXT,source_label TEXT)''')
    row={'year':2026,'program_code':'12345678','source':'OSYM'}
    con.execute('INSERT INTO program_reference_v242 VALUES (?,?,?,?,?)',(
        2026, '12345678', 'OSYM', json.dumps(row), 'fake_official' if bad else PROVENANCE))
    con.commit();con.close()
    return p


def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def test_readonly_and_student_scoped_counts(tmp_path):
    main=setup_main(tmp_path)
    trend=setup_trend(tmp_path)
    catalog=setup_catalog(tmp_path)
    before={p:digest(p) for p in (main,trend,catalog)}
    r=audit_goal_sources(main, 1, trend_db=trend,catalog_db=catalog,selected_year=2026)
    assert r.student_id==1 and r.trend_rows==1 and r.public_catalog_rows==1
    assert r.target_set and not r.has_blocker
    assert 'bağımsız resmî doğrulama' in render_goal_audit(r)
    assert {p:digest(p) for p in before}==before
    r2=audit_goal_sources(main,2,trend_db=trend,selected_year=2025)
    assert r2.trend_rows==1 and r2.public_catalog_rows==0
    assert 'Tıp' not in render_goal_audit(r2)


def test_invalid_student_ids(tmp_path):
    main=setup_main(tmp_path)
    for sid in ('1',True,0,-5,None):
        with pytest.raises(ValueError): audit_goal_sources(main,sid)
    for year in (-1,'2025',2099,True):
        with pytest.raises(ValueError): audit_goal_sources(main,1,selected_year=year)


def test_missing_main_does_not_create_database(tmp_path):
    p=tmp_path/'unknown.db'
    out=audit_goal_sources(p,1)
    assert out.has_blocker and not p.exists()
    assert any(f.code=='MAIN_DB_MISSING' for f in out.findings)


def test_missing_optional_dbs_no_create(tmp_path):
    main=setup_main(tmp_path)
    trend=tmp_path/'missing.db'
    catalog=tmp_path/'missing_catalog.db'
    r=audit_goal_sources(main,1,trend_db=trend,catalog_db=catalog)
    assert {f.code for f in r.findings}>={'TREND_MISSING','CATALOG_MISSING'}
    assert not trend.exists() and not catalog.exists()


def test_corrupt_trend_and_catalog_marked_not_accepted(tmp_path):
    main=setup_main(tmp_path)
    trend=setup_trend(tmp_path)
    catalog=setup_catalog(tmp_path,bad=True)
    con=sqlite3.connect(trend)
    con.execute("UPDATE deneme_student_v24 SET payload='not json' WHERE id=1")
    con.commit();con.close()
    r=audit_goal_sources(main,1,trend_db=trend,catalog_db=catalog,selected_year=2026)
    assert {'TREND_CORRUPT','CATALOG_MISMATCH'} <= {f.code for f in r.findings}


def test_wrong_student_not_trusted(tmp_path):
    main=setup_main(tmp_path)
    r=audit_goal_sources(main,3)
    assert r.has_blocker and any(f.code=='STUDENT_NOT_FOUND' for f in r.findings)


def test_invalid_net_range_not_automatically_fixed(tmp_path):
    main=setup_main(tmp_path)
    con=sqlite3.connect(main)
    con.execute('UPDATE ogrenci SET hedef_tyt=999 WHERE id=1')
    con.commit();con.close()
    before=digest(main)
    r=audit_goal_sources(main,1)
    assert 'TARGET_INVALID' in {f.code for f in r.findings}
    assert digest(main)==before


def test_old_schema_rejected_without_mutation(tmp_path):
    main=tmp_path/'old.db'
    con=sqlite3.connect(main);con.execute('CREATE TABLE ogrenci(id INTEGER PRIMARY KEY)');con.commit();con.close()
    r=audit_goal_sources(main,1)
    assert r.has_blocker and 'TARGET_SCHEMA' in {f.code for f in r.findings}


def test_history_existing_legacy_preserved(tmp_path):
    root=tmp_path/'newfolder';root.mkdir()
    main=root/'veritabani.db'
    local=tmp_path/'Local'
    legacy=local/'YKS_LGS_HomeworkManager'/'deneme_history.db'
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b'old')
    result=resolve_history_location(main,local_app_data=local)
    assert result.selected==legacy and not result.conflict
    assert not result.canonical.exists()


def test_history_new_install_uses_main_location(tmp_path):
    main=tmp_path/'main'/'veritabani.db'
    result=resolve_history_location(main,local_app_data=tmp_path/'Local')
    assert result.selected==main.parent/'deneme_history.db'
    assert not result.selected.exists()


def test_history_both_paths_conflict_and_no_moves(tmp_path):
    main=tmp_path/'main'/'db.sqlite'
    result=resolve_history_location(main,local_app_data=tmp_path/'Local')
    result.canonical.parent.mkdir(parents=True)
    result.legacy.parent.mkdir(parents=True)
    result.canonical.write_bytes(b'current')
    result.legacy.write_bytes(b'legacy')
    again=resolve_history_location(main,local_app_data=tmp_path/'Local')
    assert again.conflict and again.selected==again.legacy
    assert again.canonical.read_bytes()==b'current'
    assert again.legacy.read_bytes()==b'legacy'


def test_no_unexpected_gui_db_writes_in_wiring():
    p=Path(__file__).resolve().parents[1]
    ui=(p/'ui'/'target_goal_audit_v245.py').read_text()
    bridge=(p/'ui'/'target_coaching_brief_v243.py').read_text()
    assert 'get_db_path' not in ui and 'Path(db.DB_PATH)' in ui
    assert 'TargetGoalAuditDialog(self.student_id' in bridge
    assert 'query_only=ON' in (p/'services'/'target_analysis_v24'/'integrity_audit_v245.py').read_text()


def test_degenerate_trend_schema_warning(tmp_path):
    main=setup_main(tmp_path)
    trend=tmp_path/'trend.db'
    con=sqlite3.connect(trend);con.execute('CREATE TABLE deneme_student_v24(student_id INTEGER)');con.commit();con.close()
    r=audit_goal_sources(main,1,trend_db=trend)
    assert 'TREND_SCHEMA' in {f.code for f in r.findings}
