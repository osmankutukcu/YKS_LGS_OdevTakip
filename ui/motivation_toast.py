# -*- coding: utf-8 -*-
# ui/motivation_toast.py
from __future__ import annotations

import sys, os, math, random
from typing import Optional, List, Tuple, Dict, Any

from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect, QRectF, QPointF, QUrl
)
from PyQt6.QtGui import (
    QFont, QColor, QPalette, QPainter, QPainterPath
)
from PyQt6.QtWidgets import (
    QWidget, QLabel, QGraphicsOpacityEffect, QVBoxLayout
)

# (varsayılan ayar deposu – lazy loaded)
appset = None

def _ensure_appset():
    global appset
    if appset is None:
        try:
            from utils import settings
            appset = settings
        except Exception:
            pass
    return appset

# --------- Ses ----------
try:
    from PyQt6.QtMultimedia import QSoundEffect
except Exception:
    QSoundEffect = None

_IS_WIN = sys.platform.startswith("win")
_IS_MAC = sys.platform == "darwin"


# =========================================================
#  Windows görünürlük düzeltmesi için overlay host
# =========================================================
class _WinOverlay(QWidget):
    """
    Sadece Windows’ta parent.window() üstüne şeffaf bir host.
    macOS / Linux: kullanılmıyor.
    """
    def __init__(self, parent: QWidget):
        win = parent.window() if parent is not None else parent
        super().__init__(win)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        if win is not None:
            self.resize(win.size())
            self.move(0, 0)

    def sync_to_parent(self):
        p = self.parent()
        if isinstance(p, QWidget):
            self.resize(p.size())
            self.move(0, 0)


def _host_for(parent: QWidget) -> QWidget:
    """Windows'ta overlay host döner, diğerlerinde parent'ı aynen kullanır."""
    if _IS_WIN and isinstance(parent, QWidget):
        return _WinOverlay(parent)
    return parent


