"""V26.9.3: a missing revision proof must never certify a Koça Sor answer.

No real student database, network access, Qt imports or UI rendering required.
"""
from __future__ import annotations

import ast
from pathlib import Path

from services.coach_assistant_v1.revision_watch_v266 import (
    known_revision, changed_during_read,
)

ROOT = Path(__file__).resolve().parents[1]


def test_revision_proof_requires_known_database_metadata():
    valid = ((123456, 1024), None)
    assert known_revision(valid)
    assert not known_revision(None)
    assert not known_revision((None, None))
    assert not known_revision((None, (123456, 1024)))


def test_unchanged_known_revision_is_not_a_change():
    base = ((123456, 1024), None)
    assert not changed_during_read(base, base)
    assert changed_during_read(base, ((123457, 1024), None))


def test_worker_and_delivery_both_fail_closed_on_unverifiable_metadata():
    source = (ROOT / 'ui/coach_dialogue_v121.py').read_text(encoding='utf-8')
    ast.parse(source)
    # The first check protects the worker's DB read. The second check protects
    # the Qt signal delivery, after an asynchronous delay.
    assert 'not known_revision(start_revision)' in source
    assert 'not known_revision(self.finish_revision)' in source
    assert 'not known_revision(task.finish_revision)' in source
    assert 'not known_revision(current_revision)' in source
    assert "error = 'coach_revision_changed_v266'" in source
    assert 'self.setFixedWidth(430)' in source
    assert 'self.setFixedHeight(405)' in source
    assert 'PRAGMA query_only=ON' in source


def test_release_does_not_change_homework_write_paths():
    # Stable hashes pinned in previous V26.9.2 tests. Existing guards still run.
    import hashlib
    expected = {
        'ui/homework_form.py': '53e6b12db96cf81fd622947e7d343b4130a1a8e42a0e30d5c5ec58e64e456314',
        'db.py': '8b295f375a18b41bdb92f120170bafb9a2cb93863be9e98b789241ceb32c4d6b',
    }
    for name, sha in expected.items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == sha
