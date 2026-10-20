# -*- coding: utf-8 -*-
"""Windows EXE process-survival check on a temporary, disposable SQLite DB.

This DOES NOT simulate user clicks, prove usable GUI, or approve a release.
Runs exclusively on Windows CI or a Windows pilot computer.
"""
from __future__ import annotations
import argparse
import json
import secrets
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))


class _SafeTemporaryDirectory:
    """Windows üzerinde dosya tanıtıcı gecikmelerine karşı dayanıklı geçici klasör."""
    def __init__(self, *args, **kwargs):
        try:
            self._td = tempfile.TemporaryDirectory(*args, ignore_cleanup_errors=True, **kwargs)
        except TypeError:
            self._td = tempfile.TemporaryDirectory(*args, **kwargs)

    def __enter__(self):
        return self._td.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        for _ in range(6):
            try:
                if hasattr(self._td, "cleanup"):
                    self._td.cleanup()
                break
            except Exception:
                time.sleep(0.5)
        return False


def smoke(executable, *, seconds=12, platform=sys.platform, popen=subprocess.Popen,
          sleep=time.sleep, tmp_factory=_SafeTemporaryDirectory):
    if platform != 'win32':
        raise ValueError('EXE açılış denetimi yalnızca gerçek Windows üzerinde yapılır.')
    exe=Path(executable).resolve(strict=True)
    if exe.suffix.lower() != '.exe':
        raise ValueError('Windows EXE bekleniyordu.')
    if not 2 <= seconds <= 120:
        raise ValueError('Bekleme süresi 2–120 sn aralığında olmalı.')

    factory = tmp_factory if tmp_factory is not None else _SafeTemporaryDirectory
    try:
        td_ctx = factory(prefix='v35_fake_students_', ignore_cleanup_errors=True)
    except TypeError:
        try:
            td_ctx = factory(prefix='v35_fake_students_')
        except TypeError:
            td_ctx = factory()

    result_payload = None
    try:
        with td_ctx as tmp:
            # db.py contains a legacy-DB migration which copies the user's old
            # database if the requested target does not yet exist. Pre-create a
            # *valid* disposable SQLite file BEFORE launching the app, so even
            # on a machine with real legacy student data no migration runs.
            fake_db = Path(tmp) / 'synthetic_only.db'
            # Shared isolation helper also routes APPDATA, USERPROFILE, HOME and
            # temporary files into this disposable pilot run.
            from tools.v35_pilot_assistant import make_dummy_db, safe_env
            make_dummy_db(fake_db)
            env=safe_env(fake_db)
            env['QT_QPA_PLATFORM']='offscreen'
            nonce=secrets.token_hex(16)
            ready_file=Path(tmp)/'pilot_ready.json'
            env['YKS_PILOT_NONCE']=nonce
            env['YKS_PILOT_READY_PATH']=str(ready_file.resolve())
            proc=popen([str(exe)],cwd=str(exe.parent),env=env,
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            started=time.monotonic()
            survived=True
            try:
                while time.monotonic()-started < seconds:
                    if proc.poll() is not None:
                        survived=False
                        break
                    sleep(0.25)
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try: proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill(); proc.wait(timeout=5)
                # Windows'ta process sonlandıktan sonra dosya kilitlerinin bırakılması
                # için güvenlik payı ver:
                if platform == 'win32':
                    sleep(1.0)
            from services.pilot_boot_guard_v35 import ready_matches
            boot_verified=ready_matches(ready_file,nonce)
            result_payload = {
                'kind':'Windows EXE process + isolated dummy DB boot handshake',
                'seconds':seconds,'result':'PASS' if survived and boot_verified else 'FAIL',
                'isolated_db_initialized': 'PASS' if boot_verified else 'FAIL',
                'not_verified':['visible UI','checkbox','Save','cluster','installer',
                                'WhatsApp','PDF','real Windows user interaction']
            }
    except OSError:
        # Test başarıyla tamamlandıysa, yalnızca geçici klasörün Windows tarafından
        # silinmesi sırasındaki kilit gecikmesi (WinError 32) testi düşürmemeli.
        if result_payload is None:
            raise

    if result_payload is not None:
        return result_payload
    raise RuntimeError('Bilinmeyen döküm / açılış hatası')


def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument('--exe',required=True)
    ap.add_argument('--seconds',type=int,default=12)
    ap.add_argument('--report',default='dist/v35_windows_smoke.json')
    ns=ap.parse_args(argv)
    try:
        report=smoke(ns.exe,seconds=ns.seconds)
    except (ValueError,OSError) as exc:
        print('EXE açılış testi yapılamadı:',exc,file=sys.stderr)
        return 2
    dest=Path(ns.report);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    return 0 if report['result']=='PASS' else 1

if __name__=='__main__':
    raise SystemExit(main())
