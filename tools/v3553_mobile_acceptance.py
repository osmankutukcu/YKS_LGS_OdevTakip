# -*- coding: utf-8 -*-
"""V3.5.53 Mobile PDF release gate (strict, no hardware claims).

Source checks use no student data. Manual acceptance is commit/version bound,
platform-specific, and must originate from people who tested real devices.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PLATFORMS = ('windows', 'macos', 'iphone', 'android')
REQUIRED = {
    'windows': ('create_7_10_14_day_pdf', 'whatsapp_student_parent', 'call_links',
                'protected_forms_unchanged', 'reopen_exported_pdf'),
    'macos': ('create_7_10_14_day_pdf', 'whatsapp_student_parent', 'call_links',
              'old_agenda_unchanged', 'reopen_exported_pdf'),
    'iphone': ('receive_pdf_as_file', 'offline_student_navigation',
               'whatsapp_draft_student_parent', 'phone_call_dialog',
               'long_message_parts', 'return_to_document'),
    'android': ('receive_pdf_as_file', 'offline_student_navigation',
                'whatsapp_draft_student_parent', 'phone_call_dialog',
                'long_message_parts', 'return_to_document'),
}
MOBILE_MODULES = (
    'services/mobile_agenda_pdf_v3541.py',
    'services/smart_mobile_pdf_v3545.py',
    'services/mobile_pdf_system_bridge_v3546.py',
    'services/mobile_pdf_live_gateway_v3547.py',
    'services/mobile_pdf_secure_portal_v3548.py',
    'services/offline_pdf_message_center_v3549.py',
    'services/mobile_pdf_feedback_v3550.py',
    'services/mobile_pdf_feedback_center_v3551.py',
    'services/mobile_pdf_deployment_v3552.py',
    'ui/smart_mobile_pdf_dialog_v3545.py',
)


def version_from_root(root=ROOT):
    import ast
    tree = ast.parse((Path(root)/'version.py').read_text(encoding='utf8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'APP_VERSION' for t in node.targets):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return node.value.value
    raise ValueError('APP_VERSION bulunamadı')


def check_mobile_source(root=ROOT):
    root=Path(root)
    from tools.v3527_core_guard import audit
    from tools.v35_release_gate import check_source
    if audit(root)['status'] != 'PASS':
        raise ValueError('Ödev Takip/Kontrol korunan çekirdek denetimi başarısız')
    check_source(root)
    v=version_from_root(root)
    meta=json.loads((root/'version.json').read_text(encoding='utf8'))
    setup=(root/'setup.iss').read_text(encoding='utf8')
    if meta.get('version') != v or f'#define MyAppVersion "{v}"' not in setup:
        raise ValueError('Üçlü sürüm bilgisi uyuşmuyor')
    missing=[name for name in MOBILE_MODULES if not (root/name).is_file()]
    if missing:
        raise ValueError('Akıllı PDF bağımlılıkları eksik: '+','.join(missing))
    # Only the dedicated mobile PDF extension may be changed; legacy engine preserved
    return {'version':v, 'mobile_modules':len(MOBILE_MODULES),
            'protected_core':'PASS', 'actual_device_acceptance':'NOT_VERIFIED',
            'live_school_https_ssosync':'NOT_VERIFIED', 'release_authorized':False}


def template(version=None):
    return {
        'version':version or version_from_root(),
        'git_commit':'<exact 40-digit Git commit SHA>',
        'tested_at':'<YYYY-MM-DD>',
        'test_data':'SYNTHETIC_ONLY',
        'devices':{
            name:{'tester':'<tester name>', 'device':'<OS version / device / PDF viewer>',
                  'checks':{check:'PENDING' for check in checks}}
            for name, checks in REQUIRED.items()
        },
        'live_https_status':'NOT_TESTED',
        'notes':'Geri bildirim ve canlı sunucu ayrı kabul gerektirir; gerçek öğrenci kaydı kullanmayın.',
    }


def validate_device_acceptance(data, *, version, commit, today=None):
    if not isinstance(data,dict) or data.get('version')!=version:
        raise ValueError('Sürüm eşleşmiyor')
    if not re.fullmatch(r'[a-fA-F0-9]{40}', str(commit)) or str(data.get('git_commit','')).lower()!=commit.lower():
        raise ValueError('Git SHA eksik veya uyuşmuyor')
    if data.get('test_data')!='SYNTHETIC_ONLY':
        raise ValueError('Sadece sahte test verisiyle cihaz kabulü yapılabilir')
    try:
        when=date.fromisoformat(data['tested_at'])
    except (TypeError, ValueError, KeyError) as exc:
        raise ValueError('Cihaz kabul tarihi geçersiz') from exc
    delta=(today or date.today())-when
    if delta < timedelta(0) or delta > timedelta(days=30):
        raise ValueError('Cihaz kabul tarihi gelecek veya 30 günden eski')
    entries=data.get('devices')
    if not isinstance(entries,dict):
        raise ValueError('Cihaz kabul matrisi eksik')
    for platform, tests in REQUIRED.items():
        item=entries.get(platform)
        if not isinstance(item,dict):
            raise ValueError(f'{platform}: cihaz kaydı bulunamadı')
        for field in ('tester','device'):
            val=item.get(field)
            if not isinstance(val,str) or len(val.strip())<4 or '<' in val or 'TODO' in val:
                raise ValueError(f'{platform}: {field} doldurulmamış')
        checks=item.get('checks')
        if not isinstance(checks,dict) or any(checks.get(check)!='PASS' for check in tests):
            raise ValueError(f'{platform}: zorunlu gerçek cihaz kontrolleri tamamlanmadı')
    # Live server is deliberately NOT certified by PDF-device acceptance.
    if data.get('live_https_status') not in ('NOT_TESTED','SEPARATELY_VERIFIED'):
        raise ValueError('Canlı servis kabul durumu geçersiz')
    return {'version':version,'git_commit':commit,'platforms':list(PLATFORMS),
            'mobile_pdf_device_status':'PASS',
            'live_https_status':data['live_https_status']}


def main(argv=None):
    parser=argparse.ArgumentParser(description='V3.5.53 Mobil PDF kaynak ve gerçek cihaz kabul kapısı')
    parser.add_argument('--check-source', action='store_true')
    parser.add_argument('--require-device-acceptance', action='store_true')
    parser.add_argument('--acceptance',default='release/mobile_pdf_device_acceptance.json')
    parser.add_argument('--commit')
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--report',type=Path)
    ns=parser.parse_args(argv)
    result=check_mobile_source(ns.root)
    if ns.require_device_acceptance:
        from tools.v35_release_gate import expected_commit
        sha=ns.commit or expected_commit(ns.root)
        path=(ns.root/ns.acceptance).resolve()
        if not path.is_file():
            raise ValueError('Gerçek Windows/Mac/iPhone/Android kabul formu yok; yayın engellendi')
        result.update(validate_device_acceptance(json.loads(path.read_text(encoding='utf8')),
                         version=result['version'],commit=sha))
    if ns.report:
        ns.report.parent.mkdir(parents=True,exist_ok=True)
        ns.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result, ensure_ascii=False))
    return 0

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError,OSError,json.JSONDecodeError) as exc:
        print('MOBİL PDF YAYIN ENGELİ:',exc,file=sys.stderr)
        raise SystemExit(2)
