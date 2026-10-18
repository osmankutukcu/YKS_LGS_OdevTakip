#!/usr/bin/env python3
"""Additive, opt-in V12 PWA pilot helper. Does not modify the V12 core files.

All mutable operations are restricted to the user's local pilot directory.
An original SQLite file is opened only in read-only mode and copied with SQLite backup.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import secrets
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
PILOT_HOME = Path(os.environ.get('LOCALAPPDATA') or (Path.home() / '.local' / 'share')) / 'YKS_LGS_PWA_Pilot'
PILOT_DB = PILOT_HOME / 'pilot.sqlite3'
PILOT_TOKEN = PILOT_HOME / 'pilot_access_key.txt'
ASSETS = (
    'web_api/main.py', 'web_api/auth.py', 'web_api/sync_engine.py',
    'web_api/static/manifest.json', 'web_api/static/sw.js',
    'web_api/static/js/offline_sync.js', 'web_api/static/js/offline_health_v6.js',
    'web_api/static/js/offline_vault.js', 'web_api/static/js/offline_secure_store_v5.js',
    'web_api/static/js/offline_paged_v8.js', 'web_api/static/js/offline_delta_v9.js',
    'web_api/static/js/offline_resilience_v10.js', 'web_api/templates/index.html',
)

def check_layout():
    problems = [f'Dosya bulunamadı: {p}' for p in ASSETS if not (ROOT / p).is_file()]
    manifest_file = ROOT / 'web_api/static/manifest.json'
    if manifest_file.is_file():
        try:
            manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
            if manifest.get('display') != 'standalone':
                problems.append('PWA manifest display=standalone değil.')
            for item in manifest.get('icons') or []:
                # icon source is /static/... and is physically web_api/static/...
                icon = ROOT / 'web_api/static' / item['src'].removeprefix('/static/')
                if not icon.is_file(): problems.append('Simge yok: ' + item['src'])
        except (ValueError, KeyError) as err:
            problems.append('Manifest okunamadı: ' + str(err))
    sw = ROOT / 'web_api/static/sw.js'
    if sw.is_file() and "'/static/manifest.json'" not in sw.read_text(encoding='utf-8'):
        problems.append('Service Worker önbellek manifesti beklenen düzende değil.')
    return problems

def sqlite_readonly(path: Path):
    try:
        uri = path.resolve().as_uri() + '?mode=ro'
        con = sqlite3.connect(uri, uri=True, timeout=15)
        check = con.execute('PRAGMA quick_check').fetchone()[0]
    except Exception:
        con = sqlite3.connect(str(path.resolve()), timeout=15)
        con.execute('PRAGMA query_only = ON')
        check = con.execute('PRAGMA quick_check').fetchone()[0]

    try:
        if check != 'ok': raise RuntimeError('Veritabanı bütünlük kontrolü: ' + str(check))
        names = {x[0] for x in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for required in ('ogrenci', 'odev_kume', 'odev_satir'):
            if required not in names: raise RuntimeError('Veritabanı şeması uyumsuz: ' + required)
    except Exception:
        con.close()
        raise
    return con

def backup(source: Path):
    source = source.expanduser().resolve()
    if not source.is_file(): raise RuntimeError('Kaynak SQLite dosyası bulunamadı: ' + str(source))
    PILOT_HOME.mkdir(parents=True, exist_ok=True)
    if PILOT_DB.exists():
        raise RuntimeError('Pilot veritabanı zaten var. Bekleyen test ödevlerini korumak için üzerine yazmıyorum: ' + str(PILOT_DB))
    src = sqlite_readonly(source)
    try:
        temp = PILOT_HOME / ('pilot_copy_' + secrets.token_hex(8) + '.tmp')
        dst = sqlite3.connect(str(temp))
        try:
            src.backup(dst)
        finally:
            dst.close()
        ver = sqlite_readonly(temp); ver.close()
        temp.replace(PILOT_DB)
    finally:
        src.close()
    print('TEST VERİTABANI GÜVENLİ KOPYASI ALINDI:', PILOT_DB)
    print('Orijinal veritabanına yazma işlemi yapılmadı.')
    print('DİKKAT: Bu kopyada da öğrenci verileri olabilir; kimseyle paylaşmayın.')

def serve():
    problems = check_layout()
    if problems: raise RuntimeError('\n'.join(problems))
    if not PILOT_DB.is_file(): raise RuntimeError('Önce PWA_PILOT_HAZIRLA.bat ile test DB kopyası alın.')
    con = sqlite_readonly(PILOT_DB)
    try: count = con.execute('SELECT count(*) FROM ogrenci').fetchone()[0]
    finally: con.close()
    PILOT_HOME.mkdir(parents=True, exist_ok=True)
    if PILOT_TOKEN.exists():
        token = PILOT_TOKEN.read_text(encoding='ascii').strip()
        if len(token) < 32: raise RuntimeError('Pilot erişim anahtarı geçersiz, otomatik sıfırlanmadı.')
    else:
        token = secrets.token_urlsafe(48)
        with PILOT_TOKEN.open('x', encoding='ascii') as out: out.write(token)
        try: os.chmod(PILOT_TOKEN, 0o600)
        except OSError: pass
    os.environ['YKS_DB_PATH'] = str(PILOT_DB)
    os.environ['YKS_WEB_ACCESS_TOKEN'] = token
    # Never bind on the LAN. HTTPS to the phone must be provided by a trusted private reverse proxy.
    print('\n=== V12 PWA PILOTU ===')
    print('Yerel sunucu: http://127.0.0.1:8000')
    print('Test DB: ', PILOT_DB)
    print('Öğrenci adedi:', count)
    print('TELEFON için yerel IP/HTTP kullanmayın. Güvenilir HTTPS adresi gerekir.')
    print('Erişim anahtarınız (başkasıyla paylaşmayın):\n', token)
    print('Kapatmak için Ctrl+C. Bu pencere açık kalmalıdır.\n', flush=True)
    try:
        import uvicorn
        # App imports PyQt6 via db.py; dependencies must be installed on this Windows machine.
        uvicorn.run('web_api.main:app', host='127.0.0.1', port=8000, log_level='warning')
    except ImportError as err:
        raise RuntimeError('Windows Python bağımlılığı eksik: ' + str(err) + '. requirements_win.txt kontrol edin.') from err

def main():
    parser = argparse.ArgumentParser(description='V12 çevrimdışı PWA test ortamı (ana sistem değişmeden).')
    sub = parser.add_subparsers(dest='cmd', required=True)
    sub.add_parser('preflight')
    b = sub.add_parser('backup'); b.add_argument('--source', required=True, type=Path)
    sub.add_parser('serve')
    args = parser.parse_args()
    try:
        if args.cmd == 'preflight':
            problems = check_layout()
            if problems: raise RuntimeError('\n'.join(problems))
            print('PWA STATİK ÖN DENETİM BAŞARILI. Bu gerçek telefon testi değildir.')
            print('Test veritabanı:', 'HAZIR' if PILOT_DB.is_file() else 'HENÜZ HAZIR DEĞİL')
        elif args.cmd == 'backup': backup(args.source)
        elif args.cmd == 'serve': serve()
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        print('HATA:', exc, file=sys.stderr)
        return 2
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
