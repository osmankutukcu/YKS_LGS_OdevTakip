"""Read-only Windows display/DPI diagnostic; writes no user information.

Windows: python tools/v22_windows_screen_diagnostics.py
"""
import sys
from pathlib import Path
# Running directly from tools/ must still locate the project root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PyQt6.QtWidgets import QApplication
from services.responsive_v22 import (compact_main_shell,
                                      compact_homework_workspace)


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    for i, screen in enumerate(app.screens(), 1):
        area = screen.availableGeometry()
        geo = screen.geometry()
        print(f'Monitör {i}: masaüstü {geo.width()}×{geo.height()}, '
              f'kullanılabilir {area.width()}×{area.height()} Qt mantıksal piksel, '
              f'ölçek {screen.devicePixelRatio():.2f}x')
        print('  Ana menü:', 'dar görünüm' if compact_main_shell(area.width())
              else 'normal görünüm')
        print('  Öğrenci 360°:', 'dönüşümlü sağ alan' if
              compact_homework_workspace(area.width()) else 'üç sütun')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
