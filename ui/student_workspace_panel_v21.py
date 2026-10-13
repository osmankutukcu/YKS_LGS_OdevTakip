"""Compact optional read-only sidebar for the existing Homework Form.

All assignment/control writes still go through the original form and dialog.
"""
from __future__ import annotations
import sqlite3
from contextlib import closing
from urllib.parse import quote
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTextEdit, QScrollArea, QFrame, QApplication,
)
from services.student_workspace_v21 import read_workspace_report
from services.student360_v16.advisor import suggestions
from services.student360_v16.profile import student_routine_status
from services.target_analysis_v24.student_target import read_saved_target


class StudentWorkspacePanelV21(QWidget):
    def __init__(self, parent=None, *, open_control=None):
        super().__init__(parent)
        self._student_id = None
        self._loaded_id = None
        self._dirty = True
        self._is_open = False
        self._open_control = open_control
        self.setObjectName('studentWorkspaceV21')
        self.setMinimumWidth(235)
        self.setMaximumWidth(460)
        self.setStyleSheet("QWidget#studentWorkspaceV21 { background: #f8fafc; border-left: 1px solid #cbd5e1; } QLabel { background: transparent; }")
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 9, 8, 9)
        root.setSpacing(7)
        title = QLabel('Öğrenci 360° | Tek Ekran')
        title.setStyleSheet('font-weight: 800; font-size: 15px;')
        root.addWidget(title)
        self.identity = QLabel('Öğrenci seçilmedi')
        self.identity.setWordWrap(True)
        root.addWidget(self.identity)
        self.status = QLabel('İnceleme alanı. Ödevlerin kaydını değiştirmez.')
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        row = QHBoxLayout()
        refresh = QPushButton('↻ Yenile')
        refresh.clicked.connect(self.refresh)
        row.addWidget(refresh)
        control = QPushButton('✅ Kontrolü Aç')
        control.clicked.connect(self.open_control)
        row.addWidget(control)
        root.addLayout(row)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setObjectName('studentWorkspaceOverviewV21')
        self.output.setPlaceholderText('Bu öğrencinin kanıtları burada görünür.')
        root.addWidget(self.output, 1)
        more = QHBoxLayout()
        btn_topic = QPushButton('Konu Kanıtları')
        btn_topic.clicked.connect(self.open_topics)
        more.addWidget(btn_topic)
        copy = QPushButton('Özeti Kopyala')
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.output.toPlainText()))
        more.addWidget(copy)
        root.addLayout(more)
        self.output.setPlainText('Öğrenci seçilince bilgiler gösterilecek.')

    def set_open(self, visible: bool) -> None:
        self._is_open = bool(visible)
        self.setVisible(self._is_open)
        if self._is_open and self._dirty:
            self.refresh()

    def set_student(self, student_id: int | None) -> None:
        sid = int(student_id) if type(student_id) is int and student_id > 0 else None
        if sid == self._student_id:
            return
        self._student_id = sid
        self._loaded_id = None
        self._dirty = True
        # Never display old student's personally identifiable details on a switch.
        self.identity.setText('Öğrenci yükleniyor…' if sid else 'Öğrenci seçilmedi')
        self.status.setText('Yeni öğrenci seçildi; özet henüz güncellenmedi.' if sid else 'Öğrenci seçin.')
        self.output.clear()
        if self._is_open:
            QTimer.singleShot(0, lambda expected=sid: self._refresh_if_current(expected))

    def _refresh_if_current(self, expected):
        if self._is_open and expected == self._student_id and self._dirty:
            self.refresh()

    def mark_dirty(self) -> None:
        self._dirty = True
        if self._is_open:
            QTimer.singleShot(0, lambda expected=self._student_id: self._refresh_if_current(expected))

    def refresh(self) -> None:
        if not self._is_open:
            self._dirty = True
            return
        sid = self._student_id
        self._loaded_id = None
        self.output.clear()
        if sid is None:
            self.identity.setText('Öğrenci seçilmedi')
            self.status.setText('Önce öğrenci seçin.')
            return
        from db import DB_PATH
        try:
            uri = 'file:' + quote(str(DB_PATH.resolve()), safe='/') + '?mode=ro'
            with closing(sqlite3.connect(uri, uri=True, timeout=6)) as con:
                con.execute('PRAGMA query_only=ON')
                report = read_workspace_report(con, sid)
                academic_target = read_saved_target(con, sid)
                # V23.3: optional scoped-topic ledger, NEVER count in legacy control totals.
                from services.curriculum_v233 import list_assignments
                scoped_tasks = list_assignments(con, student_id=sid)
        except (sqlite3.Error, ValueError, OSError) as exc:
            self.identity.setText('Öğrenci #' + str(sid))
            self.status.setText('Özet alınamadı, kayıtlar etkilenmedi.')
            self.output.setPlainText(str(exc))
            return
        # Reject a report for the wrong student (e.g. after an asynchronous switch).
        if self._student_id != sid or report.student.student_id != sid:
            return
        s, c = report.student, report.control
        self.identity.setText(f'{s.student_name} · #{sid}')
        self.status.setText('Salt okunur · Mevcut veriler')
        blocks = [
            '✅ ÖDEV KONTROL (ANA KAYIT)',
            f'Tamamlanan: {c.completed} | Açık: {c.open}',
            f'Belirsiz: {c.unknown} | Hariç: {c.excluded}',
            'Son kontrol kayıtları:',
            *([f'• {item.lesson} / {item.topic}: {item.status}' for item in report.recent_control]
              or ['• Kayıt yok']), '',
            '📋 SON 30 GÜN / TAKİP', s.homework_last30,
            f'Gecikmiş açık kayıt: {s.homework_overdue}',
            'Ödev bitirmek, konunun öğrenildiğini kanıtlamaz.', '',
            '📈 DENEME', s.exam_summary,
            f'Karşılaştırma: {s.exam_evidence}',s.exam_explanation, '',
            '🎓 YKS/LGS HEDEFİ (ÖĞRETMEN KAYDI)', academic_target, '',
            '🎯 KOÇLUK', s.coaching_plan,
            f'Hedef: {s.coaching_goals} | Program: {s.coaching_program_entries}',
            student_routine_status(sid), '',
            '📎 KAPSAMA ÖZEL ÖDEVLER (AYRI KAYIT)',
            f'Açık: {sum(x.status == "devam" for x in scoped_tasks)} | Tamam: {sum(x.status == "tamam" for x in scoped_tasks)} | İptal: {sum(x.status == "iptal" for x in scoped_tasks)}',
            'Bu rakamlar ana ödev kontrol toplamlarına dahil değildir.', '',
            '📚 KONU HARİTASI',
            f'Kayıtlı: {s.tracked_topics} | Öğretmen işaretli: {s.marked_topics}', '',
            '🔎 KONTROL ÖNERİLERİ',
            *['• ' + item for item in suggestions(s)], '',
            *['• ' + note for note in report.notes],
        ]
        if s.source_warnings:
            blocks += ['', '⚠️ VERİ SINIRLARI', *['• ' + w for w in s.source_warnings]]
        self.output.setPlainText('\n'.join(blocks))
        self._loaded_id = sid
        self._dirty = False

    def open_control(self) -> None:
        if self._student_id is None or not callable(self._open_control):
            self.status.setText('Önce öğrenci seçin.')
            return
        self._open_control()
        # Existing controller still performs all the original validation/writes.
        self.mark_dirty()

    def open_topics(self) -> None:
        if self._student_id is None:
            self.status.setText('Önce öğrenci seçin.')
            return
        from ui.topic_evidence_dialog_v18 import TopicEvidenceDialog
        TopicEvidenceDialog(self._student_id, self).exec()
        self.mark_dirty()
