"""Compact optional read-only sidebar for the existing Homework Form.

All assignment/control writes still go through the original form and dialog.
"""
from __future__ import annotations
from html import escape as _html_escape
import sqlite3
from contextlib import closing
from datetime import datetime
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTextEdit, QScrollArea, QFrame, QApplication,
)
from services.student_workspace_v21 import read_workspace_report
from services.student360_v16.advisor import suggestions
from services.student360_v16.profile import student_routine_status
from services.target_analysis_v24.student_target import read_saved_target
from services.live_student_summary_v3 import read_coach_glance, SQLiteChangeMonitor
from ui.adaptive_coaching_center_v26 import format_lesson_name
from ui.theme import register_theme_listener
from ui.theme_tokens_v37 import semantic_palette


class StudentWorkspacePanelV21(QWidget):
    def __init__(self, parent=None, *, open_control=None, open_adaptive=None):
        super().__init__(parent)
        self._student_id = None
        self._loaded_id = None
        self._dirty = True
        self._is_open = False
        self._compact_mode = False
        self._last_plain_text = ''
        self._open_control = open_control
        self._open_adaptive = open_adaptive
        from db import DB_PATH
        self._live_monitor = SQLiteChangeMonitor(DB_PATH)
        self._live_timer = QTimer(self)
        self._live_timer.setInterval(15000)  # local DB checks only, no network
        self._live_timer.timeout.connect(self._live_tick)
        self.setObjectName('studentWorkspaceV21')
        self.setMinimumWidth(265)
        self.setMaximumWidth(480)
        self.setStyleSheet("""
            QWidget#studentWorkspaceV21 { background: #f8fafc; border-left: 1px solid #cbd5e1; }
            QLabel { background: transparent; }
            QPushButton {
                background: #ffffff; border: 1px solid #cbd5e1; border-radius: 7px;
                padding: 6px 10px; font-weight: 700; color: #1e293b; font-size: 11.5px;
            }
            QPushButton:hover { background: #eff6ff; border-color: #93c5fd;  color: #15191E;}
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 9, 8, 9)
        root.setSpacing(7)

        hdr_card = QFrame()
        hdr_card.setStyleSheet("QFrame { background: #1e293b; border-radius: 9px; }")
        hdr_lay = QVBoxLayout(hdr_card)
        hdr_lay.setContentsMargins(11, 9, 11, 9)
        hdr_lay.setSpacing(3)
        top_hdr = QHBoxLayout()
        title = QLabel('🧭 Öğrenci 360° | Tek Ekran')
        title.setStyleSheet('font-weight: 800; font-size: 13px; color: #93c5fd; border: none;')
        top_hdr.addWidget(title)
        top_hdr.addStretch(1)
        self.btn_mode = QPushButton('📋 Tablo')
        self.btn_mode.setToolTip('Renkli Kart Görünümü (Seçenek A) ile Kompakt Tablo Görünümü (Seçenek B) arasında geçiş yap')
        self.btn_mode.setStyleSheet("""
            QPushButton {
                background: #334155; color: #e2e8f0; border: 1px solid #475569;
                border-radius: 5px; padding: 2px 7px; font-size: 10px; font-weight: 700;
            }
            QPushButton:hover { background: #475569; color: #ffffff; }
        """)
        self.btn_mode.clicked.connect(self._toggle_view_mode)
        top_hdr.addWidget(self.btn_mode)
        hdr_lay.addLayout(top_hdr)

        self.identity = QLabel('Öğrenci seçilmedi')
        self.identity.setWordWrap(True)
        self.identity.setStyleSheet('font-weight: 800; font-size: 15px; color: #ffffff; border: none;')
        hdr_lay.addWidget(self.identity)
        self.status = QLabel('İnceleme alanı. Ödevlerin kaydını değiştirmez.')
        self.status.setWordWrap(True)
        self.status.setStyleSheet('color: #cbd5e1; font-size: 11px; border: none;')
        hdr_lay.addWidget(self.status)
        self.live_state = QLabel('Yerel kayıt · Henüz kontrol edilmedi')
        self.live_state.setWordWrap(True)
        self.live_state.setStyleSheet('color: #86efac; font-size: 10px; border: none;')
        hdr_lay.addWidget(self.live_state)
        root.addWidget(hdr_card)

        row = QHBoxLayout()
        row.setSpacing(6)
        refresh = QPushButton('↻ Yenile')
        refresh.clicked.connect(self.refresh)
        row.addWidget(refresh)
        control = QPushButton('✅ Kontrolü Aç')
        control.setStyleSheet("""
            QPushButton { background: #ecfdf5; border: 1px solid #6ee7b7; color: #065f46; font-weight: 700; border-radius: 7px; padding: 6px 10px; }
            QPushButton:hover { background: #d1fae5;  color: #15191E;}
        """)
        control.clicked.connect(self.open_control)
        row.addWidget(control)
        root.addLayout(row)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.output.setObjectName('studentWorkspaceOverviewV21')
        self.output.setPlaceholderText('Bu öğrencinin kanıtları burada görünür.')
        self.output.setStyleSheet("QTextEdit { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 6px;  color: #15191E;}")
        root.addWidget(self.output, 1)
        more = QHBoxLayout()
        more.setSpacing(5)
        btn_topic = QPushButton('📚 Konu Kanıtları')
        btn_topic.clicked.connect(self.open_topics)
        more.addWidget(btn_topic)
        btn_coach = QPushButton('🧠 Koçluk')
        btn_coach.setToolTip('Mevcut seçili öğrenci koçluk analizini açar; ödevlere dokunmaz')
        btn_coach.clicked.connect(self.open_adaptive)
        more.addWidget(btn_coach)
        copy = QPushButton('📋 Özeti Kopyala')
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self._last_plain_text or self.output.toPlainText()))
        more.addWidget(copy)
        root.addLayout(more)
        self.output.setPlainText('Öğrenci seçilince bilgiler gösterilecek.')
        self._on_theme_changed()
        register_theme_listener(self)

    def _on_theme_changed(self):
        c = semantic_palette()
        self.setStyleSheet(f"""
            QWidget#studentWorkspaceV21 {{background:{c['surface']};
                color:{c['surface_fg']}; border-left:1px solid {c['border']};}}
            QLabel {{background:transparent;}}
            QPushButton {{background:{c['neutral']}; color:{c['neutral_fg']};
                border:1px solid {c['border']}; border-radius:7px;
                padding:6px 10px; font-weight:700; font-size:11.5px;}}
            QPushButton:hover {{background:{c['tab_hover']};
                color:{c['tab_hover_fg']};}}
        """)

    def _toggle_view_mode(self) -> None:
        self._compact_mode = not self._compact_mode
        self.btn_mode.setText('🗂️ Kart' if self._compact_mode else '📋 Tablo')
        self._dirty = True
        self.refresh()

    def set_open(self, visible: bool) -> None:
        was_open = self._is_open
        self._is_open = bool(visible)
        self.setVisible(self._is_open)
        if self._is_open:
            if not was_open:
                self._dirty = True  # data may have changed while hidden
                try:
                    self._live_monitor.poll()  # baseline on the same connection
                except (OSError, sqlite3.Error):
                    self.live_state.setText('Yerel izleme geçici olarak kullanılamıyor')
                self._live_timer.start()
            if self._dirty:
                self.refresh()
        else:
            self._live_timer.stop()
            self._live_monitor.close()

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

    def _live_tick(self) -> None:
        if not self._is_open or self._student_id is None or not self.isVisible():
            return
        try:
            if self._live_monitor.poll():
                self.mark_dirty()
        except (sqlite3.Error, OSError):
            self.live_state.setText('Yerel değişiklik izlemesi bekliyor · Manuel yenileme kullanılabilir')

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
            uri = DB_PATH.resolve().as_uri() + '?mode=ro'
            with closing(sqlite3.connect(uri, uri=True, timeout=6)) as con:
                con.execute('PRAGMA query_only=ON')
                report = read_workspace_report(con, sid)
                academic_target = read_saved_target(con, sid)
                # V23.3: optional scoped-topic ledger, NEVER count in legacy control totals.
                from services.curriculum_v233 import list_assignments
                scoped_tasks = list_assignments(con, student_id=sid)
                # V7: advisory only; same student ID, read-only database handle.
                try:
                    from services.survey_evidence_v7 import read_survey_evidence, brief_lines
                    survey_lines = brief_lines(read_survey_evidence(con, sid))
                except (Exception,) as _survey_exc:
                    survey_lines = ('Anket kanıt özeti okunamadı; mevcut öğrenci verileri değişmedi.',)

                # V11: read-only, student-scoped outcome follow-up preview.
                # No legacy assignment/checkbox writes or auto-scoring.
                try:
                    from services.adaptive_outcomes_v11 import compact_followup_text
                    v11_followup_text = compact_followup_text(con, sid)
                except (sqlite3.Error, ValueError, ImportError):
                    v11_followup_text = 'Müdahale takibi şu an okunamadı.'
                # Non-critical advisory: reuse the EXISTING V27 coaching presenter.
                # A coaching failure cannot break the existing 360 workspace.
                coach = None
                coach_error = False
                try:
                    coach = read_coach_glance(con, sid)
                except Exception:
                    coach_error = True
        except (sqlite3.Error, ValueError, OSError) as exc:
            self.identity.setText('Öğrenci #' + str(sid))
            self.status.setText('Özet alınamadı, kayıtlar etkilenmedi.')
            self.output.setPlainText(str(exc))
            self.live_state.setText('Yerel veri okunamadı · Mevcut ödevler değişmedi')
            return
        # Reject a report for the wrong student (e.g. after an asynchronous switch).
        if self._student_id != sid or report.student.student_id != sid:
            return
        s, c = report.student, report.control
        self.identity.setText(f'👤 {s.student_name} · #{sid}')
        self.status.setText('Salt okunur · Mevcut veriler')
        self.live_state.setText('🟢 Yerel kayıt güncellendi: ' + datetime.now().strftime('%H:%M:%S')
                                + ' · Bulut eşitlemesi bu panelde doğrulanmadı')
        # Show immediate, explainable action first; never infer mastery from ticks.
        coach_block = ['🧠 ADAPTİF KOÇ · GÜNCEL ÖNCELİK']
        if coach is not None and coach.student_id == sid:
            coach_block += [f'Durum: {coach.status}',
                            f'Bağımsız ölçüm sayısı: {coach.evidence_count}',
                            f'Öncelik: {coach.priority}',
                            f'Önerilen adım: {coach.next_step}']
            if coach.basis:
                coach_block += [f'Dayanak: {coach.basis}']
            if coach.warning:
                coach_block += [f'Sınırlama: {coach.warning}']
        else:
            coach_block += ['Koçluk özeti geçici olarak alınamadı.' if coach_error
                            else 'Koçluk değerlendirmesi henüz bulunmuyor.']
        coach_block += ['Öneri otomatik ödev oluşturmaz; öğretmen onayı gerekir.', '']
        scoped_open = sum(x.status == "devam" for x in scoped_tasks)
        scoped_done = sum(x.status == "tamam" for x in scoped_tasks)
        scoped_cancel = sum(x.status == "iptal" for x in scoped_tasks)
        routine_txt = student_routine_status(sid)
        adv_list = suggestions(s)
        blocks = coach_block + ['📈 MÜDAHALE–SONUÇ TAKİBİ', v11_followup_text, ''] + [
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
            f'Karşılaştırma: {s.exam_evidence}', s.exam_explanation, '',
            '🎓 YKS/LGS HEDEFİ (ÖĞRETMEN KAYDI)', academic_target, '',
            '🎯 KOÇLUK', s.coaching_plan,
            f'Hedef: {s.coaching_goals} | Program: {s.coaching_program_entries}',
            routine_txt, '',
            '📎 KAPSAMA ÖZEL ÖDEVLER (AYRI KAYIT)',
            f'Açık: {scoped_open} | Tamam: {scoped_done} | İptal: {scoped_cancel}',
            'Bu rakamlar ana ödev kontrol toplamlarına dahil değildir.', '',
            '📚 KONU HARİTASI',
            f'Kayıtlı: {s.tracked_topics} | Öğretmen işaretli: {s.marked_topics}', '',
            '🔎 KONTROL ÖNERİLERİ',
            *['• ' + item for item in adv_list], '',
            *['• ' + note for note in report.notes],
        ]
        blocks += ['', '📝 ANKET KANITLARI · TANISAL DEĞİL', *survey_lines]
        if s.source_warnings:
            blocks += ['', '⚠️ VERİ SINIRLARI', *['• ' + w for w in s.source_warnings]]
        self._last_plain_text = '\n'.join(blocks)

        if self._compact_mode:
            html = self._build_compact_html(s, c, report, coach, coach_error, v11_followup_text,
                                            academic_target, scoped_open, scoped_done, scoped_cancel,
                                            routine_txt, adv_list, survey_lines)
        else:
            html = self._build_card_html(s, c, report, coach, coach_error, v11_followup_text,
                                         academic_target, scoped_open, scoped_done, scoped_cancel,
                                         routine_txt, adv_list, survey_lines)
        self.output.setHtml(html)
        self._loaded_id = sid
        self._dirty = False

    def _build_card_html(self, s, c, report, coach, coach_error, v11_followup_text,
                         academic_target, scoped_open, scoped_done, scoped_cancel,
                         routine_txt, adv_list, survey_lines) -> str:
        if coach is not None and coach.student_id == s.student_id:
            st_str = str(coach.status or '')
            if 'destek' in st_str.casefold() or 'acil' in st_str.casefold():
                st_bg, st_fg = '#ffe4e6', '#9f1239'
            elif 'ölçüm' in st_str.casefold() or 'tanılayıcı' in st_str.casefold():
                st_bg, st_fg = '#fef3c7', '#92400e'
            else:
                st_bg, st_fg = '#dcfce7', '#166534'
            basis_html = f'<br>📊 <b>Dayanak:</b> {_html_escape(str(coach.basis))}' if coach.basis else ''
            warn_html = f'<br>⚠️ <span style="color:#b45309;">{_html_escape(str(coach.warning))}</span>' if coach.warning else ''
            coach_inner = f'''
              <b>Durum:</b> <span style="background-color:{st_bg};color:{st_fg};font-weight:700;padding:1px 6px;">{_html_escape(st_str)}</span><br>
              <b>Bağımsız Ölçüm:</b> <b>{coach.evidence_count}</b> gözlem &nbsp;|&nbsp;
              <b>Öncelik:</b> <span style="color:#1d4ed8;font-weight:700;">{_html_escape(str(coach.priority))}</span><br>
              💡 <b>Önerilen Adım:</b> {_html_escape(str(coach.next_step))}
              {basis_html}{warn_html}
            '''
        else:
            msg = 'Koçluk özeti geçici olarak alınamadı.' if coach_error else 'Koçluk değerlendirmesi henüz bulunmuyor.'
            coach_inner = f'<span style="color:#64748b;">{_html_escape(msg)}</span>'

        recent_rows_html = []
        for idx, item in enumerate(report.recent_control):
            row_bg = '#f8fafc' if idx % 2 == 1 else '#ffffff'
            st_raw = str(item.status or '')
            if 'tamam' in st_raw.casefold() or 'bitti' in st_raw.casefold() or 'yapıldı' in st_raw.casefold():
                b_bg, b_fg, b_lbl = '#dcfce7', '#166534', f'🟢 {st_raw}'
            elif 'açık' in st_raw.casefold() or 'devam' in st_raw.casefold():
                b_bg, b_fg, b_lbl = '#fef3c7', '#92400e', f'🟠 {st_raw}'
            else:
                b_bg, b_fg, b_lbl = '#f1f5f9', '#475569', st_raw
            recent_rows_html.append(f'''
              <tr>
                <td bgcolor="{row_bg}" style="font-size:11.5px;">
                  <b>{_html_escape(format_lesson_name(item.lesson))}</b> › {_html_escape(str(item.topic))}
                </td>
                <td bgcolor="{row_bg}" align="right">
                  <span style="background-color:{b_bg};color:{b_fg};font-weight:700;font-size:10.5px;padding:1px 6px;">{_html_escape(b_lbl)}</span>
                </td>
              </tr>
            ''')
        if not recent_rows_html:
            recent_rows_html.append('<tr><td colspan="2" style="color:#64748b;">• Kayıt yok</td></tr>')

        survey_html = '<br>'.join(_html_escape(str(line)) for line in survey_lines)
        adv_html = '<br>'.join('• ' + _html_escape(str(item)) for item in adv_list)
        notes_html = '<br>'.join('• ' + _html_escape(str(n)) for n in report.notes)
        warn_sec = ''
        if s.source_warnings:
            w_txt = '<br>'.join('• ' + _html_escape(str(w)) for w in s.source_warnings)
            warn_sec = f'''
            <table width="100%" cellspacing="0" cellpadding="7" style="border:1px solid #fde68a;margin-top:6px;">
              <tr><td bgcolor="#fffbeb" style="font-weight:800;color:#92400e;font-size:11.5px;">⚠️ VERİ SINIRLARI</td></tr>
              <tr><td bgcolor="#ffffff" style="font-size:11px;color:#78350f;">{w_txt}</td></tr>
            </table>
            '''

        return f'''
        <div style="font-family:'Helvetica Neue',Arial,sans-serif;color:#0f172a;font-size:11.5px;">
          <table width="100%" cellspacing="0" cellpadding="7" style="border:1px solid #bfdbfe;margin-bottom:7px;">
            <tr><td bgcolor="#eff6ff" style="font-weight:800;color:#1d4ed8;font-size:11.5px;">🧠 ADAPTİF KOÇ · GÜNCEL ÖNCELİK</td></tr>
            <tr><td bgcolor="#ffffff" style="line-height:1.42;">
              {coach_inner}<br>
              <span style="color:#64748b;font-size:10.5px;">Öneri otomatik ödev oluşturmaz; öğretmen onayı gerekir.</span>
            </td></tr>
          </table>

          <div style="font-weight:800;color:#065f46;font-size:11.5px;margin-bottom:4px;">✅ ÖDEV KONTROL (ANA KAYIT)</div>
          <table width="100%" cellspacing="4" cellpadding="5" style="margin-bottom:6px;">
            <tr>
              <td width="25%" bgcolor="#ecfdf5" align="center" style="border:1px solid #6ee7b7;">
                <div style="font-size:9.5px;font-weight:700;color:#047857;">TAMAMLANAN</div>
                <div style="font-size:15px;font-weight:800;color:#065f46;">{c.completed}</div>
              </td>
              <td width="25%" bgcolor="#fffbeb" align="center" style="border:1px solid #fcd34d;">
                <div style="font-size:9.5px;font-weight:700;color:#b45309;">AÇIK</div>
                <div style="font-size:15px;font-weight:800;color:#92400e;">{c.open}</div>
              </td>
              <td width="25%" bgcolor="#f8fafc" align="center" style="border:1px solid #cbd5e1;">
                <div style="font-size:9.5px;font-weight:700;color:#475569;">BELİRSİZ</div>
                <div style="font-size:15px;font-weight:800;color:#334155;">{c.unknown}</div>
              </td>
              <td width="25%" bgcolor="#f8fafc" align="center" style="border:1px solid #cbd5e1;">
                <div style="font-size:9.5px;font-weight:700;color:#475569;">HARİÇ</div>
                <div style="font-size:15px;font-weight:800;color:#334155;">{c.excluded}</div>
              </td>
            </tr>
          </table>

          <table width="100%" cellspacing="0" cellpadding="5" style="border:1px solid #e2e8f0;margin-bottom:7px;">
            <tr><td colspan="2" bgcolor="#f8fafc" style="font-weight:700;color:#475569;font-size:10.5px;">Son Kontrol Kayıtları (Ders &amp; Konu)</td></tr>
            {''.join(recent_rows_html)}
          </table>

          <table width="100%" cellspacing="0" cellpadding="7" style="border:1px solid #fde68a;margin-bottom:7px;">
            <tr><td bgcolor="#fffbeb" style="font-weight:800;color:#92400e;font-size:11.5px;">📋 SON 30 GÜN / TAKİP</td></tr>
            <tr><td bgcolor="#ffffff" style="line-height:1.42;">
              {_html_escape(str(s.homework_last30))}<br>
              <b>Gecikmiş açık kayıt:</b> <span style="color:#dc2626;font-weight:800;">{s.homework_overdue}</span><br>
              <span style="color:#b45309;font-size:10.5px;">ℹ️ Ödev bitirmek, konunun öğrenildiğini kanıtlamaz.</span>
            </td></tr>
          </table>

          <table width="100%" cellspacing="0" cellpadding="7" style="border:1px solid #e9d5ff;margin-bottom:7px;">
            <tr><td bgcolor="#faf5ff" style="font-weight:800;color:#6b21a8;font-size:11.5px;">📈 MÜDAHALE–SONUÇ TAKİBİ</td></tr>
            <tr><td bgcolor="#ffffff" style="line-height:1.4;">{_html_escape(str(v11_followup_text))}</td></tr>
          </table>

          <table width="100%" cellspacing="0" cellpadding="7" style="border:1px solid #e2e8f0;margin-bottom:7px;">
            <tr><td bgcolor="#f8fafc" style="font-weight:800;color:#334155;font-size:11.5px;">📈 DENEME &amp; 🎓 AKADEMİK HEDEF</td></tr>
            <tr><td bgcolor="#ffffff" style="line-height:1.42;">
              <b>Deneme:</b> {_html_escape(str(s.exam_summary))}<br>
              <b>Karşılaştırma:</b> {_html_escape(str(s.exam_evidence))} ({_html_escape(str(s.exam_explanation))})<br>
              <b>YKS/LGS Hedefi:</b> {_html_escape(str(academic_target))}
            </td></tr>
          </table>

          <table width="100%" cellspacing="0" cellpadding="7" style="border:1px solid #e2e8f0;margin-bottom:7px;">
            <tr><td bgcolor="#f8fafc" style="font-weight:800;color:#334155;font-size:11.5px;">🎯 KOÇLUK &amp; 📚 KONU HARİTASI</td></tr>
            <tr><td bgcolor="#ffffff" style="line-height:1.42;">
              <b>Plan:</b> {_html_escape(str(s.coaching_plan))}<br>
              <b>Hedef:</b> {s.coaching_goals} | <b>Program:</b> {s.coaching_program_entries} | {_html_escape(str(routine_txt))}<br>
              <b>Konu Haritası:</b> Kayıtlı: <b>{s.tracked_topics}</b> | Öğretmen işaretli: <b>{s.marked_topics}</b>
            </td></tr>
          </table>

          <table width="100%" cellspacing="0" cellpadding="7" style="border:1px solid #e2e8f0;margin-bottom:7px;">
            <tr><td bgcolor="#f8fafc" style="font-weight:800;color:#334155;font-size:11.5px;">📎 KAPSAMA ÖZEL ÖDEVLER (AYRI KAYIT)</td></tr>
            <tr><td bgcolor="#ffffff" style="line-height:1.4;">
              Açık: <b>{scoped_open}</b> | Tamam: <b>{scoped_done}</b> | İptal: <b>{scoped_cancel}</b><br>
              <span style="color:#64748b;font-size:10.5px;">Bu rakamlar ana ödev kontrol toplamlarına dahil değildir.</span>
            </td></tr>
          </table>

          <table width="100%" cellspacing="0" cellpadding="7" style="border:1px solid #e2e8f0;margin-bottom:7px;">
            <tr><td bgcolor="#f8fafc" style="font-weight:800;color:#334155;font-size:11.5px;">📝 ANKET KANITLARI · TANISAL DEĞİL</td></tr>
            <tr><td bgcolor="#ffffff" style="line-height:1.4;">{survey_html}</td></tr>
          </table>

          <table width="100%" cellspacing="0" cellpadding="7" style="border:1px solid #e2e8f0;">
            <tr><td bgcolor="#f8fafc" style="font-weight:800;color:#334155;font-size:11.5px;">🔎 KONTROL ÖNERİLERİ</td></tr>
            <tr><td bgcolor="#ffffff" style="line-height:1.4;">{adv_html}<br>{notes_html}</td></tr>
          </table>
          {warn_sec}
        </div>
        '''

    def _build_compact_html(self, s, c, report, coach, coach_error, v11_followup_text,
                            academic_target, scoped_open, scoped_done, scoped_cancel,
                            routine_txt, adv_list, survey_lines) -> str:
        coach_status = coach.status if (coach is not None and coach.student_id == s.student_id) else ('Hata' if coach_error else 'Yok')
        coach_prio = coach.priority if (coach is not None and coach.student_id == s.student_id) else '—'
        coach_step = coach.next_step if (coach is not None and coach.student_id == s.student_id) else '—'
        rec_txt = '<br>'.join(
            f'• <b>{_html_escape(format_lesson_name(i.lesson))}</b> › {_html_escape(str(i.topic))} ({_html_escape(str(i.status))})'
            for i in report.recent_control
        ) or '• Kayıt yok'
        survey_html = '<br>'.join(_html_escape(str(line)) for line in survey_lines)
        return f'''
        <div style="font-family:'Helvetica Neue',Arial,sans-serif;color:#0f172a;font-size:11.5px;">
          <table width="100%" cellspacing="0" cellpadding="7" style="border:1px solid #cbd5e1;">
            <tr><td colspan="2" bgcolor="#eff6ff" style="font-weight:800;color:#1d4ed8;">🧠 1. ADAPTİF KOÇ · GÜNCEL ÖNCELİK</td></tr>
            <tr><td width="34%" bgcolor="#f8fafc"><b>Durum</b></td><td><b>{_html_escape(str(coach_status))}</b></td></tr>
            <tr><td bgcolor="#f8fafc"><b>Öncelik</b></td><td><span style="color:#1d4ed8;font-weight:700;">{_html_escape(str(coach_prio))}</span></td></tr>
            <tr><td bgcolor="#f8fafc"><b>Önerilen Adım</b></td><td>{_html_escape(str(coach_step))}</td></tr>
            <tr><td colspan="2" bgcolor="#ecfdf5" style="font-weight:800;color:#065f46;">✅ 2. ÖDEV KONTROL (ANA KAYIT)</td></tr>
            <tr><td bgcolor="#f8fafc"><b>Toplamlar</b></td><td><b>{c.completed}</b> Tamamlanan | <b>{c.open}</b> Açık | <b>{c.excluded}</b> Hariç</td></tr>
            <tr><td bgcolor="#f8fafc"><b>Gecikmiş Açık</b></td><td><span style="color:#dc2626;font-weight:800;">{s.homework_overdue}</span> ({_html_escape(str(s.homework_last30))})</td></tr>
            <tr><td bgcolor="#f8fafc"><b>Son Kayıtlar</b></td><td>{rec_txt}</td></tr>
            <tr><td colspan="2" bgcolor="#f1f5f9" style="font-weight:800;color:#334155;">📈 3. MÜDAHALE, DENEME &amp; ANKET</td></tr>
            <tr><td bgcolor="#f8fafc"><b>Müdahale Takibi</b></td><td>{_html_escape(str(v11_followup_text))}</td></tr>
            <tr><td bgcolor="#f8fafc"><b>Deneme Analizi</b></td><td>{_html_escape(str(s.exam_summary))}</td></tr>
            <tr><td bgcolor="#f8fafc"><b>Akademik Hedef</b></td><td>{_html_escape(str(academic_target))}</td></tr>
            <tr><td bgcolor="#f8fafc"><b>Kapsama Özel</b></td><td>Açık: {scoped_open} | Tamam: {scoped_done} | İptal: {scoped_cancel}<br><span style="color:#64748b;font-size:10px;">KAPSAMA ÖZEL ÖDEVLER (AYRI KAYIT): Bu rakamlar ana ödev kontrol toplamlarına dahil değildir.</span></td></tr>
            <tr><td bgcolor="#f8fafc"><b>Anket Kanıtı</b></td><td>{survey_html}</td></tr>
          </table>
        </div>
        '''

    def open_adaptive(self) -> None:
        if self._student_id is None or not callable(self._open_adaptive):
            self.status.setText('Önce öğrenci seçin.')
            return
        self._open_adaptive()
        self.mark_dirty()

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

