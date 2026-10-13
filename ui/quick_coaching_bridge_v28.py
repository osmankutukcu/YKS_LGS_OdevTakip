# -*- coding: utf-8 -*-
"""Optional, lazy V28 right-click menu: no checkbox or legacy save hooks.

Windows performance: no timers, no DB queries for selection/checkbox events.
The only DB write is an explicit one-choice teacher action.
"""
from __future__ import annotations
import sqlite3
from contextlib import closing
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QCursor, QIcon, QPixmap, QPainter, QColor, QBrush, QPen
from PyQt6.QtWidgets import QPushButton, QMenu, QMessageBox, QToolTip

from services.adaptive_coaching_v28.quick_notes import CHOICES, set_note

CHOICE_META = {
    'difficulty': {
        'icon': '⚠️',
        'badge': 'Zorlandı',
        'caption': 'Zorlandı; neden henüz net değil',
        'bg': '#fef3c7',
        'border': '#f59e0b',
        'text': '#92400e',
    },
    'concept': {
        'icon': '❓',
        'badge': 'Anlaşılmadı',
        'caption': 'Konu/kazanım anlaşılmadı',
        'bg': '#fee2e2',
        'border': '#ef4444',
        'text': '#991b1b',
    },
    'time': {
        'icon': '⏳',
        'badge': 'Zaman Yetmedi',
        'caption': 'Zaman yetmedi',
        'bg': '#ffedd5',
        'border': '#f97316',
        'text': '#9a3412',
    },
    'attention': {
        'icon': '⚡',
        'badge': 'İşlem/Dikkat',
        'caption': 'Dikkat veya işlem hatası',
        'bg': '#fef9c3',
        'border': '#eab308',
        'text': '#854d0e',
    },
    'workload': {
        'icon': '📦',
        'badge': 'İş Yükü Fazla',
        'caption': 'İş yükü fazla geldi',
        'bg': '#e0e7ff',
        'border': '#6366f1',
        'text': '#3730a3',
    },
    'ask': {
        'icon': '🗣️',
        'badge': 'Sorulacak',
        'caption': 'Öğrenciye sorulacak',
        'bg': '#f3e8ff',
        'border': '#a855f7',
        'text': '#6b21a8',
    },
    'easy': {
        'icon': '⭐',
        'badge': 'Kolay Geldi',
        'caption': 'Kolay geldi (öğretmen gözlemi)',
        'bg': '#dcfce7',
        'border': '#22c55e',
        'text': '#166534',
    },
}


