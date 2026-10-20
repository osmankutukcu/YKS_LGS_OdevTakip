# -*- coding: utf-8 -*-
"""Optional v3.5.63 add-on. Bridges research cards to the UNCHANGED Coach Assistant inbox.

No new controls or popups; reads are on QThreadPool, read-only, time-bounded.
Preserves both homework form sources and the legacy assistant's byte signature.
"""
from __future__ import annotations
from contextlib import closing
from html import escape
from datetime import date
import sqlite3
import time

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, QTimer, pyqtSignal, QSettings
from services.coach_assistant_v1.insights import AssistantInsight


class _ResearchSignals(QObject):
    ready=pyqtSignal(int, int, object)


class _ResearchJob(QRunnable):
    def __init__(self, serial, sid):
        super().__init__()
        self.serial, self.sid = serial, sid
        self.signals = _ResearchSignals()

    def run(self):
        card=None
        try:
            from db import DB_PATH
            from services.evidence_based_coach_v3563 import read_evidence_based_coach
            uri=DB_PATH.resolve().as_uri() + '?mode=ro'
            with closing(sqlite3.connect(uri, uri=True, timeout=2)) as con:
                con.execute('PRAGMA query_only=ON')
                # One coherent read snapshot, no schema changes, bounded CPU work.
                con.execute('BEGIN')
                deadline=time.monotonic()+2.5
                con.set_progress_handler(lambda: 1 if time.monotonic() >= deadline else 0, 2000)
                try:
                    card=read_evidence_based_coach(con, self.sid)
                    # v3.5.65: same query-only transaction; a source failure
                    # NEVER prevents the legacy scientific cards from displaying.
                    if isinstance(card, dict):
                        try:
                            from services.automatic_coaching_cycle_v3565 import read_automatic_coaching_cycle
                            card['cycle_v3565'] = read_automatic_coaching_cycle(con, self.sid)
                        except Exception:
                            card['cycle_v3565'] = None
                    # V3.5.64: reuse the SAME read-only snapshot and worker.
                    # No parallel database reader or extra UI work on checkbox clicks.
                    if isinstance(card,dict) and card.get('state')=='REVIEW_SUGGESTED':
                        from services.science_wizard_alignment_v3564 import read_science_wizard_alignment
                        try:
                            card['wizard_alignment_v3564']=read_science_wizard_alignment(
                                con,self.sid,research_card=card)
                        except Exception:
                            # Missing optional V30 sources must not suppress V3563.
                            card['wizard_alignment_v3564']=None
                    # v3.5.69: bounded, pure planning preview using already
                    # loaded, verified evidence. No new SQL or calendar claims.
                    # Unknown available time remains None, NEVER infinite.
                    if isinstance(card, dict) and card.get('cycle_v3565') is not None:
                        try:
                            from services.smart_study_plan_v3569 import build_smart_study_plan
                            card['study_plan_v3569'] = build_smart_study_plan(
                                card['cycle_v3565'], card.get('wizard_alignment_v3564'),
                                self.sid, today=date.today())
                        except (ImportError, ValueError, TypeError, KeyError):
                            card['study_plan_v3569'] = None
                    # V3.5.72 read only: an optional, approved student/parent
                    # observation is NOT an academic measurement or diagnosis.
                    try:
                        import os
                        if (isinstance(card,dict)
                                and os.getenv('YKS_HOMEWORK_FEEDBACK_V12_ENABLED')=='1'):
                            from services.homework_feedback_coaching_v3572 import read_coaching_feedback
                            card['homework_feedback_v3572']=read_coaching_feedback(con,self.sid)
                    except (sqlite3.Error, ValueError, TypeError, KeyError, ImportError):
                        pass
                finally:
                    con.set_progress_handler(None, 0)
                    con.rollback()  # end read-only snapshot
        except Exception:
            card=None  # Never show fabricated success/error diagnosis.
        self.signals.ready.emit(self.serial, self.sid, card)


