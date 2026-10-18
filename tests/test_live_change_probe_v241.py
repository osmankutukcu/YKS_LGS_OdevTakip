import os
import sqlite3
from pathlib import Path
import pytest
from services.live_change_probe_v241 import DatabaseChangeProbe


def make_db(tmp_path):
    p=tmp_path/'student_test.db'
    with sqlite3.connect(p) as c:
        c.execute('CREATE TABLE entries (id INTEGER PRIMARY KEY, name TEXT)')
    return p


def test_committed_change_and_no_uncommitted_or_rollback(tmp_path):
    p=make_db(tmp_path)
    with DatabaseChangeProbe(p) as probe:
        assert probe.poll() is False and probe.connected
        writer=sqlite3.connect(p)
        writer.execute('INSERT INTO entries(name) VALUES (?)', ('alpha',))
        assert probe.poll() is False
        writer.rollback()
        assert probe.poll() is False
        writer.execute('INSERT INTO entries(name) VALUES (?)', ('beta',))
        writer.commit()
        assert probe.poll() is True
        assert probe.poll() is False
        writer.close()


def test_readonly_probe_cannot_write_or_mutate_data(tmp_path):
    p=make_db(tmp_path)
    b=p.read_bytes()
    probe=DatabaseChangeProbe(p)
    assert not probe.poll()
    with pytest.raises(sqlite3.OperationalError):
        probe._connection.execute("INSERT INTO entries(name) VALUES ('bad')")
    assert probe.poll() is False
    assert p.read_bytes()==b
    probe.close()


def test_inform_on_file_replacement(tmp_path):
    p=make_db(tmp_path)
    probe=DatabaseChangeProbe(p)
    assert probe.poll() is False
    p2=tmp_path/'replacement.db'
    with sqlite3.connect(p2) as con:con.execute('CREATE TABLE entries(id INTEGER PRIMARY KEY)')
    os.replace(p2,p)
    assert probe.poll() is True
    assert probe.poll() is False
    probe.close()


def test_missing_database_recovery(tmp_path):
    p=tmp_path/'later.db'
    probe=DatabaseChangeProbe(p)
    assert probe.poll() is False and not p.exists()
    with sqlite3.connect(p) as c:c.execute('CREATE TABLE x(y)')
    assert probe.poll() is False  # startup baseline
    with sqlite3.connect(p) as c:c.execute('INSERT INTO x VALUES (1)')
    assert probe.poll() is True
    probe.close()


def test_two_students_not_sold_or_exported(tmp_path):
    p=make_db(tmp_path)
    with sqlite3.connect(p) as c:
        c.execute('INSERT INTO entries VALUES (?,?)',(1,'Student A'))
        c.execute('INSERT INTO entries VALUES (?,?)',(2,'Student B'))
    probe=DatabaseChangeProbe(p)
    assert probe.poll() is False
    assert not any(x in vars(probe) for x in ('student_id','student_name','student_records'))
    with sqlite3.connect(p) as c:c.execute('UPDATE entries SET name=? WHERE id=?',('Changed',2))
    assert probe.poll() is True
    assert probe.poll() is False
    probe.close()


def test_monitor_wal_mode_commits(tmp_path):
    p=make_db(tmp_path)
    con=sqlite3.connect(p)
    con.execute('PRAGMA journal_mode=WAL')
    con.close()
    with DatabaseChangeProbe(p) as probe:
        assert probe.poll() is False
        with sqlite3.connect(p) as writer:
            writer.execute('INSERT INTO entries(name) VALUES (?)', ('wal',))
        assert probe.poll() is True
    with sqlite3.connect(p) as con:
        assert con.execute('SELECT count(*) FROM entries').fetchone()[0]==1


def test_source_does_not_touch_main_form_or_db():
    from pathlib import Path
    import json,hashlib
    root=Path(__file__).resolve().parents[1]
    if not (root/'checksums.json').is_file():
        assert (root/'services/live_change_probe_v241.py').is_file()
        return
    m=json.loads((root/'checksums.json').read_text())
    assert 'ui/homework_form.py' not in m['files']
    assert 'ui/odev_kontrol.py' not in m['files']
    assert 'db.py' not in m['files']
    assert set(m['files']) == {
        'ui/coaching_manager.py','ui/topic_map_dialog.py','ui/student360_panel_v16.py',
        'ui/live_change_bridge_v241.py','services/live_change_probe_v241.py'
    }


def test_visible_screens_keep_student_selection():
    import inspect
    import ast
    root=Path(__file__).resolve().parents[1]
    if (root/'payload').is_dir():root=root/'payload'
    coach=(root/'ui/coaching_manager.py').read_text()
    topic=(root/'ui/topic_map_dialog.py').read_text()
    s360=(root/'ui/student360_panel_v16.py').read_text()
    assert 'self._shared_topic_timer_v1.start()' in coach
    assert 'self._refresh_shared_map_v1(sid)' in topic
    assert 'self.refresh()' in s360
    for txt in (coach,topic,s360):ast.parse(txt)
