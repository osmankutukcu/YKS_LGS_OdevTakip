# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QListWidget, QListWidgetItem, QMessageBox, QInputDialog, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt
from utils import settings as appset
import json

# Varsayılanlar (DB veya Settings boşsa)
DEFAULT_CONFIG = {
    "TYT": ["Türkçe", "Sosyal", "Matematik", "Fen"],
    "AYT": ["Matematik", "Fizik", "Kimya", "Biyoloji", "Edebiyat", "Tarih", "Coğrafya", "Felsefe", "Din", "Dil"],
    "LGS": ["Türkçe", "Matematik", "Fen", "İnkılap", "Din", "İngilizce"],
    "KDS": ["Türkçe", "Matematik", "Fen", "Sosyal"],
}

class TrialExamSettingsDialog(QDialog):
    """
    Deneme Sınavı Ayarları:
    - Sınav Türleri (TYT, AYT, LGS...) ekle/sil.
    - Her tür için Dersler ekle/sil/sırala.
    Ayarlar 'trial_exam_config' anahtarıyla json olarak saklanır.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Deneme Sınavı Ayarları")
        self.resize(800, 600)
        self.config = self._load_config()
        self.last_selected_type = None # Track previous selection for saving
        self._setup_ui()

    def _load_config(self):
        saved = appset.ayar_get("trial_exam_config")
        if saved:
            try:
                return json.loads(saved)
            except:
                pass
        return DEFAULT_CONFIG.copy()

    def _save_config(self):
        appset.ayar_set("trial_exam_config", json.dumps(self.config, ensure_ascii=False))

    def _setup_ui(self):
        # Ana layout'u en sonda self'e atayacağız.
        # Ara layoutlar parent=None olmalı.
        content_layout = QHBoxLayout() # self OLMAMALI

        # --- SOL: Sınav Türleri ---
        left_grp = QGroupBox("Sınav Türleri")
        l_lay = QVBoxLayout(left_grp)
        
        self.lst_types = QListWidget()
        self.lst_types.addItems(list(self.config.keys()))
        self.lst_types.currentRowChanged.connect(self._on_type_selected)
        l_lay.addWidget(self.lst_types)

        btn_box_l = QHBoxLayout()
        btn_add_type = QPushButton("+ Ekle")
        btn_del_type = QPushButton("- Sil")
        btn_add_type.clicked.connect(self._add_type)
        btn_del_type.clicked.connect(self._del_type)
        btn_box_l.addWidget(btn_add_type)
        btn_box_l.addWidget(btn_del_type)
        l_lay.addLayout(btn_box_l)
        
        l_lay.addLayout(btn_box_l)
        
        content_layout.addWidget(left_grp, 1)

        # --- SAĞ: Dersler (Sıralı Liste) ---
        right_grp = QGroupBox("Dersler (Sırayla)")
        r_lay = QVBoxLayout(right_grp)

        self.lst_subjects = QListWidget()
        self.lst_subjects.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        r_lay.addWidget(self.lst_subjects)
        
        r_lay.addWidget(QLabel("Derslerin sırasını sürükleyerek değiştirebilirsiniz."))

        btn_box_r = QHBoxLayout()
        btn_add_sub = QPushButton("+ Ders Ekle")
        btn_del_sub = QPushButton("- Ders Sil")
        btn_rename_sub = QPushButton("Ad Değiştir")
        
        btn_add_sub.clicked.connect(self._add_subj)
        btn_del_sub.clicked.connect(self._del_subj)
        btn_rename_sub.clicked.connect(self._rename_subj)
        
        btn_box_r.addWidget(btn_add_sub)
        btn_box_r.addWidget(btn_del_sub)
        btn_box_r.addWidget(btn_rename_sub)
        r_lay.addLayout(btn_box_r)

        r_lay.addLayout(btn_box_r)

        content_layout.addWidget(right_grp, 2)
        
        # --- BUTONLAR ---
        # --- BUTONLAR ---
        # main_layout = QVBoxLayout() -> Gereksiz, siliyoruz
        # main_layout.addLayout(layout)
        
        h_btns = QHBoxLayout()
        h_btns.addStretch()
        
        btn_reset = QPushButton("Varsayılanlara Dön")
        btn_reset.setStyleSheet("color: red;")
        btn_reset.clicked.connect(self._reset_defaults)
        
        btn_save = QPushButton("Kaydet ve Kapat")
        btn_save.setStyleSheet("font-weight: bold; padding: 6px 12px;")
        btn_save.clicked.connect(self.accept)

        h_btns.addWidget(btn_reset)
        h_btns.addWidget(btn_save)
        
        # main_layout.addLayout(h_btns) -> HATA: main_layout artık yok, bu satır silinmeli
        
        # Wrapper widget needed if we used main_layout as outer, 
        # but here we can just set layout to self if we restructure slightly.
        # Let's fix the layout structure:
        # self -> VBox -> [HBox(Left, Right), HBox(Buttons)]
        
        final_layout = QVBoxLayout(self)
        final_layout.addLayout(content_layout)
        final_layout.addLayout(h_btns)
        
        # Select first
        if self.lst_types.count() > 0:
            self.lst_types.setCurrentRow(0)

    # --- EVENTS ---

    def _on_type_selected(self, row):
        if row < 0:
            self.lst_subjects.clear()
            self.last_selected_type = None
            return
            
        new_type_name = self.lst_types.item(row).text()
        
        # 1. Save old type if exists
        if self.last_selected_type and self.last_selected_type in self.config:
            # Mevcut listedeki dersleri eski türe kaydet
            current_subjects = [self.lst_subjects.item(i).text() for i in range(self.lst_subjects.count())]
            self.config[self.last_selected_type] = current_subjects
            
        # 2. Load new type
        subjects = self.config.get(new_type_name, [])
        self.lst_subjects.clear()
        self.lst_subjects.addItems(subjects)
        
        # 3. Update tracker
        self.last_selected_type = new_type_name

    def _save_current_subjects(self):
        # Bu metod artık sadece manuel ekleme/silme butonlarında çağrılıyor.
        # Drag/Drop sonrası otomatik çağrılmıyor (ancak _on_type_selected veya accept bunu halleder).
        # Yine de güvende olmak için:
        if self.last_selected_type:
            new_list = [self.lst_subjects.item(i).text() for i in range(self.lst_subjects.count())]
            self.config[self.last_selected_type] = new_list

    def _add_type(self):
        text, ok = QInputDialog.getText(self, "Yeni Sınav Türü", "Tür Adı (Örn: LGS-Sözel):")
        if ok and text.strip():
            name = text.strip()
            if name in self.config:
                QMessageBox.warning(self, "Hata", "Bu tür zaten var.")
                return
            self.config[name] = []
            self.lst_types.addItem(name)
            self.lst_types.setCurrentRow(self.lst_types.count()-1)

    def _del_type(self):
        row = self.lst_types.currentRow()
        if row < 0: return
        name = self.lst_types.item(row).text()
        
        if QMessageBox.question(self, "Sil", f"'{name}' türünü silmek istediğinize emin misiniz?") == QMessageBox.StandardButton.Yes:
            del self.config[name]
            self.lst_types.takeItem(row)

    def _add_subj(self):
        row = self.lst_types.currentRow()
        if row < 0: return
        
        text, ok = QInputDialog.getText(self, "Yeni Ders", "Ders Adı:")
        if ok and text.strip():
            self.lst_subjects.addItem(text.strip())
            self._save_current_subjects()

    def _del_subj(self):
        row = self.lst_subjects.currentRow()
        if row < 0: return
        self.lst_subjects.takeItem(row)
        self._save_current_subjects()

    def _rename_subj(self):
        row = self.lst_subjects.currentRow()
        if row < 0: return
        old_text = self.lst_subjects.item(row).text()
        
        text, ok = QInputDialog.getText(self, "Ders Adı Değiştir", "Yeni Ad:", text=old_text)
        if ok and text.strip():
            self.lst_subjects.item(row).setText(text.strip())
            self._save_current_subjects()

    def _reset_defaults(self):
        if QMessageBox.question(self, "Sıfırla", "Tüm ayarlar varsayılan değerlere dönecek. Emin misiniz?") == QMessageBox.StandardButton.Yes:
            self.config = DEFAULT_CONFIG.copy()
            self._save_config() # save immediately? or wait for accept?
                                # Logic says wait, but refresh UI
            self.lst_types.clear()
            self.lst_types.addItems(list(self.config.keys()))
            if self.lst_types.count() > 0:
                self.lst_types.setCurrentRow(0)

    def accept(self):
        # 1. Anlık görünümü (seçili türü) config'e zorla kaydet
        # Bu, _save_current_subjects veya eventlerin kaçırılması durumunda garantidir.
        row = self.lst_types.currentRow()
        if row >= 0:
            type_name = self.lst_types.item(row).text()
            # Eğer silinmediyse
            if type_name in self.config:
                current_subjects = [self.lst_subjects.item(i).text() for i in range(self.lst_subjects.count())]
                self.config[type_name] = current_subjects

        # 2. Config'i DB'ye yaz
        try:
            self._save_config()
            super().accept()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Ayarlar kaydedilemedi: {e}")
