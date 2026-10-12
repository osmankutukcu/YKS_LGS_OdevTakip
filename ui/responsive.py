
from PyQt6.QtWidgets import QWidget, QTableWidget, QAbstractScrollArea, QApplication
from PyQt6.QtCore import Qt

def apply_responsive(root: QWidget):
    """Original table tuning, with a monitor-aware minimum for dialogs.

    Available geometry excludes the Windows taskbar; Qt6 returns logical
    pixels after per-monitor DPI scaling. This must not override OS fonts.
    """
    from services.responsive_v22 import screen_bound_minimum
    screen = root.screen() or QApplication.primaryScreen()
    if screen is not None:
        rect = screen.availableGeometry()
        min_width, min_height = screen_bound_minimum(
            (960, 600), (rect.width(), rect.height())
        )
        root.setMinimumSize(min_width, min_height)
        if root.isWindow():
            root.resize(min(root.width(), max(1, rect.width() - 16)),
                        min(root.height(), max(1, rect.height() - 16)))
    else:
        root.setMinimumSize(960, 600)
    root.setAttribute(Qt.WidgetAttribute.WA_LayoutOnEntireRect, True)
    _walk(root)

def _walk(w):
    for ch in w.findChildren(QWidget):
        try:
            ch.setSizePolicy(ch.sizePolicy().Expanding, ch.sizePolicy().Expanding)
        except Exception:
            pass
        if isinstance(ch, QTableWidget):
            ch.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
            try:
                ch.horizontalHeader().setStretchLastSection(True)
            except Exception:
                pass
