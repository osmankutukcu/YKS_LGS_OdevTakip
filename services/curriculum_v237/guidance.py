"""Teacher-first, read-only actions based on the *existing* V23.6 result."""
from dataclasses import dataclass

@dataclass(frozen=True)
class CoverageGuidance:
    needs_review: bool
    message: str
    action: str

def teacher_guidance(overview) -> CoverageGuidance:
    if overview is None:
        return CoverageGuidance(False, 'Konu listesi incelenebilir; öğrenci sonucu henüz hazır değil.', 'none')
    if overview.needs_attention:
        count = len(overview.problems)
        return CoverageGuidance(True,
            f'{count} konu eşleşme uyarısı var. Mevcut ödevleriniz korunuyor. '
            'Önce sorunlu konuyu inceleyin; düzeltme gerekirse mevcut Ders/Konu Düzenle ekranını kullanın.',
            'review_and_edit')
    total = overview.scoped_tasks.open_count
    if total:
        return CoverageGuidance(False,
            f'Konu kimlikleri uyumlu. Bu ders için ayrıca izlenen {total} açık özel ödev var. '
            'İsterseniz aşağıdaki Kapsama Özel Ödevler düğmesinden takip edebilirsiniz.',
            'scoped_tasks')
    return CoverageGuidance(False,
        'Konu listesinde uyuşmazlık yok; bir işlem yapmanız gerekmiyor. '
        'Yeni özel konu gerekirse aşağıdan oluşturabilirsiniz.', 'none')
