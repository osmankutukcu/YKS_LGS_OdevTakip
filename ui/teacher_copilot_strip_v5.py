"""V5 optional teacher-first dashboard. UI only, no homework writes.

Reads existing V10/V11 + V27 data in an isolated worker and opens original
screens via host signals. Feedback is per-device/category, never student data.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
import queue
import sqlite3
import threading
import time

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QWidget, QMenu)
from services.live_student_summary_v3 import SQLiteChangeMonitor
from services.teacher_copilot_v5 import read_teacher_feed
from services.proactive_integrity_v3529 import read_integrity_overview
from services.system_health_v3531 import observe_local_health
from services.teacher_feedback_v5 import vote
from services.backup_automation_v3533 import run_due_backup


def _worker(path, out, include_integrity=False):
    try:
        result = {'ok': True, 'payload': read_teacher_feed(path)}
    except (sqlite3.Error, OSError, KeyError, ValueError) as exc:
        result = {'ok': False, 'error': type(exc).__name__}
    except Exception:
        result = {'ok': False, 'error': 'Beklenmeyen analiz hatası'}
    if include_integrity:
        result['integrity'] = read_integrity_overview(path)
        # Independent of the academic feed and student identities.
        try:
            result['health'] = observe_local_health(path)
        except Exception:
            result['health'] = {'state': 'UNVERIFIED', 'issues': []}
    out.put(result)


def _plain(s):
    label = QLabel(s)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


class TeacherCopilotStripV5(QFrame):
    open_details = pyqtSignal()
    open_student = pyqtSignal(int)

    def __init__(self, db_path, parent=None):
        super().__init__(parent)
        self._path = Path(db_path).expanduser().resolve()
        self._watch = SQLiteChangeMonitor(self._path)
        self._result_queue = queue.Queue(maxsize=1)
        self._thread = None
        self._pending = False
        self._closed = False
        self._loaded = False
        self._day = date.today()
        self._cards = []
        self._next_integrity_due = 0.0  # First check is automatic, after startup.
        self._backup_thread = None
        self._backup_result_queue = queue.Queue(maxsize=1)
        self._next_backup_probe = time.monotonic() + 20.0

        self.setObjectName('teacherCopilotStripV5')
        self.setStyleSheet('''
          QFrame#teacherCopilotStripV5 {background:#f8fafc;border:1px solid #cbd5e1;border-radius:8px;}
          QFrame#teacherCopilotStripV5 QLabel {color:#334155;background:transparent;border:0;}
          QFrame#teacherCopilotStripV5 QPushButton {background:#eff6ff;color:#1e40af;border:1px solid #bfdbfe;
            border-radius:6px;padding:4px 7px;font-weight:600;}
          QFrame#teacherCopilotStripV5 QPushButton:hover {background:#dbeafe;}
        ''')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 6, 10, 6)
        outer.setSpacing(4)
        bar = QHBoxLayout()
        self.head = _plain('🧭 Akıllı Takip • Öncelikler hazırlanıyor…')
        self.head.setStyleSheet('font-weight:700;font-size:12px;')
        bar.addWidget(self.head, 1)
        self.status = _plain('Yerel • Bulut doğrulanmadı')
        self.status.setStyleSheet('color:#64748b;font-size:10px;')
        self.status.setToolTip('Yalnızca bu cihazın SQLite kayıtları izleniyor. Uzak sunucu eşitlemesi doğrulanmadı.')
        bar.addWidget(self.status)
        self.btn_expand = QPushButton('Öncelikleri göster ▾')
        self.btn_expand.setAccessibleName('Akıllı takip ayrıntılarını göster veya gizle')
        self.btn_expand.clicked.connect(self.toggle_expanded)
        bar.addWidget(self.btn_expand)
        btn_summary = QPushButton('Günün Özeti ▸')
        btn_summary.clicked.connect(lambda *_: self.open_details.emit())
        bar.addWidget(btn_summary)
        outer.addLayout(bar)
        self.preview = _plain('Mevcut Günün Akıllı Özeti ve Adaptif Koç kullanılır.')
        self.preview.setStyleSheet('color:#64748b;font-size:11px;')
        outer.addWidget(self.preview)
        # Read-only institutional review line. No extra button or navigation.
        self.cohort_notice = _plain('')
        self.cohort_notice.setStyleSheet('color:#0f766e;font-size:10px;')
        self.cohort_notice.setVisible(False)
        outer.addWidget(self.cohort_notice)
        # Only show system issues; no extra action, button, or modal dialog.
        # Existing strip, one low-noise line; no extra button or modal.
        self.followup_notice = _plain('')
        self.followup_notice.setStyleSheet('color:#854d0e;font-size:10px;')
        self.followup_notice.setVisible(False)
        outer.addWidget(self.followup_notice)
        self.integrity_notice = _plain('')
        self.integrity_notice.setStyleSheet('color:#9a3412;font-size:10px;font-weight:600;')
        self.integrity_notice.setVisible(False)
        outer.addWidget(self.integrity_notice)
        self.health_notice = _plain('')
        self.health_notice.setStyleSheet('color:#9a3412;font-size:10px;font-weight:600;')
        self.health_notice.setVisible(False)
        outer.addWidget(self.health_notice)
        self.items = QWidget(self)
        self.item_layout = QVBoxLayout(self.items)
        self.item_layout.setContentsMargins(0, 3, 0, 3)
        self.item_layout.setSpacing(5)
        self.items.hide()
        outer.addWidget(self.items)
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(20_000)
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.start()
        self._worker_timer = QTimer(self)
        self._worker_timer.setInterval(200)
        self._worker_timer.timeout.connect(self._collect)
        self._worker_timer.start()
        QTimer.singleShot(70, self._baseline)
        QTimer.singleShot(400, self.request_refresh)

    def _baseline(self):
        if not self._closed:
            try:
                self._watch.poll()
            except (OSError, sqlite3.Error):
                self.status.setText('Yerel izleme kullanılamıyor • Bulut doğrulanmadı')

    def _poll(self):
        if self._closed or not self.isVisible():
            return
        today = date.today()
        new_day = today != self._day
        self._day = today
        try:
            changed = self._watch.poll()
        except (OSError, sqlite3.Error):
            self.status.setText('Yerel izleme kesildi • Bulut doğrulanmadı')
            changed = False
        if new_day or changed or not self._loaded or time.monotonic() >= self._next_integrity_due:
            self.request_refresh()
        self._maybe_scheduled_backup()


    def _maybe_scheduled_backup(self):
        # Config is read on Qt/UI thread only. Existing close-time auto-backup
        # semantics are unchanged. The new daily scheduler requires a separate opt-in.
        if self._closed or self._backup_thread is not None or time.monotonic() < self._next_backup_probe:
            return
        self._next_backup_probe = time.monotonic() + 60  # Retry configuration lookup slowly.
        try:
            from utils import settings as appset
            enabled = str(appset.ayar_get('yedek_gunluk_dogrulamali_v3533', 'false')).lower() == 'true'
            directory = appset.ayar_get('yedek_konumu', '')
        except Exception:
            return
        if not enabled:
            return
        self._next_backup_probe = time.monotonic() + 20 * 60  # Avoid costly repeat rehearsals.
        if not directory:
            self.status.setText('Günlük yedek için klasör seçilmeli • Bulut doğrulanmadı')
            return
        def action():
            result = run_due_backup(self._path, directory, enabled=True)
            self._backup_result_queue.put(result)
        self._backup_thread = threading.Thread(target=action,
                                               name='V3533VerifiedBackup', daemon=True)
        self._backup_thread.start()

    def _collect_backup(self):
        try:
            result = self._backup_result_queue.get_nowait()
        except queue.Empty:
            return
        self._backup_thread = None
        state = result.get('status')
        if state == 'BACKUP_CREATED_AND_VERIFIED':
            self.status.setToolTip('Günlük SQLite yedeği oluşturuldu ve kurtarma provası geçti. Plan profilleri ve bulut senkronu doğrulanmadı.')
        elif state not in ('DISABLED', 'ALREADY_CURRENT'):
            self.status.setText('Günlük yedek doğrulanamadı • Yerel veri korunuyor')
            self.status.setToolTip('Yedek dosyasını ve seçilen klasörü denetleyin. Otomatik veri onarımı veya geri yükleme yapılmadı.')

    def request_refresh(self):
        if self._closed:
            return
        if self._thread is not None:
            self._pending = True
            return
        due = time.monotonic() >= self._next_integrity_due
        if due:
            self._next_integrity_due = time.monotonic() + 600  # At most every 10 minutes.
        self._thread = threading.Thread(target=_worker,
                                        args=(self._path, self._result_queue, due),
                                        name='TeacherCopilotV5', daemon=True)
        self._thread.start()

    def _collect(self):
        if self._closed:
            return
        self._collect_backup()
        try:
            result = self._result_queue.get_nowait()
        except queue.Empty:
            return
        self._thread = None
        if 'integrity' in result:
            self._present_integrity(result['integrity'])
        if 'health' in result:
            self._present_health(result['health'])
        self._present(result)
        if self._pending:
            self._pending = False
            self.request_refresh()

    def _present_integrity(self, status):
        state = status.get('state')
        if state == 'REVIEW':
            n = int(status.get('finding_count') or 0)
            self.integrity_notice.setText(
                f'🔎 Otomatik ödev veri denetimi: {n} bağlantı bulgusu incelenmeli. '
                'Hiçbir ödev değiştirilmedi. Ayrıntılar Ödev Takip → Denetim ekranında.')
            self.integrity_notice.setVisible(True)
        elif state in ('UNAVAILABLE', 'UNVERIFIED'):
            self.integrity_notice.setText(
                '🔎 Ödev bağlantı denetimi tamamlanamadı; veriler sağlam kabul edilmedi. '
                'Kayıtlar değiştirilmedi.')
            self.integrity_notice.setVisible(True)
        else:
            # Absence of findings in scoped checks is not a full system health certificate.
            self.integrity_notice.setVisible(False)

    def _present_health(self, report):
        # Only actionable, scoped findings. No scary full-screen dialog,
        # unverified green badge or new button. Source data never exposed.
        names = {
            'DB_NOT_FOUND': 'Yerel öğrenci veritabanı bulunamadı.',
            'DB_PROBE_UNVERIFIED': 'Veritabanı sağlık denetimi tamamlanamadı.',
            'BACKUP_CHECK_UNVERIFIED': 'Yedek dosyası denetimi tamamlanamadı.',
            'SCHEMA_INCOMPLETE': 'Yerel veritabanının gerekli tabloları eksik.',
            'SQLITE_QUICK_CHECK_REVIEW': 'Veritabanı tutarlılığı teknik olarak incelenmeli.',
            'BACKUP_SQL_DUMP_MISLABELED': 'Yedek dosyası SQLite yerine SQL metni içeriyor; geri yükleme uyumluluğu incelenmeli.',
            'BACKUP_FORMAT_UNVERIFIED': 'Son yedek dosyasının biçimi doğrulanamadı.',
            'GZIP_BACKUP_RESTORE_NOT_SUPPORTED_BY_UI': 'Sıkıştırılmış yedeğin mevcut geri yükleme ekranıyla uyumu doğrulanmalı.',
            'OBSERVED_BACKUP_STALE': 'Kontrol edilen klasördeki son yedek eski olabilir.',
        }
        issues = report.get('issues') if isinstance(report, dict) else None
        visible = [names[x['state']] for x in (issues or [])
                   if isinstance(x, dict) and x.get('state') in names]
        if not visible and isinstance(report, dict) and report.get('state') == 'UNVERIFIED':
            visible = ['Sistem sağlığı doğrulanamadı; sorunsuz olduğu varsayılmıyor.']
        if visible:
            self.health_notice.setText('🛡 Sistem sağlığı: ' + ' '.join(visible[:2]) +
                                       ' Otomatik onarım yapılmadı.')
            self.health_notice.setVisible(True)
        else:
            self.health_notice.setVisible(False)

    def _clear_cards(self):
        while self.item_layout.count():
            entry = self.item_layout.takeAt(0)
            widget = entry.widget()
            if widget is not None:
                widget.deleteLater()

    def _present(self, result):
        self._loaded = True
        if not result.get('ok'):
            self._cards = []
            self._clear_cards()
            self.cohort_notice.setVisible(False)
            self.followup_notice.setVisible(False)
            self.head.setText('🧭 Akıllı takip bilgileri geçici olarak okunamadı')
            self.preview.setText('Ödevler değiştirilmedi. Günün Özeti ekranı ayrıca açılabilir.')
            self.status.setText('Yerel okuma hatası • Bulut doğrulanmadı')
            return
        payload = result['payload']
        if payload.get('day') != date.today().isoformat():
            self._pending = True
            return
        self._present_cohort(payload.get('cohort'))
        self._present_followups(payload.get('intervention_followups'))
        self._cards = payload.get('cards') or []
        count = int(payload.get('total_queued') or 0)
        self.head.setText(f'🧭 Akıllı Takip • {count} öncelik' if count else '🧭 Akıllı Takip • Bekleyen öncelik yok')
        self.status.setText(f"Yerel {payload.get('checked_at', '')} • Bulut doğrulanmadı")
        if not self._cards:
            self.preview.setText('Öncelikli kayıt yok. Ayrıntılı kayıtlar Günün Özeti bölümünde.')
        else:
            first = self._cards[0]
            academic = first.get('academic')
            if academic and int(academic.get('student_id', 0)) == int(first['student_id']):
                self.preview.setText(f"{first['title']} — {first['reason']}\n📚 Öneri: {academic['next_step']}")
            else:
                self.preview.setText(f"{first['title']} — {first['reason']}")
            verified = first.get('verified_academic_action')
            if verified and verified.get('student_id') == first['student_id']:
                self.preview.setText(self.preview.text() + '\n🎓 Akademik kontrol: ' + verified['next_step'])
            # V3.5.37 compact, non-click academic suggestion on existing strip.
            intervention = first.get('intervention_draft') or {}
            if intervention.get('student_id') == first['student_id'] and intervention.get('recommendations'):
                top = intervention['recommendations'][0]
                self.preview.setText(self.preview.text() + '\n🧭 Telafi taslağı: ' + top['title'][:110])
            shared = first.get('shared_academic')
            if shared and shared.get('student_id') == first['student_id']:
                if shared.get('state') == 'LINK_REVIEW':
                    self.preview.setText(self.preview.text() + '\n⚠ Öğrenci–ödev bağlantısı denetlenmeli.')
                elif shared.get('planning_hint'):
                    self.preview.setText(self.preview.text() + '\n🗓 ' + shared['planning_hint'])
        # V3.5.39: append ONLY an anonymous, sufficiently large descriptive
        # cohort pattern. Never advertise method effectiveness or prescribe.
        historical = payload.get('historical_patterns') or {}
        if historical.get('state') in ('DESCRIPTIVE_HISTORY', 'PARTIAL_COVERAGE'):
            from services.intervention_patterns_v3539 import compact_history_line
            line = compact_history_line(historical)
            if line and self._cards:
                self.preview.setText(self.preview.text() + '\n📖 Geçmiş izlem: ' + line[:230])
        self._render_cards()

    def _present_followups(self, followups):
        # Empty verified V11 ledger is not a claim that all learners are healthy.
        if not isinstance(followups, dict):
            self.followup_notice.setVisible(False)
            return
        state = followups.get('state')
        n = followups.get('date_due_candidates')
        if state in ('OBSERVED', 'PARTIAL_COVERAGE') and type(n) is int and n > 0:
            msg = f'🗓 Onaylı müdahale izleminde {n} kayıt için 7/14 günlük kontrol tarihi gelmiş.'
            if state == 'PARTIAL_COVERAGE':
                msg += ' Yerel tarama kapsamı kısmi.'
            msg += ' Kayıtlar otomatik değiştirilmedi; Öğrenci 360 üzerinden incelenebilir.'
            self.followup_notice.setText(msg)
            self.followup_notice.setVisible(True)
        elif state == 'UNVERIFIED':
            self.followup_notice.setText('🗓 Müdahale izlem kaynağı şu anda doğrulanamadı; kayıtlarda sorun yok denemez.')
            self.followup_notice.setVisible(True)
        else:
            self.followup_notice.setVisible(False)

    def _present_cohort(self, cohort):
        if not isinstance(cohort, dict) or cohort.get('state') not in ('OBSERVED', 'REVIEW_REQUIRED', 'PARTIAL_COVERAGE'):
            self.cohort_notice.setText('🏫 Kurum genelinde akademik takip henüz doğrulanamadı. Yerel kayıtlar kontrol edilebilir.')
            self.cohort_notice.setVisible(True)
            return
        canonical = cohort.get('canonical_homework') or {}
        if canonical.get('state') in ('OBSERVED', 'PARTIAL_COVERAGE'):
            count = int(canonical.get('evaluated_students') or 0)
            overdue = int(canonical.get('overdue_students') or 0)
            task_count = int(canonical.get('canonical_tasks') or 0)
            line = (f'🏫 Yerel ortak ödev kanıtı: {count} öğrenci değerlendirildi · '
                    f'{task_count} doğrulanabilir ödev satırı · '
                    f'{overdue} öğrencide geciken açık ödev.')
            problems = int(canonical.get('ownership_or_ambiguity_review_students') or 0)
            if problems:
                line += f' ⚠ {problems} öğrencinin verisinde bağlantı/belirsizlik; bu öğrenciler önceliğe alınmadı.'
            if canonical.get('state') == 'PARTIAL_COVERAGE':
                line += ' ⚠ Veri kapsamı kısmi; eksik tarih, durum veya bağlantılar olabilir.'
            top = (canonical.get('priority_cards') or [])[:1]
            if top:
                c = top[0]
                line += (f"\nÖnce doğrulanacak: {c['name']} • {c['lesson']} • "
                         f"{c['overdue_open']} açık gecikmiş ödev. Öğretmen onayı gerekir.")
            # Existing V10/V11 review acknowledgments are NOT applied to new child rows.
            self.cohort_notice.setText(line)
            self.cohort_notice.setToolTip('Kanonik kaynak: doğrulanmış odev ve odev_satir; açık bağlar tekilleştirilir. '
                'Eski V10 incelendi işaretleri yalnızca eski V10 akışında geçerlidir. '
                'Yalnızca bu cihazın yerel kayıtları; sınav, gerçek öğrenme başarısı, uzak cihazlar doğrulanmaz.')
            self.cohort_notice.setVisible(True)
            return
        count = int(cohort.get('evaluated_students') or 0)
        pending = int(cohort.get('pending_overdue_reviews') or 0)
        overdue = int(cohort.get('overdue_students') or 0)
        line = f'🏫 Yerel akademik takip: {count} öğrenci değerlendirildi · {overdue} öğrencide geciken açık ödev · {pending} incelenmemiş öncelik.'
        blocked = int(cohort.get('ownership_review_students') or 0)
        if blocked:
            line += f' ⚠ {blocked} öğrenci için bağlantı kontrolü gerekiyor; öneri üretilmedi.'
        if int(cohort.get('modern_rows_not_evaluated') or 0):
            line += ' ⚠ Ödev kapsamı kısmi: modern ödev satırları bu öncelik hesabında yok.'
        plan = cohort.get('weekly_coaching_plan') or {}
        if plan.get('state') == 'OBSERVED_COACHING_PLANS':
            line += f" Bu hafta eşleşen koçluk planı olmayan: {int(plan.get('without_plan') or 0)}."
        else:
            line += ' Koçluk planı kapsamı doğrulanamadı.'
        first = (cohort.get('priority_cards') or [])[:1]
        if first:
            c = first[0]
            line += (f"\nÖnce kontrol edilecek: {c['name']} • "
                     f"{c['lesson'] or 'Ders belirtilmedi'} • "
                     f"{c['recent_open_due'] + c['old_open_due']} geciken açık ödev. "
                     'Ödev durumunu doğrulayın; öğrenci adına otomatik işlem yok.')
        self.cohort_notice.setText(line)
        self.cohort_notice.setToolTip('Yalnızca bu cihazdaki V10 klasik ödev kanıtı analiz edilir; modern ödev satırları, sınavlar ve diğer cihazlar bu sayıya dahil değildir. Öğrenme tanısı, otomatik kayıt veya mesaj yok.')
        self.cohort_notice.setVisible(True)

    def _render_cards(self):
        self._clear_cards()
        for card in self._cards:
            sid = int(card['student_id'])
            if sid <= 0:
                continue
            frame = QFrame(self.items)
            frame.setStyleSheet('QFrame {background:white;border:1px solid #e2e8f0;border-radius:7px;}')
            row = QHBoxLayout(frame)
            row.setContentsMargins(9, 6, 9, 6)
            text_col = QVBoxLayout()
            title = _plain(card['title'])
            title.setStyleSheet('font-weight:700;')
            text_col.addWidget(title)
            reason = _plain(card['reason'])
            reason.setStyleSheet('color:#475569;font-size:11px;')
            text_col.addWidget(reason)
            basis = _plain('Dayanak: ' + card['basis'])
            basis.setStyleSheet('color:#64748b;font-size:10px;')
            text_col.addWidget(basis)
            coach = card.get('coach')
            if coach:
                advice = _plain('Adaptif Koç: ' + coach['priority'] + ' • ' + coach['next_step'])
                advice.setStyleSheet('color:#1e40af;font-size:11px;')
                advice.setToolTip('Ölçüm kanıtı: ' + str(coach['evidence_count']) + ' • ' + coach['source'])
                text_col.addWidget(advice)
            academic = card.get('academic')
            if academic and int(academic.get('student_id', 0)) == sid:
                advice = _plain('📚 Akademik sonraki adım: ' + academic['next_step'])
                advice.setStyleSheet('color:#0f766e;font-size:11px;')
                advice.setToolTip('Dayanak: ' + academic['basis'] +
                                  ' • Öğretmen onayı gerekir; başarı veya öğrenme tanısı değildir.')
                text_col.addWidget(advice)
            shared = card.get('shared_academic')
            if shared and shared.get('student_id') == sid and shared.get('planning_hint'):
                note = _plain('🗓 Akademik plan: ' + shared['planning_hint'])
                note.setStyleSheet('color:#475569;font-size:10px;')
                note.setToolTip('Koçluk planı; haftalık takvimin doğrulandığı anlamına gelmez. Otomatik kayıt yok.')
                text_col.addWidget(note)
            row.addLayout(text_col, 1)
            actions = QVBoxLayout()
            to_student = QPushButton('Öğrenciye git')
            to_student.setToolTip('Mevcut ödev takip formunu bu öğrencinin kimliğiyle açar; kayıt değiştirmez.')
            to_student.clicked.connect(lambda _=False, selected=sid: self.open_student.emit(selected))
            actions.addWidget(to_student)
            feedback = QPushButton('Geri bildirim ⋯')
            feedback.setToolTip('Yalnızca uyarı kategorisinin sunum sırası öğrenilir; öğrenci bilgileri saklanmaz.')
            menu = QMenu(feedback)
            useful = menu.addAction('Bu uyarı faydalı')
            not_useful = menu.addAction('Bu uyarı ilgisiz')
            kind = card['kind']
            useful.triggered.connect(lambda _=False, k=kind: self._feedback(k, 'useful'))
            not_useful.triggered.connect(lambda _=False, k=kind: self._feedback(k, 'not_useful'))
            feedback.setMenu(menu)
            actions.addWidget(feedback)
            row.addLayout(actions)
            self.item_layout.addWidget(frame)

    def _feedback(self, kind, rating):
        try:
            vote(kind, rating)
        except (OSError, ValueError):
            self.status.setText('Geri bildirim kaydedilemedi • Ödevler etkilenmedi')
            return
        self.request_refresh()

    def toggle_expanded(self):
        expanded = self.items.isHidden()
        self.items.setVisible(expanded)
        self.btn_expand.setText('Öncelikleri gizle ▴' if expanded else 'Öncelikleri göster ▾')

    def closeEvent(self, event):
        self._closed = True
        self._poll_timer.stop()
        self._worker_timer.stop()
        self._watch.close()
        super().closeEvent(event)
