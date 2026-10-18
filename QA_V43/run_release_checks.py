# -*- coding: utf-8 -*-
"""V43: non-destructive, headless release checks (no app launch or real settings)."""
from __future__ import annotations
import ast
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
TESTS = [
    'QA_V36/run_theme_safety.py',
    'QA_V37/test_v37_semantic.py',
    'QA_V38/test_notification_theme_v38.py',
    'QA_V39/test_popup_theme_v39.py',
    'QA_V40/test_v40_critical_panels.py',
    'QA_V41/test_v41_scrollbars.py',
    'QA_V42/test_v42_special_colors.py',
    'QA_V43/test_theme_integration_v43.py',
]


def sha256(file: Path) -> str:
    return hashlib.sha256(file.read_bytes()).hexdigest()


def main() -> int:
    results = []
    for relative in TESTS:
        file = ROOT / relative
        proc = subprocess.run([sys.executable, str(file)], cwd=str(ROOT),
                              capture_output=True, text=True, timeout=150)
        result = {'test': relative, 'passed': proc.returncode == 0,
                  'returncode': proc.returncode,
                  'output_tail': (proc.stdout + '\n' + proc.stderr)[-1600:].strip()}
        results.append(result)
        print(('PASS' if result['passed'] else 'FAIL') + '  ' + relative, flush=True)
        if not result['passed']:
            print(result['output_tail'])

    syntax_files = [p for p in ROOT.rglob('*.py') if not any(x in p.parts for x in ('.git', '.venv', 'build', 'dist', '__pycache__'))]
    errors = []
    for file in syntax_files:
        try:
            ast.parse(file.read_text(encoding='utf-8-sig'), filename=str(file))
        except Exception as ex:
            errors.append({'file': file.relative_to(ROOT).as_posix(), 'error': str(ex)})
    print(('PASS' if not errors else 'FAIL') + f'  AST: {len(syntax_files)} Python files')

    baseline = json.loads((HERE / 'v42_data_baseline_sha256.json').read_text(encoding='utf8'))
    mismatches = []
    for relative, expected in baseline.items():
        file = ROOT / relative
        if not file.is_file() or sha256(file) != expected:
            mismatches.append(relative)
    print(('PASS' if not mismatches else 'FAIL') +
          f'  User/data-file immutability vs V42: {len(baseline)} files')

    font_manifest = json.loads((HERE / 'original_fonts_sha256.json').read_text(encoding='utf8'))
    font_errors = [k for k,v in font_manifest.items() if not (ROOT/k).is_file() or sha256(ROOT/k) != v]
    print(('PASS' if not font_errors else 'FAIL') + '  Original bundled font integrity')

    try:
        import PyQt6  # noqa: F401
        gui = 'PyQt6 detected; QA_V43/gui_theme_smoke_v43.py can now run'
    except ImportError:
        gui = 'NOT RUN: PyQt6 not installed; Windows/macOS GUI acceptance still mandatory'
    print(gui)

    passed = all(item['passed'] for item in results) and not errors and not mismatches and not font_errors
    report = {
        'utc': datetime.now(timezone.utc).isoformat(),
        'overall_headless_pass': passed,
        'checks': results,
        'python_source_count': len(syntax_files),
        'syntax_errors': errors,
        'data_baseline_files_checked': len(baseline),
        'data_integrity_errors': mismatches,
        'fonts_checked': len(font_manifest),
        'font_integrity_errors': font_errors,
        'gui_status': gui,
        'release_status': 'PILOT: requires real Windows/macOS GUI acceptance',
    }
    if '--no-report' not in sys.argv:
        (HERE / 'headless_results_v43.json').write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding='utf8')
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
