"""V32 Windows pilot entrypoint. Does not modify homework form source files.

INSPECT ONLY (works on Linux/Mac/Windows, no Qt required):
  python tools/v32_windows_profile.py --database path/to/COPIED.db --inspect-only

LIVE WINDOWS pilot (uses a COPIED DB, same UI as normal app):
  python tools/v32_windows_profile.py --database path/to/COPIED.db --output v32_times.json
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
from services.windows_perf_v32 import MethodStats, install_method_timing, inspect_query_plans, compare_header_stat_queries


def main(args=None):
    parser = argparse.ArgumentParser(description='V32 read-only query and Windows GUI timing pilot')
    parser.add_argument('--database', required=True, help='Absolute path to a TEST COPY of the DB')
    parser.add_argument('--inspect-only', action='store_true', help='No GUI, no writes')
    parser.add_argument('--student-id', type=int, help='Optional candidate SQL benchmark (ID omitted from report)')
    parser.add_argument('--output', default='v32_windows_perf_report.json')
    ns = parser.parse_args(args)
    path = Path(ns.database).resolve(strict=True)
    info = inspect_query_plans(path)
    if ns.student_id is not None:
        info['optional_query_comparison'] = compare_header_stat_queries(path, ns.student_id)
    if ns.inspect_only:
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return 0

    # Manual confirmation that the DB is a disposable TEST COPY is required.
    if os.environ.get('ODEV_V32_TEST_DB_CONFIRMED') != '1':
        parser.error('GUI profilini baslatmadan once TEST kopyayi onaylamak icin ODEV_V32_TEST_DB_CONFIRMED=1 tanimlayin.')
    os.environ['YKS_DB_PATH'] = str(path)
    collector = MethodStats()
    from ui.odev_kontrol import OdevKontrolDialog
    from ui.homework_form import OdevTakipFormu
    for method in ('_kume_ac', '_kaydet', '_on_table_item_changed', '_hesapla_yuzde',
                   '_refresh_right_table_styles', '_update_header_stats', '_hepsi_tamam', '_hepsi_geri'):
        install_method_timing(OdevKontrolDialog, method, collector)
    for method in ('_refresh_verilen_table', '_wizard_transfer_tasks', '_kaydet_kume'):
        install_method_timing(OdevTakipFormu, method, collector)

    def write_report():
        report = collector.report()
        report['sql_inspection'] = info
        out = Path(ns.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print('V32 performance report:', out)
    atexit.register(write_report)

    import app
    app.main()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
