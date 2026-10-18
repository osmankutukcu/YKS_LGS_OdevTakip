# -*- coding: utf-8 -*-
"""V12 RC salt-okunur bütünlük ve yayın durumu denetimi.
Bu araç veritabanlarına dokunmaz ve tek başına canlı yayın onayı vermez.
"""
from __future__ import annotations
from pathlib import Path
import argparse, hashlib, json, sys
ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'release/V12_RC_CONTENT_HASHES.json'

def run(root=ROOT):
    manifest=json.loads((root/'release/V12_RC_CONTENT_HASHES.json').read_text(encoding='utf-8'))
    missing=[]; changed=[]
    for name,expected in manifest['sha256'].items():
        p=root/name
        if not p.is_file(): missing.append(name)
        elif hashlib.sha256(p.read_bytes()).hexdigest()!=expected: changed.append(name)
    unexpected=[]
    allowed=set(manifest['sha256'])|{'release/V12_RC_CONTENT_HASHES.json'}
    for p in root.rglob('*'):
        if not p.is_file():continue
        rel=p.relative_to(root).as_posix()
        if '__pycache__' in p.parts or rel.startswith('.pytest_cache/') or rel.endswith('.pyc'):continue
        if rel not in allowed:unexpected.append(rel)
    prohibited=[name for name in allowed if any(name.lower().endswith(ext) for ext in
                ('.db','.sqlite','.sqlite3','.db-wal','.db-shm','.env','.pem','.key'))]
    legacy_gate = (root/'tools/v35_release_gate.py').is_file()
    status='PASS' if not (missing or changed or unexpected or prohibited or not legacy_gate) else 'FAIL'
    return {'file_integrity':status,'files_checked':len(manifest['sha256']),
       'missing':missing,'changed':changed,'unexpected':unexpected,'prohibited':prohibited,
       'legacy_gate_present':legacy_gate,
       'production_release_approved':False,
       'notice':'PASS dosya bütünlüğüdür; Windows/iOS/Android gerçek kabul testi ve onay olmadan STABLE değil.'}

if __name__=='__main__':
    result=run()
    print(json.dumps(result,ensure_ascii=False,indent=2))
    sys.exit(0 if result['file_integrity']=='PASS' else 1)
