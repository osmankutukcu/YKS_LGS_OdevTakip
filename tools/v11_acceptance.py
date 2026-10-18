# -*- coding: utf-8 -*-
"""Offline V11 synthetic acceptance runner (never touches a user database).

Execution: python tools/v11_acceptance.py --out release/V11_SYNTHETIC_RESULT.json
The generated report cannot serve as an approval for a real device or Windows.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
PYTHON_SUITES = [
    'tests/test_offline_v11_week_acceptance.py',
    'tests/test_mobile_sync_v3_integration.py',
    'tests/test_offline_v8_pages.py',
    'tests/test_offline_v9_delta.py',
    'tests/test_offline_v10_source_guards.py',
]
NODE_SUITES = sorted(str(path.relative_to(ROOT)) for path in (ROOT/'tests').glob('test_offline_*.cjs'))
SOURCE_FILES = (
    'db.py','main_window.py','ui/homework_form.py','ui/odev_kontrol.py',
    'web_api/main.py','web_api/sync_engine.py','web_api/sync_transactions.py',
    'web_api/homework_store.py',
)

def run(out: Path):
    with tempfile.TemporaryDirectory(prefix='yks-v11-synthetic-only-') as d:
        env=os.environ.copy()
        env['YKS_DB_PATH']=str(Path(d)/'DISPOSABLE_TEST.sqlite')
        env['YKS_AUTO_ADOPT']='0'
        env['YKS_WEB_ACCESS_TOKEN']='v11-acceptance-synthetic-only-'+'x'*32
        python_suites=[]
        for index,file in enumerate(PYTHON_SUITES):
            # Each suite gets its own interpreter and DB path. Legacy db.py
            # caches its DB_PATH during import, so a combined pytest session
            # can accidentally reuse a prior test module's database.
            suite_env=env.copy()
            suite_env['YKS_DB_PATH']=str(Path(d)/f'DISPOSABLE_{index}.sqlite')
            completed=subprocess.run([sys.executable,'-m','pytest','-q',file,
                                      '--disable-warnings'],cwd=ROOT,env=suite_env,
                                     text=True,capture_output=True,timeout=120)
            python_suites.append({'suite':file,'ok':completed.returncode==0,
                'last_lines':(completed.stdout+'\n'+completed.stderr).strip().splitlines()[-6:]})
        js=[]
        for file in NODE_SUITES:
            try:
                result=subprocess.run(['node',file],cwd=ROOT,env=env,text=True,
                                      capture_output=True,timeout=90)
                js.append({'suite':file,'ok':result.returncode==0,
                           'last_lines':(result.stdout+'\n'+result.stderr).strip().splitlines()[-4:]})
            except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
                js.append({'suite':file,'ok':False,'last_lines':[type(exc).__name__]})
        # Deliberately no re-pinning and no approval: the V35 reviewed SHA is
        # different from the user's original ZIP. This must be reviewed manually.
        hashes={file:hashlib.sha256((ROOT/file).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
                for file in SOURCE_FILES}
        gate_expected = '827098c0628bccbac89fbcb37cdf9967467b8971e65457d1d484768c824ffb5b'
        blocked=hashes['ui/homework_form.py'] != gate_expected
        report={
            'protocol':'YKS_LGS_V11_SYNTHETIC_ACCEPTANCE',
            'generated_at_utc':datetime.now(timezone.utc).isoformat(),
            'scope':'DISPOSABLE_SQLITE_AND_NODE_ONLY',
            'live_student_db_touched':False,
            'python':{'ok':all(entry['ok'] for entry in python_suites), 'suites':python_suites},
            'javascript':{'ok':bool(js) and all(entry['ok'] for entry in js), 'suites':js},
            'source_hashes':hashes,
            'release_blockers':{
                'previously_reviewed_homework_form_sha_mismatch':blocked,
                'real_windows_exe_test':'NOT_RUN',
                'actual_iphone_ipad_android_7_day_test':'NOT_RUN',
                'manual_windows_acceptance':'NOT_VERIFIED',
                'https_pwa_install_reopen_offline':'NOT_RUN',
            },
        }
        report['synthetic_result']='PASS' if report['python']['ok'] and report['javascript']['ok'] else 'FAIL'
        report['production_release_approved']=False
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('SYNTHETIC',report['synthetic_result'],'; PRODUCTION APPROVAL: NOT GIVEN')
        print('Python:',sum(item['ok'] for item in python_suites),'/',len(python_suites))
        print('JS:',sum(item['ok'] for item in js),'/',len(js))
        print('Release blocker:', 'source review required' if blocked else 'none from hash')
        print('Report:',out)
        return 0 if report['synthetic_result']=='PASS' else 1

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',default='release/V11_SYNTHETIC_RESULT.json')
    args=parser.parse_args()
    target=Path(args.out)
    if not target.is_absolute():target=ROOT/target
    raise SystemExit(run(target))
