# -*- coding: utf-8 -*-
"""V26.9.1 provenance/readiness safety tests (no application data)."""
from __future__ import annotations

import json
from pathlib import Path
import shutil

from tools.v2691_readiness_check import ROOT, MANIFEST, original_source_checks


def test_protected_six_sources_are_exactly_reviewed_upload():
    checks = original_source_checks()
    assert len(checks) == 6
    assert set(checks.values()) == {'PASS'}


def test_one_byte_mutation_is_rejected_even_when_legacy_ast_is_identical(tmp_path):
    data = json.loads(MANIFEST.read_text(encoding='utf-8'))
    for rel in data['protected_sha256']:
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, dest)
    target = tmp_path / 'ui/curriculum_page.py'
    target.write_bytes(target.read_bytes() + b'\n# QA tamper\n')
    checks = original_source_checks(tmp_path)
    assert checks['ui/curriculum_page.py'] == 'FAIL'
    assert all(status == 'PASS' for file, status in checks.items() if file != 'ui/curriculum_page.py')


def test_checker_cannot_silently_claim_real_desktop_approval():
    checker = (ROOT/'tools/v2691_readiness_check.py').read_text(encoding='utf-8')
    assert "'real_desktop_acceptance': 'NOT_VERIFIED'" in checker
    assert "'release_approval': 'BLOCKED_PENDING_REAL_DEVICE_ACCEPTANCE'" in checker
