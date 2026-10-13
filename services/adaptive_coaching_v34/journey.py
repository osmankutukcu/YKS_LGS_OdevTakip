# -*- coding: utf-8 -*-
"""Unified coach-facing summary of already retrieved V25/V26/V28/V29 data.

Pure, bounded formatter: no SQLite, Qt, timers, file IO, schema creation or task
writes. The old homework table is still the sole source of assignment state.
Teacher notes express hypotheses, NOT measured mastery, risk, or diagnoses.
"""
from __future__ import annotations


def compose_journey(student_id, brief, quick_notes=(), next_steps=(), *, max_actions=3):
    """Build a cross-module learner journey for one selected student.

    Fail closed if a caller accidentally passes another learner's observations.
    Original arrays and their dictionaries remain unchanged.
    """
    sid = int(student_id)
    if sid <= 0 or int(brief.get('student_id') or 0) != sid:
        raise ValueError('Öğrenci özeti kimliği uyuşmuyor.')
    quick_notes = list(quick_notes or ())
    next_steps = list(next_steps or ())
    for item in quick_notes + next_steps:
        if int(item.get('student_id') or 0) != sid:
            raise ValueError('Öğretmen gözlemi farklı bir öğrenciye ait; gösterilemiyor.')

    evidence_count = max(0, int(brief.get('evidence_count') or 0))
    actions = list(brief.get('actions') or ())
    cap = max(1, min(int(max_actions), 5))
    metrics = brief.get('metrics') or {}
    n_measured = max(0, int(metrics.get('measured') or 0))
    if not evidence_count:
        evidence_label = 'Bağımsız öğrenme ölçümü yok'
        measurement_step = '3–5 bağımsız soruyla veya ipucusuz geri getirmeyle başlangıç yoklaması yap.'
    elif not n_measured:
        evidence_label = f'{evidence_count} gözlem var; yeterli konu ölçümü bulunmuyor'
        measurement_step = 'Aynı kazanımı farklı günlerde kısa bağımsız ölçümlerle yeniden yokla.'
    else:
        evidence_label = f'{evidence_count} gözlem · {n_measured} ölçülen konu'
        measurement_step = 'Sonuçları alt kazanım ve farklı günlerdeki tekrarlarla doğrula.'

    # The next-step advisor has already verified the current homework ownership.
    # Do not treat historic, detached V28 notes as active teacher assignments.
    seen = set()
    priorities = []
    for row in next_steps:
        key = (str(row.get('lesson') or '').strip().casefold(),
               str(row.get('topic') or '').strip().casefold())
        if key in seen:
            continue
        seen.add(key)
        priorities.append({'kind': 'Öğretmen gözleminden öneri',
                           'title': str(row.get('title') or 'Öğrenciyle görüş')[:160],
                           'topic': str(row.get('topic') or '')[:160],
                           'next_step': str(row.get('next_step') or '')[:500],
                           'source': 'V28 hızlı notu + V29 kural tabanlı değerlendirme'})
        if len(priorities) >= cap:
            break
    if len(priorities) < cap:
        for row in actions:
            key = (str(row.get('lesson') or '').strip().casefold(),
                   str(row.get('topic') or '').strip().casefold())
            if key != ('', '') and key in seen:
                continue
            if key != ('', ''):
                seen.add(key)
            priorities.append({'kind': str(row.get('category') or 'İzleme')[:100],
                               'title': str(row.get('title') or '')[:160],
                               'topic': str(row.get('topic') or '')[:160],
                               'next_step': str(row.get('next_step') or measurement_step)[:500],
                               'source': str(row.get('source') or 'V26 karar katmanı')[:120]})
            if len(priorities) >= cap:
                break
    if not priorities:
        priorities.append({'kind': 'Başlangıç', 'title': 'İlk öğrenme yoklaması', 'topic': '',
                           'next_step': measurement_step, 'source': 'Ölçüm durumu'})

    return {'student_id': sid, 'evidence_label': evidence_label,
            'measurement_needed': not bool(n_measured),
            'explicit_teacher_notes': len(quick_notes),
            'verified_next_steps': len(next_steps),
            'priorities': priorities,
            'teacher_approval_required': True,
            'assignment_state': 'Verilen Ödevler ve checkbox işlemleri eski sistem tarafından yönetilir.',
            'warning': ('Ödev tamamlanması ve öğretmen notu öğrenme kanıtı değildir. '
                        'Öneriler yalnızca öğretmen onayından sonra eski ödev aktarımına gider.')}


def journey_text(result):
    """Windows text-widget and report compatible representation."""
    lines = ['ÖĞRENME DÖNGÜSÜ · ÖĞRETMEN KARAR DESTEĞİ', result['evidence_label']]
    for row in result['priorities']:
        lines.extend([f"• {row['kind']}: {row['title']}",
                      f"  Sonraki adım: {row['next_step']}",
                      f"  Kaynak: {row['source']}"])
    lines.append(result['warning'])
    return '\n'.join(lines)
