# -*- coding: utf-8 -*-
"""V3.5.85: read-only, student-ID-scoped report bridge for existing weekly plans.

Never guesses a student's profile by name, creates a timetable, or writes planner
state. Legacy/shared templates and approved snapshots are labeled precisely.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from services.plan_profile_store import load_assignments, load_profiles
from services.plan_replanner import load_approved
from services.planning_constraints import availability_for_week


@dataclass(frozen=True)
class PlannerSource:
    value: str
    scope: str
    status: str  # kayıt | eksik | doğrulanamadı
    warning: str = ''


@dataclass(frozen=True)
class PlannerEvidence:
    routine: PlannerSource
    approved_plan: PlannerSource


def _invalid(msg: str, *, warning: str = '') -> PlannerSource:
    return PlannerSource(msg, 'Yalnızca doğrulanmış öğrenci ID eşleştirmeleri okunur',
                         'doğrulanamadı', warning)


def _valid_count(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 1_000_000:
        raise ValueError(f'{label} geçersiz.')
    return value


def read_planner_evidence(student_id: int, *, reference_day: date | None = None) -> PlannerEvidence:
    """Read only the selected student's explicit routine assignment and hashed plan.

    The weekly profile describes constraints, not an audited attendance or a
    currently valid printed PDF. An approved snapshot reflects a past save,
    not proof that the original tasks are still the same.
    """
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('Geçersiz öğrenci kimliği.')
    today = reference_day or date.today()
    if not isinstance(today, date):
        raise ValueError('Referans tarihi geçersiz.')

    try:
        assignments = load_assignments()
        if not isinstance(assignments, dict):
            raise ValueError('Eşleşmeler geçersiz.')
        profile_name = assignments.get(str(student_id))
        if not profile_name:
            routine = PlannerSource('Bu öğrenciye atanmış haftalık rutin profili bulunamadı.',
                                    'Öğrenci ID eşleştirmesi yok; varsayılan veya isim benzerliğine göre profil seçilmez',
                                    'eksik')
        elif not isinstance(profile_name, str):
            routine = _invalid('Öğrenciye ait profil anahtarı doğrulanamadı.')
        else:
            profiles = load_profiles()
            if not isinstance(profiles, dict):
                raise ValueError('Profil kayıtları geçersiz.')
            profile = profiles.get(profile_name)
            if not isinstance(profile, dict):
                routine = _invalid('Profil eşleştirmesi var ancak profil dosyasında karşılığı yok.')
            elif profile.get('planner_version') != 2:
                routine = _invalid('Eski/uyumsuz profil; haftalık rutin özeti oluşturulmadı.')
            elif profile.get('_session_advisor_owner') is not None and str(profile['_session_advisor_owner']) != str(student_id):
                routine = _invalid('Eşleşen profil başka öğrenciye ait görünüyor; kullanılmadı.',
                                   warning='Haftalık profil sahipliği uyuşmuyor; planlayıcıdan eşleştirmeyi kontrol edin.')
            else:
                try:
                    windows = availability_for_week(profile)
                    max_day = _valid_count(profile.get('max', 180), 'Günlük limit')
                    if not 30 <= max_day <= 720:
                        raise ValueError('Günlük çalışma limiti beklenen aralığın dışında.')
                    eligible = sum(1 for intervals in windows.values() if any(b > a for a, b in intervals))
                    shared = sum(1 for val in assignments.values() if val == profile_name) > 1
                    session = 'Etüt oturumu etkin değil'
                    if profile.get('session_enabled'):
                        minutes = _valid_count(profile.get('session_minutes', 45), 'Etüt süresi')
                        if not 15 <= minutes <= 180:
                            raise ValueError('Etüt süresi beklenen aralığın dışında.')
                        session = f'Planlı etüt oturumu: {minutes} dk'
                    label = 'Paylaşılan rutin şablonu' if shared else 'Öğrenciye açıkça atanmış rutin profili'
                    routine = PlannerSource(
                        f'{label}. Aday çalışma aralığı bulunan gün: {eligible}/7; '
                        f'günlük çalışma üst sınırı: {max_day} dk; {session}.',
                        'Haftalık Planlayıcı V2, öğrenci ID ile ilişkilendirilmiş kayıt; '
                        'uygun aralıklar gerçek çalışma, gerçekleşen katılım veya onaylanmış PDF kanıtı değildir',
                        'kayıt')
                except (ValueError, TypeError, KeyError, OverflowError):
                    routine = _invalid('Profilin zaman kuralları geçersiz; hatalı saat bilgisi gösterilmedi.',
                                       warning='Haftalık rutin kuralları yeniden kontrol edilmeli.')
    except (OSError, ValueError, TypeError, UnicodeError, OverflowError):
        routine = _invalid('Haftalık profil/eşleştirme dosyası okunamadı; profil tahmin edilmedi.',
                           warning='Rutin dosyası okunamadı; öğrenci eşleştirmesi kontrol edilmeli.')

    try:
        snapshot = load_approved(student_id)
        if snapshot is None:
            approved = PlannerSource('Bu öğrenciye ait kayıtlı onaylı plan özeti bulunamadı.',
                                     'Öğrenci ID anahtarıyla ayrı tutulan onaylı plan taslakları', 'eksik')
        elif not isinstance(snapshot, dict) or snapshot.get('schema') != 1:
            approved = _invalid('Onaylı plan özeti eski veya geçersiz biçimde.')
        else:
            stamp = snapshot.get('created_on')
            created = date.fromisoformat(stamp) if isinstance(stamp, str) else None
            if created is None or created > today:
                raise ValueError('Onaylı plan tarihi geçersiz veya gelecekte.')
            units = _valid_count(snapshot.get('work_units'), 'Görev birimi')
            placed = _valid_count(snapshot.get('placed_minutes'), 'Yerleştirilen süre')
            pending = _valid_count(snapshot.get('pending_minutes'), 'Yerleşmeyen süre')
            if not isinstance(snapshot.get('placed'), list) or not isinstance(snapshot.get('pending'), dict):
                raise ValueError('Onaylı plan içeriği geçersiz.')
            stale = (today - created).days > 7
            approved = PlannerSource(
                f'Kayıt tarihi: {created:%d.%m.%Y}; plan birimi: {units}; '
                f'yerleştirilen: {placed} dk; yerleşmeyen: {pending} dk.' +
                (' Kayıt 7 günden eski; güncel plan olarak yorumlanmamalı.' if stale else ''),
                'Öğrenci ID anahtarlı onaylı haftalık plan taslağı; '
                'ödevlerin bugün de aynı olduğu veya plana uyulduğu doğrulanmaz',
                'kayıt',
                'Onaylı plan 7 günden eski; güncelliğini planlayıcıda kontrol edin.' if stale else '')
    except (OSError, ValueError, TypeError, OverflowError, KeyError):
        approved = _invalid('Onaylı haftalık plan kaydı okunamadı veya doğrulanamadı.',
                            warning='Onaylı haftalık plan kaydı kontrol edilmeli.')
    return PlannerEvidence(routine, approved)
