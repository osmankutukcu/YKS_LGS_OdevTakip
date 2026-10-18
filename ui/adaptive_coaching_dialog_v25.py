# -*- coding: utf-8 -*-
"""V25 bağımsız öğrenme ve adaptif koçluk çalışma alanı.

Çekirdek ödev formundan yalnızca kontrollü öneri aktarım API'sini çağırır.
Gözlemler, tıkanıklıklar ve planlar sadece adaptive_*_v25 tablolarına yazılır.
Qt bağımlılığı çekirdek analiz motorundan tamamen ayrıdır.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date

from html import escape as _html_escape
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit,
    QVBoxLayout, QWidget, QAbstractItemView,
)

import db
from services.adaptive_coaching_v25 import engine
from ui.adaptive_coaching_center_v26 import format_lesson_name, format_action_title
from services.coach_assistant_v1.module_events_v268 import publish_saved_coaching_change


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
        self.setMinimumSize(900, 660)
        self.resize(1120, 810)
        self._build()
        self.refresh()

    def _build(self):
        self.setStyleSheet('''
            QDialog {background:#f8fafc;color:#0f172a;}
            QLabel {color:#334155;}
            QGroupBox {font-weight:700; border:1px solid #cbd5e1; border-radius:9px;
                       margin-top:12px; padding:12px; background:white; color:#0f172a;}
            QGroupBox::title {subcontrol-origin:margin; left:12px; padding:0 6px; color:#1e3a8a;}
            QPushButton {border:1px solid #cbd5e1; border-radius:8px; background:white;
                         padding:7px 14px; color:#0f172a; font-weight:700;}
            QPushButton:hover {background:#eff6ff; border-color:#93c5fd;
                color: #15191E;}
            QTabWidget::pane {border:1px solid #cbd5e1; border-radius:10px; background:white;}
            QTabBar::tab {padding:9px 15px; margin-right:4px; background:#f1f5f9;
                          border:1px solid #cbd5e1; border-bottom:none; border-top-left-radius:8px; border-top-right-radius:8px;
                          color:#475569; font-weight:600;}
            QTabBar::tab:selected {font-weight:800; color:#1d4ed8; background:#ffffff; border-color:#93c5fd;}
            QTableWidget {border:1px solid #cbd5e1; border-radius:8px; gridline-color:#f1f5f9; font-size:12px;
                          selection-background-color:#e0f2fe; selection-color:#0c4a6e;}
            QHeaderView::section {background:#f1f5f9; color:#334155; padding:8px 6px; border:0; border-bottom:1px solid #cbd5e1; font-weight:700;}
            QLineEdit,QComboBox,QSpinBox,QTextEdit {border:1px solid #cbd5e1;
                border-radius:7px; padding:6px; background:white; color:#0f172a;}
        ''')
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(8)
        top_bar = QHBoxLayout()
        header = QLabel(f"🧠  Öğrenme Analizi ve Adaptif Koçluk  ·  {self.student_name} (#{self.student_id})")
        header.setStyleSheet('font-size:18px;font-weight:800;color:#0f172a;padding:4px;')
        top_bar.addWidget(header)
        top_bar.addStretch(1)
        btn_info = QPushButton("ℹ️ Nasıl Çalışır? (Rehber)")
        btn_info.setStyleSheet("""
            QPushButton {
                background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd;
                border-radius: 7px; padding: 6px 14px; font-weight: 700; font-size: 12px;
            }
            QPushButton:hover { background: #bae6fd; border-color: #7dd3fc; 
                color: #15191E;}
        """)
        btn_info.clicked.connect(self._show_info_guide)
        top_bar.addWidget(btn_info)
        root.addLayout(top_bar)
        desc = QLabel('Ödev tikleri öğrenme puanı değildir. Ölçüm ve öneriler ayrı tutulur; yeni ödev için öğretmen onayı gerekir.')
        desc.setWordWrap(True)
        desc.setStyleSheet('color:#475569;font-size:12px;padding:0 4px;')
        root.addWidget(desc)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self._build_decision_v26()
        self._build_overview()
        self._build_observation()
        self._build_plan()
        self._build_blocker()
        # V11 optional outcome tracking within the EXISTING Adaptive Coach dialog.
        from ui.adaptive_followup_v11 import AdaptiveFollowupV11
        self.followup_v11 = AdaptiveFollowupV11(self.student_id, self)
        self.tabs.addTab(self.followup_v11, '📈 Müdahale Takibi')
        self.tabs.currentChanged.connect(self._sync_followup_v11)
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
        box.setContentsMargins(12, 14, 12, 12)
        box.setSpacing(10)
        return page, box

    def _build_decision_v26(self):
        """Modular teacher-decision tab; default entry without changing V25 task flow."""
        from services.adaptive_coaching_v26.flags import enabled as enabled_v26
        self._decision_v26_enabled = enabled_v26()
        if not self._decision_v26_enabled:
            return
        page, layout = self._new_page()
        title = QLabel('🎯 Bu öğrenci için sıradaki en yararlı öğretmen müdahalesi (Neden, Öneri ve Dayanak)')
        title.setStyleSheet('font-size:14.5px;font-weight:800;color:#1e3a8a;')
        layout.addWidget(title)
        self.decision_v26_text = QTextEdit()
        self.decision_v26_text.setReadOnly(True)
        self.decision_v26_text.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.decision_v26_text, 1)
        row = QHBoxLayout()
        assessment = QPushButton('🔬 Tanılayıcı Gözlem Gir (Kazanım Teşhisi)')
        assessment.setStyleSheet('''
            QPushButton {background:#2563eb;color:#ffffff;border:none;border-radius:8px;padding:8px 16px;font-weight:700;}
            QPushButton:hover {background:#1d4ed8;
                color: #FFFFFF;}
        ''')
        assessment.clicked.connect(lambda: self.tabs.setCurrentIndex(self._find_tab('Kazanım Teşhisi')))
        row.addWidget(assessment)
        proposal = QPushButton('🌀 Spiral Ödev Taslağına Git')
        proposal.setStyleSheet('''
            QPushButton {background:#ecfdf5;color:#065f46;border:1px solid #6ee7b7;border-radius:8px;padding:8px 16px;font-weight:700;}
            QPushButton:hover {background:#d1fae5;
                color: #15191E;}
        ''')
        proposal.clicked.connect(lambda: self.tabs.setCurrentIndex(self._find_tab('Spiral Ödev Taslağı')))
        row.addWidget(proposal)
        row.addStretch(1)
        layout.addLayout(row)
        foot_note = QLabel('🛡️ Öneri taslaktır. Mevcut Kaydet, aktarım ve checkbox işleyişine müdahale edilmez.')
        foot_note.setStyleSheet('color:#64748b;font-size:11.5px;')
        layout.addWidget(foot_note)
        self.tabs.addTab(page, '🧠 Koç Karar Masası')

    def _sync_followup_v11(self, index):
        if getattr(self, 'followup_v11', None) is not None and self.tabs.widget(index) is self.followup_v11:
            self.followup_v11.suggest_context(self.lesson.text(), self.topic.text())
            self.followup_v11.refresh()

    def _find_tab(self, title):
        for i in range(self.tabs.count()):
            if title in self.tabs.tabText(i):
                return i
        return 0

    def _refresh_decision_v26(self, con):
        if not getattr(self, '_decision_v26_enabled', False):
            return
        from services.adaptive_coaching_v26.decision import student_decisions
        brief = student_decisions(con, self.student_id, maximum=9)
        status_txt = str(brief.get('status') or '')
        if 'destek' in status_txt.casefold() or 'acil' in status_txt.casefold():
            st_bg, st_fg, st_icon = '#ffe4e6', '#9f1239', '🎯'
        elif 'ölçüm' in status_txt.casefold() or 'tanılayıcı' in status_txt.casefold():
            st_bg, st_fg, st_icon = '#fef3c7', '#92400e', '⚠️'
        else:
            st_bg, st_fg, st_icon = '#dcfce7', '#166534', '✅'

        ctx = brief.get('context', {})
        target_str = ctx.get('target') or '—'
        plan_str = ctx.get('coaching_plan') or '—'
        metrics = brief.get('metrics', {})
        open_hw = metrics.get('open_homework_rows', 0)
        measured_cnt = metrics.get('measured_topics', brief.get('evidence_count', 0))
        unmeasured_cnt = metrics.get('unmeasured_topics', 0)
        support_cnt = metrics.get('support_topics', 0)

        cards_html = []
        for a in brief.get('actions', []):
            cat = str(a.get('category') or '')
            lesson_badge, topic_title = format_action_title(a.get('title') or '')
            if 'destek' in cat.casefold() or 'tıkanıklık' in cat.casefold():
                c_brd, c_hdr, b_bg = '#fecdd3', '#fff1f2', '#e11d48'
            elif 'ölçüm' in cat.casefold():
                c_brd, c_hdr, b_bg = '#fde68a', '#fffbeb', '#d97706'
            else:
                c_brd, c_hdr, b_bg = '#bfdbfe', '#eff6ff', '#1d4ed8'
            lesson_span = (
                f'&nbsp;<span style="background-color:#e2e8f0;color:#1e293b;font-size:11px;font-weight:700;padding:2px 6px;">'
                f'{_html_escape(lesson_badge)}</span>&nbsp;<b style="font-size:13px;color:#0f172a;">› {_html_escape(topic_title)}</b>'
                if lesson_badge else
                f'&nbsp;<b style="font-size:13px;color:#0f172a;">{_html_escape(topic_title)}</b>'
            )
            cards_html.append(f'''
            <table width="100%" cellspacing="0" cellpadding="8" style="margin-bottom:8px;border:1px solid {c_brd};">
              <tr>
                <td bgcolor="{c_hdr}">
                  <span style="background-color:{b_bg};color:#ffffff;font-size:10.5px;font-weight:800;padding:2px 6px;">{_html_escape(cat.upper())}</span>
                  {lesson_span}
                </td>
              </tr>
              <tr>
                <td bgcolor="#ffffff" style="font-size:12px;line-height:1.45;color:#1e293b;">
                  🔎 <b style="color:#475569;">Neden:</b> {_html_escape(str(a.get("reason") or ""))}<br>
                  💡 <b style="color:#0f766e;">Öneri:</b> {_html_escape(str(a.get("next_step") or ""))}<br>
                  📊 <span style="color:#64748b;font-size:11px;"><b>Dayanak:</b> {_html_escape(str(a.get("source") or ""))}</span>
                </td>
              </tr>
            </table>
            ''')

        warn_html = ''
        if brief.get('warnings'):
            w_items = ''.join(f'<li>{_html_escape(str(v))}</li>' for v in brief['warnings'])
            warn_html = f'''
            <table width="100%" cellspacing="0" cellpadding="8" style="margin-top:6px;border:1px solid #fde68a;">
              <tr><td bgcolor="#fffbeb" style="font-size:11.5px;color:#92400e;">
                <b>⚠️ SINIRLAR VE GÜVENLİK NOTLARI</b><ul style="margin:4px 0 0 16px;padding:0;">{w_items}</ul>
              </td></tr>
            </table>
            '''

        html = f'''
        <div style="font-family:'Helvetica Neue',Arial,sans-serif;color:#0f172a;">
          <table width="100%" cellspacing="0" cellpadding="10" style="background-color:#1e3a8a;">
            <tr>
              <td bgcolor="#1e3a8a">
                <div style="font-size:10px;font-weight:700;color:#93c5fd;">KARAR ÖZETİ · ÖĞRETMEN İÇİN ÖNCELİKLİ ADIMLAR</div>
                <div style="font-size:16px;font-weight:800;color:#ffffff;margin-top:2px;">
                  👤 {_html_escape(self.student_name)} <span style="color:#bfdbfe;font-size:13px;">(#{self.student_id})</span>
                </div>
              </td>
              <td bgcolor="#1e3a8a" align="right" valign="middle">
                <span style="background-color:{st_bg};color:{st_fg};font-weight:800;font-size:11.5px;padding:4px 9px;">
                  {st_icon} Durum: {_html_escape(status_txt)}
                </span>
              </td>
            </tr>
          </table>

          <table width="100%" cellspacing="6" cellpadding="8" style="margin-top:4px;">
            <tr>
              <td width="25%" bgcolor="#f8fafc" align="center" style="border:1px solid #cbd5e1;">
                <div style="font-size:10px;font-weight:700;color:#475569;">BAĞIMSIZ GÖZLEM</div>
                <div style="font-size:15px;font-weight:800;color:#0f172a;">{brief.get('evidence_count', 0)} Kayıt</div>
              </td>
              <td width="25%" bgcolor="#eff6ff" align="center" style="border:1px solid #bfdbfe;">
                <div style="font-size:10px;font-weight:700;color:#1d4ed8;">ÖLÇÜLEN / BEKLEYEN</div>
                <div style="font-size:15px;font-weight:800;color:#1e3a8a;">{measured_cnt} / {unmeasured_cnt} Konu</div>
              </td>
              <td width="25%" bgcolor="#fff1f2" align="center" style="border:1px solid #fecdd3;">
                <div style="font-size:10px;font-weight:700;color:#be123c;">DESTEK SİNYALİ</div>
                <div style="font-size:15px;font-weight:800;color:#9f1239;">{support_cnt} Konu</div>
              </td>
              <td width="25%" bgcolor="#fffbeb" align="center" style="border:1px solid #fde68a;">
                <div style="font-size:10px;font-weight:700;color:#b45309;">AÇIK ÖDEV SATIRI</div>
                <div style="font-size:15px;font-weight:800;color:#92400e;">{open_hw} Satır</div>
              </td>
            </tr>
          </table>

          <table width="100%" cellspacing="0" cellpadding="8" style="border:1px solid #e2e8f0;margin-bottom:8px;">
            <tr>
              <td bgcolor="#f1f5f9" style="font-size:11.5px;color:#334155;">
                🎯 <b>Hedef:</b> {_html_escape(str(target_str))} &nbsp;&nbsp;|&nbsp;&nbsp;
                📅 <b>Koçluk Planı:</b> {_html_escape(str(plan_str))}
              </td>
            </tr>
          </table>

          {''.join(cards_html)}
          {warn_html}
        </div>
        '''
        self.decision_v26_text.setHtml(html)

    def _build_overview(self):
        page, layout = self._new_page()
        self.summary = QLabel('')
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.TextFormat.RichText)
        self.summary.setStyleSheet('font-size:12.5px;font-weight:600;padding:10px 12px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;')
        layout.addWidget(self.summary)
        self.topic_table = QTableWidget(0, 8)
        self.topic_table.setHorizontalHeaderLabels([
            'Ders', 'Konu', 'Tamamlanan Ödev', 'Açık Ödev',
            'Gözlem Sayısı', 'Doğruluk', 'Kanıt Durumu (Rozet)', 'Son Ölçüm'
        ])
        self.topic_table.verticalHeader().setDefaultSectionSize(36)
        self.topic_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.topic_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.topic_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        hdr = self.topic_table.horizontalHeader()
        hdr.setMinimumSectionSize(88)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col_idx in (2, 3, 4, 5, 6, 7):
            hdr.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.ResizeToContents)
        self.topic_table.doubleClicked.connect(self._topic_to_observation)
        layout.addWidget(self.topic_table, 1)
        help_label = QLabel('💡 İpucu: Bir konuya çift tıklayarak doğrudan Kazanım Teşhisi (yeni gözlem) sekmesine geçebilirsiniz. Tamamlanan ödev tiki tek başına kazanımın öğrenildiğini göstermez.')
        help_label.setWordWrap(True)
        help_label.setStyleSheet('color:#475569;font-size:11.5px;')
        layout.addWidget(help_label)
        self.tabs.addTab(page, 'Öğrenme Panosu')

    def _build_observation(self):
        page, layout = self._new_page()
        guide = QLabel(
            '🔬 <b>KAZANIM TEŞHİSİ NASIL KULLANILIR?</b> Öğrenciye sorduğunuz 5–8 bağımsız sorunun '
            '(mini yoklama / sözlü kontrol) doğru, yanlış ve boş sayılarını kaydedin. '
            'Bu kayıt mevcut ödev tiklerini değiştirmez; koçluk motoru için gerçek öğrenme kanıtı üretir.'
        )
        guide.setWordWrap(True)
        guide.setStyleSheet('background:#f0fdf4;color:#166534;border:1px solid #86efac;border-radius:8px;padding:9px 12px;font-size:12px;')
        layout.addWidget(guide)
        group = QGroupBox('Tanılayıcı Öğrenme Gözlemi Kayıt Formu')
        form = QFormLayout(group)
        form.setSpacing(9)
        self.source = QComboBox()
        self.source.currentIndexChanged.connect(self._source_changed)
        form.addRow('İlgili Ödev:', self.source)
        self.lesson = QLineEdit()
        self.topic = QLineEdit()
        self.subskill = QLineEdit()
        self.subskill.setPlaceholderText('Örn: Özkütle–kütle/hacim grafiği')
        form.addRow('Ders:', self.lesson)
        form.addRow('Konu:', self.topic)
        form.addRow('Alt Kazanım / Mikro Eksik:', self.subskill)
        self.mode = QComboBox()
        self.mode.addItems(engine.MODES)
        form.addRow('Yoklama Yöntemi:', self.mode)
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
        for caption, spin in [('🟢 Doğru:', self.correct), ('🔴 Yanlış:', self.wrong), ('⚪ Boş:', self.blank), ('⏱️ Dakika:', self.duration)]:
            lbl = QLabel(caption)
            lbl.setStyleSheet('font-weight:700;')
            mrow.addWidget(lbl)
            mrow.addWidget(spin)
        form.addRow('Değerlendirme:', measures)
        self.reason = QComboBox()
        self.reason.addItems(engine.REASONS)
        self.reason.setCurrentText('Belirtilmedi')
        form.addRow('Hata / Zorlanma Nedeni:', self.reason)
        self.note = QTextEdit()
        self.note.setPlaceholderText('Öğrencinin gerekçesi, örnek soru veya koçun gözlemi...')
        self.note.setMaximumHeight(95)
        form.addRow('Açıklama:', self.note)
        layout.addWidget(group)
        actions = QHBoxLayout()
        actions.addStretch(1)
        btn = QPushButton('✓ Gözlemi Kaydet')
        btn.setStyleSheet('''
            QPushButton {background:#16a34a;color:#262626;border:none;border-radius:8px;padding:8px 18px;font-weight:800;}
            QPushButton:hover {background:#15803d;
                color: #FFFFFF;}
        ''')
        btn.clicked.connect(self._save_observation)
        actions.addWidget(btn)
        layout.addLayout(actions)
        info = QLabel('🛡️ Gözlem kaydedilse bile eski ödevin tamamlanma tikleri değişmez. '
                      'Ödev listesinde olmayan bir konu için “Bağımsız gözlem” seçebilirsiniz.')
        info.setWordWrap(True)
        info.setStyleSheet('color:#64748b;font-size:11.5px;')
        layout.addWidget(info)
        layout.addStretch(1)
        self.tabs.addTab(page, 'Kazanım Teşhisi')

    def _build_plan(self):
        page, layout = self._new_page()
        group = QGroupBox('Öğrenciye Özel Spiral Öneri Ayarları (%70 Odak / %30 Aralıklı Tekrar)')
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
        self.style.addItems(['Dengeli', 'Zaman bloklu', 'Mikro adım', 'Zorlayıcı'])
        for index, (name, field) in enumerate([
            ('Haftalık çalışma bütçesi:', self.weekly), ('Tekrar payı (varsayılan %30):', self.review),
            ('Oturum üst sınırı:', self.session), ('Çalışma yaklaşımı:', self.style)]):
            lbl = QLabel(name)
            lbl.setStyleSheet('font-weight:700;')
            form.addWidget(lbl, index // 2, (index % 2) * 2)
            form.addWidget(field, index // 2, (index % 2) * 2 + 1)
        layout.addWidget(group)
        controls = QHBoxLayout()
        self.preview_btn = QPushButton('⚡ Önerileri Hesapla')
        self.preview_btn.setStyleSheet('''
            QPushButton {background:#2563eb;color:#ffffff;border:none;border-radius:8px;padding:8px 16px;font-weight:700;}
            QPushButton:hover {background:#1d4ed8;
                color: #FFFFFF;}
        ''')
        self.preview_btn.clicked.connect(self._preview)
        self.save_pref = QPushButton('💾 Öğrenci Ayarlarını Kaydet')
        self.save_pref.clicked.connect(self._save_preferences)
        controls.addWidget(self.preview_btn)
        controls.addWidget(self.save_pref)
        controls.addStretch(1)
        layout.addLayout(controls)
        self.plan_summary = QLabel('Öneri henüz hesaplanmadı.')
        self.plan_summary.setWordWrap(True)
        self.plan_summary.setStyleSheet('background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:8px 12px;font-weight:600;color:#1e3a8a;')
        layout.addWidget(self.plan_summary)
        self.plan_table = QTableWidget(0, 6)
        self.plan_table.setHorizontalHeaderLabels(['Seç', 'Ders', 'Konu', 'Spiral Rolü / Tür', 'Önerilen Yöntem', 'Dakika'])
        self.plan_table.verticalHeader().setDefaultSectionSize(36)
        self.plan_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        phdr = self.plan_table.horizontalHeader()
        phdr.setMinimumSectionSize(70)
        for col_idx in (0, 1, 3, 4, 5):
            phdr.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.ResizeToContents)
        phdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.plan_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.plan_table, 1)
        actions = QHBoxLayout()
        self.save_draft = QPushButton('📝 Taslağı Kaydet (Ödev Verme Değil)')
        self.save_draft.clicked.connect(self._save_plan)
        self.save_draft.setEnabled(False)
        self.transfer_btn = QPushButton('🚀 Seçilenleri Ödev Listesine Aktar')
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
        guide = QLabel(
            '🚧 <b>TIKANIKLIK ANALİZİ NEDİR?</b> Geciken veya çok ödev verildiği halde ilerlemeyen konularda '
            'tıkanıklık nedenini (<i>İş yükü, Kavram eksikliği, Motivasyon vb.</i>) ve koçun müdahale kararını kaydedin. '
            'Eski ödev otomatik devredilmez, silinmez veya borçlandırılmaz.'
        )
        guide.setWordWrap(True)
        guide.setStyleSheet('background:#fffbeb;color:#92400e;border:1px solid #fde68a;border-radius:8px;padding:9px 12px;font-size:12px;')
        layout.addWidget(guide)
        group = QGroupBox('Geciken Ödev / Tıkanıklık Değerlendirmesi')
        form = QFormLayout(group)
        self.blocker_source = QComboBox()
        form.addRow('İlgili Ödev (İsteğe Bağlı):', self.blocker_source)
        self.blocker_reason = QComboBox()
        self.blocker_reason.addItems(engine.REASONS[:-1])
        form.addRow('Tıkanıklık Nedeni:', self.blocker_reason)
        self.blocker_note = QTextEdit()
        self.blocker_note.setMaximumHeight(85)
        self.blocker_note.setPlaceholderText('Öğrencinin yaşadığı zorluğu kısaca not edin...')
        form.addRow('Ne Oldu?', self.blocker_note)
        self.blocker_resolution = QLineEdit()
        self.blocker_resolution.setPlaceholderText('Örn: Kapsamı daralt, 15 dk örnek çöz, cuma günü yeniden görüş')
        form.addRow('Koçun Müdahale Kararı:', self.blocker_resolution)
        layout.addWidget(group)
        row = QHBoxLayout()
        row.addStretch(1)
        btn = QPushButton('✓ Tıkanıklığı Kaydet')
        btn.setStyleSheet('''
            QPushButton {background:#d97706;color:#292929;border:none;border-radius:8px;padding:8px 18px;font-weight:800;}
            QPushButton:hover {background:#b45309;
                color: #FFFFFF;}
        ''')
        btn.clicked.connect(self._save_blocker)
        row.addWidget(btn)
        layout.addLayout(row)
        self.blocker_list = QTableWidget(0, 3)
        self.blocker_list.setHorizontalHeaderLabels(['Kayıt Tarihi', 'Tıkanıklık Nedeni', 'Koçun Müdahale Kararı'])
        self.blocker_list.verticalHeader().setDefaultSectionSize(36)
        self.blocker_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.blocker_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.blocker_list.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.blocker_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.blocker_list, 1)
        foot = QLabel('🛡️ Eski ödev otomatik devredilmez, silinmez veya borçlandırılmaz.')
        foot.setStyleSheet('color:#64748b;font-size:11.5px;')
        layout.addWidget(foot)
        self.tabs.addTab(page, 'Tıkanıklık Analizi')

    def refresh(self):
        try:
            with _connection() as con:
                self._refresh_decision_v26(con)
                summary = engine.student_overview(con, self.student_id)
                topics = engine.student_topics(con, self.student_id)
                blockers = engine.get_blockers(con, self.student_id)
                prefs = engine.load_preferences(con, self.student_id)
                self._homework = [dict(r) for r in con.execute('''
                    SELECT o.id,o.ders,o.konu_ad,o.kitap_ad,o.durum
                    FROM odev o JOIN odev_kume k ON k.id=o.kume_id
                    WHERE o.ogrenci_id=? AND k.ogrenci_id=? ORDER BY o.id DESC LIMIT 600
                ''', (self.student_id, self.student_id))]
            self._render_overview(summary, topics)
            self._render_sources()
            self._render_blockers(blockers)
            # Existing learning observations may have changed since last view.
            if getattr(self, 'followup_v11', None) is not None:
                self.followup_v11.refresh()
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
            QMessageBox.critical(self, 'Koçluk verileri', f'Veriler alınamadı: {exc}')

    def _render_overview(self, stats, topics):
        self.summary.setText(
            f'<span style="color:#1e3a8a;font-weight:800;">📚 {stats["topic_count"]} konu</span>'
            f' &nbsp;&nbsp;|&nbsp;&nbsp; '
            f'<span style="color:#15803d;font-weight:800;">🔬 {stats["measured_topics"]} ölçülen konu</span>'
            f' &nbsp;&nbsp;|&nbsp;&nbsp; '
            f'<span style="color:#be123c;font-weight:800;">🎯 {stats["support_topics"]} hedefli destek</span>'
            f' &nbsp;&nbsp;|&nbsp;&nbsp; '
            f'<span style="color:#0369a1;font-weight:800;">🔄 {stats["due_topics"]} tekrar hatırlatması</span>'
            f' &nbsp;&nbsp;|&nbsp;&nbsp; '
            f'<span style="color:#b45309;font-weight:800;">📋 {stats["open_homework_rows"]} açık ödev satırı</span>'
            f' &nbsp;&nbsp;|&nbsp;&nbsp; '
            f'<span style="color:#6b21a8;font-weight:800;">🚧 {stats["blockers"]} tıkanıklık kaydı</span>'
        )
        self.topic_table.setRowCount(len(topics))
        bold_font = QFont()
        bold_font.setBold(True)
        for r, t in enumerate(topics):
            lvl = str(t.get('level') or '')
            if 'destek' in lvl.casefold():
                lvl_txt, l_bg, l_fg = f'🎯 {lvl}', '#ffe4e6', '#9f1239'
            elif 'ölçüm gerekli' in lvl.casefold():
                lvl_txt, l_bg, l_fg = f'⚠️ {lvl}', '#fef3c7', '#92400e'
            elif 'olumlu' in lvl.casefold() or 'güçlü' in lvl.casefold():
                lvl_txt, l_bg, l_fg = f'✅ {lvl}', '#dcfce7', '#166534'
            else:
                lvl_txt, l_bg, l_fg = f'📈 {lvl}', '#e0f2fe', '#075985'

            acc = t.get('accuracy')
            acc_str = f"%{acc}" if acc is not None else '—'
            cells = [
                format_lesson_name(t['lesson']),
                t['topic'],
                t['done_count'],
                t['open_count'],
                t['observations'],
                acc_str,
                lvl_txt,
                t['last_observed_on'].isoformat() if t['last_observed_on'] else '—',
            ]
            for c, val in enumerate(cells):
                cell = QTableWidgetItem(str(val))
                if c == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, str(t['lesson']))
                    cell.setFont(bold_font)
                elif c in (2, 3, 4, 5, 7):
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if c == 5 and acc is not None:
                        cell.setFont(bold_font)
                        cell.setForeground(QBrush(QColor('#166534' if acc >= 70 else '#9f1239' if acc < 50 else '#92400e')))
                elif c == 6:
                    cell.setBackground(QBrush(QColor(l_bg)))
                    cell.setForeground(QBrush(QColor(l_fg)))
                    cell.setFont(bold_font)
                self.topic_table.setItem(r, c, cell)

    def _render_sources(self):
        previous_id = self.source.currentData()
        self.source.blockSignals(True)
        self.source.clear()
        self.blocker_source.clear()
        self.source.addItem('Bağımsız gözlem (ödev bağlantısı yok)', None)
        self.blocker_source.addItem('Genel tıkanıklık (ödev bağlantısı yok)', None)
        for r in self._homework:
            label = f"#{r['id']} · {format_lesson_name(r['ders'])} / {r['kitap_ad']} / {r['konu_ad']} ({r['durum']})"
            self.source.addItem(label, r['id'])
            self.blocker_source.addItem(label, r['id'])
        target = self.initial_homework_id if self.initial_homework_id is not None else previous_id
        idx = self.source.findData(target)
        self.source.setCurrentIndex(idx if idx >= 0 else 0)
        self.source.blockSignals(False)
        self._source_changed()

    def _source_changed(self, *_):
        oid = self.source.currentData()
        r = next((row for row in self._homework if row['id'] == oid), None)
        self.lesson.setReadOnly(bool(r))
        self.topic.setReadOnly(bool(r))
        if r:
            self.lesson.setText(r['ders'])
            self.topic.setText(r['konu_ad'])

    def _topic_to_observation(self, index):
        r = index.row()
        lesson = self.topic_table.item(r, 0)
        topic = self.topic_table.item(r, 1)
        if not lesson or not topic:
            return
        self.source.setCurrentIndex(0)
        raw_lesson = lesson.data(Qt.ItemDataRole.UserRole) or lesson.text()
        self.lesson.setText(str(raw_lesson))
        self.topic.setText(topic.text())
        self.tabs.setCurrentIndex(self._find_tab('Kazanım Teşhisi'))

    def _render_blockers(self, rows):
        self.blocker_list.setRowCount(len(rows))
        bold_font = QFont()
        bold_font.setBold(True)
        for row, r in enumerate(rows):
            for col, val in enumerate((r['created_at'], r['reason'], r['resolution'] or '—')):
                cell = QTableWidgetItem(str(val))
                if col == 1:
                    cell.setBackground(QBrush(QColor('#fffbeb')))
                    cell.setForeground(QBrush(QColor('#92400e')))
                    cell.setFont(bold_font)
                self.blocker_list.setItem(row, col, cell)

    def _save_observation(self):
        try:
            with _connection() as con:
                engine.save_observation(con, self.student_id, self.lesson.text(), self.topic.text(),
                    homework_id=self.source.currentData(), subskill=self.subskill.text(),
                    mode=self.mode.currentText(), correct=self.correct.value(), wrong=self.wrong.value(),
                    blank=self.blank.value(), duration_min=self.duration.value(),
                    reason=self.reason.currentText(), note=self.note.toPlainText(),
                    observed_on=date.today())
            publish_saved_coaching_change('independent_measurement', self.student_id,
                                         lesson=self.lesson.text(), topic=self.topic.text())
            QMessageBox.information(self, 'Kaydedildi', 'Tanılayıcı gözlem kaydedildi. Eski ödev tikleri değişmedi.')
            self.correct.setValue(0); self.wrong.setValue(0); self.blank.setValue(0)
            self.note.clear()
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, 'Gözlem kaydedilemedi', str(exc))

    def _save_blocker(self):
        try:
            with _connection() as con:
                engine.save_blocker(con, self.student_id, self.blocker_reason.currentText(),
                    self.blocker_note.toPlainText(), homework_id=self.blocker_source.currentData(),
                    resolution=self.blocker_resolution.text() or None)
            publish_saved_coaching_change('coaching_plan', self.student_id)
            QMessageBox.information(self, 'Kaydedildi', 'Tıkanıklık değerlendirmesi ayrı kayda alındı.')
            self.blocker_note.clear(); self.blocker_resolution.clear()
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, 'Tıkanıklık kaydedilemedi', str(exc))

    def _preferences(self):
        return {'weekly_minutes': self.weekly.value(), 'review_percent': self.review.value(),
                'max_session_minutes': self.session.value(), 'learning_style': self.style.currentText()}

    def _save_preferences(self):
        try:
            with _connection() as con:
                engine.save_preferences(con, self.student_id, self._preferences())
            publish_saved_coaching_change('student_profile', self.student_id)
            QMessageBox.information(self, 'Kaydedildi', 'Öğrenciye özel tercih ve sınırlar kaydedildi.')
            self.current_plan = None
            self.save_draft.setEnabled(False)
            self.transfer_btn.setEnabled(False)
        except Exception as exc:
            QMessageBox.warning(self, 'Ayar hatası', str(exc))

    def _preview(self):
        try:
            with _connection() as con:
                self.current_plan = engine.make_plan(con, self.student_id, self._preferences())
            p = self.current_plan
            self.plan_summary.setText(
                f"📌 {len(p['items'])} öneri  ·  ⏱️ {p['planned_minutes']} dk toplam  ·  "
                f"🎯 {p['focus_minutes']} dk güncel odak  ·  🔄 {p['review_minutes']} dk aralıklı tekrar  ·  "
                f"🛡️ {p['unused_minutes']} dk rezerve.\n" + '\n'.join(p['warnings'])
            )
            self.plan_table.setRowCount(len(p['items']))
            bold_font = QFont()
            bold_font.setBold(True)
            for r, item in enumerate(p['items']):
                select = QTableWidgetItem('')
                select.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                select.setCheckState(Qt.CheckState.Checked)
                select.setToolTip(item['details'])
                self.plan_table.setItem(r, 0, select)
                cat_val = str(item.get('category') or '')
                for c, key in enumerate(('lesson', 'topic', 'category', 'mode', 'minutes'), 1):
                    disp = format_lesson_name(item[key]) if key == 'lesson' else str(item[key])
                    if key == 'category':
                        disp = f'🔄 {disp}' if 'tekrar' in cat_val.casefold() else f'🎯 {disp}'
                    cell = QTableWidgetItem(disp)
                    cell.setToolTip(item['details'])
                    if key == 'lesson':
                        cell.setFont(bold_font)
                    elif key == 'category':
                        cell.setFont(bold_font)
                        if 'tekrar' in cat_val.casefold():
                            cell.setBackground(QBrush(QColor('#e0f2fe')))
                            cell.setForeground(QBrush(QColor('#075985')))
                        else:
                            cell.setBackground(QBrush(QColor('#fef3c7')))
                            cell.setForeground(QBrush(QColor('#92400e')))
                    elif key == 'minutes':
                        cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        cell.setFont(bold_font)
                    self.plan_table.setItem(r, c, cell)
            self.save_draft.setEnabled(bool(p['items']))
            self.transfer_btn.setEnabled(bool(p['items']) and callable(getattr(self.host, '_wizard_transfer_tasks', None)))
        except Exception as exc:
            self.current_plan = None
            self.save_draft.setEnabled(False)
            self.transfer_btn.setEnabled(False)
            QMessageBox.warning(self, 'Plan hazırlanamadı', str(exc))


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
            publish_saved_coaching_change('coaching_plan', self.student_id)
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
