"""V21 small adapter for the original Homework Form; no checkbox/data rewrites."""
from __future__ import annotations
from PyQt6.QtWidgets import QPushButton
from ui.student_workspace_panel_v21 import StudentWorkspacePanelV21


class HomeworkWorkspaceBridgeV21:
    def __init__(self, form, splitter, bottom_bar, assignments=None):
        self.form = form
        self.panel = StudentWorkspacePanelV21(form, open_control=self._open_control, open_adaptive=self._open_adaptive)
        splitter.addWidget(self.panel)
        splitter.setStretchFactor(2, 0)
        self.panel.set_open(False)
        self._responsive_v22 = None
        if assignments is None:
            assignments = getattr(form, '_right_split_v22', None)
        if assignments is not None:
            from ui.responsive_homework_v22 import ResponsiveHomeworkV22
            self._responsive_v22 = ResponsiveHomeworkV22(form, splitter, assignments, self.panel)
        self.toggle_button = QPushButton('🧭 Öğrenci 360°')
        self.toggle_button.setToolTip('Ana ödev tablosunun yanında öğrenci kanıtlarını göster/gizle')
        self.toggle_button.setFixedHeight(24)
        from PyQt6.QtCore import Qt
        self.toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_button.setStyleSheet("""
            QPushButton {
                background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 5px;
                padding: 2px 7px; font-size: 10.5px; font-weight: 600; color: #475569;
            }
            QPushButton:hover {
                background: #eff6ff; border-color: #3b82f6; color: #1d4ed8;
            }
        """)
        bottom_bar.addWidget(self.toggle_button)
        self.toggle_button.clicked.connect(self.toggle)
        try:
            from ui.smart_coach_secretary_toast import SmartCoachSecretaryController
            self.secretary = SmartCoachSecretaryController(
                form, bottom_bar, open_control=self._open_control, open_adaptive=self._open_adaptive
            )
        except Exception:
            self.secretary = None
        for cmb in (form.cmbAd, form.cmbSoyad):
            cmb.currentIndexChanged.connect(self.selection_changed)
        # Existing clicked handlers are connected first; refresh happens after they return.
        for btn_name in ('btnKaydet', 'btnKontrol', 'btnGetir'):
            btn = getattr(form, btn_name, None)
            if btn is not None:
                btn.clicked.connect(self.panel.mark_dirty)
        self.selection_changed()

    def selection_changed(self, *_):
        try:
            sid = self.form._secili_ogrenci_id()
        except (TypeError, ValueError, AttributeError):
            sid = None
        self.panel.set_student(sid)
        if getattr(self, 'secretary', None) is not None:
            self.secretary.on_student_changed(sid)

    def toggle(self):
        want = not self.panel._is_open
        self.panel.set_open(want)
        self.toggle_button.setText('✕ 360° Gizle' if want else '🧭 Öğrenci 360°')
        if self._responsive_v22 is not None:
            self._responsive_v22.update()

    def _open_control(self):
        if self.panel._student_id != self.form._secili_ogrenci_id():
            self.panel.set_student(self.form._secili_ogrenci_id())
            return
        self.form.btnKontrol.click()

    def _open_adaptive(self):
        # Never open another learner's analysis if selection changed mid-action.
        try:
            current = self.form._secili_ogrenci_id()
        except (AttributeError, TypeError, ValueError):
            current = None
        if current is None or current != self.panel._student_id:
            self.panel.set_student(current)
            return
        btn = getattr(self.form, 'btnOgrenme', None)
        if btn is not None:
            btn.click()  # Reuse the *existing* V25 analysis path.
