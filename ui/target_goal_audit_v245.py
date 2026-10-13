# -*- coding: utf-8 -*-
"""V24.5 salt okunur veri güvenilirliği penceresi (öğrenciye özel)."""
from __future__ import annotations
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QTextEdit, QPushButton, QHBoxLayout
from PyQt6.QtCore import QStandardPaths

from services.target_analysis_v24.integrity_audit_v245 import audit_goal_sources, render_goal_audit
from services.target_analysis_v24.program_catalog_v242 import catalog_db_path
from services.target_analysis_v24.source_freshness_v241 import cache_path


class TargetGoalAuditDialog(QDialog):
    def __init__(self, student_id: int, parent=None):
        super().__init__(parent)
        self.student_id = student_id
        self.setWindowTitle('Hedef Analizi – Veri Güvenilirliği (Salt Okunur)')
        screen = QApplication.primaryScreen()
        if screen:
            available = screen.availableGeometry()
            self.resize(min(730, max(300, available.width()-50)),
                        min(550, max(300, available.height()-70)))
        layout = QVBoxLayout(self)
        label = QLabel('Yalnız seçili öğrencinin kayıtlarını ve kamuya açık veri kaynaklarının durumunu denetler. '
                       'Hiçbir hedefi, denemeyi veya ödevi kaydetmez/değiştirmez.')
        label.setWordWrap(True)
        layout.addWidget(label)
        self.result = QTextEdit()
        self.result.setReadOnly(True)
        self.result.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(self.result, 1)
        actions = QHBoxLayout()
        btn_again = QPushButton('Yeniden Denetle')
        btn_again.clicked.connect(self.refresh)
        actions.addWidget(btn_again)
        btn_copy = QPushButton('Raporu Kopyala')
        btn_copy.clicked.connect(lambda: QApplication.clipboard().setText(self.result.toPlainText()))
        actions.addWidget(btn_copy)
        actions.addStretch(1)
        btn_close = QPushButton('Kapat')
        btn_close.clicked.connect(self.accept)
        actions.addWidget(btn_close)
        layout.addLayout(actions)
        self.refresh()

    def refresh(self):
        import db
        try:
            appdir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
            public_dir = Path(appdir) if appdir else None
            db_path = Path(db.DB_PATH)
            from services.target_analysis_v24.history_location_v245 import resolve_history_location
            history = resolve_history_location(db_path)
            report = audit_goal_sources(
                db_path, self.student_id,
                trend_db=history.selected,
                catalog_db=catalog_db_path(public_dir) if public_dir else None,
                source_cache=cache_path(public_dir) if public_dir else None,
            )
            output = render_goal_audit(report)
            if history.conflict:
                output += ('\n\nUYARI: İki farklı konumda deneme geçmişi bulundu. '
                           'Otomatik birleştirme yapılmadı; veriler manuel karşılaştırılmalı.')
            self.result.setPlainText(output)
        except (ValueError, OSError) as exc:
            self.result.setPlainText('Denetim gerçekleştirilemedi: ' + str(exc) + '\nHiçbir kayıt değiştirilmedi.')
