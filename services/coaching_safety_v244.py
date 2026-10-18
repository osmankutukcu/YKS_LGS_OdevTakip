"""V24.4 Koçluk veri güvenliği: bağımsız, test edilebilir SQLite servisleri.

Değişiklikler yalnızca koçluk tablo verisine uygulanır; ana ödev/checkbox tablolarına
DOKUNULMAZ. Tek işlemde öğrenci/hafta bağlamı doğrulanır. Silme yerine koruma.
"""
from __future__ import annotations
from datetime import datetime, timezone
import math
import json
import sqlite3

class CoachingDataError(ValueError):
    pass

class CoachingConflict(CoachingDataError):
    pass

def _student(student_id):
    if type(student_id) is not int or student_id <= 0:
        raise CoachingDataError('Öğrenci seçimi geçersiz.')
    return student_id

def _name(value):
    if not isinstance(value, str) or not value.strip():
        raise CoachingDataError('Ders adı boş olamaz.')
    return ' '.join(value.split())

def _whole(value, label):
    if isinstance(value,bool) or isinstance(value,complex):
        raise CoachingDataError(f'{label}: sayı giriniz.')
    try:
        text=str(value).strip()
        if not text or any(x in text.lower() for x in ('.',',','e','nan','inf')): raise ValueError
        val=int(text)
    except (ValueError,TypeError,OverflowError):
        raise CoachingDataError(f'{label}: sıfır veya pozitif tam sayı giriniz.') from None
    if val < 0 or val > 10_000_000:
        raise CoachingDataError(f'{label}: 0–10.000.000 aralığında olmalı.')
    return val

def _hours(value, label):
    try:
        v=float(str(value).replace(',','.').strip())
    except (ValueError,TypeError,OverflowError):
        raise CoachingDataError(f'{label}: geçerli saat giriniz.') from None
    if not math.isfinite(v) or not 0<=v<=100000:
        raise CoachingDataError(f'{label}: geçerli ve negatif olmayan saat giriniz.')
    return v

def _weekly_plan(con,student_id,week):
    rows=con.execute('SELECT id FROM koc_plan WHERE ogrenci_id=? AND baslangic_tarihi=? ORDER BY id',(student_id,week)).fetchall()
    if len(rows)>1:
        raise CoachingConflict('Aynı öğrenci/hafta için birden çok plan var. Otomatik birleştirme güvenli değil; kayıtları inceleyin.')
    return int(rows[0][0]) if rows else None

def _existing_goals(con,plan_id):
    rows=con.execute('SELECT id,ders_adi FROM koc_hedef WHERE plan_id=? ORDER BY id',(plan_id,)).fetchall()
    mapping={}
    for rid, subject in rows:
        key=_name(subject).casefold()
        if key in mapping:
            raise CoachingConflict(f'{subject} için birden çok hedef satırı bulundu; ilerleme otomatik değiştirilmedi.')
        mapping[key]=int(rid)
    return mapping

def upsert_week_plan(con,student_id,week,end,selected_goals):
    """Same week/course preserves goal IDs and progress. Omitted courses retained.

    Caller commits on success; rolls back on error. No DELETE statements.
    """
    _student(student_id)
    if not isinstance(week,str) or len(week)!=10 or not isinstance(end,str) or len(end)!=10:
        raise CoachingDataError('Hafta tarih biçimi geçersiz.')
    proposed={}
    for subject, target in selected_goals:
        subject=_name(subject); key=subject.casefold()
        if key in proposed: raise CoachingDataError('Aynı ders iki kez seçildi.')
        proposed[key]=(subject,_whole(target,subject+' hedef soru'))
    if not proposed: raise CoachingDataError('En az bir ders seçiniz.')
    plan_id=_weekly_plan(con,student_id,week)
    if plan_id is None:
        # In SQLite, the surrounding caller's BEGIN IMMEDIATE serializes writers.
        cur=con.execute('INSERT INTO koc_plan(ogrenci_id,baslangic_tarihi,bitis_tarihi) VALUES(?,?,?)',
                        (student_id,week,end))
        plan_id=int(cur.lastrowid)
    existing=_existing_goals(con,plan_id)
    updated=added=0
    for key,(subject,target) in proposed.items():
        if key in existing:
            # KEEP solved questions, target hours, worked hours, status, id.
            con.execute('UPDATE koc_hedef SET hedef_soru=? WHERE id=? AND plan_id=?',
                        (target,existing[key],plan_id))
            updated+=1
        else:
            con.execute('INSERT INTO koc_hedef(plan_id,ders_adi,hedef_soru,cozulen_soru,hedef_saat,calisilan_saat) VALUES(?,?,?,0,0,0)',
                        (plan_id,subject,target))
            added+=1
    return {'plan_id':plan_id,'updated':updated,'added':added,'retained':len(set(existing)-set(proposed))}

