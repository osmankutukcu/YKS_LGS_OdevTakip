# -*- coding: utf-8 -*-
"""V29 next action advisor. A deterministic, read-only aid for the teacher.

Strict assumptions:
- Task completion, lack of completion and one-click notes are NOT mastery evidence.
- Notes identify hypotheses for conversation, not student traits or diagnoses.
- Never creates tables or writes legacy/new homework; never auto-assigns.
- Selected homework must belong both to the student and the selected cluster.
- Read bounded evidence and optional notes only when the teacher requests it.
"""
from __future__ import annotations
from datetime import date, timedelta

_REASONS = {
    'concept': ('Kavramı yeniden yokla',
        'Öğretmen konu/kazanımın anlaşılmadığını işaretlemiş.',
        'Önce öğrenciden kavramı kendi cümleleriyle açıklamasını isteyin; ardından 3–5 bağımsız tanılayıcı soru seçin.'),
    'time': ('Zaman baskısını ayırt et',
        'Öğretmen süreyle ilgili bir tıkanıklık bildirmiş.',
        'Kısa süreli ve süresiz 2–3 soruyu karşılaştırın. Hız sorunu ile kavram eksiğini ayırt etmeden ödev yükünü artırmayın.'),
    'attention': ('Hata yolunu birlikte kontrol et',
        'Öğretmen dikkat veya işlem hatası gözlemlemiş.',
        'Öğrenciye bir çözüm yolunu sesli açıklatın; işlem ve okuma hatalarını ayrı ayrı işaretleyin.'),
    'workload': ('İş yükünü sadeleştir',
        'Öğretmen ödev yükünün fazla geldiğini bildirmiş.',
        'Bitenleri yeniden vermeyin; kalanları kritik çekirdek / isteğe bağlı diye ayırıp haftalık süreye göre yeniden planlayın.'),
    'difficulty': ('Zorluğun kaynağını belirle',
        'Öğretmen zorlanma gözlemiş; neden kesin değil.',
        'Öğrenciye tek soruluk kısa görüşme yapın: kavram mı, zaman mı, soru dili mi? Ardından küçük yoklama planlayın.'),
    'ask': ('Öğrenciden bir cümlelik geri bildirim al',
        'Öğretmen nedenin öğrenciyle görüşülmesini istemiş.',
        '“En çok nerede takıldın?” sorusuyla kısa görüşme yapın; cevaba göre tek mikro görev seçin.'),
    'easy': ('Aktarımı yeni soruyla kontrol et',
        'Öğretmen çalışmanın kolay geldiğini gözlemiş.',
        'Benzer kazanımı farklı bağlamda ve ipucusuz kısa bir soruyla yoklayın; yalnızca kolay geldiği için seviye atlatmayın.'),
}


