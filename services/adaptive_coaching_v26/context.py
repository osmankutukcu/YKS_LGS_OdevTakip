# -*- coding: utf-8 -*-
"""Salt-okunur öğrenci hedefi / mevcut koçluk planı bağlantısı.

Hedefler öğretmenin kayıtlarıdır; otomatik tahmin veya kazanım kanıtı sayılmaz.
Deneme soru-kazanım eşlemesi yeterince doğrulanmadığı için bu sürümde karar
motoruna yanlış/konu eşleşmesi otomatik aktarılmaz.
"""
from __future__ import annotations
from datetime import date, datetime
from services.target_analysis_v24.student_target import read_saved_target


def student_context(con, student_id, today=None):
    day = (today.date() if isinstance(today, datetime) else today if isinstance(today, date)
           else date.fromisoformat(str(today)[:10]) if today else date.today())
    sid = int(student_id)
    if not con.execute('SELECT 1 FROM ogrenci WHERE id=?',(sid,)).fetchone():
        raise ValueError('Öğrenci bulunamadı.')
    # Upstream target adapter checks column existence before reading.
    target = read_saved_target(con,sid)
    plan_summary = 'Kayıtlı haftalık koçluk planı bulunamadı.'
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='koc_plan'")}
    if 'koc_plan' in tables:
        names = {r[1] for r in con.execute('PRAGMA table_info(koc_plan)')}
        if {'ogrenci_id','baslangic_tarihi','bitis_tarihi'}.issubset(names):
            row = con.execute('''SELECT COUNT(*) FROM koc_plan WHERE ogrenci_id=?
                AND baslangic_tarihi<=? AND bitis_tarihi>=?''',
                (sid,day.isoformat(),day.isoformat())).fetchone()
            if int(row[0] or 0):
                plan_summary = f"Bu haftaya ait {int(row[0])} koçluk planı kaydı var."
    return {'target':target, 'coaching_plan':plan_summary,
            'note':'Hedef/koçluk kayıtları ölçülmüş kazanım olarak kullanılmaz.'}