def get_or_create_week(con,student_id,week,end):
    _student(student_id)
    plan_id=_weekly_plan(con,student_id,week)
    if plan_id is not None: return plan_id,False
    cur=con.execute('INSERT INTO koc_plan(ogrenci_id,baslangic_tarihi,bitis_tarihi) VALUES(?,?,?)',
                    (student_id,week,end))
    return int(cur.lastrowid),True

def save_progress(con,student_id,plan_id,rows):
    """Atomic, ID-based, optimistic writes. All input is checked before writing."""
    _student(student_id)
    if type(plan_id) is not int or plan_id<=0:
        raise CoachingDataError('Hafta planı bulunamadı.')
    owner=con.execute('SELECT ogrenci_id FROM koc_plan WHERE id=?',(plan_id,)).fetchone()
    if owner is None or owner[0] != student_id:
        raise CoachingConflict('Seçilen haftalık plan başka öğrenciye ait veya silinmiş.')
    validated=[]; seen=set()
    for item in rows:
        rid=item.get('id')
        if type(rid) is not int or rid<=0 or rid in seen:
            raise CoachingDataError('Hedef satır kimliği eksik veya tekrar ediyor. Planı yeniden açınız.')
        seen.add(rid)
        current=( _whole(item.get('target'),'Hedef soru'), _whole(item.get('solved'),'Çözülen soru'),
                  _hours(item.get('target_hours'),'Hedef saat'), _hours(item.get('worked_hours'),'Çalışılan saat'))
        expected=item.get('expected')
        if not isinstance(expected,(tuple,list)) or len(expected)!=4:
            raise CoachingConflict('Önceki kayıt bilgisi yok; planı yeniden yükleyin.')
        previous=(_whole(expected[0],'Önceki hedef'),_whole(expected[1],'Önceki çözülen'),
                  _hours(expected[2],'Önceki hedef saat'),_hours(expected[3],'Önceki çalışılan saat'))
        validated.append((rid,current,previous))
    # first verify that no one has independently changed a row
    for rid,_,previous in validated:
        dbrow=con.execute('SELECT hedef_soru,cozulen_soru,hedef_saat,calisilan_saat FROM koc_hedef WHERE id=? AND plan_id=?',
                          (rid,plan_id)).fetchone()
        if dbrow is None or any(abs(float(a)-float(b))>1e-8 for a,b in zip(dbrow,previous)):
            raise CoachingConflict('Başka bir ekranda hedef güncellenmiş olabilir. Kayıp yaşamamak için veriler yeniden yüklensin.')
    for rid,values,_ in validated:
        con.execute('UPDATE koc_hedef SET hedef_soru=?,cozulen_soru=?,hedef_saat=?,calisilan_saat=? WHERE id=? AND plan_id=?',
                    (*values,rid,plan_id))
    return len(validated)

