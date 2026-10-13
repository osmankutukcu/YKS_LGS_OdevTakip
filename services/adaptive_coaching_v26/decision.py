# -*- coding: utf-8 -*-
"""V26 salt-okunur karar katmanı.

Öğrenciye ait ödev/kanıt/süre sinyallerini bir araya getirir; hiçbir ödev,
koçluk kaydı veya öğrencinin durumunu güncellemez. Bunlar öğretmene yardım
eden kural tabanlı *öneriler*dir; öğrenme teşhisi veya risk puanı değildir.
"""
from __future__ import annotations

from datetime import date, timedelta
import sqlite3
from services.adaptive_coaching_v25 import engine

DONE = ('yapildi', 'tamam', 'tamamlandi', 'tamamlandı')


def has_v25_data(con):
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='adaptive_observation_v25'").fetchone() is not None


def _day(value):
    return engine._date(value)


def student_decisions(con, student_id, today=None, maximum=12):
    """Produce explainable per-student priorities, without any mutations.

    If V25 tables do not yet exist, return an explicit 'not measured' state
    rather than creating tables in Student 360's read-only connection.
    """
    sid = int(student_id)
    today = _day(today) or date.today()
    engine._student_exists(con, sid)
    if not has_v25_data(con):
        return {
            'student_id': sid, 'metrics': {}, 'status': 'Öğrenme ölçümü henüz başlatılmadı',
            'actions': [], 'warnings': ['V25 gözlem tabloları henüz oluşturulmamış; ödev tiklerinden başarı çıkarılamaz.'],
            'sources': ['Ödev kayıtları ölçüm değildir.'], 'evidence_count': 0,
        }
    from .context import student_context
    ctx = student_context(con, sid, today=today)
    topics = engine.student_topics(con, sid)
    blockers = engine.get_blockers(con, sid, limit=25)
    measured = [x for x in topics if x['attempts'] >= 5]
    now_blockers = [b for b in blockers if (_day(b['created_at']) is not None and
                    0 <= (today - _day(b['created_at'])).days <= 14)]
    actions = []
    def add(priority, category, title, reason, next_step, lesson='', topic='', source=''):
        actions.append({'priority': priority, 'category': category, 'title': title,
                        'reason': reason, 'next_step': next_step, 'lesson': lesson,
                        'topic': topic, 'source': source})
    for t in topics:
        subject = f"{t['lesson']} / {t['topic']}"
        last = t.get('last_observed_on') or t.get('coach_last_review')
        due = bool(last and today >= last + timedelta(days=engine.DEFAULTS['spacing_days'][engine._stage(t)]))
        if t['level'] == 'Hedefli destek':
            subskill = ', '.join(t.get('subskills', [])[:2])
            reason = (f"{t['observations']} tanılayıcı ölçüm; toplam {t['attempts']} soru, "
                      f"yaklaşık %{t['accuracy']} doğru. " + (f"Alt başlık: {subskill}." if subskill else
                      'Alt kazanım henüz ayrıştırılmamış.'))
            add(10, 'Hedefli destek', subject, reason,
                'Kavramı 5 dakikalık geri çağırma ile yokla; en fazla 5–8 tanılayıcı soru ve hata açıklaması iste.',
                t['lesson'], t['topic'], 'V25 tanılayıcı gözlemleri')
        elif t['attempts'] < 5 and t['legacy_tasks']:
            add(6, 'Ölçüm gerekli', subject,
                f"{t['done_count']} tamamlanan, {t['open_count']} açık ödev; "
                'bunlar öğrenme kanıtı değildir.',
                'Yeni kitabı otomatik ödevlendirme; 5–8 soruluk bağımsız yoklama veya kısa serbest hatırlama yap.',
                t['lesson'], t['topic'], 'Eski ödev + V25 gözlem sayısı')
        if due and t['observations']:
            days = (today - last).days
            add(7, 'Aralıklı tekrar', subject,
                f"Son ölçümden {days} gün geçti; tekrar zamanı tahmini, kişiye göre doğrulanmalı.",
                'Önce ipucusuz geri getirme, ardından başka konuyla karışık kısa değerlendirme planla.',
                t['lesson'], t['topic'], 'V25 ölçüm tarihi')
    if any(b['reason'] in ('İş yükü', 'Zaman yönetimi', 'Erteleme / motivasyon') for b in now_blockers):
        add(9, 'Yük dengeleme', 'Biriken görevi yeniden değerlendir',
            'Son 14 gün içinde koç tarafından yük/zaman tıkanıklığı kaydedilmiş.',
            'Ödev borcunu topluca devretme; öğretmenle kritik çekirdek görevleri seç, yeni yükü gerekirse azalt.',
            source='V25 tıkanıklık kayıtları')
    if not measured and topics:
        add(8, 'İlk tanılama', 'Öğrenme kanıtı oluştur',
            'Ödev geçmişi var fakat en az 5 soruluk güvenilir gözlem bulunmuyor.',
            'Bu hafta iki farklı günde kısa, bağımsız yoklama uygula; sonuçları alt kazanıma bağla.',
            source='Eski ödevler + V25 ölçüm sayısı')
    if not topics:
        add(4, 'Veri başlangıcı', 'İlk öğrenci görüşmesi',
            'Kayıtlı ödev konusu veya öğrenme gözlemi bulunamadı.',
            'Öğrencinin hedefini ve başlangıç konularını öğretmenle belirle; önce kısa tanılama yap.',
            source='Ödev geçmişi + koçluk kayıtları')
    # Stable ordering and bounded display keep this fast and predictable.
    actions.sort(key=lambda a: (-a['priority'], a['lesson'].casefold(), a['topic'].casefold(), a['category']))
    count = sum(t['observations'] for t in topics)
    warnings = ['Doğru/yanlış verileri tüm soru ve kazanımları temsil etmeyebilir.']
    if not count:
        warnings.insert(0, 'Öğrenme kanıtı yok: tamamlanan ödev oranı ile akademik öğrenme karıştırılmamalı.')
    status = ('Tanılayıcı başlangıç gerekli' if not measured else
              'Hedefli öğretmen müdahalesi öneriliyor' if any(t['level']=='Hedefli destek' for t in topics) else
              'İzleme ve aralıklı tekrar')
    return {
        'student_id': sid, 'status': status, 'actions': actions[:max(1, min(30, int(maximum)))],
        'evidence_count': count, 'warnings': warnings,
        'metrics': {'topics': len(topics), 'measured': len(measured),
                    'support': sum(t['level']=='Hedefli destek' for t in topics),
                    'without_evidence': sum(t['attempts'] < 5 for t in topics),
                    'open_homework_rows': sum(t['open_count'] for t in topics),
                    'recent_blockers': len(now_blockers)},
        'context':ctx,
        'sources': ['Ödev Takip (salt okunur)', 'V25 kazanım gözlemleri', 'V25 tıkanıklık kayıtları',
                    'V24 hedef analizi (öğretmen hedef kaydı)', 'Koçluk planı (plan verisi)'],
    }


