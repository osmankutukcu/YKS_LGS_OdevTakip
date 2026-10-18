# -*- coding: utf-8 -*-
"""V26 kurum koçluk çalışma masası: toplu salt-okunur önceliklendirme.

Ödev takibi / kontrolü değiştirmez. Öğrenci ayrıntıları için V25 öğretmen
penceresini açar; yeni ödev oluşturma yalnızca özgün ödev formundadır.
"""
from __future__ import annotations

from html import escape as _html_escape
import re as _re
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import (QAbstractItemView, QDialog, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSplitter, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget)
import db
from services.adaptive_coaching_v25 import engine
from services.adaptive_coaching_v26 import decision
from ui.theme import register_theme_listener
from ui.theme_tokens_v37 import semantic_palette
from ui.theme_report_canvas_v40 import report_paper_qss


_LESSON_LABELS = {
    'tyt_turkce': 'TYT Türkçe',
    'tyt_matematik': 'TYT Matematik',
    'ayt_matematik': 'AYT Matematik',
    'tyt_geometri': 'TYT Geometri',
    'ayt_geometri': 'AYT Geometri',
    'geometri': 'Geometri',
    'tyt_fizik': 'TYT Fizik',
    'ayt_fizik': 'AYT Fizik',
    'fizik': 'Fizik',
    'tyt_kimya': 'TYT Kimya',
    'ayt_kimya': 'AYT Kimya',
    'kimya': 'Kimya',
    'tyt_biyoloji': 'TYT Biyoloji',
    'ayt_biyoloji': 'AYT Biyoloji',
    'biyoloji': 'Biyoloji',
    'tyt_tarih': 'TYT Tarih',
    'ayt_tarih': 'AYT Tarih',
    'tarih': 'Tarih',
    'tyt_cografya': 'TYT Coğrafya',
    'ayt_cografya': 'AYT Coğrafya',
    'cografya': 'Coğrafya',
    'tyt_felsefe': 'TYT Felsefe',
    'felsefe': 'Felsefe',
    'tyt_din': 'TYT Din Kültürü',
    'din_kulturu': 'Din Kültürü',
    'ayt_edebiyat': 'AYT Edebiyat',
    'edebiyat': 'Edebiyat',
    'lgs_turkce': 'LGS Türkçe',
    'lgs_matematik': 'LGS Matematik',
    'lgs_fen': 'LGS Fen Bilimleri',
    'lgs_inkilap': 'LGS İnkılap Tarihi',
    'lgs_ingilizce': 'LGS İngilizce',
    'lgs_din': 'LGS Din Kültürü',
    'turkce': 'Türkçe',
    'matematik': 'Matematik',
}


def format_lesson_name(raw: str) -> str:
    text = str(raw or '').strip()
    if not text:
        return ''
    key = text.casefold().replace(' ', '_').replace('-', '_')
    if key in _LESSON_LABELS:
        return _LESSON_LABELS[key]
    if '_' in text:
        parts = text.split('_')
        out = []
        for p in parts:
            low = p.casefold()
            if low in ('tyt', 'ayt', 'lgs', 'ydt'):
                out.append(low.upper())
            else:
                out.append(p.capitalize())
        return ' '.join(out)
    return text


def format_action_title(raw_title: str) -> tuple[str, str]:
    """Return (lesson_badge, topic_title) from 'ayt_matematik / Eşitsizlikler' or plain title."""
    text = str(raw_title or '').strip()
    if ' / ' in text:
        left, right = text.split(' / ', 1)
        return format_lesson_name(left), right.strip()
    return '', text


