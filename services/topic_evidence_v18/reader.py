"""Read-only bridge between homework, topic map, coaching, and course-level exams.

No schema creation, no writes, no fuzzy topic mapping, no learning diagnosis.
Main homework `odev` and its secondary `odev_satir` representation are not
added together when they share the same group: duplicates are explicitly noted.
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import replace
from datetime import date
import sqlite3
from .models import TopicEvidence, TopicEvidenceReport, LessonExamContext
from .advisor import advice

_DONE = {'tamam', 'tamamlandı', 'tamamlandi', 'bitti', 'yapıldı', 'yapildi', 'done'}
_IGNORE = {'iptal', 'iptal edildi', 'silindi', 'aktarıldı', 'aktarildi'}


def _key(a, b):
    lesson, topic = ' '.join(str(a or '').split()), ' '.join(str(b or '').split())
    if not lesson or not topic: return None
    return (lesson.casefold(), topic.casefold())


def _has(con, table, columns):
    if not con.execute('SELECT 1 FROM sqlite_master WHERE type=? AND name=?', ('table', table)).fetchone():
        return False
    return set(columns) <= {r[1] for r in con.execute(f'PRAGMA table_info("{table}")')}


def _rows(con, sql, params=()):
    cur = con.execute(sql, params)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def read_topic_evidence(con: sqlite3.Connection, student_id: int, *, as_of: date | None = None) -> TopicEvidenceReport:
    """Never create records; reject absent, inactive, or mismatched student IDs."""
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('Geçerli bir öğrenci kimliği seçin.')
    if not _has(con, 'ogrenci', {'id', 'ad', 'soyad'}):
        raise ValueError('Öğrenci tablosu bulunamadı.')
    cols = {r[1] for r in con.execute('PRAGMA table_info("ogrenci")')}
    active_sql = ', aktif' if 'aktif' in cols else ''
    student = con.execute('SELECT id, ad, soyad' + active_sql + ' FROM ogrenci WHERE id=?', (student_id,)).fetchone()
    if not student or (active_sql and student[3] == 0):
        raise ValueError('Öğrenci bulunamadı veya aktif değil.')
    name = ' '.join(str(x or '').strip() for x in student[1:3]).strip()
    buckets = defaultdict(lambda: dict(main_open=0, main_done=0, map_open=0, map_done=0, teacher=[]))
    labels = {}
    flags = defaultdict(set)
    warnings = []

    def add(lesson, topic, field, *, status=''):
        key = _key(lesson, topic)
        if key is None:
            warnings.append('Dersi veya konusu boş bir kayıt atlandı.')
            return
        labels.setdefault(key, (' '.join(str(lesson).split()), ' '.join(str(topic).split())))
        st = ' '.join(str(status or '').casefold().split())
        if st in _IGNORE: return
        if st in _DONE or st == 'tamamlandı':
            buckets[key][field + '_done'] += 1
        elif st in {'aktif', 'devam', 'bekliyor', 'açık', 'acik', 'eksik', 'beklemede'}:
            buckets[key][field + '_open'] += 1
        else:
            flags[key].add('Durumu tanınmayan ödev var; sayıma alınmadı.')

    # Main assignments use group ownership to protect against cross-student leaks.
    if _has(con, 'odev_kume', {'id','ogrenci_id'}):
        groups = {r['id'] for r in _rows(con, 'SELECT id, ogrenci_id FROM odev_kume WHERE ogrenci_id=?',(student_id,))}
        chosen_main = set()
        if _has(con, 'odev', {'kume_id','ogrenci_id','ders','konu_ad','durum'}):
            for r in _rows(con, 'SELECT kume_id, ders, konu_ad, durum FROM odev WHERE ogrenci_id=?',(student_id,)):
                gid = r['kume_id']
                if gid not in groups:
                    warnings.append('Ana ödevin küme/öğrenci bağlantısı uyumsuz, atlandı.'); continue
                chosen_main.add(gid)
                add(r['ders'], r['konu_ad'], 'main', status=r['durum'])
        if _has(con, 'odev_satir', {'kume_id','ogrenci_id','ders','konu','durum'}):
            for r in _rows(con, 'SELECT kume_id, ders, konu, durum FROM odev_satir WHERE ogrenci_id=?',(student_id,)):
                gid = r['kume_id']
                if gid not in groups:
                    warnings.append('İkincil ödevin küme/öğrenci bağlantısı uyumsuz, atlandı.'); continue
                if gid in chosen_main:
                    warnings.append('Aynı ödev kümesi iki kaynakta var; ikincil satır ayrıca sayılmadı.')
                    continue
                add(r['ders'],r['konu'],'main',status=r['durum'])

    if _has(con,'odev_takip',{'ogrenci_id','ders_adi','konu_adi','durum'}):
        for r in _rows(con, 'SELECT ders_adi, konu_adi, durum FROM odev_takip WHERE ogrenci_id=?',(student_id,)):
            add(r['ders_adi'],r['konu_adi'],'map',status=r['durum'])

    if _has(con,'koc_konu_takip',{'ogrenci_id','ders_adi','konu_adi','durum'}):
        cols = {r[1] for r in con.execute('PRAGMA table_info("koc_konu_takip")')}
        optional = [x for x in ('hakimiyet_puani','koc_notu') if x in cols]
        for r in _rows(con, 'SELECT ders_adi, konu_adi, durum' + ''.join(', ' + x for x in optional) + ' FROM koc_konu_takip WHERE ogrenci_id=?',(student_id,)):
            key = _key(r['ders_adi'],r['konu_adi'])
            if key is None:
                warnings.append('Dersi veya konusu boş bir koçluk işareti atlandı.'); continue
            labels.setdefault(key, (' '.join(str(r['ders_adi']).split()), ' '.join(str(r['konu_adi']).split())))
            buckets[key]['teacher'].append(r)

    # V19: explicit teacher-reviewed question-to-topic evidence. Never infer
    # topic from aggregate exam scores. No writes in this reader.
    if _has(con, 'soru_konu_kanit_v19',
            {'deneme_id','ogrenci_id','ders_adi','konu_adi','soru_no','sonuc','kazanim_kodu'}):
        rows=_rows(con, '''SELECT q.deneme_id,q.ders_adi,q.konu_adi,q.soru_no,q.sonuc,q.kazanim_kodu
          FROM soru_konu_kanit_v19 q
          WHERE q.ogrenci_id=? AND EXISTS (
              SELECT 1 FROM deneme_sonuclari ds JOIN denemeler d ON d.id=ds.deneme_id
              WHERE ds.deneme_id=q.deneme_id AND ds.ogrenci_id=q.ogrenci_id
                AND ds.ders_adi=q.ders_adi)
          ORDER BY q.deneme_id,q.soru_no''',(student_id,))
        for r in rows:
            key=_key(r['ders_adi'],r['konu_adi'])
            if key is None:
                warnings.append('Ders/konusu boş soru bağlantısı atlandı.');continue
            labels.setdefault(key,(' '.join(str(r['ders_adi']).split()),
                                   ' '.join(str(r['konu_adi']).split())))
            if r['sonuc'] not in ('dogru','yanlis','bos'):
                flags[key].add('Bilinmeyen soru sonucu, sayılmadı.');continue
            b=buckets[key]
            b.setdefault('question_'+r['sonuc'],0)
            b['question_'+r['sonuc']]+=1
            if r['kazanim_kodu']:
                b.setdefault('outcomes',set()).add(str(r['kazanim_kodu']))
        # Invalid references are not silently converted to evidence.
        invalid=con.execute('''SELECT COUNT(*) FROM soru_konu_kanit_v19 q
          WHERE q.ogrenci_id=? AND NOT EXISTS (
              SELECT 1 FROM deneme_sonuclari ds
              JOIN denemeler d ON d.id=ds.deneme_id
              WHERE ds.deneme_id=q.deneme_id AND ds.ogrenci_id=q.ogrenci_id
                AND ds.ders_adi=q.ders_adi)''',(student_id,)).fetchone()[0]
        if invalid: warnings.append(f'{invalid} soru eşlemesi artık geçerli sınav sonucuna bağlı değil, kanıta alınmadı.')

    topic_rows = []
    for key in sorted(buckets):
        b = buckets[key]; teacher = b['teacher']
        duplicated = max(0,len(teacher)-1)
        state = score = None; note = ''
        if len(teacher) == 1:
            row = teacher[0]
            try: state = int(row['durum']) if row['durum'] is not None else None
            except (ValueError, TypeError): flags[key].add('Koçluk durumu geçersiz.')
            if row.get('hakimiyet_puani') is not None:
                try: score = int(row['hakimiyet_puani'])
                except (ValueError,TypeError): flags[key].add('Koçluk puanı okunamadı.')
            note = str(row.get('koc_notu') or '')
        elif duplicated:
            flags[key].add('Aynı ders/konu için çoklu koçluk işareti var; hâkimiyet tekilleştirilemedi.')
        lesson, topic = labels[key]
        row = TopicEvidence(lesson,topic,b['main_open'],b['main_done'],b['map_open'],b['map_done'],
                            state,score,note,duplicated,' '.join(sorted(flags[key])))
        row=replace(row,question_correct=b.get('question_dogru',0),
                    question_wrong=b.get('question_yanlis',0),question_blank=b.get('question_bos',0),
                    outcome_codes=tuple(sorted(b.get('outcomes',()))))
        recommendation=advice(row)
        if row.question_wrong or row.question_blank:
            recommendation+=' Öğretmen onaylı soru eşlemesinde yanlış/boş var; kısa konu kontrolü düşünülebilir.'
        topic_rows.append(replace(row,recommendation=recommendation))

    # Course-level only: NEVER attach these scores to a specific topic.
    exam_context = []
    try:
        from services.performance_coaching_v15 import _load_exam_rows
        exam_rows, sources, rejected = _load_exam_rows(con, as_of or date.today(), {student_id})
        if rejected:
            warnings.append('Bazı deneme sonuçları doğrulama dışı bırakıldı.')
        grouped = defaultdict(list)
        for obs in exam_rows.get(student_id,[]):
            grouped[' '.join(str(obs.subject).split()).casefold()].append(obs)
        for lesson_key, items in sorted(grouped.items()):
            # Both sources can contain an independent record; do not infer unique exams.
            latest = max(items,key=lambda x:(x.day,x.exam_id))
            exam_context.append(LessonExamContext(str(latest.subject),len(items),
                                f'Son kayıt: {latest.day.isoformat()} / {latest.kind} / {latest.net:g} net'))
        if len(sources.get(student_id,()))>1:
            warnings.append('Denemeler eski ve yeni şemada bulunuyor; eşdeğerlik doğrulanmadan birleştirmeyin.')
    except (sqlite3.Error,ValueError) as exc:
        warnings.append('Ders düzeyindeki denemeler okunamadı: ' + str(exc))

    return TopicEvidenceReport(student_id,name,tuple(topic_rows),tuple(exam_context),tuple(dict.fromkeys(warnings)))
