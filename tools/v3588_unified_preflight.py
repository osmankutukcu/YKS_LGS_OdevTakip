# -*- coding: utf-8 -*-
"""V3.5.88 unified source release readiness (offline, fail-closed)."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
REQUIRED = ('app.py', 'main_window.py', 'db.py', 'version.py', 'version.json',
            'ui/homework_form.py', 'ui/odev_kontrol.py', 'ui/report_center_v3581.py',
            'services/professional_pdf_v3583.py', 'services/integrated_report_v3584.py',
            'services/report_planner_bridge_v3585.py', 'services/bulk_reports_v3586.py',
            'ui/pdf_page_preview_v3586.py', 'tests/test_v3587_stabilization.py',
            'tools/v3587_ci_preflight.py', 'OdevTakip_v2.spec')
SENSITIVE = ('.db', '.db-wal', '.db-shm', '.sqlite', '.sqlite3', '.lic', '.pem', '.p12', '.pfx', '.key', '.env', '.log')
OMIT_FOLDERS = {'backups', 'logs', '_admin_tools_private', '.idea', '.cache', '__pycache__'}

def check(root: Path=ROOT):
    missing=[f for f in REQUIRED if not (root/f).is_file()]
    if missing: raise ValueError('Eksik tek-kök kaynaklar: '+', '.join(missing))
    for private in ('plan_profiles.json', 'release/v35_source_review.json'):
        if (root/private).exists(): raise ValueError('Kişisel makine verisi: '+private)
    if (root/'YKS_LGS_HomeworkManager v2').exists():
        raise ValueError('Eski iç proje kökü hâlâ bulunuyor')
    v=json.loads((root/'version.json').read_text('utf-8'))
    from tools.validate_release import read_versions
    if v['version'] != read_versions(root): raise ValueError('Uyumsuz sürüm')
    if v.get('channel') not in ('pilot', 'stable'): raise ValueError('Geçersiz yayın kanalı: ' + str(v.get('channel')))
    app=(root/'app.py').read_text('utf-8')
    start=app.index('# 2.1')
    end=app.index('# 3. Üst Gri Şeridi',start)
    if 'ReportCenterDialog' not in app[start:end]: raise ValueError('Rapor Merkezi butonu eksik')
    
    # Git ortamında takip edilen dosyaları, dağıtım zip paketinde ise tüm dosyaları denetle
    is_git = (root / '.git').exists()
    if is_git:
        res = subprocess.run(['git', 'ls-files', '-z'], cwd=root, capture_output=True, check=True)
        paths = [root / p for p in res.stdout.decode('utf-8', 'replace').split('\x00') if p]
    else:
        paths = [p for p in root.rglob('*') if p.is_file()]

    for path in paths:
        if not path.is_file(): continue
        rel=path.relative_to(root)
        if '__pycache__' in rel.parts or path.name.endswith(('.pyc', '.pyo')):
            continue
        if any(part in OMIT_FOLDERS for part in rel.parts):
            raise ValueError('Özel/çalışma klasörü pakette: '+str(rel))
        if str(path.name).lower().endswith(SENSITIVE):
            raise ValueError('Veri/gizli dosya: '+str(rel))
    return len(REQUIRED)

if __name__=='__main__':
    try:
        ch = json.loads((ROOT / 'version.json').read_text('utf-8')).get('channel', 'pilot')
        n=check();print(f'GEÇTİ: {n} tek-kök zorunlu kaynak; kullanıcı verisi yok; yayın kanalı {ch}')
    except (ValueError,OSError,KeyError) as exc:
        print('YAYIN ENGELİ:',exc,file=sys.stderr);sys.exit(1)
