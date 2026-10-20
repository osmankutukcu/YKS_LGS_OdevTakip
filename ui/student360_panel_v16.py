"""Small optional read-only overview tab for the existing coaching screen."""
from urllib.parse import quote
import sqlite3
from contextlib import closing
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit, QHBoxLayout
from services.student360_v16 import read_student_overview
from services.shared_academic_decision_v3530 import read_shared_academic_card
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
        from services.adaptive_coaching_v26.flags import enabled as adaptive_v26_enabled
        self.btn_adaptive_v26 = QPushButton('🧠 Adaptif Koçluk')
        self.btn_adaptive_v26.setVisible(adaptive_v26_enabled())
        self.btn_adaptive_v26.clicked.connect(self.open_adaptive_v26)
        bar.addWidget(self.btn_adaptive_v26)
        bar.addStretch()
        lay.addLayout(bar)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        lay.addWidget(self.output)
        # V3.5.66 optional asynchronous cycle summary. The existing Student360
        # analysis, controls and layout remain unchanged.
        self._journey_v3566 = None
        try:
            from ui.student360_journey_sidecar_v3566 import Student360JourneySidecarV3566
            self._journey_v3566 = Student360JourneySidecarV3566(self)
        except ImportError:
            pass
        self.set_student(None)
        # V24.1: visible Student 360° overview follows committed SQLite updates.
        from ui.live_change_bridge_v241 import install_live_updates
        install_live_updates(self, self._on_committed_change_v241, student_attr="student_id")

    def _on_committed_change_v241(self):
        if type(self.student_id) is int and self.student_id > 0:
            self.refresh()

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

    def open_adaptive_v26(self):
        if self.student_id is None:
            self.output.setPlainText('Önce bir öğrenci seçin.')
            return
        try:
            from ui.adaptive_coaching_dialog_v25 import AdaptiveCoachingDialogV25
            AdaptiveCoachingDialogV25(self.student_id, parent=self, host=None).exec()
            self.refresh()
        except Exception as exc:
            self.output.append(f'\nAdaptif Koçluk açılamadı: {exc}')

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
                con.execute('BEGIN')  # V3.5.36: one coherent read snapshot for the overview.
                data = read_student_overview(con, sid)
                academic_target = read_saved_target(con, sid)
                shared_academic = None
                try:
                    shared_academic = read_shared_academic_card(con, sid)
                except (sqlite3.Error, ValueError, TypeError, KeyError):
                    # Optional advisory does not block the existing Student360 screen.
                    pass
                # V3.5.36 optional canonical same-student action. No writes/UI controls.
                canonical_action = None
                try:
                    from services.academic_actions_v3536 import read_student_action_card
                    canonical_action = read_student_action_card(con, sid)
                except (sqlite3.Error, ValueError, TypeError, KeyError):
                    pass  # Cannot conclude that missing evidence means no risk.
                # V3.5.37 read-only intervention DRAFT from the same student/snapshot.
                intervention_draft = None
                if canonical_action and canonical_action.get('student_id') == sid:
                    try:
                        from services.intervention_advisor_v3537 import build_intervention_draft
                        intervention_draft = build_intervention_draft(
                            con, sid, action_card=canonical_action)
                    except (sqlite3.Error, ValueError, TypeError, KeyError):
                        pass  # Optional advice is never a clean academic verdict.
                # V3.5.38: only teacher-approved V11 entries. Never create
                # interventions or learning observations during a refresh.
                intervention_followup = None
                try:
                    from services.intervention_followup_v3538 import read_student_followups
                    intervention_followup = read_student_followups(con, sid, limit=3)
                except (sqlite3.Error, ValueError, TypeError, KeyError):
                    intervention_followup = {'state': 'UNVERIFIED', 'student_id': sid}
                # V3.5.39: opt-in-by-evidence, anonymous descriptive history.
                # Only show a cohort pattern for the student's OWN approved
                # latest intervention topic, never infer a prescription.
                historical_pattern = None
                if intervention_followup and intervention_followup.get('student_id') == sid:
                    entries = intervention_followup.get('records') or []
                    if entries:
                        try:
                            from services.intervention_patterns_v3539 import read_historical_patterns
                            rec = entries[0]
                            historical_pattern = read_historical_patterns(
                                con, lesson=rec['lesson'], topic=rec['topic'],
                                max_scan=100, max_groups=2)
                        except (sqlite3.Error, ValueError, TypeError, KeyError):
                            historical_pattern = {'state': 'SOURCE_UNVERIFIED', 'patterns': []}
                # V7: existing survey records, no scoring or diagnosis.
                try:
                    from services.survey_evidence_v7 import read_survey_evidence, brief_lines
                    survey_lines = brief_lines(read_survey_evidence(con, sid))
                except (Exception,) as _survey_exc:
                    survey_lines = ('Anket kanıt özeti şu an okunamadı.',)

                # Read-only optional decision summary. Missing V25 schema is a normal state.
                adaptive_text = None
                try:
                    from services.adaptive_coaching_v26.flags import enabled as adaptive_v26_enabled
                    if adaptive_v26_enabled():
                        from services.adaptive_coaching_v26.decision import student_decisions, concise_summary
                        con.row_factory = sqlite3.Row
                        adaptive_text = concise_summary(student_decisions(con, sid), n=3)
                except (sqlite3.Error, ValueError, KeyError, TypeError) as exc:
                    adaptive_text = f'Adaptif öğrenme özeti şu an okunamadı: {exc}' 
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
        if shared_academic and shared_academic.get('student_id') == sid:
            parts += ['', 'ORTAK AKADEMİK KARAR · ÖĞRETMEN ONAYINA TABİ',
                      shared_academic['next_step'],
                      'Dayanak: ' + shared_academic['basis'],
                      'Haftalık koçluk planı: ' + shared_academic['plan']['summary'],
                      'Not: Koçluk planı, haftalık takvimin doğrulandığı anlamına gelmez.']
        if canonical_action and canonical_action.get('student_id') == sid:
            evidence = canonical_action['homework']
            parts += ['', 'ORTAK ÖDEV KANITI · V3.5.36 · YEREL KAYITLAR']
            if canonical_action['state'] == 'LINK_REVIEW':
                parts += ['⚠ Öğrenci–ödev bağlantısı doğrulanamadı; akademik sayılar gösterilmiyor.',
                          canonical_action['next_step']]
            else:
                parts += ['Doğrulanabilen satır: ' + str(evidence['canonical_tasks']),
                          'Tamamlanan satır: ' + str(evidence['completed_tasks']),
                          'Gecikmiş açık satır: ' + str(evidence['overdue_open_tasks']),
                          'Akademik takip önerisi: ' + canonical_action['next_step'],
                          'Kapsam: ' + canonical_action['global_coverage'],
                          canonical_action['note']]
                if canonical_action.get('plan_attention'):
                    parts.append('Plan durumu: ' + canonical_action['plan_attention'])
        else:
            parts += ['', 'ORTAK ÖDEV KANITI · Kayıtlar doğrulanamadı; sıfır ödev veya sorunsuz durum anlamına gelmez.']
        if intervention_draft and intervention_draft.get('student_id') == sid:
            parts += ['', 'AKADEMİK TELAFİ TASLAĞI · V3.5.37 · ÖĞRETMEN ONAYI']
            if intervention_draft['state'] == 'DATA_REVIEW':
                parts.append('Veri bağlantıları kontrol edilmeden akademik öneri verilmiyor.')
            for suggestion in intervention_draft['recommendations'][:3]:
                parts += ['• ' + suggestion['title'],
                          '  Dayanak: ' + suggestion['why'],
                          '  Önerilen kontrol: ' + suggestion['teacher_next_step'],
                          '  Takip: ' + suggestion['recheck']]
            if not intervention_draft['recommendations']:
                parts.append('Kanıta dayalı telafi taslağı üretilemedi; ek ölçüm gerekebilir.')
            parts += intervention_draft['limitations'][:2]
        if intervention_followup and intervention_followup.get('student_id') == sid:
            if intervention_followup['state'] == 'OBSERVED':
                parts += ['', 'ONAYLI MÜDAHALE İZLEMİ · V3.5.38 · OTOMATİK OKUMA']
                for rec in intervention_followup['records']:
                    parts += [f"• {rec['lesson']} / {rec['topic']} · {rec['status']}",
                              f"  7. gün: {rec['day7']} · 14. gün: {rec['day14']}",
                              '  ' + rec['reason']]
                    if rec['measurement_ready']:
                        parts.append('  Ölçüm doğruluğu farkı: '
                                     f"{rec['delta_percentage_points']:+.1f} yüzde puan; nedensellik kanıtı değildir.")
                parts.append(intervention_followup['warning'])
            elif intervention_followup['state'] == 'UNVERIFIED':
                parts += ['', 'Müdahale izlem kayıtları doğrulanamadı; müdahale bulunmadığı varsayılmıyor.']
        if historical_pattern:
            from services.intervention_patterns_v3539 import compact_history_line
            history_line = compact_history_line(historical_pattern)
            if history_line:
                parts += ['', 'GEÇMİŞ MÜDAHALE GÖZLEMLERİ · V3.5.39 · BETİMSEL',
                          history_line,
                          'Bu geçmiş örüntü aynı öğrencide başarıyı veya yöntemin etkisini öngörmez.']
        if adaptive_text:
            parts += ['', adaptive_text]
        parts += ['', 'ANKET KANITLARI · TANISAL DEĞİL', *survey_lines]
        if data.source_warnings:
            parts += ['', 'VERİ UYARILARI', *[f'• {w}' for w in data.source_warnings]]
        self.output.setPlainText('\n'.join(parts))
        if self._journey_v3566 is not None:
            self._journey_v3566.request(sid)
