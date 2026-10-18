"""No Qt dependency: actual SQLite and existing adviser bridging invariants."""
import hashlib
import sqlite3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.live_student_summary_v3 import SQLiteChangeMonitor, read_coach_glance


def test_coaching_student_isolation_and_same_v27_model():
    con = sqlite3.connect(':memory:')
    con.execute('CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, ad TEXT)')
    con.execute("INSERT INTO ogrenci VALUES (7,'Bir')")
    con.execute('PRAGMA query_only=ON')
    before = con.total_changes
    def valid(c, sid):
        assert c.row_factory is sqlite3.Row
        assert sid == 7
        return {'student_id': 7, 'evidence_count': 0, 'status': 'Ölçüm gerekli',
                'actions': [], 'guidance':'Bağımsız ölçüm yapın', 'warnings': [], 'as_of':'2026-10-15'}
    data = read_coach_glance(con, 7, provider=valid)
    assert 'Ölçüm' in data.status and data.evidence_count == 0
    assert 'Bağımsız' in data.next_step
    assert con.total_changes == before
    assert con.row_factory is None
    def wrong(c, sid):
        return {'student_id': 8}
    try:
        read_coach_glance(con,7,provider=wrong)
    except ValueError:
        pass
    else:
        raise AssertionError('wrong student accepted')
    assert con.row_factory is None


def test_advisory_failure_does_not_leak_factory():
    con = sqlite3.connect(':memory:')
    def failure(c, sid):
        raise sqlite3.OperationalError('optional table unavailable')
    try:
        read_coach_glance(con, 7, provider=failure)
    except sqlite3.OperationalError:
        pass
    else:
        raise AssertionError('expected error')
    assert con.row_factory is None
    con.close()


def test_persistent_sqlite_data_version_detects_other_connection(tmp_path):
    db = tmp_path/'test.db'
    conn = sqlite3.connect(db)
    conn.execute('CREATE TABLE work (id INTEGER PRIMARY KEY, value TEXT)')
    conn.commit()
    monitor = SQLiteChangeMonitor(db)
    try:
        assert monitor.poll() is False
        assert monitor.poll() is False
        with sqlite3.connect(db) as second:
            second.execute("INSERT INTO work(value) VALUES ('first')")
        assert monitor.poll() is True
        assert monitor.poll() is False
        with sqlite3.connect(db) as second:
            second.execute("UPDATE work SET value='next' WHERE id=1")
        assert monitor.poll() is True
    finally:
        monitor.close()
        conn.close()


def test_sqlite_replacement_detected_without_old_student_data(tmp_path):
    db = tmp_path/'test.db'
    with sqlite3.connect(db) as c:
        c.execute('CREATE TABLE work (n int)')
    monitor = SQLiteChangeMonitor(db)
    assert monitor.poll() is False
    monitor.close()
    replacement = tmp_path/'replace.db'
    with sqlite3.connect(replacement) as c:
        c.execute('CREATE TABLE other (n int)')
    replacement.replace(db)
    assert monitor.poll() is True
    monitor.close()


def test_core_v2_form_not_modified_by_v3():
    v3 = Path(__file__).resolve().parents[1]
    from hashlib import sha256
    assert sha256((v3/'ui/homework_form.py').read_bytes()).hexdigest() == '53e6b12db96cf81fd622947e7d343b4130a1a8e42a0e30d5c5ec58e64e456314'
    for name in ('_tik_degisti', '_kaydet_kume', '_is_locked_index'):
        assert name in (v3/'ui/homework_form.py').read_text(encoding='utf-8')


def test_v3_optional_ui_only_not_touching_checkbox_or_network():
    base = Path(__file__).resolve().parents[1]
    panel = (base/'ui/student_workspace_panel_v21.py').read_text(encoding='utf-8')
    bridge = (base/'ui/homework_workspace_bridge_v21.py').read_text(encoding='utf-8')
    connector = (base/'services/live_student_summary_v3.py').read_text(encoding='utf-8')
    assert 'self.form.btnKontrol.click()' in bridge
    assert 'btn.click()  # Reuse the *existing* V25 analysis path.' in bridge
    assert 'read_coach_glance(con, sid)' in panel
    assert "setInterval(15000)" in panel
    for code in (panel, bridge, connector):
        assert 'UPDATE odev ' not in code
        assert 'INSERT INTO odev ' not in code
        assert 'requests.get(' not in code


def test_unicode_sqlite_filename_support(tmp_path):
    p=tmp_path/'Türkçe soru dosyası.db'
    with sqlite3.connect(p) as con:
        con.execute('CREATE TABLE data(k TEXT)')
    watcher=SQLiteChangeMonitor(p)
    try:
        assert watcher.poll() is False
        with sqlite3.connect(p) as con:
            con.execute("INSERT INTO data VALUES('Öğrenci')")
        assert watcher.poll() is True
    finally:
        watcher.close()
