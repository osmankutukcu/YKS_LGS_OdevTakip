# -*- coding: utf-8 -*-
"""Haftalık Rozetler & Liderlik Paneli (Gamification).

Öğrenci gizliliğini (KVKK) korumak için gerçek çocuk fotoğrafları KULLANILMAZ.
Bunun yerine şık monogram harf avatarları (örn: ZK, AT, ES), madalyalar
(🥇, 🥈, 🥉), rozet etiketleri ve başarı puanları kullanılır.
"""
from __future__ import annotations

import hashlib
import re
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QPushButton, QVBoxLayout, QWidget,
)

from ui.theme import readable_text, register_theme_listener
from ui.theme_tokens_v37 import semantic_palette
from ui.theme_visual_tokens_v40 import accessible_gradient


def _initials(name: str) -> str:
    """İsimden 2 harfli büyük monogram üretir (örn: 'Zeynep Kaya' -> 'ZK')."""
    parts = [p.strip() for p in (name or "").split() if p.strip()]
    if not parts:
        return "ÖĞ"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return f"{parts[0][0]}{parts[-1][0]}".upper()


_AVATAR_PALETTE = [
    ("#4f46e5", "#3730a3"),  # Indigo
    ("#7c3aed", "#5b21b6"),  # Violet
    ("#059669", "#047857"),  # Emerald
    ("#0891b2", "#0e7490"),  # Cyan
    ("#d97706", "#b45309"),  # Amber
    ("#db2777", "#9d174d"),  # Rose
    ("#2563eb", "#1d4ed8"),  # Royal Blue
]


def _avatar_colors(name: str) -> tuple[str, str]:
    idx = int(hashlib.md5((name or "Öğrenci").encode("utf-8")).hexdigest(), 16) % len(_AVATAR_PALETTE)
    return _AVATAR_PALETTE[idx]


