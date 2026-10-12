"""Optional real Qt smoke checks; run on the user's Windows test machine.

Example: python -m pytest -q tests/test_v22_qt_layout_optional.py
"""
from __future__ import annotations
import os
import pytest

qt = pytest.importorskip('PyQt6.QtWidgets')
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QSplitter)
from PyQt6.QtCore import Qt

from ui.responsive_shell_v22 import ResponsiveShellV22
from ui.responsive_homework_v22 import ResponsiveHomeworkV22
from ui.responsive_toolbar_v22 import install_scrollable_bar, update_bar_size


@pytest.fixture(scope='module')
def qapp():
    # Use actual Windows platform plugin on Windows; offscreen on CI Linux.
    if os.name != 'nt':
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    app = QApplication.instance() or QApplication([])
    yield app


def test_compact_menu_dispatches_original_button(qapp):
    window = QMainWindow()
    content = QWidget()
    window.setCentralWidget(content)
    layout = QHBoxLayout(content)
    sidebar = QWidget()
    sidebar_layout = QVBoxLayout(sidebar)
    original = QPushButton('Ödev Takip')
    sidebar_layout.addWidget(original)
    layout.addWidget(sidebar)
    host = QWidget()
    host_layout = QVBoxLayout(host)
    layout.addWidget(host)
    triggered = []
    original.clicked.connect(lambda: triggered.append('clicked'))
    shell = ResponsiveShellV22(window, sidebar, host_layout)
    window.resize(1024, 768)
    window.show()
    qapp.processEvents()
    shell.update()
    assert shell.menu_button.isVisible()
    assert sidebar.isHidden()
    shell._rebuild_menu()
    assert shell.menu.actions()
    shell.menu.actions()[0].trigger()
    assert triggered == ['clicked']
    window.close()


def test_narrow_workspace_swaps_without_deleting_assignments(qapp):
    form = QWidget()
    layout = QVBoxLayout(form)
    split = QSplitter(Qt.Orientation.Horizontal)
    layout.addWidget(split)
    left, assignments, panel = QWidget(), QWidget(), QWidget()
    panel._is_open = False
    for w in (left, assignments, panel):
        split.addWidget(w)
    adapter = ResponsiveHomeworkV22(form, split, assignments, panel)
    form.resize(1000, 650)
    form.show()
    qapp.processEvents()
    adapter.update()
    assert not assignments.isHidden()
    panel._is_open = True
    adapter.update()
    assert assignments.isHidden()
    assert not panel.isHidden()
    assert split.count() == 3  # no widget destroyed or duplicate created
    form.close()


def test_toolbar_actions_can_scroll(qapp):
    frame = QWidget()
    root = QVBoxLayout(frame)
    actions = QHBoxLayout()
    for i in range(7):
        btn = QPushButton(f'İşlem {i}')
        btn.setFixedWidth(150)
        actions.addWidget(btn)
    area = install_scrollable_bar(root, actions, minimum_height=58)
    frame.resize(350, 200)
    frame.show()
    qapp.processEvents()
    update_bar_size(area)
    qapp.processEvents()
    assert area.horizontalScrollBar().maximum() > 0
    frame.close()
