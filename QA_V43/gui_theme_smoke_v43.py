# -*- coding: utf-8 -*-
"""Optional synthetic PyQt6 preview: no real accounts, databases or application settings.

Run on Windows/macOS with PyQt6 available:
    python QA_V43/gui_theme_smoke_v43.py
Optionally use --all-screenshots (saves all 33 themes instead of 4 samples).
The preview generates synthetic data only and is NOT a substitute for testing
all live application windows in the actual program.
"""
from __future__ import annotations
import sys
import json
import types
import importlib.util
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=Path(__file__).resolve().parent / 'local_gui_preview'

try:
    from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QLineEdit, QComboBox, QTableWidget,
        QTableWidgetItem, QCheckBox, QTextEdit, QProgressBar, QListWidget,
        QTabWidget, QMenu, QMessageBox, QScrollArea, QSpinBox)
    from PyQt6.QtCore import Qt
except ImportError as exc:
    print('SKIPPED — PyQt6 is not installed in this environment:',exc)
    sys.exit(3)

settings={}
appset=types.ModuleType('ui.app_settings')
appset.ayar_get=lambda k,default=None: settings.get(k,default)
appset.ayar_set=lambda k,v: settings.__setitem__(k,v)
sys.modules['ui.app_settings']=appset
spec=importlib.util.spec_from_file_location('ui.theme',ROOT/'ui'/'theme.py')
from ui import theme as existing_theme  # actual source; fake settings is already installed

app=QApplication.instance() or QApplication([])
window=QWidget()
window.setWindowTitle('V43 Tema Kontrol – ÖRNEK VERİ')
window.resize(940,700)
outer=QVBoxLayout(window)
outer.addWidget(QLabel('V43 • Tema görsel testi — örnek/uydurma bilgiler, gerçek öğrenci kaydı yok'))
tabs=QTabWidget()
outer.addWidget(tabs)
controls=QWidget(); layout=QVBoxLayout(controls)
row=QHBoxLayout()
for w in [QLineEdit('Örnek metin'),QComboBox(),QSpinBox(),QPushButton('Kaydet (örnek)')]:
    row.addWidget(w)
combo=row.itemAt(1).widget()
combo.addItems(['Açık/koyu geçiş testi','Metin okunabilirliği','Seçili öğe'])
layout.addLayout(row)
flag=QCheckBox('Seçili kutu – örnek')
flag.setChecked(True)
layout.addWidget(flag)
layout.addWidget(QLabel('Örnek tablolar: normal/satır seçimi/alternatif zemin'))
table=QTableWidget(4,3)
table.setHorizontalHeaderLabels(['Konu','Durum','Açıklama'])
for r in range(4):
    for c in range(3):
        table.setItem(r,c,QTableWidgetItem(['Fizik','Örnek','Kontrol'][c]))
table.setAlternatingRowColors(True)
table.selectRow(1)
layout.addWidget(table)
row2=QHBoxLayout()
items=QListWidget();items.addItems(['Liste 1','Liste 2','Liste 3']);items.setCurrentRow(1)
row2.addWidget(items)
editor=QTextEdit();editor.setText('Örnek belge metni: siyah/beyaz zemin uyumu.')
row2.addWidget(editor)
layout.addLayout(row2)
progress=QProgressBar();progress.setValue(64)
layout.addWidget(progress)
tabs.addTab(controls,'Temel kontroller')
scrollpage=QWidget();sv=QVBoxLayout(scrollpage)
for i in range(25):sv.addWidget(QLabel(f'Kaydırma ve etiket satırı {i+1}'))
area=QScrollArea();area.setWidgetResizable(True);area.setWidget(scrollpage)
tabs.addTab(area,'Kaydırma')
outer.addWidget(QLabel('Kullanım: tema geçişlerinden sonra açılır listeleri, sağ tık menülerini ve bildirimleri de gözle kontrol edin.'))
window.show()
app.processEvents()

samples={'Cloud Light','Dracula','Fenerbahçe','Cyberpunk'}
report={'utc':datetime.now(timezone.utc).isoformat(), 'status':'synthetic Qt GUI smoke (not real app)',
        'themes':[], 'screenshots':[]}
OUT.mkdir(exist_ok=True)
for name in existing_theme.tema_presets():
    existing_theme.tema_apply_preset(name)
    existing_theme.apply(app)
    app.processEvents()
    row={'name':name, 'qss_length':len(app.styleSheet()), 'table_rows':table.rowCount(),
         'selection_count':len(table.selectedItems()), 'checkbox_checked':flag.isChecked()}
    assert row['qss_length']>100 and row['table_rows']==4 and row['checkbox_checked']
    report['themes'].append(row)
    if name in samples or '--all-screenshots' in sys.argv:
        p=OUT / ('preview_'+''.join(c if c.isascii() and c.isalnum() else '_' for c in name)+'.png')
        window.grab().save(str(p))
        report['screenshots'].append(str(p.name))
    # Verify the app's popup/notification guards can be called nonmodally without signals.
    menu=QMenu(window); menu.addAction('Kontrol seçeneği');menu.addAction('Pasif seçenek').setEnabled(False)
    from ui.theme_popup_runtime_v39 import style_popup_menu
    style_popup_menu(menu)
    assert 'QMenu::item:selected' in menu.styleSheet()
    dialog=QMessageBox(window)
    dialog.setText('Örnek bilgi')
    dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
    from ui.theme_popup_runtime_v38 import _style_standard_dialog
    _style_standard_dialog(dialog)
    assert 'QMessageBox QLabel' in dialog.styleSheet()
report['gui_runtime_pass']=True
(OUT/'gui_result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print('PASS:',len(report['themes']),'themes created and applied in a PyQt6 synthetic preview.')
print('PREVIEWS:',', '.join(report['screenshots']))
print('NEXT: manually test the real program on Windows and macOS, including open dialogs.')
window.close()
sys.exit(0)
