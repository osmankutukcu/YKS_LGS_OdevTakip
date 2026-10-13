# -*- coding: utf-8 -*-
"""V25 bağımsız öğrenme ve adaptif koçluk çalışma alanı.

Çekirdek ödev formundan yalnızca kontrollü öneri aktarım API'sini çağırır.
Gözlemler, tıkanıklıklar ve planlar sadece adaptive_*_v25 tablolarına yazılır.
Qt bağımlılığı çekirdek analiz motorundan tamamen ayrıdır.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit,
    QVBoxLayout, QWidget, QAbstractItemView,
)

import db
from services.adaptive_coaching_v25 import engine


@contextmanager
def _connection():
    con = db.get_conn()
    try:
        engine.ensure_schema(con)
        yield con
    finally:
        con.close()


class AdaptiveCoachingDialogV25(QDialog):
    """One student per dialog. Student ID is immutable for its entire lifetime."""

    def __init__(self, student_id: int, parent=None, host=None, initial_homework_id=None):
        super().__init__(parent)
        self.student_id = int(student_id)
        self.host = host  # Only the homework form has the manual transfer API.
        self.initial_homework_id = initial_homework_id
        self.current_plan = None
        self._homework = []
        with _connection() as con:
            engine._student_exists(con, self.student_id)
            r = con.execute('SELECT ad, soyad FROM ogrenci WHERE id=?', (self.student_id,)).fetchone()
            self.student_name = f"{r['ad'] or ''} {r['soyad'] or ''}".strip()
        self.setWindowTitle(f"Bilimsel Koçluk • {self.student_name}")
        self.setMinimumSize(850, 640)
        self.resize(1050, 780)
        self._build()
        self.refresh()

    def _build(self):
        self.setStyleSheet('''
            QDialog {background:#f8fafc;color:#0f172a;}
            QLabel {color:#334155;}
            QGroupBox {font-weight:650; border:1px solid #dce4ef; border-radius:8px;
                       margin-top:12px; padding:12px; background:white;}
            QGroupBox::title {subcontrol-origin:margin; left:12px; padding:0 4px;}
            QPushButton {border:1px solid #cbd5e1; border-radius:7px; background:white;
                         padding:7px 12px; color:#0f172a; font-weight:600;}
            QPushButton:hover {background:#eff6ff; border-color:#93c5fd;}
            QTabWidget::pane {border:1px solid #dce4ef; border-radius:8px; background:white;}
            QTabBar::tab {padding:9px 16px; margin-right:3px;}
            QTabBar::tab:selected {font-weight:700; color:#1d4ed8;}
            QTableWidget {border:1px solid #dce4ef; gridline-color:#f1f5f9;}
            QHeaderView::section {background:#f1f5f9; color:#334155; padding:7px;}
            QLineEdit,QComboBox,QSpinBox,QTextEdit {border:1px solid #cbd5e1;
                border-radius:6px; padding:5px; background:white; color:#0f172a;}
        ''')
        root = QVBoxLayout(self)
        top_bar = QHBoxLayout()
        header = QLabel(f"🧠  Öğrenme Analizi ve Adaptif Koçluk  ·  {self.student_name} (#{self.student_id})")
        header.setStyleSheet('font-size:17px;font-weight:750;color:#0f172a;padding:8px;')
        top_bar.addWidget(header)
        top_bar.addStretch(1)
        btn_info = QPushButton("ℹ️ Nasıl Çalışır? (Rehber)")
        btn_info.setStyleSheet("""
            QPushButton {
                background: #f0f7ff; color: #0284c7; border: 1px solid #bae6fd;
                border-radius: 6px; padding: 6px 14px; font-weight: 700; font-size: 12px;
            }
            QPushButton:hover { background: #e0f2fe; border-color: #7dd3fc; }
        """)
        btn_info.clicked.connect(self._show_info_guide)
        top_bar.addWidget(btn_info)
        root.addLayout(top_bar)
        desc = QLabel('Ödev tikleri öğrenme puanı değildir. Ölçüm ve öneriler ayrı tutulur; yeni ödev için öğretmen onayı gerekir.')
        desc.setWordWrap(True)
        root.addWidget(desc)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self._build_decision_v26()
        self._build_overview()
        self._build_observation()
        self._build_plan()
        self._build_blocker()
        footer = QHBoxLayout()
        footer.addStretch(1)
        refresh = QPushButton('↻ Verileri Yenile')
        refresh.clicked.connect(self.refresh)
        footer.addWidget(refresh)
        close = QPushButton('Kapat')
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        root.addLayout(footer)

    @staticmethod
    def _new_page():
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(12, 15, 12, 12)
        box.setSpacing(10)
        return page, box

    def _build_decision_v26(self):
        """Modular teacher-decision tab; default entry without changing V25 task flow."""
        from services.adaptive_coaching_v26.flags import enabled as enabled_v26
        self._decision_v26_enabled = enabled_v26()
        if not self._decision_v26_enabled:
            return
        page, layout = self._new_page()
        title = QLabel('🎯 Bu öğrenci için sıradaki en yararlı öğretmen müdahalesi')
        title.setStyleSheet('font-size:15px;font-weight:700;')
        layout.addWidget(title)
        self.decision_v26_text = QTextEdit()
        self.decision_v26_text.setReadOnly(True)
        layout.addWidget(self.decision_v26_text, 1)
        row = QHBoxLayout()
        assessment = QPushButton('Tanılayıcı Gözlem Gir')
        assessment.clicked.connect(lambda: self.tabs.setCurrentIndex(self._find_tab('Kazanım Teşhisi')))
        row.addWidget(assessment)
        proposal = QPushButton('Ödev Taslağına Git')
        proposal.clicked.connect(lambda: self.tabs.setCurrentIndex(self._find_tab('Spiral Ödev Taslağı')))
        row.addWidget(proposal)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addWidget(QLabel('Öneri taslaktır. Mevcut Kaydet, aktarım ve checkbox işleyişine müdahale edilmez.'))
        self.tabs.addTab(page, '🧠 Koç Karar Masası')

    def _find_tab(self, title):
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == title:
                return i
        return 0

    def _refresh_decision_v26(self, con):
        if not getattr(self,'_decision_v26_enabled',False):
            return
        from services.adaptive_coaching_v26.decision import student_decisions
        brief = student_decisions(con, self.student_id, maximum=9)
        lines = [f"Durum: {brief['status']}", '',
                 f"Hedef: {brief.get('context',{}).get('target','—')}",
                 f"Koçluk planı: {brief.get('context',{}).get('coaching_plan','—')}", '',
                 f"Öğrenme gözlemi: {brief['evidence_count']} | Açık ödev: {brief['metrics'].get('open_homework_rows',0)}", '',
                 'ÖĞRETMEN İÇİN ÖNCELİKLİ ADIMLAR']
        for a in brief['actions']:
            lines += [f"\n• {a['category']} — {a['title']}",
                      f"  Neden: {a['reason']}",
                      f"  Öneri: {a['next_step']}",
                      f"  Dayanak: {a['source']}"]
        if brief['warnings']:
            lines += ['', 'SINIRLAR', *[f"• {v}" for v in brief['warnings']]]
        self.decision_v26_text.setPlainText('\n'.join(lines))

    def _build_overview(self):
        page, layout = self._new_page()
        self.summary = QLabel('')
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet('font-size:13px;font-weight:600;padding:10px;background:#eff6ff;border-radius:7px;')
        layout.addWidget(self.summary)
        self.topic_table = QTableWidget(0, 8)
        self.topic_table.setHorizontalHeaderLabels(['Ders','Konu','Ödev: yapıldı','Açık',
                     'Ölçüm','Doğruluk','Kanıt durumu','Son ölçüm'])
        self.topic_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.topic_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.topic_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.topic_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.topic_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.topic_table.doubleClicked.connect(self._topic_to_observation)
        layout.addWidget(self.topic_table, 1)
        help_label = QLabel('Bir konuya çift tıklayarak yeni kazanım gözlemi girin. Tamamlanan sayfa, tek başına kazanımın öğrenildiğini göstermez.')
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        self.tabs.addTab(page, 'Öğrenme Panosu')

    def _build_observation(self):
        page, layout = self._new_page()
        group = QGroupBox('Tanılayıcı öğrenme gözlemi')
        form = QFormLayout(group)
        self.source = QComboBox()
        self.source.currentIndexChanged.connect(self._source_changed)
        form.addRow('İlgili ödev', self.source)
        self.lesson = QLineEdit()
        self.topic = QLineEdit()
        self.subskill = QLineEdit()
        self.subskill.setPlaceholderText('Örn: Özkütle–kütle/hacim grafiği')
        form.addRow('Ders', self.lesson)
        form.addRow('Konu', self.topic)
        form.addRow('Alt kazanım / mikro eksik', self.subskill)
        self.mode = QComboBox()
        self.mode.addItems(engine.MODES)
        form.addRow('Yoklama yöntemi', self.mode)
        measures = QWidget()
        mrow = QHBoxLayout(measures)
        mrow.setContentsMargins(0, 0, 0, 0)
        self.correct = QSpinBox()
        self.wrong = QSpinBox()
        self.blank = QSpinBox()
        self.duration = QSpinBox()
        for spin in (self.correct, self.wrong, self.blank):
            spin.setRange(0, 10000)
        self.duration.setRange(0, 600)
        for caption, spin in [('Doğru',self.correct),('Yanlış',self.wrong),('Boş',self.blank),('Dakika',self.duration)]:
            mrow.addWidget(QLabel(caption))
            mrow.addWidget(spin)
        form.addRow('Değerlendirme', measures)
        self.reason = QComboBox()
        self.reason.addItems(engine.REASONS)
        self.reason.setCurrentText('Belirtilmedi')
        form.addRow('Hata / zorlanma nedeni', self.reason)
        self.note = QTextEdit()
        self.note.setPlaceholderText('Öğrencinin gerekçesi, örnek soru veya koçun gözlemi...')
        self.note.setMaximumHeight(95)
        form.addRow('Açıklama', self.note)
        layout.addWidget(group)
        actions = QHBoxLayout()
        actions.addStretch(1)
        btn = QPushButton('✓ Gözlemi Kaydet')
        btn.clicked.connect(self._save_observation)
        actions.addWidget(btn)
        layout.addLayout(actions)
        info = QLabel('Gözlem kaydedilse bile eski ödevin tamamlanma tikleri değişmez. '
                      'Ödev listesinde olmayan bir konu için “Bağımsız gözlem” seçebilirsiniz.')
        info.setWordWrap(True)
        layout.addWidget(info)
        layout.addStretch(1)
        self.tabs.addTab(page, 'Kazanım Teşhisi')

    def _build_plan(self):
        page, layout = self._new_page()
        group = QGroupBox('Öğrenciye özel öneri ayarları')
        form = QGridLayout(group)
        self.weekly = QSpinBox()
        self.weekly.setRange(30, 1800)
        self.weekly.setSuffix(' dk/hafta')
        self.review = QSpinBox()
        self.review.setRange(0, 60)
        self.review.setSuffix(' %')
        self.session = QSpinBox()
        self.session.setRange(10, 120)
        self.session.setSuffix(' dk')
        self.style = QComboBox()
        self.style.addItems(['Dengeli','Zaman bloklu','Mikro adım','Zorlayıcı'])
        for index,(name,field) in enumerate([
            ('Haftalık çalışma bütçesi',self.weekly),('Tekrar payı (varsayılan %30)',self.review),
            ('Oturum üst sınırı',self.session),('Çalışma yaklaşımı',self.style)]):
            form.addWidget(QLabel(name), index//2, (index%2)*2)
            form.addWidget(field, index//2, (index%2)*2+1)
        layout.addWidget(group)
        controls = QHBoxLayout()
        self.preview_btn = QPushButton('Önerileri Hesapla')
        self.preview_btn.clicked.connect(self._preview)
        self.save_pref = QPushButton('Öğrenci Ayarlarını Kaydet')
        self.save_pref.clicked.connect(self._save_preferences)
        controls.addWidget(self.preview_btn)
        controls.addWidget(self.save_pref)
        controls.addStretch(1)
        layout.addLayout(controls)
        self.plan_summary = QLabel('Öneri henüz hesaplanmadı.')
        self.plan_summary.setWordWrap(True)
        layout.addWidget(self.plan_summary)
        self.plan_table = QTableWidget(0, 6)
        self.plan_table.setHorizontalHeaderLabels(['Seç','Ders','Konu','Tür','Yöntem','Dakika'])
        self.plan_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.plan_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.plan_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.plan_table,1)
        actions = QHBoxLayout()
        self.save_draft = QPushButton('Taslağı Kaydet (Ödev Verme Değil)')
        self.save_draft.clicked.connect(self._save_plan)
        self.save_draft.setEnabled(False)
        self.transfer_btn = QPushButton('Seçilenleri Ödev Listesine Aktar')
        self.transfer_btn.setToolTip('Mevcut formun güvenli tik akışına aktarır; otomatik kaydetmez.')
        self.transfer_btn.clicked.connect(self._transfer)
        self.transfer_btn.setEnabled(False)
        actions.addWidget(self.save_draft)
        actions.addWidget(self.transfer_btn)
        actions.addStretch(1)
        layout.addLayout(actions)
        self.tabs.addTab(page, 'Spiral Ödev Taslağı')

    def _build_blocker(self):
        page, layout = self._new_page()
        group = QGroupBox('Geciken ödev / tıkanıklık değerlendirmesi')
        form = QFormLayout(group)
        self.blocker_source = QComboBox()
        form.addRow('İlgili ödev (isteğe bağlı)', self.blocker_source)
        self.blocker_reason = QComboBox()
        self.blocker_reason.addItems(engine.REASONS[:-1])
        form.addRow('Neden', self.blocker_reason)
        self.blocker_note = QTextEdit()
        self.blocker_note.setMaximumHeight(90)
        form.addRow('Ne oldu?', self.blocker_note)
        self.blocker_resolution = QLineEdit()
        self.blocker_resolution.setPlaceholderText('Örn: Kapsamı daralt, 15 dk örnek çöz, cuma günü yeniden görüş')
        form.addRow('Koçun müdahale kararı', self.blocker_resolution)
        layout.addWidget(group)
        row = QHBoxLayout()
        row.addStretch(1)
        btn = QPushButton('Tıkanıklığı Kaydet')
        btn.clicked.connect(self._save_blocker)
        row.addWidget(btn)
        layout.addLayout(row)
        self.blocker_list = QTableWidget(0, 3)
        self.blocker_list.setHorizontalHeaderLabels(['Tarih','Neden','Karar'])
        self.blocker_list.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch)
        self.blocker_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.blocker_list,1)
        layout.addWidget(QLabel('Eski ödev otomatik devredilmez, silinmez veya borçlandırılmaz.'))
        self.tabs.addTab(page, 'Tıkanıklık Analizi')

    def refresh(self):
        try:
            with _connection() as con:
                self._refresh_decision_v26(con)
                summary = engine.student_overview(con,self.student_id)
                topics = engine.student_topics(con,self.student_id)
                blockers = engine.get_blockers(con,self.student_id)
                prefs = engine.load_preferences(con,self.student_id)
                self._homework = [dict(r) for r in con.execute('''
                    SELECT o.id,o.ders,o.konu_ad,o.kitap_ad,o.durum
                    FROM odev o JOIN odev_kume k ON k.id=o.kume_id
                    WHERE o.ogrenci_id=? AND k.ogrenci_id=? ORDER BY o.id DESC LIMIT 600
                ''',(self.student_id,self.student_id))]
            self._render_overview(summary, topics)
            self._render_sources()
            self._render_blockers(blockers)
            self.weekly.setValue(prefs['weekly_minutes'])
            self.review.setValue(prefs['review_percent'])
            self.session.setValue(prefs['max_session_minutes'])
            self.style.setCurrentText(prefs['learning_style'])
            # A change of evidence invalidates a cached proposal.
            self.current_plan = None
            self.save_draft.setEnabled(False)
            self.transfer_btn.setEnabled(False)
            self.plan_table.setRowCount(0)
            self.plan_summary.setText('Güncel veriler yüklendi. Önerileri yeniden hesaplayın.')
        except Exception as exc:
            QMessageBox.critical(self,'Koçluk verileri',f'Veriler alınamadı: {exc}')

    def _render_overview(self, stats, topics):
        self.summary.setText(f"{stats['topic_count']} konu · {stats['measured_topics']} ölçülen konu · "
            f"{stats['support_topics']} hedefli destek · {stats['due_topics']} tekrar hatırlatması · "
            f"{stats['open_homework_rows']} açık ödev satırı · {stats['blockers']} tıkanıklık kaydı")
        self.topic_table.setRowCount(len(topics))
        for r,t in enumerate(topics):
            cells = [t['lesson'],t['topic'],t['done_count'],t['open_count'],t['observations'],
                (f"%{t['accuracy']}" if t['accuracy'] is not None else '—'),t['level'],
                t['last_observed_on'].isoformat() if t['last_observed_on'] else '—']
            for c,val in enumerate(cells):
                cell = QTableWidgetItem(str(val))
                if c in (2,3,4,5): cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.topic_table.setItem(r,c,cell)

    def _render_sources(self):
        previous_id = self.source.currentData()
        self.source.blockSignals(True)
        self.source.clear()
        self.blocker_source.clear()
        self.source.addItem('Bağımsız gözlem (ödev bağlantısı yok)',None)
        self.blocker_source.addItem('Genel tıkanıklık (ödev bağlantısı yok)',None)
        for r in self._homework:
            label = f"#{r['id']} · {r['ders']} / {r['kitap_ad']} / {r['konu_ad']} ({r['durum']})"
            self.source.addItem(label,r['id'])
            self.blocker_source.addItem(label,r['id'])
        target = self.initial_homework_id if self.initial_homework_id is not None else previous_id
        idx = self.source.findData(target)
        self.source.setCurrentIndex(idx if idx >= 0 else 0)
        self.source.blockSignals(False)
        self._source_changed()

    def _source_changed(self, *_):
        oid = self.source.currentData()
        r = next((row for row in self._homework if row['id']==oid), None)
        self.lesson.setReadOnly(bool(r))
        self.topic.setReadOnly(bool(r))
        if r:
            self.lesson.setText(r['ders'])
            self.topic.setText(r['konu_ad'])

    def _topic_to_observation(self, index):
        r = index.row()
        lesson = self.topic_table.item(r,0)
        topic = self.topic_table.item(r,1)
        if not lesson or not topic:
            return
        self.source.setCurrentIndex(0)
        self.lesson.setText(lesson.text())
        self.topic.setText(topic.text())
        self.tabs.setCurrentIndex(1)

    def _render_blockers(self,rows):
        self.blocker_list.setRowCount(len(rows))
        for row,r in enumerate(rows):
            for col,val in enumerate((r['created_at'],r['reason'],r['resolution'])):
                self.blocker_list.setItem(row,col,QTableWidgetItem(str(val)))

    def _save_observation(self):
        try:
            with _connection() as con:
                engine.save_observation(con, self.student_id, self.lesson.text(), self.topic.text(),
                    homework_id=self.source.currentData(), subskill=self.subskill.text(),
                    mode=self.mode.currentText(), correct=self.correct.value(), wrong=self.wrong.value(),
                    blank=self.blank.value(), duration_min=self.duration.value(),
                    reason=self.reason.currentText(), note=self.note.toPlainText(),
                    observed_on=date.today())
            QMessageBox.information(self,'Kaydedildi','Tanılayıcı gözlem kaydedildi. Eski ödev tikleri değişmedi.')
            self.correct.setValue(0);self.wrong.setValue(0);self.blank.setValue(0)
            self.note.clear()
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self,'Gözlem kaydedilemedi',str(exc))

    def _save_blocker(self):
        try:
            with _connection() as con:
                engine.save_blocker(con, self.student_id, self.blocker_reason.currentText(),
                    self.blocker_note.toPlainText(), homework_id=self.blocker_source.currentData(),
                    resolution=self.blocker_resolution.text() or None)
            QMessageBox.information(self,'Kaydedildi','Tıkanıklık değerlendirmesi ayrı kayda alındı.')
            self.blocker_note.clear();self.blocker_resolution.clear()
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self,'Tıkanıklık kaydedilemedi',str(exc))

    def _preferences(self):
        return {'weekly_minutes':self.weekly.value(),'review_percent':self.review.value(),
                'max_session_minutes':self.session.value(),'learning_style':self.style.currentText()}

    def _save_preferences(self):
        try:
            with _connection() as con:
                engine.save_preferences(con,self.student_id,self._preferences())
            QMessageBox.information(self,'Kaydedildi','Öğrenciye özel tercih ve sınırlar kaydedildi.')
            self.current_plan = None
            self.save_draft.setEnabled(False)
            self.transfer_btn.setEnabled(False)
        except Exception as exc:
            QMessageBox.warning(self,'Ayar hatası',str(exc))

    def _preview(self):
        try:
            with _connection() as con:
                self.current_plan = engine.make_plan(con,self.student_id,self._preferences())
            p = self.current_plan
            self.plan_summary.setText(f"{len(p['items'])} öneri · {p['planned_minutes']} dk toplam · "
                f"{p['focus_minutes']} dk odak · {p['review_minutes']} dk tekrar · "
                f"{p['unused_minutes']} dk rezerve.\n" + '\n'.join(p['warnings']))
            self.plan_table.setRowCount(len(p['items']))
            for r,item in enumerate(p['items']):
                select = QTableWidgetItem('')
                select.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                select.setCheckState(Qt.CheckState.Checked)
                select.setToolTip(item['details'])
                self.plan_table.setItem(r,0,select)
                for c,key in enumerate(('lesson','topic','category','mode','minutes'),1):
                    cell=QTableWidgetItem(str(item[key]))
                    cell.setToolTip(item['details'])
                    self.plan_table.setItem(r,c,cell)
            self.save_draft.setEnabled(bool(p['items']))
            self.transfer_btn.setEnabled(bool(p['items']) and callable(getattr(self.host,'_wizard_transfer_tasks',None)))
        except Exception as exc:
            self.current_plan=None
            self.save_draft.setEnabled(False)
            self.transfer_btn.setEnabled(False)
            QMessageBox.warning(self,'Plan hazırlanamadı',str(exc))

    def _selected_plan_items(self):
        if not self.current_plan:
            return []
        return [item for i,item in enumerate(self.current_plan['items'])
                if self.plan_table.item(i,0) and
                   self.plan_table.item(i,0).checkState()==Qt.CheckState.Checked]

    def _save_plan(self):
        if not self.current_plan:
            return
        subset = self._selected_plan_items()
        if not subset:
            QMessageBox.warning(self,'Boş taslak','Önce en az bir öneri seçin.')
            return
        try:
            review_minutes = sum(x['minutes'] for x in subset if x['category']=='Aralıklı tekrar')
            focus_minutes = sum(x['minutes'] for x in subset if x['category']=='Güncel odak')
            planned = focus_minutes + review_minutes
            plan = dict(self.current_plan,items=subset,
                        review_minutes=review_minutes,focus_minutes=focus_minutes,
                        planned_minutes=planned,
                        unused_minutes=max(0,self.current_plan.get('effective_weekly_minutes',self.current_plan['preferences']['weekly_minutes'])-planned))
            with _connection() as con:
                draft_id = engine.save_plan(con,self.student_id,plan)
            QMessageBox.information(self,'Taslak kaydedildi',
                f'#{draft_id} numaralı taslak kaydedildi. Henüz yeni ödev verilmedi.')
        except Exception as exc:
            QMessageBox.warning(self,'Taslak kaydedilemedi',str(exc))

    def _transfer(self):
        host = self.host
        if not callable(getattr(host,'_wizard_transfer_tasks',None)):
            return
        items = self._selected_plan_items()
        if not items:
            QMessageBox.warning(self,'Boş seçim','Önce en az bir öneri seçin.')
            return
        tasks = [{'ders':r['lesson'],'kitap':r['book'],'konu':r['topic'],
                  'dk':r['minutes'],'aciklama':f"{r['mode']}: {r['details']}"}
                 for r in items if r.get('book')]
        without_book = len(items)-len(tasks)
        message = (f'{len(tasks)} öneri, standart Ödev Takip Formu tik akışına aday olarak aktarılacak.\n'
                   f'{without_book} önerinin kaynak kitabı bulunmuyor ve aktarılmayacak.\n\n'
                   'Yalnızca öğrenci, ders, kitap ve konu birebir eşleşirse işaretleme yapılacak. '
                   'Veritabanına kaydetme yine mevcut Kaydet düğmesiyle yapılır. Devam?')
        if QMessageBox.question(self,'Öğretmen Onayı',message,
             QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:
            return
        try:
            # This API guards both the selected student and the loaded matrix student.
            result=host._wizard_transfer_tasks(tasks,expected_student_id=self.student_id)
            if result and result.get('added',0):
                self.plan_summary.setText(self.plan_summary.text() + '\n'
                    + f"{result['added']} öneri mevcut forma işlendi; son Kaydet öğretmende.")
        except Exception as exc:
            QMessageBox.warning(self,'Aktarım yapılamadı',str(exc))

    def _show_info_guide(self):
        try:
            from ui.homework_guide_dialog import OdevTakipRehberDialog
            OdevTakipRehberDialog(self, initial_tab=0).exec()
        except Exception as exc:
            QMessageBox.information(self, "Rehber", f"Rehber açılamadı: {exc}")
