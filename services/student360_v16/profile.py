"""Optional status of a student's routine profile; never changes assignments."""
from services.plan_profile_store import load_assignments, load_profiles


def student_routine_status(student_id: int) -> str:
    try:
        assigned = load_assignments().get(str(student_id))
        if not assigned:
            return 'Haftalık rutin profili eşleştirilmemiş'
        profiles = load_profiles()
        if assigned not in profiles:
            return 'Eşleştirme var fakat profil bulunamıyor; kontrol gerekli'
        return 'Haftalık rutin profili eşleştirilmiş (takvim değiştirilmez)'
    except (OSError, ValueError, TypeError):
        return 'Rutin profili okunamadı; mevcut planı değiştirmeyin'
