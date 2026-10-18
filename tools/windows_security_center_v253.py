#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V25.3 Windows security acceptance test. Never initiates WhatsApp."""
import argparse
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.whatsapp_queue.readiness_v252 import windows_offline_readiness
from services.whatsapp_queue.isolation_v253 import (
    IsolationTestError, current_windows_sid, prepare, verify_other, finalize, cleanup,
)


def main(argv=None):
    cli = argparse.ArgumentParser(description='V25.3 Windows güvenlik testi; gerçek mesaj göndermez')
    mode = cli.add_mutually_exclusive_group(required=True)
    mode.add_argument('--selfcheck', action='store_true', help='V25.2 sahte veri şifreleme testini çalıştır')
    mode.add_argument('--prepare', action='store_true', help='Windows kullanıcı A: test örneği üret')
    mode.add_argument('--verify-other', action='store_true', help='Windows kullanıcı B: izolasyonu denetle')
    mode.add_argument('--finalize', action='store_true', help='Windows kullanıcı A: kaydı yeniden kontrol et')
    mode.add_argument('--cleanup', action='store_true', help='Sadece sentetik test dosyalarını sil')
    cli.add_argument('--folder', default=None, help='İki Windows kullanıcısının erişebildiği TEST klasörü')
    args = cli.parse_args(argv)
    try:
        if os.name != 'nt':
            result = {'version':'V25.3','result':'NOT_RUN_WINDOWS_REQUIRED',
                      'whatsapp_connection':'NOT_ATTEMPTED', 'sending_enabled':False}
            print(json.dumps(result,ensure_ascii=False,indent=2))
            return 2
        if args.selfcheck:
            result = windows_offline_readiness()
            result['version'] = 'V25.3 (V25.2 selfcheck)'
            result['sending_enabled'] = False
            result['baileys_status'] = 'DISABLED'
        else:
            if not args.folder:
                cli.error('Bu işlem için --folder ile önceden oluşturulmuş TEST klasörü belirtin.')
            sid = current_windows_sid() if not args.cleanup else None
            if args.prepare: result = prepare(args.folder,sid)
            elif args.verify_other:result = verify_other(args.folder,sid)
            elif args.finalize:result = finalize(args.folder,sid)
            else: result = cleanup(args.folder)
        print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
        return 0 if result.get('result') in ('PASS_WINDOWS_SYNTHETIC_TEST', 'PASS_TWO_USERS_SYNTHETIC_DPAPI') or result.get('phase') else 2
    except (IsolationTestError, OSError, ValueError) as exc:
        print(json.dumps({'version':'V25.3','result':'FAIL_CLOSED',
                          'reason':str(exc), 'sending_enabled':False},ensure_ascii=False,indent=2),file=sys.stderr)
        return 2

if __name__ == '__main__': raise SystemExit(main())
