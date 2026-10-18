# -*- coding: utf-8 -*-
"""V26.9.1 pilot readiness evidence, never a release approval.

No application imports or database access during static checks. Optional tests
are executed against a disposable DB location, not the caller's YKS_DB_PATH.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'tests' / 'v2691_original_source_manifest.json'


def original_source_checks(root: Path = ROOT, manifest: Path = MANIFEST) -> dict:
    data = json.loads(manifest.read_text(encoding='utf-8'))
    expected = data['protected_sha256']
    actual = {}
    for rel, digest in expected.items():
        target = root / rel
        measured = hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else None
        actual[rel] = 'PASS' if measured == digest else 'FAIL'
    return actual


def test_selected_suite(timeout: int = 120) -> dict:
    entries = [item.strip() for item in (ROOT/'V26_9_SECILI_TEST_DOSYALARI.txt').read_text('utf-8').splitlines()
               if item.strip() and not item.lstrip().startswith('#')]
    entries.append('tests/test_curriculum_usability_v37.py')
    entries.append('tests/test_v2691_readiness.py')
    if any(not item.startswith('tests/') or '..' in Path(item).parts or not (ROOT/item).is_file()
           for item in entries):
        return {'status': 'INVALID_TEST_LIST', 'summary': '', 'modules': 0}
    try:
        with TemporaryDirectory(prefix='v2691_qa_synthetic_') as temp:
            env = os.environ.copy()
            # Never let a caller's live DB override the isolated test environment.
            env['YKS_DB_PATH'] = str(Path(temp) / 'synthetic_test_only.db')
            env['PYTHONDONTWRITEBYTECODE'] = '1'
            cmd = [sys.executable, '-m', 'pytest', '-q', *entries]
            proc = subprocess.run(cmd, cwd=ROOT, env=env, text=True, encoding='utf-8',
                                  errors='replace', stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, timeout=timeout, check=False)
            tail = proc.stdout[-2000:]
            return {'status': 'PASS' if proc.returncode == 0 else 'FAIL',
                    'summary': tail, 'modules': len(entries), 'exit_code': proc.returncode}
    except subprocess.TimeoutExpired:
        return {'status': 'TIMEOUT', 'summary': f'Exceeded {timeout}s', 'modules': len(entries)}
    except (OSError, ValueError) as exc:
        return {'status': 'ERROR', 'summary': type(exc).__name__, 'modules': len(entries)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='V26.9.1 QA source + selected tests; never a live release approval')
    ap.add_argument('--tests', action='store_true', help='Run 44 selected modules plus V37 curriculum guards')
    ap.add_argument('--report', type=Path, help='Write machine-readable report to selected path')
    ns = ap.parse_args(argv)
    try:
        sources = original_source_checks()
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f'Source verification failed: {type(exc).__name__}', file=sys.stderr)
        return 2
    report = {
        'product': 'YKS-LGS HomeworkManager',
        'pilot': 'V26.9.1',
        'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'operating_system': platform.system(),
        'protected_sources': sources,
        'selected_regression': test_selected_suite() if ns.tests else 'NOT_RUN',
        'real_desktop_acceptance': 'NOT_VERIFIED',
        'full_test_suite': 'NOT_VERIFIED',
        'release_approval': 'BLOCKED_PENDING_REAL_DEVICE_ACCEPTANCE',
    }
    if ns.report:
        ns.report.parent.mkdir(parents=True, exist_ok=True)
        ns.report.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    success = all(v=='PASS' for v in sources.values()) and (
        not ns.tests or report['selected_regression']['status']=='PASS')
    return 0 if success else 1


if __name__=='__main__':
    raise SystemExit(main())
