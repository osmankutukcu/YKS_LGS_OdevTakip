#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V25.1 Windows developer-only diagnostic. No WhatsApp network access.

Only reads legacy queue on --inspect. --copy explicitly creates a new DPAPI
queue without changing the old queue or activating any delivery engine.
"""
import argparse
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.whatsapp_queue.safe_copy_v251 import (assess_legacy,
    create_encrypted_copy, MigrationBlocked)
from services.whatsapp_queue.dpapi_v250 import PlatformProtectionUnavailable, ProtectionError


def main():
    p = argparse.ArgumentParser(description='V25.1 WhatsApp kuyruk gizlilik kontrolü; gönderim yapmaz')
    p.add_argument('--source', required=True, help='Eski kuyruğun mutlak dosya yolu')
    p.add_argument('--destination', help='Yeni, daha önce oluşturulmamış şifreli kuyruğun yolu')
    p.add_argument('--copy', action='store_true', help='Açık onay gerektirir; eski dosya korunur')
    p.add_argument('--i-understand-and-consent', action='store_true')
    args = p.parse_args()
    try:
        if not args.copy:
            if args.i_understand_and_consent:
                p.error('Onay bayrağı yalnızca --copy ile kullanılır')
            result = assess_legacy(args.source)
            print('KONTROL: Parti sayısı:', result['batches'], 'İş sayısı:', result['jobs'])
            print('Durumlara göre adetler:', result['states'])
            print('Hiçbir telefon numarası veya mesaj gösterilmedi.')
            return 0
        if os.name != 'nt':
            print('DURDURULDU: Gerçek DPAPI ile kopyalama yalnızca Windows üzerinde.',file=sys.stderr)
            return 2
        if not args.destination or not args.i_understand_and_consent:
            print('DURDURULDU: Hedef dosya ve açık onay gerekli.',file=sys.stderr)
            return 2
        result = create_encrypted_copy(args.source, args.destination, explicit_consent=True)
        print('Kopya oluşturuldu. Parti:',result['batches'],'İş:',result['jobs'])
        print('ESKİ DOSYA KORUNDU. Yeni dosya mevcut WhatsApp göndericisine bağlanmadı.')
        return 0
    except (MigrationBlocked, ProtectionError, PlatformProtectionUnavailable, PermissionError,
            OSError, ValueError) as exc:
        print('GÜVENLİK NEDENİYLE DURDURULDU:', str(exc), file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