class ResearchCoachingBridgeV3563(QObject):
    """Installed alongside existing assistant; no monkeypatches, database writes or dialogs."""
    def __init__(self, form, assistant):
        super().__init__(form)
        self.form = form
        self.assistant=assistant
        self._current_sid=None
        self._serial=0
        self._active_jobs={}
        self._navigation_snapshot_v3568 = None  # Student-scoped; no database writes.
        self._settings=QSettings('EduTrack','HomeworkManagerV2')
        # V3.5.66: AFTER-COMMIT notification via existing student-scoped
        # SQLite data-version probe. This is not a click/save interception.
        # It also observes successful commits from the separate Control dialog.
        try:
            from ui.live_change_bridge_v241 import install_live_updates
            self._commit_listener_v3566 = install_live_updates(
                form, self._on_committed_change_v3566,
                student_attr='_secili_ogrenci_id')
        except (ImportError, RuntimeError, AttributeError):
            self._commit_listener_v3566 = False
        # Optional after-save refresh: connects OUTSIDE protected form sources.
        # Never intercepts or replaces a clicked handler and never touches
        # checkbox/state/callbacks. The 850ms delay allows old save to finish.
        for control in ('btnKaydet', 'btnGetir'):
            button=getattr(form, control, None)
            if button is not None:
                button.clicked.connect(self._schedule_refresh)

    def _on_committed_change_v3566(self):
        # The original SQLite probe only calls after an observed commit and
        # a matching student-scope change. Ignore another student's updates.
        if not self._allowed() or self._current_sid is None:
            return
        try:
            selected = self.form._secili_ogrenci_id()
        except (AttributeError, TypeError, ValueError):
            return
        if type(selected) is int and selected == self._current_sid:
            self._schedule_refresh()

    def _schedule_refresh(self, *_):
        if not self._allowed():
            return
        sid=self._current_sid
        if sid is None:
            return
        try:
            selected=self.form._secili_ogrenci_id()
        except (AttributeError, TypeError, ValueError):
            return
        if selected != sid:
            return
        self._navigation_snapshot_v3568 = None  # A committed change invalidates old actions.
        QTimer.singleShot(850, lambda expected=sid: self._refresh_if_current(expected))

    def _refresh_if_current(self, expected):
        if expected == self._current_sid and self._allowed():
            self.on_student_changed(expected)

    def _allowed(self):
        # Existing assistant enable/disable remains the single user-facing switch.
        return (self.assistant is not None and self.assistant.is_enabled()
            and str(self._settings.value('research_coaching_v3563_enabled','1')).lower()
               not in ('0','false','off','no'))

    def on_student_changed(self, sid):
        self._navigation_snapshot_v3568 = None
        self._serial+=1
        self._current_sid=sid if type(sid) is int and sid>0 else None
        if self._current_sid is None or not self._allowed():
            return
        serial=self._serial
        QTimer.singleShot(550, lambda: self._load(serial))

    def _load(self, serial):
        if serial != self._serial or self._current_sid is None or not self._allowed():
            return
        # Bound number of outstanding jobs even if student selection changes quickly.
        if len(self._active_jobs)>=2:
            # Do not block the UI; the newest student is retried when jobs clear.
            return
        job=_ResearchJob(serial, self._current_sid)
        self._active_jobs[serial]=job
        job.signals.ready.connect(self._result)
        QThreadPool.globalInstance().start(job)

    def _result(self, serial, sid, card):
        self._active_jobs.pop(serial,None)
        if (serial != self._serial or sid != self._current_sid):
            if (self._current_sid is not None and self._allowed()
                and self._serial not in self._active_jobs):
                QTimer.singleShot(250, lambda expected=self._serial: self._load(expected))
            return
        if (not self._allowed()
            or not isinstance(card,dict) or card.get('schema')!='evidence_based_coach_v3563'
            or card.get('student_id')!=sid):
            return
        # v3.5.68: cache validated recommendation sources for the existing
        # context menu. This does not open any window or select a checkbox.
        # A later student selection / committed change clears this snapshot.
        self._navigation_snapshot_v3568 = {
            'student_id': sid, 'as_of': date.today().isoformat(),
            'cycle': card.get('cycle_v3565'),
            'alignment': card.get('wizard_alignment_v3564'),
        }
        # V3.5.72: at most one reviewed, student-bound observation in the
        # existing inbox. No new popup, button, survey action or auto diagnosis.
        if str(self._settings.value('homework_feedback_coaching_v3572_enabled','1')).lower() not in ('0','false','off','no'):
            self._show_feedback_v3572(sid, card.get('homework_feedback_v3572'))
        # Cycle shows only NON-DUPLICATE followup/optional-check alerts. Existing
        # research cards continue to own targeted review and spaced checks.
        priority_key = self._show_cycle_advice(sid, card.get('cycle_v3565'), card.get('study_plan_v3569'))
        if card.get('state') != 'REVIEW_SUGGESTED':
            return
        for item in card.get('cards',[])[:2]:
            if not isinstance(item,dict) or item.get('requires_teacher_approval') is not True:
                continue
            lesson,topic=str(item.get('lesson') or ''),str(item.get('topic') or '')
            if not lesson.strip() or not topic.strip(): continue
            if (lesson.strip().casefold(), topic.strip().casefold()) == priority_key:
                continue  # Shared academic priority already shown once.
            refs=', '.join(escape(str(x.get('title') or '')) for x in item.get('references',[])[:2])
            insight=AssistantInsight(
                title='📚 Kanıta Dayalı Öğrenme',badge='🔬 Öğretmen Onayı',
                curiosity_hook=f'{lesson} › {topic}: {item.get("strategy", "Kontrol önerisi")}',
                body_html=(f'<b>{escape(lesson)} › {escape(topic)}</b><br>'
                    f'{escape(str(item.get("observation") or ""))}<br>'
                    f'<b>Öneri:</b> {escape(str(item.get("teacher_activity") or ""))}<br>'
                    f'<b>Öğrenciye sor:</b> {escape(str(item.get("reflection_question") or ""))}<br>'
                    f'<small>Kaynaklar: {refs}<br>Öğrenciye özel başarı garantisi değildir; öğretmen onayı gerekir.</small>'),
                action_text='🧠 Öğrenme Ekranında İncele',target_key='btnOgrenme',
                pointer_caption='Öğrenme verileri',border_color='#38bdf8')
            # Existing checkbox attention policy = inbox ONLY, never interrupts teacher.
            self.assistant._present_insight(insight,manual=False,source='checkbox',
                                            lesson=lesson,topic_name=topic)
        # One additional, non-intrusive suggestion only when actual V30
        # book/topic records match the evidence. Opens EXISTING wizard only.
        self._show_wizard_advice(sid, card.get('wizard_alignment_v3564'))

    def _show_feedback_v3572(self, sid, feedback_card):
        if not self._allowed() or self._current_sid != sid:
            return
        try:
            from services.homework_feedback_coaching_v3572 import assistant_feedback_hint
            hint = assistant_feedback_hint(feedback_card, sid)
        except (ImportError, TypeError, ValueError, KeyError):
            return
        if not hint:
            return
        lesson, topic = hint['lesson'], hint['topic']
        insight = AssistantInsight(
            title='📝 Onaylı Ödev Geri Bildirimi', badge='🔎 Görüşme Desteği',
            curiosity_hook=f'{lesson} › {topic}: {hint["source"]}'[:180],
            body_html=(f'<b>{escape(lesson)} › {escape(topic)}</b><br>'
                f'{escape(hint["source"])}: {escape(hint["obstacle_label"])}<br>'
                f'<b>Sonraki adım:</b> {escape(hint["next_step"])}<br>'
                '<small>Öğretmenin incelediği gönüllü bildirimdir; '
                'bağımsız ölçüm, kesin kök neden veya tamamlanma kaydı değildir. '
                'Yeni ödev atanmadı.</small>'),
            action_text='🧠 Öğrenme Kayıtlarında İncele',
            target_key='btnOgrenme', pointer_caption='Öğretmen görüşmesi',
            border_color='#38bdf8')
        self.assistant._present_insight(
            insight, manual=False, source='checkbox', lesson=lesson,
            topic_name=topic,
            key_override=f'v3572:feedback:{sid}:{hint["reply_id"]}')

    def navigation_recommendations_v3568(self, sid, today=None):
        """Only today's verified evidence for the currently selected student."""
        day = today or date.today()
        snapshot = self._navigation_snapshot_v3568
        if (not self._allowed() or type(sid) is not int
            or sid != self._current_sid or type(day) is not date
            or not isinstance(snapshot, dict)
            or snapshot.get('student_id') != sid
            or snapshot.get('as_of') != day.isoformat()):
            return ()
        try:
            from services.coaching_navigation_v3568 import recommended_existing_targets
            return recommended_existing_targets(sid, day,
                cycle=snapshot.get('cycle'), alignment=snapshot.get('alignment'))
        except (ImportError, TypeError, ValueError, KeyError):
            return ()

    def _show_wizard_advice(self, sid, advice):
        if (not isinstance(advice,dict)
            or advice.get('schema')!='science_wizard_alignment_v3564'
            or advice.get('student_id')!=sid
            or advice.get('state')!='MATCHED'
            or advice.get('read_only') is not True
            or advice.get('auto_assignment') is not False
            or advice.get('teacher_approval_required') is not True
            or not self._allowed()):
            return
        items=advice.get('matched') or []
        if not items or not isinstance(items[0],dict): return
        first=items[0]
        lesson,topic=str(first.get('lesson') or ''),str(first.get('topic') or '')
        book=str(first.get('existing_book') or '')
        if not all(x.strip() for x in (lesson,topic,book)): return
        insight=AssistantInsight(
            title='✨ Koçluk → Akıllı Ödev Sihirbazı',badge='🔎 Taslak Eşleşmesi',
            curiosity_hook=f'{lesson} › {topic}: mevcut kitaptan çalışma adayı',
            body_html=(f'<b>{escape(lesson)} › {escape(topic)}</b><br>'
                f'Öğrenme kanıtıyla Sihirbaz taslağında eşleşen kitap: <b>{escape(book)}</b>.<br>'
                f'<b>Yaklaşım:</b> {escape(str(first.get("strategy") or ""))}<br>'
                f'<small>{len(items)} eşleşen aday. Yeni ödev atanmadı; Sihirbaz '
                f'açılınca öğrenci, kitap, hücre ve ödev durumu yeniden '
                f'kontrol edilmelidir. Öğretmen Sihirbazı ayrıca açıp taslağı '
                f'inceler; onay ve mevcut Kaydet gereklidir.</small>'),
            action_text='🧠 Öğrenmede Kanıtları İncele',target_key='btnOgrenme',
            pointer_caption='Mevcut Sihirbaz',border_color='#38bdf8')
        # Inbox only, no popup, no auto-click. Reuse normal assistant suppression.
        self.assistant._present_insight(
            insight,manual=False,source='checkbox',
            lesson=lesson,topic_name=topic,
            key_override=f'v3564:wizard:{sid}:{lesson.casefold()}:{topic.casefold()}')

    def _show_cycle_advice(self, sid, cycle, study_plan=None):
        """Same verified top-priority card used by Student360 and teacher strip."""
        if not self._allowed():
            return None
        if str(self._settings.value('coaching_action_center_v3567_enabled', '1')).lower() in ('0', 'false', 'off', 'no'):
            return self._show_cycle_legacy_v3565(sid, cycle)
        try:
            from services.coaching_action_center_v3567 import build_action_center_card
            if not isinstance(cycle, dict):
                return None
            day = date.today()  # Never display yesterday's priority as current.
            card = build_action_center_card(cycle, sid, today=day)
        except (TypeError, ValueError, KeyError, ImportError):
            return None
        if (card['state'] != 'ACTION_SUGGESTED'
            or card['student_id'] != sid or card['action_key'] != 'btnOgrenme'):
            return None
        lesson, topic = card['lesson'], card['topic']
        detail = card['area'] or 'Bağımsız öğrenme kontrolü'
        # Feature switch restores exact previous card text and behavior.
        plan_hint = ''
        if str(self._settings.value('smart_study_plan_v3569_enabled', '1')).lower() not in ('0', 'false', 'off', 'no'):
            try:
                from services.smart_study_plan_v3569 import compact_study_plan_hint
                plan_hint = compact_study_plan_hint(
                    study_plan, sid, today=day, expected_lesson=lesson, expected_topic=topic)
            except (ImportError, TypeError, ValueError, KeyError):
                plan_hint = ''
        insight = AssistantInsight(
            title='🧭 Ortak Koçluk Önceliği', badge='🔎 Öğretmen Onayı',
            curiosity_hook=f'{card["title"]} — {detail}'[:180],
            body_html=(f'<b>{escape(card["title"])} — {escape(detail)}</b><br>'
                f'{escape(card["reason"])}<br>'
                f'<b>Sonraki adım:</b> {escape(card["next_step"])}<br>'
                + (f'<b>Çalışma planı:</b> {escape(plan_hint)}<br>' if plan_hint else '')
                + '<small>Aynı akademik öncelik Öğrenci 360° ile paylaşılır. '
                'Yalnızca yerel öğrenme kayıtları incelendi; ödev atanmadı, '
                'ölçülmemiş öğrenme veya müdahale etkisi iddia edilmedi.</small>'),
            action_text='🧠 Öğrenme Kayıtlarını İncele', target_key='btnOgrenme',
            pointer_caption='Öğrenme / izlem', border_color='#38bdf8')
        self.assistant._present_insight(
            insight, manual=False, source='checkbox', lesson=lesson, topic_name=topic,
            key_override=(f'v3567:priority:{sid}:{card["kind"]}:'
                          f'{lesson.casefold()}:{topic.casefold()}'))
        return lesson.casefold(), topic.casefold()

    # Feature disabled: retain the exact previous V3565 optional followup inbox.
    def _show_cycle_legacy_v3565(self, sid, cycle):
        if (not self._allowed() or not isinstance(cycle, dict)
            or cycle.get('schema') != 'automatic_coaching_cycle_v3565'
            or cycle.get('student_id') != sid or cycle.get('state') != 'ACTION_SUGGESTED'
            or cycle.get('read_only') is not True
            or cycle.get('teacher_approval_required') is not True
            or cycle.get('auto_change_allowed') is not False):
            return
        # Only one inbox card. Low importance recommendations stay in existing
        # research inbox to avoid duplicating the same academic topic.
        for item in cycle.get('next_actions', [])[:2]:
            if (not isinstance(item, dict)
                or item.get('kind') not in ('INTERVENTION_FOLLOWUP', 'OPTIONAL_INDEPENDENT_CHECK')
                or item.get('teacher_approval_required') is not True
                or item.get('auto_assignment') is not False
                or item.get('auto_message') is not False):
                continue
            lesson, topic = str(item.get('lesson') or ''), str(item.get('topic') or '')
            detail = ' › '.join(p for p in (lesson,topic) if p.strip())
            insight = AssistantInsight(
                title='🔁 Akademik Koçluk Döngüsü', badge='🔎 Öğretmen İncelemesi',
                curiosity_hook=(detail or 'Bağımsız öğrenme kontrolü')[:180],
                body_html=(f'<b>{escape(detail or "Öğrenme kanıtı")}</b><br>'
                    f'{escape(str(item.get("reason") or ""))}<br>'
                    f'<b>Sonraki adım:</b> {escape(str(item.get("next_step") or ""))}<br>'
                    '<small>Ödev kaydı değiştirilmedi; öğretmen onayı gerekir. '
                    'Öğrenme veya müdahale etkisi kesinleştirilmedi.</small>'),
                action_text='🧠 Öğrenme Kayıtlarını İncele', target_key='btnOgrenme',
                pointer_caption='Öğrenme / izlem', border_color='#38bdf8')
            self.assistant._present_insight(
                insight, manual=False, source='checkbox',
                lesson=lesson, topic_name=topic,
                key_override=f'v3565:cycle:{sid}:{item["kind"]}:{lesson.casefold()}:{topic.casefold()}')
            break
