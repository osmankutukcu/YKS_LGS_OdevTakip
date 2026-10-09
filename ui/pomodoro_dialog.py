# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QProgressBar, QSpinBox, QComboBox, QLineEdit, QFrame,
    QMessageBox, QApplication
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QColor, QCursor
import db
import random

MOTIVATION_QUOTES = [
    "🚀 Gelecek, bugünden hazırlananlara aittir.",
    "🎯 Odaklanma; evet dediklerinden çok, hayır diyebildiklerinin gücüdür.",
    "💡 Zorluklar, başarının süsüdür. Masadan kalkma!",
    "🏆 Şampiyonlar antrenman bittiğinde değil, canı yanarken devam edenlerdir.",
    "⏳ 25 dakikalık saf dikkat, dağınık geçen 3 saate bedeldir.",
    "📚 Her çözülen soru, hedefe atılan sağlam bir adımdır.",
    "🌟 İstikrar, yeteneği her zaman mağlup eder."
]

class PomodoroDialog(QDialog):
    """
    Öğrenciler ve Koçlar için Gelişmiş Odaklanma ve Pomodoro Stüdyosu.
    Ders seçimi, döngü takibi, ambiyans ve motivasyon koçluğu içerir.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🍅 Odaklanma ve Pomodoro Stüdyosu")
        self.resize(460, 600)
        self.setMinimumSize(420, 540)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: #f8fafc;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel { color: #f8fafc; font-family: 'Segoe UI', Arial, sans-serif; }
            QComboBox, QLineEdit {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 7px 10px;
                color: #f8fafc;
                font-size: 12px;
            }
            QComboBox:focus, QLineEdit:focus {
                border: 1.5px solid #38bdf8;
            }
            QPushButton {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-weight: 700;
                border-radius: 8px;
            }
            QProgressBar {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                text-align: center;
                color: white;
                font-size: 10px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #38bdf8;
                border-radius: 5px;
            }
        """)
        
        self.work_time = 25 * 60
        self.break_time = 5 * 60
        self.current_time = self.work_time
        self.total_cycle_time = self.work_time
        
        self.is_running = False
        self.is_break = False
        self.completed_pomodoros = 0
        self.total_focus_minutes = 0
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timer)
        
        self._init_ui()
        self._load_lessons()
        self._set_random_quote()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        # 1. ÜST BAŞLIK VE MOD SEÇİMİ
        top_box = QHBoxLayout()
        lbl_title = QLabel("🍅 ODAKLANMA STÜDYOSU")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: 900; color: #38bdf8; letter-spacing: 1.5px;")
        top_box.addWidget(lbl_title)
        top_box.addStretch(1)

        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems([
            "🎯 Klasik (25/5)",
            "⚡ Derin Odak (50/10)",
            "🚀 Soru Kampı (40/10)",
            "⏱️ Hızlı Tekrar (15/3)"
        ])
        self.cmb_mode.currentIndexChanged.connect(self.change_mode)
        top_box.addWidget(self.cmb_mode)
        root.addLayout(top_box)

        # 2. DERS VE GÖREV SEÇİM PANELİ
        task_frame = QFrame()
        task_frame.setStyleSheet("background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 6px;")
        t_lay = QVBoxLayout(task_frame)
        t_lay.setContentsMargins(10, 8, 10, 8)
        t_lay.setSpacing(6)

        lbl_t_head = QLabel("📚 Odaklanılan Ders ve Hedef:")
        lbl_t_head.setStyleSheet("font-size: 11px; font-weight: 700; color: #94a3b8;")
        t_lay.addWidget(lbl_t_head)

        h_task = QHBoxLayout()
        h_task.setSpacing(8)
        self.cmb_lesson = QComboBox()
        self.cmb_lesson.addItem("Genel / Serbest Çalışma")
        self.cmb_lesson.setMinimumWidth(160)
        h_task.addWidget(self.cmb_lesson)

        self.txt_task = QLineEdit()
        self.txt_task.setPlaceholderText("Hedef konu veya soru adedi (örn. 30 Soru Paragraf)...")
        h_task.addWidget(self.txt_task, 1)
        t_lay.addLayout(h_task)
        root.addWidget(task_frame)

        # 3. BÜYÜK SAYAÇ VE DURUM KARTI
        timer_card = QFrame()
        timer_card.setStyleSheet("background: #111827; border: 2px solid #1e293b; border-radius: 16px;")
        tc_lay = QVBoxLayout(timer_card)
        tc_lay.setContentsMargins(16, 18, 16, 18)
        tc_lay.setSpacing(8)

        self.lbl_status = QLabel("🚀 ÇALIŞMA ZAMANI • TAM DİKKAT")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet("color: #38bdf8; font-size: 12px; font-weight: 800; letter-spacing: 1px;")
        tc_lay.addWidget(self.lbl_status)

        self.lbl_timer = QLabel("25:00")
        self.lbl_timer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_timer.setFont(QFont("Segoe UI", 68, QFont.Weight.Bold))
        self.lbl_timer.setStyleSheet("color: #ffffff; margin: 4px 0;")
        tc_lay.addWidget(self.lbl_timer)

        self.prog_bar = QProgressBar()
        self.prog_bar.setFixedHeight(8)
        self.prog_bar.setTextVisible(False)
        self.prog_bar.setValue(100)
        tc_lay.addWidget(self.prog_bar)

        root.addWidget(timer_card)

        # 4. KONTROL BUTONLARI
        h_ctrl = QHBoxLayout()
        h_ctrl.setSpacing(10)

        self.btn_start = QPushButton("▶ BAŞLAT")
        self.btn_start.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_start.setFixedHeight(44)
        self.btn_start.setStyleSheet("background-color: #2563eb; color: white; font-size: 14px; border: none;")
        self.btn_start.clicked.connect(self.toggle_timer)
        h_ctrl.addWidget(self.btn_start, 2)

        self.btn_skip = QPushButton("⏭️ İleri Sar")
        self.btn_skip.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_skip.setFixedHeight(44)
        self.btn_skip.setStyleSheet("background-color: #334155; color: #f8fafc; font-size: 12px; border: none;")
        self.btn_skip.clicked.connect(self.skip_phase)
        h_ctrl.addWidget(self.btn_skip, 1)

        self.btn_reset = QPushButton("↺ Sıfırla")
        self.btn_reset.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_reset.setFixedHeight(44)
        self.btn_reset.setStyleSheet("background-color: #ef4444; color: white; font-size: 12px; border: none;")
        self.btn_reset.clicked.connect(self.reset_timer)
        h_ctrl.addWidget(self.btn_reset, 1)

        root.addLayout(h_ctrl)

        # 5. DÖNGÜ VE İSTATİSTİK ŞERİDİ
        stats_frame = QFrame()
        stats_frame.setStyleSheet("background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 6px;")
        sf_lay = QHBoxLayout(stats_frame)
        sf_lay.setContentsMargins(12, 6, 12, 6)

        self.lbl_pomo_count = QLabel("Döngü: ⚪ ⚪ ⚪ ⚪")
        self.lbl_pomo_count.setStyleSheet("font-size: 12px; font-weight: 700; color: #f59e0b;")
        sf_lay.addWidget(self.lbl_pomo_count)
        sf_lay.addStretch(1)

        self.lbl_total_focus = QLabel("Bugün: 0 dk")
        self.lbl_total_focus.setStyleSheet("font-size: 12px; font-weight: 700; color: #10b981;")
        sf_lay.addWidget(self.lbl_total_focus)

        root.addWidget(stats_frame)

        # 6. MOTİVASYON SÖZÜ
        self.lbl_quote = QLabel("")
        self.lbl_quote.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_quote.setWordWrap(True)
        self.lbl_quote.setStyleSheet("font-size: 11px; font-style: italic; color: #94a3b8; padding: 4px 10px;")
        root.addWidget(self.lbl_quote)

    def _load_lessons(self):
        try:
            con = db.get_conn()
            rows = con.execute("SELECT DISTINCT ders FROM odev WHERE ders IS NOT NULL AND ders != '' ORDER BY ders ASC").fetchall()
            con.close()
            for r in rows:
                self.cmb_lesson.addItem(r[0])
        except Exception:
            pass

    def _set_random_quote(self):
        self.lbl_quote.setText(random.choice(MOTIVATION_QUOTES))

    def toggle_timer(self):
        if self.is_running:
            self.timer.stop()
            self.btn_start.setText("▶ DEVAM ET")
            self.btn_start.setStyleSheet("background-color: #2563eb; color: white; font-size: 14px; border: none;")
            self.is_running = False
            self.lbl_timer.setStyleSheet("color: #f59e0b;")  # Pause amber
        else:
            self.timer.start(1000)
            self.btn_start.setText("⏸ DURAKLAT")
            self.btn_start.setStyleSheet("background-color: #d97706; color: white; font-size: 14px; border: none;")
            self.is_running = True
            if self.is_break:
                self.lbl_timer.setStyleSheet("color: #34d399;")
            else:
                self.lbl_timer.setStyleSheet("color: #38bdf8;")

    def reset_timer(self):
        self.timer.stop()
        self.is_running = False
        self.is_break = False
        self.change_mode()
        self.btn_start.setText("▶ BAŞLAT")
        self.btn_start.setStyleSheet("background-color: #2563eb; color: white; font-size: 14px; border: none;")
        self.lbl_status.setText("🚀 ÇALIŞMA ZAMANI • TAM DİKKAT")
        self.lbl_status.setStyleSheet("color: #38bdf8; font-size: 12px; font-weight: 800; letter-spacing: 1px;")
        self.lbl_timer.setStyleSheet("color: #ffffff;")
        self._set_random_quote()

    def change_mode(self):
        txt = self.cmb_mode.currentText()
        if "50/10" in txt:
            self.work_time = 50 * 60
            self.break_time = 10 * 60
        elif "40/10" in txt:
            self.work_time = 40 * 60
            self.break_time = 10 * 60
        elif "15/3" in txt:
            self.work_time = 15 * 60
            self.break_time = 3 * 60
        else:
            self.work_time = 25 * 60
            self.break_time = 5 * 60

        self.current_time = self.break_time if self.is_break else self.work_time
        self.total_cycle_time = self.current_time
        self.update_display()

    def skip_phase(self):
        self.current_time = 1
        self.update_timer()

    def update_timer(self):
        self.current_time -= 1
        if self.current_time <= 0:
            self.timer.stop()
            self.is_running = False
            QApplication.beep()

            # Switch mode
            self.is_break = not self.is_break
            if self.is_break:
                self.completed_pomodoros += 1
                focus_mins = self.work_time // 60
                self.total_focus_minutes += focus_mins
                self._update_stats()

                # Her 4 pomodoroda bir uzun mola
                is_long_break = (self.completed_pomodoros % 4 == 0)
                if is_long_break:
                    self.current_time = 20 * 60
                    self.lbl_status.setText("🎉 4 DÖNGÜ BİTTİ! 20 DK UZUN MOLA ZAMANI")
                    self.lbl_status.setStyleSheet("color: #a78bfa; font-size: 12px; font-weight: 800; letter-spacing: 1px;")
                else:
                    self.current_time = self.break_time
                    self.lbl_status.setText("☕ MOLA ZAMANI • GÖZLERİNİ DİNLENDİR")
                    self.lbl_status.setStyleSheet("color: #34d399; font-size: 12px; font-weight: 800; letter-spacing: 1px;")

                self.total_cycle_time = self.current_time
                self.lbl_timer.setStyleSheet("color: #34d399;")
                QMessageBox.information(self, "Tebrikler! 🍅", f"Tebrikler! 1 Odaklanma oturumu başarıyla tamamlandı.\nŞimdi dinlenme zamanı!")
            else:
                self.current_time = self.work_time
                self.total_cycle_time = self.current_time
                self.lbl_status.setText("🚀 ÇALIŞMA ZAMANI • TAM DİKKAT")
                self.lbl_status.setStyleSheet("color: #38bdf8; font-size: 12px; font-weight: 800; letter-spacing: 1px;")
                self.lbl_timer.setStyleSheet("color: #38bdf8;")
                QMessageBox.information(self, "Mola Bitti! 🚀", "Mola süresi doldu. Yeni oturuma hazır mısın?")

            self.btn_start.setText("▶ BAŞLAT")
            self.btn_start.setStyleSheet("background-color: #2563eb; color: white; font-size: 14px; border: none;")
            self._set_random_quote()
            self.update_display()
        else:
            self.update_display()

    def update_display(self):
        m = self.current_time // 60
        s = self.current_time % 60
        self.lbl_timer.setText(f"{m:02d}:{s:02d}")

        # Progress bar
        if self.total_cycle_time > 0:
            pct = int((self.current_time / self.total_cycle_time) * 100)
            self.prog_bar.setValue(pct)

    def _update_stats(self):
        # 4 döngü rozetleri
        cycle_idx = self.completed_pomodoros % 4
        symbols = []
        for i in range(4):
            if i < cycle_idx or (cycle_idx == 0 and self.completed_pomodoros > 0):
                symbols.append("🍅")
            else:
                symbols.append("⚪")
        self.lbl_pomo_count.setText(f"Döngü: {' '.join(symbols)} ({self.completed_pomodoros})")
        self.lbl_total_focus.setText(f"Bugün: {self.total_focus_minutes} dk Odak")
