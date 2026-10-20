# -*- coding: utf-8 -*-
"""Teacher-triggered bridge; never attached to checkbox/save event handlers."""
import sqlite3
from contextlib import closing
from pathlib import Path
from html import escape
from datetime import date
from time import monotonic
from PyQt6.QtWidgets import QMessageBox
from services.weekly_adaptive_bridge_v35 import suggested_lesson_focus
from services.weekly_topic_priority_v35 import accepted_topic_pairs
from services.weekly_coaching_alignment_v3570 import align_coaching_to_existing_week


def offer_focus_suggestions(dialog):
    sid_text = str(getattr(dialog, 'student_id', '') or '').strip()
    if not sid_text.isdecimal() or int(sid_text) <= 0:
        QMessageBox.information(dialog, 'Adaptif Öncelikler',
                                'Öğrenci kimliği seçili değil. Mevcut plan ayarları korunuyor.')
        return False
    sid = int(sid_text)
    parent = dialog.parent()
    if parent is not None and hasattr(parent, '_secili_ogrenci_id'):
        if str(parent._secili_ogrenci_id() or '').strip() != sid_text:
            QMessageBox.warning(dialog, 'Öğrenci Değişti',
                                'Seçili öğrenci değişmiş. Öneriler uygulanmadı.')
            return False
    try:
        from db import DB_PATH
        uri = Path(DB_PATH).resolve().as_uri() + '?mode=ro'
        with closing(sqlite3.connect(uri, uri=True, timeout=0.5)) as con:
            con.row_factory = sqlite3.Row
            con.execute('PRAGMA query_only=ON')
            con.execute('BEGIN')  # Both readers see one consistent SQLite snapshot.
            suggestions = suggested_lesson_focus(con, sid, dialog.homework_list)
            # Same explicit teacher click: supplemental scientific coaching evidence.
            # If the modern source is unavailable, the existing v35 behavior remains.
            # Invalid modern evidence never becomes a new lesson priority.
            learning_alignment = None
            start = monotonic()
            # Explicit click only; legacy planner must not freeze if the new
            # optional source is slow on a large school database.
            con.set_progress_handler(lambda: int(monotonic() - start > 0.35), 1000)
            try:
                from services.automatic_coaching_cycle_v3565 import read_automatic_coaching_cycle
                today = date.today()
                cycle = read_automatic_coaching_cycle(con, sid, today=today)
                learning_alignment = align_coaching_to_existing_week(
                    cycle, sid, dialog.homework_list, today=today)
            except (sqlite3.Error, ValueError, TypeError, KeyError, AttributeError):
                learning_alignment = None
            finally:
                con.set_progress_handler(None, 0)
            if learning_alignment and learning_alignment['state'] == 'REVIEW_AVAILABLE':
                # Only confirmed, *already assigned* topics can join the v35
                # teacher-approved ordering; duplicate suggestions coalesce.
                for candidate in learning_alignment['focus_candidates']:
                    entry = next((x for x in suggestions
                                  if candidate['lesson'] == x['lesson']), None)
                    if entry is None:
                        suggestions.append({'lesson': candidate['lesson'],
                                            'topics': [candidate['topic']],
                                            'reasons': ['Birden fazla bağımsız ölçüm: öğretmen incelemesi öneriliyor.']})
                    elif candidate['topic'] not in entry['topics']:
                        entry['topics'].append(candidate['topic'])
                        entry['reasons'].append(
                            candidate['topic'] + ': Birden fazla bağımsız ölçüm için hedefli inceleme öneriliyor.')
    except (sqlite3.Error, OSError, ValueError) as exc:
        QMessageBox.warning(dialog, 'Adaptif Öncelikler',
                            'Öğretmen gözlemleri okunamadı; plan değişmedi.\n' + str(exc))
        return False
    followup_notes = (learning_alignment.get('measurement_notes', [])
                      if learning_alignment and learning_alignment['state'] == 'REVIEW_AVAILABLE' else [])
    if not suggestions:
        if followup_notes:
            detail = '\n'.join(f"• {n['lesson']} / {n['topic']}: {n['label']}"
                               for n in followup_notes[:3])
            QMessageBox.information(dialog, 'Öğrenme Kontrolü (Ödev Eklenmedi)',
                                    detail + '\n\nMevcut haftalık plan ve PDF değişmedi.')
            return False
        QMessageBox.information(dialog, 'Adaptif Öncelikler',
                                'Verilen ödevlerde öncelik değişikliği için yakın tarihli '
                                'öğretmen gözlemi veya kısa bağımsız ölçüm bulunmuyor.\n'
                                'Mevcut ders öncelikleri aynı kalacak.')
        return False
    items = []
    for entry in suggestions:
        detail = '; '.join(escape(x) for x in entry['reasons'][:3])
        items.append(f'<li><b>{escape(entry["lesson"])}</b>: {detail}</li>')
    html = ('<p>Yalnızca mevcut <b>Verilen Ödevler</b> konularından sinyaller bulundu:</p><ul>'
            + ''.join(items) + '</ul><p>Onay verirseniz bu haftalık plan için '
            '<b>yalnızca eşleşen ders + konu</b> ödevleri öncelik kazanır. '
            'Aynı dersteki diğer konular otomatik olarak öne alınmaz. '
            'Elle seçilmiş <b>genel ders öncelikleri</b> ayrı korunur. '
            '<b>Yeni ödev oluşturulmaz; süre, teslim tarihi ve okul/uyku sınırları değişmez.</b> '
            'Alt kazanım bilgisi Verilen Ödevler tablosunda bulunmadığı için '
            'sistem bir alt kazanım uydurmaz. Tek düşük ölçüm kesin öğrenme yargısı değildir.</p>')
    if followup_notes:
        html += ('<p><b>Bilgi — mevcut ödevlere eklenmeyen ölçüm önerileri:</b><br/>'
                 + '<br/>'.join(escape(n['lesson'] + ' / ' + n['topic'] + ': ' + n['label'])
                               for n in followup_notes[:3])
                 + '<br/>Bu ölçümler için otomatik süre, görev veya PDF satırı oluşturulmaz.</p>')
    accepted = QMessageBox.question(
        dialog, '🧠 Adaptif Koçluk → Ders Önceliği', html,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No)
    if accepted != QMessageBox.StandardButton.Yes:
        return False
    if str(getattr(dialog, 'student_id', '') or '').strip() != sid_text:
        return False
    if parent is not None and hasattr(parent, '_secili_ogrenci_id'):
        if str(parent._secili_ogrenci_id() or '').strip() != sid_text:
            return False
    topics = [{'lesson': entry['lesson'], 'topic': topic}
              for entry in suggestions for topic in entry['topics']]
    approved = accepted_topic_pairs(dialog.homework_list, topics)
    if not approved:
        return False
    # Only this dialog / plan; never overwrite the shared profile's lesson list.
    dialog._approved_topic_focus = approved
    if hasattr(dialog, 'weekly_overview'):
        dialog.weekly_overview.refresh()
    return True
