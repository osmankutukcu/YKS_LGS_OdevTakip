"""Read-only, denominator-aware exam comparisons for the one-click coach.

Does not equate a net-score difference with a change in mastery. It cannot
control for test difficulty; even comparable observations require review.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from math import isfinite


def _cols(con, name):
    try:
        return {r[1] for r in con.execute(f'PRAGMA table_info({name})')}
    except Exception:
        return set()


def _day(raw):
    try:
        d = date.fromisoformat(str(raw)[:10])
        return d
    except (ValueError, TypeError):
        return None


def _num(value):
    try:
        number = float(value)
        return number if isfinite(number) else None
    except (TypeError, ValueError, OverflowError):
        return None


def compare_exam_records(con, student_id: int, *, as_of: date | None = None):
    """Return (notes, caveats), never inventing a question denominator.

    Different exam types and unequal complete question totals aren't paired.
    A legacy schema without blank counts yields *limited* comparison only.
    """
    today = as_of or date.today()
    sc, dc = _cols(con, 'deneme_sonuclari'), _cols(con, 'denemeler')
    required = {'id', 'ogrenci_id', 'deneme_id', 'ders_adi', 'net', 'dogru', 'yanlis'}
    if not required <= sc or not {'id', 'tarih'} <= dc:
        return [], ['Deneme karşılaştırması için gerekli sütunlar bulunamadı.']
    select = [f's.{k} AS {k}' for k in ('id', 'ders_adi', 'net', 'dogru', 'yanlis')]
    select += [f"{('s.bos' if 'bos' in sc else 'NULL')} AS bos",
               f"{('d.tur' if 'tur' in dc else 'NULL')} AS tur",
               'd.tarih AS tarih']
    sql = f"SELECT {', '.join(select)} FROM deneme_sonuclari s JOIN denemeler d ON d.id=s.deneme_id WHERE s.ogrenci_id=? ORDER BY d.tarih DESC,s.id DESC LIMIT 600"
    rows = con.execute(sql, (student_id,)).fetchall()
    by_course = defaultdict(list)
    skipped = {'invalid': 0, 'future': 0, 'duplicates': 0, 'mismatch': 0, 'incomplete': 0}
    for row in rows:
        item = dict(row)
        day = _day(item['tarih'])
        if day is None:
            skipped['invalid'] += 1
            continue
        if day > today:
            skipped['future'] += 1
            continue
        net, correct, wrong = (_num(item[k]) for k in ('net', 'dogru', 'yanlis'))
        blank = _num(item['bos'])
        if not item['ders_adi'] or net is None or correct is None or wrong is None or correct < 0 or wrong < 0:
            skipped['invalid'] += 1
            continue
        if blank is not None and blank < 0:
            skipped['invalid'] += 1
            continue
        # A field in the schema doesn't ensure every historical record was filled.
        denominator = correct + wrong + blank if blank is not None and 'bos' in sc else None
        if denominator is not None and denominator < 1:
            skipped['incomplete'] += 1
            continue
        item.update(day=day, net_value=net, question_count=denominator,
                    kind=str(item['tur'] or '').strip().casefold(),
                    subject=str(item['ders_adi']).strip().casefold())
        by_course[item['subject']].append(item)

    notes = []
    for course, sequence in by_course.items():
        # Varying test type -> no comparison across types. Compare most recent
        # applicable pair in same course/type, on distinct calendar days.
        newest = sequence[0]
        earlier = None
        for candidate in sequence[1:]:
            if candidate['day'] == newest['day']:
                skipped['duplicates'] += 1
                continue
            if newest['kind'] != candidate['kind']:
                skipped['mismatch'] += 1
                continue
            a, b = newest['question_count'], candidate['question_count']
            if a is not None and b is not None and a != b:
                skipped['mismatch'] += 1
                continue
            if (a is None) != (b is None):
                skipped['incomplete'] += 1
                continue
            earlier = candidate
            break
        if earlier is None:
            continue
        comparable = bool(newest['kind'] and newest['question_count'] is not None and earlier['question_count'] is not None)
        notes.append({'subject': newest['ders_adi'], 'latest_net': round(newest['net_value'], 2),
                      'previous_net': round(earlier['net_value'], 2),
                      'date': newest['day'].isoformat(), 'previous_date': earlier['day'].isoformat(),
                      'exam_type': newest['tur'] or 'belirsiz',
                      'question_count': int(newest['question_count']) if newest['question_count'] is not None else None,
                      'comparison_quality': 'uyumlu kayıt' if comparable else 'sınırlı ölçüm',
                      'basis': 'İki ayrı tarihli ders sonucu; sınav güçlüğü eşdeğerliği bilinmiyor'})
    notes.sort(key=lambda x: x['latest_net'] - x['previous_net'])
    caveats = []
    if skipped['mismatch']:
        caveats.append(f"{skipped['mismatch']} deneme çifti sınav türü/soru sayısı farkı nedeniyle karşılaştırılmadı.")
    if skipped['future'] or skipped['invalid'] or skipped['incomplete']:
        caveats.append('Eksik, hatalı, ileri tarihli veya soru sayısı bilinmeyen deneme kayıtları temkinli değerlendirildi.')
    if any(x['comparison_quality'] == 'sınırlı ölçüm' for x in notes):
        caveats.append('Bazı denemelerde soru sayısı veya tür bilinmediği için net kıyası yalnızca kontrol ipucudur.')
    return notes, caveats
