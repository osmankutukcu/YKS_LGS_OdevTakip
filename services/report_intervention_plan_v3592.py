# -*- coding: utf-8 -*-
"""V3592: cautious, teacher-reviewed measurement planning, no diagnosis.

Pure interpreter of V3591's *typed* same-student evidence; performs no SQL,
network, writes, notifications, grading or automatic homework assignment.
"""
from __future__ import annotations
from dataclasses import dataclass

from services.report_academic_bridge_v3591 import AcademicEvidence


@dataclass(frozen=True)
class ReviewStep:
    heading: str
    instruction: str
    basis: str
    short: str  # concise text for fixed-size PDF layouts


@dataclass(frozen=True)
class ReviewPlan:
    level: str  # ölçüm var | önce doğrula | veri yetersiz
    steps: tuple[ReviewStep, ...]
    limitation: str


def plan_teacher_review(evidence: AcademicEvidence) -> ReviewPlan:
    """Return up to three ordered suggestions without deducing mastery.

    Source uncertainty takes priority over student-directed interventions.
    `exam_net` can be used to identify a measured *subject*, never to infer
    which topics were failed or to rank students.
    """
    if not isinstance(evidence, AcademicEvidence):
        raise TypeError('Yapılandırılmış akademik kanıt gerekli.')
    steps: list[ReviewStep] = []
    suspect = any(course.repeated_measurement or course.conflicting_topics
                  for course in evidence.courses)
    suspect = suspect or any(
        fragment in warning.casefold()
        for warning in evidence.warnings
        for fragment in ('hacmi denetim sınırını aşıyor', 'şeması bulunamadı',
                         'kesin ders koduyla eşleşmedi', 'iki farklı deneme',
                         'birden fazla ölçüm')
    )
    if suspect or evidence.status == 'doğrulanamadı':
        steps.append(ReviewStep(
            'Önce veriyi doğrula',
            'Deneme türü, öğrenci kimliği, mükerrer ölçüm ve konu işaretlerinin kaynağını kontrol edin.',
            'Belirsiz kayıtlar akademik eksiklik veya başarısızlık kanıtı değildir.',
            'Önce deneme kimliğini ve tekrarlanan/çelişkili kayıtları kontrol edin.'))

    valid = next((course for course in evidence.courses
                  if course.exam_net is not None and not course.repeated_measurement
                  and not course.conflicting_topics), None)
    if valid is not None and evidence.status != 'doğrulanamadı':
        steps.append(ReviewStep(
            'Ölçümü öğrenciyle incele',
            f'{valid.display_name} için {valid.exam_day:%d.%m.%Y} tarihli '
            'denemenin yanlış/boş sorularını öğrenciyle inceleyin; hangi konuyu '
            'yeniden ölçmek gerektiğini öğretmen belirlesin.',
            'Ders neti hangi kazanımın eksik olduğunu tek başına göstermez.',
            f'{valid.display_name}: yanlış/boş soruları inceleyip konu ölçümünü öğretmen seçsin.'))
        steps.append(ReviewStep(
            'Kısa kontrol ve yeniden ölçüm',
            'Öğretmenin seçtiği konu için kısa tanılayıcı sorular uygulayın. '
            'Yaklaşık bir hafta sonra aynı sınav türünde ve mümkünse eşit '
            'soru sayısı/kapsamında tekrar ölçüm yapın.',
            'İki sınavın güçlüğü doğrulanmadan net farkını kesin gelişim saymayın.',
            'Kısa kontrol soruları uygulayın; bir hafta sonra benzer kapsamda tekrar ölçün.'))
    elif not steps:
        steps.append(ReviewStep(
            'Önce ölçüm oluştur',
            'Öğrenciyle görüşüp uygun ders için tarihli, soru kapsamı belli '
            'bir ölçüm kaydedin; varsa öğretmen konu işaretlerini gözden geçirin.',
            'Bu döneme ait doğrulanmış ders ölçümü bulunmadı.',
            'Önce kapsamı ve tarihi belli bir ders ölçümü alın.'))

    if len(steps) > 3:
        steps = steps[:3]
    level = ('önce doğrula' if suspect or evidence.status == 'doğrulanamadı'
             else 'ölçüm var' if valid else 'veri yetersiz')
    return ReviewPlan(
        level, tuple(steps),
        'Bu adımlar öğretmen kontrolüne yöneliktir; otomatik tanı, '
        'ödev ataması, hedef değişikliği veya çalışma gerçekleşmesi iddiası değildir.')
