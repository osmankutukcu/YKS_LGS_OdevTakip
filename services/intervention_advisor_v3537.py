# -*- coding: utf-8 -*-
"""V3.5.37 — non-writing intervention proposals based on verified local evidence.

Homework source ownership and plan validation are delegated to V3.5.36.
An exam delta is only a measurement-review prompt, never mastery diagnosis,
causality, risk score or automatic study assignment. No background sends.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from math import isfinite
import sqlite3

from services.academic_actions_v3536 import read_student_action_card


def _columns(con, name):
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone():
        return set()
    return {r[1] for r in con.execute('PRAGMA table_info("' + name + '")')}


def _score(value):
    try:
        n = float(value)
        return n if isfinite(n) else None
    except (TypeError, ValueError, OverflowError):
        return None


def read_comparable_exam_signals(con: sqlite3.Connection, student_id: int, *,
                                 today: date | None = None, max_signals: int = 3) -> dict:
    """Read modern deneme results for ONE verified student; never compare to legacy.

    A blank count of zero is ambiguous (SQLite's default may mean unknown), so
    such rows can't prove a comparable test denominator. The reported total
    is a recorded count, not independently certified official exam length.
    """
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('Verified student id required')
    day = today or date.today()
    if not isinstance(day, date):
        raise ValueError('Reference day required')
    if type(max_signals) is not int or not 1 <= max_signals <= 5:
        raise ValueError('max_signals out of range')
    ex_cols, sc_cols = _columns(con, 'denemeler'), _columns(con,'deneme_sonuclari')
    if not {'id','tarih','tur'} <= ex_cols or not {'id','ogrenci_id','deneme_id','ders_adi','net','dogru','yanlis','bos'} <= sc_cols:
        return {'state':'SOURCE_UNVERIFIED', 'signals': [], 'validated_rows':0,
                'excluded_rows':0, 'basis':'Deneme kaynak şeması eksik veya doğrulanamadı.'}
    rows = con.execute("SELECT d.id,d.tarih,d.tur,s.ders_adi,s.dogru,s.yanlis,s.bos,s.net "
          "FROM deneme_sonuclari s JOIN denemeler d ON d.id=s.deneme_id "
          "WHERE s.ogrenci_id=? ORDER BY d.tarih DESC,d.id DESC,s.id DESC LIMIT 500", (student_id,)).fetchall()
    by_key = defaultdict(list)
    invalid = 0
    for eid, raw_day, raw_kind, raw_course, c, w, b, net in rows:
        try: observed_day = date.fromisoformat(str(raw_day)[:10])
        except (ValueError, TypeError): observed_day = None
        kind, course = str(raw_kind or '').strip(), str(raw_course or '').strip()
        cs, ws, bs, ns = (_score(v) for v in (c,w,b,net))
        values=(cs,ws,bs,ns)
        if (observed_day is None or observed_day > day or not kind or not course
            or any(v is None for v in values) or any(v < 0 or not v.is_integer() for v in (cs,ws,bs))
            or bs <= 0 or cs+ws+bs <= 0 or ns > cs + 1e-6 or ns < -ws - 1e-6):
            invalid += 1
            continue
        denominator=int(cs+ws+bs)
        key=(kind.casefold(),course.casefold(),denominator)
        by_key[key].append((observed_day, int(eid), kind[:60], course[:80], round(ns,2), denominator))
    signals=[]
    for seq in by_key.values():
        seq.sort(key=lambda r:(r[0],r[1]),reverse=True)
        if len(seq)<2: continue
        # Two results from the same day are NOT independent measurements.
        latest=seq[0]
        earlier=next((x for x in seq[1:] if x[0] < latest[0]), None)
        if earlier is None: continue
        delta=round(latest[4]-earlier[4],2)
        signals.append({'course':latest[3], 'exam_type':latest[2],
                        'latest_date':latest[0].isoformat(),
                        'previous_date':earlier[0].isoformat(),
                        'latest_net':latest[4], 'previous_net':earlier[4],
                        'net_delta':delta, 'recorded_question_count':latest[5],
                        'measurement_only':True,
                        'evidence_quality':'SAME_TYPE_SUBJECT_RECORDED_COUNT',
                        'difficulty_equivalence_verified':False})
    signals.sort(key=lambda s:(s['net_delta'],s['latest_date'],s['course']))
    return {'state':'COMPARABLE_RECORDS' if signals else 'INSUFFICIENT_COMPARABLE',
            'signals':signals[:max_signals], 'validated_rows':sum(len(x) for x in by_key.values()),
            'excluded_rows':invalid, 'basis':('Aynı ders/tür ve kayıtlı soru sayısı; farklı tarihler. '
                      'Sınav güçlüğü eşdeğerliği veya konu kazanımı doğrulanmadı.'),
            'legacy_exams_merged':False, 'remote_verified':False}


def build_intervention_draft(con: sqlite3.Connection, student_id: int, *,
                             today: date | None = None, action_card: dict | None = None) -> dict:
    """Produce at most three reversible, teacher-facing review suggestions.

    When action_card is supplied it must belong to the exact requested student;
    this avoids re-scanning the cohort in already-running screen/assistant flows.
    Caller owns the SQLite read-only snapshot and UI thread/worker scheduling.
    """
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('Verified student ID is required')
    day=today or date.today()
    if not isinstance(day,date): raise ValueError('Invalid day')
    # An externally supplied precomputed card is never a substitute for
    # checking that this student is active in the current local read snapshot.
    if not con.execute('SELECT 1 FROM ogrenci WHERE id=? AND aktif=1',
                       (student_id,)).fetchone():
        raise ValueError('Student is not active in the current data source')
    card=action_card if action_card is not None else read_student_action_card(con,student_id,today=day)
    if (not isinstance(card,dict) or card.get('student_id') != student_id
        or card.get('as_of') != day.isoformat()):
        raise ValueError('Student ownership or reference date mismatch')
    basis={'student_id':student_id,'as_of':day.isoformat(),
           'requires_teacher_approval':True,'auto_change_allowed':False,
           'messages_sent':False,'assignments_created':False,'calendar_written':False,
           'remote_verified':False,'local_data_only':True,
           'not_learning_or_risk_diagnosis':True,
           'scope':'draft_for_teacher_not_automatic_prescription'}
    if card['state']=='LINK_REVIEW':
        return {**basis,'state':'DATA_REVIEW','exam':{'state':'WITHHELD','signals':[]},
                'recommendations':[{'type':'VERIFY_LINKS','subject':None,
                  'title':'Öğrenci ve ödev bağlantılarını doğrulayın',
                  'why':'Öğrenci–ödev ilişkisinde güvenlik tutarsızlığı bulundu.',
                  'teacher_next_step':'Denetim ekranındaki öğrenci/küme bağlarını kontrol edin.',
                  'recheck':'Bağlantı temizlenmeden akademik müdahale kararı vermeyin.',
                  'evidence':'Korunan kanonik ödev ilişki denetimi'}],
                'limitations':['Bu öğrenci için sınav ve ödevden akademik sonuç üretilmedi.']}
    homework=card['homework']
    if homework.get('state')=='LINK_REVIEW':
        raise ValueError('Blocked homework evidence cannot become advice')
    recs=[]
    overdue=homework.get('overdue_open_tasks')
    if type(overdue) is int and overdue>0:
        subject=str(homework.get('top_overdue_lesson') or 'Ders belirtilmemiş')[:80]
        recs.append({'type':'FOLLOWUP_OVERDUE','subject':subject,
             'title':f'{subject}: gecikmiş açık ödevi doğrula',
             'why':f'Öğrenciye bağlı {overdue} açık ödevin teslim tarihi geçmiş.',
             'teacher_next_step':'Öğrenciyle tamamlanma durumunu ve engelleri kontrol et; gerekirse kısa telafi öner.',
             'recheck':'Ödev durumunun doğrulandığı kaydı ve sonraki kontrol tarihini öğretmen belirlesin.',
             'evidence':'Yerel kanonik ödev satırları ve bağlı teslim tarihleri'})
    try:
        exam=read_comparable_exam_signals(con,student_id,today=day)
    except (sqlite3.Error,ValueError,TypeError,KeyError):
        exam={'state':'SOURCE_UNVERIFIED','signals':[], 'basis':'Sınav kayıtları okunamadı.'}
    # Threshold is a notification filter (>= 1 net), NOT statistical significance.
    for signal in exam['signals']:
        if signal['net_delta'] > -1.0: continue
        recs.append({'type':'REVIEW_EXAM_CHANGE','subject':signal['course'],
            'title':f"{signal['course']}: deneme sonucunu birlikte incele",
            'why':(f"Aynı tür ve kayıtlı soru sayısındaki iki denemede "
                   f"{signal['previous_net']:g} → {signal['latest_net']:g} net gözlendi. "
                   'Güçlük farkı veya ölçüm koşulları bilinmiyor.'),
            'teacher_next_step':('Hata türlerini ve ilgili kazanımları öğrenciyle incele; '
                                  'gerekirse konu kontrolü ve hedefli tekrar öner.'),
            'recheck':'Benzer kapsamda yeni ölçüm kaydedildiğinde yeniden karşılaştır.',
            'evidence':('Deneme sonuçları: '+signal['previous_date']+' / '+signal['latest_date'])})
        if len(recs)>=3: break
    plan=card.get('plan') or {}
    if len(recs)<3 and plan.get('state') in ('MISSING','NO_BLOCKS','CONFLICT'):
        recs.append({'type':'REVIEW_PLAN','subject':None,
              'title':'Haftalık koçluk planını kontrol et',
              'why':str(plan.get('summary') or 'Koçluk planı doğrulanamadı.')[:160],
              'teacher_next_step':'Çakışan veya eksik haftalık hedefleri öğrenciyle doğrula; gerekirse plan öner.',
              'recheck':'Güncellenmiş ve öğretmen tarafından onaylanmış planı yeniden gözden geçir.',
              'evidence':'Yerel koçluk planı kayıt durumu (gerçek takvim doğrulanmadı)'})
    limitations=['Ödev tamamlamak öğrenme kanıtı değildir.',
                 'Sınav net farklılığı konu eksikliğini, nedeni veya kazanımı kanıtlamaz.',
                 'Yeni ödev, WhatsApp gönderimi veya takvim kaydı otomatik yapılmaz.']
    if exam['state']!='COMPARABLE_RECORDS':
        limitations.append('Karşılaştırılabilir iki sınav ölçümü bulunamadı veya sınav kaynağı doğrulanamadı.')
    if card.get('global_coverage')!='OBSERVED' or card.get('state') in ('PARTIAL_COVERAGE','UNVERIFIED'):
        limitations.append('Yerel akademik kanıt kapsamı kısmi; eksik veri başarı anlamına gelmez.')
    if not recs:
        return {**basis,'state':'NO_VERIFIED_INTERVENTION','exam':exam,
                'recommendations':[],'limitations':limitations}
    return {**basis,'state':'DRAFT_REVIEW','exam':exam,
            'recommendations':recs[:3], 'limitations':limitations}
