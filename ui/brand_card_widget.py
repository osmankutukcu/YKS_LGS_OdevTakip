# -*- coding: utf-8 -*-
"""KoçPilot 360: Executive brand card widget for the dark sidebar."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QGraphicsDropShadowEffect
)


class BrandCardWidget(QFrame):
    """Deep navy frosted brand container with glowing compass emblem."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("BrandCardWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("""
            QFrame#BrandCardWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #162238, stop:0.55 #111a2e, stop:1 #0c1424);
                border-radius: 14px;
                border: 1px solid rgba(148, 163, 184, 0.22);
            }
            QFrame#BrandCardWidget:hover {
                border: 1px solid rgba(56, 189, 248, 0.45);
            }
        """)

        # Soft card shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 90))
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 14, 10, 12)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 1. Glowing Compass Emblem
        icon_outer = QFrame()
        icon_outer.setFixedSize(50, 50)
        icon_outer.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        icon_outer.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #06b6d4, stop:0.5 #0284c7, stop:1 #2563eb);
                border-radius: 25px;
                border: 2px solid #38bdf8;
            }
        """)
        icon_shadow = QGraphicsDropShadowEffect(icon_outer)
        icon_shadow.setBlurRadius(18)
        icon_shadow.setOffset(0, 0)
        icon_shadow.setColor(QColor(34, 211, 238, 180))
        icon_outer.setGraphicsEffect(icon_shadow)

        icon_inner = QVBoxLayout(icon_outer)
        icon_inner.setContentsMargins(0, 0, 0, 0)
        icon_inner.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_lbl = QLabel("🧭")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 24px; background: transparent; border: none;")
        icon_inner.addWidget(icon_lbl)

        layout.addWidget(icon_outer, 0, Qt.AlignmentFlag.AlignCenter)

        # 2. Typography Row: KoçPilot + 360 Badge
        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        title_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_koc = QLabel("KoçPilot")
        lbl_koc.setStyleSheet(
            "font-size: 16px; font-weight: 900; color: #ffffff; "
            "letter-spacing: -0.3px; background: transparent; border: none;"
        )
        title_row.addWidget(lbl_koc)

        lbl_360 = QLabel("360")
        lbl_360.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #22d3ee, stop:1 #0284c7);
            color: #0b1329;
            font-size: 10px;
            font-weight: 900;
            padding: 2px 6px;
            border-radius: 6px;
            border: none;
        """)
        title_row.addWidget(lbl_360)

        layout.addLayout(title_row)

        # 3. Subtitle
        sub_lbl = QLabel("BÜTÜNLEŞİK PLATFORM")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_lbl.setStyleSheet(
            "font-size: 9px; font-weight: 700; color: #94a3b8; "
            "letter-spacing: 1.2px; background: transparent; border: none;"
        )
        layout.addWidget(sub_lbl)
