# -*- coding: utf-8 -*-
from __future__ import annotations
from ui.responsive import apply_responsive
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QListWidget, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox, QListWidgetItem, QApplication, QSizePolicy,
    QStyledItemDelegate, QStyleOptionViewItem, QStyle
)
from PyQt6.QtGui import (
    QShortcut, QKeySequence, QColor, QBrush, QFontMetrics, QLinearGradient, QPixmap, QPen,
    QGuiApplication, QPainter, QPainterPath, QFont
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QSize, QPoint, QRectF, QPointF, QEvent
from datetime import datetime
import db

from contextlib import contextmanager
from PyQt6.QtCore import Qt
AL = Qt.AlignmentFlag  # kısaltma

# dosya: ui/odev_kontrol.py  (senin örneğinde bu sınıfın olduğu dosya)
# … diğer importların altına ekle:
try:
    from ui.whatsapp_dialog import WhatsAppGonderDialog
except Exception:
    from whatsapp_dialog import WhatsAppGonderDialog  # proje kökündeyse
from utils import settings as appset
from utils import whatsapp
from utils import audit_manager  # NEW: Audit Logging




# --------------------------------------------------------------------
# PyQt5 ↔ PyQt6 uyumluluk (UserRole)
try:
    USERROLE = Qt.ItemDataRole.UserRole          # PyQt6
except Exception:  # pragma: no cover
    try:
        USERROLE = Qt.UserRole                   # PyQt5
    except Exception:
        USERROLE = 0x0100                        # son çare
# --------------------------------------------------------------------


# ---- Basit FlowLayout (PyQt6 güvenli sürüm) ----
from PyQt6.QtWidgets import QLayout
from PyQt6.QtCore import QPoint, QRect, QSize, Qt

# print_helper entegrasyonu
try:
    from print_helper import ListPrintDialog, PrintProfile, _ModelAdapter
except Exception:
    # dosya yolu farklıysa kendi yolunu yaz
    from ui.print_helper import ListPrintDialog, PrintProfile, _ModelAdapter



# PyQt6/PyQt5 uyumu: 0 flags değeri
try:
    ORIENTATIONS_ZERO = Qt.Orientations(0)   # PyQt5'te var
except Exception:
    ORIENTATIONS_ZERO = Qt.Orientation(0)    # PyQt6'da doğru tip

from ui.motivation_toast import celebrate_saved# motivasyon

class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, hspacing=8, vspacing=6):
        super().__init__(parent)
        self._items = []
        self._hspacing = hspacing
        self._vspacing = vspacing
        self.setContentsMargins(margin, margin, margin, margin)

    # Zorunlu üyeler
    def addItem(self, item): self._items.append(item)
    def count(self): return len(self._items)
    def itemAt(self, i): return self._items[i] if 0 <= i < len(self._items) else None
    def takeAt(self, i): return self._items.pop(i) if 0 <= i < len(self._items) else None

    # QFlags<Qt::Orientation> beklenir → 0 flags döndür
    def expandingDirections(self):
        return ORIENTATIONS_ZERO

    def hasHeightForWidth(self): return True
    def heightForWidth(self, w): return self._do_layout(QRect(0, 0, w, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self): return self.minimumSize()
    def minimumSize(self):
        s = QSize()
        for it in self._items:
            s = s.expandedTo(it.sizeHint())
        l, t, r, b = self.getContentsMargins()
        s += QSize(l + r, t + b)
        return s

    def _do_layout(self, rect, test_only):
        l, t, r, b = self.getContentsMargins()
        eff = QRect(rect.x()+l, rect.y()+t, rect.width()-l-r, rect.height()-t-b)

        x = eff.x()
        y = eff.y()
        line_h = 0

        for it in self._items:
            sz = it.sizeHint()
            next_x = x + sz.width() + self._hspacing
            if next_x - self._hspacing > eff.right() and line_h > 0:
                x = eff.x()
                y += line_h + self._vspacing
                next_x = x + sz.width() + self._hspacing
                line_h = 0
            if not test_only:
                it.setGeometry(QRect(QPoint(x, y), sz))
            x = next_x
            line_h = max(line_h, sz.height())

        return y + line_h - rect.y() + b



# -- KUME LIST ITEM (veriliş + kalem satırları ekli, bar içinde %) ------------
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QProgressBar, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont
import datetime as _dt
import re

# dosyanın tepesine bir yere:
from utils import settings as appset
import os

#s --yapılmayanları aktar ama kümeden silme
from ui.motivation_toast import quick_toast, celebrate, celebrate_saved, motivate_for_progress

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush
import json
#f --




#s
# --- Mini üst istatistik barı (çizerek) ---
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QPainter, QColor, QFont
from PyQt6.QtWidgets import QWidget

class _MiniStats(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pct = 0; self._k = 0; self._t = 0; self._a = 0
        self.setFixedHeight(18)

    def sizeHint(self):  # küçük ve kompakt kalsın
        return QSize(280, 18)

    def setStats(self, pct: int, kume_say: int, toplam_odev: int, akt: int):
        self._pct = max(0, min(100, int(pct or 0)))
        self._k   = int(kume_say or 0)
        self._t   = int(toplam_odev or 0)
        self._a   = int(akt or 0)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing, True)
        r = self.rect(); x = 0; h = r.height()

        # "Tamamlanma:"
        f = p.font(); f.setBold(True); p.setFont(f)
        p.setPen(QColor("#1f2937"))
        txt = "Tamamlanma:"
        p.drawText(x, 0, h, Qt.AlignmentFlag.AlignVCenter, txt)
        x += p.fontMetrics().horizontalAdvance(txt) + 6

        # bar
        bar_w = 120; bar_h = 10; y = (h - bar_h) // 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#eef2f7"))
        p.drawRoundedRect(x, y, bar_w, bar_h, 5, 5)
        fill_w = int(bar_w * self._pct / 100)
        p.setBrush(QColor("#22c55e"))
        p.drawRoundedRect(x, y, fill_w, bar_h, 5, 5)
        x += bar_w + 6

        # % değer
        f = p.font(); f.setBold(True); p.setFont(f)
        p.setPen(QColor("#111827"))
        pct_txt = f"%{self._pct}"
        p.drawText(x, 0, h, Qt.AlignmentFlag.AlignVCenter, pct_txt)
        x += p.fontMetrics().horizontalAdvance(pct_txt) + 10

        # küçük istatistik çiftleri
        def pair(label, val, color=None):
            nonlocal x
            # etiket
            f = p.font(); f.setBold(False); p.setFont(f)
            p.setPen(QColor("#6b7280"))
            lab = f"{label}: "
            p.drawText(x, 0, h, Qt.AlignmentFlag.AlignVCenter, lab)
            x += p.fontMetrics().horizontalAdvance(lab)
            # değer
            f = p.font(); f.setBold(True); p.setFont(f)
            p.setPen(QColor(color) if color else QColor("#111827"))
            sval = str(val)
            p.drawText(x, 0, h, Qt.AlignmentFlag.AlignVCenter, sval)
            x += p.fontMetrics().horizontalAdvance(sval) + 10

        pair("Küme", self._k)
        pair("Ödev", self._t)
        pair("Aktarılan", self._a, "#7c3aed")  # mor vurgulu

        p.end()
#f


#s--öcev kartlarında rozet tıklama için
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import QLabel
class _ClickLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # İstemezsen kaldır: görsel feedback için el işareti zaten set ediyorsun
        # self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            e.accept()          # 👈 olay yukarı çıkmasın
            return
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            e.accept()          # 👈 olay yukarı çıkmasın
            try:
                self.clicked.emit()
            finally:
                return
        super().mouseReleaseEvent(e)
#f--



def _load_motive_settings():
    """Aynı ayarın TR/EN anahtar adlarını birleştirip güvenle döndürür."""
    def _pick(keys, default=None, cast=None):
        val = None
        for k in keys:
            v = appset.ayar_get(k, None)
            if v not in (None, ""):
                val = v
                break
        if val in (None, ""):
            val = default
        if cast is not None:
            try:
                val = cast(val)
            except Exception:
                val = default
        return val

    msg   = _pick(["motive_message", "motive_mesaj"], "Harika! Tüm ödevleri tamamladın! 🎉", str)
    color = _pick(["motive_color", "motive_renk"], "#16a34a", str)
    dur   = _pick(["motive_duration", "motive_sure"], 2600, int)
    fnt   = _pick(["motive_font_size", "motive_font"], 24, int)
    s_path= _pick(["motive_sound_path", "motive_ses_yolu"], "assets/success.wav", str)
    s_vol = _pick(["motive_sound_volume", "motive_ses_seviyesi"], 0.25, float)
    dens  = _pick(["motive_confetti_density", "motive_confetti"], 120, int)

    # Ses dosyası yoksa sessize al
    if not s_path or not os.path.exists(s_path):
        s_path = None

    return {
        "message": msg,
        "color": color,
        "duration": dur,
        "font": fnt,
        "sound_path": s_path,
        "sound_volume": s_vol,
        "confetti_density": dens,
    }

class KumeListItem(QWidget):
    """
    Modernize Edilmiş Akıllı Küme Kartı
    - Sol: Durum çubuğu (renkli şerit)
    - Orta: Başlık, Tarih Aralığı (ikonlu), Özet İstatistikler
    - Sağ: Büyük Yüzde ve İlerleme Barı
    """

    def __init__(self, num_label: str, tarih_label: str, adet_label: str,
                 percent: int, moved: int = 0, last_moved: str = "", parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("KumeCard")

        self._moved = int(moved or 0)
        ver_txt, bit_txt = self._split_dates(tarih_label)
        days_left, due_cls = self._days_left(bit_txt)
        
        # --- Toplam Sayıyı Bul (Akıllı Analiz İçin) ---
        total_items = 1
        try:
            # "2 kalem" -> 2
            match = re.search(r'(\d+)', str(adet_label))
            if match:
                total_items = int(match.group(1))
        except:
            total_items = 1
        
        total_items = max(1, total_items)
        
        # Yaklaşık "Yapılan" sayısı (Yüzdeden geri hesapla)
        done_count = int(round((total_items * percent) / 100.0))
        
        # İşlem Gören (Yapılan + Aktarılan)
        processed_count = done_count + self._moved
        remaining_count = total_items - processed_count
        
        # Yüzdeler (Bar Gösterimi İçin)
        p_done = percent
        p_moved = int((self._moved / total_items) * 100.0)
        # Toplam %100'ü geçmesin (yuvarlama hatası vs)
        if p_done + p_moved > 100:
            p_moved = 100 - p_done
            
        # --- Türkçe Tarih Yardımcısı (Local) ---
        def _to_tr_date(d_str):
            if not d_str or d_str == "-": return "-"
            try:
                dt_obj = _dt.datetime.strptime(d_str, "%Y-%m-%d")
                months = {
                    1: "Oca", 2: "Şub", 3: "Mar", 4: "Nis", 5: "May", 6: "Haz",
                    7: "Tem", 8: "Ağu", 9: "Eyl", 10: "Eki", 11: "Kas", 12: "Ara"
                }
                return f"{dt_obj.day} {months.get(dt_obj.month, '')}"
            except:
                return d_str

        # --- Profesyonel ve Akıllı Durum Analizi ---
        status_text = "Devam Ediyor"
        status_color = "#3b82f6" # Mavi
        
        is_cleared = (remaining_count <= 0)
        
        if percent >= 100:
            status_text = "✅ Tamamlandı"
            status_color = "#10b981" # Yeşil
        elif is_cleared:
            # Liste tamamen erimiş (kısmen yapıldı, kısmen aktarıldı)
            if self._moved > 0:
                status_text = f"✅ Liste Kapandı ({self._moved} Aktarım)"
            else:
                status_text = "✅ Liste Kapandı"
            status_color = "#10b981" # Yine Yeşil/Başarılı tonu
        elif due_cls == "danger":
             if days_left is not None and days_left < 0:
                 status_text = "⛔️ Gecikmiş / Tamamlanmadı"
                 status_color = "#ef4444"
             else:
                 status_text = f"🚨 Kritik: Son {days_left} Gün"
                 status_color = "#ef4444"
        elif due_cls == "warn":
             status_text = f"⚠️ Son {days_left} Gün"
             status_color = "#f59e0b"
        else:
             if percent == 0 and self._moved == 0:
                 status_text = "⏳ Henüz Başlanmadı"
                 status_color = "#64748b"
             else:
                 status_text = "🏃 Devam Ediyor"

        # --- Layout ---
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Sol Renkli Şerit
        self.strip = QWidget()
        self.strip.setFixedWidth(6)
        self.strip.setStyleSheet(f"background-color: {status_color}; border-top-left-radius: 12px; border-bottom-left-radius: 12px;")
        main_layout.addWidget(self.strip)

        # 2. İçerik Alanı
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(12, 10, 12, 10)
        content_layout.setSpacing(4)
        
        # 2a. Üst Satır
        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        
        lbl_title = QLabel(num_label)
        lbl_title.setStyleSheet("font-size: 15px; font-weight: 800; color: #1e293b;")
        top_row.addWidget(lbl_title)
        
        # Aktarım Rozeti
        self.badgeXfer = _ClickLabel()
        if self._moved > 0:
            self.badgeXfer.setText(f"↩ {self._moved} Aktarılan")
            self.badgeXfer.setStyleSheet("""
                background-color: #f3e8ff; color: #7c3aed; 
                padding: 2px 8px; border-radius: 6px; font-weight: 600; font-size: 11px;
            """)
            self.badgeXfer.setCursor(Qt.CursorShape.PointingHandCursor)
            top_row.addWidget(self.badgeXfer)
        else:
            self.badgeXfer.setVisible(False)
            
        top_row.addStretch()
        
        # Durum Metni
        lbl_status = QLabel(status_text)
        lbl_status.setStyleSheet(f"color: {status_color}; font-weight: 700; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;")
        top_row.addWidget(lbl_status)
        
        content_layout.addLayout(top_row)
        
        # 2b. Orta: Tarihler & Detay
        d_ver = _to_tr_date(ver_txt)
        d_bit = _to_tr_date(bit_txt)

        lbl_dates = QLabel(f"📅  {d_ver}  ➝  {d_bit}")
        lbl_dates.setStyleSheet("color: #64748b; font-size: 12px; font-weight: 500;")
        content_layout.addWidget(lbl_dates)
        
        lbl_count = QLabel(f"📝  {adet_label}")
        lbl_count.setStyleSheet("color: #475569; font-size: 12px;")
        content_layout.addWidget(lbl_count)
        
        content_layout.addStretch()
        main_layout.addWidget(content_widget, 1)

        # 3. Sağ Taraf (Smart Gradient Bar)
        stats_widget = QWidget()
        stats_widget.setFixedWidth(90)
        stats_layout = QVBoxLayout(stats_widget)
        stats_layout.setContentsMargins(0, 10, 12, 10)
        stats_layout.setSpacing(4)
        stats_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Yüzde Metni (Tamamlanma Oranı)
        # Eğer liste kapandıysa ve %100 değilse, bunu belirtelim mi?
        # Kullanıcı "bunu yüzde 50 gösteriyor" dedi, yani bundan rahatsız.
        # Eğer liste kapandıysa (remaining=0), %100 Done olmasa bile %100 Processed.
        # Biz yine de "başarı" oranını gösterelim ama rengi yeşil yapalım.
        
        disp_percent = percent
        pct_color = "#334155"
        if is_cleared and percent < 100:
            # Özel Gösterim: %50 (Kapalı)
            # Ya da karışıklık olmasın diye %50 kalsın ama bar her şeyi anlatsın.
            pass

        self.lbl_percent = QLabel(f"%{disp_percent}")
        self.lbl_percent.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_percent.setStyleSheet(f"font-size: 20px; font-weight: 900; color: {pct_color};")
        stats_layout.addWidget(self.lbl_percent)
        
        # --- Multi-color Gradient Bar ---
        # 0..p_done: Yeşil
        # p_done..(p_done+p_moved): Mor
        # geri kalan: Gri
        
        stop_1 = float(p_done) / 100.0
        stop_2 = float(p_done + p_moved) / 100.0
        
        # Gradient string
        # stop:0 green, stop:0.5 green, stop:0.501 purple, stop:1.0 purple ...
        grad_stops = []
        
        # Yeşil Kısım (Yapılan)
        if p_done > 0:
            grad_stops.append(f"stop:0 #10b981")
            grad_stops.append(f"stop:{stop_1:.3f} #10b981")
            
        # Mor Kısım (Aktarılan)
        if p_moved > 0:
            # Geçiş keskin olsun diye azıcık kaydırıyoruz
            grad_stops.append(f"stop:{stop_1 + 0.001:.3f} #a78bfa")
            grad_stops.append(f"stop:{stop_2:.3f} #a78bfa")
            
        # Varsayılan arka plan zaten gri (#e2e8f0), chunk sadece doluluk
        # QProgressBar chunk mekanizması tek parça çalışır. 
        # Bu yüzden background gradient'i QProgressBar'ın kendisine değil, chunk'a veremeyiz (chunk tek parça boyanır).
        # ÇÖZÜM: QProgressBar'ın background'ına vereceğiz, value'yu 100 yapacağız? 
        # Hayır, value 100 yaparsak "dolu" görünür.
        # Biz en iyisi "chunk" ın background'ına gradient verelim. Chunk width 0..100.
        # Ama chunk sadece %VAL kadar çizilir. 
        # Biz value'yu (p_done + p_moved) yapalım! Böylece bar "işlem görmüş" kadar dolar.
        # Ve o dolan kısmın içini yeşil/mor boyayalım.
        
        total_fill = p_done + p_moved
        
        # Gradienti normalize etmemiz lazım (0..total_fill arası 1.0 kabul edilir chunk içinde)
        # Örnek: Total fill 60. Done 30, Moved 30.
        # Chunk 0..0.5 Green, 0.5..1.0 Purple.
        
        if total_fill > 0:
            if p_moved > 0 and p_done > 0:
                ratio_done = p_done / total_fill
                s1 = min(0.998, max(0.001, ratio_done))
                s2 = min(0.999, s1 + 0.001)
                chunk_grad = f"""
                    qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #10b981, stop:{s1:.3f} #10b981,
                    stop:{s2:.3f} #a78bfa, stop:1 #a78bfa)
                """
            elif p_moved > 0:
                chunk_grad = "#a78bfa"
            else:
                chunk_grad = "#10b981"
        else:
            chunk_grad = "#10b981"

        self.mini_bar = QProgressBar()
        self.mini_bar.setFixedHeight(8) # Biraz kalınlaştıralım detay görünsün
        self.mini_bar.setTextVisible(False)
        self.mini_bar.setRange(0, 100)
        self.mini_bar.setValue(total_fill) # İşlem gören kadar doldur
        
        self.mini_bar.setStyleSheet(f"""
            QProgressBar {{ background-color: #e2e8f0; border-radius: 4px; border: none; }}
            QProgressBar::chunk {{ background: {chunk_grad}; border-radius: 4px; }}
        """)
        stats_layout.addWidget(self.mini_bar)
        
        main_layout.addWidget(stats_widget)

        # -- Genel Stil --
        self.setMinimumHeight(85)
        self.setStyleSheet("""
            #KumeCard {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
            }
            #KumeCard[hover="true"] {
                background-color: #ffffff;
                border: 1px solid #94a3b8; 
            }
        """)
        
        self.setToolTip(f"Veriliş: {ver_txt}\nBitiş: {bit_txt}\nDurum: {status_text}\nYapılan: %{p_done}, Aktarılan: %{p_moved}")


    # ---------------- public ----------------
    def setPercent(self, p: int):
        val = max(0, min(100, int(p)))
        self.lbl_percent.setText(f"%{val}")
        self.mini_bar.setValue(val)

        # Dinamik Renk Güncelleme
        color = "#3b82f6"
        if val >= 100: color = "#10b981"
        elif val < 40: color = "#f59e0b"
        
        self.mini_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #e2e8f0;
                border-radius: 3px;
                border: none;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 3px;
            }}
        """)

    # ---------------- events ----------------
    def enterEvent(self, e):
        self.setProperty("hover", True)
        self.style().unpolish(self); self.style().polish(self)
        
        # Hafif gölge efekti (QGraphicsEffect pahalı olabilir, border değişimi yeterli)
        # Veya kod içinde shadow ekleyebiliriz:
        if not self.graphicsEffect():
            sh = QGraphicsDropShadowEffect(self)
            sh.setBlurRadius(15)
            sh.setOffset(0, 4)
            sh.setColor(QColor(0,0,0, 40)) # Daha belirgin gölge
            self.setGraphicsEffect(sh)

        super().enterEvent(e)

    def leaveEvent(self, e):
        self.setProperty("hover", False)
        self.style().unpolish(self); self.style().polish(self)
        
        # Gölgeyi yumuşat veya kaldır
        if self.graphicsEffect():
             self.graphicsEffect().setColor(QColor(0,0,0, 0)) # Gizle

        super().leaveEvent(e)

    def sizeHint(self) -> QSize:
        return QSize(320, 95)
        
    # ---------------- helpers ----------------
    def _split_dates(self, txt: str):
        if not txt: return "-", "-"
        parts = [p.strip() for p in re.split(r"→|->|—>|-{1,2}>", txt) if p is not None]
        if len(parts) >= 2: return (parts[0] or "-"), (parts[1] or "-")
        return txt, "-"

    def _days_left(self, bitis_txt: str):
        try:
            if not bitis_txt or bitis_txt in ("-", ""): return None, "none"
            d = _dt.datetime.strptime(bitis_txt, "%Y-%m-%d").date()
            diff = (d - _dt.date.today()).days
            if diff < 0: return diff, "danger" # Gecikmiş
            if diff <= 3:   return diff, "danger"
            elif diff <= 7: return diff, "warn"
            else:           return diff, "ok"
        except Exception:
            return None, "none"



# --- tıklanabilir QLabel için küçük filtre (QLabel'da clicked yoksa kullanacağız)
from PyQt6.QtCore import QObject, QEvent, Qt
class _ClickFilter(QObject):
    def __init__(self, on_click):
        super().__init__()
        self._on_click = on_click

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            try:
                self._on_click()
            except Exception:
                pass
            return True
        return False



class _YapildiColumnDelegate(QStyledItemDelegate):
    """0. kolon (Yapıldı) için platformdan bağımsız kusursuz vektör checkbox çizici."""
    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        widget = opt.widget
        style = widget.style() if widget else QApplication.style()
        style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, opt, painter, widget)

        check_state = index.data(Qt.ItemDataRole.CheckStateRole)
        if check_state is not None:
            cw, ch = 18, 18
            cx = option.rect.center().x()
            cy = option.rect.center().y()
            rf = QRectF(cx - cw / 2.0, cy - ch / 2.0, cw, ch)

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            is_checked = bool(check_state in (Qt.CheckState.Checked, 2, Qt.CheckState.Checked.value))
            is_enabled = bool(opt.state & QStyle.StateFlag.State_Enabled)

            if is_checked:
                painter.setBrush(QColor("#16a34a" if is_enabled else "#94a3b8"))
                painter.setPen(QPen(QColor("#15803d" if is_enabled else "#64748b"), 1.2))
                painter.drawRoundedRect(rf, 3.5, 3.5)

                pen = QPen(QColor("#ffffff"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)

                path = QPainterPath()
                path.moveTo(QPointF(rf.x() + cw * 0.22, rf.y() + ch * 0.52))
                path.lineTo(QPointF(rf.x() + cw * 0.42, rf.y() + ch * 0.74))
                path.lineTo(QPointF(rf.x() + cw * 0.78, rf.y() + ch * 0.28))
                painter.drawPath(path)
            else:
                is_hover = bool(opt.state & QStyle.StateFlag.State_MouseOver)
                painter.setBrush(QColor("#ffffff"))
                painter.setPen(QPen(QColor("#2563eb" if is_hover else "#94a3b8"), 1.5))
                painter.drawRoundedRect(rf, 3.5, 3.5)

            painter.restore()

    def editorEvent(self, event, model, option, index):
        if not (index.flags() & Qt.ItemFlag.ItemIsEnabled):
            return False
        if not (index.flags() & Qt.ItemFlag.ItemIsUserCheckable):
            return False

        if event.type() in (QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick):
            if event.button() == Qt.MouseButton.LeftButton:
                curr = index.data(Qt.ItemDataRole.CheckStateRole)
                if curr is not None:
                    is_currently_checked = bool(curr in (Qt.CheckState.Checked, 2, Qt.CheckState.Checked.value))
                    new_state = Qt.CheckState.Unchecked if is_currently_checked else Qt.CheckState.Checked
                    model.setData(index, new_state, Qt.ItemDataRole.CheckStateRole)
                    return True
        elif event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                return True
        return super().editorEvent(event, model, option, index)


class OdevKontrolDialog(QDialog):
    """
    - Öğrenciye ait ödev kümelerini listeler.
    - Seçilen kümenin ödevlerini tabloda gösterir; ilk sütunda 'Yapıldı' checkbox.
    - Kaydet: işaretli olanları 'yapildi', diğerlerini 'devam' yapar.
    - Yapılmayanları Ödeve Aktar: işaretsizleri 'iptal' işaretler ve ebeveyne aktarılacak listeyi döner.
    """
    sonuc_sinyal = pyqtSignal(list, list)  # (tamamlanan_listesi, kalan_listesi)

    def __init__(self, ogrenci_id: int, ebeveyn=None):
        super().__init__(ebeveyn)
        self.setWindowTitle("Ödev Kontrol")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.resize(1100, 700)
        self.ogr_id = ogrenci_id
        self._all_tasks_mode = False
        self._build_ui()
        self._yukle_kumeler()
        try:
            apply_responsive(self)
        except Exception:
            pass

        # bayrak aktarılan tıklama
        self._only_moved = False
        self._only_moved = False
        self.lstKume.itemClicked.connect(lambda _item: self._kume_ac(None, False))
        self._apply_modern_visuals()

    def _apply_modern_visuals(self):
        self.setStyleSheet("""
            QDialog, QWidget {
                font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
                font-size: 13px;
                background-color: #f8fafc;
                color: #1e293b;
            }
            
            QListWidget {
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                background: #ffffff;
                padding: 4px;
            }
            QListWidget::item {
                padding: 6px 10px;
                border-radius: 6px;
                margin-bottom: 2px;
            }
            QListWidget::item:hover {
                background-color: #f1f5f9;
            }
            QListWidget::item:selected {
                background-color: #e0f2fe;
                color: #0369a1;
                font-weight: 600;
            }

            /* Buttons */
            QPushButton {
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
                background: #ffffff;
                border: 1px solid #cbd5e1;
                color: #334155;
            }
            QPushButton:hover {
                background: #f1f5f9;
                border-color: #94a3b8;
                color: #0f172a;
            }
            QPushButton:pressed {
                background: #e2e8f0;
            }
            
            QPushButton#btnAction, QPushButton#btnKaydet {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #059669, stop:1 #047857);
                color: white;
                border: 1px solid #047857;
            }
            QPushButton#btnAction:hover, QPushButton#btnKaydet:hover {
                background: #047857;
            }
            
            QPushButton#btnPrimary, QPushButton#btnAktar {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2563eb, stop:1 #1d4ed8);
                color: white;
                border: 1px solid #1d4ed8;
            }
            QPushButton#btnPrimary:hover, QPushButton#btnAktar:hover {
                background: #1d4ed8;
            }

            QPushButton#btnAktarSilmeden {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0284c7, stop:1 #0369a1);
                color: white;
                border: 1px solid #0369a1;
            }
            QPushButton#btnAktarSilmeden:hover {
                background: #0369a1;
            }

            QPushButton#btnWhatsApp {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #10b981, stop:1 #059669);
                color: white;
                border: 1px solid #047857;
            }
            QPushButton#btnWhatsApp:hover {
                background: #047857;
            }
            
            QPushButton#btnDanger, QPushButton#btnSatirSil, QPushButton#btnKumeSil {
                background-color: #fff1f2;
                color: #b91c1c;
                border: 1px solid #fecdd3;
            }
            QPushButton#btnDanger:hover, QPushButton#btnSatirSil:hover, QPushButton#btnKumeSil:hover {
                background-color: #ffe4e6;
                border-color: #fda4af;
            }
            
            QPushButton#btnSuccess, QPushButton#btnHepsiTamam {
                background-color: #ecfdf5;
                color: #047857;
                border: 1px solid #a7f3d0;
            }
            QPushButton#btnSuccess:hover, QPushButton#btnHepsiTamam:hover {
                background-color: #d1fae5;
                border-color: #6ee7b7;
            }

            QPushButton#btnStandard, QPushButton#btnHepsiGeri {
                background-color: #ffffff;
                color: #374151;
                border: 1px solid #cbd5e1;
            }
            QPushButton#btnStandard:hover, QPushButton#btnHepsiGeri:hover {
                background-color: #f1f5f9;
            }

            QPushButton#btnKapat {
                background-color: #f1f5f9;
                color: #475569;
                border: 1px solid #cbd5e1;
            }
            QPushButton#btnKapat:hover {
                background-color: #e2e8f0;
                color: #0f172a;
            }
            
            QPushButton#btnInfo {
                background-color: #eff6ff;
                color: #1d4ed8;
                border: 1px solid #bfdbfe;
            }
            QPushButton#btnInfo:hover {
                background-color: #dbeafe;
            }

            QComboBox, QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 5px 8px;
                background: white;
            }
            QComboBox:focus, QLineEdit:focus {
                border: 2px solid #3b82f6;
            }
        """)

    # ---------------- UI ----------------
    def _build_ui(self):
        from PyQt6.QtWidgets import (
            QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QPushButton, QTableWidget,
            QTableWidgetItem, QAbstractItemView, QSizePolicy, QSplitter, QWidget,
            QToolButton, QMenu, QLineEdit, QComboBox, QFrame, QPushButton as QBtn
        )
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QAction, QShortcut, QKeySequence  # QAction burada!

        root = QVBoxLayout(self)

        # --------- ÜST: BUTON BAR (FlowLayout => otomatik sarma & Modern Kart) ---------
        btnBarContainer = QFrame()
        btnBarContainer.setObjectName("btnBarContainer")
        btnBarContainer.setStyleSheet("""
            QFrame#btnBarContainer {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
            }
        """)
        btnBarLayout = QVBoxLayout(btnBarContainer)
        btnBarLayout.setContentsMargins(4, 4, 4, 4)

        btnBar = QWidget()
        flow = FlowLayout(btnBar, margin=4, hspacing=8, vspacing=6)

        def _mk(text, obj="btnStandard"):
            b = QPushButton(text)
            b.setMinimumHeight(32)
            b.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            b.setObjectName(obj)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            return b

        self.btnHepsiTamam = _mk("✅ Hepsi Tamam (Ctrl+Shift+A)", "btnHepsiTamam")
        self.btnHepsiGeri = _mk("↩️ Geri Taşı (Ctrl+Shift+Z)", "btnHepsiGeri")
        self.btnKaydet = _mk("💾 Kaydet", "btnKaydet")
        self.btnAktar = _mk("📤 Aktar (Temizle) (F7)", "btnAktar")
        self.btnAktarSilmeden = _mk("📥 Aktar (Sakla) (F8)", "btnAktarSilmeden")
        self.btnSatirSil = _mk("❌ Seçilen Sil", "btnSatirSil")
        self.btnKumeSil = _mk("🗑️ Küme Sil", "btnKumeSil")
        self.btnWpGonder = _mk("💬 WhatsApp", "btnWhatsApp")
        self.btnKapat = _mk("🚪 Kapat", "btnKapat")

        # FlowLayout’a ekleme sırası:
        for b in [self.btnHepsiTamam, self.btnHepsiGeri, self.btnKaydet,
                  self.btnAktar, self.btnAktarSilmeden,
                  self.btnSatirSil, self.btnKumeSil,
                  self.btnWpGonder, self.btnKapat]:
            flow.addWidget(b)

        # --- “Liste” açılır menüsü (PDF + Tüm Ödevler) ---
        self.btnListe = QToolButton()
        self.btnListe.setText("📄 Liste & PDF ▾")
        self.btnListe.setObjectName("btnInfo")
        self.btnListe.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btnListe.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.btnListe.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnListe.setMinimumHeight(32)

        m = QMenu(self.btnListe)
        m.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                background-color: transparent;
                padding: 6px 24px 6px 12px;
                border-radius: 4px;
                color: #334155;
                font-family: 'Segoe UI', sans-serif;
            }
            QMenu::item:selected {
                background-color: #f1f5f9;
                color: #1e293b;
            }
            QMenu::separator {
                height: 1px;
                background-color: #e2e8f0;
                margin: 4px 6px; 
            }
        """)
        m.addAction("PDF’ye Yazdır", getattr(self, "_print_current_table_pdf", lambda: None))
        m.addSeparator()
        m.addAction("Tüm Ödevleri Göster", getattr(self, "_tum_odevleri_yukle", lambda: None))
        m.addAction("Yalnız Seçili Kümeyi Göster", getattr(self, "_kume_ac", lambda: None))
        m.setMinimumWidth(220)
        self.btnListe.setMenu(m)

        self.btnListe.setStyleSheet("""
            QToolButton {
                background: #ffffff; 
                color: #334155; 
                border: 1px solid #cbd5e1;
                border-radius: 6px; 
                padding: 6px 12px; 
                font-weight: 600;
                font-family: 'Segoe UI', sans-serif;
            }
            QToolButton:hover { 
                background: #f1f5f9; 
                color: #1e293b;
                border-color: #94a3b8;
            }
            QToolButton:pressed { 
                background: #e2e8f0; 
                border-color: #64748b;
            }
            QToolButton::menu-indicator { 
                image: none; 
                width: 0px; 
            }
        """)

        flow.addWidget(self.btnListe)
        btnBarLayout.addWidget(btnBar)
        root.addWidget(btnBarContainer)

        # --------- EXECUTIVE KPI HEADER CARD ---------
        self.kpiCard = QFrame()
        self.kpiCard.setObjectName("kpiCard")
        self.kpiCard.setStyleSheet("""
            QFrame#kpiCard {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
            }
        """)
        kpiLayout = QHBoxLayout(self.kpiCard)
        kpiLayout.setContentsMargins(10, 6, 10, 6)
        kpiLayout.setSpacing(12)

        self.lblOgr = QLabel("👤 Öğrenci: ...")
        self.lblOgr.setStyleSheet("""
            QLabel {
                font-weight: 700;
                font-size: 13px;
                color: #1e3a8a;
                background: #eff6ff;
                border: 1px solid #bfdbfe;
                border-radius: 14px;
                padding: 4px 12px;
            }
        """)
        kpiLayout.addWidget(self.lblOgr)

        self.lblYuzde = QLabel("%0")
        self.lblYuzde.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.lblYuzde.setTextFormat(Qt.TextFormat.RichText)
        kpiLayout.addWidget(self.lblYuzde, 1)

        root.addWidget(self.kpiCard)

        # --------- İKİ SÜTUN: SOL (liste) ↔ SAĞ (tablo) ---------
        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        root.addWidget(split, 1)

        # SOL
        leftW = QWidget()
        left = QVBoxLayout(leftW)
        left.setContentsMargins(0, 0, 0, 0)
        self.lstKume = QListWidget()
        try:
            self.lstKume.setSelectionMode(self.lstKume.SelectionMode.ExtendedSelection)
        except Exception:
            pass
        self.lstKume.setMinimumWidth(420)
        self.lstKume.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left.addWidget(self.lstKume)
        split.addWidget(leftW)

        # Sağ tık menüsü için:
        self.lstKume.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.lstKume.customContextMenuRequested.connect(self._on_kume_context_menu)

        # SAĞ
        rightW = QWidget()
        right = QVBoxLayout(rightW)
        right.setContentsMargins(0, 0, 0, 0)

        # --- Filtre çubuğu (Ders / Durum / Arama) ---
        flt_frame = QFrame()
        flt_frame.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
            QComboBox, QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 8px;
                background: #f8fafc;
                font-size: 12px;
                color: #1e293b;
            }
            QComboBox:focus, QLineEdit:focus {
                border: 1px solid #3b82f6;
                background: #ffffff;
            }
            QPushButton {
                background: #f1f5f9;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 10px;
                font-weight: 600;
                color: #475569;
            }
            QPushButton:hover {
                background: #e2e8f0;
                color: #1e293b;
            }
        """)
        flt = QHBoxLayout(flt_frame)
        flt.setContentsMargins(6, 4, 6, 4)
        flt.setSpacing(8)
        self.cboFltDers = QComboBox()
        self.cboFltDers.addItem("Ders: Hepsi", "")
        self.cboFltDurum = QComboBox()
        self.cboFltDurum.addItems(["Durum: Hepsi", "Yapıldı", "Devam"])
        self.txtFltAra = QLineEdit()
        self.txtFltAra.setPlaceholderText("🔍 Kitap, konu veya not ara…")
        btnFltClear = QBtn("🧹 Temizle")
        btnFltClear.setToolTip("Filtreleri sıfırla")
        flt.addWidget(self.cboFltDers)
        flt.addWidget(self.cboFltDurum)
        flt.addWidget(self.txtFltAra)
        flt.addWidget(btnFltClear)

        self.lblFltCount = QLabel("")
        self.lblFltCount.setStyleSheet("color: #64748b; font-size: 12px; font-weight: 600; padding-left: 6px;")
        flt.addWidget(self.lblFltCount)
        flt.addStretch(1)
        right.addWidget(flt_frame)

        # --------- MODERN HEADER (Sağ Taraf İçin) ---------
        # Bilgi satırını (info) ve butonların bir kısmını buraya alacağız.
        
        # Tablo
        # Tablo
        self.tab = QTableWidget(0, 6)
        self.tab.setHorizontalHeaderLabels(["Yapıldı", "Ders", "Kitap", "Konu", "Süre(dk)", "Açıklama"])
        self.tab.horizontalHeader().setStretchLastSection(True)
        self.tab.setAlternatingRowColors(True)
        self.tab.setShowGrid(False)  # Izgaraları kaldır, modern görünüm
        
        # Modern Table Stylesheet
        self.tab.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                gridline-color: #f1f5f9;
                selection-background-color: #eff6ff; /* Light Blue Focus */
                selection-color: #1e293b;
                font-family: 'Segoe UI', sans-serif;
                outline: none; /* Focus rect yok */
            }
            QTableWidget::item {
                padding: 8px 12px;
                border-bottom: 1px solid #f1f5f9;
                color: #334155;
            }
            QTableWidget::item:focus {
                outline: none;
                border: none;
            }
            QTableWidget::item:selected {
                background-color: #eff6ff;
                border-bottom: 1px solid #bfdbfe;
                color: #1e293b;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                padding: 10px 12px;
                border: none;
                border-bottom: 2px solid #e2e8f0;
                font-weight: 700;
                color: #475569;
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
        """)

        try:
            self.tab.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            self.tab.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            self.tab.verticalHeader().setVisible(False) # Satır noları gizle
            self.tab.setFocusPolicy(Qt.FocusPolicy.NoFocus) # Çerçeve focus çizgisini kaldır
        except Exception:
            pass
        self.tab.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right.addWidget(self.tab)

        #sağ tablo
        # === Sağ tablo: tek seferlik kurulum ===
        self._setup_right_table_styles()
        self.tab.itemChanged.connect(self._on_table_item_changed)

        # Adım 3'ü otomatik yap: model değiştikçe stili tazele
        from PyQt6.QtCore import QTimer
        from PyQt6.QtGui import QColor, QBrush  # (stil metotları bunları kullanıyor)

        m = self.tab.model()

        # Checkbox sütunundaki boşluğa tıklanınca da değişsin
        self.tab.cellClicked.connect(self._chk_cell_click)

        # Model olaylarına bağlan
        for sig in (m.rowsInserted, m.rowsRemoved, m.modelReset, m.layoutChanged, m.dataChanged):
            sig.connect(lambda *_, self=self: self._refresh_right_table_styles())

        # İlk açılışta da bir kez çalışsın
        QTimer.singleShot(0, self._refresh_right_table_styles)
        #

        split.addWidget(rightW)

        # oranlar
        split.setStretchFactor(0, 6)  # sol geniş
        split.setStretchFactor(1, 4)  # sağ biraz dar
        # --- Splitter genişliğini hatırla (tek blok çözüm) ---
        from PyQt6.QtCore import QSettings

        # Önce daha önce kaydedilen değerleri yükle
        _s = QSettings("OKApps", "YKS_LGS_HomeworkManager")
        _sizes = _s.value("OdevKontrol/SplitSizes", None)
        if _sizes:
            try:
                split.setSizes([int(x) for x in list(_sizes)])
            except Exception:
                pass

        # Splitter hareket ettikçe otomatik kaydet
        def _save_sizes():
            _s.setValue("OdevKontrol/SplitSizes", split.sizes())

        try:
            split.splitterMoved.connect(lambda *_: _save_sizes())
        except Exception:
            pass

        # --------- SİNYALLER / KISAYOLLAR ---------
        self.lstKume.currentRowChanged.connect(lambda _: self._kume_ac())
        # self.btnHepsiTamam... (yukarıda bağlandı)
        self.btnHepsiTamam.clicked.connect(self._hepsi_tamam)
        self.btnHepsiGeri.clicked.connect(self._hepsi_geri)
        self.btnKaydet.clicked.connect(self._kaydet)
        self.btnAktar.clicked.connect(self._aktar)
        self.btnAktarSilmeden.clicked.connect(self.aktar_silmeden)  # ✅ yeni
        self.btnSatirSil.clicked.connect(getattr(self, "_satir_sil", lambda: None))
        self.btnKumeSil.clicked.connect(getattr(self, "_kume_sil", lambda: None))
        self.btnWpGonder.clicked.connect(self._wp_gonder)
        self.btnKapat.clicked.connect(self.accept)
        self.tab.itemChanged.connect(lambda _: self._hesapla_yuzde())






        # Filtre sinyalleri
        self.cboFltDers.currentIndexChanged.connect(getattr(self, "_apply_filters", lambda: None))
        self.cboFltDurum.currentIndexChanged.connect(getattr(self, "_apply_filters", lambda: None))
        self.txtFltAra.textChanged.connect(getattr(self, "_apply_filters", lambda: None))
        btnFltClear.clicked.connect(getattr(self, "_clear_filters", lambda: None))


        # Kısayollar
        QShortcut(QKeySequence("Ctrl+Shift+A"), self, activated=self._hepsi_tamam)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self, activated=self._hepsi_geri)
        QShortcut(QKeySequence("F7"), self, activated=self._yapilmayanlari_geri_tasi)
        QShortcut(QKeySequence("Delete"), self, activated=getattr(self, "_satir_sil", lambda: None))
        QShortcut(QKeySequence("F8"), self, activated=self.aktar_silmeden)  # ✅ yeni

    # ---------------- Veri yükleme ----------------
    def _yukle_kumeler(self):
        con = db.get_conn()
        ogr = con.execute("SELECT ad, soyad FROM ogrenci WHERE id=?", (self.ogr_id,)).fetchone()
        ad_soyad = f"{(ogr['ad'] or '')} {(ogr['soyad'] or '')}".strip() if ogr else ""
        self.lblOgr.setText(f"👤 {ad_soyad}")

        # adet (toplam ödev) + tamam (yapıldı/tamam)
        rows = con.execute("""
            SELECT
                k.id,
                COALESCE(k.verilis_tarihi,'')   AS verilis_tarihi,
                COALESCE(k.bitis_tarihi,'')     AS bitis_tarihi,
                COALESCE((
                    SELECT COUNT(*) FROM odev d WHERE d.kume_id = k.id
                ), 0) AS adet,
                COALESCE((
                    SELECT COUNT(*) FROM odev d
                    WHERE d.kume_id = k.id AND LOWER(COALESCE(d.durum,'')) IN ('yapildi','tamam')
                ), 0) AS tamam,

                -- 🟣 Rozet için: bu kümede silmeden aktarılan kaç ödev var?
                COALESCE((
                    SELECT COUNT(*) FROM odev d
                    WHERE d.kume_id = k.id AND COALESCE(d.aktarildi,0) = 1
                ), 0) AS aktarilan,

                -- 🟣 Rozet tooltip’i için: en son aktarım tarihi
                COALESCE((
                    SELECT MAX(d.aktarim_tarihi) FROM odev d
                    WHERE d.kume_id = k.id AND COALESCE(d.aktarildi,0) = 1
                ), '') AS son_aktarim

            FROM odev_kume k
            WHERE k.ogrenci_id = ?
            ORDER BY COALESCE(k.verilis_tarihi,'') DESC, k.id DESC
        """, (self.ogr_id,)).fetchall()

        self._style_left_list()
        self._populate_kume_list(rows)

        # İlk öğeyi seç ve tabloyu yükle (varsa)
        if self.lstKume.count() > 0:
            self.lstKume.setCurrentRow(0)
            try:
                self._kume_ac()
            except Exception:
                pass
        else:
            self.tab.setRowCount(0)
            self._hesapla_yuzde()

    def _secili_kume_id(self):
        """Şu anda seçili olan ödev kümesinin ID'sini döndürür (güvenli)."""
        it = self.lstKume.currentItem()
        if not it:
            return None

        # Öncelik: UserRole içinde doğrudan int id
        try:
            val = it.data(USERROLE)
            if val is not None:
                return int(val)
        except Exception:
            pass

        # Eski biçim (#13 …) için uyum
        try:
            text = (it.text() or "").strip()
            if text.startswith("#"):
                return int(text.split()[0].replace("#", ""))
        except Exception:
            pass

        return None

    def _secili_kume_id_listesi(self):
        """Küme listesinde seçilen tüm item’ların ID’lerini döndür."""
        ids = []
        for it in self.lstKume.selectedItems():
            try:
                val = it.data(USERROLE)
                if val is not None:
                    ids.append(int(val))
            except Exception:
                try:
                    text = (it.text() or "").strip()
                    if text.startswith("#"):
                        ids.append(int(text.split()[0].replace("#", "")))
                except Exception:
                    pass
        if not ids:
            k = self._secili_kume_id()
            if k:
                ids.append(k)
        return sorted(set(ids))

    def _tum_kume_idleri(self):
        """Öğrencinin tüm küme ID’lerini getir (desc)."""
        con = db.get_conn()
        rows = con.execute(
            "SELECT id FROM odev_kume WHERE ogrenci_id=? ORDER BY id DESC",
            (self.ogr_id,)
        ).fetchall()
        return [int(r["id"]) for r in rows]

    def _kume_odev_satirlari(self, kume_id: int):
        """Bir kümenin ödev satırlarını ve tarih aralığını döndürür."""
        con = db.get_conn()
        info = con.execute(
            "SELECT verilis_tarihi, bitis_tarihi FROM odev_kume WHERE id=?",
            (kume_id,)
        ).fetchone()
        ver = info["verilis_tarihi"] or "-"
        bit = info["bitis_tarihi"] or "-"
        rows = con.execute(
            "SELECT ders, kitap_ad, konu_ad, COALESCE(saat_dk,0) AS dk, durum "
            "FROM odev WHERE kume_id=? ORDER BY id",
            (kume_id,)
        ).fetchall()
        items = [{
            "ders": r["ders"], 
            "kitap": r["kitap_ad"], 
            "konu": r["konu_ad"], 
            "dk": int(r["dk"] or 0),
            "durum": (r["durum"] or "devam")
        } for r in rows]
        return (ver, bit, items)

    def _mesaj_olustur(self, kume_idler, baslik_adi: str):
        """Bir veya birden çok küme için WhatsApp metnini üretir."""
        parcalar = []
        toplam_sure = 0

        # Başlık otomatik kalın, emoji ekle (eğer baslık_adi içinde yoksa)
        if "Ödev Özeti" in baslik_adi and "🎓" not in baslik_adi:
             baslik_adi = f"🎓 *{baslik_adi}*"
        else:
             baslik_adi = f"*{baslik_adi}*"

        parcalar.append(baslik_adi)

        for kid in kume_idler:
            ver, bit, items = self._kume_odev_satirlari(kid)
            if not items:
                continue
            
            # Küme başlığı
            parcalar.append(f"\n📅 *Küme #{kid}* ({ver} → {bit})")
            
            # Listeyi "Tablo gibi" (Code Block) içinde gösteriyoruz
            table_lines = []
            for it in items:
                # Durum ikonu
                if it['durum'] == 'yapildi':
                    icon = "✅"
                elif it['durum'] == 'iptal':
                    icon = "🚫"
                else:
                    icon = "⏳" # devam/boş
                
                # Satır içeriği: Ders / Kitap / Konu
                satir = f"{icon} {it['ders']} / {it['kitap']} / {it['konu']}"
                if it['dk'] > 0:
                    satir += f" ({it['dk']} dk)"
                    toplam_sure += it['dk']
                table_lines.append(satir)

            # Code block wrap
            if table_lines:
                parcalar.append("```")
                parcalar.extend(table_lines)
                parcalar.append("```")

            # Sadece ayırıcı çizgi yerine boşluk
            parcalar.append("") 

        if not parcalar:
            return None

        govde = "\n".join(parcalar).strip()
        
        alt_bilgi = []
        if toplam_sure > 0:
            alt_bilgi.append(f"⏱️ _Toplam Süre: {toplam_sure} dk_")
        
        alt_bilgi.append("🚀 _Başarılar dileriz._")
        
        alt_str = "\n".join(alt_bilgi)

        return f"{govde}\n\n{alt_str}"

    def _telefon_listesi(self):
        """Öğrencinin veli/öğrenci telefonlarını dizi olarak döndür."""
        con = db.get_conn()
        r = con.execute(
            "SELECT veli_tel1, veli_tel2, ogr_tel, ad, soyad FROM ogrenci WHERE id=?",
            (self.ogr_id,)
        ).fetchone()
        nums = []
        for k in ("veli_tel1", "veli_tel2", "ogr_tel"):
            v = (r[k] or "").strip()
            if v:
                nums.append(v)
        adsoyad = f"{(r['ad'] or '')} {(r['soyad'] or '')}".strip()
        return adsoyad, nums

    # ---- küçük yardımcı: signals güvenli bloklayıcı ----
    from contextlib import contextmanager



    @contextmanager
    def _block_table_signals(self):
        """Tablo sinyallerini geçici olarak devre dışı bırakır."""
        try:
            self.tab.blockSignals(True)
            yield
        finally:
            try:
                self.tab.blockSignals(False)
            except Exception:
                pass

    def _kume_ac(self, kume_id: int | None = None, only_moved: bool | None = None):
        """
        Küme içeriğini yükler.
        - only_moved=True  -> sadece silmeden aktarılanları göster
        - only_moved=False -> tüm satırları göster (aktarılmış + aktarılmamış)
        - only_moved=None  -> varsayılanı sıfırla (tümü)
        """
        # 0) Bayrak: güvenli başlat + tek yerden yönet
        if not hasattr(self, "_only_moved"):
            self._only_moved = False
        if only_moved is None:
            self._only_moved = False
        else:
            self._only_moved = bool(only_moved)

        # 1) Küme kimliği
        if kume_id is None:
            kume_id = self._secili_kume_id()
        if not kume_id:
            self.tab.setRowCount(0)
            self._hesapla_yuzde()
            return

        # 2) Filtreler (ders / arama)
        ders_eq = None
        try:
            cbo = getattr(self, "cboDersFilter", None)
            if cbo:
                txt = (cbo.currentText() or "").strip()
                if txt and txt.lower() not in ("tümü", "tum", "hepsi", "all"):
                    ders_eq = txt
        except Exception:
            pass

        q = None
        try:
            le = getattr(self, "txtAra", None)
            t = (le.text() or "").strip() if le else ""
            q = t or None
        except Exception:
            pass

        # 3) Sorgu
        where = ["kume_id = ?"]
        args = [kume_id]

        if ders_eq:
            where.append("LOWER(ders) = LOWER(?)")
            args.append(ders_eq)

        if q:
            where.append("(LOWER(kitap_ad) LIKE LOWER(?) OR LOWER(konu_ad) LIKE LOWER(?))")
            like = f"%{q}%"
            args.extend([like, like])

        # 🔵 Rozet filtresi: SADECE aktarılanlar (aksi halde tümü)
        if self._only_moved:
            where.append("COALESCE(aktarildi,0) = 1")

        sql = (
            "SELECT id, ders, kitap_ad, konu_ad, "
            "       COALESCE(saat_dk,0) AS dk, "
            "       COALESCE(aciklama,'') AS aciklama, "
            "       LOWER(COALESCE(durum,'')) AS durum, "
            "       COALESCE(aktarildi,0) AS aktarildi, "
            "       COALESCE(aktarim_tarihi,'') AS aktarim_tarihi "
            f"FROM odev WHERE {' AND '.join(where)} "
            "ORDER BY id"
        )

        # 4) Çek & tabloya bas
        con = db.get_conn()
        rows = con.execute(sql, args).fetchall()

        with self._block_table_signals():
            self.tab.setRowCount(0)
            done = 0
            for r in rows:
                i = self.tab.rowCount()
                self.tab.insertRow(i)

                # checkbox
                chk = QTableWidgetItem()
                # Düzenlenebilir olmasın (Editörü kapat), Sadece Check edilebilir ve Seçilebilir olsun.
                chk.setFlags(
                    Qt.ItemFlag.ItemIsUserCheckable | 
                    Qt.ItemFlag.ItemIsEnabled | 
                    Qt.ItemFlag.ItemIsSelectable
                )
                chk.setFlags(chk.flags() & ~Qt.ItemFlag.ItemIsEditable) # Garanti olsun

                is_done = (r["durum"] in ("yapildi", "tamam"))
                chk.setCheckState(Qt.CheckState.Checked if is_done else Qt.CheckState.Unchecked)
                if is_done:
                    done += 1
                self.tab.setItem(i, 0, chk)

                # kolonlar
                # Ders (Bold ve Renkli)
                it_ders = QTableWidgetItem(r["ders"] or "")
                it_ders.setData(USERROLE, int(r["id"]))
                it_ders.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                it_ders.setForeground(QBrush(QColor("#0ea5e9"))) # Sky 500
                self.tab.setItem(i, 1, it_ders)

                # Kitap (Hafif silik)
                it_kitap = QTableWidgetItem(r["kitap_ad"] or "")
                it_kitap.setForeground(QBrush(QColor("#64748b"))) # Slate 500
                self.tab.setItem(i, 2, it_kitap)

                # Konu (Normal)
                it_konu = QTableWidgetItem(r["konu_ad"] or "")
                it_konu.setForeground(QBrush(QColor("#0f172a"))) # Slate 900
                self.tab.setItem(i, 3, it_konu)
                
                # Süre (Ortalı)
                it_sure = QTableWidgetItem(str(int(r["dk"] or 0)))
                it_sure.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tab.setItem(i, 4, it_sure)
                
                # Açıklama
                self.tab.setItem(i, 5, QTableWidgetItem(r["aciklama"] or ""))

                # aktarılanı kilitle/etiketle
                if int(r["aktarildi"] or 0) == 1:
                    self._mark_row_aktarildi(i, r["aktarim_tarihi"] or "")

            try:
                self.tab.resizeColumnsToContents()
                self.tab.horizontalHeader().setStretchLastSection(True)
            except Exception:
                pass

        # 5) Yüzde
        #self.lblYuzde.setText(f"%{int(100 * done / max(1, len(rows))) if rows else 0}")
        self._update_header_stats()
    def _mark_row_aktarildi(self, row: int, tarih: str = ""):
        """Satırı kilitle, gri/lila fonda göster, checkbox'ı pasifleştir, tooltip ekle."""
        tip = "Bu ödev silmeden aktarıldı.\nArtık düzenlenemez."
        if tarih:
            tip += f"\nAktarım tarihi: {tarih}"

        # Checkbox kontrolü
        it_chk = self.tab.item(row, 0)
        if it_chk:
            it_chk.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable | 
                Qt.ItemFlag.ItemIsEnabled | 
                Qt.ItemFlag.ItemIsSelectable
            )
            it_chk.setToolTip(tip)

        # Diğer hücreleri seçilebilir ama düzenlenemez yap
        for col in range(1, self.tab.columnCount()):
            it = self.tab.item(row, col)
            if not it:
                continue
            it.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            it.setToolTip(tip)

        # Arkaplan / yazı rengi
        from PyQt6.QtGui import QColor, QBrush
        bg = QBrush(QColor("#f3e8ff"))  # yumuşak lila
        fg = QBrush(QColor("#6b21a8"))  # mor vurgu
        for col in range(self.tab.columnCount()):
            it = self.tab.item(row, col)
            if it:
                it.setBackground(bg)
                if col in (1, 5):
                    it.setForeground(fg)
                # Açıklamaya 🔒 rozeti ekle
                if col == 5:
                    txt = it.text() or ""
                    rozet = f"🔒 Aktarıldı{(' • ' + tarih) if tarih else ''}"
                    if rozet not in txt:
                        it.setText(f"{rozet} — {txt}" if txt else rozet)

    # ---------------- Silme işlemleri ----------------
    def _kume_sil(self):
        kume_id = self._secili_kume_id()
        if not kume_id:
            QMessageBox.information(self, "Sil", "Önce bir küme seçin.")
            return

        if QMessageBox.question(
            self, "Kümeyi Sil",
            "Bu kümeyi ve içindeki tüm ödevleri kalıcı olarak silmek istiyor musunuz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return

        con = db.get_conn()
        cur = con.cursor()
        try:
            cur.execute("DELETE FROM odev WHERE kume_id=?", (kume_id,))
            cur.execute("DELETE FROM odev_kume WHERE id=?", (kume_id,))
            con.commit()
            self.tab.setRowCount(0)
            self._yukle_kumeler()
        except Exception as e:
            try:
                con.rollback()
            except Exception:
                pass
            QMessageBox.critical(self, "Hata", f"Küme silinemedi:\n{e}")

    def _satir_sil(self):
        sel_rows = sorted({i.row() for i in self.tab.selectedIndexes()})
        if not sel_rows:
            r = self.tab.currentRow()
            if r >= 0:
                sel_rows = [r]
        if not sel_rows:
            QMessageBox.information(self, "Sil", "Silmek için satır seçin.")
            return

        if QMessageBox.question(
            self, "Ödev Sil",
            f"Seçili {len(sel_rows)} ödev kaydını silmek istiyor musunuz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return

        # id’leri 1. sütunun UserRole’ünden çekiyoruz
        od_ids = []
        for r in sel_rows:
            it = self.tab.item(r, 1)  # 'Ders' hücresi
            if it:
                val = it.data(USERROLE)
                if val is not None:
                    try:
                        od_ids.append(int(val))
                    except Exception:
                        pass

        if not od_ids:
            QMessageBox.information(self, "Sil", "Seçilen satırlarda silinecek id bulunamadı.")
            return

        con = db.get_conn()
        cur = con.cursor()
        try:
            q = "DELETE FROM odev WHERE id IN (" + ",".join(["?"] * len(od_ids)) + ")"
            cur.execute(q, od_ids)
            con.commit()
            for r in sorted(sel_rows, reverse=True):
                self.tab.removeRow(r)
            self._hesapla_yuzde()
        except Exception as e:
            try:
                con.rollback()
            except Exception:
                pass
            QMessageBox.critical(self, "Hata", f"Ödev(ler) silinemedi:\n{e}")

    # ---------------- Bilgi yardımcıları ----------------
    def _satir_bilgisi(self, i):
        return dict(
            id=int(self.tab.item(i, 1).data(USERROLE)),
            ders=self.tab.item(i, 1).text(),
            kitap=self.tab.item(i, 2).text(),
            konu=self.tab.item(i, 3).text(),
        )

    # ---------------- İşlemler ----------------

    def _kaydet(self):
        kume_id = self._secili_kume_id()
        if not kume_id:
            return

        con = db.get_conn()
        cur = con.cursor()

        # Aynı "Kaydet" turunda uyarıyı en fazla 1 kez göster
        self._warned_old_cluster = False

        for i in range(self.tab.rowCount()):
            # 0: checkbox, 1: ders, 2: kitap, 3: konu, 5: açıklama (sizde böyle görünüyor)
            it_chk = self.tab.item(i, 0)
            it_ders = self.tab.item(i, 1)
            it_kitap = self.tab.item(i, 2)
            it_konu = self.tab.item(i, 3)
            it_ack = self.tab.item(i, 5)

            # USERROLE'de odev id
            od_id = int(self.tab.item(i, 1).data(USERROLE))
            yapildi = (it_chk and it_chk.checkState() == Qt.CheckState.Checked)

            new_durum = "yapildi" if yapildi else "devam"
            bitis_tarihi = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if yapildi else None

            if yapildi:
                try:
                    ders = (self.tab.item(i, 1).text() if self.tab.item(i, 1) else "") or ""
                    kitap = (self.tab.item(i, 2).text() if self.tab.item(i, 2) else "") or ""
                    konu = (self.tab.item(i, 3).text() if self.tab.item(i, 3) else "") or ""

                    row_newest = con.execute("""
                        SELECT MAX(k.id) AS max_id
                          FROM odev d
                          JOIN odev_kume k ON k.id = d.kume_id
                         WHERE k.ogrenci_id = ?
                           AND d.ders      = ?
                           AND d.kitap_ad  = ?
                           AND d.konu_ad   = ?
                    """, (self.ogr_id, ders, kitap, konu)).fetchone()

                    newest_id = int(row_newest["max_id"]) if row_newest and row_newest["max_id"] is not None else None
                    if newest_id and newest_id > int(kume_id) and not self._warned_old_cluster:
                        QMessageBox.information(
                            self, "Bilgi",
                            "Bu ödev daha yeni bir kümede de yer alıyor.\n"
                            "Yine de eski kümede TAMAMLANDI olarak kaydedilecek."
                        )
                        self._warned_old_cluster = True
                except Exception:
                    pass

            cur.execute(
                "UPDATE odev SET durum=?, aciklama=? WHERE id=?",
                ("yapildi" if yapildi else "devam",
                 it_ack.text() if it_ack else "",
                 od_id)
            )
        con.commit()
        audit_manager.log("UPDATE", "HOMEWORK", f"Ödev kümesi kaydedildi (ID: {kume_id})")

        # Tamamlanan / kalan listeleri sinyal iletimi için
        tamamlanan, kalan = [], []
        for i in range(self.tab.rowCount()):
            info = self._satir_bilgisi(i)
            it_chk = self.tab.item(i, 0)
            if it_chk and it_chk.checkState() == Qt.CheckState.Checked:
                tamamlanan.append(info)
            else:
                kalan.append(info)

        #s--
        self.sonuc_sinyal.emit(tamamlanan, kalan)

        # Küçük bilgi tostu
        quick_toast(self, "Durumlar güncellendi.", kind_color="#16a34a", duration_ms=1800, font_size=14)

        # --- %50 / %75 motivasyonları (mevcut yapıyı BOZMADAN) ---
        try:
            rc = self.tab.rowCount()
            if rc > 0:
                checked = 0
                for i in range(rc):
                    it_chk = self.tab.item(i, 0)
                    if it_chk and it_chk.checkState() == Qt.CheckState.Checked:
                        checked += 1
                yuzde = (checked / float(rc)) * 100.0
                motivate_for_progress(self, yuzde)
        except Exception:
            # burada sessiz kalmak daha güvenli
            pass

        # === KUTLAMA: ayarlara saygılı tek akış (SADECE %100) ===
        if self._all_checked():
            try:
                from utils import settings as appset
                # yeni veya eski anahtarı oku
                auto = appset.ayar_get(
                    "motive_auto_on_full",
                    appset.ayar_get("motive_auto_100", "1")
                )
            except Exception:
                auto = "1"
            if str(auto).strip().lower() in ("1", "true", "yes", "evet", "on"):
                celebrate_saved(self)

        #f--




    #ödevi full yapanlar için motivasyon yazıları
    def _all_checked(self) -> bool:  # motivation_toast.py kullanıyor
        rc = self.tab.rowCount()
        if rc == 0:
            return False
        for i in range(rc):
            it = self.tab.item(i, 0)
            if not it or it.checkState() != Qt.CheckState.Checked:
                return False
        return True





        """
        İşaretlenmemiş (yapılmayan) ödevleri:
          - 'odev' tablosundan siler (kayıt kümeden tamamen çıkar),
          - ebeveyne aktarılacak listeye ekler (ödev takip formu, "verilenler"e düşsün diye),
          - küme tamamen boşaldıysa 'odev_kume' kaydını da siler,
          - sadece UNCHECKED olanları aktarır (CHECKED asla aktarılmaz).
        """
        kume_id = self._secili_kume_id()
        if not kume_id:
            return

        con = db.get_conn()
        cur = con.cursor()

        aktar_list = []
        silinecek_odev_idler = []

        # 1) Tablodaki satırları tara → SADECE Unchecked olanları topla
        for i in range(self.tab.rowCount()):
            chk_item = self.tab.item(i, 0)
            # güvenli kontrol: checkbox yoksa "yapıldı" kabul edip atla
            if not chk_item:
                continue

            state = chk_item.checkState()
            is_unchecked = (state == Qt.CheckState.Unchecked)  # sadece tam Unchecked aktarılır

            if not is_unchecked:
                # Checked veya PartiallyChecked ise ATLA (aktarma)
                continue

            # Bu satır aktarılacak (yani kümeden silinecek)
            try:
                od_id = int(self.tab.item(i, 1).data(USERROLE))
            except Exception:
                continue

            silinecek_odev_idler.append(od_id)
            aktar_list.append(self._satir_bilgisi(i))  # (ders, kitap, konu) -> ödev takip formuna

        # 2) Hiç bir şey yoksa çık
        if not silinecek_odev_idler:
            # yine de ebeveyne boş listeyi verelim; o tarafta bir şey yapılmaz
            self.setProperty("aktar_list", [])
            self.done(2)
            return

        # 3) DB'de bu ödevleri kümeden tamamen sil
        try:
            q = "DELETE FROM odev WHERE id IN (" + ",".join(["?"] * len(silinecek_odev_idler)) + ")"
            cur.execute(q, silinecek_odev_idler)

            # küme boşaldı mı? boşaldıysa kümeyi de sil
            kalan = cur.execute("SELECT COUNT(*) FROM odev WHERE kume_id=?", (kume_id,)).fetchone()[0]
            if int(kalan or 0) == 0:
                cur.execute("DELETE FROM odev_kume WHERE id=?", (kume_id,))

            con.commit()
        except Exception:
            con.rollback()
            raise

        # 4) UI tarafı: aktarılan satırları tablodan kaldır ve yüzdeyi güncelle
        try:
            # tablodan, indexler kaymasın diye büyükten küçüğe sil
            # önce bu satırların indexlerini bulalım
            silinecek_satir_indexleri = []
            ids_set = set(silinecek_odev_idler)
            for i in range(self.tab.rowCount()):
                it = self.tab.item(i, 1)
                if it:
                    try:
                        if int(it.data(USERROLE)) in ids_set:
                            silinecek_satir_indexleri.append(i)
                    except Exception:
                        pass
            for r in sorted(silinecek_satir_indexleri, reverse=True):
                self.tab.removeRow(r)
        finally:
            self._hesapla_yuzde()

        # 5) Ebeveyne aktarılacak listeyi ver ve özel kodla dön
        self.setProperty("aktar_list", aktar_list)
        self.done(2)

    ##WİNDOWS DA CHECKBOX TIKLAMA SORUNU İÇİN
    def _aktar(self):
        """
        İşaretlenmemiş (yapılmayan) ödevleri:
          - 'odev' tablosundan siler (kayıt kümeden tamamen çıkar),
          - ebeveyne aktarılacak listeye ekler (ödev takip formu, "verilenler"e düşsün diye),
          - küme tamamen boşaldıysa 'odev_kume' kaydını da siler,
          - sadece UNCHECKED olanları aktarır (CHECKED asla aktarılmaz).
        """
        kume_id = self._secili_kume_id()
        if not kume_id:
            return

        con = db.get_conn()
        cur = con.cursor()

        aktar_list = []
        silinecek_odev_idler = []

        # 1) Tablodaki satırları tara → SADECE Unchecked olanları topla
        for i in range(self.tab.rowCount()):
            chk_item = self.tab.item(i, 0)
            # güvenli kontrol: checkbox yoksa "yapıldı" kabul edip atla
            if not chk_item:
                continue

            state = chk_item.checkState()
            is_unchecked = (state == Qt.CheckState.Unchecked)  # sadece tam Unchecked aktarılır

            if not is_unchecked:
                # Checked veya PartiallyChecked ise ATLA (aktarma)
                continue

            # Bu satır aktarılacak (yani kümeden silinecek)
            try:
                od_id = int(self.tab.item(i, 1).data(USERROLE))
            except Exception:
                continue

            silinecek_odev_idler.append(od_id)
            aktar_list.append(self._satir_bilgisi(i))  # (ders, kitap, konu) -> ödev takip formuna

        # 2) Hiç bir şey yoksa çık
        if not silinecek_odev_idler:
            # yine de ebeveyne boş listeyi verelim; o tarafta bir şey yapılmaz
            self.setProperty("aktar_list", [])
            self.done(2)
            return

        # 3) DB'de bu ödevleri kümeden tamamen sil
        try:
            q = "DELETE FROM odev WHERE id IN (" + ",".join(["?"] * len(silinecek_odev_idler)) + ")"
            cur.execute(q, silinecek_odev_idler)

            # küme boşaldı mı? boşaldıysa kümeyi de sil
            kalan = cur.execute("SELECT COUNT(*) FROM odev WHERE kume_id=?", (kume_id,)).fetchone()[0]
            if int(kalan or 0) == 0:
                cur.execute("DELETE FROM odev_kume WHERE id=?", (kume_id,))

            con.commit()
        except Exception:
            con.rollback()
            raise

        # 4) UI tarafı: aktarılan satırları tablodan kaldır ve yüzdeyi güncelle
        try:
            # tablodan, indexler kaymasın diye büyükten küçüğe sil
            # önce bu satırların indexlerini bulalım
            silinecek_satir_indexleri = []
            ids_set = set(silinecek_odev_idler)
            for i in range(self.tab.rowCount()):
                it = self.tab.item(i, 1)
                if it:
                    try:
                        if int(it.data(USERROLE)) in ids_set:
                            silinecek_satir_indexleri.append(i)
                    except Exception:
                        pass
            for r in sorted(silinecek_satir_indexleri, reverse=True):
                self.tab.removeRow(r)
        finally:
            self._hesapla_yuzde()

        # 5) Ebeveyne aktarılacak listeyi ver ve özel kodla dön
        self.setProperty("aktar_list", aktar_list)
        self.done(2)

        # _aktar sonunda
        self.setProperty("aktar_list", aktar_list)
        self.setProperty("aktar_mode", "silerek")
        self.done(2)

    #s ödevleri silmeden aktarma
    def _tbl_cols(self, con, table: str) -> set[str]:
        try:
            rows = con.execute(f"PRAGMA table_info({table})").fetchall()
            cols = set()
            for r in rows:
                cols.add(r[1] if isinstance(r, tuple) else r["name"])
            return cols
        except Exception:
            return set()
    def _ensure_odev_satir_min_schema(self, cur):
        """odev_satir için aktarımda gerekli kolonları yoksa ekler."""
        need = [
            ("odev_id", "INTEGER"),
            ("ogrenci_id", "INTEGER"),
            ("kume_id", "INTEGER"),
            ("ders", "TEXT"),
            ("kitap_ad", "TEXT"),
            ("konu_ad", "TEXT"),
            ("dk", "INTEGER DEFAULT 0"),
            ("aciklama", "TEXT"),
            ("aktarildi", "INTEGER DEFAULT 0"),
            ("aktarim_tarihi", "TEXT"),
            ("tarih", "TEXT"),
            ("durum", "TEXT DEFAULT 'devam'"),
            ("gerekce", "TEXT"),
            ("koc", "TEXT"),
        ]
        cols = self._tbl_cols(cur.connection, "odev_satir")
        if not cols:
            # tablo yoksa minimal bir tablo da oluşturabiliriz:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS odev_satir (
                    id INTEGER PRIMARY KEY AUTOINCREMENT
                )
            """)
            cols = self._tbl_cols(cur.connection, "odev_satir")
        for name, typ in need:
            if name not in cols:
                try:
                    cur.execute(f"ALTER TABLE odev_satir ADD COLUMN {name} {typ}")
                except Exception:
                    pass  # başka yerde farklı tipte olabilir; önemli olan INSERT edebilmek
    def _ensure_aktar_log_schema(self, cur):
        cur.execute("""
            CREATE TABLE IF NOT EXISTS odev_aktar_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                ogrenci_id INTEGER,
                kume_id INTEGER,
                odev_id INTEGER,
                ders TEXT, kitap_ad TEXT, konu_ad TEXT,
                dk INTEGER,
                note TEXT,
                source TEXT DEFAULT 'OdevKontrol',
                user TEXT
            )
        """)

    def _unchecked_rows(self):
        """Tablodaki işaretlenmemiş (yapılmayan) satırların özetini döndürür."""
        rows = []
        for i in range(self.tab.rowCount()):
            it_chk = self.tab.item(i, 0)
            if not it_chk or it_chk.checkState() == Qt.CheckState.Checked:
                continue  # sadece Unchecked
            try:
                od_id = int(self.tab.item(i, 1).data(USERROLE))
            except Exception:
                od_id = None
            ders = (self.tab.item(i, 1).text() if self.tab.item(i, 1) else "") or ""
            kitap = (self.tab.item(i, 2).text() if self.tab.item(i, 2) else "") or ""
            konu = (self.tab.item(i, 3).text() if self.tab.item(i, 3) else "") or ""
            try:
                dk = int((self.tab.item(i, 4).text() or "0").strip())
            except Exception:
                dk = 0
            acik = (self.tab.item(i, 5).text() if self.tab.item(i, 5) else "") or ""
            rows.append({
                "odev_id": od_id, "ders": ders, "kitap_ad": kitap, "konu_ad": konu,
                "dk": dk, "aciklama": acik
            })
        return rows
   
        """
        Yapılmayan (Unchecked) ödevleri 'silmeden aktar':
          - odev.aktarildi=1, odev.aktarim_tarihi=BUGÜN, odev.durum='aktarildi'
          - (opsiyonel) odev_islem_log'a kayıt
          - UI'da satırları kilitle + 'Aktarıldı · YYYY-MM-DD' göster
          - Sol listedeki küme kartlarını (rozetler dahil) tazele
          - Parent forma aktar_list ver ve mevcut akıştaki done(2) ile dön
          - Zaten aktarılmış ödevleri tekrar aktarmaya çalışmaz.
        """
        from PyQt6.QtWidgets import QMessageBox
        import datetime as _dt

        # --- 0) seçili küme kontrolü
        kume_id = self._secili_kume_id()
        if not kume_id:
            QMessageBox.information(self, "Aktar", "Lütfen bir küme seçin.")
            return

        # --- 1) yapılmayan satırları ve id'leri topla
        ids_unchecked = []
        for i in range(self.tab.rowCount()):
            chk = self.tab.item(i, 0)
            if not chk or chk.checkState() == Qt.CheckState.Checked:
                continue  # sadece yapılmayanlar
            try:
                od_id = int(self.tab.item(i, 1).data(USERROLE))
            except Exception:
                continue
            ids_unchecked.append(od_id)

        if not ids_unchecked:
            try:
                from ui.motivation_toast import quick_toast
                quick_toast(self, "Aktarılacak ödev yok.", kind_color="#64748b",
                            duration_ms=1400, font_size=13)
            except Exception:
                QMessageBox.information(self, "Aktar", "Aktarılacak ödev yok.")
            return

        # --- 1.5) DB: zaten aktarılmış olanları ele (tekrar eklenmesin)
        con = db.get_conn()
        cur = con.cursor()
        try:
            q_sel = ("SELECT id FROM odev WHERE id IN (" + ",".join(["?"] * len(ids_unchecked)) + ") "
                                                                                                  "AND COALESCE(aktarildi,0)=0")
            rows = cur.execute(q_sel, ids_unchecked).fetchall()
            ids_to_update = [int(r[0]) for r in rows]
        except Exception:
            # herhangi bir sorun olursa eski davranışı koru
            ids_to_update = ids_unchecked[:]

        if not ids_to_update:
            # Hepsi zaten aktarılmış → kullanıcıyı bilgilendir, ama akışı bozma
            try:
                from ui.motivation_toast import quick_toast
                quick_toast(self, "Seçilen ödevler zaten aktarılmış.", kind_color="#64748b",
                            duration_ms=1400, font_size=13)
                #quick_toast(self, "Seçilen ödevler zaten aktarılmış.", kind_color="#16a34a", duration_ms=1800, font_size=14)
            except Exception:
                pass
            # yine de yüzde ve sol listeyi tazele
            self._hesapla_yuzde()
            try:
                self._yukle_kumeler();
                self._kume_ac(kume_id)
            except Exception:
                pass
            # parent’a boş/aynı aktar_list ile sinyal gönder (orijinal akış)
            self.setProperty("aktar_list", [])
            self.done(2)
            return

        today = _dt.date.today().isoformat()

        # --- 2) DB güncelle: sadece gerçekten aktarılacakları işaretle
        try:
            q_up = ("UPDATE odev SET aktarildi=1, aktarim_tarihi=?, durum='aktarildi' "
                    "WHERE id IN (" + ",".join(["?"] * len(ids_to_update)) + ")")
            cur.execute(q_up, [today, *ids_to_update])

            # (opsiyonel) log
            try:
                cur.executemany(
                    "INSERT INTO odev_islem_log (odev_id, islem, islem_tarihi, notlar) "
                    "VALUES (?, ?, ?, ?)",
                    [(oid, "aktar_silmeden", today, "") for oid in ids_to_update]
                )
            except Exception:
                pass

            con.commit()
        except Exception as e:
            try:
                con.rollback()
            except Exception:
                pass
            QMessageBox.critical(self, "Hata", f"Aktarım sırasında hata oluştu:\n{e}")
            return

        # --- 3) UI: satırları yerinde kilitle + "Aktarıldı · tarih" yaz (sadece güncellenenler)
        try:
            ids_set = set(ids_to_update)
            for i in range(self.tab.rowCount()):
                it = self.tab.item(i, 1)
                if not it:
                    continue
                try:
                    if int(it.data(USERROLE)) in ids_set:
                        # varsa mevcut yardımcı fonksiyonun
                        self._mark_row_aktarildi(i, today)
                except Exception:
                    # minimal kilitleme
                    try:
                        chk = self.tab.item(i, 0)
                        if chk:
                            chk.setFlags(chk.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                        acik_it = self.tab.item(i, 6)  # açıklama kolonu sende 6 idi
                        if acik_it:
                            txt = acik_it.text().strip()
                            prefix = f"Aktarıldı · {today}"
                            acik_it.setText(prefix if not txt else f"{prefix}   •   {txt}")
                    except Exception:
                        pass
        finally:
            self._hesapla_yuzde()

        # --- 3.5) aktar_list: sadece GERÇEKTEN AKTARILANLARLA doldur
        aktar_list = []
        try:
            ids_set = set(ids_to_update)
            for i in range(self.tab.rowCount()):
                it = self.tab.item(i, 1)
                if not it:
                    continue
                try:
                    od_id = int(it.data(USERROLE))
                except Exception:
                    continue
                if od_id in ids_set:
                    try:
                        aktar_list.append(self._satir_bilgisi(i))  # {id, ders, kitap, konu} / senin mevcut formatın
                    except Exception:
                        pass
        except Exception:
            pass

        # --- 4) Sol listedeki küme kartlarını/rozetleri tazele, seçim kaybolmasın
        try:
            self._yukle_kumeler()
            self._kume_ac(kume_id)
        except Exception:
            try:
                self._kume_ac(kume_id)
            except Exception:
                pass

        # --- 5) parent akışına aktar_list ver ve ORİJİNAL gibi bitir
        self.setProperty("aktar_list", aktar_list)
        self.done(2)  # ❗ orijinal davranış: parent tarafı aynen tetiklenir

        # --- 6) minik başarı bildirimi
        try:
            from ui.motivation_toast import quick_toast
            quick_toast(self, "Aktarıldı (silmeden).", kind_color="#0ea5e9",
                        duration_ms=1400, font_size=13)
        except Exception:
            try:
                from ui.toast import show_toast
                show_toast(self, "Aktarıldı (silmeden).", kind="success",
                           duration_ms=1400, corner="br")
            except Exception:
                pass

     ##WİNDOWS DA CHECKBOX TIKLAMA SORUNU İÇİN
    def aktar_silmeden(self):
        """
        Yapılmayan (Unchecked) ödevleri 'silmeden aktar':
          - odev.aktarildi=1, odev.aktarim_tarihi=BUGÜN, odev.durum='aktarildi'
          - (opsiyonel) odev_islem_log'a kayıt
          - UI'da satırları kilitle + 'Aktarıldı · YYYY-MM-DD' göster
          - Sol listedeki küme kartlarını (rozetler dahil) tazele
          - Parent forma aktar_list ver ve mevcut akıştaki done(2) ile dön
          - Zaten aktarılmış ödevleri tekrar aktarmaya çalışmaz.
        """
        from PyQt6.QtWidgets import QMessageBox
        import datetime as _dt

        # --- 0) seçili küme kontrolü
        kume_id = self._secili_kume_id()
        if not kume_id:
            QMessageBox.information(self, "Aktar", "Lütfen bir küme seçin.")
            return

        # --- 1) yapılmayan satırları ve id'leri topla
        ids_unchecked = []
        for i in range(self.tab.rowCount()):
            chk = self.tab.item(i, 0)
            if not chk or chk.checkState() == Qt.CheckState.Checked:
                continue  # sadece yapılmayanlar
            try:
                od_id = int(self.tab.item(i, 1).data(USERROLE))
            except Exception:
                continue
            ids_unchecked.append(od_id)

        if not ids_unchecked:
            try:
                from ui.motivation_toast import quick_toast
                quick_toast(self, "Aktarılacak ödev yok.", kind_color="#64748b",
                            duration_ms=1400, font_size=13)
            except Exception:
                QMessageBox.information(self, "Aktar", "Aktarılacak ödev yok.")
            return

        # --- 1.5) DB: zaten aktarılmış olanları ele (tekrar eklenmesin)
        con = db.get_conn()
        cur = con.cursor()
        try:
            q_sel = ("SELECT id FROM odev WHERE id IN (" + ",".join(["?"] * len(ids_unchecked)) + ") "
                                                                                                  "AND COALESCE(aktarildi,0)=0")
            rows = cur.execute(q_sel, ids_unchecked).fetchall()
            ids_to_update = [int(r[0]) for r in rows]
        except Exception:
            # herhangi bir sorun olursa eski davranışı koru
            ids_to_update = ids_unchecked[:]

        if not ids_to_update:
            # Hepsi zaten aktarılmış → kullanıcıyı bilgilendir, ama akışı bozma
            try:
                from ui.motivation_toast import quick_toast
                quick_toast(self, "Seçilen ödevler zaten aktarılmış.", kind_color="#64748b",
                            duration_ms=1400, font_size=13)
                #quick_toast(self, "Seçilen ödevler zaten aktarılmış.", kind_color="#16a34a", duration_ms=1800, font_size=14)
            except Exception:
                pass
            # yine de yüzde ve sol listeyi tazele
            self._hesapla_yuzde()
            try:
                self._yukle_kumeler();
                self._kume_ac(kume_id)
            except Exception:
                pass
            # parent’a boş/aynı aktar_list ile sinyal gönder (orijinal akış)
            self.setProperty("aktar_list", [])
            self.done(2)
            return

        today = _dt.date.today().isoformat()

        # --- 2) DB güncelle: sadece gerçekten aktarılacakları işaretle
        try:
            q_up = ("UPDATE odev SET aktarildi=1, aktarim_tarihi=?, durum='aktarildi' "
                    "WHERE id IN (" + ",".join(["?"] * len(ids_to_update)) + ")")
            cur.execute(q_up, [today, *ids_to_update])

            # (opsiyonel) log
            try:
                cur.executemany(
                    "INSERT INTO odev_islem_log (odev_id, islem, islem_tarihi, notlar) "
                    "VALUES (?, ?, ?, ?)",
                    [(oid, "aktar_silmeden", today, "") for oid in ids_to_update]
                )
            except Exception:
                pass

            con.commit()
        except Exception as e:
            try:
                con.rollback()
            except Exception:
                pass
            QMessageBox.critical(self, "Hata", f"Aktarım sırasında hata oluştu:\n{e}")
            return

        # --- 3) UI: satırları yerinde kilitle + "Aktarıldı · tarih" yaz (sadece güncellenenler)
        try:
            ids_set = set(ids_to_update)
            for i in range(self.tab.rowCount()):
                it = self.tab.item(i, 1)
                if not it:
                    continue
                try:
                    if int(it.data(USERROLE)) in ids_set:
                        # varsa mevcut yardımcı fonksiyonun
                        self._mark_row_aktarildi(i, today)
                except Exception:
                    # minimal kilitleme
                    try:
                        chk = self.tab.item(i, 0)
                        if chk:
                            chk.setFlags(chk.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                        acik_it = self.tab.item(i, 6)  # açıklama kolonu sende 6 idi
                        if acik_it:
                            txt = acik_it.text().strip()
                            prefix = f"Aktarıldı · {today}"
                            acik_it.setText(prefix if not txt else f"{prefix}   •   {txt}")
                    except Exception:
                        pass
        finally:
            self._hesapla_yuzde()

        # --- 3.5) aktar_list: sadece GERÇEKTEN AKTARILANLARLA doldur
        aktar_list = []
        try:
            ids_set = set(ids_to_update)
            for i in range(self.tab.rowCount()):
                it = self.tab.item(i, 1)
                if not it:
                    continue
                try:
                    od_id = int(it.data(USERROLE))
                except Exception:
                    continue
                if od_id in ids_set:
                    try:
                        aktar_list.append(self._satir_bilgisi(i))  # {id, ders, kitap, konu} / senin mevcut formatın
                    except Exception:
                        pass
        except Exception:
            pass

        # --- 4) Sol listedeki küme kartlarını/rozetleri tazele, seçim kaybolmasın
        try:
            self._yukle_kumeler()
            self._kume_ac(kume_id)
        except Exception:
            try:
                self._kume_ac(kume_id)
            except Exception:
                pass

        # --- 5) parent akışına aktar_list ver ve ORİJİNAL gibi bitir
        self.setProperty("aktar_list", aktar_list)
        self.done(2)  # ❗ orijinal davranış: parent tarafı aynen tetiklenir

        # --- 6) minik başarı bildirimi
        try:
            from ui.motivation_toast import quick_toast
            quick_toast(self, "Aktarıldı (silmeden).", kind_color="#0ea5e9",
                        duration_ms=1400, font_size=13)
        except Exception:
            try:
                from ui.toast import show_toast
                show_toast(self, "Aktarıldı (silmeden).", kind="success",
                           duration_ms=1400, corner="br")
            except Exception:
                pass
        # aktar_silmeden sonunda
        self.setProperty("aktar_list", aktar_list)
        self.setProperty("aktar_mode", "silmeden")
        self.done(2)

    #f

    # ---------------- Kısayollar / Yardımcılar ----------------
    def _yapilmayanlari_geri_tasi(self):
        self._aktar()

    def _set_all_checkbox(self, value: bool):
        state = Qt.CheckState.Checked if value else Qt.CheckState.Unchecked
        for i in range(self.tab.rowCount()):
            it = self.tab.item(i, 0)
            if it is not None:
                it.setCheckState(state)

    def _hepsi_tamam(self):
        self._set_all_checkbox(True)

    def _hepsi_geri(self):
        self._set_all_checkbox(False)



    def _hesapla_yuzde(self):
        rc = self.tab.rowCount()
        if rc == 0:
            self.lblYuzde.setText("%0")
            return

        done = 0
        total = 0
        for i in range(rc):
            # Aktarılanlar yüzdeye dahil edilmesin
            # Bunu, 1. sütundaki USERROLE id'si üzerinden 'aktarildi' bilgisine erişemiyoruz;
            # ama kilitli satırları, checkbox flags'ından anlayabiliriz:
            chk = self.tab.item(i, 0)
            if not chk:
                continue
            is_locked = (chk.flags() == Qt.ItemFlag.NoItemFlags)
            if is_locked:
                continue  # dahil etme
            total += 1
            if chk.checkState() == Qt.CheckState.Checked:
                done += 1

        total = max(1, total)
        yuz = int(100 * done / total)
        self.lblYuzde.setText(f"%{yuz}")

    def _hesapla_yuzde(self):
        rc = self.tab.rowCount()
        if rc == 0:
            # boşken de barı/özetleri yazalım
            self._set_header_stats(0, 1)
            return

        done = 0
        total = 0
        for i in range(rc):
            chk = self.tab.item(i, 0)
            if not chk:
                continue
            is_locked = (chk.flags() == Qt.ItemFlag.NoItemFlags)  # aktarılmışları dahil etme
            if is_locked:
                continue
            total += 1
            if chk.checkState() == Qt.CheckState.Checked:
                done += 1

        total = max(1, total)
        # ⬇️ sadece BU satır değişti
        #self._set_header_stats(done, total)
        self._update_header_stats()



    def _set_compact_mode(self, on: bool):
        """Dar pencerelerde buton metinlerini kısaltır."""
        if getattr(self, "_is_compact", None) == on:
            return
        self._is_compact = on

        if on:
            # Kısa metinler (compact)
            self.btnHepsiTamam.setText("✅ Tümü")
            self.btnHepsiGeri.setText("↩️ Geri")
            self.btnKaydet.setText("💾 Kaydet")
            self.btnAktar.setText("📤 Aktar")
            self.btnAktarSilmeden.setText("📥 Aktar")
            self.btnSatirSil.setText("❌ Sil")
            self.btnKumeSil.setText("🗑️ Küme")
            self.btnWpGonder.setText("💬 WP")
            self.btnKapat.setText("❌ Kapat")

            for b in [
                self.btnHepsiTamam, self.btnHepsiGeri, self.btnKaydet,
                self.btnAktar, self.btnAktarSilmeden, self.btnSatirSil,
                self.btnKumeSil, self.btnWpGonder, self.btnKapat
            ]:
                b.setMinimumHeight(26)
                # b.setStyleSheet("QPushButton{padding:3px 5px; font-size:11px;}") # Stil dosyasını bozma

        else:
            # Normal (uzun) metinler
            self.btnHepsiTamam.setText("✅ Hepsi Tamam (Ctrl+Shift+A)")
            self.btnHepsiGeri.setText("↩️ Geri Taşı (Ctrl+Shift+Z)")
            self.btnKaydet.setText("💾 Kaydet")
            self.btnAktar.setText("📤 Aktar (Temizle) (F7)")
            self.btnAktarSilmeden.setText("📥 Aktar (Sakla) (F8)")
            self.btnSatirSil.setText("❌ Seçilen Sil")
            self.btnKumeSil.setText("🗑️ Küme Sil")
            self.btnWpGonder.setText("💬 WhatsApp")
            self.btnKapat.setText("❌ Kapat")

            for b in [
                self.btnHepsiTamam, self.btnHepsiGeri, self.btnKaydet,
                self.btnAktar, self.btnAktarSilmeden, self.btnSatirSil,
                self.btnKumeSil, self.btnWpGonder, self.btnKapat
            ]:
                b.setMinimumHeight(30)
                b.setStyleSheet("QPushButton{padding:4px 8px; font-size:12px;}")

    def resizeEvent(self, e):
        """Pencere genişliğine göre otomatik kompakt moda geç."""
        super().resizeEvent(e)
        w = self.width()
        # Eşik değerleri denerken hizalı çalışıyor:
        #  ≤ 1050px: compact,  > 1050px: normal
        self._set_compact_mode(w <= 1050)

    # ---------------- WhatsApp gönderimi ----------------
    def _wp_gonder(self):
        # 1) Öğrenci + telefonlar (etiketli)
        con = db.get_conn()
        r = con.execute(
            "SELECT ad, soyad, veli_tel1, veli_tel2, ogr_tel, veli_ad, veli_yakinlik FROM ogrenci WHERE id=?",
            (self.ogr_id,)
        ).fetchone()
        adsoy = f"{(r['ad'] or '').strip()} {(r['soyad'] or '').strip()}".strip()

        alicilar = []
        v1 = (r['veli_tel1'] or '').strip()
        v2 = (r['veli_tel2'] or '').strip()
        vo = (r['ogr_tel'] or '').strip()

        # Veli 1 Etiketi
        v1_lbl = "Veli 1"
        if r['veli_ad']:
            v1_lbl = f"{r['veli_ad']}"
            if r['veli_yakinlik']:
                v1_lbl += f" ({r['veli_yakinlik']})"
        elif r['veli_yakinlik']:
            v1_lbl = f"Veli ({r['veli_yakinlik']})"

        if v1: alicilar.append((v1_lbl, v1))
        if v2: alicilar.append(("Veli 2", v2))
        if vo: alicilar.append((f"Öğrenci ({adsoy})", vo))

        if not alicilar:
            QMessageBox.warning(self, "Eksik", "Kayıtlı telefon bulunamadı (veli_tel1, veli_tel2, ogr_tel).")
            return

        # 2) Kapsam: seçili kümeler mi tümü mü?
        secenek = QMessageBox.question(
            self,
            "Gönderim Kapsamı",
            "Seçili küme(ler)i mi yoksa tüm kümeleri mi göndermek istersiniz?\n\n"
            "Evet: Seçili küme(ler)\nHayır: Tüm kümeler",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if secenek == QMessageBox.StandardButton.Yes:
            kume_ids = self._secili_kume_id_listesi()
        else:
            kume_ids = self._tum_kume_idleri()

        if not kume_ids:
            QMessageBox.information(self, "Bilgi", "Gönderilecek küme bulunamadı.")
            return

        # 3) Mesaj gövdesi
        baslik = f"{adsoy} - Ödev Özeti"
        mesaj_ilk = self._mesaj_olustur(kume_ids, baslik)
        if not mesaj_ilk:
            QMessageBox.information(self, "Bilgi", "Seçilen kapsamda ödev satırı bulunamadı.")
            return

        # 4) Üst bilgi (ayarlar) + logo
        ust_text, logo_path = self._ust_bilgi_paketi()

        # 5) ALICI SEÇİM + ÖNİZLEME DİYALOĞU (Ödev Takip Formu ile aynı)
        #    - Üstteki bilgileri göster
        #    - checkbox varsayılan: işaretli
        dlg = WhatsAppGonderDialog(
            alicilar=alicilar,  # [(etiket, tel), ...]
            mesaj=mesaj_ilk,  # başlangıç mesaj metni
            parent=self,
            header_text=ust_text,  # sağdaki üst panel metni
            header_logo_path=logo_path,  # sağdaki logo önizlemesi
            header_checked=True  # "Üsttekileri mesaja ekle" varsayılan açık
        )

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return  # İptal/çarpı -> hiçbir şey yapma

        secili_numaralar = dlg.secili_alicilar()  # ['+905xx...', ...]
        mesaj_final = dlg.mesaj()  # kullanıcı düzenlediyse son metin
        ust_eklensin = getattr(dlg, "ust_eklensin", True)  # diyalogtan işaret durumu (yoksa True varsay)

        if not secili_numaralar:
            QMessageBox.information(self, "WhatsApp", "Seçili alıcı yok, gönderilmedi.")
            return

        # 6) Gönder (macOS’ta logo’yu görsel olarak da yollamak istersen)
        gorsel_yolu = logo_path if (ust_eklensin and logo_path) else None
        try:
            sonuc = whatsapp.whatsapp_gonder(secili_numaralar, mesaj_final, image_path=gorsel_yolu)
            det = (
                f"Gönderildi: {len(sonuc.get('ok', []))}  |  Başarısız: {len(sonuc.get('fail', []))}\n"
                f"Başarısız Numaralar: {', '.join(sonuc.get('fail', [])) or '-'}"
            )
            QMessageBox.information(self, "WhatsApp", det)
        except Exception as e:
            QMessageBox.critical(self, "WhatsApp Hatası", str(e))

    def _ust_bilgi_paketi(self):
        """
        Ayarlardan üst bilgi metni ve logo yolunu hazırlar.
        Dönüş: (text, logo_path)  — metin boş olabilir, logo Path boş olabilir.
        """
        kurum = (appset.ayar_get('kurum_adi', '') or '').strip()
        kocu = (appset.ayar_get('egitim_kocu', '') or '').strip()
        ilet = (appset.ayar_get('iletisim_satiri', '') or '').strip()
        web = (appset.ayar_get('kurum_web', '') or '').strip()
        logo = (appset.ayar_get('logo_path', '') or '').strip()

        satirlar = []
        if kurum: satirlar.append(kurum)
        if kocu:  satirlar.append(f"Eğitim Koçu: {kocu}")
        if ilet:  satirlar.append(ilet)
        if web:   satirlar.append(web)

        return ("\n".join(satirlar).strip(), logo)

    # ---------------- sol liste yardımcıları ----------------
    def _style_left_list(self):
        """Sol taraftaki QListWidget (self.lstKume) için görsel iyileştirme."""
        lw = self.lstKume
        lw.setAlternatingRowColors(True)
        lw.setSpacing(4)
        lw.setStyleSheet("""
            QListWidget { outline:none; border:1px solid #d9d9d9; background:#fafafa; }
            QListWidget::item { margin:2px; }
            QListWidget::item:selected { background:#e7f0ff; border:1px solid #a7c3ff; margin:1px; }
        """)

    def _populate_kume_list(self, rows):
        self.lstKume.clear()

        for r in rows:
            kid = int(r["id"])
            ver = r["verilis_tarihi"] or "-"
            bit = r["bitis_tarihi"] or "-"
            adet = int(r["adet"] or 0)
            tamam = int(r["tamam"] or 0)

            # yüzde
            yuzde = int(100 * tamam / max(1, adet)) if adet else 0

            # rozet verileri
            akt_say = int(r["aktarilan"] or 0)
            son_aktar = r["son_aktarim"] or ""

            w = KumeListItem(
                num_label=f"#{kid}",
                tarih_label=f"{ver} → {bit}",
                adet_label=f"{adet} kalem",
                percent=yuzde,
                moved=akt_say,  # ✅ rozet sayısı
                last_moved=son_aktar,  # ✅ rozet tooltip tarihi
                parent=self.lstKume
            )

            # --- Rozeti tıklanabilir yap: önce doğrudan clicked varsa bağla,
            # yoksa eventFilter ile tıklamayı yakala (QLabel senaryosu)
            try:
                # Eğer KumeListItem içinde badgeXfer bir ClickLabel ise:
                w.badgeXfer.clicked.connect(lambda kid=kid: self._kume_ac_moved(kid))
            except Exception:
                try:
                    # QLabel ise event filter ile tıklama kazandır
                    flt = _ClickFilter(lambda kid=kid: self._kume_ac_moved(kid))
                    w.badgeXfer.installEventFilter(flt)
                    # GC olmasın diye referansı widget üzerinde tut
                    w._xfer_click_filter = flt
                except Exception:
                    pass

            it = QListWidgetItem(self.lstKume)
            it.setSizeHint(w.sizeHint())
            it.setData(USERROLE, kid)
            self.lstKume.setItemWidget(it, w)

    def _populate_kume_list(self, rows):
        self.lstKume.clear()

        # GC'de kaybolmasın diye filtreleri listede tutalım
        if not hasattr(self, "_xfer_filters"):
            self._xfer_filters = []

        def _safe(row, key, default=None):
            try:
                # sqlite3.Row keys() destekler
                return row[key] if key in row.keys() else default
            except Exception:
                return default

        for r in rows:
            kid = int(_safe(r, "id", 0) or 0)
            ver = _safe(r, "verilis_tarihi", "") or "-"
            bit = _safe(r, "bitis_tarihi", "") or "-"
            adet = int(_safe(r, "adet", 0) or 0)
            tamam = int(_safe(r, "tamam", 0) or 0)

            yuzde = int(100 * tamam / max(1, adet)) if adet else 0

            # rozet verileri (alias yoksa 0/"")
            akt_say = int(_safe(r, "aktarilan", 0) or 0)
            son_aktar = _safe(r, "son_aktarim", "") or ""

            w = KumeListItem(
                num_label=f"#{kid}",
                tarih_label=f"{ver} → {bit}",
                adet_label=f"{adet} kalem",
                percent=yuzde,
                moved=akt_say,
                last_moved=son_aktar,
                parent=self.lstKume
            )

            # --- Rozeti tıklanabilir yap ---
            # 1) KumeListItem içinde _ClickLabel kullanıyorsan 'clicked' sinyali olur:
            bound = False
            try:
                # clicked sinyali varsa, imzaya argümansız bağlan (lambda kid=kid: ...)
                if hasattr(w.badgeXfer, "clicked"):
                    w.badgeXfer.clicked.connect(lambda kid=kid: getattr(self, "_kume_ac_moved", lambda *_: None)(kid))
                    bound = True
            except Exception:
                pass

            # 2) Değilse (QLabel ise) eventFilter ile tıklama kazandır:
            if not bound:
                try:
                    flt = _ClickFilter(lambda kid=kid: getattr(self, "_kume_ac_moved", lambda *_: None)(kid))
                    w.badgeXfer.installEventFilter(flt)
                    self._xfer_filters.append(flt)  # referansı sakla
                except Exception:
                    pass

            # QListWidget'a yerleştir
            it = QListWidgetItem(self.lstKume)
            it.setSizeHint(w.sizeHint())
            it.setData(USERROLE, kid)
            self.lstKume.setItemWidget(it, w)

    def _kume_ac_moved(self, kume_id: int):
        """Seçili kümede yalnızca silmeden aktarılan (aktarildi=1) satırları gösterir."""
        if not kume_id:
            return

        con = db.get_conn()
        rows = con.execute("""
            SELECT id, ders, kitap_ad, konu_ad,
                   COALESCE(saat_dk,0) AS dk,
                   COALESCE(aciklama,'') AS aciklama,
                   COALESCE(aktarildi,0) AS akt,
                   COALESCE(aktarim_tarihi,'') AS akt_tarih
              FROM odev
             WHERE kume_id = ?
               AND COALESCE(aktarildi,0) = 1
             ORDER BY id
        """, (kume_id,)).fetchall()

        with self._block_table_signals():
            self.tab.setRowCount(0)
            for r in rows:
                i = self.tab.rowCount()
                self.tab.insertRow(i)

                # 0: kilitli checkbox (tıklanamaz)
                chk = QTableWidgetItem()
                chk.setFlags(chk.flags() & ~Qt.ItemFlag.ItemIsEnabled)  # disable
                chk.setCheckState(Qt.CheckState.Unchecked)
                self.tab.setItem(i, 0, chk)

                # 1..5: hücreler (id UserRole’de)
                it_d = QTableWidgetItem(r["ders"] or "")
                it_d.setData(USERROLE, int(r["id"]))
                self.tab.setItem(i, 1, it_d)
                self.tab.setItem(i, 2, QTableWidgetItem(r["kitap_ad"] or ""))
                self.tab.setItem(i, 3, QTableWidgetItem(r["konu_ad"] or ""))
                self.tab.setItem(i, 4, QTableWidgetItem(str(int(r["dk"] or 0))))

                # 5: açıklama → “Aktarıldı · tarih”
                acik = "Aktarıldı"
                if r["akt_tarih"]:
                    acik += f" · {r['akt_tarih']}"
                it_ac = QTableWidgetItem(acik)
                # satırı pastel gri/maviye boyayalım ve tıklanamaz yapalım
                it_ac.setFlags(it_ac.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.tab.setItem(i, 5, it_ac)

                # satırın tamamını hafifçe grileştir (okunur kalsın)
                for c in range(6):
                    cell = self.tab.item(i, c)
                    if cell:
                        cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable & ~Qt.ItemFlag.ItemIsEnabled)
                        cell.setBackground(QBrush(QColor("#F3F4F6")))  # pastel gri
                        cell.setForeground(QBrush(QColor("#374151")))  # koyu gri metin

        # Başlık istatistiklerini güncelle
        self._update_header_stats()
        try:
            self.tab.resizeColumnsToContents()
            self.tab.horizontalHeader().setStretchLastSection(True)
        except Exception:
            pass

    # ---------------- filtre yardımcıları ----------------

    def _fill_table(self, rows):
        """rows: SELECT sonuc listesi (odev tablosundan)."""
        try:
            self.tab.blockSignals(True)
        except Exception:
            pass
        self.tab.setRowCount(0)
        for r in rows:
            i = self.tab.rowCount();
            self.tab.insertRow(i)
            # 0: checkbox
            chk = QTableWidgetItem()
            chk.setFlags(chk.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            durum = (r["durum"] or "").lower()
            chk.setCheckState(Qt.CheckState.Checked if durum in ("yapildi", "tamam") else Qt.CheckState.Unchecked)
            self.tab.setItem(i, 0, chk)
            # 1..5
            it_ders = QTableWidgetItem(r["ders"] or "");
            it_ders.setData(USERROLE, int(r["id"]))
            self.tab.setItem(i, 1, it_ders)
            self.tab.setItem(i, 2, QTableWidgetItem(r["kitap_ad"] or ""))
            self.tab.setItem(i, 3, QTableWidgetItem(r["konu_ad"] or ""))
            self.tab.setItem(i, 4, QTableWidgetItem(str(r["saat_dk"] or 0)))
            self.tab.setItem(i, 5, QTableWidgetItem(r["aciklama"] or ""))
        try:
            self.tab.blockSignals(False)
        except Exception:
            pass
        self._hesapla_yuzde()
        self._refresh_filter_sources(rows)

    def _refresh_filter_sources(self, rows):
        """Ders combobox’ını mevcut satırlara göre güncelle (Hepsi + alfabetik)."""
        dersler = sorted({(r["ders"] or "").strip() for r in rows if (r["ders"] or "").strip()})
        cur = self.cboFltDers.currentData()
        self.cboFltDers.blockSignals(True)
        self.cboFltDers.clear()
        self.cboFltDers.addItem("Ders: Hepsi", "")
        for d in dersler:
            self.cboFltDers.addItem(d, d)
        self.cboFltDers.blockSignals(False)
        # eski seçim uygunsa koru
        if cur:
            idx = self.cboFltDers.findData(cur)
            if idx >= 0: self.cboFltDers.setCurrentIndex(idx)

    def _apply_filters(self):
        """Sağ tablodaki görünür satırları filtrele."""
        ders = self.cboFltDers.currentData() or ""
        durum_txt = self.cboFltDurum.currentText()
        want_done = (durum_txt == "Yapıldı")
        want_devam = (durum_txt == "Devam")
        q = (self.txtFltAra.text() or "").strip().lower()

        for i in range(self.tab.rowCount()):
            d = (self.tab.item(i, 1).text() if self.tab.item(i, 1) else "")
            kit = (self.tab.item(i, 2).text() if self.tab.item(i, 2) else "")
            kon = (self.tab.item(i, 3).text() if self.tab.item(i, 3) else "")
            chk = self.tab.item(i, 0)
            is_done = (chk and chk.checkState() == Qt.CheckState.Checked)

            ok = True
            if ders and d != ders: ok = False
            if want_done and not is_done: ok = False
            if want_devam and is_done: ok = False
            if q and (q not in kit.lower() and q not in kon.lower() and q not in d.lower()): ok = False

            self.tab.setRowHidden(i, not ok)

        # Filtrelenen satır sayısını ve yüzdesini filtre çubuğunda göster
        total_rows = self.tab.rowCount()
        vis = sum(1 for i in range(total_rows) if not self.tab.isRowHidden(i))
        done = sum(1 for i in range(total_rows)
                   if not self.tab.isRowHidden(i) and self.tab.item(i, 0) and self.tab.item(i, 0).checkState() == Qt.CheckState.Checked)
        yuz = int(100 * done / max(1, vis)) if vis > 0 else 0
        if hasattr(self, "lblFltCount"):
            if total_rows == 0:
                self.lblFltCount.setText("")
            elif vis < total_rows:
                self.lblFltCount.setText(f"🔍 <b>{vis} / {total_rows}</b> ödev gösteriliyor (%{yuz} tamam)")
            else:
                self.lblFltCount.setText(f"📋 Toplam <b>{total_rows}</b> ödev")

    def _clear_filters(self):
        self.cboFltDers.setCurrentIndex(0)
        self.cboFltDurum.setCurrentIndex(0)
        self.txtFltAra.clear()
        self._apply_filters()

    def _print_current_table_pdf(self):
        """
        Sağdaki mevcut tabloyu print_helper ile yazdırma diyaloguna taşır.
        - Kullanıcı kendi yazıcı/önizleme/başlık/altbilgi ayarlarını yapar
        - Üstte öğrenci/dönem/%tamamlama özet bloğu otomatik eklenir
        - Logo ve kurum bilgisi ayarlardan çekilir
        """
        # Tablo boşsa çık
        if self.tab.rowCount() == 0:
            QMessageBox.information(self, "PDF", "Yazdırılacak satır yok.")
            return

        # 1) Adapter + diyalog
        adapter = _ModelAdapter(self.tab)
        dlg = ListPrintDialog(
            parent=self,
            model_adapter=adapter,
            profile=PrintProfile(app="YKS_LGS_HomeworkManager", key="OdevKontrolListesi"),
            title="Ödev Listesi Yazdır"
        )

        # 2) Varsayılan başlık / logo (ayarlarından)
        try:
            hdr, logo = self._ust_bilgi_paketi()  # (text, logo_path)
        except Exception:
            hdr, logo = ("", "")
        dlg.edt_header.setPlainText(hdr or "Ödev Listesi")
        dlg._header_text = hdr or "Ödev Listesi"
        dlg._logo_path = logo or ""

        # 3) Sayfa özeti: öğrenci adı + dönem + %’ler
        try:
            con = db.get_conn()
            # Seçili küme için özet (yoksa genel)
            kid = self._secili_kume_id()
            if kid:
                dlg.apply_student_summary(con, self.ogr_id, kume_id=kid, position="top")
            else:
                dlg.apply_student_summary(con, self.ogr_id, kume_id=None, position="top")
        except Exception:
            pass
        finally:
            try:
                con.close()
            except Exception:
                pass

        # 4) Diyaloğu aç
        dlg.resize(820, 600)
        dlg.exec()

    def _rowval(self, row, key, default=""):
        try:
            v = row[key]
            return v if v is not None else default
        except Exception:
            return default

    def _tum_odevleri_yukle(self):
        """
        Öğrencinin tüm kümelerindeki ödevleri tek listede gösterir.
        Sol listede seçimden bağımsızdır; sağ tabloyu doldurur, filtreler çalışır.
        """
        con = db.get_conn()
        rows = con.execute("""
            SELECT  d.id,
                    d.ders,
                    d.kitap_ad,
                    d.konu_ad,
                    COALESCE(d.saat_dk, 0)            AS dk,
                    COALESCE(d.aciklama, '')           AS aciklama,
                    LOWER(COALESCE(d.durum, ''))       AS durum,
                    COALESCE(k.verilis_tarihi, '')     AS verilis_tarihi,
                    COALESCE(k.bitis_tarihi, '')       AS bitis_tarihi
            FROM odev d
            JOIN odev_kume k ON k.id = d.kume_id
            WHERE k.ogrenci_id = ?
            ORDER BY k.id DESC, d.id
        """, (self.ogr_id,)).fetchall()

        # tabloyu doldur (mevcut doldurma mantığınla birebir uyumlu alan adları)
        try:
            self.tab.blockSignals(True)
        except Exception:
            pass
        self.tab.setRowCount(0)

        done = 0
        for r in rows:
            i = self.tab.rowCount()
            self.tab.insertRow(i)

            # 0: checkbox
            chk = QTableWidgetItem()
            chk.setFlags(chk.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            is_done = (r["durum"] in ("yapildi", "tamam"))
            chk.setCheckState(Qt.CheckState.Checked if is_done else Qt.CheckState.Unchecked)
            if is_done: done += 1
            self.tab.setItem(i, 0, chk)

            # 1..5: aynı başlık dizilimi
            it_d = QTableWidgetItem(r["ders"] or "")
            it_d.setData(USERROLE, int(r["id"]))
            self.tab.setItem(i, 1, it_d)
            self.tab.setItem(i, 2, QTableWidgetItem(r["kitap_ad"] or ""))
            self.tab.setItem(i, 3, QTableWidgetItem(r["konu_ad"] or ""))
            self.tab.setItem(i, 4, QTableWidgetItem(str(int(r["dk"] or 0))))
            # açıklamaya dönem bilgisini ufakçe eklemek istersen (isteğe bağlı):
            acik = r["aciklama"] or ""
            if r["verilis_tarihi"] or r["bitis_tarihi"]:
                acik = f"{acik}   [Dönem: {r['verilis_tarihi'] or '-'} → {r['bitis_tarihi'] or '-'}]".strip()
            self.tab.setItem(i, 5, QTableWidgetItem(acik))

        try:
            self.tab.blockSignals(False)
            self.tab.resizeColumnsToContents()
            self.tab.horizontalHeader().setStretchLastSection(True)
        except Exception:
            pass

        # yüzde ve filtre kaynakları
        yuz = int(100 * done / max(1, len(rows))) if rows else 0
        self.lblYuzde.setText(f"%{yuz}")
        self._refresh_filter_sources(rows)
        self._apply_filters()

    #s----sağ tık menüsü ekle
    def _on_kume_context_menu(self, pos):
        kume_id = self._secili_kume_id()
        if not kume_id:
            return

        from PyQt6.QtWidgets import QMenu
        m = QMenu(self)
        m.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                background-color: transparent;
                padding: 6px 24px 6px 12px;
                border-radius: 4px;
                color: #334155;
                font-family: 'Segoe UI', sans-serif;
            }
            QMenu::item:selected {
                background-color: #f1f5f9;
                color: #1e293b;
            }
            QMenu::separator {
                height: 1px;
                background-color: #e2e8f0;
                margin: 4px 6px; 
            }
        """)

        m.addAction("Küme Detaylarını Gör", lambda: self._show_kume_details(kume_id))
        m.addSeparator()

        m.addAction("Bitiş tarihini düzenle…", lambda: self._edit_kume_bitis_tarihi(kume_id))
        m.addAction("Bitiş tarihini temizle", lambda: self._clear_kume_bitis_tarihi(kume_id))

        sub = m.addMenu("Bitiş tarihini uzat")
        # Sub-menu needs style too usually inherits but explicit is safe
#        sub.setStyleSheet(m.styleSheet()) 
        sub.addAction("+1 Gün", lambda: self._shift_kume_bitis(kume_id, days=1))
        sub.addAction("+3 Gün", lambda: self._shift_kume_bitis(kume_id, days=3))
        sub.addAction("+1 Hafta", lambda: self._shift_kume_bitis(kume_id, days=7))

        m.addSeparator()
        m.addAction("WhatsApp’tan Gönder (yalnız bu küme)", lambda: self._wp_gonder_tek_kume(kume_id))
        m.addAction("Küme Raporunu PDF’ye Yazdır", lambda: self._print_kume_pdf(kume_id))
        m.addSeparator()
        m.addAction("Kümedeki Tüm Ödevleri Sil (Kümeyi Koru)", lambda: self._clear_kume_tasks(kume_id))

        m.exec(self.lstKume.mapToGlobal(pos))

    # --- Yardımcı: solda belirli bir kümeyi seç ---
    def _select_kume_in_list(self, kume_id: int):
        for i in range(self.lstKume.count()):
            it = self.lstKume.item(i)
            try:
                if int(it.data(USERROLE)) == int(kume_id):
                    self.lstKume.setCurrentRow(i)
                    return
            except Exception:
                pass

    # --- 1) Küme detayları ---
    def _show_kume_details(self, kume_id: int):
        con = db.get_conn()
        info = con.execute("""
            SELECT  COALESCE(verilis_tarihi,'') AS ver, COALESCE(bitis_tarihi,'') AS bit
            FROM odev_kume WHERE id=?""", (kume_id,)).fetchone()

        adet = con.execute("SELECT COUNT(*) FROM odev WHERE kume_id=?", (kume_id,)).fetchone()[0]
        tamam = con.execute("""
            SELECT COUNT(*) FROM odev
            WHERE kume_id=? AND LOWER(COALESCE(durum,'')) IN ('yapildi','tamam')
        """, (kume_id,)).fetchone()[0]

        dersler = con.execute("""
            SELECT ders, COUNT(*) AS n
            FROM odev WHERE kume_id=? GROUP BY ders ORDER BY ders
        """, (kume_id,)).fetchall()

        satirlar = [f"Küme #{kume_id}",
                    f"Veriliş: {info['ver'] or '-'}",
                    f"Bitiş:   {info['bit'] or '-'}",
                    f"Toplam ödev: {adet}",
                    f"Tamamlanan: {tamam}",
                    ""]
        if dersler:
            satirlar.append("Ders dağılımı:")
            for r in dersler:
                satirlar.append(f"  • {r['ders']} : {r['n']}")

        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Küme Detayları", "\n".join(satirlar))

    # --- 2) Bitiş tarihini gün sayısı kadar ötele ---
    def _shift_kume_bitis(self, kume_id: int, days: int = 1):
        import datetime as _dt
        con = db.get_conn()
        cur = con.cursor()

        row = cur.execute("SELECT bitis_tarihi FROM odev_kume WHERE id=?", (kume_id,)).fetchone()
        old = (row["bitis_tarihi"] or "").strip() if row else ""

        def _fmt(d: _dt.date) -> str:
            return d.strftime("%Y-%m-%d")

        if old:
            try:
                base = _dt.datetime.strptime(old, "%Y-%m-%d").date()
            except Exception:
                base = _dt.date.today()
        else:
            base = _dt.date.today()

        yeni = base + _dt.timedelta(days=int(days))
        cur.execute("UPDATE odev_kume SET bitis_tarihi=? WHERE id=?", (_fmt(yeni), kume_id))
        con.commit()

        # UI yenile
        self._yukle_kumeler()
        self._select_kume_in_list(kume_id)
        self._kume_ac(kume_id)

    # --- 3) WhatsApp: yalnız bu kümeyi gönder ---
    def _wp_gonder_tek_kume(self, kume_id: int):
        # Mevcut yardımcılarını tekrar kullanıyoruz
        adsoy, nums = self._telefon_listesi()
        if not nums:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "WhatsApp", "Kayıtlı telefon numarası bulunamadı.")
            return

        baslik = f"{adsoy} - Ödev Özeti"
        metin = self._mesaj_olustur([kume_id], baslik)
        if not metin:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "WhatsApp", "Bu kümeye ait ödev bulunamadı.")
            return

        # Üst bilgi + logo
        ust_text, logo_path = self._ust_bilgi_paketi()

        # Diyalog (Ödev Takip Formu ile aynı arayüz)
        dlg = WhatsAppGonderDialog(
            alicilar=[("Veli/Öğrenci", n) for n in nums],
            mesaj=metin,
            parent=self,
            header_text=ust_text,
            header_logo_path=logo_path,
            header_checked=True
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        secili = dlg.secili_alicilar()
        mesaj_final = dlg.mesaj()
        ust_eklensin = getattr(dlg, "ust_eklensin", True)
        gorsel_yolu = logo_path if (ust_eklensin and logo_path) else None

        try:
            sonuc = whatsapp.whatsapp_gonder(secili, mesaj_final, image_path=gorsel_yolu)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "WhatsApp",
                f"Gönderildi: {len(sonuc.get('ok', []))}  |  Başarısız: {len(sonuc.get('fail', []))}"
            )
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "WhatsApp Hatası", str(e))

    # --- 4) PDF: yalnız bu küme ---
    def _print_kume_pdf(self, kume_id: int):
        # mevcut tabloyu bozmadan kısa yol: kümeyi aç → yazdır → eski seçimi geri al
        prev = self._secili_kume_id()
        self._select_kume_in_list(kume_id)
        self._kume_ac(kume_id)
        try:
            self._print_current_table_pdf()
        finally:
            if prev and prev != kume_id:
                self._select_kume_in_list(prev)
                self._kume_ac(prev)

    # --- 5) Kümedeki tüm ödevleri sil (kümeyi koru) ---
    def _clear_kume_tasks(self, kume_id: int):
        from PyQt6.QtWidgets import QMessageBox
        if QMessageBox.question(
                self, "İşlem Onayı",
                "Bu kümedeki TÜM ödevler silinsin mi? (Küme kaydı korunur)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return

        con = db.get_conn()
        cur = con.cursor()
        try:
            cur.execute("DELETE FROM odev WHERE kume_id=?", (kume_id,))
            con.commit()
        except Exception:
            try:
                con.rollback()
            except Exception:
                pass
            QMessageBox.critical(self, "Hata", "Ödevler silinemedi.")
            return

        # UI yenile
        self._yukle_kumeler()
        self._select_kume_in_list(kume_id)
        self._kume_ac(kume_id)

    # --- Bitiş tarihini düzenle ---
    def _edit_kume_bitis_tarihi(self, kume_id: int):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDateEdit, QDialogButtonBox
        from PyQt6.QtCore import QDate

        # Mevcut bitiş tarihini al
        con = db.get_conn()
        row = con.execute(
            "SELECT COALESCE(bitis_tarihi,'') AS bt FROM odev_kume WHERE id=?",
            (kume_id,)
        ).fetchone()
        old_txt = (row["bt"] or "").strip() if row else ""

        # Küçük diyalog
        dlg = QDialog(self)
        dlg.setWindowTitle("Bitiş tarihini düzenle")
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(f"Küme #{kume_id} için bitiş tarihi:"))

        de = QDateEdit()
        de.setCalendarPopup(True)
        # yyyy-MM-dd formatını QDate'e çevir
        if old_txt:
            qd = QDate.fromString(old_txt, "yyyy-MM-dd")
            if not qd.isValid():
                qd = QDate.currentDate()
        else:
            qd = QDate.currentDate()
        de.setDate(qd)
        lay.addWidget(de)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        lay.addWidget(bb)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        new_txt = de.date().toString("yyyy-MM-dd")

        # DB güncelle
        cur = con.cursor()
        cur.execute("UPDATE odev_kume SET bitis_tarihi=? WHERE id=?", (new_txt, kume_id))
        con.commit()

        # UI yenile
        self._yukle_kumeler()
        self._select_kume_in_list(kume_id)
        self._kume_ac(kume_id)

    # --- Bitiş tarihini temizle (NULL yap) ---
    def _clear_kume_bitis_tarihi(self, kume_id: int):
        from PyQt6.QtWidgets import QMessageBox
        if QMessageBox.question(
                self, "Bitiş Tarihini Temizle",
                "Bu kümenin bitiş tarihini temizlemek istiyor musunuz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return

        con = db.get_conn()
        cur = con.cursor()
        cur.execute("UPDATE odev_kume SET bitis_tarihi=NULL WHERE id=?", (kume_id,))
        con.commit()

        # UI yenile
        self._yukle_kumeler()
        self._select_kume_in_list(kume_id)
        self._kume_ac(kume_id)
    #f---

#--------verilen ödev detayları-----

    # === Sağ tablo görsel iyileştirme ===
    def _setup_right_table_styles(self):
        t = self.tab
        t.setAlternatingRowColors(True)
        t.setShowGrid(True)
        t.verticalHeader().setVisible(False)
        t.verticalHeader().setDefaultSectionSize(30)
        t.horizontalHeader().setStretchLastSection(True)
        t.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        t.setColumnWidth(0, 64)
        try:
            t.setItemDelegateForColumn(0, _YapildiColumnDelegate(t))
        except Exception:
            pass
        t.setStyleSheet("""
            QHeaderView::section {
                background: #f8fafc;
                color: #475569;
                font-weight: 700;
                font-size: 11px;
                border: 0;
                border-bottom: 2px solid #e2e8f0;
                padding: 8px 10px;
            }
            QTableWidget, QTableView {
                background-color: #ffffff;
                gridline-color: #f1f5f9;
                alternate-background-color: #f8fafc;
                selection-background-color: #eff6ff;
                selection-color: #1e293b;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
            QTableWidget::item, QTableView::item {
                padding: 6px 8px;
            }
            QTableView::item:hover {
                background: #f1f5f9;
            }
            QTableWidget::indicator, QTableView::indicator {
                width: 18px;
                height: 18px;
                border: 1.5px solid #94a3b8;
                border-radius: 3.5px;
                background-color: #ffffff;
            }
            QTableWidget::indicator:hover, QTableView::indicator:hover {
                border-color: #2563eb;
            }
            QTableWidget::indicator:checked, QTableView::indicator:checked {
                background-color: #16a34a;
                border: 1.5px solid #15803d;
                image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 16 16'><path fill='none' stroke='white' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round' d='M3.2 8.2l3.4 3.4L13 4.2'/></svg>");
            }
        """)

    def _refresh_right_table_styles(self):
        """Yapıldı satırlarını renklendir (güvenli, sade sürüm)"""
        # --- KORUMA: tablo yoksa veya silindiyse çalıştırma
        t = getattr(self, "tab", None)
        if t is None:
            return

        # PyQt6'da sip her zaman importlu olmayabilir → güvenli import
        try:
            import sip
            if sip.isdeleted(t):
                return
        except Exception:
            pass

        # --- Stil renkleri ---
        done_bg = QColor("#ecfdf5")  # açık yeşil arka plan
        done_fg = QColor("#065f46")  # koyu yeşil yazı
        normal_fg = QColor("#0f172a")  # normal yazı

        try:
            for r in range(t.rowCount()):
                chk = t.item(r, 0)
                is_done = bool(chk and chk.checkState() == Qt.CheckState.Checked)
                for c in range(t.columnCount()):
                    it = t.item(r, c)
                    if not it:
                        continue
                    if is_done:
                        it.setBackground(QBrush(done_bg))
                        it.setForeground(QBrush(done_fg))
                    else:
                        it.setBackground(QBrush(Qt.GlobalColor.transparent))
                        it.setForeground(QBrush(normal_fg))
        except RuntimeError:
            # tablo silindiyse veya kapatılırken çağrıldıysa sessizce çık
            return

    # ---------------- Sağ Tablo Olayları (Checkbox Click) ----------------
    def _chk_cell_click(self, row, col):
        """0. kolondaki (checkbox) hücrenin herhangi bir yerine tıklandığında değişimi tetikle."""
        if col == 0:
            import time
            # Eğer son 200ms içinde zaten native bir değişim olduysa, biz müdahale etmeyelim (double-toggle önlemi)
            last = getattr(self, "_last_chk_time", 0)
            if time.time() - last < 0.2:
                return

            it = self.tab.item(row, 0)
            if it and (it.flags() & Qt.ItemFlag.ItemIsEnabled):
                # Manuel toggle
                curr = it.checkState()
                new_state = Qt.CheckState.Unchecked if curr == Qt.CheckState.Checked else Qt.CheckState.Checked
                it.setCheckState(new_state)

    def _on_table_item_changed(self, item):
        # Native değişim zamanını kaydet (anti-bounce için)
        if item.column() == 0:
            import time
            self._last_chk_time = time.time()
            
        try:
            self._hesapla_yuzde()
        finally:
            self._refresh_right_table_styles()

    #s  Tamamlanma: %  sini bar olarak göster
    # --- Eski çağrılar için köprü: _set_header_stats(done, total) ---
    def _set_header_stats(self, done: int, total: int) -> None:
        """
        Eski kodun çağırdığı metot. Varsa _update_header_stats'i kullanır.
        Yoksa hızlı bir metin barıyla yalnızca yüzdeyi yazar.
        """
        try:
            # Yeni, tam kapsamlı başlık istatistiği fonksiyonunuz varsa onu çağır.
            if hasattr(self, "_update_header_stats"):
                self._update_header_stats()
                return
        except Exception:
            pass

        # Yalın geri dönüş (sadece yüzde barı)
        try:
            total = max(1, int(total or 0))
            done = max(0, int(done or 0))
            pct = int(100 * done / total)

            bar_len = 16
            filled = max(0, min(bar_len, round(pct * bar_len / 100)))
            bar = "▰" * filled + "▱" * (bar_len - filled)

            self.lblYuzde.setText(f"{bar}  %{pct}")
            self.lblYuzde.setToolTip(f"Tamamlanma: %{pct}  (done={done}, total={total})")
        except Exception:
            # hiçbir şey yapma; etiket yoksa sessizce geç
            pass
    def _update_header_stats(self):
        """
        Üst çubuk (lblYuzde):
          - GENEL tamamlama yüzdesi => bar (tüm ödevlerde: yapılmış + aktarılmış)
          - Aktif tamamlama % (aktarılmamışlarda ilerleme)
          - Kısa istatistikler: Küme, Toplam Ödev, Tamamlanan, Bekleyen,
                                Aktarılan, Ortalama Süre(dk), Ders çeşitliliği
        Tek fonksiyon; başka yere dokunmaya gerek yok.
        """
        from PyQt6.QtCore import Qt
        from datetime import datetime

        # --- 0) Çift "Tamamlanma" başlığını temizle (bir defalık)
        if not hasattr(self, "_header_cleaned"):
            try:
                for w in self.findChildren(QLabel):
                    if w is not getattr(self, "lblYuzde", None) and "Tamamlanma" in (w.text() or ""):
                        w.setVisible(False)  # ✨ ikinci başlığı gizle
            except Exception:
                pass
            self._header_cleaned = True

        con = db.get_conn()

        # --- 1) GENEL istatistikler (tüm ödevler)
        total_all, done_all, bekleyen_all, aktarilan, sum_dk, avg_dk, ders_distinct = con.execute("""
            SELECT
                COUNT(*) AS total_all,
                -- SADECE gerçekten bitenler
                SUM(CASE
                        WHEN TRIM(LOWER(COALESCE(d.durum,''))) IN ('yapildi','tamam')
                    THEN 1 ELSE 0
                END) AS done_all,
                -- Bekleyenler: bitmemiş ve silinmemiş (aktarılmışlar da burada kalsın istersen)
                SUM(CASE
                        WHEN TRIM(LOWER(COALESCE(d.durum,''))) NOT IN ('yapildi','tamam')
                             AND COALESCE(d.silindi,0)=0
                    THEN 1 ELSE 0
                END) AS bekleyen_all,
                -- Kaç tanesi aktarılmış bilgi olarak dursun
                SUM(CASE WHEN COALESCE(d.aktarildi,0)=1 THEN 1 ELSE 0 END) AS aktarilan,
                SUM(COALESCE(d.saat_dk,0)) AS sum_dk,
                AVG(NULLIF(d.saat_dk,0)) AS avg_dk,
                COUNT(DISTINCT TRIM(COALESCE(d.ders,''))) AS ders_distinct
            FROM odev d
            JOIN odev_kume k ON k.id = d.kume_id
            WHERE k.ogrenci_id = ? AND COALESCE(d.silindi,0)=0
        """, (self.ogr_id,)).fetchone()

        total_all = int(total_all or 0)
        done_all = int(done_all or 0)
        aktarilan = int(aktarilan or 0)
        sum_dk = int(sum_dk or 0)
        avg_dk = int(round(avg_dk or 0))
        ders_distinct = int(ders_distinct or 0)
        bekleyen_all = max(0, total_all - done_all)

        # --- 2) AKTİF istatistik (aktarılmamışlarda ilerleme)
        total_aktif, done_aktif = con.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE
                        WHEN TRIM(LOWER(COALESCE(d.durum,''))) IN ('yapildi','tamam')
                    THEN 1 ELSE 0
                END) AS done
            FROM odev d
            JOIN odev_kume k ON k.id = d.kume_id
            WHERE k.ogrenci_id = ? AND COALESCE(d.aktarildi,0)=0
        """, (self.ogr_id,)).fetchone()
        total_aktif = int(total_aktif or 0)
        done_aktif = int(done_aktif or 0)

        # --- 3) Küme sayısı
        kume_say = con.execute(
            "SELECT COUNT(*) FROM odev_kume WHERE ogrenci_id=?", (self.ogr_id,)
        ).fetchone()[0] or 0
        kume_say = int(kume_say)

        # --- 4) Yüzdeler
        pct_genel = int(100 * done_all / max(1, total_all)) if total_all else 0
        pct_aktif = int(100 * done_aktif / max(1, total_aktif)) if total_aktif else 0

        # --- 5) Bar (GENEL % için)
        bar_len = 16
        filled = max(0, min(bar_len, round(pct_genel * bar_len / 100)))
        col_fill = "#10B981" if pct_genel >= 80 else ("#3B82F6" if pct_genel >= 50 else ("#F59E0B" if pct_genel >= 25 else "#EF4444"))
        col_empty = "#E2E8F0"
        bar_html = (
                "".join(f"<span style='color:{col_fill}; font-size:12px;'>■</span>" for _ in range(filled)) +
                "".join(f"<span style='color:{col_empty}; font-size:12px;'>■</span>" for _ in range(bar_len - filled))
        )

        # Süre metni (Ø00 dk hatası düzeltildi)
        if avg_dk > 0:
            sure_badge = f"⏱️ Ort. <b>{avg_dk} dk</b>"
        elif sum_dk > 0:
            sure_badge = f"⏱️ Top. <b>{sum_dk} dk</b>"
        else:
            sure_badge = "⏱️ <b>- dk</b>"

        # --- 6) Metin: profesyonel mini-panel (Renkli Badgeler / Pill Rozetler)
        html = (
            "<table border='0' cellspacing='3' cellpadding='2' style='vertical-align:middle; font-size:12px; font-family:\"Segoe UI\", sans-serif;'>"
            "<tr>"
            f"<td style='padding-right:2px;'><b>🎯 İlerleme:</b></td>"
            f"<td>{bar_html}</td>"
            f"<td style='padding-right:6px;'><b style='color:{col_fill}; font-size:13px;'>%{pct_genel}</b></td>"
            "<td style='color:#cbd5e1;'>|</td>"
            f"<td style='background:#fef3c7; color:#92400e; padding:3px 7px; border-radius:4px;'><b>⚡ %{pct_aktif}</b> Aktif</td>"
            f"<td style='background:#ede9fe; color:#5b21b6; padding:3px 7px; border-radius:4px;'><b>📦 {kume_say}</b> Küme</td>"
            f"<td style='background:#eff6ff; color:#1d4ed8; padding:3px 7px; border-radius:4px;'><b>📚 {total_all}</b> Ödev</td>"
            f"<td style='background:#ecfdf5; color:#065f46; padding:3px 7px; border-radius:4px;'><b>✅ {done_all}</b> Biten</td>"
            f"<td style='background:#fff1f2; color:#991b1b; padding:3px 7px; border-radius:4px;'><b>⏳ {bekleyen_all}</b> Kalan</td>"
            f"<td style='background:#f5f3ff; color:#6d28d9; padding:3px 7px; border-radius:4px;'><b>⬆️ {aktarilan}</b> Aktarılan</td>"
            f"<td style='background:#f0fdfa; color:#0f766e; padding:3px 7px; border-radius:4px;'>{sure_badge}</td>"
            f"<td style='background:#f8fafc; color:#334155; padding:3px 7px; border-radius:4px;'><b>📘 {ders_distinct}</b> Ders</td>"
            "</tr>"
            "</table>"
        )

        self.lblYuzde.setTextFormat(Qt.TextFormat.RichText)
        self.lblYuzde.setText(html)
        self.lblYuzde.setToolTip(
            "GENEL Tamamlama: %{0}\nAktif Tamamlama: %{1}\n"
            "Küme: {2}\nToplam ödev: {3}\nTamamlanan: {4}\nBekleyen: {5}\nAktarılan: {6}\n"
            "Toplam süre: {7} dk, Ortalama süre: {8} dk\nDers çeşitliliği: {9}".format(
                pct_genel, pct_aktif, kume_say, total_all, done_all, bekleyen_all,
                aktarilan, sum_dk, avg_dk, ders_distinct
            )
        )

        #s--
        # --- Ders dağılımı tooltip (renkli + mini barlar, tek fonksiyon)
        try:
            rows = con.execute("""
                SELECT TRIM(COALESCE(d.ders,'')) AS ders, COUNT(*) AS c
                FROM odev d
                JOIN odev_kume k ON k.id = d.kume_id
                WHERE k.ogrenci_id = ?
                GROUP BY TRIM(COALESCE(d.ders,''))
                HAVING COUNT(*) > 0
                ORDER BY c DESC
            """, (self.ogr_id,)).fetchall()
        except Exception:
            rows = []

        total = sum(int(r[1] or 0) for r in rows) or 1

        # Palet (uyumlu, canlı renkler)
        palette = ["#7C3AED", "#3B82F6", "#22C55E", "#F59E0B",
                   "#EF4444", "#06B6D4", "#A3E635", "#14B8A6"]

        # En çok 7 ders + "Diğer"
        items, others = [], 0
        for i, (ders, c) in enumerate(rows):
            if i < 7:
                items.append((str(ders or "—"), int(c or 0)))
            else:
                others += int(c or 0)
        if others > 0:
            items.append(("Diğer", others))

        # HTML tooltip
        parts = []
        parts.append("<html>")
        parts.append(
            "<div style='font-family:-apple-system,Segoe UI,Roboto,Ubuntu,Arial;"
            "font-size:12px;color:#111;background:#fff;'>"
            "<div style='font-weight:700;margin-bottom:6px;'>📊 Derse göre ödev dağılımı</div>"
        )

        # küçük özet
        parts.append(
            f"<div style='color:#6b7280;margin-bottom:6px;'>Toplam: <b>{total}</b> ödev</div>"
        )

        # satır satır: dot + ders + yüzde + (adet) + mini bar
        for i, (ders, c) in enumerate(items):
            pct = int(round(100 * c / total))
            col = palette[i % len(palette)]
            # satır
            parts.append(
                "<div style='display:flex;align-items:center;gap:8px;margin:4px 0;'>"
                f"<span style='display:inline-block;width:10px;height:10px;"
                f"background:{col};border-radius:50%;flex:0 0 auto;'></span>"
                f"<span style='min-width:90px;font-weight:600;color:#111;'>{ders}</span>"
                f"<span style='color:#111;font-variant-numeric:tabular-nums;'>%{pct}</span>"
                f"<span style='color:#6b7280;'>&nbsp;({c})</span>"
                "</div>"
            )
            # mini bar
            parts.append(
                "<div style='width:200px;height:6px;border-radius:4px;background:#E5E7EB;overflow:hidden;"
                "margin:2px 0 8px 18px;'>"
                f"<div style='height:100%;width:{pct}%;background:{col};'></div>"
                "</div>"
            )

        # minik not
        parts.append(
            "<div style='color:#9ca3af;margin-top:4px;'>İpucu: Yüzdeler bütün ödevler üzerinden hesaplanır.</div>")
        parts.append("</div></html>")

        self.lblYuzde.setToolTip("".join(parts))
        #f--











