# -*- coding: utf-8 -*-
"""V3594 opt-in bridge to EXISTING Koçluk/Ödev Takip workflows.

No task creation, plan generation, changes to the legacy form or implicit
approval. The weekly button opens Ödev Takip for the verified student; the
teacher then uses the existing Haftalık Planlayıcı button deliberately.
"""
from __future__ import annotations
from services.report_navigation_v3594 import verify_navigation


def _select_coaching_student(widget, student_id: int, *, role: int):
    """Find the exact ID. Fail rather than exposing a different student."""
    student_list = getattr(widget, 'list_students', None)
    if student_list is None or not callable(getattr(widget, '_on_student_selected', None)):
        raise RuntimeError('Koçluk Planı öğrenci seçimi doğrulanamadı.')
    item = next((student_list.item(i) for i in range(student_list.count())
                 if type(student_list.item(i).data(role)) is int and
                 student_list.item(i).data(role) == student_id), None)
    if item is None:
        raise RuntimeError('Öğrenci Koçluk Planı listesinde bulunamadı.')
    student_list.setCurrentItem(item)
    widget._on_student_selected(item)  # existing read/display path only
    if getattr(widget, 'current_student_id', None) != student_id:
        raise RuntimeError('Koçluk Planı farklı öğrenci gösterdi; işlem durduruldu.')


def open_confirmed_navigation(main_window, intent):
    """Called AFTER both modal decision and report dialogs have closed."""
    import db
    con = db.get_conn()
    try:
        if not verify_navigation(con, intent):
            raise ValueError('Öğrenci kaydı veya geçiş süresi doğrulanamadı.')
    finally:
        con.close()

    if intent.destination == 'weekly':
        from ui.homework_form import OdevTakipFormu
        target = getattr(main_window, '_show_dialog', None)
        if not callable(target):
            raise RuntimeError('Ödev Takip açılış yolu bulunamadı.')
        requested_id = intent.student_id

        class _SelectedHomeworkForm(OdevTakipFormu):
            def __init__(self, parent=None):
                # Pass ID at construction time: do not depend on the default
                # student's queued autoload or name/surname matching.
                super().__init__(parent, ogrenci_id=requested_id)
                self.select_student_by_id(requested_id, autoload=False)
                selected = self._secili_ogrenci_id()
                if type(selected) is not int or selected != requested_id:
                    raise RuntimeError('Ödev Takip farklı öğrenci gösterdi; işlem durduruldu.')

        _SelectedHomeworkForm.__name__ = OdevTakipFormu.__name__
        # The teacher chooses the original weekly planner button afterward.
        target(_SelectedHomeworkForm)
    elif intent.destination == 'coaching':
        from PyQt6.QtCore import Qt
        from ui.coaching_manager import CoachingManager
        target = getattr(main_window, '_show_dialog', None)
        if not callable(target):
            raise RuntimeError('Koçluk Planı açılış yolu bulunamadı.')
        requested_id = intent.student_id

        class _SelectedCoachingManager(CoachingManager):
            def __init__(self, parent=None):
                super().__init__(parent)
                _select_coaching_student(self, requested_id,
                                         role=Qt.ItemDataRole.UserRole)

        # Same original CoachingManager UI, only explicit-ID preselection.
        _SelectedCoachingManager.__name__ = CoachingManager.__name__
        target(_SelectedCoachingManager)
    else:
        raise ValueError('Desteklenmeyen yönlendirme.')
