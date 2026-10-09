# ui/toast.py
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QColor, QPainter, QFont, QGuiApplication
from PyQt6.QtWidgets import QWidget, QGraphicsOpacityEffect, QLabel, QVBoxLayout

# Açık pencerede birden çok toast'ı alt alta istifle
_ACTIVE = []

_KIND_STYLES = {
    "info":    {"bg": "#2563eb", "fg": "#ffffff", "emoji": "ℹ️"},
    "success": {"bg": "#16a34a", "fg": "#ffffff", "emoji": "✅"},
    "warn":    {"bg": "#eab308", "fg": "#111827", "emoji": "⚠️"},
    "error":   {"bg": "#dc2626", "fg": "#ffffff", "emoji": "✖"},
}

class Toast(QWidget):
    from typing import Optional

    def __init__(self, text: str, kind: str = "info", duration_ms: int = 2200,
                 parent: Optional[QWidget] = None, font_size: int = 14, corner: str = "br"):

        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.ToolTip |
                            Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        st = _KIND_STYLES.get(kind, _KIND_STYLES["info"])
        self.bg = QColor(st["bg"])
        self.fg = QColor(st["fg"])

        # içerik
        self.label = QLabel(f"{st['emoji']}  {text}")
        f = QFont("Poppins, Segoe UI, Arial")
        f.setPointSize(font_size)
        f.setBold(True)
        self.label.setFont(f)
        self.label.setStyleSheet(f"color:{st['fg']};")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 12, 18, 12)
        lay.addWidget(self.label)

        # opaklık animasyonu
        self._fx = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._fx)
        self._fade_in = QPropertyAnimation(self._fx, b"opacity", self)
        self._fade_in.setDuration(180)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._fade_out = QPropertyAnimation(self._fx, b"opacity", self)
        self._fade_out.setDuration(220)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade_out.finished.connect(self._close_and_unstack)

        # konumlandırma
        self._corner = corner
        self._duration = duration_ms

    # arka planı yuvarlak köşeli boyar
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setBrush(self.bg)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(self.rect(), 12, 12)

    def showEvent(self, _):
        self.adjustSize()
        self._place()
        _ACTIVE.append(self)
        self._fade_in.start()
        QTimer.singleShot(self._duration, self.hide_smooth)

    def hide_smooth(self):
        self._fade_out.start()

    def _close_and_unstack(self):
        try:
            _ACTIVE.remove(self)
        except ValueError:
            pass
        self.close()
        # üsttekileri aşağı kaydır
        base = self._anchor()
        margin = 14
        y = base.y()
        for t in _ACTIVE:
            geo = t.geometry()
            if self._corner in ("br","tr"):
                y -= geo.height() + margin
            else:
                y += geo.height() + margin
            geo.moveTop(y)
            t.setGeometry(geo)

    def _anchor(self):
        # parent varsa onu, yoksa aktif ekranı baz al
        if self.parent() is not None:
            return self.parent().frameGeometry()
        scr = QGuiApplication.primaryScreen()
        return scr.availableGeometry()

    def _place(self):
        margin = 16
        stack_gap = 14
        base = self._anchor()
        w, h = self.width(), self.height()

        # mevcut toasts sayısına göre yeri ayarla
        stacked_h = sum(t.height()+stack_gap for t in _ACTIVE)

        if self._corner == "br":  # bottom-right
            x = base.right() - w - margin
            y = base.bottom() - h - margin - stacked_h
        elif self._corner == "bl":  # bottom-left
            x = base.left() + margin
            y = base.bottom() - h - margin - stacked_h
        elif self._corner == "tr":  # top-right
            x = base.right() - w - margin
            y = base.top() + margin + stacked_h
        else:  # "tl"
            x = base.left() + margin
            y = base.top() + margin + stacked_h

        self.setGeometry(QRect(x, y, w, h))

def show_toast(parent: QWidget, text: str,
               kind: str="info", duration_ms: int=2200, font_size: int=14, corner: str="br"):
    t = Toast(text=text, kind=kind, duration_ms=duration_ms,
              parent=parent, font_size=font_size, corner=corner)
    t.show()
    return t
