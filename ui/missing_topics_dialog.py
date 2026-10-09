from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QPushButton, QTableWidget, QTableWidgetItem, QAbstractItemView, 
    QMessageBox, QWidget, QFrame, QHeaderView, QCheckBox, QProgressBar,
    QLineEdit
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor
import db
from typing import Dict, List, Any, Optional

class MissingTopicsDialog(QDialog):
    """
    Müfredat ve Eksik Konu Analiz Paneli.
    Tüm derslerdeki konuların çalışılma durumunu, ÖSYM sınav önem derecelerini
    ve eksiklik seviyelerini analiz ederek tek tıkla ödev listesine aktarır.
    """
    def __init__(self, ogrenci_id: int, parent=None, available_books=None, active_lesson: str = None):
        super().__init__(parent)
        self.setWindowTitle("⚠️ Müfredat ve Eksik Konu Analiz Paneli")
        self.resize(1100, 720)
        self.ogrenci_id = ogrenci_id
        self.available_books = available_books or {}
        self.active_lesson = active_lesson
        self.all_topics_data: List[Dict[str, Any]] = []
        self.filtered_topics_data: List[Dict[str, Any]] = []
        self.selected_topics: List[Dict[str, Any]] = []

        self._build_ui()
        QTimer.singleShot(100, self._load_curriculum_analysis)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        # --- ÜST BAŞLIK ---
        header = QHBoxLayout()
        header.setSpacing(10)

        lbl_icon = QLabel("⚠️")
        lbl_icon.setStyleSheet("font-size: 32px;")
        header.addWidget(lbl_icon)

        vbox = QVBoxLayout()
        lbl_title = QLabel("Müfredat & Eksik Konu Analiz Paneli")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #b45309;")
        lbl_sub = QLabel("Öğrencinin tüm müfredattaki eksik, yarım ve çalışılmamış konularını sınav ağırlığına göre listeler.")
        lbl_sub.setStyleSheet("color: #64748b; font-size: 12px;")
        vbox.addWidget(lbl_title)
        vbox.addWidget(lbl_sub)
        header.addLayout(vbox)
        header.addStretch(1)

        root.addLayout(header)

        # --- MÜFREDAT TAMAMLAMA İLERLEME ÇUBUĞU KARTI ---
        pbar_card = QFrame()
        pbar_card.setStyleSheet("QFrame { background: #fffbeb; border: 1px solid #fef3c7; border-radius: 8px; padding: 6px; }")
        p_lay = QVBoxLayout(pbar_card)
        p_lay.setContentsMargins(8, 6, 8, 6)
        p_lay.setSpacing(4)

        h_info = QHBoxLayout()
        self.lblProgressText = QLabel("Müfredat Durumu Yükleniyor...")
        self.lblProgressText.setStyleSheet("font-weight: bold; color: #92400e; font-size: 13px;")
        self.lblProgressPercent = QLabel("%0")
        self.lblProgressPercent.setStyleSheet("font-weight: 900; color: #b45309; font-size: 14px;")
        h_info.addWidget(self.lblProgressText)
        h_info.addStretch(1)
        h_info.addWidget(self.lblProgressPercent)
        p_lay.addLayout(h_info)

        self.progressBar = QProgressBar()
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(0)
        self.progressBar.setTextVisible(False)
        self.progressBar.setFixedHeight(8)
        self.progressBar.setStyleSheet("""
            QProgressBar { background-color: #fef3c7; border-radius: 4px; }
            QProgressBar::chunk { background-color: #f59e0b; border-radius: 4px; }
        """)
        p_lay.addWidget(self.progressBar)
        root.addWidget(pbar_card)

        # --- FİLTRE VE ARAMA ÇUBUĞU ---
        filter_frame = QFrame()
        filter_frame.setStyleSheet("QFrame { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; }")
        fl = QHBoxLayout(filter_frame)
        fl.setContentsMargins(10, 8, 10, 8)
        fl.setSpacing(10)

        # Arama
        self.txtSearch = QLineEdit()
        self.txtSearch.setPlaceholderText("🔍 Konu veya ders ara...")
        self.txtSearch.setStyleSheet("background: white; border: 1px solid #cbd5e1; border-radius: 6px; padding: 5px 10px;")
        self.txtSearch.textChanged.connect(self._apply_filters)
        fl.addWidget(self.txtSearch, 2)

        # Ders Seçici
        fl.addWidget(QLabel("<b>Ders:</b>"))
        self.cmbLesson = QComboBox()
        self.cmbLesson.addItem("Tüm Dersler", "")
        self.cmbLesson.setStyleSheet("""
            QComboBox { background: white; border: 1px solid #cbd5e1; border-radius: 6px; padding: 5px 10px; }
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 22px; border: none; background: transparent; }
            QComboBox::down-arrow { border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid #64748b; margin-right: 6px; }
        """)
        self.cmbLesson.currentIndexChanged.connect(self._apply_filters)
        fl.addWidget(self.cmbLesson, 1)

        # Sınav Önemi Filtresi
        fl.addWidget(QLabel("<b>Sınav Önemi:</b>"))
        self.cmbImportance = QComboBox()
        self.cmbImportance.addItems(["Tümü", "🔥 Çok Yüksek (⭐⭐⭐)", "⭐ Orta Ağırlık", "🟢 Standart"])
        self.cmbImportance.setStyleSheet("""
            QComboBox { background: white; border: 1px solid #cbd5e1; border-radius: 6px; padding: 5px 10px; }
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 22px; border: none; background: transparent; }
            QComboBox::down-arrow { border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid #64748b; margin-right: 6px; }
        """)
        self.cmbImportance.currentIndexChanged.connect(self._apply_filters)
        fl.addWidget(self.cmbImportance, 1)

        # Eksik Durumu
        fl.addWidget(QLabel("<b>Durum:</b>"))
        self.cmbStatus = QComboBox()
        self.cmbStatus.addItems(["Tümü (Eksikler)", "🔴 Sadece Hiç Çalışılmamış", "🟡 Sadece Yarım / Düşük Başarı"])
        self.cmbStatus.setStyleSheet("""
            QComboBox { background: white; border: 1px solid #cbd5e1; border-radius: 6px; padding: 5px 10px; }
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 22px; border: none; background: transparent; }
            QComboBox::down-arrow { border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid #64748b; margin-right: 6px; }
        """)
        self.cmbStatus.currentIndexChanged.connect(self._apply_filters)
        fl.addWidget(self.cmbStatus, 1)

        self.btnToggleAll = QPushButton("Tümünü Seç/Kaldır")
        self.btnToggleAll.setStyleSheet("background: white; border: 1px solid #cbd5e1; border-radius: 6px; padding: 5px 10px; font-size: 11px; font-weight: bold;")
        self.btnToggleAll.clicked.connect(self._toggle_selection)
        fl.addWidget(self.btnToggleAll)

        root.addWidget(filter_frame)

        # --- TABLO ---
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "ÖSYM Önemi", "Ders", "Konu Adı", "Mevcut Durum", "Kitap", "Hedef Yük", "Seç"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setStyleSheet("""
            QTableWidget { background: white; gridline-color: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 6px; }
            QHeaderView::section { background-color: #f8fafc; padding: 6px 8px; border: 1px solid #e2e8f0; font-weight: bold; color: #334155; }
            QTableWidget::item { padding: 4px 6px; }
        """)
        self.table.verticalHeader().setVisible(False)
        root.addWidget(self.table, 1)

        # --- ALT BAR ---
        bottom = QHBoxLayout()
        bottom.setSpacing(10)

        self.lblSummary = QLabel("Seçilen: 0 Eksik Konu (~0 dk, ~0 Soru)")
        self.lblSummary.setStyleSheet("font-size: 13px; font-weight: bold; color: #b45309;")
        bottom.addWidget(self.lblSummary)
        bottom.addStretch(1)

        self.btnCancel = QPushButton("Vazgeç")
        self.btnCancel.setStyleSheet("background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px 16px; font-weight: bold; color: #475569;")
        self.btnCancel.clicked.connect(self.reject)
        bottom.addWidget(self.btnCancel)

        self.btnAdd = QPushButton("✅ Seçilen Eksikleri Ödev Olarak Ekle")
        self.btnAdd.setStyleSheet("""
            QPushButton { background-color: #059669; color: white; padding: 9px 20px; font-weight: bold; border-radius: 6px; font-size: 13px; }
            QPushButton:hover { background-color: #047857; }
        """)
        self.btnAdd.clicked.connect(self._accept_selection)
        bottom.addWidget(self.btnAdd)

        root.addLayout(bottom)

    def _load_curriculum_analysis(self):
        if not self.ogrenci_id:
            return

        con = db.get_conn()
        try:
            from utils import ai_recommend

            # 1. Dersleri Doldur (ilk açılışta)
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

            # 2. Öğrencinin geçmiş ödevleri ve koçluk verilerini al
            analytics = ai_recommend.get_comprehensive_student_analytics(con, self.ogrenci_id)
            group = analytics["student"].get("ana_grup", "YKS")
            curriculum = ai_recommend.get_curriculum_dict()

            # Tamamlanan konular kümesi
            completed_set = set()
            for r in con.execute("SELECT ders, konu_ad FROM odev WHERE ogrenci_id=? AND durum IN ('tamam', 'yapildi')", (self.ogrenci_id,)).fetchall():
                completed_set.add(((r["ders"] or "").strip().lower(), (r["konu_ad"] or "").strip()))

            # Başlanan / yarım kalanlar
            started_dict = {}
            for r in con.execute("SELECT ders, konu_ad, durum FROM odev WHERE ogrenci_id=? AND durum NOT IN ('tamam', 'yapildi')", (self.ogrenci_id,)).fetchall():
                k = ((r["ders"] or "").strip().lower(), (r["konu_ad"] or "").strip())
                started_dict[k] = r["durum"]

            # Tüm derslerin müfredat konularını tara
            all_topics = []
            total_curr_count = 0
            total_done_count = 0

            lesson_rows = con.execute("SELECT id, ad FROM ders_tanimlari WHERE aktif=1 ORDER BY siralama").fetchall()
            for l in lesson_rows:
                d_key = l["id"]
                d_name = l["ad"]
                if not ai_recommend._is_lesson_relevant(group, d_key):
                    continue

                topics = db.ders_konularini_cek(con, d_key) or []
                for t in topics:
                    k_name = t["konu"] if hasattr(t, "__getitem__") else str(t)
                    total_curr_count += 1

                    is_completed = (d_key, k_name) in completed_set
                    if is_completed:
                        total_done_count += 1
                        continue # Eksik listesinde tamamlananları varsayılan olarak atla

                    is_started = (d_key, k_name) in started_dict
                    status_text = "🟡 Yarım / Pekiştirilmeli" if is_started else "🔴 Hiç Çalışılmadı"
                    status_type = "started" if is_started else "never"

                    c_info = curriculum.get(k_name, {})
                    importance = c_info.get("importance", "Orta (3/5)")
                    questions = c_info.get("questions", "1 Soru")
                    tip = c_info.get("tip", "")

                    # Kitap belirle
                    book = "Soru Bankası"
                    if d_key in self.available_books and self.available_books[d_key]:
                        book = self.available_books[d_key][0]

                    all_topics.append({
                        "ders": d_key,
                        "ders_name": d_name,
                        "konu": k_name,
                        "status_type": status_type,
                        "status_text": status_text,
                        "importance": importance,
                        "questions": questions,
                        "tip": tip,
                        "kitap": book,
                        "dk": 35,
                        "soru": 25,
                    })

            self.all_topics_data = all_topics

            # Genel ilerleme çubuğunu güncelle
            pct = int(round((total_done_count / total_curr_count * 100))) if total_curr_count > 0 else 0
            self.progressBar.setValue(pct)
            self.lblProgressPercent.setText(f"%{pct}")
            self.lblProgressText.setText(f"Müfredat İlerlemesi: {total_done_count}/{total_curr_count} Konu Tamamlandı ({len(all_topics)} Konu Eksik)")

            self._apply_filters()

        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Müfredat analizi yüklenemedi:\n{e}")
        finally:
            con.close()

    def _apply_filters(self):
        search_txt = self.txtSearch.text().strip().lower()
        sel_lesson = self.cmbLesson.currentData()
        imp_idx = self.cmbImportance.currentIndex()
        status_idx = self.cmbStatus.currentIndex()

        filtered = []
        for t in self.all_topics_data:
            # Ders
            if sel_lesson and t["ders"] != sel_lesson:
                continue

            # Önem
            if imp_idx == 1 and ("5/5" not in t["importance"] and "Yüksek" not in t["importance"]):
                continue
            elif imp_idx == 2 and ("4/5" not in t["importance"] and "Orta" not in t["importance"]):
                continue
            elif imp_idx == 3 and ("3/5" not in t["importance"] and "Standart" not in t["importance"]):
                continue

            # Durum
            if status_idx == 1 and t["status_type"] != "never":
                continue
            elif status_idx == 2 and t["status_type"] != "started":
                continue

            # Metin arama
            if search_txt:
                if search_txt not in t["konu"].lower() and search_txt not in t["ders_name"].lower():
                    continue

            filtered.append(t)

        self.filtered_topics_data = filtered
        self._fill_table()

    def _fill_table(self):
        self.table.setRowCount(0)
        for i, t in enumerate(self.filtered_topics_data):
            self.table.insertRow(i)

            # 0: Önem Rozeti
            is_high = "5/5" in t["importance"] or "Yüksek" in t["importance"]
            b_text = f"🔥 {t['importance']} ({t['questions']})" if is_high else f"⭐ {t['importance']} ({t['questions']})"
            lbl_imp = QLabel(f" {b_text} ")
            col = "#b45309" if is_high else "#475569"
            lbl_imp.setStyleSheet(f"background: {col}15; color: {col}; border: 1px solid {col}40; border-radius: 4px; font-weight: bold; font-size: 11px;")
            self.table.setCellWidget(i, 0, lbl_imp)

            # 1: Ders
            it_ders = QTableWidgetItem(t["ders_name"])
            it_ders.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self.table.setItem(i, 1, it_ders)

            # 2: Konu
            it_konu = QTableWidgetItem(t["konu"])
            it_konu.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            if t.get("tip"):
                it_konu.setToolTip(t["tip"])
            self.table.setItem(i, 2, it_konu)

            # 3: Mevcut Durum
            lbl_st = QLabel(f" {t['status_text']} ")
            s_col = "#dc2626" if t["status_type"] == "never" else "#d97706"
            lbl_st.setStyleSheet(f"background: {s_col}15; color: {s_col}; border-radius: 4px; font-size: 11px; font-weight: bold;")
            self.table.setCellWidget(i, 3, lbl_st)

            # 4: Kitap
            self.table.setItem(i, 4, QTableWidgetItem(t.get("kitap", "-")))

            # 5: Hedef Yük
            it_load = QTableWidgetItem(f"🎯 ~{t['soru']} Soru • ⏱️ {t['dk']} dk")
            it_load.setForeground(QColor("#059669"))
            self.table.setItem(i, 5, it_load)

            # 6: Checkbox
            chk = QCheckBox()
            w = QWidget()
            l = QHBoxLayout(w)
            l.setContentsMargins(0, 0, 0, 0)
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l.addWidget(chk)
            self.table.setCellWidget(i, 6, w)
            w.chk = chk
            chk.stateChanged.connect(self._update_summary)

        self.table.resizeColumnsToContents()
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(6, 45)

        self._update_summary()

    def _toggle_selection(self):
        if self.table.rowCount() == 0:
            return
        w0 = self.table.cellWidget(0, 6)
        tgt = not w0.chk.isChecked() if w0 else True
        for i in range(self.table.rowCount()):
            w = self.table.cellWidget(i, 6)
            if w:
                w.chk.setChecked(tgt)
        self._update_summary()

    def _update_summary(self):
        count = 0
        total_dk = 0
        total_q = 0
        for i in range(self.table.rowCount()):
            w = self.table.cellWidget(i, 6)
            if w and hasattr(w, "chk") and w.chk.isChecked():
                count += 1
                if i < len(self.filtered_topics_data):
                    t = self.filtered_topics_data[i]
                    total_dk += t.get("dk", 35)
                    total_q += t.get("soru", 25)

        saat = total_dk // 60
        dk_mod = total_dk % 60
        time_str = f"{total_dk} dk" if saat == 0 else f"{saat} sa {dk_mod} dk ({total_dk} dk)"

        self.lblSummary.setText(f"Seçilen: {count} Eksik Konu (~{time_str}, ~{total_q} Soru)")

    def _accept_selection(self):
        picked = []
        for i in range(self.table.rowCount()):
            w = self.table.cellWidget(i, 6)
            if w and hasattr(w, "chk") and w.chk.isChecked():
                if i < len(self.filtered_topics_data):
                    t = self.filtered_topics_data[i]
                    picked.append({
                        "ders": t["ders"],
                        "kitap": t["kitap"],
                        "konu": t["konu"],
                        "dk": t["dk"],
                        "aciklama": f"[Müfredat Eksik] ÖSYM Önemi: {t['importance']}"
                    })

        if not picked:
            QMessageBox.information(self, "Seçim Yapılmadı", "Lütfen ödev listesine eklemek istediğiniz eksik konuları seçiniz.")
            return

        self.selected_topics = picked
        self.accept()
