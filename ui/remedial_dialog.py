from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QPushButton, QTableWidget, QTableWidgetItem, QAbstractItemView, 
    QMessageBox, QWidget, QFrame, QHeaderView, QCheckBox, QSpinBox,
    QScrollArea
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor
import db
from typing import Dict, List, Any, Optional

class SmartRemedialDialog(QDialog):
    """
    Akıllı Takviye & Telafi Oluşturucu.
    Öğrencinin geciken ödevlerini, düşük başarılı konularını ve unutma eğrisindeki
    pekiştirme ihtiyaçlarını hedef alarak doğrudan telafi ödevleri üretir.
    """
    def __init__(self, ogrenci_id: int, parent=None, available_books=None, active_lesson: str = None):
        super().__init__(parent)
        self.setWindowTitle("🎯 Akıllı Takviye ve Telafi Oluşturucu")
        self.resize(1000, 680)
        self.ogrenci_id = ogrenci_id
        self.available_books = available_books or {}
        self.active_lesson = active_lesson
        self.candidates: List[Dict[str, Any]] = []
        self.selected_remedials: List[Dict[str, Any]] = []

        self._build_ui()
        QTimer.singleShot(100, self._load_remedials)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        # --- ÜST BAŞLIK ---
        header = QHBoxLayout()
        header.setSpacing(10)

        lbl_icon = QLabel("🎯")
        lbl_icon.setStyleSheet("font-size: 32px;")
        header.addWidget(lbl_icon)

        vbox = QVBoxLayout()
        lbl_title = QLabel("Akıllı Takviye & Telafi Planlayıcı")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #dc2626;")
        lbl_sub = QLabel("Gecikmiş ödevlerin toparlanması, zayıf kalınan konuların güçlendirilmesi ve aralıklı tekrar.")
        lbl_sub.setStyleSheet("color: #64748b; font-size: 12px;")
        vbox.addWidget(lbl_title)
        vbox.addWidget(lbl_sub)
        header.addLayout(vbox)
        header.addStretch(1)

        root.addLayout(header)

        # --- FİLTRE & AYAR ÇUBUĞU ---
        filter_frame = QFrame()
        filter_frame.setStyleSheet("QFrame { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; }")
        fl = QHBoxLayout(filter_frame)
        fl.setContentsMargins(10, 8, 10, 8)
        fl.setSpacing(12)

        # Takviye Hedefi
        fl.addWidget(QLabel("<b>Takviye Hedefi:</b>"))
        self.cmbFocus = QComboBox()
        self.cmbFocus.addItems([
            "🚨 Geciken & Yapılmayan Ödevler",
            "📉 Düşük Başarılı Konuları Güçlendirme",
            "🧠 Hafıza Tazeleyici & Ebbinghaus Pekiştirme",
            "⚡ Hızlı Sınav Takviyesi (ÖSYM ⭐⭐⭐)"
        ])
        self.cmbFocus.setStyleSheet("""
            QComboBox { background: white; border: 1px solid #cbd5e1; border-radius: 6px; padding: 5px 10px; font-weight: 600; }
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 22px; border: none; background: transparent; }
            QComboBox::down-arrow { border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid #64748b; margin-right: 6px; }
        """)
        self.cmbFocus.currentIndexChanged.connect(self._load_remedials)
        fl.addWidget(self.cmbFocus)

        # Ders Filtresi
        fl.addWidget(QLabel("<b>Ders:</b>"))
        self.cmbLesson = QComboBox()
        self.cmbLesson.addItem("Tüm Dersler", "")
        self.cmbLesson.setStyleSheet("""
            QComboBox { background: white; border: 1px solid #cbd5e1; border-radius: 6px; padding: 5px 10px; }
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 22px; border: none; background: transparent; }
            QComboBox::down-arrow { border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid #64748b; margin-right: 6px; }
        """)
        self.cmbLesson.currentIndexChanged.connect(self._load_remedials)
        fl.addWidget(self.cmbLesson)

        # Hedef Süre
        fl.addWidget(QLabel("<b>Hedef Süre:</b>"))
        self.spTarget = QSpinBox()
        self.spTarget.setRange(20, 360)
        self.spTarget.setSingleStep(20)
        self.spTarget.setValue(60)
        self.spTarget.setSuffix(" dk")
        self.spTarget.setStyleSheet("background: white; border: 1px solid #cbd5e1; border-radius: 6px; padding: 4px;")
        self.spTarget.valueChanged.connect(self._reselect_by_target)
        fl.addWidget(self.spTarget)

        fl.addStretch(1)

        self.btnInfo = QPushButton("ℹ️ Nasıl Çalışır? (Rehber)")
        self.btnInfo.setStyleSheet("""
            QPushButton {
                background: #f0fdf4;
                border: 1px solid #bbf7d0;
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 11px;
                font-weight: bold;
                color: #15803d;
            }
            QPushButton:hover {
                background: #dcfce7;
                border-color: #86efac;
            }
        """)
        self.btnInfo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnInfo.clicked.connect(self._show_info_dialog)
        fl.addWidget(self.btnInfo)

        self.btnToggleAll = QPushButton("Tümünü Seç/Kaldır")
        self.btnToggleAll.setStyleSheet("background: white; border: 1px solid #cbd5e1; border-radius: 6px; padding: 5px 10px; font-size: 11px; font-weight: bold;")
        self.btnToggleAll.clicked.connect(self._toggle_selection)
        fl.addWidget(self.btnToggleAll)

        root.addWidget(filter_frame)

        # --- TABLO ---
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Seç", "Öncelik / Tür", "Ders", "Kitap / Kaynak", "Konu", "Takviye Hedefi", "Gerekçe & Analiz"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setStyleSheet("""
            QTableWidget { background: white; gridline-color: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 6px; }
            QHeaderView::section { background-color: #f8fafc; padding: 6px 8px; border: 1px solid #e2e8f0; font-weight: bold; color: #334155; }
            QTableWidget::item { padding: 4px 6px; }
        """)
        self.table.verticalHeader().setVisible(False)
        self.table.cellClicked.connect(self._on_cell_clicked)
        root.addWidget(self.table, 1)

        # --- ALT BAR ---
        bottom = QHBoxLayout()
        bottom.setSpacing(10)

        self.lblSummary = QLabel("Seçilen: 0 Takviye Ödevi (~0 dk, ~0 Soru)")
        self.lblSummary.setStyleSheet("font-size: 13px; font-weight: bold; color: #dc2626;")
        bottom.addWidget(self.lblSummary)
        bottom.addStretch(1)

        self.btnCancel = QPushButton("Vazgeç")
        self.btnCancel.setStyleSheet("background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px 16px; font-weight: bold; color: #475569;")
        self.btnCancel.clicked.connect(self.reject)
        bottom.addWidget(self.btnCancel)

        self.btnAdd = QPushButton("✅ Takviyeleri Ödev Listesine Ekle")
        self.btnAdd.setStyleSheet("""
            QPushButton { background-color: #dc2626; color: white; padding: 9px 20px; font-weight: bold; border-radius: 6px; font-size: 13px; }
            QPushButton:hover { background-color: #b91c1c; }
        """)
        self.btnAdd.clicked.connect(self._accept_selection)
        bottom.addWidget(self.btnAdd)

        root.addLayout(bottom)

    def _load_remedials(self):
        if not self.ogrenci_id:
            return

        con = db.get_conn()
        try:
            from utils import ai_recommend

            # Dersleri doldur (ilk açılışta)
            if self.cmbLesson.count() <= 1:
                try:
                    lessons = con.execute("SELECT id, ad FROM ders_tanimlari WHERE aktif=1 ORDER BY siralama").fetchall()
                    for l in lessons:
                        self.cmbLesson.addItem(l["ad"], l["id"])
                    if self.active_lesson:
                        for i in range(self.cmbLesson.count()):
                            if self.cmbLesson.itemData(i) == self.active_lesson:
                                self.cmbLesson.setCurrentIndex(i)
                                break
                except Exception:
                    pass

            analytics = ai_recommend.get_comprehensive_student_analytics(con, self.ogrenci_id)
            focus_idx = self.cmbFocus.currentIndex()
            selected_lesson = self.cmbLesson.currentData()

            candidates: List[Dict[str, Any]] = []

            # 1. Geciken / Yapılmayan Ödevler
            if focus_idx == 0:
                for ov in analytics["overdue_remedials"]:
                    if selected_lesson and ov["ders"] != selected_lesson:
                        continue
                    book = ov.get("kitap") or "Soru Bankası"
                    # Gerçek ödev kitabını başka bir kitabın ilk kaydıyla DEĞİŞTİRME.
                    candidates.append({
                        "type": "overdue",
                        "badge": "🚨 Geciken Telafi",
                        "badge_color": "#dc2626",
                        "ders": ov["ders"],
                        "kitap": book,
                        "konu": ov["konu"],
                        "dk": min(40, max(20, ov.get("dk", 30))),
                        "soru": 25,
                        "reason": f"Geciken ödev: {ov.get('gecikme_gun', 2)} gün gecikti. Eksik kalmaması için hızlı telafi."
                    })

            # 2. Düşük Başarılı Konular
            elif focus_idx == 1:
                # Başarısı düşük derslerden veya az soru çözülen konulardan çek
                for d_key, s_data in analytics["lesson_stats"].items():
                    if selected_lesson and d_key != selected_lesson:
                        continue
                    if s_data["ratio"] < 65 or s_data["total"] < 3:
                        topics = db.ders_konularini_cek(con, d_key) or []
                        for t in topics[:3]:
                            t_konu = t["konu"] if hasattr(t, "__getitem__") else str(t)
                            book = "Konu Pekiştirme"
                            if d_key in self.available_books and self.available_books[d_key]:
                                book = self.available_books[d_key][0]
                            candidates.append({
                                "type": "weak",
                                "badge": "📉 Zayıf Konu",
                                "badge_color": "#d97706",
                                "ders": d_key,
                                "kitap": book,
                                "konu": t_konu,
                                "dk": 30,
                                "soru": 20,
                                "reason": f"{s_data['name']} dersi başarı oranı düşük (%{s_data['ratio']}). Temel kazanımı güçlendir."
                            })

            # 3. Ebbinghaus Aralıklı Tekrar
            elif focus_idx == 2:
                for eb in analytics["ebbinghaus_reviews"]:
                    if selected_lesson and eb["ders"] != selected_lesson:
                        continue
                    book = eb.get("kitap") or "Tekrar Fasikülü"
                    if eb["ders"] in self.available_books and self.available_books[eb["ders"]]:
                        book = self.available_books[eb["ders"]][0]
                    candidates.append({
                        "type": "ebbinghaus",
                        "badge": "🧠 Ebbinghaus Tekrarı",
                        "badge_color": "#7c3aed",
                        "ders": eb["ders"],
                        "kitap": book,
                        "konu": eb["konu"],
                        "dk": eb["recommended_minutes"],
                        "soru": eb["recommended_questions"],
                        "reason": f"{eb['days_ago']} gün önce çalışıldı. {eb['stage']} uyarınca kalıcı hafıza pekiştirmesi."
                    })

            # 4. Hızlı Sınav Takviyesi (ÖSYM ⭐⭐⭐)
            else:
                for gp in analytics["curriculum_gaps"]:
                    if selected_lesson and gp["ders"] != selected_lesson:
                        continue
                    if "5/5" in gp["importance"] or "Yüksek" in gp["importance"]:
                        book = "ÖSYM Soru Bankası"
                        if gp["ders"] in self.available_books and self.available_books[gp["ders"]]:
                            book = self.available_books[gp["ders"]][0]
                        candidates.append({
                            "type": "exam",
                            "badge": "⚡ Sınav Takviyesi",
                            "badge_color": "#059669",
                            "ders": gp["ders"],
                            "kitap": book,
                            "konu": gp["konu"],
                            "dk": 35,
                            "soru": 25,
                            "reason": f"Sınavda çıkma olasılığı yüksek ({gp['questions_exam']}). {gp.get('tip', '')}"
                        })

            # Aynı ders/kitap/konu için birden fazla gecikmiş satır varsa
            # telafi olarak üç kez ödev yazmayı önle.
            from utils.wizard_integrity_v8 import exact_task_key
            unique = {}
            for candidate in candidates:
                key = exact_task_key(candidate.get('ders'), candidate.get('kitap'), candidate.get('konu'))
                if all(key) and key not in unique:
                    unique[key] = candidate
            self.candidates = list(unique.values())
            self._fill_table()
            self._reselect_by_target()

        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Takviye adayları üretilemedi:\n{e}")
        finally:
            con.close()

    def _is_row_checked(self, row: int) -> bool:
        w = self.table.cellWidget(row, 0)
        return bool(w and hasattr(w, "chk") and w.chk.isChecked())

    def _set_row_checked(self, row: int, checked: bool):
        w = self.table.cellWidget(row, 0)
        if w and hasattr(w, "chk"):
            w.chk.blockSignals(True)
            w.chk.setChecked(checked)
            w.chk.blockSignals(False)

    def _on_cell_clicked(self, row, col):
        if col != 0:
            cur = self._is_row_checked(row)
            self._set_row_checked(row, not cur)
            self._update_summary()

    def _fill_table(self):
        self.table.setRowCount(0)
        for i, c in enumerate(self.candidates):
            self.table.insertRow(i)

            # 0: Checkbox (Çoklu Seçim Kutucuğu)
            chk = QCheckBox()
            chk.setStyleSheet("QCheckBox { margin-left: 6px; }")
            w = QWidget()
            l = QHBoxLayout(w)
            l.setContentsMargins(0, 0, 0, 0)
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l.addWidget(chk)
            self.table.setCellWidget(i, 0, w)
            w.chk = chk
            chk.stateChanged.connect(self._update_summary)

            # 1: Badge
            lbl = QLabel(f" {c['badge']} ")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col = c.get("badge_color", "#dc2626")
            lbl.setStyleSheet(f"background: {col}15; color: {col}; border: 1px solid {col}40; border-radius: 4px; font-weight: bold; font-size: 11px;")
            self.table.setCellWidget(i, 1, lbl)

            # 2: Ders
            it_ders = QTableWidgetItem(c["ders"].replace("_", " ").title())
            it_ders.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self.table.setItem(i, 2, it_ders)

            # 3: Kitap
            self.table.setItem(i, 3, QTableWidgetItem(c.get("kitap", "-")))

            # 4: Konu
            it_konu = QTableWidgetItem(c.get("konu", "-"))
            it_konu.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self.table.setItem(i, 4, it_konu)

            # 5: Hedef
            dk = c.get("dk", 30)
            soru = c.get("soru", 20)
            it_h = QTableWidgetItem(f"🎯 ~{soru} Soru • ⏱️ {dk} dk")
            it_h.setForeground(QColor("#059669"))
            self.table.setItem(i, 5, it_h)

            # 6: Gerekçe
            it_r = QTableWidgetItem(c.get("reason", ""))
            it_r.setToolTip(c.get("reason", ""))
            self.table.setItem(i, 6, it_r)

        self.table.resizeColumnsToContents()
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 50)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)

    def _reselect_by_target(self):
        tgt = self.spTarget.value()
        curr_min = 0
        sel_rows = set()
        for i, c in enumerate(self.candidates):
            dk = c.get("dk", 30)
            if curr_min + dk <= tgt + 15:
                sel_rows.add(i)
                curr_min += dk
            elif not sel_rows:
                sel_rows.add(i)
                curr_min += dk
                break

        for r in range(self.table.rowCount()):
            self._set_row_checked(r, r in sel_rows)

        self._update_summary()

    def _toggle_selection(self):
        if self.table.rowCount() == 0:
            return
        all_checked = all(self._is_row_checked(r) for r in range(self.table.rowCount()))
        new_state = not all_checked
        for r in range(self.table.rowCount()):
            self._set_row_checked(r, new_state)
        self._update_summary()

    def _get_selected_indices(self) -> list:
        checked = [r for r in range(self.table.rowCount()) if self._is_row_checked(r)]
        if checked:
            return checked
        return [idx.row() for idx in self.table.selectionModel().selectedRows()]

    def _update_summary(self):
        sel_rows = self._get_selected_indices()
        tot_min = 0
        tot_q = 0
        for r in sel_rows:
            if r < len(self.candidates):
                c = self.candidates[r]
                tot_min += c.get("dk", 30)
                tot_q += c.get("soru", 20)

        saat = tot_min // 60
        dk_mod = tot_min % 60
        time_str = f"{tot_min} dk" if saat == 0 else f"{saat} sa {dk_mod} dk ({tot_min} dk)"

        self.lblSummary.setText(f"Seçilen: {len(sel_rows)} Takviye Ödevi (~{time_str}, ~{tot_q} Soru)")

    def _accept_selection(self):
        sel_rows = self._get_selected_indices()
        if not sel_rows:
            QMessageBox.information(self, "Seçim Yapılmadı", "Lütfen eklemek istediğiniz takviye ödevlerini onay kutusunu (☑️) işaretleyerek seçiniz.")
            return

        final_list = []
        for r in sel_rows:
            if r < len(self.candidates):
                c = self.candidates[r]
                final_list.append({
                    "ders": c["ders"],
                    "kitap": c["kitap"],
                    "konu": c["konu"],
                    "dk": c["dk"],
                    "aciklama": f"[Takviye] {c.get('reason', '')[:60]}"
                })

        self.selected_remedials = final_list
        self.accept()

    def _show_info_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("ℹ️ Akıllı Takviye & Telafi Sistemi Rehberi")
        dlg.resize(640, 580)
        dlg.setStyleSheet("""
            QDialog { background-color: #f8fafc; font-family: 'Segoe UI', system-ui, sans-serif; }
        """)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Header banner
        header = QFrame()
        header.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #15803d, stop:1 #059669);
            border-radius: 8px;
            padding: 12px 16px;
        """)
        h_lay = QVBoxLayout(header)
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(2)
        lbl_h1 = QLabel("🎯 Akıllı Takviye & Telafi Sistemi Rehberi")
        lbl_h1.setStyleSheet("color: white; font-size: 15px; font-weight: bold;")
        lbl_h2 = QLabel("Hedef türleri, Ebbinghaus tekrar modeli ve süre/soru belirleme kriterleri")
        lbl_h2.setStyleSheet("color: #dcfce7; font-size: 11px;")
        h_lay.addWidget(lbl_h1)
        h_lay.addWidget(lbl_h2)
        layout.addWidget(header)

        # Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        content = QWidget()
        cv = QVBoxLayout(content)
        cv.setContentsMargins(0, 4, 0, 4)
        cv.setSpacing(10)

        def add_card(title, text):
            card = QFrame()
            card.setStyleSheet("background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 14px;")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(4)
            t = QLabel(title)
            t.setStyleSheet("font-size: 13px; font-weight: bold; color: #166534;")
            b = QLabel(text)
            b.setStyleSheet("font-size: 12px; color: #334155; line-height: 1.5;")
            b.setWordWrap(True)
            cl.addWidget(t)
            cl.addWidget(b)
            cv.addWidget(card)

        add_card("1. 🎯 Akıllı Takviye ve Telafi Formunun Amacı",
                 "Bu form, öğrencinin çalışma geçmişini analiz ederek eksiklerini tespit eder. "
                 "Amacı öğrenciye rastgele ödev yığmak değil; <b>geciken ödevleri toparlamak</b>, "
                 "<b>unutulmaya başlayan konuları tazelemek</b> ve <b>zayıf kalınan kazanımları güçlendirmektir</b>.")

        add_card("2. 🧠 'Ebbinghaus Aralıklı Tekrar' Nedir ve Nasıl Çalışır?",
                 "Alman psikolog Hermann Ebbinghaus'un bilimsel <b>'Unutma Eğrisi'</b> modeline dayanır.<br/>"
                 "• İnsan beyni yeni öğrendiği bilginin %70'ini ilk günlerde unutur.<br/>"
                 "• Bilginin kalıcı hafızaya kazınması için sistem öğrencinin tamamladığı ödevlerin tarihlerini takip eder.<br/>"
                 "• <b>24 saat, 7. gün, 14. gün ve 30. gün</b> kritik eşiklerine gelen konular otomatik olarak "
                 "<i>'Ebbinghaus Tekrarı'</i> rozetiyle listelenir. Sıfırdan konu çalışmak yerine 20-25 dakikalık hızlı bir testle hafıza kilitlenir.")

        add_card("3. 🚨 'Geciken & Yapılmayan Ödevler' Mantığı",
                 "Öğrenciye geçmişte verilmiş ancak teslim tarihi geçmesine rağmen henüz tamamlanmamış ödevleri listeler. "
                 "Öğrencinin ödev borcunu biriktirmeden hızlıca eritmesi için öncelikli telafi olarak sunulur.")

        add_card("4. 📉 'Düşük Başarılı Konular' ve ⚡ 'Sınav Takviyesi'",
                 "• <b>Düşük Başarılı Konular:</b> Öğrencinin test ve deneme çözümlerinde başarı oranı %65'in altında kalan veya az soru çözülen temel konularıdır.<br/>"
                 "• <b>Sınav Takviyesi (ÖSYM Odaklı):</b> Müfredatta ÖSYM sınavlarında en çok soru çıkan kritik konuları tarar.")

        add_card("5. ⏱️ Takviye Hedefi (Süre ve Soru) Neye Göre Belirlenir?",
                 "Takviye ödevlerinde öğrenciyi bunaltmamak için <b>mikro seanslar (1 Pomodoro = ~25-35 dk)</b> hedeflenir:<br/>"
                 "• <b>Geciken Telafi:</b> ~25 Soru • 30 dk (hızlı borç kapatma).<br/>"
                 "• <b>Zayıf Konu:</b> ~20 Soru • 30 dk (kavrama ve temel kazanım).<br/>"
                 "• <b>Ebbinghaus Tekrarı:</b> ~20 Soru • 25 dk (hafıza tetikleme testi).<br/>"
                 "• <b>Sınav Takviyesi:</b> ~25 Soru • 35 dk (çıkmış soru tarzı pratik).")

        add_card("6. ☑️ Çoklu Seçim ve 'Hedef Süre' Kullanımı",
                 "• <b>Onay Kutuları (☑️):</b> Dilediğiniz takviye ödevlerini kutucuklara tıklayarak tek tek veya çoklu seçebilirsiniz. Satırın herhangi bir yerine tıklamak da kutucuğu açıp kapatır.<br/>"
                 "• <b>Hedef Süre (Spinbox):</b> İstediğiniz çalışma süresini (örn: 60 dk) seçtiğinizde sistem süre bütçesine tam sığacak ödevleri otomatik olarak işaretler.<br/>"
                 "• <b>Tümünü Seç/Kaldır:</b> Listedeki tüm ödevleri tek tıkla topluca işaretler veya temizler.")

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        btnKapat = QPushButton("Anladım, Kapat")
        btnKapat.setFixedHeight(38)
        btnKapat.setCursor(Qt.CursorShape.PointingHandCursor)
        btnKapat.setStyleSheet("""
            QPushButton {
                background: #f1f5f9;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                font-weight: bold;
                color: #334155;
            }
            QPushButton:hover {
                background: #e2e8f0;
            }
        """)
        btnKapat.clicked.connect(dlg.close)
        layout.addWidget(btnKapat)

        dlg.exec()
