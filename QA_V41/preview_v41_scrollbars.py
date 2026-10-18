"""Optional isolated Qt visual acceptance -- requires installed PyQt6.

Run from the project root:
    python QA_V41/preview_v41_scrollbars.py
No databases, app_settings DB, students, or licence services are loaded.
"""
import os
import sys
import types
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
# In-memory theme settings: prevent any user preference writes.
settings={}
appset=types.ModuleType('ui.app_settings')
appset.ayar_get=lambda k,default=None:settings.get(k) or default
appset.ayar_set=lambda k,v:settings.__setitem__(k,v)
sys.modules['ui.app_settings']=appset
import ui
ui.app_settings=appset

try:
    from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
        QComboBox, QSpinBox, QTableWidget, QTableWidgetItem, QLabel, QTextEdit,
        QListWidget, QScrollArea, QFrame)
except ImportError:
    raise SystemExit('This preview requires PyQt6 on the test computer.')
from ui.theme import tema_presets, tema_apply_preset, apply

app=QApplication(sys.argv)
window=QWidget()
window.setWindowTitle('V41 Theme / Scrollbar QA — no real data')
window.resize(900,650)
lay=QVBoxLayout(window)
row=QHBoxLayout(); lay.addLayout(row)
row.addWidget(QLabel('Tema'))
chooser=QComboBox();chooser.addItems(tema_presets().keys());row.addWidget(chooser)
row.addWidget(QLabel('Kaydırma kalınlığı'))
size=QSpinBox();size.setRange(6,24);size.setValue(12);row.addWidget(size)
row.addStretch()

hint=QLabel('Dikey/yatay çubuk, hover, sürükleme ve tema geçişini kontrol edin. Örnek veri.')
lay.addWidget(hint)

tbl=QTableWidget(70,9)
tbl.setHorizontalHeaderLabels([f'Ders / Alan {n}' for n in range(1,10)])
for r in range(70):
    for c in range(9):
        tbl.setItem(r,c,QTableWidgetItem(f'Örnek satır {r+1} / sütun {c+1}'))
for c in range(9):tbl.setColumnWidth(c,170)
lay.addWidget(tbl,4)

text=QTextEdit(); text.setPlainText('\n'.join(f'Örnek bilgi {i} -- bunu gerçek kayıtlarla karıştırmayın' for i in range(100)))
lay.addWidget(text,2)

lst=QListWidget();lst.addItems([f'Liste örneği {i:02}' for i in range(90)])
lay.addWidget(lst,2)

def refresh():
    tema_apply_preset(chooser.currentText())
    settings['tema_scrollbar']=str(size.value())
    apply(app)

chooser.currentTextChanged.connect(refresh)
size.valueChanged.connect(refresh)
refresh()
window.show()
sys.exit(app.exec())
