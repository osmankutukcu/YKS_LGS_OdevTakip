# -*- coding: utf-8 -*-
"""V12 release candidate evidence/preflight, never a substitute for device sign-off.

Usage:
 python tools/v12_release_readiness.py --run-synthetic --original-zip PATH --out release/V12_READINESS.json
 python tools/v12_release_readiness.py --require-production --evidence PATH

Default and synthetic modes are read-only for project databases. Synthetic tests
run against separately created disposable databases through v11_acceptance.
"""
from __future__ import annotations
import argparse
import ast
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
PROTECTED_FILES = (
    'ui/homework_form.py', 'ui/odev_kontrol.py', 'db.py', 'main_window.py',
    'web_api/main.py', 'web_api/sync_engine.py', 'web_api/sync_transactions.py',
    'web_api/homework_store.py',
)
EXPECTED_PLATFORMS = ('windows_11', 'iphone_safari', 'ipad_safari', 'android_chrome')
REQUIRED_DEVICE_STEPS = (
    'https_install', 'offline_restart', 'encrypted_backup_restore',
    'seven_day_retention', 'queued_assignment_and_status',
    'network_cut_replay', 'desktop_form_reconciliation',
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest()


def original_provenance(root: Path, original_zip: Path | None) -> dict:
    results = {'result': 'NOT_PROVIDED', 'original_zip': None, 'files': {}, 'mismatches': []}
    if not original_zip:
        return results
    if not original_zip.is_file() or not zipfile.is_zipfile(original_zip):
        raise ValueError('Orijinal kaynak ZIP dosyası bulunamadı veya geçersiz.')
    results['original_zip'] = original_zip.name
    with zipfile.ZipFile(original_zip) as z:
        names = set(z.namelist())
        for relative in PROTECTED_FILES:
            if relative not in names:
                # The historical main project may not include newer sync files;
                # that is a NOT_COMPARABLE case, not a mismatch.
                results['files'][relative] = 'NOT_IN_ORIGINAL'
                continue
            local = root / relative
            if not local.is_file():
                results['files'][relative] = 'MISSING_IN_CANDIDATE'
                results['mismatches'].append(relative)
                continue
            match = digest(z.read(relative)) == digest(local.read_bytes())
            results['files'][relative] = 'IDENTICAL' if match else 'CHANGED'
            if not match:
                results['mismatches'].append(relative)
    results['result'] = 'MATCH' if not results['mismatches'] else 'MISMATCH'
    return results


def shell_preflight(root: Path) -> dict:
    sw = (root / 'web_api/static/sw.js').read_text(encoding='utf-8')
    health = (root / 'web_api/static/js/offline_health_v6.js').read_text(encoding='utf-8')
    html = (root / 'web_api/templates/index.html').read_text(encoding='utf-8')
    sw_match = re.search(r'SHELL_ASSETS\s*=\s*Object\.freeze\(\s*(\[[\s\S]*?\])\s*\)', sw)
    health_match = re.search(r'ASSETS\s*=\s*(\[[\s\S]*?\])\s*;', health)
    if not sw_match or not health_match:
        raise ValueError('PWA dosya listesi doğrulanamadı.')
    shell = ast.literal_eval(sw_match.group(1))
    audited = ast.literal_eval(health_match.group(1))
    if not isinstance(shell, list) or not shell or len(shell) != len(set(shell)):
        raise ValueError('Service Worker listesinde boş veya tekrarlı dosya var.')
    missing = []
    for url in shell:
        if url == '/':
            file = root / 'web_api/templates/index.html'
        elif isinstance(url, str) and url.startswith('/static/'):
            file = root / 'web_api/static' / url.removeprefix('/static/')
        else:
            raise ValueError(f'Güvensiz PWA önbellek girdisi: {url}')
        if not file.is_file():
            missing.append(url)
    caches = re.findall(r'yks-kocluk-shell-v\d+', sw)
    cache_health = re.findall(r'yks-kocluk-shell-v\d+', health)
    versions = re.findall(r'version\s*:\s*(\d+)', sw)
    health_versions = re.findall(r'version\s*:\s*(\d+)', health)
    same_cache = bool(caches and cache_health and caches[0] == cache_health[0])
    same_version = bool(versions and health_versions and versions[-1] == health_versions[-1])
    linked = all(f'/static/js/{name}' in html for name in (
        'offline_sync.js', 'offline_secure_store_v5.js', 'offline_health_v6.js',
        'offline_delta_v9.js', 'offline_resilience_v10.js'))
    sw_registered = "serviceWorker.register('/sw.js'" in html
    errors = []
    if missing: errors.append('PWA önbelleği için eksik dosyalar: ' + ', '.join(missing))
    if shell != audited: errors.append('SW ve çevrimdışı hazırlık dosya listeleri farklı.')
    if not same_cache or not same_version: errors.append('SW ve hazırlık ekranı sürümleri uyumsuz.')
    if not linked or not sw_registered: errors.append('Mobil HTML betik bağlantıları veya SW kaydı eksik.')
    return {'result': 'PASS' if not errors else 'FAIL', 'cached_assets': len(shell),
            'missing_assets': missing, 'sw_and_health_lists_equal': shell == audited,
            'cache_name_consistent': same_cache, 'version_consistent': same_version,
            'html_scripts_linked': linked, 'sw_registration_present': sw_registered,
            'errors': errors}


def evidence_template() -> dict:
    return {'kind': 'V12_REAL_DEVICE_ACCEPTANCE', 'project_commit': '<Git SHA>',
            'reviewer': '<Windows ve mobil test sorumlusu>',
            'devices': {platform: {
                'device_model': '<model>', 'os_version': '<OS sürümü>',
                'tested_from': '<YYYY-MM-DD>', 'tested_until': '<YYYY-MM-DD>',
                'steps': {step: 'PENDING' for step in REQUIRED_DEVICE_STEPS},
                'notes': 'Yalnızca sahte öğrenci; gerçek veri, parola ve token eklemeyin.'
            } for platform in EXPECTED_PLATFORMS},
            'manual_windows_acceptance': 'PENDING',
            'protected_source_review': 'PENDING'}


def validate_evidence(data: dict, today: date | None = None) -> list[str]:
    problems = []
    if not isinstance(data, dict) or data.get('kind') != 'V12_REAL_DEVICE_ACCEPTANCE':
        return ['Gerçek cihaz kabul kanıtının türü geçersiz.']
    commit = data.get('project_commit', '')
    if not isinstance(commit, str) or not re.fullmatch('[0-9a-f]{40}', commit):
        problems.append('Gerekli Git commit kimliği girilmemiş.')
    reviewer = data.get('reviewer', '')
    if not isinstance(reviewer, str) or reviewer.startswith('<') or len(reviewer.strip()) < 4:
        problems.append('Gerçek test sorumlusu belirtilmemiş.')
    devices = data.get('devices', {})
    now = today or date.today()
    for platform in EXPECTED_PLATFORMS:
        entry = devices.get(platform, {}) if isinstance(devices, dict) else {}
        if not isinstance(entry, dict): entry = {}
        if any(not isinstance(entry.get(k), str) or '<' in entry.get(k, '') or len(entry.get(k, '').strip()) < 2
               for k in ('device_model', 'os_version')):
            problems.append(f'{platform}: cihaz modeli/işletim sistemi eksik.')
        try:
            d0 = date.fromisoformat(entry['tested_from']); d1 = date.fromisoformat(entry['tested_until'])
            if d1 < d0 or (d1-d0) < timedelta(days=7) or d1 > now:
                problems.append(f'{platform}: gerçek yedi günlük test aralığı geçersiz.')
        except (ValueError, KeyError, TypeError):
            problems.append(f'{platform}: gerçek test tarihleri eksik.')
        steps = entry.get('steps', {})
        if not isinstance(steps, dict) or any(steps.get(s) != 'PASS' for s in REQUIRED_DEVICE_STEPS):
            problems.append(f'{platform}: zorunlu gerçek cihaz kontrolleri tamamlanmamış.')
    for k in ('manual_windows_acceptance', 'protected_source_review'):
        if data.get(k) != 'PASS': problems.append(f'{k}: manuel onay eksik.')
    return problems


def run_v11_synthetic(root: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix='v12-no-user-db-') as directory:
        report_path = Path(directory) / 'synthetic.json'
        proc = subprocess.run([sys.executable, 'tools/v11_acceptance.py', '--out', str(report_path)],
                              cwd=root, capture_output=True, text=True, timeout=450)
        if not report_path.is_file():
            return {'result': 'FAIL', 'error': (proc.stdout + '\n' + proc.stderr)[-1800:]}
        report = json.loads(report_path.read_text(encoding='utf-8'))
        return {'result': 'PASS' if proc.returncode == 0 and report.get('synthetic_result') == 'PASS' else 'FAIL',
                'python_suites': len(report.get('python', {}).get('suites', [])),
                'javascript_suites': len(report.get('javascript', {}).get('suites', [])),
                'python_suites_passed': sum(bool(e.get('ok')) for e in report.get('python', {}).get('suites', [])),
                'javascript_suites_passed': sum(bool(e.get('ok')) for e in report.get('javascript', {}).get('suites', [])),
                'test_only_db': True,
                'details': report.get('python', {}).get('suites', []) + report.get('javascript', {}).get('suites', [])}


def run(*, root: Path = ROOT, original_zip: Path | None = None, test: bool = False,
        evidence: Path | None = None, require_production: bool = False) -> dict:
    from tools.v35_release_gate import check_source
    provenance = original_provenance(root, original_zip)
    shell = shell_preflight(root)
    synthetic = run_v11_synthetic(root) if test else {'result': 'NOT_RUN'}
    try:
        check_source(root)
        source_gate = 'PASS'
        source_error = None
    except (ValueError, OSError) as exc:
        source_gate = 'BLOCKED'
        source_error = str(exc)
    if evidence and evidence.is_file():
        real_device = {'status':'REVIEW_REQUIRED', 'problems':validate_evidence(json.loads(evidence.read_text(encoding='utf-8')))}
    else:
        real_device = {'status':'NOT_RUN', 'problems':['Gerçek cihaz kabul raporu bulunamadı.']}
    # A form is not a substitute for the existing commit-bound V35 gate.
    problems = []
    if shell['result'] != 'PASS': problems.append('PWA statik hazırlık kontrolü başarısız.')
    if synthetic['result'] != 'PASS': problems.append('Sentetik testler bu çalıştırmada başarılı değil veya çalıştırılmadı.')
    if source_gate != 'PASS': problems.append('V35 korunan kaynak onayı bekliyor.')
    if real_device['problems']: problems.append('Gerçek cihaz kabulü tamamlanmadı.')
    if provenance['result'] == 'MISMATCH': problems.append('Orijinal ana projedeki korunan dosyalardan bazıları değişmiş.')
    if provenance['result'] == 'NOT_PROVIDED': problems.append('Orijinal ana proje ZIP karşılaştırması yapılmadı.')
    blockers = problems + [
        'Windows EXE kurulum/kaldırma ve checkbox davranışı bu ortamda manuel test edilmedi.',
        'Gerçek iPhone/iPad/Android üzerinde 7 gün çevrimdışı test edilmedi.',
    ]
    return {'protocol':'YKS_LGS_OFFLINE_V12_RELEASE_READINESS',
            'generated_at_utc':datetime.now(timezone.utc).isoformat(),
            'scope':'STATIC_PREFLIGHT_AND_SYNTHETIC_TESTS_ONLY',
            'original_project':provenance,'offline_pwa_shell':shell,
            'synthetic_tests':synthetic,
            'v35_protected_source_gate':{'status':source_gate,'reason':source_error},
            'real_device_acceptance':real_device,
            'synthetic_ready':shell['result']=='PASS' and synthetic['result']=='PASS',
            'production_release_approved':False,
            'production_blockers':blockers,
            'requested_production':bool(require_production),
            'note':'Yayın için ayrıca gerçek Windows ve mobil cihaz testleri, V35 kaynak incelemesi, sürüm/commit eşleşen manuel onay gerekir.'}


def main(argv=None):
    ap=argparse.ArgumentParser(description='V12 güvenli pilot; gerçek cihaz onayı otomatik verilmez.')
    ap.add_argument('--original-zip',type=Path)
    ap.add_argument('--run-synthetic',action='store_true')
    ap.add_argument('--evidence',type=Path)
    ap.add_argument('--write-evidence-template',action='store_true')
    ap.add_argument('--require-production',action='store_true')
    ap.add_argument('--out',type=Path,default=Path('release/V12_READINESS.json'))
    ns=ap.parse_args(argv)
    if ns.write_evidence_template:
        path=ROOT/'release/V12_REAL_DEVICE_TEMPLATE.json'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(evidence_template(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('Gerçek test şablonu:',path)
        return 0
    result=run(original_zip=ns.original_zip, test=ns.run_synthetic,
               evidence=ns.evidence, require_production=ns.require_production)
    out=ns.out if ns.out.is_absolute() else ROOT/ns.out
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('V12:', 'SENTETİK HAZIR' if result['synthetic_ready'] else 'SENTETİK ONAYLANMADI')
    print('CANLI YAYIN: ONAYLANMADI; kalan engeller:',len(result['production_blockers']))
    print('Rapor:',out)
    if ns.require_production:
        # Preserve the existing fail-closed source gate and manual checks; never
        # issue release permission based only on this JSON evidence summary.
        return 2
    return 0 if result['synthetic_ready'] else 1


if __name__=='__main__':
    try: raise SystemExit(main())
    except (OSError,ValueError,json.JSONDecodeError,subprocess.TimeoutExpired) as error:
        print('V12 DENETİM HATASI:',error,file=sys.stderr)
        raise SystemExit(1)
