# -*- coding: utf-8 -*-
"""Read-only 10/14 day schedule for the separate mobile PDF only.

The legacy _fetch_data (seven days) and all original dialogs remain untouched.
Repeating weekdays get unique date-qualified keys, so a second Monday cannot
overwrite the first Monday. No coach status guesses or student data updates.
"""
from __future__ import annotations

from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path
import sqlite3
from urllib.parse import quote

DAYS_TR=('Pazartesi','Salı','Çarşamba','Perşembe','Cuma','Cumartesi','Pazar')


def fetch_mobile_pdf_schedule_range(db_path, *, group_filter='Tümü', days_count=10, today=None):
    if type(days_count) is not int or days_count not in (7,10,14):
        raise ValueError('Desteklenen süreler 7, 10 veya 14 gündür.')
    today=today or date.today()
    if type(today) is not date:
        raise ValueError('Geçersiz başlangıç tarihi.')
    if not isinstance(group_filter,str) or len(group_filter)>128:
        raise ValueError('Grup seçimi geçersiz.')
    names=[]; schedule={}; day_index={}
    for i in range(days_count):
        d=today+timedelta(days=i)
        label=f'{DAYS_TR[d.weekday()]} {d:%d.%m}'
        names.append((d.isoformat(),label))
        schedule[label]=[]
        day_index[d.isoformat()]=label
    source=Path(db_path)
    if not source.is_file():
        raise FileNotFoundError('Ajanda veritabanı bulunamadı.')
    uri='file:'+quote(str(source.resolve()),safe='/:')+'?mode=ro'
    with closing(sqlite3.connect(uri, uri=True,timeout=5)) as db:
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA query_only=ON')
        db.execute('PRAGMA busy_timeout=4000')
        db.execute('BEGIN')
        try:
            fixed=db.execute('SELECT id,ad,soyad,ogr_tel,veli_tel1,kocluk_gunu,kocluk_saati,ana_grup '
                             'FROM ogrenci WHERE aktif=1 AND kocluk_gunu IS NOT NULL '
                             "AND kocluk_gunu != ''").fetchall()
            for r in fixed:
                if group_filter!='Tümü' and r['ana_grup']!=group_filter:
                    continue
                for iso,label in names:
                    if DAYS_TR[date.fromisoformat(iso).weekday()]!=r['kocluk_gunu']:
                        continue
                    schedule[label].append({
                        'oid':r['id'],'ad':f'{r["ad"] or ""} {r["soyad"] or ""}'.strip(),
                        'tel_ogr':r['ogr_tel'],'tel_veli':r['veli_tel1'],
                        'saat':r['kocluk_saati'] or '??:??','tip':'Görüşme',
                        'meta':{'lines':[],'notes':[], 'status':'normal'}})
            raw=db.execute('''
                SELECT k.id as kid, k.bitis_tarihi, o.id as oid,o.ad,o.soyad,
                  o.ogr_tel,o.veli_tel1,o.ana_grup,k.aciklama,
                  GROUP_CONCAT(COALESCE(os.ders,'') || '|' ||
                     COALESCE(os.kitap_ad,'') || '|' ||
                     COALESCE(os.konu_ad,'Genel'), '$$$') as icerik_raw
                FROM odev_kume k JOIN ogrenci o ON o.id=k.ogrenci_id
                LEFT JOIN odev os ON os.kume_id=k.id
                WHERE o.aktif=1 AND date(k.bitis_tarihi) BETWEEN date(?) AND date(?)
                GROUP BY k.id
                ''',(names[0][0],names[-1][0])).fetchall()
            # Aggregate multiple homework groups for one student / date, but
            # do not merge unrelated students merely because names match.
            seen={}
            for r in raw:
                iso=str(r['bitis_tarihi'] or '')[:10]
                label=day_index.get(iso)
                if not label or (group_filter!='Tümü' and r['ana_grup']!=group_filter):
                    continue
                sid=r['oid']
                entry_key=(iso,sid,r['kid']) if sid is None else (iso,sid)
                if entry_key not in seen:
                    ev={'oid':sid,'ad':f'{r["ad"] or ""} {r["soyad"] or ""}'.strip(),
                        'tel_ogr':r['ogr_tel'],'tel_veli':r['veli_tel1'],
                        'saat':'18:00', 'tip':'Teslim',
                        'meta':{'nice_date':date.fromisoformat(iso).strftime('%d.%m.%Y'),
                                'lines':[],'notes':[], 'status':'normal'}}
                    seen[entry_key]=ev
                    schedule[label].append(ev)
                ev=seen[entry_key]
                for item in str(r['icerik_raw'] or '').split('$$$'):
                    parts=item.split('|',2)
                    if len(parts)<3: continue
                    course,book,topic=[x.replace('_',' ').strip() for x in parts]
                    if topic=='Genel':topic=''
                    text=' - '.join(x for x in (course.title(),book.title(),topic) if x)
                    if text:ev['meta']['lines'].append(text)
                # Freeform teacher notes are not added to external messages.
            for label in schedule:
                schedule[label].sort(key=lambda x:(x.get('saat') or '',x.get('ad') or ''))
        finally:
            db.execute('ROLLBACK')
    return schedule,names
