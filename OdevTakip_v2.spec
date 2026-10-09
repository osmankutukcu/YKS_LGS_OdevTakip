# -*- mode: python ; coding: utf-8 -*-
import sys
import os

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
    ('YKS_LGS_HomeworkManager.db', '.'),
]
if os.path.exists('fonts'):
    datas.append(('fonts', 'fonts'))

binaries = []
hiddenimports = [
    'sqlite3',
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.QtPrintSupport',
    'PyQt6.QtSvg',
    'openpyxl',
    'pandas',
    'pyautogui',
    'reportlab',
    'fastapi',
    'uvicorn',
    'pydantic',
    'multipart',
    'certifi',
    'unittest',
    'matplotlib',
]

try:
    from PyInstaller.utils.hooks import collect_all
    ret_cert = collect_all('certifi')
    datas += ret_cert[0]
    binaries += ret_cert[1]
    hiddenimports += ret_cert[2]
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
    excludes=['tkinter'],
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
    upx=False,
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
    upx=False,
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
