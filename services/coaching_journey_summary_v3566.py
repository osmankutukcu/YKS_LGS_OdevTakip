# -*- coding: utf-8 -*-
"""V3.5.66: render verified, read-only cycle information for Student 360.

This is presentation-only.  No diagnosis, no automatic homework assignment,
no student data writes and no claim that an intervention caused improvement.
"""
from __future__ import annotations

_KIND_LABELS = {
    'INTERVENTION_FOLLOWUP': 'Onaylı müdahale sonrası kontrol',
    'OPTIONAL_INDEPENDENT_CHECK': 'İsteğe bağlı bağımsız öğrenme kontrolü',
    'TARGETED_REVIEW': 'Hedefli kazanım incelemesi',
    'INDEPENDENT_RECHECK': 'Bağımsız yeniden ölçüm',
    'CLARIFY_OBSERVATION': 'Öğretmen gözlemini doğrulama',
    'SPACED_RETRIEVAL': 'Aralıklı hatırlama kontrolü',
}


def format_journey_summary(cycle: dict, student_id: int) -> str:
    """Fail closed; never attribute another student's content to the selected one."""
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('Doğrulanmış öğrenci gerekli')
    heading = 'AKADEMİK KOÇLUK DÖNGÜSÜ · GÜNCEL DEĞERLENDİRME'
    if (not isinstance(cycle, dict)
        or cycle.get('schema') != 'automatic_coaching_cycle_v3565'
        or cycle.get('student_id') != student_id
        or cycle.get('read_only') is not True
        or cycle.get('teacher_approval_required') is not True
        or cycle.get('auto_change_allowed') is not False
        or cycle.get('automatic_assignments') is not False
        or cycle.get('automatic_messages') is not False):
        return f'{heading}\nVeriler doğrulanamadı. Öğrenme düzeyi hakkında çıkarım yapılmadı.'
    state = cycle.get('state')
    if state == 'DATA_REVIEW':
        return f'{heading}\nÖnce öğrenci ve kanıt kaynakları kontrol edilmeli. Otomatik akademik yorum durduruldu.'
    if state == 'NO_PRIORITY':
        return (f'{heading}\nBugün güvenilir kaynaklarla yeni öncelikli kontrol önerisi belirlenmedi. '
                'Bu durum öğrenmenin kanıtlandığını göstermez.')
    if state != 'ACTION_SUGGESTED':
        return f'{heading}\nKoçluk özeti bu kayıt için doğrulanamadı.'
    steps = cycle.get('next_actions')
    if not isinstance(steps, list) or len(steps) > 3 or not steps:
        return f'{heading}\nÖneri listesi doğrulanamadı.'
    lines = [heading, f"Değerlendirme tarihi: {str(cycle.get('as_of') or '')[:10]}"]
    for step in steps:
        if (not isinstance(step, dict)
            or step.get('kind') not in _KIND_LABELS
            or step.get('read_only') is not True
            or step.get('teacher_approval_required') is not True
            or step.get('auto_assignment') is not False
            or step.get('auto_message') is not False):
            return f'{heading}\nÖneri güvenliği doğrulanamadı.'
        course = str(step.get('lesson') or '').strip()[:90]
        topic = str(step.get('topic') or '').strip()[:140]
        area = ' / '.join(x for x in (course, topic) if x)
        lines.append('• ' + _KIND_LABELS[step['kind']] + (f' — {area}' if area else ''))
        reason = str(step.get('reason') or '').strip()[:300]
        action = str(step.get('next_step') or '').strip()[:300]
        if reason:
            lines.append('  Gözlem: ' + reason)
        if action:
            lines.append('  Öğretmenin değerlendireceği adım: ' + action)
    lines.append('Not: Ödev tamamlanması öğrenmenin kanıtı değildir. Müdahalenin nedensel etkisi doğrulanmamıştır.')
    lines.append('Bu bilgiler öneridir; öğrenci kaydı değiştirilmedi, onay öğretmendedir.')
    return '\n'.join(lines)
