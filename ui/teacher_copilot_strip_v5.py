"""V5 optional teacher-first dashboard. UI only, no homework writes.

Reads existing V10/V11 + V27 data in an isolated worker and opens original
screens via host signals. Feedback is per-device/category, never student data.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
import queue
import sqlite3
import threading

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QWidget, QMenu)
from services.live_student_summary_v3 import SQLiteChangeMonitor
from services.teacher_copilot_v5 import read_teacher_feed
from services.teacher_feedback_v5 import vote


def _worker(path, out):
    try:
        result = {'ok': True, 'payload': read_teacher_feed(path)}
    except (sqlite3.Error, OSError, KeyError, ValueError) as exc:
        result = {'ok': False, 'error': type(exc).__name__}
    except Exception:
        result = {'ok': False, 'error': 'Beklenmeyen analiz hatası'}
    out.put(result)


def _plain(s):
    label = QLabel(s)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


class TeacherCopilotStripV5(QFrame):
    open_details = pyqtSignal()
    open_student = pyqtSignal(int)

    def __init__(self, db_path, parent=None):
        super().__init__(parent)
        self._path = Path(db_path).expanduser().resolve()
        self._watch = SQLiteChangeMonitor(self._path)
        self._result_queue = queue.Queue(maxsize=1)
        self._thread = None
        self._pending = False
        self._closed = False
        self._loaded = False
        self._day = date.today()
        self._cards = []
        self.setObjectName('teacherCopilotStripV5')
        self.setStyleSheet('''
          QFrame#teacherCopilotStripV5 {background:#f8fafc;border:1px solid #cbd5e1;border-radius:8px;}
          QFrame#teacherCopilotStripV5 QLabel {color:#334155;background:transparent;border:0;}
          QFrame#teacherCopilotStripV5 QPushButton {background:#eff6ff;color:#1e40af;border:1px solid #bfdbfe;
            border-radius:6px;padding:4px 7px;font-weight:600;}
          QFrame#teacherCopilotStripV5 QPushButton:hover {background:#dbeafe;}
        ''')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 6, 10, 6)
        outer.setSpacing(4)
        bar = QHBoxLayout()
        self.head = _plain('🧭 Akıllı Takip • Öncelikler hazırlanıyor…')
        self.head.setStyleSheet('font-weight:700;font-size:12px;')
        bar.addWidget(self.head, 1)
        self.status = _plain('Yerel • Bulut doğrulanmadı')
        self.status.setStyleSheet('color:#64748b;font-size:10px;')
        self.status.setToolTip('Yalnızca bu cihazın SQLite kayıtları izleniyor. Uzak sunucu eşitlemesi doğrulanmadı.')
        bar.addWidget(self.status)
        self.btn_expand = QPushButton('Öncelikleri göster ▾')
        self.btn_expand.setAccessibleName('Akıllı takip ayrıntılarını göster veya gizle')
        self.btn_expand.clicked.connect(self.toggle_expanded)
        bar.addWidget(self.btn_expand)
        btn_summary = QPushButton('Günün Özeti ▸')
        btn_summary.clicked.connect(lambda *_: self.open_details.emit())
        bar.addWidget(btn_summary)
        outer.addLayout(bar)
        self.preview = _plain('Mevcut Günün Akıllı Özeti ve Adaptif Koç kullanılır.')
        self.preview.setStyleSheet('color:#64748b;font-size:11px;')
        outer.addWidget(self.preview)
        self.items = QWidget(self)
        self.item_layout = QVBoxLayout(self.items)
        self.item_layout.setContentsMargins(0, 3, 0, 3)
        self.item_layout.setSpacing(5)
        self.items.hide()
        outer.addWidget(self.items)
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(20_000)
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.start()
        self._worker_timer = QTimer(self)
        self._worker_timer.setInterval(200)
        self._worker_timer.timeout.connect(self._collect)
        self._worker_timer.start()
        QTimer.singleShot(70, self._baseline)
        QTimer.singleShot(400, self.request_refresh)

    def _baseline(self):
        if not self._closed:
            try:
                self._watch.poll()
            except (OSError, sqlite3.Error):
                self.status.setText('Yerel izleme kullanılamıyor • Bulut doğrulanmadı')

    def _poll(self):
        if self._closed or not self.isVisible():
            return
        today = date.today()
        new_day = today != self._day
        self._day = today
        try:
            changed = self._watch.poll()
        except (OSError, sqlite3.Error):
            self.status.setText('Yerel izleme kesildi • Bulut doğrulanmadı')
            changed = False
        if new_day or changed or not self._loaded:
            self.request_refresh()

    def request_refresh(self):
        if self._closed:
            return
        if self._thread is not None:
            self._pending = True
            return
        self._thread = threading.Thread(target=_worker,
                                        args=(self._path, self._result_queue),
                                        name='TeacherCopilotV5', daemon=True)
        self._thread.start()

    def _collect(self):
        if self._closed:
            return
        try:
            result = self._result_queue.get_nowait()
        except queue.Empty:
            return
        self._thread = None
        self._present(result)
        if self._pending:
            self._pending = False
            self.request_refresh()

    def _clear_cards(self):
        while self.item_layout.count():
            entry = self.item_layout.takeAt(0)
            widget = entry.widget()
            if widget is not None:
                widget.deleteLater()

    def _present(self, result):
        self._loaded = True
        if not result.get('ok'):
            self._cards = []
            self._clear_cards()
            self.head.setText('🧭 Akıllı takip bilgileri geçici olarak okunamadı')
            self.preview.setText('Ödevler değiştirilmedi. Günün Özeti ekranı ayrıca açılabilir.')
            self.status.setText('Yerel okuma hatası • Bulut doğrulanmadı')
            return
        payload = result['payload']
        if payload.get('day') != date.today().isoformat():
            self._pending = True
            return
        self._cards = payload.get('cards') or []
        count = int(payload.get('total_queued') or 0)
        self.head.setText(f'🧭 Akıllı Takip • {count} öncelik' if count else '🧭 Akıllı Takip • Bekleyen öncelik yok')
        self.status.setText(f"Yerel {payload.get('checked_at', '')} • Bulut doğrulanmadı")
        if not self._cards:
            self.preview.setText('Öncelikli kayıt yok. Ayrıntılı kayıtlar Günün Özeti bölümünde.')
        else:
            first = self._cards[0]
            self.preview.setText(f"{first['title']} — {first['reason']}")
        self._render_cards()

    def _render_cards(self):
        self._clear_cards()
        for card in self._cards:
            sid = int(card['student_id'])
            if sid <= 0:
                continue
            frame = QFrame(self.items)
            frame.setStyleSheet('QFrame {background:white;border:1px solid #e2e8f0;border-radius:7px;}')
            row = QHBoxLayout(frame)
            row.setContentsMargins(9, 6, 9, 6)
            text_col = QVBoxLayout()
            title = _plain(card['title'])
            title.setStyleSheet('font-weight:700;')
            text_col.addWidget(title)
            reason = _plain(card['reason'])
            reason.setStyleSheet('color:#475569;font-size:11px;')
            text_col.addWidget(reason)
            basis = _plain('Dayanak: ' + card['basis'])
            basis.setStyleSheet('color:#64748b;font-size:10px;')
            text_col.addWidget(basis)
            coach = card.get('coach')
            if coach:
                advice = _plain('Adaptif Koç: ' + coach['priority'] + ' • ' + coach['next_step'])
                advice.setStyleSheet('color:#1e40af;font-size:11px;')
                advice.setToolTip('Ölçüm kanıtı: ' + str(coach['evidence_count']) + ' • ' + coach['source'])
                text_col.addWidget(advice)
            row.addLayout(text_col, 1)
            actions = QVBoxLayout()
            to_student = QPushButton('Öğrenciye git')
            to_student.setToolTip('Mevcut ödev takip formunu bu öğrencinin kimliğiyle açar; kayıt değiştirmez.')
            to_student.clicked.connect(lambda _=False, selected=sid: self.open_student.emit(selected))
            actions.addWidget(to_student)
            feedback = QPushButton('Geri bildirim ⋯')
            feedback.setToolTip('Yalnızca uyarı kategorisinin sunum sırası öğrenilir; öğrenci bilgileri saklanmaz.')
            menu = QMenu(feedback)
            useful = menu.addAction('Bu uyarı faydalı')
            not_useful = menu.addAction('Bu uyarı ilgisiz')
            kind = card['kind']
            useful.triggered.connect(lambda _=False, k=kind: self._feedback(k, 'useful'))
            not_useful.triggered.connect(lambda _=False, k=kind: self._feedback(k, 'not_useful'))
            feedback.setMenu(menu)
            actions.addWidget(feedback)
            row.addLayout(actions)
            self.item_layout.addWidget(frame)

    def _feedback(self, kind, rating):
        try:
            vote(kind, rating)
        except (OSError, ValueError):
            self.status.setText('Geri bildirim kaydedilemedi • Ödevler etkilenmedi')
            return
        self.request_refresh()

    def toggle_expanded(self):
        expanded = self.items.isHidden()
        self.items.setVisible(expanded)
        self.btn_expand.setText('Öncelikleri gizle ▴' if expanded else 'Öncelikleri göster ▾')

    def closeEvent(self, event):
        self._closed = True
        self._poll_timer.stop()
        self._worker_timer.stop()
        self._watch.close()
        super().closeEvent(event)
