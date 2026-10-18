# -*- coding: utf-8 -*-
"""V3.5.28: declarative, source-only registry of existing feature areas.

Presence is NOT proof that a feature works. No imports of feature modules,
Qt, databases or networks are performed here. All source paths are relative.
The protected forms are described but never modified.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Module:
    key: str
    label: str
    sources: tuple[str, ...]
    depends_on: tuple[str, ...] = ()
    protected: bool = False
    responsibility: str = ''


MODULES = (
    Module('student_records', 'Öğrenci kayıtları', ('ui/student_form.py', 'db.py'),
           responsibility='Öğrenci kimliği ve kayıt sistemi'),
    Module('homework', 'Ödev Takip', ('ui/homework_form.py', 'utils/checkbox_dispatch.py'),
           ('student_records',), True, 'Ödev seçimi, matris ve küme kayıtları'),
    Module('control', 'Ödev Kontrol', ('ui/odev_kontrol.py', 'utils/homework_integrity_v133.py'),
           ('homework',), True, 'Ödev durumu, tamamlanma ve geri alma'),
    Module('student360', 'Öğrenci 360', ('ui/student360_panel_v16.py', 'services/live_student_summary_v3.py'),
           ('student_records',), False, 'Öğrenci kanıtları ve gelişim özeti'),
    Module('coaching', 'Adaptif koçluk', ('ui/adaptive_coaching_dialog_v25.py', 'services/coach_evidence_v5.py'),
           ('student360',), False, 'Koçluk kanıt ve müdahaleleri'),
    Module('coach_assistant', 'Koç Asistanı', (
        'services/coach_assistant_v1/module_bridge_v264.py',
        'services/coach_assistant_v1/event_router_v267.py'),
        ('coaching',), False, 'Öğrenci kapsamlı modül koordinasyonu'),
    Module('wizard', 'Akıllı Ödev Sihirbazı', ('ui/smart_wizard_dialog.py', 'utils/wizard_integrity_v8.py'),
           ('homework', 'student360'), False, 'Önerinin denetlenip ödeve aktarılması'),
    Module('planner', 'Haftalık Planlayıcı', ('ui/weekly_plan.py', 'services/smart_calendar.py'),
           ('homework',), False, 'Zaman ve ödev dağılımı'),
    Module('exam', 'Deneme ve sınav', ('ui/trial_exam_manager.py', 'services/exam_data.py'),
           ('student_records',), False, 'Deneme kayıtları ve analiz kanıtı'),
    Module('targets', 'Hedef Analizi', ('ui/target_analysis_dialog.py', 'services/target_analysis_v24'),
           ('exam',), False, 'Hedef ve sonuçların yorumlanması'),
    Module('reports', 'Raporlama', ('ui/reports.py', 'services/portal_homework_v3526.py'),
           ('homework', 'control'), False, 'Ödev ve öğrenci raporları'),
    Module('messaging', 'WhatsApp İletişim', ('ui/mail_send_whatsapp.py', 'services/whatsapp_queue'),
           ('student_records',), False, 'İzinli bildirim, ulaşım ve kuyruk'),
    Module('web_pwa', 'Yerel Web / PWA', ('web_api', 'ui/web_access_dialog.py'),
           ('student_records',), False, 'Web erişimi ve çevrimdışı iş akışı'),
    Module('themes', 'Tema / Görünüm', ('ui/theme.py', 'ui/theme_special_v42.py'),
           responsibility='Tema ve görsel uyum'),
    Module('live_probe', 'Yerel değişiklik izleme', (
        'services/live_change_probe_v241.py', 'ui/live_change_bridge_v241.py'),
        ('student_records',), False, 'Dış SQLite commit değişikliklerini izler'),
)

_BY_KEY = {module.key: module for module in MODULES}
assert len(_BY_KEY) == len(MODULES), 'Duplicate feature key'


def validate_registry(root: Path) -> dict:
    """Only check declared paths and dependency cycles; no dynamic imports."""
    root = Path(root)
    problems = []
    modules = []
    for spec in MODULES:
        missing = tuple(name for name in spec.sources if not (root / name).exists())
        for dependency in spec.depends_on:
            if dependency not in _BY_KEY:
                problems.append('UNKNOWN_DEPENDENCY:' + spec.key + ':' + dependency)
        modules.append({
            'id': spec.key, 'title': spec.label, 'sources_present': not missing,
            'missing_sources': list(missing), 'dependencies': list(spec.depends_on),
            'protected_core': spec.protected,
            'runtime_tested': False, 'windows_uat': 'NOT_VERIFIED',
        })
    visiting, visited = set(), set()
    def walk(key: str):
        if key in visiting:
            problems.append('DEPENDENCY_CYCLE:' + key)
            return
        if key in visited:
            return
        visiting.add(key)
        for dependency in _BY_KEY[key].depends_on:
            if dependency in _BY_KEY:
                walk(dependency)
        visiting.remove(key)
        visited.add(key)
    for key in _BY_KEY:
        walk(key)
    if any(not item['sources_present'] for item in modules):
        problems.append('MISSING_MODULE_SOURCE')
    return {
        'catalog_count': len(modules),
        'source_present': sum(bool(m['sources_present']) for m in modules),
        'status': 'PASS' if not problems else 'REVIEW',
        'issues': sorted(set(problems)), 'modules': modules,
        'source_presence_is_runtime_proof': False,
    }


# The catalog contains relationships, not permission to mutate data.
# On database_unknown all modules may need to re-query; no student may be inferred.
_EVENT_IMPACT = {
    'homework': ('homework', 'control', 'student360', 'coaching', 'coach_assistant',
                 'wizard', 'planner', 'reports', 'web_pwa'),
    'control': ('homework', 'control', 'student360', 'coaching', 'coach_assistant',
                'planner', 'reports', 'web_pwa'),
    'student_profile': ('student_records', 'student360', 'coaching', 'coach_assistant',
                        'wizard', 'planner', 'reports', 'messaging', 'web_pwa'),
    'exam': ('exam', 'targets', 'student360', 'coaching', 'coach_assistant', 'reports'),
    'independent_measurement': ('student360', 'coaching', 'coach_assistant', 'targets'),
    'coaching_plan': ('coaching', 'coach_assistant', 'planner', 'student360', 'reports'),
}


def affected_modules(kind: str) -> tuple[str, ...]:
    if kind == 'database_unknown':
        return tuple(spec.key for spec in MODULES)
    if kind not in _EVENT_IMPACT:
        raise ValueError('Unknown event kind (cannot assume a safe refresh scope)')
    return _EVENT_IMPACT[kind]
