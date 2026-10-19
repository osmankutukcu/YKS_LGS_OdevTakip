# -*- coding: utf-8 -*-
"""CI release gate, no external dependencies."""
import argparse
import hashlib
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def read_versions(root=ROOT):
    py = (root / 'version.py').read_text(encoding='utf-8')
    iss = (root / 'setup.iss').read_text(encoding='utf-8')
    a = re.search(r'^APP_VERSION\s*=\s*["\'](\d+\.\d+\.\d+)["\']', py, re.M)
    b = re.search(r'^#define MyAppVersion ["\'](\d+\.\d+\.\d+)["\']', iss, re.M)
    if not a or not b or a.group(1) != b.group(1):
        raise ValueError('version.py ve setup.iss surumleri AYNI olmali')
    return a.group(1)


def check_tracked_databases(root=ROOT):
    """Git deposunda takip edilen hassas dosyaları, veritabanlarını ve özel anahtarları denetler."""
    result = subprocess.run(['git', 'ls-files', '-z'], cwd=root, check=True,
                            capture_output=True).stdout
    files = [s.decode('utf-8', 'replace') for s in result.split(b'\x00') if s]
    
    # 1. Yasaklı uzantılar ve yollar
    forbidden_suffixes = ('.db', '.sqlite', '.sqlite3', '.db-wal', '.db-shm', '.sqlite-wal', '.sqlite-shm', '.lic', '.key', '.pem', '.p12', '.pfx')
    forbidden = []
    
    for f in files:
        f_lower = f.lower()
        if f_lower.endswith(forbidden_suffixes):
            forbidden.append(f"{f} (yasaklı uzantı)")
        elif '_admin_tools_private' in f_lower or 'keygen' in f_lower or 'lisans_uretici' in f_lower:
            forbidden.append(f"{f} (gizli admin/keygen aracı)")
        elif f.endswith('.py') and not f.startswith('tests/') and f != 'tools/validate_release.py':
            # İçerik taraması: Takip edilen kodlarda özel anahtar (RSA_D / PRIVATE KEY) olmamalı
            try:
                content = (root / f).read_text(encoding='utf-8', errors='ignore')
                priv_marker = 'BEGIN ' + 'PRIVATE KEY'
                rsa_priv_marker = 'BEGIN RSA ' + 'PRIVATE KEY'
                if priv_marker in content or rsa_priv_marker in content or re.search(r'\bRSA_D(_V\d)?\s*=\s*\d{20,}', content):
                    forbidden.append(f"{f} (özel anahtar / RSA_D tespiti)")
            except Exception:
                pass
                
    if forbidden:
        raise ValueError('Git deposunda yayınlanmaması gereken hassas dosya/anahtar tespit edildi:\n  - ' + '\n  - '.join(forbidden))


def check_distribution_hygiene(dist_dir=ROOT / 'dist'):
    """Derleme (dist) klasörünün hassas dosyalardan arındırıldığını doğrular."""
    if not dist_dir.is_dir():
        return
    forbidden = []
    for item in dist_dir.rglob('*'):
        if not item.is_file():
            continue
        name_lower = item.name.lower()
        rel_str = str(item.relative_to(dist_dir)).lower()
        if '_admin_tools_private' in rel_str or 'keygen' in name_lower or 'lisans_uretici' in name_lower:
            forbidden.append(str(item.relative_to(dist_dir)))
        elif name_lower.endswith(('.db', '.sqlite', '.sqlite3', '.lic', '.key', '.p12', '.pfx')):
            forbidden.append(str(item.relative_to(dist_dir)))
        elif name_lower.endswith('.pem') and name_lower != 'cacert.pem':
            forbidden.append(str(item.relative_to(dist_dir)))
    if forbidden:
        raise ValueError('Dağıtım paketinde (dist) sızan gizli/admin dosya tespit edildi:\n  - ' + '\n  - '.join(forbidden))


def emit_checksum(installer):
    installer = pathlib.Path(installer)
    if not installer.is_file() or installer.name != 'OdevTakip_v2_Kurulum.exe':
        raise ValueError('Beklenen Inno Setup EXE bulunamadi')
    with installer.open('rb') as f:
        if f.read(2) != b'MZ':
            raise ValueError('Kurulum Windows EXE biciminde degil')
    hasher = hashlib.sha256()
    with installer.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            hasher.update(chunk)
    sidecar = installer.with_name(installer.name + '.sha256')
    sidecar.write_text(hasher.hexdigest() + '  ' + installer.name + '\n', encoding='utf-8')
    return sidecar


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tag')
    ap.add_argument('--check-tracked', action='store_true')
    ap.add_argument('--check-hygiene', action='store_true')
    ap.add_argument('--installer')
    ap.add_argument('--checksum', action='store_true')
    args = ap.parse_args()
    ver = read_versions()
    if args.tag and args.tag != 'v' + ver:
        raise ValueError(f'Tag {args.tag!r} yerine v{ver} olmali')
    if args.check_tracked:
        check_tracked_databases()
    if args.check_hygiene or args.checksum:
        check_distribution_hygiene()
    if args.checksum:
        if not args.installer: raise ValueError('--installer gerekli')
        print('SHA256:', emit_checksum(args.installer))
    print('Release surumu kontrol edildi:', ver)

if __name__ == '__main__':
    try:
        main()
    except (ValueError, subprocess.CalledProcessError) as exc:
        print('HATA:', exc, file=sys.stderr)
        sys.exit(1)
