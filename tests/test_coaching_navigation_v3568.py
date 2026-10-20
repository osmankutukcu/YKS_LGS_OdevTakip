"""Stage9 pure routing and existing-menu acceptance tests; no PyQt or student DB."""
from __future__ import annotations
from datetime import date, timedelta
from pathlib import Path
from services.coaching_navigation_v3568 import recommended_existing_targets
from tests.test_context_integrations_v2 import Form, Menu, CENTERS
from ui.homework_context_integrations_v2 import install_existing_centers

DAY = date(2026,10,20)


def valid_cycle():
    return {'schema': 'automatic_coaching_cycle_v3565', 'student_id': 14,
        'as_of': DAY.isoformat(), 'state': 'ACTION_SUGGESTED', 'read_only': True,
        'teacher_approval_required': True, 'auto_change_allowed': False,
        'automatic_assignments': False, 'automatic_messages': False,
        'homework_is_not_mastery': True, 'mastery_verified': False,
        'causality_verified': False, 'next_actions': [{
            'kind': 'TARGETED_REVIEW', 'lesson': 'Matematik', 'topic': 'Polinomlar',
            'reason': 'Ölçüm gerekir', 'next_step': 'Kısa kontrol',
            'priority': 1, 'read_only': True, 'teacher_approval_required': True,
            'auto_assignment': False, 'auto_message': False,
            'mastery_verified': False, 'causality_verified': False}]}


def valid_alignment():
    return {'schema': 'science_wizard_alignment_v3564', 'student_id': 14,
        'as_of': DAY.isoformat(), 'state': 'MATCHED', 'read_only': True,
        'teacher_approval_required': True, 'auto_assignment': False,
        'auto_selection': False, 'requires_live_matrix_recheck': True,
        'existing_wizard_unchanged': True,
        'matched': [{'lesson': 'Matematik', 'topic': 'Polinomlar',
            'existing_book': 'AYT 1', 'minutes': 20,
            'teacher_must_review_in_existing_wizard': True,
            'automatic_transfer': False}]}


def test_pure_targets_require_verified_student_date_and_read_only():
    routes = recommended_existing_targets(14,DAY,cycle=valid_cycle(),alignment=valid_alignment())
    assert [x['key'] for x in routes] == ['learning', 'wizard']
    assert all(x['student_id'] == 14 and x['read_only'] for x in routes)
    assert recommended_existing_targets(22,DAY,cycle=valid_cycle(),alignment=valid_alignment()) == ()
    assert recommended_existing_targets(14,DAY + timedelta(days=1),cycle=valid_cycle(),alignment=valid_alignment()) == ()
    assert recommended_existing_targets(True,DAY,cycle=valid_cycle()) == ()
    assert recommended_existing_targets(14,'2026-10-20',cycle=valid_cycle()) == ()


def test_unsafe_cycle_and_wizard_not_presented():
    for field, value in [('automatic_messages', True), ('automatic_assignments', True),
                         ('mastery_verified', True), ('student_id', True),
                         ('as_of', '2026-10-19')]:
        bad = {**valid_cycle(), field: value}
        assert not any(x['key']=='learning' for x in recommended_existing_targets(14, DAY, cycle=bad))
    for field, value in [('auto_assignment', True), ('auto_selection', True),
                         ('requires_live_matrix_recheck', False), ('student_id', 15),
                         ('as_of','2026-10-19')]:
        bad = {**valid_alignment(), field: value}
        assert not any(x['key']=='wizard' for x in recommended_existing_targets(14,DAY,alignment=bad))
    bad = valid_alignment()
    bad['matched'][0]['automatic_transfer'] = True
    assert recommended_existing_targets(14,DAY,alignment=bad) == ()


def test_default_no_snapshot_same_menu_as_previous():
    form = Form()
    menu = Menu()
    install_existing_centers(menu,form)
    assert len([a for a in menu.recursive_actions() if a.title != '---']) == len(CENTERS)+2


def test_menu_with_verified_snapshot_only_on_explicit_click(monkeypatch):
    import ui.homework_context_integrations_v2 as navigation
    monkeypatch.setattr(navigation, '_warn', lambda *args: None)
    # Menu uses live date, so generate today's snapshot.
    today = date.today()
    cycle = valid_cycle(); cycle['as_of'] = today.isoformat()
    alignment = valid_alignment(); alignment['as_of'] = today.isoformat()
    routes = recommended_existing_targets(14,today,cycle=cycle,alignment=alignment)
    form = Form()
    form._loaded_student_id = 14
    form._workspace_v21.research_coach = type('Coach', (), {
        'navigation_recommendations_v3568': lambda self,sid,day: routes if sid==14 and day==today else ()
    })()
    menu=Menu()
    install_existing_centers(menu,form)
    actions=list(menu.recursive_actions())
    new_learning=next(a for a in actions if a.title.startswith('🧠 Öğrenme kontrolünü incele'))
    new_wizard=next(a for a in actions if a.title.startswith('✨ Mevcut Sihirbaz taslağını incele'))
    assert sum(getattr(form,c.button).count for c in CENTERS)==0
    new_learning.triggered.fire()
    assert form.btnOgrenme.count==1 and form.btnSihirbaz.count==0
    new_wizard.triggered.fire()
    assert form.btnSihirbaz.count==1
    form._loaded_student_id = 99
    new_wizard.triggered.fire()
    assert form.btnSihirbaz.count==1
    form.sid=15;form.cmbAd.sid=15;form.cmbSoyad.sid=15
    new_learning.triggered.fire()
    assert form.btnOgrenme.count==1


def test_no_production_core_or_original_assistant_modification():
    root=Path(__file__).resolve().parents[1]
    for file in ('ui/homework_form.py','ui/odev_kontrol.py','ui/smart_coach_secretary_toast.py'):
        assert 'coaching_navigation_v3568' not in (root/file).read_text(encoding='utf8')


def test_feature_toggle_preserves_original_right_click_menu(monkeypatch):
    today = date.today()
    cycle = valid_cycle(); cycle['as_of'] = today.isoformat()
    routes = recommended_existing_targets(14, today, cycle=cycle)
    form = Form()
    form._workspace_v21.research_coach = type('Coach', (), {
        'navigation_recommendations_v3568': lambda self, sid, day: routes
    })()
    monkeypatch.setenv('KOCPILOT_COACH_NAV_V3568', '0')
    menu = Menu()
    install_existing_centers(menu, form)
    actions = [a for a in menu.recursive_actions() if a.title != '---']
    assert len(actions) == len(CENTERS)+2
    assert not any('Öğrenme kontrolünü incele' in a.title for a in actions)
