# -*- coding: utf-8 -*-
"""Teacher-triggered bridge; never attached to checkbox/save event handlers."""
import sqlite3
from contextlib import closing
from pathlib import Path
from html import escape
from PyQt6.QtWidgets import QMessageBox
from services.weekly_adaptive_bridge_v35 import suggested_lesson_focus
from services.weekly_topic_priority_v35 import accepted_topic_pairs


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
            suggestions = suggested_lesson_focus(con, sid, dialog.homework_list)
    except (sqlite3.Error, OSError, ValueError) as exc:
        QMessageBox.warning(dialog, 'Adaptif Öncelikler',
                            'Öğretmen gözlemleri okunamadı; plan değişmedi.\n' + str(exc))
        return False
    if not suggestions:
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
