# -*- coding: utf-8 -*-
"""V26 kurum koçluk çalışma masası: toplu salt-okunur önceliklendirme.

Ödev takibi / kontrolü değiştirmez. Öğrenci ayrıntıları için V25 öğretmen
penceresini açar; yeni ödev oluşturma yalnızca özgün ödev formundadır.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QAbstractItemView, QDialog, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSplitter, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget)
import db
from services.adaptive_coaching_v25 import engine
from services.adaptive_coaching_v26 import decision


class AdaptiveCoachingCenterV26(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Adaptif Koçluk Merkezi • Öğretmen Karar Masası')
        self.setMinimumSize(990, 670)
        self.resize(1190, 790)
        self._rows = []
        self._build()
        self.refresh()

    def _build(self):
        self.setStyleSheet('''
          QDialog {background:#f7f9fc;color:#15243b;}
          QLabel {color:#25364d;}
          QPushButton {background:#fff;border:1px solid #d8e2ee;border-radius:7px;
            padding:8px 12px;color:#15243b;font-weight:600;}
          QPushButton:hover {background:#eff6ff;border-color:#93c5fd;}
          QLineEdit {padding:8px;border:1px solid #cbd5e1;border-radius:7px;background:white;}
          QTableWidget {border:1px solid #dce4ee;background:white;gridline-color:#f0f3f9;}
          QHeaderView::section {background:#f0f5fa;color:#1f3048;padding:8px;border:0;}
          QTextEdit {border:1px solid #dce4ee;border-radius:8px;background:white;padding:10px;}
        ''')
        root = QVBoxLayout(self)
        title = QLabel('🧠 Adaptif Koçluk Merkezi  |  Kurum Karar Masası')
        title.setStyleSheet('font-size:20px;font-weight:750;padding:8px;')
        root.addWidget(title)
        desc = QLabel('Öğretmenin öncelik sırasını belirlemeye yardım eder. Ödev tamamlanması öğrenme sayılmaz; '
                      'öneriler otomatik ödev yazmaz, silmez veya devretmez.')
        desc.setWordWrap(True)
        root.addWidget(desc)
        tools = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText('Öğrenci ara…')
        self.search.textChanged.connect(self._filter)
        tools.addWidget(self.search, 1)
        self.refresh_button = QPushButton('↻ Yenile')
        self.refresh_button.clicked.connect(self.refresh)
        tools.addWidget(self.refresh_button)
        self.open_button = QPushButton('Seçili Öğrencinin Koçluk Masasını Aç')
        self.open_button.clicked.connect(self._open_student)
        tools.addWidget(self.open_button)
        self.btn_info = QPushButton('ℹ️')
        self.btn_info.setFixedWidth(34)
        self.btn_info.setToolTip('Adaptif Koçluk ve Karar Masası Çalışma Mantığı & Rehberi')
        self.btn_info.setStyleSheet('''
            QPushButton {
                font-size: 15px; font-weight: bold; background: #e0f2fe; color: #0284c7;
                border: 1px solid #bae6fd; border-radius: 6px; padding: 4px;
            }
            QPushButton:hover {
                background: #bae6fd; color: #0369a1;
            }
        ''')
        self.btn_info.clicked.connect(self._show_info_dialog)
        tools.addWidget(self.btn_info)
        root.addLayout(tools)
        self.overview = QLabel('Kurum kayıtları okunuyor…')
        self.overview.setStyleSheet('background:#eef4fc;border-radius:7px;padding:11px;font-weight:600;')
        root.addWidget(self.overview)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(['Öğrenci','Durum','Açık ödev','Ölçülen','Destek'])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._selected)
        self.table.cellClicked.connect(lambda r, c: self._selected())
        self.table.doubleClicked.connect(self._open_student)
        splitter.addWidget(self.table)
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        splitter.addWidget(self.detail)
        splitter.setSizes([580, 580])
        root.addWidget(splitter, 1)
        footer = QHBoxLayout()
        self.note = QLabel('Bu ekranın değerlendirmeleri kural tabanlıdır; sınav başarısı veya psikolojik tanı üretmez.')
        self.note.setWordWrap(True)
        footer.addWidget(self.note, 1)
        close = QPushButton('Kapat')
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        root.addLayout(footer)

    def refresh(self):
        selected_sid = self._selected_student_id()
        try:
            con = db.get_conn()
            try:
                # V34: visiting the institution dashboard must not create
                # adaptive tables or migrate historical student records.
                con.execute('PRAGMA query_only=ON')
                data = decision.institution_queue(con, limit=500)
            finally:
                con.close()
            self._rows = data['students']
            self.overview.setText(
                f"{data['total_students']} kayıtlı öğrenci · "
                f"{sum(r['attention']=='Tanılayıcı destek' for r in self._rows)} hedefli destek sinyali · "
                f"{sum(r['attention']=='Ölçüm gerekli' for r in self._rows)} ölçümü eksik öğrenci"
                + (' · İlk 500 kayıt görüntüleniyor' if data['truncated'] else ''))
            self.table.blockSignals(True)
            self.table.setRowCount(len(self._rows))
            restore = -1
            for i,r in enumerate(self._rows):
                if selected_sid == r['student_id']:
                    restore = i
                vals = [r['name'] or f"Öğrenci #{r['student_id']}", r['attention'],
                        r['open_rows'], r['measured'], r['support']]
                for c,val in enumerate(vals):
                    cell = QTableWidgetItem(str(val))
                    if c == 0:
                        cell.setData(Qt.ItemDataRole.UserRole, int(r['student_id']))
                    elif c > 1:
                        cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.table.setItem(i,c,cell)
            self.table.blockSignals(False)
            self._filter(self.search.text())
            if not self._rows:
                self.detail.setPlainText('Önceliklendirme için henüz öğrenci kaydı bulunmuyor.')
            else:
                self.table.selectRow(max(0,restore))
                self._selected()
        except Exception as exc:
            self.detail.setPlainText(f'Koçluk sırası yüklenemedi: {exc}\nEski ödev kayıtları değiştirilmedi.')
            self.overview.setText('Veri okuma hatası')

    def _filter(self, query):
        needle = (query or '').strip().casefold()
        for i,r in enumerate(self._rows):
            text = (r['name'] + ' ' + r['attention']).casefold()
            self.table.setRowHidden(i, needle not in text)
        if self.table.currentRow() >= 0 and self.table.isRowHidden(self.table.currentRow()):
            self.table.clearSelection()
            self.detail.setPlainText('Görmek istediğiniz öğrenciyi seçin.')

    def _selected_student_id(self):
        selection = self.table.selectionModel()
        if selection:
            selected_rows = selection.selectedRows()
            if selected_rows:
                row = selected_rows[0].row()
                if not self.table.isRowHidden(row):
                    cell = self.table.item(row, 0)
                    return int(cell.data(Qt.ItemDataRole.UserRole)) if cell else None
        row = self.table.currentRow()
        if row < 0 or self.table.isRowHidden(row):
            return None
        cell = self.table.item(row, 0)
        return int(cell.data(Qt.ItemDataRole.UserRole)) if cell else None

    def _show_info_dialog(self):
        try:
            from ui.homework_guide_dialog import OdevTakipRehberDialog
            OdevTakipRehberDialog(self, initial_tab=0).exec()
        except Exception as exc:
            QMessageBox.information(self, "Rehber", f"Rehber açılamadı: {exc}")

    def _selected(self):
        sid = self._selected_student_id()
        if sid is None:
            self.detail.setPlainText('Sol tablodan bir öğrenci seçin.')
            return
        try:
            con = db.get_conn()
            try:
                # Optional tables may not exist; decision layer handles that.
                con.execute('PRAGMA query_only=ON')
                brief = decision.student_decisions(con, sid)
                from services.adaptive_coaching_v28.flags import enabled as quick_notes_enabled
                if quick_notes_enabled():
                    from services.adaptive_coaching_v28.quick_notes import recent_notes
                    notes = recent_notes(con, sid, limit=6)
                else:
                    notes = []
                next_steps = []
                try:
                    from services.adaptive_coaching_v29.flags import enabled as v29_enabled
                    if v29_enabled():
                        from services.adaptive_coaching_v29.next_steps import student_next_steps
                        next_steps = student_next_steps(con, sid, limit=3)
                except Exception:
                    # V29 is optional. A failure here must not break V26.
                    next_steps = []
            finally:
                con.close()
            lines = [f"ÖĞRENCİ #{sid} · {brief['status']}", '',
                     decision.concise_summary(brief, n=7), '', 'NEDEN BU ÖNERİ?']
            for a in brief['actions'][:7]:
                lines.extend([f"\n• {a['category']} — {a['title']}",
                              f"  Kanıt: {a['reason']}", f"  Öneri: {a['next_step']}",
                              f"  Kaynak: {a['source']}"])
            if brief['warnings']:
                lines += ['', 'DİKKAT', *['• '+w for w in brief['warnings']]]
            # V28 sidecar read: only on selecting a student, not in the
            # institution's bulk list or the legacy homework UI.
            if notes:
                lines += ['', 'HIZLI KOÇ NOTLARI (öğretmen gözlemi; öğrenme kanıtı değil)']
                for item in notes:
                    lines.append(f"• {item['lesson']} / {item['topic']}: {item['label']}")
            # V34 learner synthesis works only on an explicitly selected learner.
            try:
                from services.adaptive_coaching_v34.flags import enabled as v34_enabled
                if v34_enabled():
                    from services.adaptive_coaching_v34.journey import compose_journey, journey_text
                    joined = compose_journey(sid, brief, notes, next_steps)
                    lines += ['', journey_text(joined)]
            except ImportError:
                pass
            self.detail.setPlainText('\n'.join(lines))
        except Exception as exc:
            self.detail.setPlainText(f'Öğrencinin koçluk verileri okunamadı: {exc}')

    def _open_student(self, *_):
        sid = self._selected_student_id()
        if sid is None:
            QMessageBox.information(self, 'Öğrenci Seçiniz', 'Önce bir öğrenci seçin.')
            return
        try:
            from ui.adaptive_coaching_dialog_v25 import AdaptiveCoachingDialogV25
            # Only selected student. Host=None prevents accidental legacy task writes.
            AdaptiveCoachingDialogV25(sid, parent=self, host=None).exec()
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, 'Koçluk masası', f'Modül açılamadı: {exc}')
