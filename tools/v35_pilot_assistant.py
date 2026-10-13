# -*- coding: utf-8 -*-
"""V35 Windows pilot helper: isolated dummy DB + *manual* acceptance checklist.

No production DB is opened, no test is marked PASS automatically, no personal
student data is included in the report. This does not certify the UI or release.

Usage (Windows, source checkout):
    py -3.11 tools\v35_pilot_assistant.py --interactive
Cross-platform safe preflight (no GUI launched):
    python tools/v35_pilot_assistant.py --prepare-only --output-root some_dir
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import secrets
import sqlite3
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.v35_release_gate import MANUAL_CHECKS, check_source, expected_commit, template

CHECK_LABELS = {
    'installer_install_uninstall': 'Windows EXE kurulum/kaldırma: gerçek test (otomatik değil)',
    'windows_10_or_11_launch': 'Windows 10/11 üzerinde arayüzün açılması',
    'homework_checkbox_add_remove': 'Ödev Takip tik ekle/kaldır: örnek hücrelerde test',
    'given_homework_rows_and_minutes': 'Verilen Ödevler satırları ve süre toplamı tutarlı',
    'control_checkbox_save_reopen': 'Ödev Kontrol tik/Kaydet/uygulamayı yeniden aç',
    'control_cluster_move_delete_rollback': 'Küme Geri Taşı, Aktar, Sil ve geri dönüş',
    'student_identity_isolation': 'İki sahte öğrencinin verileri birbirine karışmıyor',
    'adaptive_draft_teacher_approval': 'Adaptif taslak iptal/onay ve eski aktarım',
    'pdf_print_whatsapp_workflows': 'Sahte kayıtla PDF, yazdırma ve WhatsApp denemesi',
    'backup_restore_old_data': 'Yalnızca kopya veritabanı ile yedek/geri yükleme',
    'windows_ux_latency_ab_comparison': 'Checkbox/Kaydet gecikme A/B ölçümleri kaydedildi',
    'no_critical_errors': 'Kritik hata/veri kaybı/yanlış öğrenci aktarımı yok',
}


def make_dummy_db(path: Path) -> None:
    """Precreate an actual SQLite database: db.py must NOT import a real legacy DB.

    db.py has a legacy migration of the home DB when YKS_DB_PATH does not exist.
    Thus just setting YKS_DB_PATH is *insufficient* on its own.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # Refuse overwrite, even when a path is pointed at an existing real DB.
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    fd = os.open(str(path), flags, 0o600)
    os.close(fd)
    try:
        with sqlite3.connect(path) as con:
            con.execute('CREATE TABLE v35_disposable_pilot_guard (test_only INTEGER NOT NULL)')
            con.execute('INSERT INTO v35_disposable_pilot_guard VALUES (1)')
    except Exception:
        path.unlink(missing_ok=True)
        raise


def safe_env(path: Path) -> dict[str, str]:
    """Run with isolated DB, user profile, config, cache and temporary folders.

    These env overrides cover Python/Qt modules using HOME, USERPROFILE,
    LOCALAPPDATA or tempfile. They do not isolate Windows known-folders, the
    registry, network integrations, a differently launched subprocess, etc.
    Thus the manual pilot is still mandatory and MUST NOT use real students.
    """
    db = path.resolve()
    work = db.parent / 'SAHTE_KULLANICI_PROFILI'
    folders = {
        'USERPROFILE': work,
        'HOME': work,
        'APPDATA': work / 'AppData' / 'Roaming',
        'LOCALAPPDATA': work / 'AppData' / 'Local',
        'TEMP': work / 'Temp',
        'TMP': work / 'Temp',
        'XDG_DATA_HOME': work / '.local' / 'share',
        'XDG_CONFIG_HOME': work / '.config',
        'XDG_CACHE_HOME': work / '.cache',
    }
    for folder in set(folders.values()):
        folder.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update({key: str(value) for key,value in folders.items()})
    env.update({'YKS_DB_PATH': str(db), 'YKS_DATA_DIR': str(db.parent),
                'YKS_AUTO_ADOPT': '0', 'YKS_PILOT_ISOLATED': '1',
                'EDUTRACK_ADAPTIVE_V33': '0', 'PYTHONUTF8': '1'})
    return env


