# -*- coding: utf-8 -*-
"""Real-device PyQt preview. Uses only fictional data and in-memory settings.

Run: python QA_V39/preview_popup_windows_v39.py
Requires PyQt6. No real student data, no database, no saves.
"""
import sys
import types
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
settings = {'tema':'açık', 'tema_mod':'açık'}
stub = types.ModuleType('ui.app_settings')
stub.ayar_get = lambda key, default=None: settings.get(key) or default
stub.ayar_set = lambda key, value: settings.__setitem__(key,str(value))
sys.modules['ui.app_settings'] = stub

from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel,
    QPushButton, QComboBox, QMenu, QMessageBox, QErrorMessage, QLineEdit)
from ui import theme
from ui.progress import IlerlemePenceresi

app = QApplication(sys.argv)
window = QWidget()
window.setWindowTitle('V39 • Popup / Bildirim Tema Testi (örnek veriler)')
layout = QVBoxLayout(window)
layout.addWidget(QLabel('Tema değiştirerek sağ tık menüsü, özel dialog ve mesaj kutusunu deneyin.'))
selector = QComboBox(window)
selector.addItems(theme.tema_presets())
selector.setCurrentText('Cloud Light')
layout.addWidget(selector)


def apply_name(name):
    theme.tema_apply_preset(name)
    theme.apply(app)

selector.currentTextChanged.connect(apply_name)
result = QLabel('Bu örnekte gerçek öğrenci verisi ve veritabanı kullanılmaz.')


def open_menu():
    menu = QMenu(window)
    menu.setStyleSheet('QMenu { background:#ffffff; padding:6px; } QMenu::item { padding:8px 14px; }')
    action = menu.addAction('Örnek ödev işlemi')
    action.triggered.connect(lambda:result.setText('Menü aksiyonu çalıştı.'))
    menu.addAction('Devre dışı seçenek').setEnabled(False)
    menu.addSeparator()
    menu.addAction('Kapat')
    menu.exec(menu_button.mapToGlobal(menu_button.rect().bottomLeft()))

menu_button=QPushButton('Açılır menü (açık zemin testi)')
menu_button.clicked.connect(open_menu)
layout.addWidget(menu_button)


def open_box():
    box=QMessageBox(window)
    box.setWindowTitle('Örnek uyarı')
    box.setText('Tema değiştirildiğinde bütün metinler ve düğmeler görünür olmalıdır.')
    box.setInformativeText('Öğrenci verisi içermeyen örnek mesaj.')
    box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    box.setDefaultButton(QMessageBox.StandardButton.No)
    box.open()
    window.v39_box=box

button=QPushButton('Açık kalan Evet / Hayır diyalogu')
button.clicked.connect(open_box)
layout.addWidget(button)


def open_error():
    err=QErrorMessage(window)
    err.setWindowTitle('Örnek ayrıntılı hata')
    err.showMessage('İşlem sırasında örnek bir hata oluştu.')
    window.v39_error=err

button=QPushButton('QErrorMessage • Hata örneği')
button.clicked.connect(open_error)
layout.addWidget(button)


def open_progress():
    dlg=IlerlemePenceresi('Örnek işlem sürüyor...', window)
    dlg.guncelle(42,'42 örnek kayıt incelendi (gerçek veri yok)')
    dlg.show()
    window.v39_progress=dlg

button=QPushButton('Özel ilerleme penceresi (tema canlı yenileme)')
button.clicked.connect(open_progress)
layout.addWidget(button)

field=QLineEdit(window)
field.setPlaceholderText('Yazı/zemin/odak kontrastı denemesi')
layout.addWidget(field)
layout.addWidget(result)
apply_name(selector.currentText())
window.resize(560, 370)
window.show()
sys.exit(app.exec())
