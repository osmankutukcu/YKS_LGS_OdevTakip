"""V4 lightweight proactive gateway to the EXISTING Günün Akıllı Özeti.

Background work touches a separate, read-only SQLite connection; UI never
changes homework, status, colours, lock state, local schema or WhatsApp queue.
Cloud connectivity is not asserted on the basis of a local SQLite refresh.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
import queue
import sqlite3
import threading

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton

from services.live_student_summary_v3 import SQLiteChangeMonitor
from services.today_priority_v4 import read_today_priority
from ui.theme import register_theme_listener, readable_text
from ui.theme_tokens_v37 import semantic_palette


def _read_worker(path: Path, target: queue.Queue):
    try:
        result = {'ok': True, 'payload': read_today_priority(path)}
    except (sqlite3.Error, OSError, ValueError, KeyError) as exc:
        result = {'ok': False, 'error': str(exc)[:180]}
    except Exception as exc:
        result = {'ok': False, 'error': type(exc).__name__}
    target.put(result)


class TodayPriorityStripV4(QFrame):
    open_details = pyqtSignal()

    def __init__(self, db_path, parent=None):
        super().__init__(parent)
        self.path = Path(db_path).expanduser().resolve()
        self._watcher = SQLiteChangeMonitor(self.path)
        self._thread = None
        self._results = queue.Queue(maxsize=1)
        self._pending = False
        self._last_day = date.today()
        self._closed = False
        self._has_loaded = False
        self.setObjectName('todayPriorityStripV4')
        # V40: theme-specific styles applied after children are built.
        root = QHBoxLayout(self)
        root.setContentsMargins(10, 5, 10, 5)
        root.setSpacing(9)
        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(1)
        self.headline = QLabel('🧠 Bugünün öncelikleri hazırlanıyor…')
        self.headline.setWordWrap(True)
        self.headline.setStyleSheet('font-size:12px; font-weight:700;')
        self.detail = QLabel('Mevcut Günün Akıllı Özeti V10–V11 kullanılacak.')
        self.detail.setWordWrap(True)
        self.detail.setStyleSheet('font-size:10px;')
        title_col.addWidget(self.headline)
        title_col.addWidget(self.detail)
        root.addLayout(title_col, 1)
        self.status = QLabel('Yerel veri • Bulut doğrulanmadı')
        self.status.setToolTip('Yalnızca yerel SQLite değişikliklerini izler; bulut bağlantısını kanıtlamaz.')
        self.status.setStyleSheet('font-size:9px;')
        root.addWidget(self.status)
        self.btn = QPushButton('Günün Özeti ▸')
        self.btn.setToolTip('Mevcut Günün Akıllı Özeti ekranını açar')
        self.btn.clicked.connect(lambda *_: self.open_details.emit())
        root.addWidget(self.btn)

        register_theme_listener(self)
        self._on_theme_changed()
        self._timer = QTimer(self)
        self._timer.setInterval(20_000)
        self._timer.timeout.connect(self._poll)
        self._timer.start()
        self._result_timer = QTimer(self)
        self._result_timer.setInterval(250)
        self._result_timer.timeout.connect(self._check_result)
        self._result_timer.start()
        QTimer.singleShot(60, self._baseline_monitor)
        QTimer.singleShot(450, self.request_refresh)

    def _on_theme_changed(self):
        c = semantic_palette()
        # Keep the action easy to distinguish without hard-coded light surfaces.
        button_bg = c['selected']
        button_fg = readable_text(button_bg, c['selected_fg'])
        self.setStyleSheet(f"""
            QFrame#todayPriorityStripV4 {{background:{c['surface']};border:1px solid {c['border']};border-radius:8px;}}
            QFrame#todayPriorityStripV4 QLabel {{border:0;background:transparent;color:{c['surface_fg']};}}
            QFrame#todayPriorityStripV4 QPushButton {{background:{button_bg};color:{button_fg};
                border:1px solid {c['border']};border-radius:6px;padding:5px 8px;font-weight:600;}}
            QFrame#todayPriorityStripV4 QPushButton:hover {{background:{c['tab_hover']};color:{c['tab_hover_fg']};}}
        """)
        muted = readable_text(c['surface'], c['surface_fg'])
        self.detail.setStyleSheet(f'font-size:10px;color:{muted};')
        self.status.setStyleSheet(f'font-size:9px;color:{muted};')

    def _baseline_monitor(self):
        if self._closed:
            return
        try:
            self._watcher.poll()
        except (sqlite3.Error, OSError):
            self.status.setText('Yerel izleme geçici olarak kullanılamıyor')

    def _poll(self):
        if self._closed or not self.isVisible():
            return
        day = date.today()
        changed_day = day != self._last_day
        if changed_day:
            self._last_day = day
        try:
            changed = self._watcher.poll()
        except (sqlite3.Error, OSError):
            self.status.setText('Yerel izleme kesildi • Bulut doğrulanmadı')
            changed = False
        if changed_day or changed or not self._has_loaded:
            self.request_refresh()

    def request_refresh(self):
        if self._closed:
            return
        if self._thread is not None:
            self._pending = True
            return
        self._thread = threading.Thread(
            target=_read_worker, args=(self.path, self._results),
            name='HomeworkDailyBriefV4', daemon=True)
        self._thread.start()

    def _check_result(self):
        if self._closed:
            return
        try:
            result = self._results.get_nowait()
        except queue.Empty:
            return
        self._present(result)
        self._thread = None
        if self._pending:
            self._pending = False
            self.request_refresh()

    def _present(self, result):
        if not result.get('ok'):
            self.headline.setText('Günlük özet şu anda okunamadı')
            self.detail.setText('Ödev kayıtları değiştirilmedi. Günün Özeti ekranından tekrar deneyebilirsiniz.')
            self.status.setText('Yerel okuma hatası • Bulut doğrulanmadı')
            self._has_loaded = True  # No aggressive retry loop on corrupt DB.
            return
        payload = result['payload']
        if payload.get('day') != date.today().isoformat():
            self._pending = True
            return
        self._has_loaded = True
        count = int(payload['priority_count'])
        item = payload['first']
        if item is None:
            self.headline.setText('🧠 Bugünün ilk 5 önceliğinde bekleyen kayıt yok')
            self.detail.setText('Diğer kayıtlar Günün Özeti içindeki Tümü bölümünde bulunabilir.')
        else:
            self.headline.setText(f'🧠 Bugünün {count} önceliği • {item["title"]}')
            self.detail.setText(item['reason'])
            self.detail.setToolTip('Dayanak: ' + item['basis'])
        self.status.setText('Yerel • ' + str(payload['checked_at']) + '\nBulut doğrulanmadı')

    def closeEvent(self, event):
        self._closed = True
        self._timer.stop()
        self._result_timer.stop()
        self._watcher.close()
        super().closeEvent(event)
