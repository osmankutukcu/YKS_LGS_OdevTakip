"""Conservative, explainable coach prompts. They are not diagnoses."""
from .models import StudentOverview


def suggestions(data: StudentOverview) -> tuple[str, ...]:
    actions = []
    if data.homework_uncertainty:
        actions.append('Öncelik: çift/kopuk ödev kayıtlarını Denetim ekranında kontrol edin.')
    if data.homework_overdue:
        actions.append(f'{data.homework_overdue} gecikmiş açık ödevi öğrenciyle gözden geçirin.')
    if data.homework_sample == 0:
        actions.append('Ödev geçmişi yetersiz. Çalışılmadığı sonucuna varmayın.')
    elif data.homework_sample < 5:
        actions.append('Ödev sayısı az; tek haftalık yüzdelerle karar vermeyin.')
    if data.exam_evidence in ('Yok', 'Tek ölçüm'):
        actions.append('Denemelerde karşılaştırılabilir yeni bir ölçüm varsa ekleyin.')
    elif data.exam_evidence == 'Sınırlı karşılaştırma':
        actions.append('Denemeler arasındaki net farkını sınav güçlüğüyle birlikte değerlendirin.')
    if data.coaching_goals == 0:
        actions.append('Öğrenciye uygun, öğretmenin onaylayacağı küçük bir haftalık hedef belirleyin.')
    if data.tracked_topics == 0:
        actions.append('Konu Haritası kaydı yok; öğrenme düzeyini varsaymayın.')
    return tuple(actions[:4]) or ('Kayıtlarda acil kontrol gerekçesi belirlenmedi; mevcut düzeni izleyin.',)
