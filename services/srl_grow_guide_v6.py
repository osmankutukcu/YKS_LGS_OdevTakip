# -*- coding: utf-8 -*-
"""Read-only pedagogy: optional SRL/GROW coaching prompts.

No student profile, scores, labels, inference or databases here. Prompts are
conversation starters, not psychological diagnoses or automatic homework orders.
"""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class Phase:
    key: str
    title: str
    aim: str
    questions: tuple[str, ...]
    next_step: str

PHASES = (
    Phase('R', '1 · Gerçeklik ve öz-yansıma',
          'Geçen haftayı öğrenciyle birlikte, mümkünse tarihli kanıtlara bakarak değerlendirin.',
          ('Geçen haftadan hangi hedef gerçekleşti? Hangi kayıttan bunu doğrulayabiliriz?',
           'Çalışırken sana gerçekten yardımcı olan yöntem neydi?',
           'Hangi soruda ya da görevde zorlandın? Sence bunun başka açıklamaları olabilir mi?',
           'Ödevlerin tamamlanması dışında konuyu anladığını gösteren bir örnek var mı?'),
          'Kayıtlı ödev ile bağımsız öğrenme ölçümünü ayrı değerlendirin.'),
    Phase('G', '2 · Hedefi netleştirme',
          'Öğrencinin seçtiği küçük, somut ve kontrol edilebilir hedefleri belirleyin.',
          ('Bu hafta en çok ilerlemek istediğin konu ya da soru tipi hangisi?',
           'Hedefe ulaştığını hangi bağımsız küçük yoklamayla anlayabiliriz?',
           'Bu hedefi günlük hayatına uygun hale getirmek için neyi küçültelim?'),
          'Tek bir puandan öğrencinin kaygısı veya bilişsel yükü hakkında teşhis koymayın.'),
    Phase('O', '3 · Seçenekler ve yöntem',
          'Stratejiyi öğretmen dikte etmeden öğrenciyle birlikte seçin.',
          ('Aynı konuya çalışmak için hangi iki farklı yöntemi deneyebiliriz?',
           'Yanlış soruları analiz etmek mi, kısa geri çağırma mı, yeni bir yoklama mı daha uygun?',
           'Bu planı zorlaştırabilecek hangi engel var, alternatifimiz ne olacak?'),
          'Yanlışların nedenini öğrencinin tek bir cevabından kesin sınıflandırmayın.'),
    Phase('W', '4 · İlk adım ve takip',
          'Uygulanabilir bir ilk adım ve ölçüm tarihi üzerinde anlaşın.',
          ('Görüşmeden sonra yapacağın ilk küçük adım ne ve ne zaman?',
           'Planın aksarsa daha küçük bir alternatif adımın ne olacak?',
           'Bir sonraki görüşmede hangi kanıta bakarak ilerlemeyi değerlendireceğiz?'),
          'Ödev atama ve haftalık plan değişiklikleri için mevcut onaylı araçları kullanın.'),
)

def phase(key: str) -> Phase:
    for item in PHASES:
        if item.key == key:
            return item
    raise ValueError('Bilinmeyen görüşme aşaması')


def append_prompt(existing: str, question: str, *, phase_key: str) -> str:
    """Returns an editable note; does NOT save anything or touch Qt/SQLite."""
    p = phase(phase_key)
    if question not in p.questions:
        raise ValueError('Seçim geçerli rehber sorularından biri değil')
    existing = (existing or '').rstrip()
    line = f'[{p.key} · {p.title.split(" · ",1)[1]}] {question}'
    if line in existing.splitlines():
        return existing
    return f'{existing}\n{line}'.strip() if existing else line
