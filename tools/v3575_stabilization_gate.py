# -*- coding: utf-8 -*-
"""V3.5.75: reproducible, read-only KoçPilot release evidence gate.

No production DB, user records, cloud endpoint, installer, or Windows UI is touched.
This tool can disqualify a release but cannot authorize a live rollout.
Run `python -m tools.v3575_stabilization_gate --run-tests --output ...`.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'tests/v3575_critical_source_manifest.json'

# Separate Python processes are intentional: some legacy test modules install
# synthetic Qt stubs into sys.modules and pollute subsequent test collection.
TEST_GROUPS = {
    'coaching_decisions': [
        'tests/test_coaching_integration_guard_v3560.py',
        'tests/test_coaching_evidence_hub_v3561.py',
        'tests/test_learning_intervention_bridge_v3562.py',
        'tests/test_evidence_based_coach_v3563.py',
        'tests/test_automatic_coaching_cycle_v3565.py',
        'tests/test_coaching_action_center_v3567.py',
        'tests/test_coaching_navigation_v3568.py',
        'tests/test_smart_study_plan_v3569.py',
        'tests/test_weekly_coaching_alignment_v3570.py',
    ],
    'weekly_planning': [
        'tests/test_weekly_calendar_safety_patch.py',
        'tests/test_weekly_input_invariants_v35.py',
        'tests/test_weekly_equal_distribution_v35.py',
        'tests/test_weekly_exam_plan_v3557.py',
        'tests/test_weekly_routine_habits_v35.py',
        'tests/test_weekly_topic_priority_v35.py',
        'tests/test_weekly_one_click_v35.py',
        'tests/test_weekly_adaptive_bridge_v35.py',
        'tests/test_weekly_planner_presentation_v35.py',
    ],
    'feedback_contract': [
        'tests/test_homework_feedback_v3571.py',
        'tests/test_homework_feedback_coaching_v3572.py',
        'tests/test_feedback_relay_v3573.py',
        'tests/test_feedback_deployment_v3574.py',
    ],
    'windows_logic_not_gui': [
        'tests/test_windows_perf_v32.py',
        'tests/test_windows_perf_v33.py',
        'tests/test_write_durability_v354.py',
    ],
}


def verify_locked_sources(root: Path = ROOT, manifest_path: Path | None = None) -> list[str]:
    manifest_path = manifest_path or root / MANIFEST
    data = json.loads(manifest_path.read_text(encoding='utf8'))
    errors = []
    for name, expected in data['files'].items():
        p = root / name
        if not p.is_file():
            errors.append('MISSING:' + name)
        elif hashlib.sha256(p.read_bytes()).hexdigest() != expected:
            errors.append('HASH_MISMATCH:' + name)
    return errors


def scan_python_syntax(root: Path = ROOT) -> dict:
    problems = []
    count = 0
    for path in root.rglob('*.py'):
        if '.venv' in path.parts or '__pycache__' in path.parts:
            continue
        count += 1
        try:
            source = path.read_bytes()
            # ast.parse compiles the syntax without importing the program, Qt,
            # student DBs, or any local configuration.
            ast.parse(source, filename=str(path))
        except (SyntaxError, UnicodeError, ValueError) as exc:
            problems.append({'path':str(path.relative_to(root)), 'error':type(exc).__name__})
    return {'files_checked':count, 'issues':problems}


def execute_test_group(root: Path, group: str, files: list[str], timeout: int) -> dict:
    missing = [p for p in files if not (root / p).is_file()]
    if missing:
        return {'state':'BLOCKED', 'missing_tests':missing}
    cmd = [sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', *files]
    qt_deferred = []
    if importlib.util.find_spec('PyQt6') is None:
        if group == 'weekly_planning':
            qt_deferred = ['test_page_count_single_page_when_details_disabled']
        elif group == 'coaching_decisions':
            qt_deferred = ['test_known_plan_approved_topic_mechanism_reused']
        if qt_deferred:
            # Explicitly defer these genuine GUI/Qt checks, never count as pass.
            cmd.extend(['-k', ' and '.join('not ' + x for x in qt_deferred)])
    env = os.environ.copy()
    env['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PYTHONPATH'] = str(root)
    try:
        result = subprocess.run(cmd, cwd=root, env=env, capture_output=True,
                                text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return {'state':'TIMEOUT','seconds':timeout}
    output = (result.stdout + '\n' + result.stderr).strip()
    matched = list(re.finditer(r'(?P<count>\d+) passed(?:, (?P<skipped>\d+) skipped)?', output))
    passing = int(matched[-1].group('count')) if matched else 0
    skips = int(matched[-1].group('skipped') or 0) if matched else 0
    return {'state':'PASS' if result.returncode == 0 else 'FAIL',
            'returncode':result.returncode,
            'passed':passing, 'skipped':skips, 'qt_tests_deferred':qt_deferred,
            # The final 8 lines can contain filenames, never collect secrets.
            'result_summary':'\n'.join(output.splitlines()[-8:])[:1500]}


def build_report(root: Path = ROOT, *, run_tests: bool = False, timeout: int = 50) -> dict:
    from tools.v3527_core_guard import audit
    locked = verify_locked_sources(root)
    syntax = scan_python_syntax(root)
    core = audit(root)
    groups = {}
    if run_tests:
        for name, files in TEST_GROUPS.items():
            groups[name] = execute_test_group(root, name, files, timeout)
    static_ok = not locked and not syntax['issues'] and core['status'] == 'PASS'
    tests_ok = run_tests and all(x['state'] == 'PASS' for x in groups.values())
    return {
        'version':'v3.5.75',
        'scope':'read_only_stabilization_preflight',
        'core_static_contract':core['status'],
        'core_guard_summary':{'protected_files':core['protected_files'],
                              'protected_helpers':core['protected_helpers'],
                              'protected_behavior_handlers':core['protected_behavior_handlers'],
                              'warnings':core['warnings']},
        'critical_source_checks':{'count':len(json.loads((root/MANIFEST).read_text(encoding='utf8'))['files']),
                                  'errors':locked},
        'python_syntax':syntax,
        'test_groups':groups,
        'selected_test_total':sum(x.get('passed',0) for x in groups.values()),
        'qt_tests_deferred':[case for result in groups.values() for case in result.get('qt_tests_deferred',[])],
        'manual_release_blockers':[
            'Gerçek Windows/PyQt6 üzerinde tıklama, kayıt, geri alma ve kilit denetimi',
            'Gerçek öğrenci rutinleriyle haftalık PDF A4 yatay sayfa/görünüm karşılaştırması',
            'Gerçek Windows checkbox gecikmesi ve performans ölçümü',
            'EXE kurulumu, lisanslama, GitHub otomatik güncelleme ve geri dönüş',
            'Gerçek HTTPS/telefon anket gönderim ve senkronizasyon testi (pilot kapalı)',
            'Tam test paketinde özel lisans test bağımlılıkları ve Qt kurulumu',
        ],
        'preflight_status':'PASS_STATIC_AND_SELECTED_TESTS' if static_ok and tests_ok
                           else 'BLOCKED' if not static_ok or (run_tests and not tests_ok)
                           else 'STATIC_ONLY',
        'production_release_authorized':False,
        'reason':'Bu test kapısı tek başına müşteri dağıtımını onaylamaz.',
    }


def main(argv=None):
    p = argparse.ArgumentParser(description='KoçPilot v3.5.75 çevrimdışı sürüm kabul kapısı')
    p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--run-tests',action='store_true')
    p.add_argument('--timeout',type=int,default=50)
    p.add_argument('--output',type=Path)
    args = p.parse_args(argv)
    report = build_report(args.root,run_tests=args.run_tests,timeout=args.timeout)
    content = json.dumps(report,indent=2,ensure_ascii=False)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(content,encoding='utf8')
    print(content)
    return 0 if report['preflight_status'] != 'BLOCKED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
