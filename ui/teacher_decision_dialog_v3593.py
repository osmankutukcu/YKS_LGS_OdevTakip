# -*- coding: utf-8 -*-
"""V3.5.93 – separate, opt-in Teacher Decision Panel (read-only).

No legacy report widget or query is replaced. No student data leaves the device.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from services.report_decision_view_v3593 import make_decision_view


class TeacherDecisionDialog(QDialog):
    """Teacher-selects-student workflow; no automated assignment or writes."""

    def __init__(self, con, parent=None):
        super().__init__(parent)
        self.con = con
        self._students = ()
        self._last_key = None
        self.approved_navigation = None
        self.setObjectName('TeacherDecisionV3593')
        self.setWindowTitle('KoçPilot 360 • Öğretmen Karar Paneli (Pilot)')
        self.resize(920, 750)
        self.setMinimumSize(660, 510)
        self._style()
        self._build()
        self._load_students()

    def _style(self):
        dark = self.palette().color(QPalette.ColorRole.Window).lightness() < 130
        bg = '#0e1726' if dark else '#f8fafc'
        card = '#172337' if dark else '#ffffff'
        ink = '#f1f5f9' if dark else '#0f172a'
        soft = '#cbd5e1' if dark else '#475569'
        line = '#40526c' if dark else '#dce5f0'
        self.setStyleSheet(f'''
            QDialog#TeacherDecisionV3593 {{ background: {bg}; }}
            QFrame#DecisionCard {{ background: {card}; border:1px solid {line}; border-radius: 9px; }}
            QLabel#DecisionHeading {{ color:{ink}; font-size:15px; font-weight:750; }}
            QLabel#DecisionBody {{ color:{soft}; font-size:12px; }}
            QLabel#DecisionMinor {{ color:{soft}; font-size:11px; }}
            QScrollArea {{ border:none; background: transparent; }}
        ''')

    @staticmethod
    def _label(value: str, name: str = 'DecisionBody') -> QLabel:
        w = QLabel(str(value))
        w.setObjectName(name)
        w.setTextFormat(Qt.TextFormat.PlainText)
        w.setWordWrap(True)
        w.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return w

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(19, 18, 19, 16)
        outer.setSpacing(12)
        banner = QFrame(self)
        banner.setStyleSheet('QFrame { background: #14243e; border-radius: 10px; }'
                             'QLabel { background:transparent; color: #ffffff; }')
        bl = QVBoxLayout(banner)
        title = self._label('🧭  ÖĞRETMEN KARAR PANELİ', 'DecisionHeading')
        title.setStyleSheet('color:white; font-weight:800; font-size:20px;')
        bl.addWidget(title)
        subtitle = self._label('Öğrenciyi seçin; kanıtı, belirsizliği ve önerilen öğretmen kontrolünü aynı yerde görün.')
        subtitle.setStyleSheet('color:#dbeafe; font-size:12px;')
        bl.addWidget(subtitle)
        outer.addWidget(banner)

        filters = QHBoxLayout()
        filters.addWidget(self._label('Ara'))
        self.search = QLineEdit()
        self.search.setPlaceholderText('Ad, soyad veya öğrenci numarası…')
        self.search.setAccessibleName('Öğrenci listesinde ara')
        filters.addWidget(self.search, 1)
        filters.addWidget(self._label('Öğrenci'))
        self.students = QComboBox()
        self.students.setMinimumWidth(190)
        self.students.setAccessibleName('Analizi yapılacak aktif öğrenci')
        filters.addWidget(self.students, 2)
        filters.addWidget(self._label('Dönem'))
        self.period = QComboBox()
        for days in (30, 90, 180):
            self.period.addItem(f'Son {days} gün', days)
        self.period.setCurrentIndex(1)
        filters.addWidget(self.period)
        outer.addLayout(filters)

        self.info = self._label('Bir öğrenci seçerek incelemeye başlayın.', 'DecisionMinor')
        outer.addWidget(self.info)
        area = QScrollArea(self)
        area.setWidgetResizable(True)
        self.holder = QWidget()
        self.content = QVBoxLayout(self.holder)
        self.content.setContentsMargins(3, 3, 3, 3)
        self.content.setSpacing(9)
        self.content.addStretch()
        area.setWidget(self.holder)
        outer.addWidget(area, 1)
        caution = self._label('Bu panel tanı koymaz; konuların öğrenildiğini doğrulamaz. '
                              'Ödev, hedef, plan veya kayıt değiştirmez. Öğrenci verileri internete gönderilmez.',
                              'DecisionMinor')
        outer.addWidget(caution)
        buttons = QHBoxLayout()
        self.reload = QPushButton('↻ Veriyi Yenile')
        self.reload.setAccessibleName('Seçili öğrencinin analizini yeniden hesapla')
        buttons.addWidget(self.reload)
        buttons.addStretch(1)
        close = QPushButton('Rapor Merkezine Dön')
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        outer.addLayout(buttons)
        navigation = QHBoxLayout()
        navigation.addWidget(self._label('Onaylı geçiş:'))
        self.to_coaching = QPushButton('🎯 Koçluk Planı’na Git')
        self.to_coaching.setToolTip('Seçilen öğrencinin mevcut Koçluk Planı ekranını açar; kayıt değiştirmez')
        self.to_coaching.setEnabled(False)
        self.to_coaching.clicked.connect(lambda: self._request_navigation('coaching'))
        navigation.addWidget(self.to_coaching, 1)
        self.to_weekly = QPushButton('📅 Haftalık Planlayıcı’ya Git')
        self.to_weekly.setToolTip('Ödev Takip’i seçili öğrenciyle açar; planlayıcıyı öğretmen başlatır')
        self.to_weekly.setEnabled(False)
        self.to_weekly.clicked.connect(lambda: self._request_navigation('weekly'))
        navigation.addWidget(self.to_weekly, 1)
        outer.addLayout(navigation)
        self.search.textChanged.connect(self._filter_students)
        self.students.currentIndexChanged.connect(self._refresh)
        self.period.currentIndexChanged.connect(self._refresh)
        self.reload.clicked.connect(self._refresh)

    def _load_students(self):
        """Only active students; no name-based identity mapping."""
        try:
            cols = {str(r[1]) for r in self.con.execute('PRAGMA table_info(ogrenci)')}
            if not {'id', 'ad', 'soyad'} <= cols:
                raise ValueError('Öğrenci listesinin zorunlu alanları bulunamadı.')
            active_filter = 'WHERE COALESCE(aktif,1)=1' if 'aktif' in cols else ''
            rows = self.con.execute(
                f'SELECT id, ad, soyad FROM ogrenci {active_filter} '
                'ORDER BY ad COLLATE NOCASE, soyad COLLATE NOCASE, id LIMIT 1001'
            ).fetchall()
            if len(rows) > 1000:
                raise ValueError('Öğrenci listesi sınırını aşıyor; arama kapsamı doğrulanamadı.')
            self._students = tuple((int(sid), f'{ad or ""} {surname or ""}'.strip())
                                   for sid, ad, surname in rows if type(sid) is int and sid > 0)
            self._filter_students()
        except Exception:
            self._students = ()
            self._clear_display('Öğrenci listesi güvenilir biçimde okunamadı. Kayıtlar değiştirilmedi.')
            self.reload.setEnabled(False)

    def _filter_students(self, *_):
        needle = self.search.text().strip().casefold()
        self.students.blockSignals(True)
        self.students.clear()
        self.students.addItem('— Öğrenci seçin —', None)
        for sid, name in self._students:
            if needle in name.casefold() or needle in str(sid):
                self.students.addItem(f'{name}  ·  ID {sid}', sid)
        self.students.setCurrentIndex(0)
        self.students.blockSignals(False)
        self._clear_display('Öğrenci seçin. Arama değişince eski analiz temizlenir.')

    def _clear_cards(self):
        while self.content.count():
            item = self.content.takeAt(0)
            child = item.widget()
            if child is not None:
                child.deleteLater()
            elif item.layout() is not None:
                # Only widgets and a trailing stretch are added by this class.
                pass
        self.content.addStretch()

    def _clear_display(self, description):
        self._last_key = None
        self.approved_navigation = None
        self.to_coaching.setEnabled(False)
        self.to_weekly.setEnabled(False)
        self._clear_cards()
        self.info.setText(description)
        self.reload.setEnabled(self.students.currentData() is not None)

    def _section(self, heading, lines):
        frame = QFrame(self.holder)
        frame.setObjectName('DecisionCard')
        vertical = QVBoxLayout(frame)
        vertical.setContentsMargins(14, 12, 14, 12)
        vertical.setSpacing(7)
        vertical.addWidget(self._label(heading, 'DecisionHeading'))
        for line in lines:
            vertical.addWidget(self._label(line))
        self.content.insertWidget(self.content.count()-1, frame)

    def _refresh(self, *_):
        sid = self.students.currentData()
        days = self.period.currentData()
        self._clear_display('Veri seçimi güncelleniyor…' if sid else 'Öğrenci seçin.')
        if type(sid) is not int or type(days) is not int:
            return
        try:
            view = make_decision_view(self.con, sid, days=days)
            # Never expose data if the current selection changed meanwhile.
            if (view.student_id, view.days) != (self.students.currentData(), self.period.currentData()):
                return
        except Exception:
            self._clear_display('Bu öğrencinin akademik kayıtları doğrulanamadı. '
                                'Deneme ve konu takip kaynaklarını kontrol edin; hiçbir kayıt değiştirilmedi.')
            return
        self._last_key = (sid, days, view.as_of)
        self.to_coaching.setEnabled(True)
        self.to_weekly.setEnabled(True)
        self.info.setText(f'Öğrenci ID {sid} · Son {days} gün · {view.as_of:%d.%m.%Y} · Durum: {view.status}')
        self._section('1. Ölçülen dersler',
                      [f'{r.title} — {r.exam_line}\n{r.topic_line}' for r in view.courses]
                      or ['Bu döneme ait doğrulanmış, ders koduyla eşleşen deneme ölçümü bulunamadı.'])
        self._section('2. Öğretmen için sonraki adımlar',
                      [f'{i}. {heading}\n{instruction}\nGerekçe: {basis}'
                       for i, (heading, instruction, basis) in enumerate(view.steps, 1)]
                      or ['Öğretmen kontrolü için yeterli kaynak bulunamadı.'])
        self._section('3. Veri uyarıları', list(view.warnings) or ['Ek kaynak uyarısı bulunmadı.'])
        self._section('4. Ölçüm kapsamı ve sınırı', [view.scope, view.limitation])

    def _request_navigation(self, destination):
        """Explicit user approval; never sends suggestions to the target form."""
        from services.report_navigation_v3594 import issue_navigation
        sid = self.students.currentData()
        days = self.period.currentData()
        if not self._last_key or (sid, days) != self._last_key[:2]:
            QMessageBox.warning(self, 'Öğrenci seçimi',
                                'Önce öğrenciyi seçip veriyi yenileyin.')
            return
        target_label = ('Koçluk Planı' if destination == 'coaching'
                        else 'Ödev Takip içindeki Haftalık Planlayıcı')
        message = (f'Öğrenci ID {sid} için {target_label} ekranına geçilsin mi?\n\n'
                   'Öneriler otomatik aktarılmaz. Ödev, plan ve hedefler öğretmen '
                   'onayı olmadan oluşturulmaz veya değiştirilmez.')
        if destination == 'weekly':
            message += '\n\nÖdev Takip açıldıktan sonra Haftalık Planlayıcı’yı siz seçersiniz.'
        choice = QMessageBox.question(self, 'Kontrollü geçiş', message,
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                      QMessageBox.StandardButton.No)
        if choice != QMessageBox.StandardButton.Yes:
            return
        try:
            self.approved_navigation = issue_navigation(
                self.con, destination, sid, selected_student_id=self.students.currentData())
        except ValueError:
            QMessageBox.warning(self, 'Geçiş iptal edildi',
                                'Öğrenci kaydı tekrar doğrulanamadı. Hiçbir işlem yapılmadı.')
            return
        self.accept()
