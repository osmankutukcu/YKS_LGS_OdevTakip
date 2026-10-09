# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, 
    QListWidget, QListWidgetItem, QCheckBox, 
    QPushButton, QLabel, QDialogButtonBox, QMessageBox, QFrame,
    QAbstractItemView
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QFont, QColor
import db

class StudentSelectionDialog(QDialog):
    """
    Hızlı PDF ve Toplu Rapor için Gelişmiş Öğrenci Seçim Diyaloğu.
    - Hızlı filtre butonları (Tümü, Gecikenler, Aktif Ödevliler, Temizle)
    - Canlı anlık arama
    - Öğrenci durum rozetleri (Grup, Aktif Ödev, Gecikme)
    - Birebir uyumlu get_data() arayüzü: (selected_students, auto_save, print_requested)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📄 Hızlı PDF Raporu - Öğrenci Seçimi")
        self.resize(560, 700)
        self.selected_students = [] # List of (id, name)
        self.auto_save = True
        self.print_requested = False
        
        # UI Setup
        self.init_ui()
        self.load_students()

    def init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
            }
            QFrame#HeaderCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e293b, stop:1 #334155);
                border-radius: 10px;
                padding: 12px;
            }
            QLabel#HeaderTitle {
                color: #ffffff;
                font-size: 16px;
                font-weight: bold;
            }
            QLabel#HeaderSub {
                color: #94a3b8;
                font-size: 12px;
            }
            QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 10px 14px;
                background-color: #ffffff;
                font-size: 13px;
                color: #0f172a;
            }
            QLineEdit:focus {
                border: 2px solid #3b82f6;
            }
            QListWidget {
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                background-color: #ffffff;
                font-size: 13px;
                outline: none;
                padding: 4px;
            }
            QListWidget::item {
                padding: 10px 12px;
                border-bottom: 1px solid #f1f5f9;
                border-radius: 6px;
                margin-bottom: 2px;
            }
            QListWidget::item:selected {
                background-color: #eff6ff;
                color: #1e3a8a;
                border-left: 4px solid #3b82f6;
                font-weight: 600;
            }
            QListWidget::item:hover {
                background-color: #f8fafc;
            }
            QCheckBox {
                spacing: 8px;
                font-size: 13px;
                color: #334155;
                font-weight: 500;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
            }
            QPushButton.filterBtn {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 600;
                color: #475569;
            }
            QPushButton.filterBtn:hover {
                background-color: #f1f5f9;
                border-color: #94a3b8;
                color: #1e293b;
            }
            QPushButton[text="OK"], QPushButton[text="Tamam"] {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 9px 20px;
                font-weight: 600;
            }
            QPushButton[text="OK"]:hover, QPushButton[text="Tamam"]:hover {
                background-color: #1d4ed8;
            }
            QPushButton[text="Cancel"], QPushButton[text="İptal"] {
                background-color: #ffffff;
                color: #475569;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 9px 18px;
                font-weight: 600;
            }
            QPushButton[text="Cancel"]:hover, QPushButton[text="İptal"]:hover {
                background-color: #f1f5f9;
            }
            QPushButton#btnPrint { 
                background-color: #10b981; 
                color: white; 
                border: none;
                border-radius: 6px;
                padding: 9px 20px;
                font-weight: 600;
            }
            QPushButton#btnPrint:hover {
                background-color: #059669;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header Card
        header_card = QFrame()
        header_card.setObjectName("HeaderCard")
        h_lay = QVBoxLayout(header_card)
        h_lay.setContentsMargins(12, 10, 12, 10)
        h_lay.setSpacing(4)
        
        lbl_title = QLabel("📑 Hızlı PDF Rapor Oluşturucu")
        lbl_title.setObjectName("HeaderTitle")
        lbl_sub = QLabel("Raporlanacak öğrencileri filtreleyin veya seçin. Birden fazla seçim yapabilirsiniz.")
        lbl_sub.setObjectName("HeaderSub")
        h_lay.addWidget(lbl_title)
        h_lay.addWidget(lbl_sub)
        layout.addWidget(header_card)

        # Search Box
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Öğrenci adı, soyadı veya grup ile ara...")
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.textChanged.connect(self.filter_students)
        layout.addWidget(self.txt_search)

        # Quick Preset Buttons Bar
        preset_bar = QHBoxLayout()
        preset_bar.setSpacing(8)

        self.btn_sel_all = QPushButton("🌟 Tümünü Seç")
        self.btn_sel_all.setProperty("class", "filterBtn")
        self.btn_sel_all.clicked.connect(self.select_all_visible)
        preset_bar.addWidget(self.btn_sel_all)

        self.btn_sel_delayed = QPushButton("⚠️ Gecikenler")
        self.btn_sel_delayed.setProperty("class", "filterBtn")
        self.btn_sel_delayed.setToolTip("Gecikmiş ödevi bulunan öğrencileri otomatik seç")
        self.btn_sel_delayed.clicked.connect(self.select_delayed_students)
        preset_bar.addWidget(self.btn_sel_delayed)

        self.btn_sel_active = QPushButton("📋 Aktif Ödevliler")
        self.btn_sel_active.setProperty("class", "filterBtn")
        self.btn_sel_active.setToolTip("Aktif (tamamlanmamış) ödevi olanları seç")
        self.btn_sel_active.clicked.connect(self.select_active_students)
        preset_bar.addWidget(self.btn_sel_active)

        self.btn_clear_sel = QPushButton("🧹 Temizle")
        self.btn_clear_sel.setProperty("class", "filterBtn")
        self.btn_clear_sel.clicked.connect(self.clear_selection)
        preset_bar.addWidget(self.btn_clear_sel)

        layout.addLayout(preset_bar)

        # List Widget - MULTI SELECT
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.itemSelectionChanged.connect(self._update_selection_counter)
        layout.addWidget(self.list_widget, 1)

        # Info & Counter Row
        counter_row = QHBoxLayout()
        self.lbl_counter = QLabel("0 öğrenci seçildi")
        self.lbl_counter.setStyleSheet("font-weight: 600; color: #2563eb;")
        counter_row.addWidget(self.lbl_counter)
        counter_row.addStretch()
        layout.addLayout(counter_row)

        # Checkbox (Auto Save)
        self.chk_auto_save = QCheckBox("Raporları otomatik olarak masaüstüne kaydet (Odev_Raporlari)")
        self.chk_auto_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_auto_save.setToolTip("Seçilirse, PDF dosyaları Masaüstü/Odev_Raporlari klasörüne 'Ad_Soyad_ID.pdf' formatında kaydedilir.")
        self.chk_auto_save.setChecked(True)
        layout.addWidget(self.chk_auto_save)

        # Action Buttons
        btn_box = QDialogButtonBox()
        self.btn_ok = btn_box.addButton("📄 PDF Oluştur", QDialogButtonBox.ButtonRole.AcceptRole)
        self.btn_cancel = btn_box.addButton("İptal", QDialogButtonBox.ButtonRole.RejectRole)
        
        self.btn_print = QPushButton("🖨️ Yazdır")
        self.btn_print.setObjectName("btnPrint")
        self.btn_print.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_print.clicked.connect(self.accept_print)
        btn_box.addButton(self.btn_print, QDialogButtonBox.ButtonRole.ActionRole)

        btn_box.accepted.connect(self.accept_selection)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        # Data Holder
        self.all_students = []  # list of dicts with id, full_name, display, geciken_odev, aktif_odev
        self.current_filtered = []

    def load_students(self):
        try:
            con = db.get_conn()
            rows = con.execute("""
                SELECT o.id, o.ad, o.soyad, 
                       COALESCE(o.ana_grup, '') as ana_grup, 
                       COALESCE(o.alt_grup, '') as alt_grup,
                       COUNT(od.id) as total_odev,
                       SUM(CASE WHEN od.durum NOT IN ('Tamamlandı', 'tamam', 'ok') AND (od.silindi = 0 OR od.silindi IS NULL) THEN 1 ELSE 0 END) as aktif_odev,
                       SUM(CASE WHEN od.durum IN ('Gecikti', 'gecikti') OR (od.durum NOT IN ('Tamamlandı', 'tamam', 'ok') AND date(k.bitis_tarihi) < date('now')) THEN 1 ELSE 0 END) as geciken_odev
                FROM ogrenci o
                LEFT JOIN odev od ON od.ogrenci_id = o.id AND (od.silindi = 0 OR od.silindi IS NULL)
                LEFT JOIN odev_kume k ON k.id = od.kume_id
                WHERE o.aktif = 1 OR o.aktif IS NULL
                GROUP BY o.id
                ORDER BY o.ad, o.soyad
            """).fetchall()
            
            self.all_students = []
            for r in rows:
                full_name = f"{r['ad']} {r['soyad']}".strip()
                grp_info = f" • {r['ana_grup']}" if r['ana_grup'] else ""
                if r['alt_grup']:
                    grp_info += f" ({r['alt_grup']})"
                
                aktif = int(r['aktif_odev'] or 0)
                geciken = int(r['geciken_odev'] or 0)
                
                tags = []
                if geciken > 0:
                    tags.append(f"⚠️ {geciken} Gecikme")
                elif aktif > 0:
                    tags.append(f"📋 {aktif} Aktif")
                else:
                    tags.append("✅ Görev Yok")

                tag_str = " | ".join(tags)
                display = f"{full_name}{grp_info}   [{tag_str}]"
                
                self.all_students.append({
                    "id": r["id"],
                    "name": full_name,
                    "display": display,
                    "aktif_odev": aktif,
                    "geciken_odev": geciken
                })
            
            self.update_list(self.all_students)
            
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Öğrenci verileri yüklenirken hata oluştu:\n{e}")

    def update_list(self, filtered_data):
        self.list_widget.clear()
        self.current_filtered = filtered_data
        for item_data in filtered_data:
            item = QListWidgetItem(item_data["display"])
            item.setData(Qt.ItemDataRole.UserRole, item_data["id"])
            item.setData(Qt.ItemDataRole.UserRole + 1, item_data["name"])
            item.setData(Qt.ItemDataRole.UserRole + 2, item_data["geciken_odev"])
            item.setData(Qt.ItemDataRole.UserRole + 3, item_data["aktif_odev"])
            
            if item_data["geciken_odev"] > 0:
                item.setForeground(QColor("#b91c1c"))
            self.list_widget.addItem(item)
        self._update_selection_counter()

    def filter_students(self, text):
        text = text.lower().strip()
        if not text:
            self.update_list(self.all_students)
            return
            
        filtered = []
        for s in self.all_students:
            if text in s["display"].lower() or str(s["id"]) == text:
                filtered.append(s)
        self.update_list(filtered)

    def select_all_visible(self):
        self.list_widget.selectAll()

    def clear_selection(self):
        self.list_widget.clearSelection()

    def select_delayed_students(self):
        self.list_widget.clearSelection()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            geciken = item.data(Qt.ItemDataRole.UserRole + 2) or 0
            if geciken > 0:
                item.setSelected(True)

    def select_active_students(self):
        self.list_widget.clearSelection()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            aktif = item.data(Qt.ItemDataRole.UserRole + 3) or 0
            if aktif > 0:
                item.setSelected(True)

    def _update_selection_counter(self):
        count = len(self.list_widget.selectedItems())
        total = self.list_widget.count()
        self.lbl_counter.setText(f"Seçilen: {count} / {total} öğrenci")

    def accept_print(self):
        """Action for Print Button"""
        self.print_requested = True
        self.accept_selection()

    def accept_selection(self):
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen en az bir öğrenci seçin.")
            return

        self.selected_students = []
        for item in selected_items:
            sid = item.data(Qt.ItemDataRole.UserRole)
            name = item.data(Qt.ItemDataRole.UserRole + 1)
            self.selected_students.append((sid, name))
            
        self.auto_save = self.chk_auto_save.isChecked()
        self.accept()

    def get_data(self):
        """Returns (list_of_tuples(id, name), auto_save_bool, print_requested_bool)"""
        return self.selected_students, self.auto_save, self.print_requested
