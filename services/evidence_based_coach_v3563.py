# -*- coding: utf-8 -*-
"""v3.5.63: research-aligned, cautious, read-only coaching card.

Uses the existing V3562 observed-data decision; never labels a student,
claims effect size/forgetting percentage, or acts without teacher approval.
"""
from __future__ import annotations
from datetime import date, datetime
import sqlite3
from services.learning_intervention_bridge_v3562 import read_learning_intervention_draft

SOURCES = {
 'DUNLOSKY_2013': {'title':'Dunlosky et al. (2013), Improving Students\' Learning with Effective Learning Techniques',
    'url':'https://www.psychologicalscience.org/journals/pspi/1529100612453266/', 'scope':'Araştırma derlemesi: alıştırma testleri ve dağıtılmış çalışma'},
 'IES_2007': {'title':'IES What Works Clearinghouse (2007), Organizing Instruction and Study',
    'url':'https://ies.ed.gov/ncee/wwc/PracticeGuide/1', 'scope':'Geri getirme testi, zaman aralığı, açıklama soruları'},
 'EEF_MSR_2025': {'title':'EEF (2025), Metacognition and Self-Regulated Learning guidance',
    'url':'https://educationendowmentfoundation.org.uk/education-evidence/guidance-reports/metacognition',
    'scope':'Planla, izle, değerlendir; öğretmen modellemesi'},
 'EEF_FEEDBACK_2021': {'title':'EEF (2021), Teacher Feedback to Improve Pupil Learning',
    'url':'https://educationendowmentfoundation.org.uk/education-evidence/guidance-reports/feedback',
    'scope':'Hedefe bağlı, zamanında ve uygulanabilir dönüt'},
}

# Each mapping is an educational *suggestion*, NOT a clinical/causal diagnosis.
STRATEGIES = {
 'TARGETED_REVIEW': {'strategy':'Hedefli geri bildirim + gecikmeli kısa yoklama',
   'activity':'Bir yanlış çözümü birlikte inceleyin; öğrenci çözüm nedenini açıklasın. Ardından farklı bir günde 5 yeni soruluk bağımsız kontrol planlayın.',
   'coach_question':'Bu soruda nerede takıldın? Yeni soruda hangi farklı adımı deneyeceksin?',
   'source_ids':('EEF_FEEDBACK_2021','IES_2007')},
 'CHECK_ERRORS': {'strategy':'Biçimlendirici kontrol + aktif hatırlama',
   'activity':'Öğrencinin yanlış türünü belirlemek için birkaç kısa soru sorun; aynı soruyu ezberletmeden bağımsız yeniden ölçün.',
   'coach_question':'Neden bu çözüm yolunu seçtin? Farklı bir soruda nasıl denersin?',
   'source_ids':('IES_2007','EEF_FEEDBACK_2021')},
 'CLARIFY_OBSERVATION': {'strategy':'Öz değerlendirme + öğretmen doğrulaması',
   'activity':'Öğretmen gözleminin olası açıklamasını öğrencinin çözümüyle karşılaştırın; mümkünse 5 soruluk kısa bir kontrol yapın.',
   'coach_question':'Çözümün hangi aşaması zor geldi ve bir sonraki denemede neyi değiştirebilirsin?',
   'source_ids':('EEF_MSR_2025','EEF_FEEDBACK_2021')},
 'SPACED_CHECK': {'strategy':'Aralıklı tekrar + geri getirme',
   'activity':'Önce kitaba bakmadan kısa bir hatırlama testi yapın. Sonuca göre sonraki tekrar zamanını öğretmen belirlesin.',
   'coach_question':'Kitaba bakmadan hangi kuralı açıklayabilirsin? Nerede daha fazla alıştırma gerekiyor?',
   'source_ids':('DUNLOSKY_2013','IES_2007')},
}
BLOCKED = frozenset({'DATA_REVIEW','SOURCE_REVIEW'})


