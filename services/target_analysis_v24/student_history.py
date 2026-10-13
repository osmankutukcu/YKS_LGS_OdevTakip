# -*- coding: utf-8 -*-
"""V24 kişi kapsamlı deneme-trend geçmişi.

Eski öğrenci kimliği OLMAYAN `deneme` tablosuna dokunmaz ve kayıtları
keyfî öğrenciye bağlamaz. Yeni satırlar ayrı tabloda saklanır. Kaynak anahtarı
ile aynı sınavın mükerrer senkronizasyonu engellenir.
"""
from __future__ import annotations
import sqlite3
import datetime as dt
import json
from pathlib import Path
from typing import Any, Mapping


class StudentTrendStore:
    def __init__(self, db_path: str):
        self.db_path = str(db_path)
        # Testlerde/uygulamada yolu çağıran belirler; canlı veriye taşıma yapmaz.
        with self._connection() as con:
            con.execute('''CREATE TABLE IF NOT EXISTS deneme_student_v24 (
                id INTEGER PRIMARY KEY,
                student_id INTEGER NOT NULL CHECK(student_id > 0),
                d TEXT NOT NULL,
                exam TEXT NOT NULL,
                alan TEXT NOT NULL,
                payload TEXT NOT NULL,
                source_key TEXT,
                UNIQUE(student_id, source_key)
            )''')
            con.execute('''CREATE INDEX IF NOT EXISTS idx_student_v24_history
                         ON deneme_student_v24(student_id, exam, alan, d)''')

    def _connection(self):
        return sqlite3.connect(self.db_path, timeout=10)

    def add(self, student_id: int, date_: dt.date, exam: str, alan: str,
            payload: Mapping[str, Any], source_key: str | None = None) -> bool:
        student_id = int(student_id)
        if student_id <= 0:
            raise ValueError('Trend kaydı için geçerli öğrenci kimliği gerekir.')
        if not isinstance(date_, dt.date):
            raise ValueError('Tarih tipi geçersiz.')
        if not isinstance(payload, Mapping):
            raise ValueError('Deneme sonucu geçersiz.')
        raw = json.dumps(dict(payload),ensure_ascii=False,allow_nan=False)
        with self._connection() as con:
            cur = con.execute('''INSERT OR IGNORE INTO deneme_student_v24
                (student_id, d, exam, alan, payload, source_key)
                VALUES (?,?,?,?,?,?)''', (student_id,date_.isoformat(),exam,alan,raw,source_key))
            return cur.rowcount == 1

    def sync_source(self, student_id: int, date_: dt.date, exam: str, alan: str,
                    payload: Mapping[str, Any], source_key: str) -> str:
        # Kaynağı belli sınavı güncelle; manuel satırlara dokunma.
        # Sonuç: inserted / updated / unchanged.
        sid = int(student_id)
        if sid <= 0 or not source_key or not isinstance(date_,dt.date):
            raise ValueError('Geçerli öğrenci, sınav kaynağı ve tarih gerekli.')
        raw = json.dumps(dict(payload),ensure_ascii=False,allow_nan=False,sort_keys=True)
        with self._connection() as con:
            existing = con.execute('''SELECT id,d,exam,alan,payload
                 FROM deneme_student_v24 WHERE student_id=? AND source_key=?''',
                 (sid,source_key)).fetchone()
            if existing is None:
                con.execute('''INSERT INTO deneme_student_v24
                    (student_id,d,exam,alan,payload,source_key) VALUES (?,?,?,?,?,?)''',
                    (sid,date_.isoformat(),exam,alan,raw,source_key))
                return 'inserted'
            rowid, old_date, old_exam, old_alan, old_payload = existing
            if (old_date,old_exam,old_alan,json.loads(old_payload)) == (date_.isoformat(),exam,alan,json.loads(raw)):
                return 'unchanged'
            con.execute('''UPDATE deneme_student_v24 SET d=?,exam=?,alan=?,payload=?
                WHERE id=? AND student_id=?''',
                (date_.isoformat(),exam,alan,raw,rowid,sid))
            return 'updated'

    def list_last(self, student_id: int, exam: str, alan: str, n: int = 20):
        student_id = int(student_id)
        if student_id <= 0:
            return []
        n = max(1,min(int(n),200))
        with self._connection() as con:
            rows = con.execute('''SELECT d, payload FROM deneme_student_v24
                WHERE student_id=? AND exam=? AND alan=?
                ORDER BY d DESC, id DESC LIMIT ?''', (student_id,exam,alan,n)).fetchall()
        out=[]
        for d,p in reversed(rows):
            try:
                out.append((dt.date.fromisoformat(d),json.loads(p)))
            except (ValueError,TypeError,json.JSONDecodeError):
                continue
        return out