_HISTORY_SQL="""CREATE TABLE IF NOT EXISTS koc_gorusme_gecmis_v244 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL,
    ogrenci_id INTEGER NOT NULL,
    kayit_zamani TEXT NOT NULL,
    kaynak TEXT NOT NULL CHECK(kaynak IN ('legacy','manual')),
    notlar TEXT NOT NULL,
    FOREIGN KEY(plan_id) REFERENCES koc_plan(id) ON DELETE CASCADE,
    FOREIGN KEY(ogrenci_id) REFERENCES ogrenci(id) ON DELETE CASCADE
)"""

def _has_history(con):
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='koc_gorusme_gecmis_v244'").fetchone() is not None

def append_note(con,student_id,plan_id,new_text):
    _student(student_id)
    if not isinstance(new_text,str) or not new_text.strip():
        raise CoachingDataError('Boş görüşme notu arşive kaydedilmez.')
    if len(new_text)>250000:
        raise CoachingDataError('Görüşme notu çok uzun.')
    if type(plan_id) is not int or plan_id<=0:
        raise CoachingDataError('Geçerli hafta planı bulunamadı.')
    row=con.execute('SELECT notlar FROM koc_plan WHERE id=? AND ogrenci_id=?',(plan_id,student_id)).fetchone()
    if row is None:
        raise CoachingConflict('Öğrenci ve hafta eşleşmedi; not kaydı yapılmadı.')
    old=row[0] or ''
    con.execute(_HISTORY_SQL)
    con.execute('CREATE INDEX IF NOT EXISTS idx_koc_gorusme_v244_ogr ON koc_gorusme_gecmis_v244(ogrenci_id,plan_id,id)')
    last=con.execute('SELECT notlar FROM koc_gorusme_gecmis_v244 WHERE plan_id=? AND ogrenci_id=? ORDER BY id DESC LIMIT 1',
                     (plan_id,student_id)).fetchone()
    if old and (last is None or last[0] != old):
        con.execute('INSERT INTO koc_gorusme_gecmis_v244(plan_id,ogrenci_id,kayit_zamani,kaynak,notlar) VALUES(?,?,?,?,?)',
                    (plan_id,student_id,datetime.now(timezone.utc).isoformat(timespec='seconds'),'legacy',old))
    if old==new_text:
        # no duplicate for identical value; if legacy initially existed, it is archived
        return False
    con.execute('INSERT INTO koc_gorusme_gecmis_v244(plan_id,ogrenci_id,kayit_zamani,kaynak,notlar) VALUES(?,?,?,?,?)',
                (plan_id,student_id,datetime.now(timezone.utc).isoformat(timespec='seconds'),'manual',new_text))
    con.execute('UPDATE koc_plan SET notlar=? WHERE id=? AND ogrenci_id=?',(new_text,plan_id,student_id))
    return True

def note_history(con,student_id):
    """Read historical revisions; old-format weekly notes still returned."""
    _student(student_id)
    history=[]
    if _has_history(con):
        rows=con.execute("""SELECT h.id,h.plan_id,h.kayit_zamani,h.kaynak,h.notlar,p.baslangic_tarihi
                             FROM koc_gorusme_gecmis_v244 h
                             JOIN koc_plan p ON p.id=h.plan_id
                             WHERE h.ogrenci_id=? AND p.ogrenci_id=? ORDER BY h.id DESC""",
                         (student_id,student_id)).fetchall()
        for r in rows:
            history.append({'id':r[0],'plan_id':r[1],'date':r[5], 'created':r[2], 'source':r[3], 'notes':r[4], 'kind':'history'})
    archived_plan_ids={r['plan_id'] for r in history}
    for plan_id,date,raw in con.execute("""SELECT id,baslangic_tarihi,notlar FROM koc_plan
                                           WHERE ogrenci_id=? AND COALESCE(notlar,'')<>'' ORDER BY baslangic_tarihi DESC""",
                                        (student_id,)).fetchall():
        if plan_id not in archived_plan_ids:
            history.append({'id':None,'plan_id':plan_id,'date':date,'created':'', 'source':'legacy','notes':raw,'kind':'weekly'})
    return history
