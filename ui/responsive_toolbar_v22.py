"""Scrollable button/tool bars: never hide active actions off-screen."""
from __future__ import annotations
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QScrollArea, QWidget, QSizePolicy, QFrame


def install_scrollable_bar(root, contents_layout, *, minimum_height: int) -> QScrollArea:
    inner = QWidget()
    inner.setObjectName('scrollableActionsV22')
    inner.setLayout(contents_layout)
    inner.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    area = QScrollArea()
    area.setObjectName('actionScrollV22')
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setWidgetResizable(True)
    area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    area.setWidget(inner)
    area.setFixedHeight(minimum_height)
    root.addWidget(area)
    QTimer.singleShot(0, lambda: update_bar_size(area))
    return area


def update_bar_size(area: QScrollArea) -> None:
    widget = area.widget()
    if widget is not None:
        widget.adjustSize()
        widget.updateGeometry()


def install_scrollable_widget(parent_layout, widget: QWidget, *, minimum_height: int) -> QScrollArea:
    """Wrap an existing widget without rebuilding its signal connections."""
    area = QScrollArea()
    area.setObjectName('horizontalWidgetScrollV22')
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setWidgetResizable(True)
    area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    area.setWidget(widget)
    area.setFixedHeight(minimum_height)
    parent_layout.addWidget(area)
    QTimer.singleShot(0, lambda: update_bar_size(area))
    return area

