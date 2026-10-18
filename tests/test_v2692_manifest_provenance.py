# -*- coding: utf-8 -*-
"""QA-only immutable proof for the V26.8 Student 360 signal hookup."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILE = 'ui/student_workspace_panel_v21.py'
BEFORE = '89bbbc6ef0ed74b4f068a6644a7d0e9b5cc900368178d3ad68a9daf05ac260a2'
AFTER = 'd98b2403e7f7ee147e1e7a6b6a1098117efaad0fc466eeafac44314678eff432'


def test_v268_panel_update_pins_both_revision_hashes():
    old = json.loads((ROOT/'V24_MANIFEST.json').read_text('utf-8'))
    delta = json.loads((ROOT/'V26_8_MANIFEST.json').read_text('utf-8'))
    assert old['files'][FILE] == BEFORE
    assert delta['previous_source_sha256'] == {FILE: BEFORE}
    assert delta['files'] == {FILE: AFTER}
    assert hashlib.sha256((ROOT/FILE).read_bytes()).hexdigest() == AFTER


def test_v268_panel_requires_scoped_router_not_a_second_timer():
    panel = (ROOT/FILE).read_text('utf-8')
    assert 'get_coach_router()' in panel
    assert 'self._coach_router.check(' in panel
    assert 'student_id=self._student_id' in panel
    assert panel.count('self._live_timer = QTimer(self)') == 1


def test_v2692_never_claims_ci_or_desktop_approval():
    source = (ROOT/'tools/v2692_release_audit.py').read_text('utf8')
    assert "'real_desktop_acceptance': 'NOT_VERIFIED'" in source
    assert "'release_status': 'BLOCKED'" in source
