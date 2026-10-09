from __future__ import annotations
# fx.py — PyQt6 için kolay efekt & animasyon yardımcıları (modern & sabit)
from typing import Optional

from PyQt6.QtCore import (
    Qt, QObject, QEasingCurve, QEvent, QPropertyAnimation, QPoint, QRect,
    QParallelAnimationGroup, QTimer, QVariantAnimation
)
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QWidget, QGraphicsDropShadowEffect, QGraphicsOpacityEffect


def _clamp(v: float, a: float, b: float) -> float:
    return max(a, min(b, v))


def _as_color(c: str | QColor | None, fallback: str = "#40a0ff") -> QColor:
    if isinstance(c, QColor):
        return c
    if isinstance(c, str) and c.strip():
        return QColor(c)
    return QColor(fallback)


class FX(QObject):
    """
    Tek satırla kullanım örnekleri:
        FX.use(btn).preset_button()
        FX.use(lbl).hover_glow(radius=24, color="#3aa6ff", strength=0.9).press_flash()
        FX.use(panel).fade_on_show(220)
        FX.fade_in(dialog, dur=200); FX.fade_out(dialog, dur=180)
        FX.shake(entry); FX.pulse(btn); FX.bounce_in(lbl)

    Zincirlenebilir:
        FX.use(btn).dur(140).ease("out_cubic").hover_glow().press_flash()
    """
    # --------- STATİK KISA YOLLAR ---------
    @staticmethod
    def use(w: QWidget) -> "FX":
        """Her widget için tek bir FX nesnesi; yaşam döngüsü widget'a bağlı."""
        fx = getattr(w, "_fx_helper", None)
        if fx is None:
            fx = FX(w)
            setattr(w, "_fx_helper", fx)
        return fx

    # -- Presetler (buton stilleri)
    @staticmethod
    def preset_button(w: QWidget) -> "FX":
        return FX.use(w).hover_glow().press_flash().dur(140).ease("out_cubic")

    @staticmethod
    def preset_button_primary(w: QWidget) -> "FX":
        return FX.use(w).hover_glow(color="#0d6efd", radius=24, strength=0.85).press_flash(0.40).dur(120)

    @staticmethod
    def preset_button_success(w: QWidget) -> "FX":
        return FX.use(w).hover_glow(color="#28a745", radius=24, strength=0.85).press_flash(0.40).dur(120)

    @staticmethod
    def preset_button_warn(w: QWidget) -> "FX":
        return FX.use(w).hover_glow(color="#ffc107", radius=26, strength=0.90).press_flash(0.45).dur(120)

    @staticmethod
    def preset_button_danger(w: QWidget) -> "FX":
        return FX.use(w).hover_glow(color="#ff4d4f", radius=28, strength=0.95).press_flash(0.50).dur(120)

    @staticmethod
    def preset_card(w: QWidget) -> "FX":
        return FX.use(w).hover_glow(radius=28, strength=0.5).fade_on_show(220)

    @staticmethod
    def enhance_list(w: QWidget) -> "FX":
        """Listeler/tablolar için nazik bir hover gölgesi + açılış fade."""
        return FX.use(w).hover_glow(radius=18, strength=0.35).fade_on_show(180)

    # --------- BASİT YARDIMCILAR (efekt bağımsız) ---------
    @staticmethod
    def _curve(typ: QEasingCurve.Type = QEasingCurve.Type.OutCubic) -> QEasingCurve:
        return QEasingCurve(typ)

    @staticmethod
    def fade_in(w: QWidget, dur: int = 200):
        """Var olan efekt çakışmaz: geçici opacity effect uygulayıp sonra geri yükler."""
        if not w:
            return
        prev: Optional[object] = w.graphicsEffect()
        # Eğer zaten OpacityEffect varsa onu kullan; değilse geçici kur.
        if isinstance(prev, QGraphicsOpacityEffect):
            eff = prev
        else:
            eff = QGraphicsOpacityEffect(w)
            w.setGraphicsEffect(eff)

        start_val = 0.0
        end_val = 1.0
        try:
            cur = float(getattr(eff, "opacity")())
            start_val = cur if cur is not None else 0.0
        except Exception:
            pass

        anim = QPropertyAnimation(eff, b"opacity", w)
        anim.setDuration(dur)
        anim.setStartValue(start_val)
        anim.setEndValue(end_val)
        anim.setEasingCurve(FX._curve(QEasingCurve.Type.OutCubic))

        def _restore():
            # Eğer önceden farklı bir efekt vardıysa, animasyon bitince geri yükle
            try:
                if prev and prev is not eff:
                    w.setGraphicsEffect(prev)
            except Exception:
                pass

        anim.finished.connect(_restore)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        w.setVisible(True)

    @staticmethod
    def fade_out(w: QWidget, dur: int = 200, hide_after: bool = True):
        """Var olan efekt çakışmaz: geçici opacity effect uygulayıp sonunda geri yükler/gizler."""
        if not w:
            return
        prev: Optional[object] = w.graphicsEffect()
        if isinstance(prev, QGraphicsOpacityEffect):
            eff = prev
        else:
            eff = QGraphicsOpacityEffect(w)
            eff.setOpacity(1.0)
            w.setGraphicsEffect(eff)

        anim = QPropertyAnimation(eff, b"opacity", w)
        anim.setDuration(dur)
        try:
            start = float(eff.opacity())
        except Exception:
            start = 1.0
        anim.setStartValue(start)
        anim.setEndValue(0.0)
        anim.setEasingCurve(FX._curve(QEasingCurve.Type.OutCubic))

        def _finish():
            try:
                if hide_after:
                    w.setVisible(False)
                # Önceki efekt geri yüklensin (örn. drop shadow)
                if prev and prev is not eff:
                    w.setGraphicsEffect(prev)
            except Exception:
                pass

        anim.finished.connect(_finish)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    @staticmethod
    def slide_in(w: QWidget, dx: int = 0, dy: int = 12, dur: int = 220):
        if not w:
            return
        start_geo = w.geometry()
        off = start_geo.translated(dx, dy)
        w.setGeometry(off)
        FX.fade_in(w, dur=int(dur * 0.85))
        anim = QPropertyAnimation(w, b"geometry", w)
        anim.setDuration(dur)
        anim.setStartValue(off)
        anim.setEndValue(start_geo)
        anim.setEasingCurve(FX._curve(QEasingCurve.Type.OutCubic))
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    @staticmethod
    def shake(w: QWidget, amplitude: int = 6, times: int = 6, dur: int = 300):
        if not w:
            return
        base = w.pos()
        group = QParallelAnimationGroup(w)
        anim = QPropertyAnimation(w, b"pos", w)
        anim.setDuration(dur)
        anim.setEasingCurve(FX._curve(QEasingCurve.Type.OutQuad))
        steps = max(2 * times, 6)
        for i in range(steps + 1):
            t = i / steps
            a = int(amplitude * (1 - t))  # sönümlü
            x = base.x() + (a if i % 2 == 0 else -a)
            anim.setKeyValueAt(t, QPoint(x, base.y()))
        anim.finished.connect(lambda: w.move(base))
        group.addAnimation(anim)
        group.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    @staticmethod
    def pulse(w: QWidget, scale: float = 1.04, dur: int = 140):
        """Kısa vurgulama (geometry ile mikro büyüt-küçült)."""
        if not w:
            return
        g = w.geometry()
        cx = g.center()
        w1 = int(g.width() * scale)
        h1 = int(g.height() * scale)
        g1 = QRect(cx.x() - w1 // 2, cx.y() - h1 // 2, w1, h1)

        up = QPropertyAnimation(w, b"geometry", w)
        up.setDuration(int(dur * 0.6))
        up.setStartValue(g)
        up.setEndValue(g1)
        up.setEasingCurve(FX._curve(QEasingCurve.Type.OutCubic))

        down = QPropertyAnimation(w, b"geometry", w)
        down.setDuration(int(dur * 0.4))
        down.setStartValue(g1)
        down.setEndValue(g)
        down.setEasingCurve(FX._curve(QEasingCurve.Type.InCubic))

        grp = QParallelAnimationGroup(w)  # tek grup içinde ardışık çalıştırmak için küçük hile
        # Ardışık yapmak istersek QSequentialAnimationGroup kullanabilirdik; burada iki ayrı start ile de olurdu.
        def start_down():
            down.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

        up.finished.connect(start_down)
        up.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        grp.addAnimation(up)
        grp.addAnimation(down)

    @staticmethod
    def bounce_in(w: QWidget, dy: int = 12, dur: int = 260):
        """Kısa 'zıplama ile giriş' (özellikle label/buton için hoş)."""
        if not w:
            return
        g0 = w.geometry()
        g1 = g0.translated(0, dy)
        w.setGeometry(g1)
        FX.fade_in(w, dur=int(dur * 0.7))
        anim = QPropertyAnimation(w, b"geometry", w)
        anim.setDuration(dur)
        anim.setStartValue(g1)
        anim.setEndValue(g0)
        anim.setEasingCurve(FX._curve(QEasingCurve.Type.OutBack))
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    # --------- ÖRNEK YAŞAM DÖNGÜSÜ & KURULUM ---------
    def __init__(self, w: QWidget):
        super().__init__(w)  # parent = widget -> GC güvenli
        self.w = w
        self._hover = False
        self._press = False
        self._dur = 140
        self._ease: QEasingCurve.Type = QEasingCurve.Type.OutCubic

        # Glow (gölge) konfig
        self._hover_glow_enabled = False
        self._glow_radius = 22
        self._glow_color = QColor("#40a0ff")
        self._glow_strength = 0.75  # 0..1
        self._base_shadow_opacity = 0.0

        # Press anim
        self._press_flash_enabled = False
        self._press_boost = 0.35  # gölgeyi anlık arttır

        # Açılışta fade
        self._fade_on_show = 0  # ms

        # Eventleri dinle
        w.installEventFilter(self)
        w.destroyed.connect(self._on_destroy)

    # --------- ZİNCİRLENEBİLİR API ---------
    def dur(self, ms: int) -> "FX":
        self._dur = int(_clamp(ms, 1, 5000))
        return self

    def ease(self, name: str | QEasingCurve | QEasingCurve.Type) -> "FX":
        if isinstance(name, QEasingCurve):
            self._ease = name.type()
        elif isinstance(name, QEasingCurve.Type):
            self._ease = name
        else:
            m = {
                "linear": QEasingCurve.Type.Linear,
                "out_cubic": QEasingCurve.Type.OutCubic,
                "out_quint": QEasingCurve.Type.OutQuint,
                "out_back": QEasingCurve.Type.OutBack,
                "in_out_cubic": QEasingCurve.Type.InOutCubic,
            }
            self._ease = m.get(name.lower(), QEasingCurve.Type.OutCubic)
        return self

    def hover_glow(self, radius: int = 22, color: str | QColor | None = None, strength: float = 0.75) -> "FX":
        self._hover_glow_enabled = True
        self._glow_radius = int(_clamp(radius, 0, 256))
        self._glow_color = _as_color(color, fallback="#40a0ff")
        self._glow_strength = _clamp(strength, 0.0, 1.0)
        self._ensure_shadow()
        self._apply_shadow_opacity(self._base_shadow_opacity)
        return self

    def press_flash(self, boost: float = 0.35) -> "FX":
        self._press_flash_enabled = True
        self._press_boost = _clamp(boost, 0.0, 1.0)
        self._ensure_shadow()
        return self

    def fade_on_show(self, dur: int = 200) -> "FX":
        self._fade_on_show = int(_clamp(dur, 0, 10000))
        return self

    # Kısa yol preset zincirleyiciler:
    def preset_button(self) -> "FX":
        return self.hover_glow().press_flash().dur(140).ease("out_cubic")

    def preset_card(self) -> "FX":
        return self.hover_glow(radius=28, strength=0.5).fade_on_show(220)

    # --------- İÇ LOJİK ---------
    def eventFilter(self, obj: QObject, ev: QEvent) -> bool:
        if obj is not self.w:
            return False
        t = ev.type()
        if t in (QEvent.Type.Show, QEvent.Type.ShowToParent) and self._fade_on_show > 0:
            QTimer.singleShot(0, lambda: FX.fade_in(self.w, self._fade_on_show))
        elif t in (QEvent.Type.Enter, QEvent.Type.HoverEnter):
            self._hover = True
            self._animate_hover(True)
        elif t in (QEvent.Type.Leave, QEvent.Type.HoverLeave):
            self._hover = False
            self._animate_hover(False)
        elif t == QEvent.Type.MouseButtonPress:
            self._press = True
            self._animate_press(True)
        elif t == QEvent.Type.MouseButtonRelease:
            self._press = False
            self._animate_press(False)
        return False

    def _ensure_shadow(self):
        eff = self.w.graphicsEffect()
        if isinstance(eff, QGraphicsDropShadowEffect):
            # mevcut gölgeyi güncelle
            eff.setBlurRadius(self._glow_radius)
            eff.setColor(self._glow_color)
            eff.setOffset(0, 0)
            return
        if isinstance(eff, QGraphicsOpacityEffect):
            # OpacityEffect varken gölge kurmayız (tek efekt hakkı var).
            # Hover sırasında sadece alpha animasyonu yapacağız.
            return
        # hiç efekt yoksa gölge kur
        sh = QGraphicsDropShadowEffect(self.w)
        sh.setBlurRadius(self._glow_radius)
        sh.setColor(self._glow_color)
        sh.setOffset(0, 0)
        self.w.setGraphicsEffect(sh)

    def _shadow(self) -> Optional[QGraphicsDropShadowEffect]:
        eff = self.w.graphicsEffect()
        return eff if isinstance(eff, QGraphicsDropShadowEffect) else None

    def _apply_shadow_opacity(self, op: float):
        sh = self._shadow()
        if not sh:
            return
        c = QColor(self._glow_color)
        a = _clamp(int(255 * _clamp(op, 0.0, 1.0)), 0, 255)
        c.setAlpha(int(a))
        sh.setColor(c)
        sh.setBlurRadius(self._glow_radius)

    def _animate_hover(self, entering: bool):
        if not self._hover_glow_enabled:
            return
        # Hem gölge varsa alfa ile oynarız; yoksa (ör. o an OpacityEffect takılıyken)
        # yine de nazik bir animasyon sağlayalım (no-op güvenliği)
        start = 0.0
        end = self._glow_strength if entering else self._base_shadow_opacity
        sh = self._shadow()
        if sh:
            try:
                start = float(sh.color().alphaF())
            except Exception:
                start = 0.0

        anim = QVariantAnimation(self.w)
        anim.setDuration(self._dur)
        anim.setStartValue(float(start))
        anim.setEndValue(float(end))
        anim.setEasingCurve(FX._curve(self._ease))
        anim.valueChanged.connect(lambda v: self._apply_shadow_opacity(float(v)))
        anim.finished.connect(anim.deleteLater)
        anim.start()

    def _animate_press(self, down: bool):
        if not self._press_flash_enabled:
            return
        sh = self._shadow()
        cur = float(sh.color().alphaF()) if sh else 0.0
        target = _clamp(cur + (self._press_boost if down else -self._press_boost), 0.0, 1.0)

        anim = QVariantAnimation(self.w)
        anim.setDuration(int(self._dur * 0.7))
        anim.setStartValue(float(cur))
        anim.setEndValue(float(target))
        anim.setEasingCurve(FX._curve(QEasingCurve.Type.OutCubic))
        anim.valueChanged.connect(lambda v: self._apply_shadow_opacity(float(v)))
        anim.finished.connect(anim.deleteLater)
        anim.start()

    def _on_destroy(self, *_):
        # Widget yok olurken event filter'ı kaldır (animasyon kalıntısı kalmasın)
        try:
            self.w.removeEventFilter(self)
        except Exception:
            pass