def test_target_identity(executable: Path | None = None) -> dict[str, str]:
    """Record only the artifact name and SHA-256; never a user directory path."""
    candidate = (executable.resolve(strict=True) if executable else ROOT / 'app.py')
    if not candidate.is_file():
        raise ValueError('Test uygulaması bulunamadı.')
    if executable:
        if candidate.suffix.lower() != '.exe':
            raise ValueError('Yalnız Windows .exe kabul edilir.')
        if candidate.name.lower().endswith('_kurulum.exe'):
            raise ValueError('Kurulum dosyası değil, uygulamanın ana EXE dosyası seçilmeli.')
    h = hashlib.sha256()
    with candidate.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return {'kind': 'WINDOWS_EXE' if executable else 'PYTHON_SOURCE',
            'filename': candidate.name, 'sha256': h.hexdigest(),
            'matches_release_commit': 'NOT_VERIFIED'}


def get_commit():
    try:
        return expected_commit(ROOT)
    except (ValueError, OSError):
        # A distributed source ZIP may not include .git. Never fake a SHA.
        return None


def qt_module_installed() -> bool:
    """An in-memory mock package without ModuleSpec is not installed Qt."""
    try:
        return importlib.util.find_spec('PyQt6') is not None
    except (ValueError, ImportError, AttributeError):
        return False


def prepare(output_root: Path, *, now=None) -> tuple[Path, dict]:
    source = check_source(ROOT)  # fail closed if core differs
    stamp = (now or datetime.now()).strftime('%Y%m%d_%H%M%S')
    run = output_root / f'v35_pilot_{stamp}_{uuid.uuid4().hex[:8]}'
    run.mkdir(parents=True, exist_ok=False)
    make_dummy_db(run / 'SADECE_DENEME.db')
    commit = get_commit()
    manifest = {
        'stage':'WINDOWS_MANUAL_ACCEPTANCE_PENDING',
        'app_version':source['version'],
        'source_integrity':source['source_status'],
        'windows_manual_status':'NOT_VERIFIED',
        'test_database':'ISOLATED_DUMMY_PRECREATED',
        'legacy_db_auto_adopt':'DISABLED',
        'pilot_user_profile':'ISOLATED_ENV',
        'git_commit':commit if commit else 'UNAVAILABLE_IN_ZIP',
        'platform_family':platform.system(),
        'python_qt_module_present':qt_module_installed(),
        'checks':{check:'PENDING' for check in MANUAL_CHECKS},
        'note':('Bu dosya test onayı değildir; testler öğretmen tarafından '
                'gerçek Windows ortamında uygulanmalıdır. Öğrenci verisi içermez.'),
    }
    write_json(run / 'pilot_durumu.json', manifest)
    checklist = '\n'.join([
        '# V35 Windows pilotu – manuel kontrol listesi',
        '',
        'Bu çalışma gerçek öğrenci verileri yerine sahte veritabanı kullanır.',
        'Her madde ayrı ayrı kontrol edilmeden PASS işaretlenmemelidir.',
        'Formu doldurmak başarı kanıtı değildir; ekranı Windows üzerinde deneyin.',
        '',
        *[f'- [ ] {i}. {CHECK_LABELS[x]} (`{x}`)' for i,x in enumerate(MANUAL_CHECKS,1)],
        '',
        'Ölçümler: `tools/v33_windows_ab_pilot.py` ile test DB üzerinde alınabilir.',
        'Eski sürümle gerçek verinin geri yüklenmesi sadece ayrı test klasöründe yapılmalı.',
    ])
    (run / 'KONTROL_LISTESI.md').write_text(checklist + '\n',encoding='utf-8')
    return run, manifest


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def run_gui(run: Path, executable: Path | None = None) -> bool:
    if sys.platform != 'win32':
        raise ValueError('Pencere testi gerçek Windows bilgisayarda çalıştırılmalıdır.')
    db = run / 'SADECE_DENEME.db'
    if not db.is_file():
        raise ValueError('Sahte test veritabanı yok; gerçek DB ile başlatma engellendi.')
    with sqlite3.connect(db) as con:
        guard = con.execute('SELECT test_only FROM v35_disposable_pilot_guard').fetchone()
        if guard != (1,):
            raise ValueError('Test koruma kaydı eksik; açılış engellendi.')
    if executable is None:
        if importlib.util.find_spec('PyQt6') is None:
            raise ValueError('PyQt6 yok. requirements_win.txt bağımlılıklarını kurun veya --exe kullanın.')
        cmd = [sys.executable, str(ROOT/'app.py')]
        cwd = ROOT
    else:
        exe = executable.resolve(strict=True)
        if exe.suffix.lower() != '.exe':
            raise ValueError('Sadece Windows .exe dosyası kabul edilir.')
        cmd = [str(exe)]
        cwd = exe.parent
    from services.pilot_boot_guard_v35 import ready_matches
    env = safe_env(db)
    nonce = secrets.token_hex(16)
    ready_path = run / 'pilot_ready.json'
    env['YKS_PILOT_NONCE'] = nonce
    env['YKS_PILOT_READY_PATH'] = str(ready_path.resolve())
    print('Test programı açılıyor. Yalnızca sahte öğrenci kaydı kullanın.')
    proc = subprocess.Popen(cmd, cwd=str(cwd), env=env)
    rc = proc.wait()
    verified = ready_matches(ready_path, nonce)
    print('Uygulama kapandı. Çıkış kodu:',rc,
          '| sahte DB açılış kanıtı:', 'PASS' if verified else 'FAIL')
    return rc == 0 and verified


