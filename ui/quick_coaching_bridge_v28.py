# -*- coding: utf-8 -*-
"""Optional, lazy V28 right-click menu: no checkbox or legacy save hooks.

Windows performance: no timers, no DB queries for selection/checkbox events.
The only DB write is an explicit one-choice teacher action.
"""
from __future__ import annotations
import sqlite3
from contextlib import closing
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QPushButton, QMenu, QMessageBox, QToolTip

from services.adaptive_coaching_v28.quick_notes import CHOICES, set_note


def install(dialog):
    bridge = QuickCoachBridgeV28(dialog)
    bridge.install()
    return bridge


class QuickCoachBridgeV28:
    def __init__(self, dialog):
        self.dialog = dialog
        self.tab = dialog.tab
        self.button = None

    def install(self):
        # Append to the existing flowing button strip. Its old items/signal
        # connections remain untouched and retain the same order.
        root = self.dialog.layout()
        bar_wrap = root.itemAt(0).widget() if root and root.count() else None
        bar = bar_wrap.layout().itemAt(0).widget() if bar_wrap is not None else None
        flow = bar.layout() if bar is not None else None
        if flow is None:
            raise RuntimeError('Ödev Kontrol düğme alanı bulunamadı.')
        btn = QPushButton('⚡ Hızlı Teşhis')
        btn.setToolTip('Sağdaki ödev satırını seçin; nedenini isteğe bağlı tek seçimle kaydedin. '
                       'Ödev tiki ve Kaydet işleyişi aynen korunur.')
        btn.setObjectName('btnInfo')
        btn.setMinimumHeight(32)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self.open_for_selection)
        flow.addWidget(btn)
        self.button = btn
        # Only right-click; does not touch the left-click/check-state delegate.
        self.tab.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tab.customContextMenuRequested.connect(self.open_from_context)

    def _homework_at(self, row):
        if row < 0 or row >= self.tab.rowCount():
            return None
        cell = self.tab.item(row, 1)
        if cell is None:
            return None
        try:
            from ui.odev_kontrol import USERROLE
            return int(cell.data(USERROLE))
        except (ValueError, TypeError):
            return None

    def open_from_context(self, point):
        index = self.tab.indexAt(point)
        if index.isValid():
            self._show_menu(index.row(), self.tab.viewport().mapToGlobal(point))

    def open_for_selection(self):
        row = self.tab.currentRow()
        if self._homework_at(row) is None:
            QMessageBox.information(self.dialog,'Hızlı Teşhis',
                'Önce sağdaki tablodan bir ödev satırını seçin. Ödev kontrolü eskisi gibi çalışır.')
            return
        self._show_menu(row, self.button.mapToGlobal(self.button.rect().bottomLeft()))

    def _show_menu(self, row, position):
        homework_id = self._homework_at(row)
        if homework_id is None:
            return
        lesson = self.tab.item(row, 1)
        topic = self.tab.item(row, 3)
        title = f"{lesson.text() if lesson else ''} / {topic.text() if topic else ''}"
        menu = QMenu(self.dialog)
        heading = menu.addAction(title[:90])
        heading.setEnabled(False)
        menu.addSeparator()
        for code, caption in CHOICES:
            act = menu.addAction(caption)
            act.setData(code)
        # V29 read-only next-step action is a menu item, not a checkbox callback.
        try:
            from services.adaptive_coaching_v29.flags import enabled as v29_enabled
            show_v29 = v29_enabled()
        except ImportError:
            show_v29 = False  # An incomplete optional upgrade must not block V28.
        if show_v29:
            menu.addSeparator()
            action = menu.addAction('🧠 Sonraki adım önerisini göster (salt okunur)')
            action.setData('__v29_preview__')
        menu.addSeparator()
        clear = menu.addAction('Hızlı notu temizle (ödev silinmez)')
        clear.setData('__clear__')
        selected = menu.exec(position)
        if selected is None:
            return
        code = selected.data()
        if code is None:
            return
        sid = int(self.dialog.ogr_id)
        if code == '__v29_preview__':
            from ui.adaptive_next_step_v29 import show_for_selected_homework
            show_for_selected_homework(self.dialog,sid,homework_id)
            return
        from db import DB_PATH
        try:
            # Use a short timeout to keep Windows UI responsive even if
            # another process briefly locks the shared SQLite database.
            with closing(sqlite3.connect(str(DB_PATH), timeout=0.25)) as con:
                con.row_factory = sqlite3.Row
                con.execute('PRAGMA foreign_keys=ON')
                label = set_note(con, sid, homework_id, None if code=='__clear__' else code)
            QToolTip.showText(QCursor.pos(),
               ('Hızlı not silindi.' if label is None else 'Hızlı not kaydedildi: '+label)
               +'\nÖdev tikleri değişmedi.', self.tab)
        except (sqlite3.Error, OSError, ValueError) as exc:
            QMessageBox.warning(self.dialog,'Hızlı Teşhis',
                'Hızlı gözlem kaydedilemedi; mevcut ödevler etkilenmedi.\n' + str(exc))
