# -*- coding: utf-8 -*-
"""Optional UI-only adapter: switch right pane without recreating assignments.

The existing right_split and its rows remain alive in QStackedWidget index 0.
No assignment/control clicks are intercepted and all original slots are intact.
"""
from __future__ import annotations
from PyQt6.QtWidgets import QPushButton
from ui.adaptive_homework_sidebar_v27 import AdaptiveHomeworkSidebarV27


class HomeworkAdaptiveBridgeV27:
    def __init__(self, host, stack, bottom):
        self.host, self.stack = host, stack
        self.panel = next((stack.widget(i) for i in range(stack.count())
                           if isinstance(stack.widget(i), AdaptiveHomeworkSidebarV27)), None)
        if self.panel is None:
            raise ValueError('Adaptif panelin sağ görünümü kurulmadı.')
        self.button = QPushButton('🧠 Adaptif Koçluk')
        self.button.setToolTip('Verilen Ödevler ile salt-okunur Adaptif Koçluk paneli arasında geçiş')
        self.button.setFixedHeight(24)
        self.button.setStyleSheet('''
            QPushButton {background:#f5f3ff;border:1px solid #c4b5fd;
               border-radius:6px;color:#6d28d9;font-weight:700;padding:2px 9px;}
            QPushButton:hover {background:#ede9fe;border-color:#8b5cf6;}
        ''')
        bottom.addWidget(self.button)
        self.button.clicked.connect(self.toggle)
        for cmb in (host.cmbAd, host.cmbSoyad):
            cmb.currentIndexChanged.connect(self.selection_changed)
        for btn_name in ('btnGetir', 'btnKaydet', 'btnKontrol'):
            btn = getattr(host, btn_name, None)
            if btn is not None:
                btn.clicked.connect(self.panel.mark_dirty)
        # Keep Student 360 exclusive to the adaptive right-paned view.
        old_360 = getattr(host, '_workspace_v21', None)
        if old_360 is not None:
            old_360.toggle_button.clicked.connect(self._sync_360)
        self.selection_changed()

    def selection_changed(self, *_):
        try:
            sid = self.host._secili_ogrenci_id()
        except (AttributeError, TypeError, ValueError):
            sid = None
        self.panel.set_student(sid)

    def _sync_360(self):
        old = getattr(self.host, '_workspace_v21', None)
        if old is not None and old.panel._is_open:
            self.show_assignments()

    def toggle(self):
        if self.stack.currentWidget() is self.panel:
            self.show_assignments()
        else:
            self.show_adaptive()

    def show_assignments(self):
        self.panel.set_active(False)
        self.stack.setCurrentIndex(0)
        self.button.setText('🧠 Adaptif Koçluk')

    def show_adaptive(self):
        if self.host._secili_ogrenci_id() is None:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self.host,'Öğrenci seçiniz','Önce öğrenci seçiniz.')
            return
        old = getattr(self.host, '_workspace_v21', None)
        if old is not None and old.panel._is_open:
            old.toggle()  # Only closes optional 360; no assignment data touched.
        self.stack.setCurrentWidget(self.panel)
        self.button.setText('📋 Verilen Ödevlere Dön')
        self.panel.set_active(True)
