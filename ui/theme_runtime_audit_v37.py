# -*- coding: utf-8 -*-
"""Opt-in, read-only widget color diagnostic for the running PyQt6 application.

Run with YKS_THEME_AUDIT=1. NEVER logs widget text, table contents, student
names, phone numbers, paths from input fields, passwords, or database contents.
Static checks cannot infer the final cascaded Qt palette; these runtime findings
are indicative and require visual confirmation for translucent or custom-painted UI.
"""
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from PyQt6.QtCore import QObject, QEvent, QTimer, Qt
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import (
    QApplication, QWidget, QDialog, QMainWindow, QLabel, QAbstractButton,
    QAbstractItemView, QTableWidget, QLineEdit, QTextEdit, QPlainTextEdit,
    QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QTimeEdit, QDateTimeEdit,
)
from ui.theme import contrast_ratio


class ThemeContrastObserver(QObject):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self._waiting = False
        self.output = Path(os.environ.get('YKS_THEME_AUDIT_FILE') or
                           str(Path.cwd() / 'QA_V37' / 'theme_runtime_findings.jsonl'))

    def eventFilter(self, watched, event):
        try:
            if event.type() == QEvent.Type.Show and isinstance(watched, (QDialog, QMainWindow)):
                self.schedule_audit()
        except RuntimeError:
            pass
        return False

    def schedule_audit(self):
        if not self._waiting:
            self._waiting = True
            QTimer.singleShot(450, self.audit_open_windows)

    @staticmethod
    def _hex(c):
        if c.isValid() and c.alpha() >= 220:
            return c.name()
        return None

    def _check_one(self, w):
        p = w.palette()
        if isinstance(w, (QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox,
                          QDoubleSpinBox, QDateEdit, QTimeEdit, QDateTimeEdit, QAbstractItemView)):
            fg_role = QPalette.ColorRole.Text
            bg_role = QPalette.ColorRole.Base
        elif isinstance(w, QAbstractButton):
            fg_role = QPalette.ColorRole.ButtonText
            bg_role = QPalette.ColorRole.Button
        elif isinstance(w, QLabel):
            fg_role = QPalette.ColorRole.WindowText
            bg_role = QPalette.ColorRole.Window
            # Qt QLabel is usually transparent; ancestor background is hard to infer.
            # Do not report it as a definite mismatch without an explicit local style.
            local_qss = w.styleSheet().lower()
            if not ('background:' in local_qss or 'background-color:' in local_qss):
                return None
        else:
            return None
        fg = self._hex(p.color(QPalette.ColorGroup.Active, fg_role))
        bg = self._hex(p.color(QPalette.ColorGroup.Active, bg_role))
        if not fg or not bg:
            return None
        ratio = contrast_ratio(fg,bg)
        if ratio >= 4.5:
            return None
        return {'widget_type':type(w).__name__, 'foreground':fg, 'background':bg,
                'ratio':round(ratio,2),'disabled':not w.isEnabled()}

    def _check_table_items(self, table, issues, limit=4000):
        # Only explicit item background; skips blank/transparent cells.
        shown=0
        fallback = self._hex(table.palette().color(QPalette.ColorRole.Text))
        for row in range(table.rowCount()):
            for col in range(table.columnCount()):
                if shown>=limit:return
                shown+=1
                item = table.item(row,col)
                if not item or not item.text().strip():continue
                bg_brush=item.background()
                if bg_brush.style()==Qt.BrushStyle.NoBrush:continue
                bg=self._hex(bg_brush.color())
                if not bg:continue
                fg_brush=item.foreground()
                fg=self._hex(fg_brush.color()) if fg_brush.style()!=Qt.BrushStyle.NoBrush else fallback
                if not fg:continue
                ratio=contrast_ratio(fg,bg)
                if ratio<4.5:
                    issues.append({'widget_type':'QTableWidgetItem','foreground':fg,'background':bg,
                        'ratio':round(ratio,2),'row':row,'column':col})
                if len(issues)>=500:return

    def audit_open_windows(self):
        self._waiting=False
        issues=[];widgets=0;tables=0
        for win in self.app.topLevelWidgets():
            if not win.isVisible():continue
            for w in [win]+win.findChildren(QWidget):
                if not w.isVisible():continue
                widgets+=1
                item=self._check_one(w)
                if item and len(issues)<500:issues.append(item)
                if isinstance(w,QTableWidget):
                    tables+=1
                    self._check_table_items(w,issues)
        report={'utc':datetime.now(timezone.utc).isoformat(),
                'widgets_checked':widgets,'tables_checked':tables,
                'issues_count':len(issues),'truncated':len(issues)>=500,
                'method':'palette-based heuristic; visual confirmation required',
                'issues':issues}
        try:
            self.output.parent.mkdir(parents=True,exist_ok=True)
            with self.output.open('a',encoding='utf8') as f:
                f.write(json.dumps(report,ensure_ascii=False)+'\n')
        except OSError:
            pass  # QA write failures must never affect the application.
        return report


def install_dev_theme_audit(app):
    if os.environ.get('YKS_THEME_AUDIT') != '1':
        return None
    monitor=getattr(app,'_theme_contrast_observer_v37',None)
    if monitor is None:
        monitor=ThemeContrastObserver(app)
        app.installEventFilter(monitor)
        app._theme_contrast_observer_v37=monitor
    monitor.schedule_audit()
    return monitor
