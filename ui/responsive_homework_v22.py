"""Adaptive 2/3-column behavior for the existing read-only V21 sidebar."""
from __future__ import annotations
from PyQt6.QtCore import QObject, QEvent, QTimer
from services.responsive_v22 import compact_homework_workspace


class ResponsiveHomeworkV22(QObject):
    def __init__(self, form, splitter, assignments, panel):
        super().__init__(form)
        self.form = form
        self.splitter = splitter
        self.assignments = assignments
        self.panel = panel
        self._pending = False
        self._last = None
        form.installEventFilter(self)
        QTimer.singleShot(0, self.update)

    def eventFilter(self, obj, event):
        if obj is self.form and event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            if not self._pending:
                self._pending = True
                QTimer.singleShot(0, self._scheduled)
        return False

    def _scheduled(self):
        self._pending = False
        self.update()

    def update(self):
        compact = compact_homework_workspace(self.form.width())
        panel_open = bool(self.panel._is_open)
        layout_state = (compact, panel_open)
        if layout_state == self._last:
            return
        self._last = layout_state
        # Narrow screens: replace only the assignments view while the panel
        # is open, not the assignment data; hiding a QWidget does not destroy it.
        self.assignments.setVisible(not (compact and panel_open))
        self.panel.setVisible(panel_open)
        if compact:
            self.splitter.setStretchFactor(0, 7)
            self.splitter.setStretchFactor(1, 3)
            self.splitter.setStretchFactor(2, 3)
        else:
            self.splitter.setStretchFactor(0, 7)
            self.splitter.setStretchFactor(1, 3)
            self.splitter.setStretchFactor(2, 2)
