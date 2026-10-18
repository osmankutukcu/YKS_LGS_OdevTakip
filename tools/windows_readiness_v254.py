#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V25.4 offline Windows readiness report. Never connects to WhatsApp.

Only synthetic tests. No student, parent or WhatsApp files are accessed.
No dependencies are installed. No sending capability can be enabled here.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from services.whatsapp_queue.readiness_v252 import windows_offline_readiness

EXPECTED = frozenset({
    'dpapi_roundtrip', 'purpose_isolation',
    'vault_restart_and_no_plaintext', 'legacy_copy_source_unchanged',
    'encrypted_queue_restart_and_no_plaintext',
    'crash_recovery_no_duplicate_send',
})
STATUS = {
    'PASS_WINDOWS_SYNTHETIC_TEST': ('KONTROLLER BASARILI',
         'Windows uzerindeki sahte veri testleri basarili. Gercek WhatsApp gonderimi test EDILMEDI.'),
    'NOT_RUN_WINDOWS_REQUIRED': ('WINDOWS GEREKLI',
         'Bu kontrol gercek Windows bilgisayarinda calistirilmalidir.'),
    'FAIL_CLOSED': ('KONTROL BASARISIZ',
         'Bir guvenlik adimi tamamlanamadi; arka plan baglantisi KAPALI kalir.'),
}

def build_report(*, checker=windows_offline_readiness, os_name=None) -> dict:
    """Construct strictly allowlisted, PII-free diagnostic result."""
    actual_os = os.name if os_name is None else os_name
    if actual_os != 'nt':
        result = 'NOT_RUN_WINDOWS_REQUIRED'
        checks = []
    else:
        try:
            raw = checker()
            result = str(raw.get('result'))
            checks = raw.get('passed_checks', [])
            # Never trust injected/test-double or incomplete check reports.
            if result == 'PASS_WINDOWS_SYNTHETIC_TEST':
                if not isinstance(checks,list) or set(checks) != EXPECTED or len(checks) != len(EXPECTED):
                    result = 'FAIL_CLOSED'
        except Exception:
            result = 'FAIL_CLOSED';checks=[]
    if result not in STATUS:result = 'FAIL_CLOSED'
    title,desc = STATUS[result]
    ok = result == 'PASS_WINDOWS_SYNTHETIC_TEST'
    # All outgoing fields are fixed or allowlisted; no paths or user data.
    return {
        'version':'V25.4',
        'test_kind':'synthetic_offline_only',
        'os_check':'WINDOWS' if actual_os == 'nt' else 'WINDOWS_REQUIRED',
        'result':result,
        'human_title':title,
        'human_explanation':desc,
        'passed_checks':sorted(EXPECTED) if ok else [],
        'two_distinct_windows_users':'NOT_VERIFIED',
        'actual_whatsapp_login':'NOT_ATTEMPTED',
        'actual_whatsapp_send':'NOT_ATTEMPTED',
        'personal_data_read':'NONE',
        'secure_queue_is_default':'NO',
        'baileys_enabled':False,
        'automatic_sending_enabled':False,
        'next_step': ('V25.3 iki Windows kullanicisi testi ve gercek Windows uygulama testi gerekli.'
                      if ok else 'Windows bilgisayarda tanilamayi tekrar calistirin ve teknik inceleme yaptirin.'),
    }

def _safe_output_dir(requested: str | None) -> Path:
    if requested:
        target = Path(requested).expanduser()
    elif os.name == 'nt':
        appdata = os.environ.get('LOCALAPPDATA')
        if not appdata: raise RuntimeError('Windows yerel veri klasoru bulunamadi.')
        target = Path(appdata)/'OdevTakip'/'Guvenlik_Raporlari_V254'
    else:
        target = Path(tempfile.gettempdir())/'odevtakip_v254_offline_reports'
    if target.is_symlink(): raise RuntimeError('Baglanti klasorune rapor yazilamaz.')
    target.mkdir(parents=True,exist_ok=True)
    if target.is_symlink() or not target.is_dir():
        raise RuntimeError('Rapor klasoru guvenli degil.')
    return target

def render_text(report: dict) -> str:
    # Fixed fields only. No path/account/message data.
    return ('ODEV TAKIP - V25.4 WINDOWS GUVENLIK ON KONTROLU\n'
            '================================================\n'
            f'Sonuc: {report["human_title"]}\n'
            f'Aciklama: {report["human_explanation"]}\n'
            f'Tamamlanan sahte veri testi: {len(report["passed_checks"])}/{len(EXPECTED)}\n'
            'Iki gercek Windows hesabi ile ayrim testi: HENUZ DOGRULANMADI\n'
            'Gercek WhatsApp baglantisi/gonderimi: YAPILMADI\n'
            'Veli/ogrenci/gercek oturum bilgisi: OKUNMADI\n'
            'Baileys arka plan motoru: KAPALI\n'
            'Mesaj gonderimi: KAPALI\n'
            f'Sonraki adim: {report["next_step"]}\n'
            'NOT: Bu rapor gercek Windows cihazinda calistirilmadikca dogrulama sayilmaz.\n')

def save_report(report:dict, folder:Path) -> tuple[Path,Path]:
    marker = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')+'_'+secrets.token_hex(3)
    json_path = folder/('V25_4_RAPOR_'+marker+'.json')
    txt_path  = folder/('V25_4_RAPOR_'+marker+'.txt')
    outputs = ((json_path, json.dumps(report,indent=2,sort_keys=True,ensure_ascii=False)+'\n'),
               (txt_path, render_text(report)))
    written=[]
    try:
        for dest,body in outputs:
            # Exclusive creation, never modify student data or existing reports.
            with dest.open('x',encoding='utf-8') as f:
                f.write(body);f.flush();os.fsync(f.fileno())
            written.append(dest)
    except Exception:
        for p in written:p.unlink(missing_ok=True)
        raise
    return json_path,txt_path

def main(argv=None) -> int:
    arg=argparse.ArgumentParser(description='V25.4 cevrimdisi Windows guvenlik on kontrol')
    arg.add_argument('--output-dir',default=None,help='Yalnizca rapor dosyalari icin klasor')
    args=arg.parse_args(argv)
    report=build_report()
    try:
        folder=_safe_output_dir(args.output_dir)
        _,txt=save_report(report,folder)
    except (OSError,RuntimeError,ValueError):
        print('Rapor yazilamadi. WhatsApp arka plan motoru KAPALI kalir.',file=sys.stderr)
        return 2
    print(render_text(report))
    print('Rapor dosyasi: '+str(txt))
    return 0 if report['result']=='PASS_WINDOWS_SYNTHETIC_TEST' else 2

if __name__=='__main__':raise SystemExit(main())
