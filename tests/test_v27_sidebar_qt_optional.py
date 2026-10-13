"""Real Qt visual-switch smoke test (skipped when PyQt6 is unavailable)."""
import os
import pytest
qt = pytest.importorskip('PyQt6.QtWidgets')
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QStackedWidget,
                             QHBoxLayout, QComboBox, QPushButton, QLabel)
from ui.adaptive_homework_sidebar_v27 import AdaptiveHomeworkSidebarV27
from ui.homework_adaptive_bridge_v27 import HomeworkAdaptiveBridgeV27


@pytest.fixture
def window():
    if os.name != 'nt':
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    app = QApplication.instance() or QApplication([])
    form = QWidget()
    form.cmbAd, form.cmbSoyad = QComboBox(), QComboBox()
    form.btnKaydet, form.btnKontrol, form.btnGetir = QPushButton(), QPushButton(), QPushButton()
    form._secili_ogrenci_id = lambda: 1
    form._workspace_v21 = None
    layout = QVBoxLayout(form)
    stack = QStackedWidget()
    old = QWidget()
    old.data = ['Ödev A düzenlendi', 'Ödev B açık']
    stack.addWidget(old)
    adaptive = AdaptiveHomeworkSidebarV27(form)
    # No actual SQLite access needed for rendering/stack switching test.
    adaptive.refresh = lambda: None
    stack.addWidget(adaptive)
    layout.addWidget(stack)
    bottom = QHBoxLayout()
    layout.addLayout(bottom)
    form._adaptive_bridge_v27 = HomeworkAdaptiveBridgeV27(form,stack,bottom)
    form.show()
    app.processEvents()
    yield form,stack,old,adaptive,app
    form.close()


def test_assignments_untouched_when_adaptive_toggled(window):
    form,stack,old,adaptive,app = window
    before = list(old.data)
    assert stack.currentIndex() == 0
    form._adaptive_bridge_v27.show_adaptive()
    app.processEvents()
    assert stack.currentWidget() is adaptive
    assert old.data == before
    form._adaptive_bridge_v27.show_assignments()
    assert stack.currentWidget() is old
    assert old.data == before


def test_student_switch_clears_prior_identity_without_altering_assignments(window):
    form,stack,old,adaptive,app = window
    adaptive.set_student(1)
    adaptive.identity.setText('Öğrenci Bir')
    adaptive.set_student(2)
    assert adaptive._student_id == 2
    assert 'Öğrenci Bir' not in adaptive.identity.text()
    assert old.data == ['Ödev A düzenlendi', 'Ödev B açık']
