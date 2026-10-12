"""V13.6 manual reconciliation helper: REVIEW is read-only; APPLY creates a new DB copy.

Review: python tools/reconcile_homework_v136.py review --db input.db --manifest review.json
Apply:  python tools/reconcile_homework_v136.py apply --db input.db --manifest approved.json \
          --output NEW.db --approver "Yetkili" --confirm ONAYLI_KOPYA_OLUSTUR
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from services.homework_reconciliation_v136 import (ACKNOWLEDGEMENT, ReconciliationError,
    build_review_manifest, apply_to_new_copy)


def main(argv=None):
    p=argparse.ArgumentParser(description='Ödev bağlantılarında yönetici onaylı, kopyaya güvenli uzlaştırma.')
    sub=p.add_subparsers(dest='command',required=True)
    r=sub.add_parser('review',help='Salt okunur inceleme dosyası oluştur')
    r.add_argument('--db',type=Path,required=True)
    r.add_argument('--manifest',type=Path,required=True)
    a=sub.add_parser('apply',help='Yalnızca YENİ veritabanı kopyasında onaylı işlem uygula')
    a.add_argument('--db',type=Path,required=True)
    a.add_argument('--manifest',type=Path,required=True)
    a.add_argument('--output',type=Path,required=True)
    a.add_argument('--approver',required=True)
    a.add_argument('--confirm',required=True,help=ACKNOWLEDGEMENT)
    args=p.parse_args(argv)
    try:
        if args.command == 'review':
            result=build_review_manifest(args.db)
            with args.manifest.open('x',encoding='utf-8') as f:
                json.dump(result,f,ensure_ascii=False,indent=2)
            print(f"İnceleme hazır: {args.manifest} ({len(result['kayitlar'])} satır). Değişiklik yapılmadı.")
        else:
            plan=json.loads(args.manifest.read_text(encoding='utf-8'))
            result=apply_to_new_copy(args.db,plan,args.output,approver=args.approver,acknowledgement=args.confirm)
            print(f"Onaylı YENİ kopya: {args.output}; işlenen satır: {len(result['changes'])}; orijinal değişmedi.")
        return 0
    except (ReconciliationError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f'İşlem reddedildi: {exc}',file=sys.stderr)
        return 2

if __name__=='__main__':
    raise SystemExit(main())
