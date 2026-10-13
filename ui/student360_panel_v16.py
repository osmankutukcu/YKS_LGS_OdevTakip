"""Small optional read-only overview tab for the existing coaching screen."""
from urllib.parse import quote
import sqlite3
from contextlib import closing
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit, QHBoxLayout
from services.student360_v16 import read_student_overview
from services.student360_v16.advisor import suggestions
from services.student360_v16.profile import student_routine_status
from services.target_analysis_v24.student_target import read_saved_target


class Student360Panel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.student_id = None
        lay = QVBoxLayout(self)
        title = QLabel('Öğrenci 360° | Ortak Veri Özeti')
        title.setStyleSheet('font-size: 16px; font-weight: bold')
        lay.addWidget(title)
        subtitle = QLabel('Ödev, deneme ve koçluk kayıtları salt okunur birleştirilir; hiçbir veri değiştirilmez.')
        subtitle.setWordWrap(True)
        lay.addWidget(subtitle)
        bar = QHBoxLayout()
        self.btn_refresh = QPushButton('↻ Verileri Yenile')
        self.btn_refresh.clicked.connect(self.refresh)
        bar.addWidget(self.btn_refresh)
        self.btn_copy = QPushButton('Özeti Kopyala')
        self.btn_copy.clicked.connect(self.copy_summary)
        bar.addWidget(self.btn_copy)
        self.btn_topic_evidence = QPushButton('Konu Kanıtları')
        self.btn_topic_evidence.clicked.connect(self.open_topic_evidence)
        bar.addWidget(self.btn_topic_evidence)
        bar.addStretch()
        lay.addLayout(bar)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        lay.addWidget(self.output)
        self.set_student(None)

    def set_student(self, student_id):
        self.student_id = int(student_id) if student_id is not None else None
        if self.isVisible():
            self.refresh()
        else:
            self.output.setPlainText('Öğrenci seçildi. Özeti görmek için bu sekmeyi açın.')

    def open_topic_evidence(self):
        if self.student_id is None:
            self.output.setPlainText('Önce bir öğrenci seçin.')
            return
        from ui.topic_evidence_dialog_v18 import TopicEvidenceDialog
        TopicEvidenceDialog(self.student_id, self).exec()

    def copy_summary(self):
        # Clipboard export only upon explicit teacher action.
        QApplication.clipboard().setText(self.output.toPlainText())

    def refresh(self):
        sid = self.student_id
        if sid is None:
            self.output.setPlainText('Sol listeden bir öğrenci seçin.')
            return
        # Use an owned read-only connection. db.get_conn() sets WAL pragmas;
        # this tab intentionally performs no schema init or any writes.
        from db import DB_PATH
        try:
            uri = 'file:' + quote(str(DB_PATH.resolve()), safe='/') + '?mode=ro'
            with closing(sqlite3.connect(uri, uri=True, timeout=8)) as con:
                con.execute('PRAGMA query_only=ON')
                data = read_student_overview(con, sid)
                academic_target = read_saved_target(con, sid)
        except (sqlite3.Error, ValueError, OSError) as exc:
            self.output.setPlainText(f'Öğrenci özeti alınamadı: {exc}\nMevcut koçluk kayıtlarınız değiştirilmedi.')
            return
        parts = [
            f'ÖĞRENCİ: {data.student_name}  (Kayıt: {data.student_id})', '',
            'ÖDEV TAKİBİ', data.homework_last30,
            f'Gecikmiş açık ödev: {data.homework_overdue}',
            'Not: Tamamlama akademik başarı değildir.', '',
            'DENEME SINAVLARI', data.exam_summary,
            f'Kanıt düzeyi: {data.exam_evidence}',data.exam_explanation, '',
            'YKS/LGS HEDEFİ (ÖĞRETMEN KAYDI)', academic_target, '',
            'KOÇLUK',data.coaching_plan,
            f'Kayıtlı hedef: {data.coaching_goals} | Program satırı: {data.coaching_program_entries}',
            student_routine_status(sid), '',
            'KONU HARİTASI',
            f'Takip edilen kayıt: {data.tracked_topics}; öğretmen tarafından işaretlenen: {data.marked_topics}',
            'Not: İşaretleme, tek başına öğrenme kanıtı değildir.', '',
            'ÖĞRETMEN İÇİN KISA KONTROL LİSTESİ',
        ]
        parts += [f'• {x}' for x in suggestions(data)]
        if data.source_warnings:
            parts += ['', 'VERİ UYARILARI', *[f'• {w}' for w in data.source_warnings]]
        self.output.setPlainText('\n'.join(parts))
