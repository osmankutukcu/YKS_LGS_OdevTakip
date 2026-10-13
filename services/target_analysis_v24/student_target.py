# -*- coding: utf-8 -*-
# V24 öğrencinin kaydedilmiş hedefini salt okunur gösterir.
# Yerleşme olasılığı veya resmî puan tahmini üretmez.
from __future__ import annotations
import sqlite3


def read_saved_target(con: sqlite3.Connection, student_id: int) -> str:
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('Geçersiz öğrenci kimliği.')
    required = {'id', 'hedef_bolum', 'hedef_tyt', 'hedef_ayt', 'hedef_lgs'}
    names = {row[1] for row in con.execute('PRAGMA table_info(ogrenci)')}
    if not required.issubset(names):
        return 'YKS/LGS hedef alanları bu veritabanında bulunmuyor.'
    row = con.execute('''SELECT hedef_bolum, hedef_tyt, hedef_ayt, hedef_lgs
                         FROM ogrenci WHERE id=?''',(student_id,)).fetchone()
    if row is None:
        return 'Öğrenciye ait hedef bulunamadı.'
    label = str(row[0] or '').strip()
    if not label:
        return 'Henüz hedef kaydedilmedi.'
    try:
        if float(row[3] or 0)>0:
            nums = f'LGS hedef neti: {float(row[3]):g}/90'
        else:
            nums = f'TYT: {float(row[1] or 0):g} | AYT/YDT: {float(row[2] or 0):g}'
    except (ValueError,TypeError):
        nums='Hedef net sayıları doğrulanamadı.'
    return f'{label} — {nums}. Bu hedef öğretmen kaydıdır; yerleşme garantisi değildir.'