class AdaptiveCoachingCenterV26(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Adaptif Koçluk Merkezi • Öğretmen Karar Masası')
        self.setMinimumSize(1020, 680)
        self.resize(1240, 810)
        self._rows = []
        self._build()
        register_theme_listener(self)
        self._on_theme_changed()
        self.refresh()

    def _build(self):
        self.setStyleSheet('''
          QDialog {background:#f8fafc;color:#0f172a;}
          QLabel {color:#1e293b;}
          QPushButton {background:#ffffff;border:1px solid #cbd5e1;border-radius:8px;
            padding:8px 14px;color:#0f172a;font-weight:700;}
          QPushButton:hover {background:#eff6ff;border-color:#93c5fd;
                color: #15191E;}
          QLineEdit {padding:8px 12px;border:1px solid #cbd5e1;border-radius:8px;background:white;font-size:13px;
                color: #15191E;}
          QTableWidget {border:1px solid #cbd5e1;border-radius:10px;background:white;gridline-color:#f1f5f9;font-size:12px;
            selection-background-color:#e0f2fe;selection-color:#0c4a6e;
                color: #15191E;}
          QHeaderView::section {background:#f1f5f9;color:#334155;padding:8px 6px;border:0;border-bottom:1px solid #cbd5e1;font-weight:700;}
          QTextEdit {border:1px solid #cbd5e1;border-radius:10px;background:white;padding:10px;
                color: #15191E;}
        ''')
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)
        self._v40_title = title = QLabel('🧠 Adaptif Koçluk Merkezi  |  Kurum Karar Masası')
        title.setStyleSheet('font-size:20px;font-weight:800;color:#0f172a;padding:2px 4px;')
        root.addWidget(title)
        self._v40_desc = desc = QLabel('Öğretmenin öncelik sırasını belirlemeye yardım eder. Ödev tamamlanması öğrenme sayılmaz; '
                      'öneriler otomatik ödev yazmaz, silmez veya devretmez.')
        desc.setWordWrap(True)
        desc.setStyleSheet('color:#475569;font-size:12px;padding:0 4px;')
        root.addWidget(desc)
        tools = QHBoxLayout()
        tools.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText('🔍 Öğrenci adı veya durum ara…')
        self.search.textChanged.connect(self._filter)
        tools.addWidget(self.search, 1)
        self.refresh_button = QPushButton('↻ Yenile')
        self.refresh_button.clicked.connect(self.refresh)
        tools.addWidget(self.refresh_button)
        self.open_button = QPushButton('🚀 Seçili Öğrencinin Koçluk Masasını Aç')
        self.open_button.setStyleSheet('''
            QPushButton {background:#2563eb;color:#ffffff;border:none;border-radius:8px;padding:8px 16px;font-weight:700;}
            QPushButton:hover {background:#1d4ed8;
                color: #FFFFFF;}
        ''')
        self.open_button.clicked.connect(self._open_student)
        tools.addWidget(self.open_button)
        self.btn_info = QPushButton('ℹ️')
        self.btn_info.setFixedWidth(38)
        self.btn_info.setToolTip('Adaptif Koçluk ve Karar Masası Çalışma Mantığı & Rehberi')
        self.btn_info.setStyleSheet('''
            QPushButton {
                font-size: 15px; font-weight: bold; background: #e0f2fe; color: #0272ab;
                border: 1px solid #bae6fd; border-radius: 8px; padding: 6px;
            }
            QPushButton:hover {
                background: #bae6fd; color: #03679e;
            }
        ''')
        self.btn_info.clicked.connect(self._show_info_dialog)
        tools.addWidget(self.btn_info)
        root.addLayout(tools)
        self.overview = QLabel('Kurum kayıtları okunuyor…')
        self.overview.setTextFormat(Qt.TextFormat.RichText)
        self.overview.setStyleSheet('background:#eff6ff;border:1px solid #bfdbfe;border-radius:9px;padding:9px 12px;font-weight:600;')
        root.addWidget(self.overview)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(['Öğrenci', 'Durum Rozeti', 'Açık Ödev', 'Ölçülen', 'Destek'])
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._selected)
        self.table.cellClicked.connect(lambda r, c: self._selected())
        self.table.doubleClicked.connect(self._open_student)
        splitter.addWidget(self.table)
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        splitter.addWidget(self.detail)
        splitter.setSizes([540, 680])
        root.addWidget(splitter, 1)
        footer = QHBoxLayout()
        self.note = QLabel('🛡️ Bu ekranın değerlendirmeleri kural tabanlıdır; sınav başarısı veya psikolojik tanı üretmez.')
        self.note.setWordWrap(True)
        self.note.setStyleSheet('color:#64748b;font-size:11.5px;')
        footer.addWidget(self.note, 1)
        close = QPushButton('Kapat')
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        root.addLayout(footer)

    def _on_theme_changed(self):
        c = semantic_palette()
        self.setStyleSheet(f"""
           QDialog {{background:{c['bg']};color:{c['fg']};}}
           QLabel {{color:{c['fg']};}}
           QPushButton {{background:{c['surface']};border:1px solid {c['border']};
             border-radius:8px;padding:8px 14px;color:{c['surface_fg']};font-weight:700;}}
           QPushButton:hover {{background:{c['tab_hover']};color:{c['tab_hover_fg']};}}
           QLineEdit {{padding:8px 12px;border:1px solid {c['border']};border-radius:8px;
             background:{c['field']};color:{c['field_fg']};font-size:13px;}}
           QTableWidget {{border:1px solid {c['border']};border-radius:10px;
             background:#FFFFFF;color:#172033;gridline-color:#E2E8F0;font-size:12px;
             selection-background-color:#DBEAFE;selection-color:#1E3A8A;}}
           QHeaderView::section {{background:#F1F5F9;color:#334155;padding:8px 6px;
             border:0;border-bottom:1px solid #CBD5E1;font-weight:700;}}
        """)
        self._v40_title.setStyleSheet(f'font-size:20px;font-weight:800;color:{c["fg"]};padding:2px 4px;')
        self._v40_desc.setStyleSheet(f'font-size:12px;color:{c["fg"]};padding:0 4px;')
        self.note.setStyleSheet(f'color:{c["fg"]};font-size:11.5px;')
        # Legacy HTML keeps its explicitly light reading paper. This prevents
        # white sections from inheriting the dark QSS foreground on theme switch.
        self.detail.setStyleSheet(report_paper_qss())
        # Inline overview texts were authored for a light information badge.
        self.overview.setStyleSheet('background:#EFF6FF;color:#1E3A8A;'
            'border:1px solid #BFDBFE;border-radius:9px;padding:9px 12px;font-weight:600;')

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
            support_cnt = sum(r['attention'] == 'Tanılayıcı destek' for r in self._rows)
            missing_cnt = sum(r['attention'] == 'Ölçüm gerekli' for r in self._rows)
            balanced_cnt = max(0, len(self._rows) - support_cnt - missing_cnt)
            trunc_txt = ' &nbsp;·&nbsp; <span style="color:#64748b;">İlk 500 kayıt görüntüleniyor</span>' if data['truncated'] else ''
            self.overview.setText(
                f'<span style="color:#1e3a8a;font-weight:800;">👥 {data["total_students"]} kayıtlı öğrenci</span>'
                f' &nbsp;&nbsp;|&nbsp;&nbsp; '
                f'<span style="color:#be123c;font-weight:800;">🎯 {support_cnt} hedefli destek sinyali</span>'
                f' &nbsp;&nbsp;|&nbsp;&nbsp; '
                f'<span style="color:#b45309;font-weight:800;">⚠️ {missing_cnt} ölçümü eksik öğrenci</span>'
                f' &nbsp;&nbsp;|&nbsp;&nbsp; '
                f'<span style="color:#15803d;font-weight:800;">✅ {balanced_cnt} dengeli / takipte</span>'
                + trunc_txt
            )
            self.table.blockSignals(True)
            self.table.setRowCount(len(self._rows))
            restore = -1
            bold_font = QFont()
            bold_font.setBold(True)
            for i, r in enumerate(self._rows):
                if selected_sid == r['student_id']:
                    restore = i
                att = str(r['attention'] or '')
                if att == 'Tanılayıcı destek':
                    badge_txt = '🎯 Tanılayıcı destek'
                    b_bg, b_fg = '#ffe4e6', '#9f1239'
                elif att == 'Ölçüm gerekli':
                    badge_txt = '⚠️ Ölçüm gerekli'
                    b_bg, b_fg = '#fef3c7', '#92400e'
                elif 'Acil' in att or 'destek' in att.casefold():
                    badge_txt = f'🎯 {att}'
                    b_bg, b_fg = '#ffe4e6', '#9f1239'
                else:
                    badge_txt = f'✅ {att}' if att else '✅ Takipte'
                    b_bg, b_fg = '#dcfce7', '#166534'

                student_label = f"{r['name'] or ('Öğrenci #' + str(r['student_id']))} (#{r['student_id']})"
                vals = [student_label, badge_txt, r['open_rows'], r['measured'], r['support']]
                for c, val in enumerate(vals):
                    cell = QTableWidgetItem(str(val))
                    if c == 0:
                        cell.setData(Qt.ItemDataRole.UserRole, int(r['student_id']))
                        cell.setFont(bold_font)
                    elif c == 1:
                        cell.setBackground(QBrush(QColor(b_bg)))
                        cell.setForeground(QBrush(QColor(b_fg)))
                        cell.setFont(bold_font)
                    elif c > 1:
                        cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        if c == 2 and int(r.get('open_rows') or 0) >= 25:
                            cell.setForeground(QBrush(QColor('#b91c1c')))
                            cell.setFont(bold_font)
                    self.table.setItem(i, c, cell)
            self.table.blockSignals(False)
            self._filter(self.search.text())
            if not self._rows:
                self.detail.setPlainText('Önceliklendirme için henüz öğrenci kaydı bulunmuyor.')
            else:
                self.table.selectRow(max(0, restore))
                self._selected()
        except Exception as exc:
            self.detail.setPlainText(f'Koçluk sırası yüklenemedi: {exc}\nEski ödev kayıtları değiştirilmedi.')
            self.overview.setText('Veri okuma hatası')

    def _filter(self, query):
        needle = (query or '').strip().casefold()
        for i, r in enumerate(self._rows):
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

            st_row = next((r for r in self._rows if r['student_id'] == sid), None)
            student_name = (st_row['name'] if st_row and st_row.get('name') else f"Öğrenci #{sid}")
            metrics = brief.get('metrics', {})
            measured_cnt = metrics.get('measured_topics', brief.get('evidence_count', 0))
            unmeasured_cnt = metrics.get('unmeasured_topics', 0)
            support_cnt = metrics.get('support_topics', 0)
            total_topics = measured_cnt + unmeasured_cnt
            ctx = brief.get('context', {})
            target_str = ctx.get('target') or 'Henüz hedef kaydedilmedi'
            plan_str = ctx.get('coaching_plan') or 'Kayıtlı plan bulunamadı'

            status_txt = str(brief.get('status') or '')
            if 'destek' in status_txt.casefold() or 'acil' in status_txt.casefold():
                st_bg, st_fg, st_icon = '#ffe4e6', '#9f1239', '🎯'
            elif 'ölçüm' in status_txt.casefold() or 'tanılayıcı' in status_txt.casefold():
                st_bg, st_fg, st_icon = '#fef3c7', '#92400e', '⚠️'
            else:
                st_bg, st_fg, st_icon = '#dcfce7', '#166534', '✅'

            cards_html = []
            for a in brief.get('actions', [])[:7]:
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
                      🔎 <b style="color:#475569;">Neden (Kanıt):</b> {_html_escape(str(a.get("reason") or ""))}<br>
                      💡 <b style="color:#0f766e;">Önerilen Adım:</b> {_html_escape(str(a.get("next_step") or ""))}<br>
                      📊 <span style="color:#64748b;font-size:11px;"><b>Kaynak:</b> {_html_escape(str(a.get("source") or ""))}</span>
                    </td>
                  </tr>
                </table>
                ''')

            warn_html = ''
            if brief.get('warnings'):
                w_items = ''.join(f'<li>{_html_escape(str(w))}</li>' for w in brief['warnings'])
                warn_html = f'''
                <table width="100%" cellspacing="0" cellpadding="8" style="margin-top:6px;border:1px solid #fde68a;">
                  <tr><td bgcolor="#fffbeb" style="font-size:11.5px;color:#92400e;">
                    <b>⚠️ DİKKAT / SINIRLAR</b><ul style="margin:4px 0 0 16px;padding:0;">{w_items}</ul>
                  </td></tr>
                </table>
                '''

            notes_html = ''
            if notes:
                n_items = ''.join(
                    f'<li><b>{_html_escape(format_lesson_name(item.get("lesson")))} › {_html_escape(str(item.get("topic") or ""))}:</b> '
                    f'{_html_escape(str(item.get("label") or ""))}</li>'
                    for item in notes
                )
                notes_html = f'''
                <table width="100%" cellspacing="0" cellpadding="8" style="margin-top:6px;border:1px solid #e2e8f0;">
                  <tr><td bgcolor="#f8fafc" style="font-size:11.5px;color:#334155;">
                    <b>📝 HIZLI KOÇ NOTLARI (Öğretmen Gözlemi; Öğrenme Kanıtı Değil)</b>
                    <ul style="margin:4px 0 0 16px;padding:0;">{n_items}</ul>
                  </td></tr>
                </table>
                '''

            journey_html = ''
            try:
                from services.adaptive_coaching_v34.flags import enabled as v34_enabled
                if v34_enabled():
                    from services.adaptive_coaching_v34.journey import compose_journey, journey_text
                    joined = compose_journey(sid, brief, notes, next_steps)
                    j_txt = journey_text(joined)
                    if j_txt:
                        journey_html = f'''
                        <table width="100%" cellspacing="0" cellpadding="8" style="margin-top:6px;border:1px solid #cbd5e1;">
                          <tr><td bgcolor="#f1f5f9" style="font-size:11.5px;color:#334155;white-space:pre-wrap;">{_html_escape(j_txt)}</td></tr>
                        </table>
                        '''
            except ImportError:
                pass

            html = f'''
            <div style="font-family:'Helvetica Neue',Arial,sans-serif;color:#0f172a;">
              <table width="100%" cellspacing="0" cellpadding="11" style="background-color:#1e3a8a;">
                <tr>
                  <td bgcolor="#1e3a8a">
                    <div style="font-size:10.5px;font-weight:700;color:#93c5fd;">SEÇİLİ ÖĞRENCİ KARAR ÖZETİ</div>
                    <div style="font-size:17px;font-weight:800;color:#ffffff;margin-top:2px;">
                      👤 {_html_escape(student_name)} <span style="color:#bfdbfe;font-size:13px;font-weight:600;">(#{sid})</span>
                    </div>
                  </td>
                  <td bgcolor="#1e3a8a" align="right" valign="middle">
                    <span style="background-color:{st_bg};color:{st_fg};font-weight:800;font-size:11.5px;padding:4px 9px;">
                      {st_icon} {_html_escape(status_txt)}
                    </span>
                  </td>
                </tr>
              </table>

              <table width="100%" cellspacing="6" cellpadding="9" style="margin-top:4px;">
                <tr>
                  <td width="33%" bgcolor="#f8fafc" align="center" style="border:1px solid #cbd5e1;">
                    <div style="font-size:10px;font-weight:700;color:#475569;">ÖLÇÜLEN KONU</div>
                    <div style="font-size:16px;font-weight:800;color:#0f172a;margin-top:2px;">{measured_cnt} / {total_topics}</div>
                    <div style="font-size:10px;color:#64748b;">Bağımsız yoklama kaydı</div>
                  </td>
                  <td width="33%" bgcolor="#fff1f2" align="center" style="border:1px solid #fecdd3;">
                    <div style="font-size:10px;font-weight:700;color:#be123c;">DESTEK ÖNERİSİ</div>
                    <div style="font-size:16px;font-weight:800;color:#9f1239;margin-top:2px;">{support_cnt} Konu</div>
                    <div style="font-size:10px;color:#e11d48;">Hedefli müdahale sinyali</div>
                  </td>
                  <td width="34%" bgcolor="#fffbeb" align="center" style="border:1px solid #fde68a;">
                    <div style="font-size:10px;font-weight:700;color:#b45309;">ÖLÇÜM BEKLEYEN</div>
                    <div style="font-size:16px;font-weight:800;color:#92400e;margin-top:2px;">{unmeasured_cnt} Konu</div>
                    <div style="font-size:10px;color:#d97706;">Ödev kaydı var, ölçüm yok</div>
                  </td>
                </tr>
              </table>

              <table width="100%" cellspacing="0" cellpadding="8" style="border:1px solid #e2e8f0;margin-bottom:8px;">
                <tr>
                  <td bgcolor="#f1f5f9" style="font-size:11.5px;color:#334155;">
                    🎯 <b>Akademik Hedef:</b> {_html_escape(str(target_str))} &nbsp;&nbsp;|&nbsp;&nbsp;
                    📅 <b>Koçluk Planı:</b> {_html_escape(str(plan_str))}
                  </td>
                </tr>
              </table>

              <div style="font-size:12.5px;font-weight:800;color:#1e293b;margin-bottom:6px;">
                📌 ÖĞRETMEN İÇİN ÖNCELİKLİ EYLEM KARTLARI (Neden &amp; Ne Yapmalı?)
              </div>
              {''.join(cards_html)}
              {warn_html}
              {notes_html}
              {journey_html}
            </div>
            '''
            self.detail.setHtml(html)
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

