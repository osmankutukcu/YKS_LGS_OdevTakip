# -*- coding: utf-8 -*-
"""Fail-closed static audit of the Windows report release path.

No real student files, network, GUI, installer or Windows process is opened.
This is a *preflight* only: GUI+installer testing remains mandatory.
"""
from __future__ import annotations
from pathlib import Path
import argparse
import ast
import sys


def verify(root: Path) -> tuple[str, ...]:
    root = root.resolve()
    required = (
        'tools/v35_windows_smoke.py',
        'tests/test_v3554_stabilization.py',
        'tests/test_v3587_stabilization.py',
        'services/bulk_reports_v3586.py',
        'ui/pdf_page_preview_v3586.py',
        'fonts/DejaVuSans.ttf',
        'fonts/DejaVuSans-Bold.ttf',
        'OdevTakip_v2.spec',
        'build_app.py',
        '.github/workflows/build_installer.yml',
    )
    for path in required:
        if not (root / path).is_file():
            raise ValueError('Eksik dağıtım girdisi: ' + path)
    spec = (root / 'OdevTakip_v2.spec').read_text('utf-8')
    ast.parse(spec)
    for fragment in ("'fitz'", "'reportlab'", "('fonts', 'fonts')"):
        if fragment not in spec:
            raise ValueError('PyInstaller girdisi eksik: ' + fragment)
    builder = (root / 'build_app.py').read_text('utf-8')
    if 'OdevTakip_v2.spec' not in builder or 'PyInstaller' not in builder:
        raise ValueError('Windows derlemesi doğrulanan spec dosyasını kullanmıyor.')
    workflow = (root / '.github/workflows/build_installer.yml').read_text('utf-8')
    for fragment in (
        'python -m pip install "PyMuPDF>=1.24,<2"',
        'python tools/v3587_ci_preflight.py',
        'tests.test_v3587_stabilization',
        'python -m pytest -q tests/test_v3554_stabilization.py',
        'python tools/v35_windows_smoke.py',
        'Windows EXE acilis testi basarisiz; kurulum yayinlanamaz',
    ):
        if fragment not in workflow:
            raise ValueError('CI akışındaki zorunlu adım eksik: ' + fragment)
    # The previous CI explicitly erased the EXE smoke failure. Forbid that.
    start = workflow.index('      - name: Gercek Windows EXE')
    end = workflow.index('      - name: Inno Setup kur', start)
    if 'exit 0' in workflow[start:end]:
        raise ValueError('Windows EXE testi başarısızken sonuç yok sayılıyor.')
    if workflow.index('      - name: V3.5.87 Rapor Merkezi') > workflow.index('      - name: PyInstaller uygulama EXE'):
        raise ValueError('Rapor regresyon testi EXE derlemesinden sonra çalışıyor.')
    legacy = (root / 'tests/test_v3554_stabilization.py').read_text('utf-8')
    if "' '.join(' '.join(pg.get_text() for pg in doc).split())" not in legacy:
        raise ValueError('PDF metnindeki satır bölünmesine dayanıklı güvenlik testi eksik.')
    if 'self.assertFalse(any(u.startswith((' not in legacy:
        raise ValueError('Bağlantı güvenlik koşulları korunmamış.')
    return required


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        required = verify(args.root)
    except (ValueError, OSError, SyntaxError) as ex:
        print('RED / CI ön denetimi geçemedi:', ex, file=sys.stderr)
        return 1
    print(f'GEÇTİ: {len(required)} kritik kaynak/bağımlılık, PDF testleri ve EXE hata engeli doğrulandı.')
    print('Bu sonuç gerçek Windows EXE açılışı, yazdırma veya manuel kullanıcı kabulü yerine geçmez.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