def map_learning_to_evidence_card(learning: dict, *, student_id: int, today: date) -> dict:
    """Pure mapper, no database or external access; fail closed on bad payloads."""
    if type(student_id) is not int or student_id <= 0 or type(today) is not date:
        raise ValueError('Validated student/date required')
    if (not isinstance(learning, dict) or learning.get('schema') != 'learning_intervention_bridge_v3562'
        or learning.get('student_id') != student_id or learning.get('as_of') != today.isoformat()
        or learning.get('read_only') is not True or learning.get('auto_change_allowed') is not False):
        raise ValueError('Untrusted learning evidence')
    base = {'schema':'evidence_based_coach_v3563','student_id': student_id,
        'as_of':today.isoformat(),'read_only':True,'automatic_actions':False,
        'teacher_approval_required':True,'diagnosis':False,
        'scientific_effect_for_this_student_proven':False,
        'disclaimer':'Araştırmalar yöntemleri destekler; bu öğrenciye özel etki henüz ölçülmedi.',
        'source_quality':learning.get('source_quality'), 'cards':[]}
    if learning.get('state') in BLOCKED:
        return {**base,'state':'DATA_REVIEW','next_step':learning.get('next_step') or 'Kanıt kaynağını doğrulayın.'}
    if learning.get('state') not in ('REVIEW_SUGGESTED','NO_LEARNING_PRIORITY'):
        return {**base,'state':'UNVERIFIED','next_step':'Akademik kaynakları kontrol edin.'}
    if learning.get('state') == 'NO_LEARNING_PRIORITY':
        return {**base,'state':'NO_SUGGESTION','next_step':'Şimdilik yeni öğrenme kontrolü önerisi yok; bu, ustalık kanıtı değildir.'}
    original = learning.get('recommendations')
    if not isinstance(original, list):
        return {**base,'state':'UNVERIFIED','next_step':'Öneri kaynağı doğrulanamadı.'}
    used=set()
    cards=[]
    for item in original[:3]:
        if not isinstance(item, dict) or item.get('requires_teacher_approval') is not True or item.get('auto_assignment') is not False:
            return {**base,'state':'UNVERIFIED','next_step':'Öneri güvenlik alanları doğrulanamadı.'}
        kind = item.get('kind')
        rule = STRATEGIES.get(kind)
        lesson, topic = item.get('lesson'), item.get('topic')
        if rule is None or not isinstance(lesson,str) or not lesson.strip() or not isinstance(topic,str) or not topic.strip():
            return {**base,'state':'UNVERIFIED','next_step':'Öneri türü veya konusu doğrulanamadı.'}
        dedup_key=(lesson.strip().casefold(),topic.strip().casefold())
        if dedup_key in used: continue
        used.add(dedup_key)
        source_ids=rule['source_ids']
        cards.append({'kind':kind,'lesson':lesson[:90],'topic':topic[:140],
          'basis':str(item.get('basis') or '')[:160], 'observation':str(item.get('why') or '')[:280],
          'strategy':rule['strategy'], 'teacher_activity':rule['activity'],
          'reflection_question':rule['coach_question'],
          'suggested_check_on':item.get('suggested_check_on'),
          'references':[{'id':sid,**SOURCES[sid]} for sid in source_ids],
          'requires_teacher_approval':True,'auto_assignment':False})
    return {**base,'state':'REVIEW_SUGGESTED' if cards else 'NO_SUGGESTION',
       'next_step': cards[0]['teacher_activity'] if cards else 'Yeni öneri yok.', 'cards':cards}


def read_evidence_based_coach(con:sqlite3.Connection, student_id:int, *, today:date | None = None) -> dict:
    day = today if today is not None else date.today()
    if type(day) is not date: raise ValueError('today must be date')
    # All validation and student/homework ownership checks happen in V3562.
    learning = read_learning_intervention_draft(con, student_id, today=day)
    return map_learning_to_evidence_card(learning,student_id=student_id,today=day)
