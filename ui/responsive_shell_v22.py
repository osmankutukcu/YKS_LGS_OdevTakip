"""Responsive main menu: leaves every original QPushButton signal intact."""
from __future__ import annotations

from PyQt6.QtCore import QObject, QEvent, Qt, QTimer
from PyQt6.QtWidgets import QMenu, QPushButton, QToolButton
from services.responsive_v22 import compact_main_shell


class ResponsiveShellV22(QObject):
    def __init__(self, window, sidebar, content_layout):
        super().__init__(window)
        self.window = window
        self.sidebar = sidebar
        self.content_layout = content_layout
        self._compact = None
        self._pending = False

        self.menu_button = QToolButton(window)
        self.menu_button.setObjectName('compactMainMenuV22')
        self.menu_button.setText('☰ Menü / Modüller')
        self.menu_button.setToolTip('Dar ekranda ana modüllere erişim')
        self.menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.menu_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.menu = QMenu(self.menu_button)
        self.menu.aboutToShow.connect(self._rebuild_menu)
        self.menu_button.setMenu(self.menu)
        self.content_layout.insertWidget(0, self.menu_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.menu_button.hide()
        self.window.installEventFilter(self)
        QTimer.singleShot(0, self.update)

    def _rebuild_menu(self):
        self.menu.clear()
        # Use the very same buttons/controllers as the original sidebar.
        for button in self.sidebar.findChildren(QPushButton):
            if not button.text().strip():
                continue
            action = self.menu.addAction(button.text().strip())
            action.setEnabled(button.isEnabled())
            action.triggered.connect(lambda checked=False, target=button: target.click())

    def eventFilter(self, obj, event):
        if obj is self.window and event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            if not self._pending:
                self._pending = True
                QTimer.singleShot(0, self._scheduled)
        return False

    def _scheduled(self):
        self._pending = False
        self.update()

    def update(self):
        compact = compact_main_shell(self.window.width())
        if compact == self._compact:
            return
        self._compact = compact
        self.sidebar.setVisible(not compact)
        self.menu_button.setVisible(compact)
        self.content_layout.setContentsMargins(*( (8, 6, 8, 7) if compact else (20, 20, 20, 20) ))