def record_manual(run: Path, manifest: dict, *, launch_ok=True, response=input) -> dict:
    """Only actual human keyboard responses can change statuses from PENDING."""
    if sys.platform != 'win32':
        raise ValueError('Manuel kabul yalnız gerçek Windows üzerinde kaydedilebilir.')
    print('Her madde için P=geçti, F=hata, Enter=bekliyor. İşlem yapılmadıysa P girmeyin.')
    results = {}
    for idx,check in enumerate(MANUAL_CHECKS,1):
        raw = response(f'{idx}/12 – {CHECK_LABELS[check]} [P/F/Enter]: ').strip().upper()
        results[check] = {'P':'PASS','F':'FAIL'}.get(raw,'PENDING')
    if not launch_ok:
        # A crashed process cannot be accepted as a successful GUI launch.
        results['windows_10_or_11_launch']='FAIL'
    manifest['checks']=results
    manifest['tested_at']=date.today().isoformat()
    status='PASS' if all(v=='PASS' for v in results.values()) else 'NOT_VERIFIED'
    manifest['windows_manual_status']=status
    write_json(run/'pilot_durumu.json',manifest)
    # A draft is NEVER automatically installed as a release approval. A
    # reviewer must copy it into release/ after evidence and commit check.
    draft = template(manifest['app_version'])
    draft['git_commit']=manifest['git_commit'] if re.fullmatch(r'[0-9a-f]{40}',manifest['git_commit']) else '<commit hash from GitHub>'
    draft['tested_at']=manifest['tested_at']
    draft['windows']=platform.platform()
    draft['checks']=results
    draft['notes']='Tüm kontroller manuel doğrulanmadıysa yayın yapmayın. Öğrenci bilgisi yazmayın.'
    write_json(run/'windows_acceptance_TASLAK.json',draft)
    return manifest


def main(argv=None):
    parser=argparse.ArgumentParser(description='V35 salt-deneme Windows pilot yardımcısı')
    parser.add_argument('--prepare-only', action='store_true', help='Sadece sahte DB ve PENDING kontrol listesi üretir')
    parser.add_argument('--interactive', action='store_true', help='Windows GUI aç ve manuel kabul adımlarını sor')
    parser.add_argument('--exe',type=Path,help='Ayrı test kurulumundaki Windows EXE yolu')
    parser.add_argument('--output-root',type=Path,default=ROOT/'pilot_runs')
    ns=parser.parse_args(argv)
    if ns.exe and not ns.interactive:
        parser.error('--exe yalnızca --interactive ile kullanılabilir.')
    if ns.interactive and sys.platform!='win32':
        parser.error('Etkileşimli pilot yalnız Windows üzerinde çalıştırılır.')
    run, manifest=prepare(ns.output_root)
    print('Pilot klasörü:',run)
    print('Kaynak denetimi: PASS; Windows manuel kabulü: NOT_VERIFIED')
    if ns.prepare_only or not ns.interactive:
        return 0
    try:
        manifest['launch_target']=test_target_identity(ns.exe)
        write_json(run/'pilot_durumu.json',manifest)
        launched=run_gui(run,ns.exe)
    except (OSError,ValueError) as exc:
        print('Test uygulaması açılamadı:',exc,file=sys.stderr)
        manifest['launch']='FAILED_OR_BLOCKED'
        write_json(run/'pilot_durumu.json',manifest)
        return 2
    manifest['launch']='CLOSED_NORMALLY' if launched else 'PROCESS_ERROR'
    if not launched:
        print('Program hatayla kapandı; herhangi bir kabulü otomatik PASS saymayın.')
    record_manual(run, manifest, launch_ok=launched)
    print('Rapor:',run/'pilot_durumu.json')
    print('Kabul taslağı:',run/'windows_acceptance_TASLAK.json')
    print('Yayın onayı otomatik verilmedi. GitHub commit eşleştirmesi gereklidir.')
    return 0 if manifest['windows_manual_status']=='PASS' and launched else 1


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except (OSError,ValueError,sqlite3.DatabaseError) as exc:
        print('PILOT ENGELI:',exc,file=sys.stderr)
        raise SystemExit(2)
