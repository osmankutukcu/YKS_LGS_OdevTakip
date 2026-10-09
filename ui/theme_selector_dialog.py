# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame, QGridLayout, QButtonGroup,
    QRadioButton, QApplication, QMessageBox
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QFont, QCursor

from ui import app_settings as appset
from ui.theme import tema_presets, tema_apply_preset, build_qss


class ThemeCard(QFrame):
    """Her tema için görsel önizleme ve seçim kartı."""
    def __init__(self, name: str, info: dict, is_selected: bool, on_select_callback):
        super().__init__()
        self.name = name
        self.info = info
        self.on_select_callback = on_select_callback
        self.is_selected = is_selected
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._build_ui()
        self.update_selection_state(is_selected)

    def _build_ui(self):
        self.setFixedSize(195, 105)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)

        # Üst Satır: Tema Adı & Mod Rozeti
        top_row = QHBoxLayout()
        lbl_name = QLabel(self.name)
        lbl_name.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        lbl_name.setStyleSheet("color: #0f172a;")

        is_dark = self.info.get("mode") == "dark"
        lbl_mode = QLabel("🌙 Koyu" if is_dark else "☀️ Açık")
        lbl_mode.setStyleSheet(
            "font-size: 9px; font-weight: bold; padding: 2px 5px; border-radius: 4px; "
            + ("background: #1e293b; color: #93c5fd;" if is_dark else "background: #fef3c7; color: #b45309;")
        )

        top_row.addWidget(lbl_name, 1)
        top_row.addWidget(lbl_mode)
        lay.addLayout(top_row)

        # Renk Paleti Önizlemesi (3 Nokta)
        color_row = QHBoxLayout()
        color_row.setSpacing(6)

        p_col = self.info.get("primary", "#2563eb")
        a_col = self.info.get("accent", "#10b981")
        bg_col = self.info.get("bg", "#ffffff")

        def make_dot(hex_code, label_text):
            dot_w = QFrame()
            dot_w.setFixedSize(22, 22)
            dot_w.setStyleSheet(f"background-color: {hex_code}; border-radius: 11px; border: 1.5px solid rgba(0,0,0,0.15);")
            dot_w.setToolTip(f"{label_text}: {hex_code}")
            return dot_w

        color_row.addWidget(make_dot(p_col, "Ana Renk"))
        color_row.addWidget(make_dot(a_col, "Vurgu Rengi"))
        color_row.addWidget(make_dot(bg_col, "Arka Plan"))
        color_row.addStretch(1)

        # Seçim İşareti
        self.lbl_check = QLabel("✓")
        self.lbl_check.setStyleSheet("font-size: 14px; font-weight: bold; color: #2563eb;")
        self.lbl_check.setVisible(self.is_selected)
        color_row.addWidget(self.lbl_check)

        lay.addLayout(color_row)

    def update_selection_state(self, selected: bool):
        self.is_selected = selected
        self.lbl_check.setVisible(selected)
        if selected:
            self.setStyleSheet("""
                QFrame {
                    background-color: #eff6ff;
                    border: 2px solid #2563eb;
                    border-radius: 10px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-radius: 10px;
                }
                QFrame:hover {
                    border: 1px solid #94a3b8;
                    background-color: #f8fafc;
                }
            """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.on_select_callback(self.name)


class ThemeSelectorDialog(QDialog):
    """Kullanıcının uygulamayı kapatıp açmasına gerek kalmadan canlı tema seçebildiği pencere."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🎨 Tema ve Renk Stili Seçici")
        self.resize(860, 560)
        self.setMinimumSize(780, 500)

        # Mevcut aktif tema
        self.current_theme = appset.ayar_get("tema_seti", "Cloud Light") or "Cloud Light"
        self.cards = {}
        self.filter_mode = "all"  # 'all', 'light', 'dark', 'fun'

        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("""
            QDialog { background-color: #f8fafc; }
            QLabel { font-family: 'Segoe UI', sans-serif; }
            QPushButton { font-family: 'Segoe UI', sans-serif; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # 1. Başlık ve Açıklama Barı
        top_box = QHBoxLayout()
        v_title = QVBoxLayout()
        lbl_title = QLabel("🎨 Görsel Tema ve Renk Tercihleri")
        lbl_title.setStyleSheet("font-size: 17px; font-weight: 800; color: #0f172a;")
        lbl_desc = QLabel("Çalışma ortamınıza en uygun temayı seçin. Değişiklikler uygulamayı yeniden başlatmadan anında canlı uygulanır.")
        lbl_desc.setStyleSheet("font-size: 11.5px; color: #64748b;")
        v_title.addWidget(lbl_title)
        v_title.addWidget(lbl_desc)
        top_box.addLayout(v_title, 1)

        layout.addLayout(top_box)

        # 2. Filtre Butonları (Tümü, Açık, Koyu, Özel)
        f_bar = QHBoxLayout()
        f_bar.setSpacing(8)

        self.btn_f_all = QPushButton("🌟 Tümü")
        self.btn_f_light = QPushButton("☀️ Açık Temalar")
        self.btn_f_dark = QPushButton("🌙 Koyu Temalar")
        self.btn_f_fun = QPushButton("🎮 Özel / Renkli")

        for b, mode in [(self.btn_f_all, "all"), (self.btn_f_light, "light"), (self.btn_f_dark, "dark"), (self.btn_f_fun, "fun")]:
            b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            b.setFixedHeight(30)
            b.clicked.connect(lambda _, m=mode: self._set_filter(m))
            f_bar.addWidget(b)

        f_bar.addStretch(1)
        layout.addLayout(f_bar)
        self._update_filter_buttons()

        # 3. Tema Kartları Izgarası (Scroll Area)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(4, 4, 4, 4)
        self.grid_layout.setSpacing(12)
        scroll.setWidget(self.grid_container)
        layout.addWidget(scroll, 1)

        self._populate_cards()

        # 4. Alt İşlem Barı
        bot_box = QFrame()
        bot_box.setStyleSheet("background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 6px;")
        b_lay = QHBoxLayout(bot_box)
        b_lay.setContentsMargins(12, 6, 12, 6)

        self.lbl_status = QLabel(f"Seçili Tema: <b>{self.current_theme}</b>")
        self.lbl_status.setStyleSheet("font-size: 12px; color: #1e293b;")
        b_lay.addWidget(self.lbl_status)
        b_lay.addStretch(1)

        btn_apply = QPushButton("⚡ Canlı Uygula")
        btn_apply.setStyleSheet("background: #3b82f6; color: white; font-weight: 700; border-radius: 6px; padding: 7px 16px;")
        btn_apply.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_apply.clicked.connect(lambda: self._apply_theme_live(self.current_theme, show_toast=True))
        b_lay.addWidget(btn_apply)

        btn_ok = QPushButton("✓ Kaydet ve Kapat")
        btn_ok.setStyleSheet("background: #10b981; color: white; font-weight: 700; border-radius: 6px; padding: 7px 18px;")
        btn_ok.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_ok.clicked.connect(self._save_and_close)
        b_lay.addWidget(btn_ok)

        layout.addWidget(bot_box)

    def _set_filter(self, mode: str):
        self.filter_mode = mode
        self._update_filter_buttons()
        self._populate_cards()

    def _update_filter_buttons(self):
        base_style = "border-radius: 6px; font-weight: 600; font-size: 11px; padding: 4px 12px;"
        active_style = base_style + " background: #2563eb; color: white; border: none;"
        inactive_style = base_style + " background: white; color: #475569; border: 1px solid #cbd5e1;"

        self.btn_f_all.setStyleSheet(active_style if self.filter_mode == "all" else inactive_style)
        self.btn_f_light.setStyleSheet(active_style if self.filter_mode == "light" else inactive_style)
        self.btn_f_dark.setStyleSheet(active_style if self.filter_mode == "dark" else inactive_style)
        self.btn_f_fun.setStyleSheet(active_style if self.filter_mode == "fun" else inactive_style)

    def _populate_cards(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.cards.clear()

        presets = tema_presets()
        fun_themes = {"Neon", "Cyberpunk", "Vaporwave", "Pastel Pop", "Sakura", "Ocean Breeze", "Sunset Pop", "Retro GameBoy", "Rainbow Candy", "Fenerbahçe", "Galatasaray", "Beşiktaş", "Trabzonspor"}

        filtered = []
        for name, info in presets.items():
            mode = info.get("mode")
            if self.filter_mode == "light" and mode != "light":
                continue
            if self.filter_mode == "dark" and mode != "dark":
                continue
            if self.filter_mode == "fun" and name not in fun_themes:
                continue
            filtered.append((name, info))

        cols = 4
        for idx, (name, info) in enumerate(filtered):
            card = ThemeCard(name, info, name == self.current_theme, self._on_card_selected)
            r = idx // cols
            c = idx % cols
            self.grid_layout.addWidget(card, r, c)
            self.cards[name] = card

    def _on_card_selected(self, name: str):
        self.current_theme = name
        self.lbl_status.setText(f"Seçili Tema: <b>{self.current_theme}</b>")
        for t_name, card in self.cards.items():
            card.update_selection_state(t_name == name)
        self._apply_theme_live(name, show_toast=False)

    def _apply_theme_live(self, name: str, show_toast: bool = False):
        try:
            tema_apply_preset(name)
            new_qss = build_qss()
            app = QApplication.instance()
            if app:
                app.setStyleSheet(new_qss)
            if show_toast:
                QMessageBox.information(self, "Tema Uygulandı", f"'{name}' teması başarıyla uygulandı!")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Tema uygulanırken hata oluştu:\n{e}")

    def _save_and_close(self):
        self._apply_theme_live(self.current_theme, show_toast=False)
        self.accept()
