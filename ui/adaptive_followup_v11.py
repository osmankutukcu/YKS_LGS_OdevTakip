# -*- coding: utf-8 -*-
"""Optional tab in EXISTING Adaptive Koç dialog. Teacher initiated; no homework writes."""
from __future__ import annotations

from html import escape as _html_escape
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QTextEdit, QPushButton, QMessageBox, QFormLayout, QGroupBox
)

from services.adaptive_outcomes_v11 import (
    ACTIONS, REVIEWS, record_intervention, review_intervention,
    list_interventions, evaluate_intervention,
)
from ui.adaptive_coaching_center_v26 import format_lesson_name
from ui.theme import register_theme_listener
from ui.theme_report_canvas_v40 import report_paper_qss


class AdaptiveFollowupV11(QWidget):
    def __init__(self, student_id, parent=None):
        super().__init__(parent)
        self.student_id = int(student_id)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        self._v40_header = header = QLabel(
            '📈 <b>MÜDAHALE–SONUÇ TAKİBİ NASIL ÇALIŞIR?</b> Öğrenciye uyguladığınız koçluk adımını kaydedin; '
            'sistem müdahaleden <b>önceki 45 gün</b> ile <b>sonraki 45 gün</b> arasındaki bağımsız ölçüm değişimini karşılaştırır. '
            'Ödev tikleri ve koçluk motoru otomatik değişmez.'
        )
        header.setWordWrap(True)
        header.setStyleSheet('background:#faf5ff;color:#6b21a8;border:1px solid #d8b4fe;border-radius:8px;padding:9px 12px;font-size:12px;')
        lay.addWidget(header)

        grp = QGroupBox('Yeni Müdahale Adımı Kaydet (Öğretmen Onaylı)')
        form = QFormLayout(grp)
        form.setSpacing(8)
        self.lesson = QLineEdit()
        self.topic = QLineEdit()
        self.lesson.setPlaceholderText('Örn: TYT Matematik')
        self.topic.setPlaceholderText('Örn: Parabol')
        form.addRow('Ders:', self.lesson)
        form.addRow('Konu:', self.topic)
        self.action = QComboBox()
        for code, label in ACTIONS.items():
            self.action.addItem(label, code)
        form.addRow('Uygulanan Adım:', self.action)
        self.rationale = QLineEdit()
        self.rationale.setMaxLength(500)
        self.rationale.setPlaceholderText('İsteğe bağlı kısa açıklama (Örn: 10 soruluk rehberli tekrar yapıldı)')
        form.addRow('Gerekçe / Not:', self.rationale)
        lay.addWidget(grp)

        row = QHBoxLayout()
        save = QPushButton('✓ Uyguladığım Adımı Kaydet')
        save.setStyleSheet('''
            QPushButton {background:#7c3aed;color:#ffffff;border:none;border-radius:8px;padding:8px 18px;font-weight:800;}
            QPushButton:hover {background:#6d28d9;
                color: #FFFFFF;}
        ''')
        save.clicked.connect(self._record)
        row.addWidget(save)
        row.addStretch(1)
        lay.addLayout(row)

        select = QHBoxLayout()
        lbl_rec = QLabel('📋 Kayıtlı Müdahaleler:')
        lbl_rec.setStyleSheet('font-weight:700;color:#1e293b;')
        select.addWidget(lbl_rec)
        self.records = QComboBox()
        self.records.currentIndexChanged.connect(self._selected)
        select.addWidget(self.records, 1)
        refresh = QPushButton('↻ Ölçümleri Yenile')
        refresh.clicked.connect(self.refresh)
        select.addWidget(refresh)
        lay.addLayout(select)

        self.summary = QTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        lay.addWidget(self.summary, 1)

        reviewrow = QHBoxLayout()
        lbl_rev = QLabel('🎯 Öğretmen Değerlendirmesi:')
        lbl_rev.setStyleSheet('font-weight:700;color:#1e293b;')
        reviewrow.addWidget(lbl_rev)
        self.rating = QComboBox()
        for key, label in REVIEWS.items():
            self.rating.addItem(label, key)
        reviewrow.addWidget(self.rating, 1)
        vote = QPushButton('💾 Öğretmen Değerlendirmemi Kaydet')
        vote.clicked.connect(self._review)
        reviewrow.addWidget(vote)
        lay.addLayout(reviewrow)
        register_theme_listener(self)
        self._on_theme_changed()
        self.refresh()

    def _on_theme_changed(self):
        # Preserve status-coloured HTML with a neutral, bounded document canvas.
        self.summary.setStyleSheet(report_paper_qss())
        self._v40_header.setStyleSheet(
            'background:#FAF5FF;color:#6B21A8;border:1px solid #D8B4FE;'
            'border-radius:8px;padding:9px 12px;font-size:12px;')

    def suggest_context(self, lesson, topic):
        if lesson and not self.lesson.text().strip():
            self.lesson.setText(str(lesson))
        if topic and not self.topic.text().strip():
            self.topic.setText(str(topic))

    def _record(self):
        from db import get_conn
        try:
            result = QMessageBox.question(
                self, 'Onay',
                'Bu adımı gerçekten uyguladığınızı kendi adınıza kaydetmek istiyor musunuz?\n'
                'Öğrenciye otomatik ödev verilmez.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if result != QMessageBox.StandardButton.Yes:
                return
            con = get_conn()
            try:
                record_intervention(con, self.student_id, self.lesson.text(), self.topic.text(),
                                    self.action.currentData(), rationale=self.rationale.text(), teacher_confirmed=True)
            finally:
                con.close()
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, 'Takip kaydı oluşturulamadı', str(exc))

    def refresh(self):
        from db import get_conn
        old_id = self.records.currentData()
        try:
            con = get_conn()
            try:
                rows = list_interventions(con, self.student_id, limit=20)
            finally:
                con.close()
            self.records.blockSignals(True)
            self.records.clear()
            for r in rows:
                label = f"{r['applied_on']} · {format_lesson_name(r['lesson'])} / {r['topic']} · {ACTIONS.get(r['action_code'], 'Takip')}"
                self.records.addItem(label, r['id'])
            if old_id is not None:
                idx = self.records.findData(old_id)
                if idx >= 0:
                    self.records.setCurrentIndex(idx)
            self.records.blockSignals(False)
            self._selected()
        except Exception as exc:
            self.summary.setPlainText('Takip kayıtları şu an gösterilemiyor: ' + str(exc))

    def _selected(self, *_):
        rid = self.records.currentData()
        if rid is None:
            self.summary.setHtml('''
            <div style="font-family:'Helvetica Neue',Arial,sans-serif;color:#334155;font-size:12px;">
              <table width="100%" cellspacing="0" cellpadding="12" style="border:1px solid #cbd5e1;">
                <tr>
                  <td bgcolor="#f8fafc">
                    <b style="font-size:13px;color:#1e293b;">ℹ️ Henüz Kayıtlı Müdahale Bulunmuyor</b><br><br>
                    Yukarıdaki formdan öğrenciye uyguladığınız adımı (<i>örn. kısa bağımsız yoklama, rehberli soru çözümü, kapsam daraltma</i>)
                    onaylayarak kaydettiğinizde, önceki ve sonraki ölçüm karşılaştırma kartları burada görüntülenir.
                  </td>
                </tr>
              </table>
            </div>
            ''')
            return
        from db import get_conn
        try:
            con = get_conn()
            try:
                report = evaluate_intervention(con, self.student_id, rid)
            finally:
                con.close()
            start, end = report['baseline'], report['followup']
            b_acc = f"%{start['accuracy']}" if start['accuracy'] is not None else 'Ölçüm yok'
            f_acc = f"%{end['accuracy']}" if end['accuracy'] is not None else 'Ölçüm yok'
            delta = report.get('delta_percentage_points')
            if delta is not None:
                delta_str = f"{'+' if delta >= 0 else ''}{delta} puan"
                d_bg, d_fg = ('#dcfce7', '#166534') if delta > 0 else ('#ffe4e6', '#9f1239') if delta < 0 else ('#f1f5f9', '#334155')
            else:
                delta_str = 'Karşılaştırma Bekleniyor'
                d_bg, d_fg = '#fef3c7', '#92400e'

            rev_lbl = REVIEWS.get(report.get('teacher_review'), 'Henüz değerlendirilmedi')
            html = f'''
            <div style="font-family:'Helvetica Neue',Arial,sans-serif;color:#0f172a;font-size:12px;">
              <table width="100%" cellspacing="0" cellpadding="9" style="background-color:#4c1d95;margin-bottom:6px;">
                <tr>
                  <td bgcolor="#4c1d95">
                    <span style="color:#ddd6fe;font-size:10px;font-weight:700;">UYGULANAN MÜDAHALE ADIMI</span><br>
                    <b style="color:#ffffff;font-size:14px;">{_html_escape(str(report.get("action_name") or ""))}</b>
                    <span style="color:#c4b5fd;font-size:12px;"> · Tarih: {_html_escape(str(report.get("applied_on") or ""))}</span>
                  </td>
                  <td bgcolor="#4c1d95" align="right" valign="middle">
                    <span style="background-color:{d_bg};color:{d_fg};font-weight:800;font-size:11.5px;padding:4px 8px;">
                      Fark: {_html_escape(delta_str)}
                    </span>
                  </td>
                </tr>
              </table>

              <table width="100%" cellspacing="6" cellpadding="9" style="margin-bottom:6px;">
                <tr>
                  <td width="50%" bgcolor="#f8fafc" style="border:1px solid #cbd5e1;">
                    <div style="font-size:10.5px;font-weight:800;color:#475569;">⏪ ÖNCEKİ 45 GÜN (BAZ ÖLÇÜM)</div>
                    <div style="font-size:16px;font-weight:800;color:#0f172a;margin-top:3px;">Doğruluk: {_html_escape(b_acc)}</div>
                    <div style="font-size:11px;color:#64748b;margin-top:2px;">{start['days']} ölçüm günü · {start['attempts']} soru</div>
                  </td>
                  <td width="50%" bgcolor="#ecfdf5" style="border:1px solid #6ee7b7;">
                    <div style="font-size:10.5px;font-weight:800;color:#047857;">⏩ SONRAKİ 45 GÜN (İZLEM ÖLÇÜMÜ)</div>
                    <div style="font-size:16px;font-weight:800;color:#065f46;margin-top:3px;">Doğruluk: {_html_escape(f_acc)}</div>
                    <div style="font-size:11px;color:#047857;margin-top:2px;">{end['days']} ölçüm günü · {end['attempts']} soru</div>
                  </td>
                </tr>
              </table>

              <table width="100%" cellspacing="0" cellpadding="8" style="border:1px solid #cbd5e1;">
                <tr>
                  <td bgcolor="#ffffff" style="line-height:1.45;">
                    📌 <b>Durum:</b> {_html_escape(str(report.get("status") or ""))}<br>
                    💡 <b>Önerilen Sonraki Adım:</b> {_html_escape(str(report.get("next_step") or ""))}<br>
                    🎯 <b>Öğretmen Değerlendirmesi:</b> <span style="color:#6b21a8;font-weight:700;">{_html_escape(str(rev_lbl))}</span><br>
                    <span style="color:#64748b;font-size:11px;">⚠️ {_html_escape(str(report.get("warning") or ""))}</span>
                  </td>
                </tr>
              </table>
            </div>
            '''
            self.summary.setHtml(html)
        except Exception as exc:
            self.summary.setPlainText('Karşılaştırma gösterilemiyor: ' + str(exc))

    def _review(self):
        rid = self.records.currentData()
        if rid is None:
            return
        from db import get_conn
        try:
            con = get_conn()
            try:
                review_intervention(con, self.student_id, rid, self.rating.currentData())
            finally:
                con.close()
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, 'Değerlendirme kaydedilemedi', str(exc))

