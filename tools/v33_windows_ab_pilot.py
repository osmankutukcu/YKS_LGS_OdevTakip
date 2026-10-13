"""V33 Windows A/B pilot. Requires a DISPOSABLE copied test database.

Baseline:
  python tools/v33_windows_ab_pilot.py --database C:\\OdevTest\\ORNEK.db --mode baseline --output v33_baseline.json
Trial:
  python tools/v33_windows_ab_pilot.py --database C:\\OdevTest\\ORNEK.db --mode coalesced --output v33_coalesced.json

Never invoke with real student database. Does not change the normal app entry.
"""
from __future__ import annotations
import argparse
import atexit
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(args=None):
    ap = argparse.ArgumentParser(description='V33 experimental Windows style A/B pilot on test copies')
    ap.add_argument('--database', required=True)
    ap.add_argument('--mode', choices=('baseline','coalesced'), default='baseline')
    ap.add_argument('--output', default=None)
    ap.add_argument('--inspect-only', action='store_true')
    ap.add_argument('--student-id', type=int)
    ns = ap.parse_args(args)
    p = Path(ns.database).resolve(strict=True)
    if not p.is_file():
        ap.error('Test veritabani bulunamadi.')
    # Preserve V32 read-only inspection path; no PyQt needed here.
    if ns.inspect_only:
        from tools.v32_windows_profile import main as v32_main
        cmd = ['--database', str(p), '--inspect-only']
        if ns.student_id is not None:
            cmd += ['--student-id', str(ns.student_id)]
        return v32_main(cmd)
    if os.environ.get('ODEV_V33_TEST_DB_CONFIRMED') != '1':
        ap.error('Yalnizca kopya/sahte ogrenci DB: once ODEV_V33_TEST_DB_CONFIRMED=1 ayarlayin.')
    # V32 launcher requires its own explicit gate; we set it only after V33 gate.
    os.environ['ODEV_V32_TEST_DB_CONFIRMED'] = '1'
    os.environ['YKS_DB_PATH'] = str(p)
    from tools.v32_windows_profile import main as v32_main
    output = ns.output or f'v33_{ns.mode}_timings.json'
    if Path(output).suffix.lower() != '.json':
        ap.error('--output bir .json dosyasi olmali.')

    # IMPORTANT: when deferred, V32's wrapper duration is merely QUEUE time.
    # Record the actual legacy styling work separately to prevent a false
    # speed-up claim. Register first so this handler runs AFTER V32 writes.
    from services.windows_perf_v32 import MethodStats
    style_actual = MethodStats()
    def annotate_report():
        dest = Path(output)
        if not dest.exists():
            return
        report = json.loads(dest.read_text(encoding='utf-8'))
        report['v33_trial'] = {
            'mode': ns.mode,
            'important': ('In coalesced mode, _refresh_right_table_styles '
                          'in methods measures queue duration, not styling time. '
                          'Compare actual_style_work below with baseline method durations, '
                          'plus visible Windows UI responsiveness.'),
            'actual_style_work': style_actual.report()['methods'],
            'experimental_default_off': True,
        }
        dest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    atexit.register(annotate_report)

    if ns.mode == 'coalesced':
        from ui.odev_kontrol import OdevKontrolDialog
        from services.windows_perf_v33 import install_experimental_style_coalescing
        if not install_experimental_style_coalescing(
                OdevKontrolDialog,
                record_actual_ns=lambda n: style_actual.record('legacy_style_actual', n)):
            ap.error('Style trial already patched or unsupported.')
    return v32_main(['--database',str(p),'--output',str(output)])


if __name__ == '__main__':
    raise SystemExit(main())
