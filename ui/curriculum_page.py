# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, 
                             QPushButton, QHeaderView, QCheckBox, QLabel, QInputDialog, QMessageBox, 
                             QComboBox, QFrame, QTabWidget, QListWidget, QGroupBox, QSplitter, QScrollArea)
from PyQt6.QtCore import Qt
import db

class CurriculumPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)
        
        # 1. TAB: Ders Listesi
        try:
            self.tab_list = LessonListPage()
            self.tabs.addTab(self.tab_list, "📋 Ders Listesi")
        except Exception as e:
            self.tabs.addTab(QLabel(f"Hata: {e}"), "Hata")
        
        # 2. TAB: Grup Atama
        try:
            self.tab_mapping = GroupMappingPage()
            self.tabs.addTab(self.tab_mapping, "🔗 Grup Eşleştirmeleri")
        except Exception as e:
             self.tabs.addTab(QLabel(f"Hata: {e}"), "Hata")

    def save(self):
        # Eğer aktif tab "Mapping" ise veya genel kaydet denildiyse
        if hasattr(self, 'tab_mapping'):
            self.tab_mapping.save_current(silent=True)

# --- TAB 1: MEVCUT LİSTE ---
class LessonListPage(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        # Bilgi
        info = QLabel("Sisteme yeni dersler ekleyebilir veya kullanmadığınız dersleri pasife alabilirsiniz.\nÖzel eklenen dersler 'Özel' olarak işaretlenir.")
        info.setStyleSheet("color: #64748b; margin-bottom: 5px;")
        self.layout.addWidget(info)
        
        # Üst Bar
        h = QHBoxLayout()
        h.addStretch()
        
        self.btnAdd = QPushButton("+ Yeni Özel Ders Ekle")
        self.btnAdd.setStyleSheet("background-color: #2563eb; color: white; padding: 6px 15px; border-radius: 6px; font-weight: bold;")
        self.btnAdd.clicked.connect(self.add_lesson)
        h.addWidget(self.btnAdd)
        
        self.layout.addLayout(h)
        
        # Tablo
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "Görünen Ad", "Grup", "Durum", "Tür"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet("""
            QTableWidget { border: 1px solid #e2e8f0; border-radius: 8px; background: white; gridline-color: #f1f5f9; }
            QHeaderView::section { background-color: #f8fafc; padding: 8px; border: none; font-weight: bold; color: #475569; }
        """)
        self.layout.addWidget(self.table)
        
        self.refresh()
        
    def refresh(self):
        conn = db.get_conn()
        try: db.init_curriculum(conn)
        except: pass
        config = db.get_lesson_config(conn)
            
        self.table.setRowCount(0)
        items = sorted(config.values(), key=lambda x: (x['grup'], x['siralama']))
        
        self.table.setRowCount(len(items))
        for r, item in enumerate(items):
            it_id = QTableWidgetItem(item['id'])
            it_id.setFlags(it_id.flags() ^ Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 0, it_id)
            self.table.setItem(r, 1, QTableWidgetItem(item['ad']))
            self.table.setItem(r, 2, QTableWidgetItem(item['grup']))
            
            chk = QCheckBox()
            chk.setChecked(bool(item['aktif']))
            chk.toggled.connect(lambda checked, lid=item['id']: self.toggle_active(lid, checked))
            w = QWidget(); l = QHBoxLayout(w); l.setAlignment(Qt.AlignmentFlag.AlignCenter); l.setContentsMargins(0,0,0,0); l.addWidget(chk)
            self.table.setCellWidget(r, 3, w)
            
            is_custom = bool(item.get('ozel', 0))
            tur_text = "✨ Özel" if is_custom else "🔒 Sistem"
            it_tur = QTableWidgetItem(tur_text)
            it_tur.setForeground(Qt.GlobalColor.blue if is_custom else Qt.GlobalColor.darkGray)
            it_tur.setFlags(it_tur.flags() ^ Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 4, it_tur)
            
    def toggle_active(self, lid, checked):
        try: db.update_lesson_status(lid, checked)
        except: pass
        
    def add_lesson(self):
        name, ok = QInputDialog.getText(self, "Yeni Ders", "Ders Adı:")
        if not ok or not name: return
        groups = ["YKS", "LGS", "Ara Sınıf", "Genel"]
        grup, ok = QInputDialog.getItem(self, "Grup", "Grup:", groups, 0, False)
        if not ok: return
        
        res = db.add_custom_lesson(name.strip(), grup)
        if hasattr(res, '__getitem__') and res[0]:
            QMessageBox.information(self, "Başarılı", res[1])
            self.refresh()
        else:
            QMessageBox.critical(self, "Hata", str(res))

# --- TAB 2: GRUP EŞLEŞTİRME ---
class GroupMappingPage(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        # Sol: Gruplar
        gb_groups = QGroupBox("1. Öğrenci Grubu Seçin")
        v1 = QVBoxLayout(gb_groups)
        self.listGroups = QListWidget()
        
        # Grupları statik yükleyelim (veya db'den distinct çekilebilir)
        # Şimdilik standart listeyi kullanıyoruz.
        self.all_groups = [
            "12-say", "12-ea", "12-söz", "mezun-say", "mezun-ea", "mezun-söz",
            "11-say", "11-ea", "11-söz", "10.sınıf", "9.sınıf",
            "8.sınıf", "7.sınıf", "6.sınıf"
        ]
        self.listGroups.addItems(self.all_groups)
        self.listGroups.currentItemChanged.connect(self.load_mapping)
        v1.addWidget(self.listGroups)
        
        # Sağ: Dersler
        gb_lessons = QGroupBox("2. Görülecek Dersleri İşaretleyin")
        v2 = QVBoxLayout(gb_lessons)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.chkContainer = QWidget()
        self.chkLayout = QVBoxLayout(self.chkContainer)
        self.scroll.setWidget(self.chkContainer)
        
        self.check_map = {} # lid -> QCheckBox
        
        # Butonlar
        h_btn = QHBoxLayout()
        self.btnSave = QPushButton("Değişiklikleri Kaydet")
        self.btnSave.setStyleSheet("background-color: #10b981; color: white; font-weight: bold; padding: 8px;")
        self.btnSave.clicked.connect(self.save_mapping)
        self.btnReset = QPushButton("Varsayılana Dön (Hepsi)")
        self.btnReset.clicked.connect(self.reset_mapping)
        h_btn.addWidget(self.btnReset)
        h_btn.addWidget(self.btnSave)
        
        v2.addWidget(self.scroll)
        v2.addLayout(h_btn)
        
        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(gb_groups)
        splitter.addWidget(gb_lessons)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        
        self.layout.addWidget(splitter)
        
        # Init lesson list
        self.init_lesson_list()

    def init_lesson_list(self):
        # Tüm checkable dersleri yükle
        config = db.get_lesson_config()
        # Aktif olanlar
        items = sorted([v for k,v in config.items() if v['aktif']], key=lambda x: (x['grup'], x['ad']))
        
        # Temizle
        for i in reversed(range(self.chkLayout.count())): 
            self.chkLayout.itemAt(i).widget().setParent(None)
        self.check_map = {}
        
        last_grp = ""
        for item in items:
            lid = item['id']
            # Grup başlığı
            if item['grup'] != last_grp:
                lbl = QLabel(f"--- {item['grup']} ---")
                lbl.setStyleSheet("font-weight: bold; color: #64748b; margin-top: 5px;")
                self.chkLayout.addWidget(lbl)
                last_grp = item['grup']
                
            chk = QCheckBox(item['ad'])
            self.chkLayout.addWidget(chk)
            self.check_map[lid] = chk
            
        self.chkLayout.addStretch()

    def load_mapping(self, current_item, previous_item):
        if not current_item: return
        group_name = current_item.text()
        
        # DB'den yüklü olanları çek
        db.init_group_lessons(db.get_conn()) # ensure table
        selected_ids = db.get_lessons_for_group(group_name)
        
        # Eğer özel ayar yoksa (liste boşsa), VARSAYILANLARI seçili getir
        if not selected_ids:
            # Grup Hangi kategoride? (Basit Mapping)
            ana_grup = "YKS" # Default
            groups_map = {
                "LGS": ["8.sınıf", "7.sınıf", "6.sınıf"],
                "Ara Sınıf": ["11-say", "11-ea", "11-söz", "10.sınıf", "9.sınıf"],
                "YKS": ["mezun-say", "mezun-ea", "mezun-söz", "12-say", "12-ea", "12-söz"]
            }
            for k, v in groups_map.items():
                if group_name in v:
                    ana_grup = k
                    break
            
            # DB'deki default listeden çek
            defaults = []
            if hasattr(db, 'DEFAULT_GRUP_DERSLER'):
                defaults = db.DEFAULT_GRUP_DERSLER.get(ana_grup, [])
            
            # Checkboxları ayarla
            for lid, chk in self.check_map.items():
                chk.setChecked(lid in defaults)
                
            self.btnSave.setText("Değişiklikleri Kaydet (Şu an Varsayılan)")
        else:
            # Özel ayar varsa onları yükle
            for lid, chk in self.check_map.items():
                chk.setChecked(lid in selected_ids)
            self.btnSave.setText("Değişiklikleri Kaydet")

    def save_mapping(self):
        self.save_current(silent=False)

    def save_current(self, silent=False):
        item = self.listGroups.currentItem()
        if not item: 
            if not silent: QMessageBox.warning(self, "Uyarı", "Grup seçiniz.")
            return
        
        group_name = item.text()
        selected_ids = [lid for lid, chk in self.check_map.items() if chk.isChecked()]
        
        try:
            db.set_lessons_for_group(group_name, selected_ids)
            if not silent:
                QMessageBox.information(self, "Başarılı", f"'{group_name}' grubu için {len(selected_ids)} ders atandı.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))
            
    def reset_mapping(self):
        # Hepsini seç ve kaydet (veya sil)
        # Logiğimiz: DB'de kayıt varsa özelleştirilmiş, yoksa hepsi.
        # Varsayılana dönmek DB'den silmek demektir.
        item = self.listGroups.currentItem()
        if not item: return
        
        group_name = item.text()
        try:
            # Boş liste gönderirsek siler mi? implementation'a bağlı.
            # db.set_lessons_for_group koduna bakalım: yes, delete then insert if list not empty.
            # So sending empty list means "NO LESSONS"? Or "DEFAULT"?
            # db.py'da get_student_curriculum: if not ozel_liste -> return ALL.
            # Wait, get_lessons_for_group returns [] if empty.
            # set_lessons_for_group([], empty_list) delete rows.
            # So if rows are deleted, get_student_curriculum returns ALL.
            
            db.set_lessons_for_group(group_name, []) 
            
            # UI update: Select All
            for lid, chk in self.check_map.items():
                chk.setChecked(True)
                
            QMessageBox.information(self, "Sıfırlandı", f"'{group_name}' grubu varsayılana döndürüldü (Tüm dersler aktif).")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))
