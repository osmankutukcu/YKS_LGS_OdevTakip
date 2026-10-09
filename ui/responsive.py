
from PyQt6.QtWidgets import QWidget, QTableWidget, QAbstractScrollArea
from PyQt6.QtCore import Qt

def apply_responsive(root: QWidget):
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
