# -*- coding: utf-8 -*-
"""Visual QA for Windows/macOS; SYNTHETIC DATA ONLY, no student DB use.

Run: python QA_V38/preview_notification_windows_v38.py
Requires PyQt6. It deliberately stubs settings so theme selections are not saved.
"""
import sys
import types
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# In-memory preferences: do not open or modify user/project settings or database.
settings = {'tema':'açık','tema_mod':'açık'}
stub = types.ModuleType('ui.app_settings')
stub.ayar_get = lambda name, default=None: settings.get(name) or default
stub.ayar_set = lambda name,value: settings.__setitem__(name, str(value))
sys.modules['ui.app_settings'] = stub

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel,
    QComboBox, QPushButton, QMessageBox, QInputDialog, QProgressDialog, QCheckBox)
from ui import theme
from ui.toast import show_toast

app = QApplication(sys.argv)
win = QWidget()
win.setWindowTitle('V38 – Bildirim tema testi (örnek veriler)')
lay = QVBoxLayout(win)
lay.addWidget(QLabel('Tema değiştirip aşağıdaki mesaj türlerini kontrol edin.\nBu ekran öğrenci veya ödev verisi kullanmaz.'))
selector = QComboBox()
selector.addItems(theme.tema_presets().keys())
selector.setCurrentText('Cloud Light')
lay.addWidget(selector)


def set_theme(name):
    theme.tema_apply_preset(name)  # in-memory stub; never saved to project database
    theme.apply(app)

selector.currentTextChanged.connect(set_theme)


def add_button(title, func):
    b = QPushButton(title)
    b.clicked.connect(func)
    lay.addWidget(b)


def show_info():
    box = QMessageBox(win)
    box.setIcon(QMessageBox.Icon.Information)
    box.setWindowTitle('Bilgi • V38 testi')
    box.setText('Seçili temada hem başlık hem mesaj hem butonlar okunmalı.')
    box.setInformativeText('Bu alanda uzun bir açıklama veya bağlantı olabilir.')
    box.setDetailedText('Detaylar bölümü açıldığında metin, kaydırma ve kopyalama düzgün görünmeli.\nÖrnek değer: 123')
    box.setCheckBox(QCheckBox('Bir daha gösterme (yalnızca örnek)'))
    box.open()  # leaves main window available to change theme while dialog is visible
    win.active_test_box = box


def show_question():
    reply = QMessageBox.question(win, 'Onay • V38 testi', 'Bu örnek işlemi onaylıyor musunuz?',
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No)
    result.setText('Onay yanıtı: ' + ('Evet' if reply == QMessageBox.StandardButton.Yes else 'Hayır'))


def show_input():
    value, ok = QInputDialog.getText(win, 'Giriş • V38 testi', 'Örnek metin:')
    result.setText('Girdi kabul edildi: ' + ('Evet' if ok else 'Hayır'))


def show_progress():
    dlg = QProgressDialog('Örnek çalışma sürüyor…', 'İptal', 0, 100, win)
    dlg.setMinimumDuration(0)
    dlg.setWindowModality(Qt.WindowModality.NonModal)
    dlg.setValue(41)
    dlg.show()
    win.active_progress = dlg

add_button('Bilgi + ayrıntılar + checkbox (modeless)', show_info)
add_button('Evet / Hayır (varsayılan Hayır)', show_question)
add_button('Metin giriş diyaloğu', show_input)
add_button('İlerleme / İptal', show_progress)
add_button('Başarı toast', lambda: show_toast(win,'Kayıt başarılı (örnek)',kind='success',duration_ms=4500))
add_button('Uyarı toast', lambda: show_toast(win,'Örnek uyarı',kind='warn',duration_ms=4500))
result = QLabel('Örnek kullanıcı yanıtı burada görünecek.')
lay.addWidget(result)
set_theme(selector.currentText())
win.resize(480, 480)
win.show()
sys.exit(app.exec())
