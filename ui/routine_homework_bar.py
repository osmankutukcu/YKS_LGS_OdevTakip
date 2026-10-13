"""ui/routine_homework_bar.py

Paragraf ve Problemler sekmelerinin üzerinde yer alan, öğretmenin tek tıkla
haftalık rutin soru ve süre hedefi atamasını sağlayan kompakt ve modern arayüz bileşeni.
"""
from __future__ import annotations
from typing import List, Any
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QSpinBox, QComboBox,
    QToolButton, QMenu, QMessageBox
)
from services.routine_homework_helper import (
    load_routine_defaults, save_routine_defaults, generate_routine_tasks
)


class RoutineHomeworkBar(QFrame):
    """Paragraf ve Problemler için hızlı rutin ödev şeridi."""

    def __init__(self, ogr_id: int, ders: str, books: List[str], table: Any, parent_form: Any):
        super().__init__()
        self.ogr_id = ogr_id
        self.ders = ders.strip().lower()
        self.books = [b for b in books if b and b.strip()]
        self.table = table
        self.parent_form = parent_form
        self._current_days = 7
        self._init_ui()

    def _init_ui(self):
        self.setFixedHeight(34)
        self.setStyleSheet("""
            RoutineHomeworkBar {
                background: #f5f7ff;
                border: 1px solid #c7d2fe;
                border-radius: 6px;
                margin-bottom: 2px;
            }
            QLabel {
                font-size: 11px;
                color: #334155;
                font-weight: 600;
                border: none;
                background: transparent;
            }
            QSpinBox {
                background: white;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 1px 4px;
                font-size: 11px;
                font-weight: 700;
                color: #1e293b;
            }
            QComboBox {
                background: white;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 1px 6px;
                font-size: 11px;
                font-weight: 600;
                color: #1e293b;
            }
            QToolButton {
                background: #4f46e5;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 4px 10px;
                font-weight: 700;
                font-size: 11px;
            }
            QToolButton:hover {
                background: #4338ca;
            }
            QToolButton::menu-button {
                border-left: 1px solid rgba(255, 255, 255, 0.35);
                border-top-right-radius: 5px;
                border-bottom-right-radius: 5px;
                width: 16px;
            }
            QToolButton::menu-button:hover {
                background: #3730a3;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(6)

        # 1. Başlık & Rozet
        icon = "📑" if "paragraf" in self.ders else "🧩"
        title_text = "Haftalık Rutin:"
        lbl_title = QLabel(f"<b>{icon} {title_text}</b>")
        lbl_title.setStyleSheet("color: #4338ca; font-size: 11px;")
        layout.addWidget(lbl_title)

        # Tercihleri yükle
        prefs = load_routine_defaults(self.ders)
        self._current_days = prefs.get("gun", 7)
        if self._current_days not in (5, 7):
            self._current_days = 7

        # 2. Soru Sayısı SpinBox (Otomatik Kayıtlı)
        layout.addWidget(QLabel("Günde:"))
        self.sp_soru = QSpinBox()
        self.sp_soru.setRange(1, 150)
        self.sp_soru.setValue(prefs.get("soru", 20 if "paragraf" in self.ders else 15))
        self.sp_soru.setSuffix(" Soru")
        self.sp_soru.setFixedWidth(74)
        self.sp_soru.valueChanged.connect(self._on_prefs_changed)
        layout.addWidget(self.sp_soru)

        # 3. Kitap Seçimi (Tek Kitap veya Dönüşümlü)
        layout.addWidget(QLabel("Kitap:"))
        self.cmb_book = QComboBox()
        self.cmb_book.setMaximumWidth(130)
        self._populate_books()
        layout.addWidget(self.cmb_book)

        # 4. Süre SpinBox (Otomatik Kayıtlı)
        layout.addWidget(QLabel("Süre:"))
        self.sp_sure = QSpinBox()
        self.sp_sure.setRange(5, 180)
        self.sp_sure.setSingleStep(5)
        self.sp_sure.setValue(prefs.get("sure", 25 if "paragraf" in self.ders else 30))
        self.sp_sure.setSuffix(" dk")
        self.sp_sure.setFixedWidth(64)
        self.sp_sure.valueChanged.connect(self._on_prefs_changed)
        layout.addWidget(self.sp_sure)

        layout.addStretch(1)

        # 5. Tek Tıkla Haftalık Rutin Ata (1 Satır = 1 Hafta Rutini)
        self.btn_assign = QToolButton()
        self.btn_assign.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.btn_assign.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_assign.setToolTip("1 Satır = 1 Hafta: Sıradaki haftalık satırı işaretler ve haftalık hedefi ödev listesine aktarır (40 hafta boyunca yeter).")

        menu = QMenu(self.btn_assign)
        act_7 = menu.addAction("📅 7 Günlük Haftalık Rutin (Pzt - Paz • 1 Hafta)")
        act_7.triggered.connect(lambda: self._set_days_and_assign(7))
        act_5 = menu.addAction("💼 5 Günlük Haftalık Rutin (Pzt - Cum • Hafta İçi)")
        act_5.triggered.connect(lambda: self._set_days_and_assign(5))
        self.btn_assign.setMenu(menu)

        self._update_btn_text()
        self.btn_assign.clicked.connect(lambda: self._execute_assign(days=self._current_days))
        layout.addWidget(self.btn_assign)

    def _update_btn_text(self):
        lbl_days = f"{self._current_days} Gün"
        self.btn_assign.setText(f"🚀 Haftaya Ata ({lbl_days})")

    def _set_days_and_assign(self, days: int):
        self._current_days = days
        self._update_btn_text()
        self._on_prefs_changed()
        self._execute_assign(days=days)

    def _populate_books(self):
        self.cmb_book.clear()
        if not self.books:
            self.cmb_book.addItem("⚠️ Kaynak Kitap Yok", "")
            return
        if len(self.books) > 1:
            self.cmb_book.addItem("🔄 Tüm Kitaplar (Dönüşümlü)", "__ALL_ALTERNATING__")
        for b in self.books:
            self.cmb_book.addItem(f"📖 {b}", b)

    def _on_prefs_changed(self):
        """Soru ve süre her değiştiğinde arka planda otomatik kaydeder."""
        save_routine_defaults(
            self.ders,
            soru=self.sp_soru.value(),
            sure=self.sp_sure.value(),
            gun=self._current_days
        )

    def _notify(self, text: str, kind: str = "success"):
        """Kullanıcıyı tıklamaya mecbur bırakmayan, 2 saniyede kendiliğinden kaybolan Toast bildirim."""
        # 1. Öncelik: Formun dahili _toast metodu (Butonun hemen altına şık rozet)
        toast_func = getattr(self.parent_form, "_toast", None)
        if callable(toast_func):
            try:
                prefix = "✅ " if kind == "success" else ("⚠️ " if kind == "warn" else "❌ ")
                toast_func(f"{prefix}{text}", parent=self.parent_form, msec=1800, under_widget=self.btn_assign)
                return
            except Exception:
                pass

        # 2. Öncelik: ui.toast.show_toast
        try:
            from ui.toast import show_toast
            host = self.parent_form if self.parent_form else self
            show_toast(parent=host, text=text, kind=kind, duration_ms=2000, font_size=13, corner="br")
            return
        except Exception:
            pass

        print(f"[Rutin Bildirimi - {kind}]: {text}")

    def _execute_assign(self, days: int = 7):
        """Öğrencinin sıradaki haftalık boş satırını tespit eder ve sağdaki ödev listesine aktarır."""
        if not self.books:
            self._notify(
                f"{self.ders.capitalize()} dersine tanımlı kaynak kitap bulunamadı.",
                kind="warn"
            )
            return

        selected_mode = self.cmb_book.currentData()
        if selected_mode is None:
            selected_mode = self.books[0]

        questions = self.sp_soru.value()
        duration = self.sp_sure.value()

        # Otomatik kaydet
        save_routine_defaults(self.ders, soru=questions, sure=duration, gun=days)

        tasks = generate_routine_tasks(
            lesson=self.ders,
            books=self.books,
            selected_book_mode=selected_mode,
            days_count=days,
            questions_per_day=questions,
            duration_minutes=duration,
            table=self.table
        )

        if not tasks:
            self._notify(
                f"{self.ders.capitalize()} tablosunda boş haftalık satır kalmadı.",
                kind="warn"
            )
            return

        transfer_func = getattr(self.parent_form, "_wizard_transfer_tasks", None)
        if callable(transfer_func):
            try:
                res = transfer_func(tasks, expected_student_id=self.ogr_id, show_dialog=False)
            except TypeError:
                res = transfer_func(tasks, expected_student_id=self.ogr_id)
            added = res.get("added", 0) if isinstance(res, dict) else len(tasks)
            if added > 0:
                topic_label = tasks[0].get("konu", "")
                total_duration = sum(t.get("dk", 0) for t in tasks)
                self._notify(
                    f"{self.ders.capitalize()} rutini eklendi: {topic_label} ({total_duration} dk)",
                    kind="success"
                )
            else:
                self._notify(
                    "Ödevler listeye aktarılamadı.",
                    kind="error"
                )