def concise_summary(brief, n=3):
    """No diagnosis or made-up exam score; usable in Student 360 plain-text."""
    rows = ['ADAPTİF KOÇLUK / ÖĞRETMEN KARAR DESTEĞİ', brief['status']]
    ctx = brief.get('context') or {}
    if ctx:
        rows.extend([f"Hedef: {ctx.get('target','—')}", f"Koçluk: {ctx.get('coaching_plan','—')}"])
    m = brief['metrics']
    if m:
        rows.append(f"Ölçülen konu: {m['measured']} / {m['topics']} | "
                    f"Destek önerisi: {m['support']} | Yeni ölçüm gereken: {m['without_evidence']}")
    for item in brief['actions'][:n]:
        rows += [f"• {item['category']}: {item['title']}", f"  → {item['next_step']}"]
    rows.append('Öneriler öğretmen onayına tabidir. Ödev tikleri değişmez.')
    return '\n'.join(rows)


def institution_queue(con, *, today=None, limit=250):
    """Single batched SQL read; no N+1 per-student Python scans on the landing page.

    Queue is not an educational ranking or risk probability. It highlights
    missing evidence and observed support needs. Legacy homework is untouched.
    """
    day = _day(today) or date.today()
    cap = max(1, min(int(limit), 500))
    v25 = has_v25_data(con)
    # Snapshot student/task counts before considering optional V25 data.
    base_sql = '''SELECT s.id AS student_id, TRIM(COALESCE(s.ad,'') || ' ' || COALESCE(s.soyad,'')) AS name,
      COALESCE(h.open_rows,0) AS open_rows, COALESCE(h.done_rows,0) AS done_rows
      FROM ogrenci s
      LEFT JOIN (
        SELECT o.ogrenci_id AS sid,
        SUM(CASE WHEN LOWER(TRIM(COALESCE(o.durum,''))) IN ('yapildi','tamam','tamamlandi','tamamlandı') THEN 0 ELSE 1 END) AS open_rows,
        SUM(CASE WHEN LOWER(TRIM(COALESCE(o.durum,''))) IN ('yapildi','tamam','tamamlandi','tamamlandı') THEN 1 ELSE 0 END) AS done_rows
        FROM odev o INNER JOIN odev_kume k ON k.id=o.kume_id AND k.ogrenci_id=o.ogrenci_id
        GROUP BY o.ogrenci_id) h ON h.sid=s.id
      ORDER BY s.id'''
    rows = [dict(r) for r in con.execute(base_sql)]
    signals = {}
    if v25:
        # Efficient aggregation without joining the two optional tables (which would multiply rows).
        for r in con.execute('''SELECT student_id, COUNT(*) AS topics,
            SUM(CASE WHEN attempts>=5 THEN 1 ELSE 0 END) AS measured,
            SUM(CASE WHEN attempts>=5 AND correct_count*100 < attempts*65 THEN 1 ELSE 0 END) AS support,
            SUM(CASE WHEN last_seen<=? THEN 1 ELSE 0 END) AS old_observations
            FROM (SELECT student_id,lesson,topic, MAX(observed_on) AS last_seen,
                SUM(correct) AS correct_count, SUM(correct+wrong+blank) AS attempts
                FROM adaptive_observation_v25 GROUP BY student_id,lesson,topic)
            GROUP BY student_id''', ((day-timedelta(days=7)).isoformat(),)):
            signals[int(r['student_id'])] = dict(r)
    for row in rows:
        s = signals.get(row['student_id'], {})
        row.update(measured=int(s.get('measured') or 0),
                   support=int(s.get('support') or 0),
                   old_observations=int(s.get('old_observations') or 0),
                   topics_with_observation=int(s.get('topics') or 0))
        if row['support']:
            row['attention'] = 'Tanılayıcı destek'
        elif row['open_rows'] and row['measured'] == 0:
            row['attention'] = 'Ölçüm gerekli'
        elif row['old_observations']:
            row['attention'] = 'Tekrar kontrolü'
        else:
            row['attention'] = 'İzleme / başlangıç'
    # Presence of assignments alone never ranks a student as low mastery.
    weight = {'Tanılayıcı destek': 0, 'Ölçüm gerekli':1, 'Tekrar kontrolü':2, 'İzleme / başlangıç':3}
    rows.sort(key=lambda x: (weight[x['attention']], -x['support'], -x['open_rows'], x['name'].casefold(), x['student_id']))
    return {'students': rows[:cap], 'total_students': len(rows), 'has_observations': v25,
            'truncated': len(rows) > cap, 'as_of': day.isoformat()}
