# -*- coding: utf-8 -*-
"""V29 optional, read-only detail pop-up. No checkbox / save listeners."""
import sqlite3
from contextlib import closing
from pathlib import Path
from PyQt6.QtWidgets import QMessageBox

from services.adaptive_coaching_v29.next_steps import next_step_for_homework, plain_text


def show_for_selected_homework(parent, student_id, homework_id):
    try:
        from db import DB_PATH
        # Path.as_uri() preserves Windows drive letters and UNC routes.
        uri = Path(DB_PATH).resolve().as_uri() + '?mode=ro'
        with closing(sqlite3.connect(uri, uri=True, timeout=0.35)) as con:
            con.row_factory = sqlite3.Row
            con.execute('PRAGMA query_only=ON')
            result = next_step_for_homework(con, student_id, homework_id)
        QMessageBox.information(parent,'🧠 Sonraki Adım · Öğretmen Önerisi',plain_text(result))
    except (sqlite3.Error, OSError, ValueError) as exc:
        QMessageBox.warning(parent,'Adaptif Koçluk',
            'Öneri okunamadı. Mevcut ödevler ve kaydetme işlemleri etkilenmedi.\n'+str(exc))
