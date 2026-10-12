"""Cautious rules for teacher review; no claims of proven mastery."""
from .models import TopicEvidence


def advice(t: TopicEvidence) -> str:
    if t.source_warning:
        return 'Kaynak kayıtlarını doğrulayın; belirsiz satırlara dayanarak yeni ödev üretmeyin.'
    if t.main_open or t.map_open:
        return f'Açık çalışma var ({t.main_open + t.map_open} kayıt); öğrenciyle durumu kontrol edin.'
    if t.teacher_state is not None and t.teacher_state == 2:
        return 'Öğretmen bitirdi olarak işaretlemiş; öğrenmeyi gerekiyorsa kısa bir ölçmeyle doğrulayın.'
    if t.main_done or t.map_done:
        return 'Çalışma tamamlanmış; konu hâkimiyeti için bağımsız ölçüm gereklidir.'
    if t.teacher_state is not None:
        return 'Öğretmen konu takip işareti var; yeni ölçüm olmadan eksik/öğrenildi demeyin.'
    return 'Bu konu için yeterli bireysel kayıt bulunmuyor; gerekiyorsa kısa ölçme planlayın.'
