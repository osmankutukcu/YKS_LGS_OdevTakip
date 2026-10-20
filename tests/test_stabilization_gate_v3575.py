"""Pure-function tests. No real DB, Qt, credentials or network."""
import hashlib
import json
from pathlib import Path

from tools.v3575_stabilization_gate import (
    ROOT, MANIFEST, verify_locked_sources, scan_python_syntax, build_report,
)


def test_all_guarded_files_match_frozen_baseline():
    assert verify_locked_sources(ROOT) == []


def test_hash_change_blocks_release(tmp_path):
    source = tmp_path / 'my_module.py'
    source.write_text('value = 1\n', encoding='utf8')
    (tmp_path / 'manifest.json').write_text(json.dumps({'files':{
        'my_module.py':hashlib.sha256(source.read_bytes()).hexdigest()}}))
    assert verify_locked_sources(tmp_path, tmp_path / 'manifest.json') == []
    source.write_text('value = 2\n', encoding='utf8')
    assert verify_locked_sources(tmp_path, tmp_path / 'manifest.json') == ['HASH_MISMATCH:my_module.py']


def test_missing_source_blocks_release(tmp_path):
    (tmp_path/'manifest.json').write_text(json.dumps({'files':{'missing.py':'abc'}}))
    assert verify_locked_sources(tmp_path,tmp_path/'manifest.json') == ['MISSING:missing.py']


def test_syntax_scanner_detects_errors_without_running_code(tmp_path):
    (tmp_path/'okay.py').write_text('raise RuntimeError("must not execute")\n')
    assert scan_python_syntax(tmp_path)['issues'] == []
    (tmp_path/'bad.py').write_text('def invalid(\n')
    problems = scan_python_syntax(tmp_path)['issues']
    assert len(problems) == 1 and problems[0]['path'] == 'bad.py'


def test_static_only_never_authorizes_customer_rollout():
    report = build_report(ROOT, run_tests=False)
    assert report['preflight_status'] == 'STATIC_ONLY'
    assert report['production_release_authorized'] is False
    assert report['critical_source_checks']['errors'] == []
    assert report['core_static_contract'] == 'PASS'


def test_contract_protects_both_forms_and_weekly_planner():
    pinned = json.loads((ROOT/MANIFEST).read_text(encoding='utf8'))['files']
    for filename in ('ui/homework_form.py','ui/odev_kontrol.py','ui/weekly_plan.py',
                     'web_api/main.py','utils/updater.py'):
        assert filename in pinned
