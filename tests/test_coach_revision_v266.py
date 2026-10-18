"""V26.6 revision observation: pure tests, no Qt, no student DB updates."""
from pathlib import Path
import ast
import hashlib
import sqlite3

from services.coach_assistant_v1.revision_watch_v266 import (
    RevisionWatch, get_revision, known_revision, changed_during_read,
)


class Clock:
    def __init__(self):
        self.t = 0.0
    def __call__(self):
        return self.t
    def advance(self, seconds):
        self.t += seconds


def test_new_revision_requires_quiet_period_then_one_notification():
    c = Clock()
    w = RevisionWatch(clock=c, quiet_seconds=2, cooldown_seconds=45)
    before, after = ((100, 7), None), ((110, 15), None)
    assert not w.observe(before)
    c.advance(1)
    assert not w.observe(after)
    c.advance(1.5)
    assert not w.observe(after)
    c.advance(0.6)
    assert w.observe(after)
    assert not w.observe(after)


def test_coalescing_discards_middle_writes_and_requires_stability():
    c = Clock()
    w = RevisionWatch(clock=c)
    base = ((100, 7), None)
    a = ((101, 7), None)
    b = ((102, 7), None)
    assert not w.observe(base)
    c.advance(1)
    assert not w.observe(a)
    c.advance(1)
    assert not w.observe(b)
    c.advance(1.1)
    assert not w.observe(b)
    c.advance(1)
    assert w.observe(b)


def test_cooldown_and_student_switch_reset():
    c = Clock()
    w = RevisionWatch(clock=c, quiet_seconds=0, cooldown_seconds=60)
    a, b, d = ((100, 1), None), ((110, 1), None), ((120, 1), None)
    w.observe(a)
    assert not w.observe(b)
    assert w.observe(b)
    assert not w.observe(d)
    assert not w.observe(d)  # cooldown
    c.advance(61)
    assert w.observe(d)
    w.reset(a)
    assert not w.observe(b)
    assert w.observe(b)


def test_transient_file_error_never_triggers_fake_update():
    c = Clock()
    w = RevisionWatch(clock=c, quiet_seconds=1)
    base = ((10, 100), None)
    next_rev = ((20, 100), None)
    w.observe(base)
    assert not w.observe(None)
    c.advance(2)
    assert not w.observe(next_rev)
    c.advance(1)
    assert w.observe(next_rev)
    assert not known_revision((None, None))
    assert not changed_during_read(None, next_rev)
    assert changed_during_read(base, next_rev)


def test_real_sqlite_commit_changes_db_or_wal_stamp(tmp_path):
    db = tmp_path / 'studentless.sqlite'
    with sqlite3.connect(db) as con:
        con.execute('CREATE TABLE sample (value TEXT)')
        con.execute("INSERT INTO sample VALUES ('a')")
    prev = get_revision(db)
    assert known_revision(prev)
    with sqlite3.connect(db) as con:
        con.execute("INSERT INTO sample VALUES ('b')")
    later = get_revision(db)
    assert changed_during_read(prev, later)
    missing = get_revision(tmp_path / 'absent.sqlite')
    assert not known_revision(missing)


def test_commit_in_wal_changes_stamps_without_writes_from_guard(tmp_path):
    db = tmp_path / 'wal.sqlite'
    with sqlite3.connect(db) as con:
        con.execute('PRAGMA journal_mode=WAL')
        con.execute('CREATE TABLE sample (i INTEGER)')
    with sqlite3.connect(db) as con:
        con.execute('PRAGMA journal_mode=WAL')
        before = get_revision(db)
        con.execute('INSERT INTO sample VALUES (2)')
        con.commit()
        after = get_revision(db)
        assert changed_during_read(before, after)
        with sqlite3.connect(f'{db.as_uri()}?mode=ro', uri=True) as observer:
            observer.execute('PRAGMA query_only=ON')
            assert observer.execute('SELECT COUNT(*) FROM sample').fetchone()[0] == 1


def test_integration_does_not_modify_protected_form_or_records():
    root = Path(__file__).resolve().parents[1]
    # Pinned from V26.5, so protection also works after ZIP is moved to Windows/Mac.
    protected_hashes = {
        'ui/homework_form.py': '53e6b12db96cf81fd622947e7d343b4130a1a8e42a0e30d5c5ec58e64e456314',
        'db.py': '8b295f375a18b41bdb92f120170bafb9a2cb93863be9e98b789241ceb32c4d6b',
        'services/student_workspace_v21.py': '7f9f64c09723938a9bf9bb34712a2bc18101c67527bc5cac129e1cb06e17c49f',
        'ui/adaptive_coaching_center_v26.py': 'f93056b4df379e702572495198e3cd116bb8a0af351e9acedc62841209feb646',
        'ui/smart_coach_secretary_toast.py': (
            '6f48b901c3449a0612c16058bc40e6a74a797ee594d34e417970e6f5f7758ae9',
            'c3d06192cd979a7b6c478d75a4c96f85d9f0509eec05424c978204ce64850329',
        ),
    }
    for protected, expected in protected_hashes.items():
        actual = hashlib.sha256((root / protected).read_bytes()).hexdigest()
        if isinstance(expected, tuple):
            assert actual in expected, protected
        else:
            assert actual == expected, protected
    source = (root/'ui/coach_dialogue_v121.py').read_text()
    assert 'coach_revision_changed_v266' in source
    assert 'get_revision(DB_PATH)' in source
    assert 'self._retry_changed_read' in source
    assert 'self.setFixedWidth(430)' in source
    assert 'self.setFixedHeight(405)' in source
    assert 'PRAGMA query_only=ON' in source
    ast.parse(source)
