# -*- coding: utf-8 -*-
"""V35: fail-closed Windows release gates; no Qt or DB access.

A source review is NOT Windows manual acceptance. Tag/release creation requires
an explicit, version-and-commit-bound acceptance record supplied by a tester.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
# Reviewed V35 RC2 baseline: the weekly calendar launcher now includes
# the approved no-hidden-homework snapshot and pre-PDF integrity check.
# The original tick/save/control operations are protected separately by AST.
PROTECTED = {
    'ui/homework_form.py': 'f015d489390ad0d529aabd2f447eaeaed14ccd54f48aaa81dd4a5ed47aef6cad',
    'ui/odev_kontrol.py': '7ca39f447e4a7cd71cb4eb14fde9bba53fae6c183092d0758a77c8d009cd4d0c',
    'db.py': '0273aa9842fea40e1961728de39c2a04bc796eb66d9dadad2bb2d25e22b75b94',
    'main_window.py': '953aef2a7cb3c4296015b565d145d794c6e86f491c3b215ee4ed03150fa3e668',
}
MANUAL_CHECKS = (
    'installer_install_uninstall',
    'windows_10_or_11_launch',
    'homework_checkbox_add_remove',
    'given_homework_rows_and_minutes',
    'control_checkbox_save_reopen',
    'control_cluster_move_delete_rollback',
    'student_identity_isolation',
    'adaptive_draft_teacher_approval',
    'pdf_print_whatsapp_workflows',
    'backup_restore_old_data',
    'windows_ux_latency_ab_comparison',
    'no_critical_errors',
)


def app_version(root=ROOT):
    source = (root / 'version.py').read_text(encoding='utf-8')
    setup = (root / 'setup.iss').read_text(encoding='utf-8')
    a = re.search(r'^APP_VERSION\s*=\s*[\'"](\d+\.\d+\.\d+)[\'"]', source, re.M)
    b = re.search(r'^#define MyAppVersion\s+[\'"](\d+\.\d+\.\d+)[\'"]', setup, re.M)
    if not a or not b or a.group(1) != b.group(1):
        raise ValueError('version.py ve setup.iss uyumlu değil.')
    return a.group(1)


def check_source(root=ROOT):
    """Never modifies the protected legacy behavior or any SQLite database."""
    changed = []
    for name, expected in PROTECTED.items():
        target = root / name
        digest = hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else None
        if digest != expected:
            changed.append(name)
    if changed:
        raise ValueError('Korunan kaynak değişmiş (manuel inceleme gerekir): ' + ', '.join(changed))
    if __package__:
        from .v35_reviewed_source_contract import verify_legacy_handlers
    else:
        from v35_reviewed_source_contract import verify_legacy_handlers
    verify_legacy_handlers(root)
    version = app_version(root)
    setup = (root / 'setup.iss').read_text(encoding='utf-8').lower()
    for excluded in ('*.db', '*.sqlite', '*.sqlite3', '*.db-wal', '*.db-shm'):
        if excluded not in setup:
            raise ValueError(f'Kurulum dosyası veritabanı hariç tutma kontrolü: {excluded}')
    return {'version': version, 'protected_files': len(PROTECTED), 'source_status':'PASS',
            'manual_windows_acceptance': 'NOT_VERIFIED'}


def template(version=None):
    return {
        'version': version or app_version(),
        'git_commit': '<exact GitHub commit SHA>',
        'tested_at': '<YYYY-MM-DD>',
        'tester': '<Windows testini yapan kişi>',
        'windows': '<Windows sürümü ve mimari>',
        'notes': 'Yalnızca sahte öğrenci veritabanı kullanın; kişisel bilgi yazmayın.',
        'checks': {c: 'PENDING' for c in MANUAL_CHECKS},
    }


def expected_commit(root=ROOT):
    sha = os.environ.get('GITHUB_SHA','').strip()
    if re.fullmatch(r'[0-9a-fA-F]{40}',sha):
        return sha.lower()
    result = subprocess.run(['git','rev-parse','HEAD'],cwd=root,
                            text=True,capture_output=True,check=False)
    sha = result.stdout.strip()
    if result.returncode or not re.fullmatch(r'[0-9a-fA-F]{40}',sha):
        raise ValueError('Git commit hash çözülemedi; sürüm onayı yapılamaz.')
    return sha.lower()


def validate_acceptance(data, *, version, commit, today=None):
    """Reject incomplete/outdated/mismatched signoffs, including placeholders."""
    if not isinstance(data,dict):
        raise ValueError('Windows kabul dosyası bir JSON nesnesi olmalı.')
    if data.get('version') != version or data.get('git_commit','').lower() != commit.lower():
        raise ValueError('Windows kabul formunun sürümü veya commit hash değeri uyuşmuyor.')
    for field in ('tester','windows'):
        val=data.get(field)
        if not isinstance(val,str) or len(val.strip()) < 4 or '<' in val:
            raise ValueError(f'Kabul formunda {field} bilgisi eksik.')
    try:
        tested=date.fromisoformat(data['tested_at'])
    except (KeyError,TypeError,ValueError) as exc:
        raise ValueError('Kabul testinin tarihi ISO YYYY-MM-DD biçiminde olmalı.') from exc
    day=today or date.today()
    if tested > day or day-tested > timedelta(days=30):
        raise ValueError('Windows kabul testinin tarihi gelecek veya 30 günden eski.')
    checks=data.get('checks')
    if not isinstance(checks,dict) or any(checks.get(c) != 'PASS' for c in MANUAL_CHECKS):
        raise ValueError('Windows kabul formunda bütün zorunlu kontroller PASS değil.')
    return {'version':version, 'commit':commit, 'windows_manual_status':'PASS',
            'manual_checks':len(MANUAL_CHECKS)}


def main(argv=None):
    ap=argparse.ArgumentParser(description='V35 sürüm koruması ve Windows manuel kabul kilidi')
    ap.add_argument('--require-acceptance', action='store_true')
    ap.add_argument('--acceptance', default='release/windows_acceptance_v35.json')
    ap.add_argument('--write-template', action='store_true')
    ap.add_argument('--report')
    ns=ap.parse_args(argv)
    if ns.write_template:
        dest=ROOT/'release/windows_acceptance_TEMPLATE.json'
        dest.parent.mkdir(exist_ok=True)
        dest.write_text(json.dumps(template(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('Boş Windows kabul formu:',dest)
        return 0
    report=check_source()
    if ns.require_acceptance:
        path=(ROOT/ns.acceptance).resolve()
        if not path.is_file():
            raise ValueError('Gerçek Windows kabul formu bulunamadı; Stable/Release engellendi.')
        data=json.loads(path.read_text(encoding='utf-8'))
        report.update(validate_acceptance(data,version=report['version'],commit=expected_commit()))
        report['manual_windows_acceptance']='PASS'
    if ns.report:
        p=Path(ns.report)
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print('V35 YAYIN ENGELİ:',error,file=sys.stderr)
        raise SystemExit(1)