# =========================================================
#  A) TOAST (zoom + fade) – pozisyon destekli
# =========================================================
class MotivationToast(QWidget):
    """
    Basit başarı tostu.
    position:
        center, top, bottom, top_left, top_right, bottom_left, bottom_right
    """
    def __init__(
        self,
        message: str = "Süpersin! 🎉",
        duration: int = 2400,
        color: str = "#22c55e",
        font_size: int = 26,
        radius: int = 16,
        position: str = "center",
        parent: Optional[QWidget] = None,
    ):
        self._host = _host_for(parent)
        super().__init__(self._host)

        # macOS’ta görünmeyen toast sorununa karşı: her OS’te üstte dursun
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._duration = int(duration)
        self._radius = int(radius)
        self._position = (position or "center").lower()
        self._target_geo: Optional[QRect] = None

        # Arka plan ve Stil
        self.bg_color = QColor(color)
        
        # QPalette yerine stylesheet kullanmak daha güvenli (global temalar widget'i bozmasın)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {color};
                border-radius: {self._radius}px;
            }}
            QLabel {{
                color: #ffffff !important;
                font-weight: 700;
                padding: 8px 14px;
                background-color: transparent !important;
                border: none;
            }}
        """)

        # Metin
        self.label = QLabel(message)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # label style is now handled in parent stylesheet to ensure specificity
        
        f = QFont("Poppins, Segoe UI, Arial")
        f.setPointSize(int(font_size))
        self.label.setFont(f)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 16, 22, 16)
        lay.addWidget(self.label)

        # Şeffaflık
        self._fx = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._fx)

        self._fade_in = QPropertyAnimation(self._fx, b"opacity", self)
        self._fade_in.setDuration(200)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._fade_out = QPropertyAnimation(self._fx, b"opacity", self)
        self._fade_out.setDuration(220)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade_out.finished.connect(self._close_self)

        # DEBUG: Font size tracing
        try:
            from utils import audit_manager
            audit_manager.log("DEBUG", "TOAST", f"Toast init. Font: {font_size}")
        except: pass

    # ---------- konum hesaplama ----------
    def _compute_target_geo(self) -> QRect:
        host_geo = (
            self._host.rect()
            if isinstance(self._host, QWidget)
            else (self.parent().geometry() if self.parent() else self.geometry())
        )

        if _IS_WIN and isinstance(self._host, _WinOverlay):
            self._host.sync_to_parent()
            host_geo = self._host.rect()

        w, h = self.width(), self.height()
        margin = 32

        pos = self._position
        if pos == "top":
            x = host_geo.center().x() - w // 2
            y = host_geo.top() + margin
        elif pos == "bottom":
            x = host_geo.center().x() - w // 2
            y = host_geo.bottom() - h - margin
        elif pos == "top_left":
            x = host_geo.left() + margin
            y = host_geo.top() + margin
        elif pos == "top_right":
            x = host_geo.right() - w - margin
            y = host_geo.top() + margin
        elif pos == "bottom_left":
            x = host_geo.left() + margin
            y = host_geo.bottom() - h - margin
        elif pos == "bottom_right":
            x = host_geo.right() - w - margin
            y = host_geo.bottom() - h - margin
        else:   # center
            x = host_geo.center().x() - w // 2
            y = host_geo.center().y() - h // 2

        return QRect(x, y, w, h)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self.bg_color)
        p.drawRoundedRect(self.rect(), self._radius, self._radius)

    def showEvent(self, _):
        self.adjustSize()
        self._target_geo = self._compute_target_geo()
        self.setGeometry(self._target_geo)

        # Önce hostu göster (Windows), sonra kendini
        if _IS_WIN and isinstance(self._host, _WinOverlay):
            self._host.show()
            self._host.raise_()
        self.show()
        self.raise_()

        self._fade_in.start()
        self._zoom_in()
        QTimer.singleShot(self._duration, self.fade_out)

    def _zoom_in(self):
        if self._target_geo is None:
            return
        geo = self._target_geo
        start = QRect(0, 0, int(geo.width() * 0.9), int(geo.height() * 0.9))
        start.moveCenter(geo.center())
        self._zoom = QPropertyAnimation(self, b"geometry", self)
        self._zoom.setDuration(180)
        self._zoom.setStartValue(start)
        self._zoom.setEndValue(geo)
        self._zoom.setEasingCurve(QEasingCurve.Type.OutBack)
        self._zoom.start()

    def fade_out(self):
        self._fade_out.start()

    def _close_self(self):
        try:
            self.close()
        finally:
            if _IS_WIN and isinstance(self._host, _WinOverlay):
                t = QTimer(self)
                t.setSingleShot(True)
                t.timeout.connect(lambda: self._host.deleteLater())
                t.start(10)


# =========================================================
#  B) KONFETİ YAĞMURU
# =========================================================
_PALETTE = ["#f43f5e", "#f59e0b", "#22c55e", "#0ea5e9", "#6366f1", "#a855f7", "#ec4899"]


def _qcolor(c):
    q = QColor(c)
    q.setAlpha(230)
    return q


class _Confetti(QWidget):
    def __init__(self, parent: QWidget, duration_ms: int = 2400, density: int = 100):
        self._host = _host_for(parent)
        super().__init__(self._host)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self._life = int(duration_ms)
        self._t = 0
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._parts: List[dict] = []

        # Windows’ta çok yoğunluk takılma yapmasın
        if _IS_WIN:
            density = max(30, min(int(density), 160))
        self._spawn(int(density))

        # Geometri
        if _IS_WIN and isinstance(self._host, _WinOverlay):
            self._host.sync_to_parent()
            self.resize(self._host.size())
            self.move(0, 0)
        else:
            self.resize(parent.size())
            self.move(0, 0)

        self._timer.start()

        if _IS_WIN and isinstance(self._host, _WinOverlay):
            self._host.show()
            self._host.raise_()
        self.show()
        self.raise_()

    def _spawn(self, n: int):
        if _IS_WIN and isinstance(self._host, _WinOverlay):
            w, h = self._host.width(), self._host.height()
        else:
            w, h = self.parent().width(), self.parent().height()
        for _ in range(n):
            x = random.uniform(0, w)
            y = random.uniform(-0.15 * h, 0)
            vy = random.uniform(1.7, 3.2)
            vx = random.uniform(-0.8, 0.8)
            size = random.randint(6, 12)
            rot = random.uniform(0, 360)
            col = _qcolor(random.choice(_PALETTE))
            self._parts.append(
                dict(x=x, y=y, vx=vx, vy=vy, s=size, r=rot, c=col, t=0)
            )

    def _tick(self):
        dt = 16
        self._t += dt
        h = self.height()
        alive = []
        for p in self._parts:
            p["t"] += dt
            p["x"] += p["vx"] + math.sin(p["t"] * 0.01) * 0.3
            p["y"] += p["vy"]
            p["r"] += 3.0
            if p["y"] < h + 20:
                alive.append(p)
        self._parts = alive
        if self._t >= self._life and not self._parts:
            self._timer.stop()
            if _IS_WIN and isinstance(self._host, _WinOverlay):
                try:
                    self._host.hide()
                    self._host.deleteLater()
                except Exception:
                    pass
            self.deleteLater()
        self.update()

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for p in self._parts:
            painter.save()
            painter.translate(QPointF(p["x"], p["y"]))
            painter.rotate(p["r"])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(p["c"])
            s = float(p["s"])
            rect = QRectF(-s / 2.0, -s / 2.0, s, s * 0.66)
            painter.drawRoundedRect(rect, 2.0, 2.0)
            painter.restore()


def show_confetti(parent: QWidget, duration_ms: int = 2400, density: int = 100):
    w = _Confetti(parent, duration_ms=duration_ms, density=density)
    return w


# =========================================================
#  C) YILDIZ PATLAMASI
# =========================================================
class _StarBurst(QWidget):
    def __init__(
        self,
        parent: QWidget,
        center: Optional[Tuple[int, int]] = None,
        count: int = 22,
        duration_ms: int = 900,
    ):
        self._host = _host_for(parent)
        super().__init__(self._host)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )

        # Geometri
        if _IS_WIN and isinstance(self._host, _WinOverlay):
            self._host.sync_to_parent()
            self.resize(self._host.size())
            self.move(0, 0)
            cx = center[0] if center else self._host.width() // 2
            cy = center[1] if center else self._host.height() // 2
        else:
            self.resize(parent.size())
            self.move(0, 0)
            cx = center[0] if center else self.width() // 2
            cy = center[1] if center else self.height() // 2

        self._parts = []
        for i in range(count):
            ang = 2 * math.pi * i / max(1, count)
            spd = random.uniform(2.2, 4.0)
            col = _qcolor(random.choice(_PALETTE))
            self._parts.append(
                dict(
                    x=cx,
                    y=cy,
                    vx=math.cos(ang) * spd,
                    vy=math.sin(ang) * spd,
                    life=duration_ms,
                    age=0,
                    c=col,
                    s=random.randint(6, 10),
                )
            )
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        if _IS_WIN and isinstance(self._host, _WinOverlay):
            self._host.show()
            self._host.raise_()
        self.show()
        self.raise_()

    def _tick(self):
        dt = 16
        alive = []
        for p in self._parts:
            p["age"] += dt
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["vy"] += 0.05
            if p["age"] < p["life"]:
                alive.append(p)
        self._parts = alive
        if not self._parts:
            self._timer.stop()
            if _IS_WIN and isinstance(self._host, _WinOverlay):
                try:
                    self._host.hide()
                    self._host.deleteLater()
                except Exception:
                    pass
            self.deleteLater()
        self.update()

    def _star_path(self, r: float) -> QPainterPath:
        path = QPainterPath()
        for i in range(10):
            a = math.pi / 2 + i * math.pi / 5
            rad = r if i % 2 == 0 else r * 0.45
            x = math.cos(a) * rad
            y = -math.sin(a) * rad
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        path.closeSubpath()
        return path

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for s in self._parts:
            p.save()
            p.translate(QPointF(s["x"], s["y"]))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(s["c"])
            p.drawPath(self._star_path(s["s"]))
            p.restore()


def star_burst(
    parent: QWidget,
    center: Optional[Tuple[int, int]] = None,
    count: int = 24,
    duration_ms: int = 900,
):
    w = _StarBurst(parent, center=center, count=count, duration_ms=duration_ms)
    return w


# =========================================================
#  D) SES (GC güvenli)
# =========================================================
_ACTIVE_SOUNDS: List[QSoundEffect] = []


def play_success(path: Optional[str] = None, volume: float = 0.25):
    if QSoundEffect is None or not path or not os.path.exists(path):
        return None
    try:
        eff = QSoundEffect()
        eff.setVolume(max(0.0, min(1.0, float(volume))))
        eff.setSource(QUrl.fromLocalFile(path))
        eff.play()
        _ACTIVE_SOUNDS.append(eff)
        t = QTimer()
        t.setSingleShot(True)

        def _cleanup():
            try:
                if eff in _ACTIVE_SOUNDS:
                    _ACTIVE_SOUNDS.remove(eff)
            except Exception:
                pass
            t.deleteLater()

        t.timeout.connect(_cleanup)
        t.start(5000)
        return eff
    except Exception:
        return None


# =========================================================
#  E) YÜKSEK SEVİYE TOAST API
# =========================================================
def quick_toast(
    parent: QWidget,
    msg: str = "Durumlar güncellendi.",
    kind_color: str = "#16a34a",
    duration_ms: int = 1800,
    font_size: int = 16,
    position: str = "center",
):
    # Buradaki font_size parametresi hâlâ kullanılabiliyor ama
    # genelde celebrate_saved / _run_style üzerinden ayardan geliyor.
    t = MotivationToast(
        message=msg,
        color=kind_color,
        duration=duration_ms,
        font_size=font_size,
        parent=parent,
        position=position,
    )
    t.show()
    return t


# =========================================================
#  F) **AYAR YÖNETİMİ**  (100% için – mevcut yapı)
# =========================================================
CANON = {
    "message": "motive_message",
    "color": "motive_color",
    "duration": "motive_duration",
    "font": "motive_font_size",  # YENİ anahtar
    "sound_path": "motive_sound_path",
    "sound_volume": "motive_sound_volume",
    "confetti": "motive_confetti_density",
    "auto_when_100": "motive_auto_when_full",
    "style": "motive_style",
}

# Eski/TR karşılıklar
ALIASES: Dict[str, list[str]] = {
    "message": ["motive_mesaj"],
    "color": ["motive_renk"],
    "duration": ["motive_sure"],
    "font": ["motive_font"],  # ESKİ anahtar
    "sound_path": ["motive_ses_yolu"],
    "sound_volume": ["motive_ses_seviyesi"],
    "confetti": ["motive_confetti"],
    "auto_when_100": ["motive_auto_100", "motive_auto_on_full"],
    "style": ["motive_stil"],
}

DEFAULTS = dict(
    message="Harika! Tüm ödevleri tamamladın! 🎉",
    color="#16a34a",
    duration=2600,
    font=24,
    sound_path=None,
    sound_volume=0.25,
    confetti=120,
    auto_when_100=True,
    style="both",  # varsayılan: toast + confetti
)

# Bellek içi fallback (utils.settings yoksa)
_RAM_STORE: Dict[str, Any] = {CANON[k]: v for k, v in DEFAULTS.items()}


def _get(key: str, default=None):
    ap = _ensure_appset()
    if ap:
        return ap.ayar_get(key, default)
    return _RAM_STORE.get(key, default)


def _set(key: str, value: Any):
    ap = _ensure_appset()
    if ap:
        return ap.ayar_set(key, value)
    _RAM_STORE[key] = value


def _pick(keys: list[str], default: Any, cast=None):
    for k in keys:
        v = _get(k, None)
        if v not in (None, ""):
            if cast:
                try:
                    v = cast(v)
                except Exception:
                    v = default
            return v
    return default


def load_settings() -> Dict[str, Any]:
    """TR/EN tüm anahtarları destekleyerek oku (100% seviyesi)."""
    out: Dict[str, Any] = {}

    for field, canon in CANON.items():
        # FONT için: hem eski, hem yeni anahtarı destekle
        if field == "font":
            cands = [canon] + ALIASES.get(field, [])  # ["motive_font_size", "motive_font"]
        else:
            cands = [canon] + ALIASES.get(field, [])

        default = DEFAULTS[field]
        cast = None

        if field in ("duration", "font", "confetti"):
            cast = int
        elif field == "sound_volume":
            cast = float
        elif field == "auto_when_100":
            def _c(v):
                s = str(v).strip().lower()
                return s in ("1", "true", "evet", "yes", "on")
            cast = _c

        out[field] = _pick(cands, default, cast)

    # Ses yolu yoksa/yanlışsa devre dışı
    if out["sound_path"] and not os.path.exists(out["sound_path"]):
        out["sound_path"] = None

    return out
def load_settings(prefix: str = "") -> dict:
    """DB veya bellekten güncel ayarları çeker (prefix opsiyonel, loglama için)."""
    out: Dict[str, Any] = {}
    for field, canon in CANON.items():
        # 1) Önce canonical key (örn: motive_font_size)
        # 2) Sonra eski/alias anahtarlar (örn: motive_font)
        cands = [canon] + ALIASES.get(field, [])

        default = DEFAULTS[field]
        cast = None

        if field in ("duration", "font", "confetti"):
            cast = int
        elif field == "sound_volume":
            cast = float
        elif field == "auto_when_100":

            def _c(v):
                s = str(v).strip().lower()
                return s in ("1", "true", "evet", "yes", "on")

            cast = _c

        out[field] = _pick(cands, default, cast)

    # Ses yolu yoksa/yanlışsa devre dışı
    if out["sound_path"] and not os.path.exists(out["sound_path"]):
        out["sound_path"] = None

    return out


def save_settings(prefs: Dict[str, Any]) -> None:
    """Sadece canonical anahtarlarla kaydet (100%)."""
    for field, canon in CANON.items():
        _set(canon, prefs.get(field, DEFAULTS[field]))


def preview_settings(parent: QWidget):
    """Motivasyon ayarları diyalogundaki önizleme butonu için."""
    s = load_settings()
    _run_style(
        parent=parent,
        style=s.get("style", "both"),
        message=s["message"],
        color=s["color"],
        duration_ms=s["duration"],
        font_size=s["font"],
        confetti_density=s["confetti"],
        sound_path=s["sound_path"],
        sound_volume=s["sound_volume"],
        position="center",
    )


# =========================================================
#  G) %50 / %75 AYARLARI (EKSTRA – mevcut yapıyı bozmaz)
# =========================================================
def _bool_cast(v, default=False):
    try:
        if isinstance(v, bool):
            return v
        s = str(v).strip().lower()
        if s in ("1", "true", "evet", "yes", "on"):
            return True
        if s in ("0", "false", "hayir", "hayır", "no", "off"):
            return False
    except Exception:
        pass
    return default


def _level_key(level: int, field: str) -> str:
    return f"motive_{level}_{field}"


def load_level_settings(level: int) -> Dict[str, Any]:
    """
    level: 50 veya 75.
    Eğer ilgili ayar yoksa 100% (base) ayarlarına düşer.
    """
    base = load_settings()
    out: Dict[str, Any] = {}

    # auto
    auto = _get(_level_key(level, "auto"), None)
    out["auto"] = _bool_cast(
        auto, default=(True if level in (50, 75) else base["auto_when_100"])
    )

    def get_level(field: str, base_key: str):
        val = _get(_level_key(level, field), None)
        if val in (None, ""):
            return base[base_key]
        if field in ("duration", "font", "confetti"):
            try:
                return int(val)
            except Exception:
                return base[base_key]
        if field == "sound_volume":
            try:
                return float(val)
            except Exception:
                return base[base_key]
        return val

    out["message"] = get_level("message", "message")
    out["color"] = get_level("color", "color")
    out["duration"] = get_level("duration", "duration")
    out["font"] = get_level("font", "font")
    out["style"] = get_level("style", "style")
    out["confetti"] = get_level("confetti", "confetti")
    out["sound_path"] = get_level("sound_path", "sound_path")
    out["sound_volume"] = get_level("sound_volume", "sound_volume")

    # Ses yolu yoksa devre dışı
    if out["sound_path"] and not os.path.exists(out["sound_path"]):
        out["sound_path"] = None

    return out


# =========================================================
#  H) STİL MOTORU – 15+ farklı stil
# =========================================================
STYLE_POSITIONS = {
    # sade toast stilleri
    "zoom_fade": "center",
    "toast": "center",
    "toast_center": "center",
    "toast_top": "top",
    "toast_bottom": "bottom",
    "toast_top_right": "top_right",
    "toast_bottom_right": "bottom_right",
    "toast_top_left": "top_left",
    "toast_bottom_left": "bottom_left",
    # aşağıdakiler kombinasyon stilleri için pozisyon ipucu
    "exam_focus": "top",
    "last_sprint": "bottom",
    "epic": "center",
    "soft": "center",
    "minimal": "bottom_right",
}


def _run_style(
    parent: QWidget,
    style: str,
    message: str,
    color: str,
    duration_ms: int,
    font_size: int,
    confetti_density: int,
    sound_path: Optional[str],
    sound_volume: float,
    position: str = "center",
):
    """
    Tüm animasyon stilleri buradan yönetilir.
    Combobox’a koyabileceğin stil isimleri (en az 15):

        zoom_fade
        toast
        toast_top
        toast_bottom
        toast_top_right
        toast_bottom_right
        toast_top_left
        toast_bottom_left
        confetti
        confetti_soft
        confetti_crazy
        stars
        both           (toast + confetti)
        both_soft      (toast + hafif konfeti)
        exam_focus     (üstten bar + hafif konfeti)
        last_sprint    (%75 civarı için güçlü konfeti + yıldız)
        epic           (her şey + yüksek yoğunluk)
        minimal        (küçük sade toast, köşede)
    """
    s = (style or "both").strip().lower()
    pos = STYLE_POSITIONS.get(s, position)

    # ---- sadece toast ağırlıklı stiller ----
    if s in (
        "zoom_fade",
        "toast",
        "toast_center",
        "toast_top",
        "toast_bottom",
        "toast_top_right",
        "toast_bottom_right",
        "toast_top_left",
        "toast_bottom_left",
        "minimal",
    ):
        if s == "minimal":
            quick_toast(
                parent,
                msg=message,
                kind_color=color,
                duration_ms=max(1200, duration_ms),
                font_size=max(12, font_size - 4),
                position="bottom_right",
            )
        else:
            quick_toast(
                parent,
                msg=message,
                kind_color=color,
                duration_ms=duration_ms,
                font_size=font_size,
                position=pos,
            )

    # ---- sadece konfeti / yıldız / balon stilleri ----
    elif s in ("confetti", "confetti_only"):
        show_confetti(parent, duration_ms=duration_ms, density=confetti_density)
    elif s == "confetti_soft":
        show_confetti(parent, duration_ms=duration_ms, density=max(30, confetti_density // 2))
    elif s == "confetti_crazy":
        show_confetti(
            parent,
            duration_ms=duration_ms + 600,
            density=min(confetti_density * 2, 220),
        )
        star_burst(parent, duration_ms=min(duration_ms + 600, 1400))
    elif s == "stars":
        star_burst(parent, duration_ms=min(duration_ms, 1100))
    elif s == "balloons":
        _Balloons(parent, duration_ms=duration_ms + 800, count=min(20, max(5, confetti_density // 5)))
        quick_toast(
            parent,
            msg=message,
            kind_color=color,
            duration_ms=duration_ms,
            font_size=font_size,
            position=pos,
        )

    # ---- karma stiller ----
    elif s in ("both", "all", "rainbow"):
        quick_toast(
            parent,
            msg=message,
            kind_color=color if s != "rainbow" else "#9333ea", # Purple defaults for rainbow
            duration_ms=duration_ms,
            font_size=font_size,
            position=pos,
        )
        show_confetti(parent, duration_ms=duration_ms, density=confetti_density)
        star_burst(parent, duration_ms=min(duration_ms, 1200))
        if s == "rainbow":
            _Balloons(parent, duration_ms=duration_ms + 1000, count=15)
    
    elif s == "both_soft":
        quick_toast(
            parent,
            msg=message,
            kind_color=color,
            duration_ms=duration_ms,
            font_size=font_size,
            position=pos,
        )
        show_confetti(
            parent, duration_ms=duration_ms, density=max(40, confetti_density // 2)
        )
    elif s == "exam_focus":
        quick_toast(
            parent,
            msg=message,
            kind_color=color,
            duration_ms=duration_ms,
            font_size=font_size,
            position="top",
        )
        show_confetti(
            parent, duration_ms=duration_ms, density=max(30, confetti_density // 2)
        )
    elif s == "last_sprint":
        quick_toast(
            parent,
            msg=message,
            kind_color=color,
            duration_ms=duration_ms,
            font_size=font_size,
            position="bottom",
        )
        show_confetti(
            parent, duration_ms=duration_ms, density=min(confetti_density * 2, 200)
        )
        star_burst(parent, duration_ms=min(duration_ms, 1200))
    elif s == "epic":
        quick_toast(
            parent,
            msg=message,
            kind_color=color,
            duration_ms=max(2600, duration_ms),
            font_size=font_size,
            position="center",
        )
        show_confetti(
            parent,
            duration_ms=max(2600, duration_ms),
            density=min(confetti_density * 2, 220),
        )
        star_burst(parent, duration_ms=1300)
        _Balloons(parent, duration_ms=max(2600, duration_ms)+500, count=20)
    elif s == "fireworks":
        _Fireworks(parent, duration_ms=duration_ms + 1000)
        quick_toast(parent, msg=message, kind_color=color, duration_ms=duration_ms, font_size=font_size, position=pos)
    elif s == "snow":
        _Snow(parent, duration_ms=duration_ms + 1000)
        quick_toast(parent, msg=message, kind_color=color, duration_ms=duration_ms, font_size=font_size, position="center")
    else:
        # Tanınmayan stil -> sade toast
        quick_toast(
            parent,
            msg=message,
            kind_color=color,
            duration_ms=duration_ms,
            font_size=font_size,
            position=pos,
        )

    # Ses (dosya varsa) – tüm stillerde ortak
    if sound_path:
        try:
            play_success(sound_path, sound_volume)
        except Exception:
            pass


# =========================================================
#  I) Kullanıcı ayarına göre kutlama – 100% seviyesi
# =========================================================
def celebrate_saved(parent: QWidget):
    """
    Kullanıcının 'Motivasyon Ayarları' formunda yaptığı ayarlara göre
    animasyonları, sesi ve temayı çalıştırır.
    """
    try:
        prefs = load_settings()
    except Exception:
        prefs = {}

    msg = prefs.get("message", DEFAULTS["message"])
    renk = prefs.get("color", DEFAULTS["color"])
    sure = int(prefs.get("duration", DEFAULTS["duration"]))
    font = int(prefs.get("font", DEFAULTS["font"]))
    dens = int(prefs.get("confetti", DEFAULTS["confetti"]))
    stil = str(prefs.get("style", DEFAULTS["style"])).strip().lower()
    ses_yol = prefs.get("sound_path", DEFAULTS["sound_path"])
    ses_vol = float(prefs.get("sound_volume", DEFAULTS["sound_volume"]))

    _run_style(
        parent=parent,
        style=stil,
        message=msg,
        color=renk,
        duration_ms=sure,
        font_size=font,
        confetti_density=dens,
        sound_path=ses_yol,
        sound_volume=ses_vol,
        position="center",
    )


# =========================================================
#  J) %50 / %75 / %100 ilerleme için profesyonel motivasyon
# =========================================================
def motivate_for_progress(parent: QWidget, progress_percent: float):
    """
    Ödev / konu tamamlama yüzdesine göre motivasyon:

        0–49   : sessiz
        50–74  : %50 seviyesi (motive_50_*)
        75–99  : %75 seviyesi (motive_75_*)
        100    : burası için celebrate_saved kullanılıyor.

    • 0–1 aralığında (0.7 gibi) değer gelse bile otomatik olarak %'ye çevirir.
    """

    # --- 0–1 / 0–100 normalize et ---
    try:
        p = float(progress_percent)
    except Exception:
        return

    if 0.0 <= p <= 1.0:
        p = p * 100.0

    if p < 0.0:
        p = 0.0
    if p > 100.0:
        p = 100.0

    if 75.0 <= p < 100.0:
        # %75 bandı – son düzlüğe girdin
        lvl = load_level_settings(75)
        if not lvl.get("auto", True):
            return

        msg = lvl.get("message", "Son düzlüğe girdin, bırakma! 🚀")
        _run_style(
            parent,
            style=lvl.get("style", "last_sprint"),
            message=msg,
            color=lvl.get("color", "#0ea5e9"),
            duration_ms=int(lvl.get("duration", 2200)),
            font_size=int(lvl.get("font", 22)),
            confetti_density=int(lvl.get("confetti", 140)),
            sound_path=lvl.get("sound_path", None),
            sound_volume=float(lvl.get("sound_volume", 0.25)),
            position="bottom",
        )
        return

    if 50.0 <= p < 75.0:
        # %50 bandı – yolun yarısı
        lvl = load_level_settings(50)
        if not lvl.get("auto", True):
            return

        msg = lvl.get("message", "Güzel başlangıç, yolun yarısındasın! 💪")
        _run_style(
            parent,
            style=lvl.get("style", "exam_focus"),
            message=msg,
            color=lvl.get("color", "#f59e0b"),
            duration_ms=int(lvl.get("duration", 2000)),
            font_size=int(lvl.get("font", 20)),
            confetti_density=int(lvl.get("confetti", 80)),
            sound_path=lvl.get("sound_path", None),
            sound_volume=float(lvl.get("sound_volume", 0.25)),
            position="top",
        )
        return

    # 0–49 veya 100: burada sessiz kalıyoruz, 100 için ayrı celebrate_saved çağırıyorsun.
    return


# =========================================================
#  K) GERİYE DÖNÜK UYUMLU celebrate(...)
# =========================================================
# =========================================================
#  L) BALON EFEKTİ
# =========================================================
class _Balloons(QWidget):
    def __init__(self, parent: QWidget, duration_ms: int = 3000, count: int = 15):
        self._host = _host_for(parent)
        super().__init__(self._host)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint
        )
        if _IS_WIN and isinstance(self._host, _WinOverlay):
            self._host.sync_to_parent()
            self.resize(self._host.size())
            self.move(0, 0)
        else:
            self.resize(parent.size())
            self.move(0, 0)
            
        self._parts = []
        w, h = self.width(), self.height()
        for _ in range(count):
            x = random.uniform(0, w)
            y = h + random.uniform(0, 200) # Start below
            vy = random.uniform(1.5, 4.0) # Speed up
            size = random.randint(30, 60)
            col = _qcolor(random.choice(_PALETTE))
            self._parts.append(
                dict(x=x, y=y, vy=vy, s=size, c=col, wob=random.uniform(0, 100))
            )
            
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        
        self._life = duration_ms
        self._elapsed = 0
        
        if _IS_WIN and isinstance(self._host, _WinOverlay):
            self._host.show(); self._host.raise_()
        self.show(); self.raise_()

    def _tick(self):
        dt = 16
        self._elapsed += dt
        alive = []
        for p in self._parts:
            p["y"] -= p["vy"]
            p["wob"] += 0.05
            p["x"] += math.sin(p["wob"]) * 0.5
            if p["y"] + p["s"] > -50:
                alive.append(p)
        self._parts = alive
        
        if self._elapsed >= self._life or not self._parts:
            self._timer.stop()
            if _IS_WIN and isinstance(self._host, _WinOverlay):
                try: self._host.hide(); self._host.deleteLater()
                except: pass
            self.deleteLater()
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        
        for part in self._parts:
            p.setBrush(part["c"])
            # Oval balloon
            p.drawEllipse(int(part["x"]), int(part["y"]), int(part["s"]), int(part["s"]*1.2))
            # String
            p.setPen(QColor(200, 200, 200, 150))
            p.drawLine(int(part["x"]+part["s"]/2), int(part["y"]+part["s"]*1.1), int(part["x"]+part["s"]/2), int(part["y"]+part["s"]*1.1)+15)
            p.setPen(Qt.PenStyle.NoPen)

# =========================================================
#  M) KIVILCIM / HAVAİ FİŞEK (Fireworks)
# =========================================================
class _Fireworks(QWidget):
    def __init__(self, parent: QWidget, duration_ms: int = 4000, count: int = 5):
        self._host = _host_for(parent)
        super().__init__(self._host)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        
        if _IS_WIN and isinstance(self._host, _WinOverlay):
            self._host.sync_to_parent()
            self.resize(self._host.size())
        else:
            self.resize(parent.size())
            
        self._rockets = []
        self._sparks = []
        self.w, self.h = self.width(), self.height()
        
        # Initial rockets
        for _ in range(count):
            self._launch_rocket()
            
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        
        self._life = duration_ms
        self._elapsed = 0
        
        if _IS_WIN and isinstance(self._host, _WinOverlay):
            self._host.show(); self._host.raise_()
        self.show(); self.raise_()

    def _launch_rocket(self):
        x = random.uniform(self.w * 0.2, self.w * 0.8)
        self._rockets.append({
            "x": x, "y": self.h, 
            "vx": random.uniform(-1, 1), "vy": random.uniform(-12, -8),
            "color": _qcolor(random.choice(_PALETTE))
        })

    def _explode(self, x, y, color):
        for _ in range(30):
            ang = random.uniform(0, 6.28)
            spd = random.uniform(1, 5)
            self._sparks.append({
                "x": x, "y": y,
                "vx": math.cos(ang)*spd, "vy": math.sin(ang)*spd,
                "color": color, "life": 1.0, "decay": random.uniform(0.02, 0.04)
            })

    def _tick(self):
        self._elapsed += 16
        if self._elapsed > self._life:
            self._timer.stop()
            self.deleteLater()
            return
            
        # Rockets
        alive_rockets = []
        for r in self._rockets:
            r["x"] += r["vx"]
            r["y"] += r["vy"]
            r["vy"] += 0.2 # gravity
            if r["vy"] >= -2: # Apex reached
                self._explode(r["x"], r["y"], r["color"])
            else:
                alive_rockets.append(r)
        self._rockets = alive_rockets
        
        # Chance to launch more
        if self._elapsed < self._life - 1000 and random.random() < 0.05:
            self._launch_rocket()

        # Sparks
        alive_sparks = []
        for s in self._sparks:
            s["x"] += s["vx"]
            s["y"] += s["vy"]
            s["vy"] += 0.1 # gravity
            s["life"] -= s["decay"]
            if s["life"] > 0:
                alive_sparks.append(s)
        self._sparks = alive_sparks
        
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Rockets
        for r in self._rockets:
            p.setBrush(r["color"])
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(int(r["x"]), int(r["y"]), 6, 6)
            
        # Sparks
        for s in self._sparks:
            c = QColor(s["color"])
            c.setAlphaF(max(0, min(1, s["life"])))
            p.setBrush(c)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(int(s["x"]), int(s["y"]), 4, 4)

# =========================================================
#  N) KAR YAĞIŞI (Snow)
# =========================================================
class _Snow(QWidget):
    def __init__(self, parent: QWidget, duration_ms: int = 4000):
        self._host = _host_for(parent)
        super().__init__(self._host)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        
        if _IS_WIN and isinstance(self._host, _WinOverlay):
            self._host.sync_to_parent()
            self.resize(self._host.size())
        else:
            self.resize(parent.size())
            
        self._flakes = []
        w, h = self.width(), self.height()
        for _ in range(100):
            self._respawn(initial=True)
            
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        
        self._life = duration_ms
        self._elapsed = 0
        
        if _IS_WIN and isinstance(self._host, _WinOverlay):
            self._host.show(); self._host.raise_()
        self.show(); self.raise_()

    def _respawn(self, initial=False):
        x = random.uniform(0, self.width())
        y = random.uniform(-self.height(), 0) if initial else -10
        s = random.randint(3, 8)
        self._flakes.append({"x": x, "y": y, "s": s, "vx": random.uniform(-1, 1), "vy": random.uniform(2, 5)})

    def _tick(self):
        self._elapsed += 16
        if self._elapsed > self._life:
            self._timer.stop()
            self.deleteLater()
            return
            
        for f in self._flakes:
            f["y"] += f["vy"]
            f["x"] += f["vx"] + math.sin(f["y"]*0.05)
            if f["y"] > self.height():
                f["y"] = -10
                f["x"] = random.uniform(0, self.width())
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(255, 255, 255, 200))
        p.setPen(Qt.PenStyle.NoPen)
        for f in self._flakes:
            p.drawEllipse(int(f["x"]), int(f["y"]), int(f["s"]), int(f["s"]))

def celebrate(
    parent: QWidget,
    message: str = "Harika! Tüm ödevleri tamamladın! 🎉",
    color: str = "#16a34a",
    duration_ms: int = 2600,
    font_size: int = 24,
    confetti_density: int = 120,
    starburst_on: bool = True,
    sound_path: Optional[str] = None,
    sound_volume: float = 0.25,
    position: str = "center",
):
    """
    Eski kodlarda celebrate(...) çağrısı varsa,
    artık ayarlardan okuyan celebrate_saved'i kullanır.
    Parametreler sadece imzayı korumak için duruyor.
    """
    return celebrate_saved(parent)