class GamificationWidget(QFrame):
    """
    Haftalık Rozetler & Liderlik Panosu:
    Haftalık Performans Trendi grafiğinin yanında yatay olarak yer alır (Tek Ekran Tasarımı).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_stats = {}
        self.setObjectName("GamificationWidget")
        self.setFixedHeight(215)  # WeeklyTrendWidget ile tam eşleşen yükseklik
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 18))
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        # 1. Başlık Satırı
        header_row = QHBoxLayout()
        header_row.setSpacing(6)

        self.lbl_title = QLabel("🏆 Haftalık Rozetler & Liderlik")
        self.lbl_title.setStyleSheet("font-size: 14px; font-weight: 800; color: #0f172a; border: none; background: transparent;")
        header_row.addWidget(self.lbl_title)

        header_row.addStretch()

        self.lbl_subtitle = QLabel("Haftanın Öne Çıkanları")
        self.lbl_subtitle.setStyleSheet("font-size: 11px; font-weight: 600; color: #64748b; border: none; background: transparent;")
        header_row.addWidget(self.lbl_subtitle)

        layout.addLayout(header_row)

        # 2. Liderlik Listesi Alanı
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(4)
        layout.addLayout(self.rows_layout)

        # 3. Alt Kritik Uyarı / İpucu Satırı
        self.footer_frame = QFrame()
        self.footer_frame.setObjectName("LeaderboardFooter")
        self.footer_frame.setFixedHeight(26)
        f_lay = QHBoxLayout(self.footer_frame)
        f_lay.setContentsMargins(8, 2, 8, 2)
        f_lay.setSpacing(6)

        self.lbl_footer_icon = QLabel("💡")
        self.lbl_footer_icon.setStyleSheet("font-size: 11px; border: none; background: transparent;")
        f_lay.addWidget(self.lbl_footer_icon)

        self.lbl_footer_text = QLabel("Haftalık hedef: Düzenli takip ile başarı artar.")
        self.lbl_footer_text.setStyleSheet("font-size: 10px; font-weight: 600; color: #475569; border: none; background: transparent;")
        f_lay.addWidget(self.lbl_footer_text, 1)

        layout.addWidget(self.footer_frame)

        # Başlangıçta boş veya örnek verileri yükle
        self._render_leaderboard([])

        register_theme_listener(self)
        self._on_theme_changed()

    def _on_theme_changed(self):
        c = semantic_palette()
        is_dark = c.get("dark", False)
        bg = c["surface"]
        fg = c["surface_fg"]
        border = c["border"]

        self.setStyleSheet(f"""
            QFrame#GamificationWidget {{
                background-color: {bg};
                border-radius: 14px;
                border: 1px solid {border};
            }}
        """)
        self.lbl_title.setStyleSheet(f"font-size: 14px; font-weight: 800; color: {fg}; border: none; background: transparent;")
        self.lbl_subtitle.setStyleSheet(f"font-size: 11px; font-weight: 600; color: #94a3b8 if is_dark else #64748b; border: none; background: transparent;")

        footer_bg = "#2a1c22" if is_dark else "#f1f5f9"
        footer_border = "#4c1d29" if is_dark else "#e2e8f0"
        footer_fg = "#fecdd3" if is_dark else "#475569"
        self.footer_frame.setStyleSheet(f"""
            QFrame#LeaderboardFooter {{
                background: {footer_bg};
                border: 1px solid {footer_border};
                border-radius: 6px;
            }}
        """)
        self.lbl_footer_text.setStyleSheet(f"font-size: 10px; font-weight: 600; color: {footer_fg}; border: none; background: transparent;")

        # Mevcut verilerle satırları tekrar çiz
        if self._last_stats:
            self.refresh_badges(self._last_stats)

    def refresh_badges(self, stats: dict):
        """Dashboard snapshot'ından gelen verilerle liderlik tablosunu yeniler."""
        self._last_stats = dict(stats or {})

        leaderboard_data = self._last_stats.get("leaderboard") or []
        top_worker = self._last_stats.get("top_worker")
        top_ratio = self._last_stats.get("top_ratio")
        alerts = self._last_stats.get("alerts") or []

        # Eğer leaderboard listesi snapshot'ta varsa onu kullan
        entries = []
        if leaderboard_data:
            for item in leaderboard_data[:3]:
                entries.append({
                    "name": item.get("name", "Öğrenci"),
                    "done": item.get("done", 0),
                    "assigned": item.get("assigned", 0),
                    "ratio": item.get("ratio", 0),
                })
        elif top_worker or top_ratio:
            # Alternatif olarak top_worker ve top_ratio'yu ekle
            if top_worker and top_worker.get("val", 0) > 0:
                entries.append({
                    "name": top_worker.get("name", "Öğrenci"),
                    "done": top_worker.get("val", 0),
                    "assigned": top_worker.get("val", 0),
                    "ratio": 100,
                })
            if top_ratio and top_ratio.get("val", 0) > 0:
                if not entries or entries[0]["name"] != top_ratio.get("name"):
                    entries.append({
                        "name": top_ratio.get("name", "Öğrenci"),
                        "done": 10,
                        "assigned": 10,
                        "ratio": top_ratio.get("val", 0),
                    })

        self._render_leaderboard(entries)

        # Alt Uyarı / İpucu Alanını Güncelle
        if alerts:
            first_alert = alerts[0]
            txt = first_alert.get("text", "")
            self.lbl_footer_icon.setText("⚡")
            self.lbl_footer_text.setText(f"Kritik: {txt}")
        else:
            self.lbl_footer_icon.setText("💡")
            self.lbl_footer_text.setText("Haftalık hedef: Düzenli takip ile başarı %40 artar.")

    def _render_leaderboard(self, entries: list[dict]):
        # Mevcut satırları temizle
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Varsayılan şık modeller (Eğer DB'de henüz 3 öğrenci yoksa gösterim amacıyla tamamla)
        defaults = [
            {"name": "Zeynep K.", "done": 48, "ratio": 98, "badge": "🏆 Zirve (%98)", "preview": True},
            {"name": "Ahmet T.", "done": 42, "ratio": 92, "badge": "⚡ Seri (6 Gün)", "preview": True},
            {"name": "Elif S.", "done": 39, "ratio": 88, "badge": "📚 Canavar", "preview": True},
        ]

        ranks_meta = [
            {"medal": "🥇", "bg": "#fef9c3", "border": "#fde047", "fg": "#854d0e", "badge": "🏆 Zirve"},
            {"medal": "🥈", "bg": "#f1f5f9", "border": "#cbd5e1", "fg": "#334155", "badge": "⚡ Seri"},
            {"medal": "🥉", "bg": "#ffedd5", "border": "#fed7aa", "fg": "#9a3412", "badge": "📚 Canavar"},
        ]

        final_rows = []
        for i in range(3):
            if i < len(entries):
                e = entries[i]
                ratio = e.get("ratio", 90)
                badge_title = f"{ranks_meta[i]['badge']} (%{ratio})"
                final_rows.append({
                    "name": e.get("name", "Öğrenci"),
                    "done": e.get("done", 0),
                    "ratio": ratio,
                    "badge": badge_title,
                    "preview": False,
                })
            else:
                final_rows.append(defaults[i])

        c = semantic_palette()
        is_dark = c.get("dark", False)

        for i, row_data in enumerate(final_rows):
            meta = ranks_meta[i]
            row_frame = QFrame()
            row_frame.setCursor(Qt.CursorShape.PointingHandCursor)
            row_frame.setFixedHeight(38)

            row_bg = "#1e293b" if is_dark else "#ffffff"
            row_border = "#334155" if is_dark else "#f1f5f9"
            hover_border = "#38bdf8" if is_dark else "#93c5fd"

            row_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {row_bg};
                    border: 1px solid {row_border};
                    border-radius: 8px;
                }}
                QFrame:hover {{
                    border-color: {hover_border};
                    background-color: {"#26334d" if is_dark else "#f8fafc"};
                }}
            """)

            h = QHBoxLayout(row_frame)
            h.setContentsMargins(8, 4, 10, 4)
            h.setSpacing(8)

            # 1. Madalya Simgesi
            lbl_medal = QLabel(meta["medal"])
            lbl_medal.setStyleSheet("font-size: 16px; border: none; background: transparent;")
            lbl_medal.setFixedWidth(22)
            lbl_medal.setAlignment(Qt.AlignmentFlag.AlignCenter)
            h.addWidget(lbl_medal)

            # 2. Monogram Harf Avatarı (Çocuk resmi yerine şık, güvenli ve KVKK uyumlu)
            c1, c2 = _avatar_colors(row_data["name"])
            lbl_avatar = QLabel(_initials(row_data["name"]))
            lbl_avatar.setFixedSize(26, 26)
            lbl_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_avatar.setStyleSheet(f"""
                QLabel {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {c1}, stop:1 {c2});
                    color: #ffffff;
                    font-size: 10px;
                    font-weight: 800;
                    border-radius: 13px;
                    border: 1px solid rgba(255, 255, 255, 0.4);
                }}
            """)
            h.addWidget(lbl_avatar)

            # 3. Öğrenci Adı
            lbl_name = QLabel(row_data["name"])
            name_fg = "#f8fafc" if is_dark else "#1e293b"
            lbl_name.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {name_fg}; border: none; background: transparent;")
            h.addWidget(lbl_name, 1)

            # 4. Rozet Rozeti / Başarı Hapı
            lbl_badge = QLabel(row_data["badge"])
            lbl_badge.setStyleSheet(f"""
                QLabel {{
                    background-color: {meta["bg"]};
                    color: {meta["fg"]};
                    border: 1px solid {meta["border"]};
                    border-radius: 5px;
                    padding: 2px 6px;
                    font-size: 10px;
                    font-weight: 700;
                }}
            """)
            h.addWidget(lbl_badge)

            # 5. Ödev Sayısı
            done_cnt = row_data["done"]
            lbl_done = QLabel(f"{done_cnt} Ödev")
            done_fg = "#38bdf8" if is_dark else "#2563eb"
            lbl_done.setStyleSheet(f"font-size: 11px; font-weight: 800; color: {done_fg}; border: none; background: transparent;")
            h.addWidget(lbl_done)

            # Tıklanınca detay aç
            def _make_click_handler(rdata, rmeta):
                return lambda event: self._show_badge_detail(rdata, rmeta)
            row_frame.mousePressEvent = _make_click_handler(row_data, meta)

            self.rows_layout.addWidget(row_frame)

    def _show_badge_detail(self, row_data, meta):
        dlg_data = {
            "title": row_data.get("badge", "Haftalık Başarı"),
            "subtitle": f"{row_data['name']} · {row_data['done']} Ödev Tamamlandı",
            "icon": meta.get("medal", "🏆"),
            "grad": f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {meta['bg']}, stop:1 {meta['border']})",
            "text": meta.get("fg", "#1e293b"),
            "desc_val": row_data.get("done", 0),
        }
        dlg = BadgeDetailDialog(dlg_data, self)
        dlg.exec()


class ClickableBadge(QFrame):
    """Geriye dönük uyumluluk için korunan tıklanabilir rozet kartı."""

    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data = data
        stops = re.findall(r'stop:[01]\s*(#[0-9a-fA-F]{6})', str(data.get('grad', '')))
        preferred = str(data.get('text', '#334155'))
        if len(stops) >= 2:
            a, b, self._badge_fg = accessible_gradient(stops[0], stops[1], preferred)
            self._badge_gradient = str(data['grad']).replace(stops[0], a).replace(stops[1], b)
        else:
            self._badge_fg = preferred
            self._badge_gradient = data.get('grad', '')

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(80, 105)
        self.setStyleSheet(f"""
            ClickableBadge {{
                background: {self._badge_gradient};
                border: 1px solid {data.get('text', '#334155')}30;
                border-radius: 12px;
            }}
            ClickableBadge:hover {{
                border: 1px solid {data.get('text', '#334155')};
                margin-top: -2px;
            }}
        """)

        v = QVBoxLayout(self)
        v.setContentsMargins(5, 8, 5, 8)
        v.setSpacing(4)

        ic = QLabel(data.get('icon', '⭐'))
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet("font-size: 28px; background: transparent; border:none;")

        tt = QLabel(data.get('title', 'Rozet'))
        tt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tt.setStyleSheet(f"font-size: 11px; font-weight: 800; color: {self._badge_fg}; background: transparent; border:none;")

        sub = QLabel(data.get('subtitle', ''))
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"font-size: 9px; font-weight: 600; color: {self._badge_fg}; background: transparent; border:none;")

        v.addWidget(ic)
        v.addWidget(tt)
        v.addWidget(sub)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            dlg = BadgeDetailDialog(self.data, self)
            dlg.exec()
        super().mousePressEvent(event)


class BadgeDetailDialog(QDialog):
    """Rozet ve Liderlik Detay Penceresi - Modern & Profesyonel."""

    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data = data
        self.setWindowTitle(f"{data.get('title', 'Rozet')} Detayları")
        self.setFixedSize(400, 470)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._body_frame = main_frame = QFrame(self)
        main_frame.setGeometry(10, 10, 380, 450)
        main_frame.setStyleSheet("background-color: white; border-radius: 16px;")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 5)
        main_frame.setGraphicsEffect(shadow)

        layout = QVBoxLayout(main_frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header (Gradient)
        header = QFrame()
        header.setFixedHeight(130)
        header.setStyleSheet(f"""
            border-top-left-radius: 16px;
            border-top-right-radius: 16px;
            background: {data.get('grad', '#e0e7ff')};
        """)
        h_lay = QVBoxLayout(header)
        h_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QLabel(data.get('icon', '🏆'))
        icon.setStyleSheet("font-size: 58px; background: transparent;")
        h_lay.addWidget(icon)

        layout.addWidget(header)

        # Body
        body = QWidget()
        b_lay = QVBoxLayout(body)
        b_lay.setContentsMargins(28, 20, 28, 20)
        b_lay.setSpacing(12)

        self._detail_title = lbl_title = QLabel(data.get('title', ''))
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_title.setStyleSheet("font-size: 20px; font-weight: 800; color: #1e293b;")

        self._detail_sub = lbl_sub = QLabel(data.get('subtitle', ''))
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_sub.setStyleSheet("font-size: 13px; font-weight: 600; color: #64748b;")

        b_lay.addWidget(lbl_title)
        b_lay.addWidget(lbl_sub)

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background: #f1f5f9;")
        b_lay.addWidget(line)

        advice_text = self._get_smart_advice(data)
        self._detail_advice = lbl_advice = QLabel(advice_text)
        lbl_advice.setWordWrap(True)
        lbl_advice.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_advice.setStyleSheet("font-size: 13px; line-height: 1.5; color: #475569;")
        b_lay.addWidget(lbl_advice)

        b_lay.addStretch()

        self._detail_button = btn_close = QPushButton("Harika, Devam Et! 🚀")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self.accept)
        btn_close.setFixedHeight(42)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                font-weight: bold;
                font-size: 13px;
                border-radius: 10px;
                border: none;
            }
            QPushButton:hover { background-color: #1d4ed8; }
        """)
        b_lay.addWidget(btn_close)

        layout.addWidget(body)
        register_theme_listener(self)
        self._on_theme_changed()

    def _on_theme_changed(self):
        c = semantic_palette()
        self._body_frame.setStyleSheet(f'background:{c["surface"]};border-radius:16px;')
        self._detail_title.setStyleSheet(f'font-size:20px;font-weight:800;color:{c["surface_fg"]};')
        self._detail_sub.setStyleSheet(f'font-size:13px;font-weight:600;color:{c["surface_fg"]};')
        self._detail_advice.setStyleSheet(f'font-size:13px;line-height:1.5;color:{c["surface_fg"]};')

    def _get_smart_advice(self, data):
        title = data.get('title', '')
        sub = data.get('subtitle', '')
        val = data.get('desc_val', '')

        if "Zirve" in title:
            return f"🏔️ <b>{sub}</b><br>Ödev tamamlama oranıyla haftanın zirvesinde yer alıyor. Tebrikler! 👏"
        elif "Seri" in title:
            return f"⚡ <b>{sub}</b><br>Kesintisiz çalışma ve ödev tamamlama disiplinini başarıyla sürdürüyor."
        elif "Canavar" in title:
            return f"📚 <b>{sub}</b><br>Toplamda <b>{val} ödev</b> tamamlayarak haftanın en çalışkanı oldu!"
        else:
            return "🌟 <b>Düzenli Takip!</b><br>Öğrencilerinizin haftalık performansını buradan izleyebilir, onları başarı rozetleriyle ödüllendirebilirsiniz."