def create_badge_icon(code: str) -> QIcon:
    meta = CHOICE_META.get(code)
    if not meta:
        return QIcon()
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QBrush(QColor(meta['bg'])))
    p.setPen(QPen(QColor(meta['border']), 1))
    p.drawRoundedRect(1, 1, 22, 22, 5, 5)
    font = p.font()
    font.setPixelSize(13)
    p.setFont(font)
    p.drawText(QRect(0, 0, 24, 24), Qt.AlignmentFlag.AlignCenter, meta['icon'])
    p.end()
    return QIcon(pixmap)


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
        # Sadece sağ tık menüsü
        self.tab.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tab.customContextMenuRequested.connect(self.open_from_context)

        # Küme açıldığında veya değiştiğinde rozetleri otomatik olarak yükle
        orig_kume_ac = self.dialog._kume_ac
        orig_kume_ac_moved = getattr(self.dialog, '_kume_ac_moved', None)

        def wrapped_kume_ac(*args, **kwargs):
            res = orig_kume_ac(*args, **kwargs)
            try:
                self.decorate_table()
            except Exception:
                pass
            return res

        self.dialog._kume_ac = wrapped_kume_ac

        if orig_kume_ac_moved is not None:
            def wrapped_kume_ac_moved(*args, **kwargs):
                res = orig_kume_ac_moved(*args, **kwargs)
                try:
                    self.decorate_table()
                except Exception:
                    pass
                return res
            self.dialog._kume_ac_moved = wrapped_kume_ac_moved

        self.decorate_table()

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

    def _decorate_row(self, row: int, code: str | None):
        if row < 0 or row >= self.tab.rowCount():
            return
        topic_item = self.tab.item(row, 3)
        if not topic_item:
            return
        if code and code in CHOICE_META:
            meta = CHOICE_META[code]
            topic_item.setIcon(create_badge_icon(code))
            topic_item.setToolTip(f"⚡ Hızlı Teşhis: {meta['caption']}")
            if self.tab.columnWidth(3) < 180:
                self.tab.setColumnWidth(3, 190)
        else:
            topic_item.setIcon(QIcon())
            topic_item.setToolTip("")

    def decorate_table(self):
        """Hızlı teşhis notu olan ödevlerin konu hücresine renkli simge rozeti ekler."""
        try:
            sid = int(self.dialog.ogr_id)
        except (AttributeError, ValueError, TypeError):
            return

        hw_rows = {}
        for r in range(self.tab.rowCount()):
            hid = self._homework_at(r)
            if hid is not None:
                hw_rows[hid] = r

        if not hw_rows:
            return

        from db import DB_PATH
        try:
            with closing(sqlite3.connect(str(DB_PATH), timeout=0.25)) as con:
                con.row_factory = sqlite3.Row
                exists = con.execute("""SELECT 1 FROM sqlite_master
                                        WHERE type='table' AND name='adaptive_quick_note_v28'""").fetchone()
                if not exists:
                    return
                placeholders = ','.join('?' * len(hw_rows))
                rows = con.execute(f"""SELECT homework_id, reason_code FROM adaptive_quick_note_v28
                                       WHERE student_id = ? AND homework_id IN ({placeholders})""",
                                   [sid] + list(hw_rows.keys())).fetchall()
                notes = {int(r['homework_id']): str(r['reason_code']) for r in rows}
        except Exception:
            return

        has_any_note = False
        for hid, r in hw_rows.items():
            code = notes.get(hid)
            if code:
                has_any_note = True
            self._decorate_row(r, code)
        if has_any_note and self.tab.columnWidth(3) < 180:
            self.tab.setColumnWidth(3, 190)

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
        menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 6px;
                font-size: 13px;
                font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            }
            QMenu::item {
                padding: 8px 24px 8px 12px;
                border-radius: 6px;
                color: #1e293b;
                margin: 1px 4px;
            }
            QMenu::item:selected {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: 500;
            }
            QMenu::item:disabled {
                color: #475569;
                font-weight: bold;
                background-color: #f1f5f9;
                border-radius: 4px;
                padding: 7px 12px;
                margin-bottom: 4px;
            }
            QMenu::separator {
                height: 1px;
                background-color: #e2e8f0;
                margin: 4px 8px;
            }
        """)
        heading = menu.addAction(f"📌 {title[:90]}")
        heading.setEnabled(False)
        menu.addSeparator()
        for code, caption in CHOICES:
            meta = CHOICE_META.get(code, {})
            icon_prefix = meta.get('icon', '•')
            act = menu.addAction(f"{icon_prefix}  {caption}")
            act.setData(code)
        # V29 read-only next-step action is a menu item, not a checkbox callback.
        try:
            from services.adaptive_coaching_v29.flags import enabled as v29_enabled
            show_v29 = v29_enabled()
        except ImportError:
            show_v29 = False  # An incomplete optional upgrade must not block V28.
        if show_v29:
            menu.addSeparator()
            action = menu.addAction('🧠  Sonraki adım önerisini göster (salt okunur)')
            action.setData('__v29_preview__')
        menu.addSeparator()
        clear = menu.addAction('🗑️  Hızlı notu temizle (ödev silinmez)')
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
            # Seçilen satırı anında simgeyle güncelle (veya temizle)
            self._decorate_row(row, None if code == '__clear__' else code)
            QToolTip.showText(QCursor.pos(),
               ('Hızlı not silindi.' if label is None else f'Hızlı not kaydedildi: {label}')
               +'\nÖdev tikleri değişmedi.', self.tab)
        except (sqlite3.Error, OSError, ValueError) as exc:
            QMessageBox.warning(self.dialog,'Hızlı Teşhis',
                'Hızlı gözlem kaydedilemedi; mevcut ödevler etkilenmedi.\n' + str(exc))
