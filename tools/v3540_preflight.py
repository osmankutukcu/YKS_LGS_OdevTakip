# -*- coding: utf-8 -*-
"""V3.5.40: local, read-only stabilization / release preflight.

No live DB is opened, no credentials are needed, no external services are called.
A successful preflight is NOT a Windows user acceptance or publication permission.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.v3527_core_guard import audit as core_audit
from tools.v35_release_gate import check_source as historical_source_check
from tools.validate_release import read_versions

ACADEMIC_MODULES = (
    'services/system_health_v3528.py',
    'services/shared_academic_decision_v3530.py',
    'services/system_health_v3531.py',
    'services/verified_recovery_v3532.py',
    'services/canonical_homework_evidence_v3535.py',
    'services/academic_actions_v3536.py',
    'services/intervention_patterns_v3539.py',
)
# A distributable curriculum-only reference DB is a special *source asset*.
# No student SQLite database may be present in the public source package.
CURRICULUM_SQLITE_ALLOWLIST = {'YKS_Kazanimlar.sqlite'}
SENSITIVE_NAMES = {'license.json', 'config.json', '.env', 'id_rsa', 'id_ed25519'}
SENSITIVE_SUFFIXES = ('.db', '.sqlite', '.sqlite3', '.lic', '.pem', '.p12', '.pfx', '.key', '.log')
SKIP_DIRS = {'.git', '__pycache__', '.venv', 'venv', 'node_modules', '.next', '.pytest_cache', 'dist', 'build', 'backups', 'logs', 'scratch'}


def _step(workflow: str, step_title: str) -> str:
    """Return a named workflow step, fail closed if missing / ambiguous."""
    marker = '      - name: ' + step_title + '\n'
    if workflow.count(marker) != 1:
        raise ValueError('Yayın iş akışı adımı eksik veya tekrarlanmış: ' + step_title)
    return workflow.split(marker, 1)[1].split('\n      - name: ', 1)[0]


def verify_workflow(source: str) -> list[str]:
    """Check the Windows release gates in build_installer.yml."""
    errors = []
    try:
        smoke = _step(source, 'Gercek Windows EXE izole sahte veritabani acilis testi')
    except ValueError:
        errors.append('WINDOWS_SMOKE_STEP_MISSING')
    else:
        if 'tools/v35_windows_smoke.py --exe' not in smoke:
            errors.append('WINDOWS_SMOKE_NOT_INVOKED')
    try:
        manual = _step(source, 'Etiket icin gercek Windows manuel kabul kaydi zorunlu')
    except ValueError:
        errors.append('WINDOWS_MANUAL_GATE_MISSING')
    else:
        if "if: startsWith(github.ref, 'refs/tags/v')" not in manual:
            errors.append('WINDOWS_MANUAL_TAG_CONDITION_MISSING')
        if 'tools/v35_release_gate.py' not in manual:
            errors.append('WINDOWS_MANUAL_ACCEPTANCE_NOT_REQUIRED')
        if not re.search(r'if\s*\(\$LASTEXITCODE\s*-ne\s*0\)\s*\{\s*throw\b', manual):
            errors.append('WINDOWS_MANUAL_FAILED_VALIDATION_NOT_BLOCKING')
    try:
        release = _step(source, 'v3.5.4 gibi etiketlerde Release yayinla')
    except ValueError:
        errors.append('GITHUB_RELEASE_STEP_MISSING')
    else:
        if "if: startsWith(github.ref, 'refs/tags/v')" not in release:
            errors.append('GITHUB_RELEASE_TAG_CONDITION_MISSING')
    if 'python tools/v3540_preflight.py' not in source or 'tests.test_v3540_release_safety' not in source:
        errors.append('V3540_IN_CI_NOT_ENFORCED')
    return errors


def inventory_sensitive_source(root: Path) -> list[str]:
    """Inspect source filenames only, never open personal records."""
    import subprocess
    blocked = []
    candidates: list[Path] = []
    if (root / '.git').exists():
        try:
            proc = subprocess.run(
                ['git', 'ls-files'],
                cwd=str(root),
                capture_output=True,
                text=True,
                check=True,
            )
            candidates = [root / line.strip() for line in proc.stdout.splitlines() if line.strip()]
        except Exception:
            candidates = list(root.rglob('*'))
    else:
        candidates = list(root.rglob('*'))
    for f in candidates:
        if not f.is_file() or any(part in SKIP_DIRS or part.startswith('.venv') for part in f.relative_to(root).parts):
            continue
        rel = f.relative_to(root).as_posix()
        name = f.name.lower()
        if rel in CURRICULUM_SQLITE_ALLOWLIST:
            continue
        if (name in SENSITIVE_NAMES or name.startswith('.env.') or
                name.endswith(SENSITIVE_SUFFIXES) or
                name.endswith(('.db-wal', '.db-shm', '.sqlite-wal', '.sqlite-shm')) or
                'keygen' in name or 'lisans_uretici' in name or
                '_admin_tools_private' in rel.lower()):
            blocked.append(rel)
    return sorted(blocked)


def inspect_source(root: Path = ROOT) -> dict:
    root = Path(root)
    errors = []
    details = {}
    try:
        ver = read_versions(root)
        version_json = json.loads((root/'version.json').read_text('utf8'))['version']
        if ver != version_json:
            errors.append('VERSION_TRIPLE_MISMATCH')
        details['version'] = ver
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        errors.append('VERSION_CHECK_FAILED')
        details['version_error_type'] = type(exc).__name__

    try:
        core = core_audit(root)
        details['protected_core'] = {'status':core['status'],
                                     'protected_files':core['protected_files'],
                                     'protected_helpers':core['protected_helpers'],
                                     'effective_handlers':len(core['effective_handlers'])}
        if core['status'] != 'PASS':
            errors.append('PROTECTED_FORMS_CHANGED')
    except (ValueError, OSError, KeyError) as exc:
        errors.append('PROTECTED_FORMS_AUDIT_FAILED')
        details['protected_audit_error_type'] = type(exc).__name__

    try:
        historical = historical_source_check(root)
        details['historical_gate'] = historical['source_status']
        if historical['source_status'] != 'PASS':
            errors.append('V35_CORE_GATE_FAILED')
    except (ValueError, OSError, KeyError) as exc:
        errors.append('V35_CORE_GATE_FAILED')
        details['historical_gate_error_type'] = type(exc).__name__

    try:
        workflow = (root/'.github/workflows/build_installer.yml').read_text('utf8')
        errors.extend(verify_workflow(workflow))
    except OSError:
        errors.append('GITHUB_WORKFLOW_MISSING')

    missing = [p for p in ACADEMIC_MODULES if not (root/p).is_file()]
    details['academic_modules_present'] = len(ACADEMIC_MODULES)-len(missing)
    if missing:
        errors.append('ACADEMIC_MODULES_MISSING')
        details['missing_modules'] = missing

    violations = inventory_sensitive_source(root)
    if violations:
        errors.append('SENSITIVE_SOURCE_FILES_PRESENT')
        details['blocked_file_count'] = len(violations)
        # Don't echo sensitive pathnames: no names of private student files in reports.

    syntax_bad = 0
    python_files = 0
    for f in root.rglob('*.py'):
        if any(part in SKIP_DIRS or part.startswith('.venv') for part in f.relative_to(root).parts):
            continue
        python_files += 1
        try:
            ast.parse(f.read_text(encoding='utf8'), filename=f.name)
        except (SyntaxError, UnicodeError, OSError):
            syntax_bad += 1
    details['python_files_parsed'] = python_files
    details['python_syntax_failures'] = syntax_bad
    if syntax_bad:
        errors.append('PYTHON_SYNTAX_ERROR')

    return {'source_status':'PASS' if not errors else 'BLOCK',
            'blockers':sorted(set(errors)),
            'details':details,
            'manual_windows_uat':'NOT_VERIFIED',
            'backup_restore_real_windows':'NOT_VERIFIED',
            'baileys_real_windows':'NOT_VERIFIED',
            'windows_installer_smoke':'NOT_VERIFIED',
            'production_release_authorized':False,
            'explanation':'Source preflight is not end-to-end GUI or release acceptance.'}


def main(argv=None):
    ap = argparse.ArgumentParser(description='V3.5.40 salt-okunur kaynak/yayın kapısı')
    ap.add_argument('--root', type=Path, default=ROOT)
    ap.add_argument('--report', type=Path, help='Optional no-student-PII JSON report')
    args = ap.parse_args(argv)
    status = inspect_source(args.root)
    payload = json.dumps(status, ensure_ascii=False, indent=2)+'\n'
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload, encoding='utf8')
    print(payload)
    return 0 if status['source_status']=='PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