def _exists(con, name):
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _as_day(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _evidence(con, sid, lesson, topic, day):
    """Up to 16 newest observations for EXACT student, lesson and topic."""
    if not _exists(con, 'adaptive_observation_v25'):
        return []
    rows = con.execute('''SELECT correct,wrong,blank,subskill,mode,observed_on
        FROM adaptive_observation_v25 WHERE student_id=? AND lesson=? AND topic=?
          AND observed_on<=? ORDER BY observed_on DESC,id DESC LIMIT 16''',
        (sid, lesson, topic, day.isoformat())).fetchall()
    result = []
    for r in rows:
        total = int(r['correct'] or 0)+int(r['wrong'] or 0)+int(r['blank'] or 0)
        result.append({'correct':int(r['correct'] or 0), 'total':total,
                       'day':r['observed_on'], 'subskill':r['subskill'] or ''})
    return result


def _build(sid, homework_id, lesson, topic, homework_state, note, evidence, as_of):
    code = note.get('reason_code') if note else None
    title, why, next_step = _REASONS.get(code, (
        'Kısa öğrenme kontrolü yap',
        'Bu ödev için kayıtlı, doğrulanmış bir zorlanma nedeni bulunmuyor.',
        'Tamamlama tikinden sonuç çıkarmadan önce 3–5 bağımsız soru veya ipucusuz hatırlama uygulayın.'))
    attempts = sum(x['total'] for x in evidence)
    distinct_days = len({str(x['day'])[:10] for x in evidence if x['total']>=5})
    recent = evidence[0] if evidence else None
    context = []
    if homework_state.strip().lower() in ('yapildi','tamam','tamamlandi','tamamlandı'):
        context.append('Ödev tamamlandı işaretli; bu, öğrenmenin kanıtı değildir.')
    else:
        context.append('Ödev tamamlanmadı olarak görünüyor; bunun nedeni henüz kanıtlanmış değildir.')
    if recent:
        context.append(f"Son bağımsız ölçüm: {recent['correct']}/{recent['total']} doğru"
                       f" ({str(recent['day'])[:10]}); geçmişte {distinct_days} ayrı günde ≥5 soruluk ölçüm var.")
        if recent['total']>=5 and recent['correct']/max(1,recent['total'])<0.65:
            context.append('Son ölçüm düşük doğruluk içeriyor; öncelik kazanımın kısa tanılanması olmalı.')
        if recent.get('subskill'):
            context.append('Ölçülen alt başlık: '+str(recent['subskill'])[:100])
    else:
        context.append('Bu ders/konu için sayısal öğrenme ölçümü bulunamadı.')
    return {'student_id':sid, 'homework_id':homework_id, 'lesson':lesson,'topic':topic,
            'title':title,'reason':why,'next_step':next_step,'context':context,
            'teacher_note':code if code in _REASONS else None,
            'evidence_observations':len(evidence),'evidence_attempts':attempts,
            'as_of':as_of.isoformat(), 'approval_required':True,
            'warning':'Bu öneri otomatik ödev değildir; öğretmen değerlendirmesi gerekir.'}


def next_step_for_homework(con, student_id, homework_id, *, today=None):
    """Read-only recommendation for one explicitly selected row.

    Raises ValueError for a missing/wrong-owner homework; cannot leak names or notes.
    """
    sid, hid = int(student_id), int(homework_id)
    if sid <= 0 or hid <= 0:
        raise ValueError('Geçersiz öğrenci veya ödev seçimi.')
    day = _as_day(today) if today is not None else date.today()
    if day is None:
        raise ValueError('Tarih YYYY-AA-GG biçiminde olmalıdır.')
    row = con.execute('''SELECT o.ders,o.konu_ad,o.durum FROM odev o
        INNER JOIN odev_kume k ON k.id=o.kume_id AND k.ogrenci_id=o.ogrenci_id
        WHERE o.id=? AND o.ogrenci_id=?''',(hid,sid)).fetchone()
    if not row:
        raise ValueError('Ödev seçili öğrenciye ait değil veya bulunamadı.')
    lesson, topic = str(row['ders'] or '').strip(),str(row['konu_ad'] or '').strip()
    note = None
    if _exists(con,'adaptive_quick_note_v28'):
        found = con.execute('''SELECT reason_code,updated_at FROM adaptive_quick_note_v28
            WHERE student_id=? AND homework_id=? AND substr(updated_at,1,10)<=?
            LIMIT 1''',(sid,hid,day.isoformat())).fetchone()
        if found and _as_day(found['updated_at']) and (day-_as_day(found['updated_at'])).days<=30:
            note = dict(found)
    return _build(sid,hid,lesson,topic,row['durum'] or '',note,
                  _evidence(con,sid,lesson,topic,day),day)


def student_next_steps(con, student_id, *, today=None, limit=3):
    """Bounded recent teacher notes for optional summary. Never treats note as success.

    No table or no recent note -> empty array, not a fabricated risk score.
    """
    sid=int(student_id)
    if sid<=0 or not con.execute('SELECT 1 FROM ogrenci WHERE id=?',(sid,)).fetchone():
        raise ValueError('Öğrenci bulunamadı.')
    day=_as_day(today) if today is not None else date.today()
    if day is None:
        raise ValueError('Geçersiz tarih.')
    if not _exists(con,'adaptive_quick_note_v28'):
        return []
    cap=max(1,min(int(limit),5))
    since=(day-timedelta(days=14)).isoformat()
    notes=con.execute('''SELECT homework_id,lesson,topic,reason_code,updated_at
        FROM adaptive_quick_note_v28 WHERE student_id=?
          AND updated_at>=? AND updated_at<?
        ORDER BY updated_at DESC,id DESC LIMIT ?''',
        (sid,since, (day+timedelta(days=1)).isoformat(),cap)).fetchall()
    result=[]
    for n in notes:
        if n['reason_code'] not in _REASONS:
            continue
        # Deleted homework retains only the V28 observation history, no longer actionable row.
        if n['homework_id'] is None:
            continue
        row=con.execute('''SELECT o.durum FROM odev o JOIN odev_kume k
            ON k.id=o.kume_id AND k.ogrenci_id=o.ogrenci_id
            WHERE o.id=? AND o.ogrenci_id=? AND o.ders=? AND o.konu_ad=?''',
            (n['homework_id'],sid,n['lesson'],n['topic'])).fetchone()
        if row is None:
            continue
        result.append(_build(sid,int(n['homework_id']),n['lesson'],n['topic'],row['durum'] or '',
                             dict(n),_evidence(con,sid,n['lesson'],n['topic'],day),day))
    return result


def plain_text(result):
    """Portable presentation without dependencies on PyQt6 or UI state."""
    return (f"{result['lesson']} / {result['topic']}\n"
            f"Öneri: {result['title']}\n"
            f"Gerekçe: {result['reason']}\n"
            f"Sonraki adım: {result['next_step']}\n"
            + '\n'.join(result['context'])
            + '\n'+result['warning'])
