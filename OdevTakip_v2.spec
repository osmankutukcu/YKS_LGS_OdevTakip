# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_all

is_mac = (sys.platform == 'darwin')
app_icon = 'assets/app.icns' if is_mac else 'assets/app_icon.ico'

datas = [
    ('assets', 'assets'),
    ('themes', 'themes'),
    ('ui', 'ui'),
    ('utils', 'utils'),
    ('seed', 'seed'),
    ('services', 'services'),
    ('web_api', 'web_api'),
    ('db.py', '.'),
    ('YKS_LGS_HomeworkManager.db', '.')
]
if os.path.exists('fonts'):
    datas.append(('fonts', 'fonts'))

binaries = []
hiddenimports = [
    'sqlite3', 'PyQt6', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets',
    'openpyxl', 'pandas', 'pyautogui', 'reportlab',
    'fastapi', 'uvicorn', 'pydantic', 'python-multipart'
]

# Robust PyQt6 & sqlite3 collection
try:
    d_qt, b_qt, h_qt = collect_all('PyQt6')
    datas += d_qt
    binaries += b_qt
    hiddenimports += h_qt
except Exception:
    pass

try:
    d_sql, b_sql, h_sql = collect_all('sqlite3')
    datas += d_sql
    binaries += b_sql
    hiddenimports += h_sql
except Exception:
    pass

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='OdevTakip_v2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=app_icon,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='OdevTakip_v2',
)
if is_mac:
    app = BUNDLE(
        coll,
        name='OdevTakip_v2.app',
        icon='assets/app.icns',
        bundle_identifier=None,
    )

