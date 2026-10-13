# -*- coding: utf-8 -*-
"""Idempotent source bridge checker: use only against the V25 baseline.

Patch is deliberately split from V26 engine so existing homeworks never
need a schema migration. Running a second time does not duplicate insertions.
"""
from pathlib import Path


def patch(path, replacements):
    p = Path(path)
    s = p.read_text(encoding='utf-8')
    for before, after in replacements:
        if after in s:
            continue
        if s.count(before) != 1:
            raise RuntimeError(f'{path}: expected one V25 insertion point, got {s.count(before)}')
        s = s.replace(before, after)
    p.write_text(s, encoding='utf-8')


def run(root):
    root = Path(root)
    patch(root / 'main_window.py', [
        ('''        self.btnDeneme = style_sidebar_btn(QPushButton("Deneme Sınavları"), "📝")''',
         '''        # V26 modüler kurum koçluk merkezi (mevcut Ödev Takip aynen kalır).
        from services.adaptive_coaching_v26.flags import enabled as adaptive_v26_enabled
        self.btnAdaptiveV26 = style_sidebar_btn(QPushButton("Adaptif Koçluk Merkezi"), "🧠")
        self.btnAdaptiveV26.setVisible(adaptive_v26_enabled())
        self.btnAdaptiveV26.setToolTip("Öğrenci bazlı öğrenme kanıtları ve öğretmen karar destek merkezi")
        self.btnDeneme = style_sidebar_btn(QPushButton("Deneme Sınavları"), "📝")'''),
        ('''        menu_layout.addWidget(self.btnOdev)
        menu_layout.addWidget(self.btnDeneme)''',
         '''        menu_layout.addWidget(self.btnOdev)
        menu_layout.addWidget(self.btnAdaptiveV26)
        menu_layout.addWidget(self.btnDeneme)'''),
        ('''        self.btnOdev.clicked.connect(self._odev_ac)''',
         '''        self.btnOdev.clicked.connect(self._odev_ac)
        self.btnAdaptiveV26.clicked.connect(self._open_adaptive_v26)'''),
        ('''        self.dashboard.sig_open_students.connect(self._ogrenci_ac)''',
         '''        self.dashboard.sig_open_students.connect(self._ogrenci_ac)
        self.dashboard.sig_open_adaptive.connect(self._open_adaptive_v26)'''),
        ('''    def _ogrenci_ac(self): self._show_dialog(OgrenciFormu)''',
         '''    def _open_adaptive_v26(self):
        """Lazy/isolated decision center: failure cannot alter task tracking."""
        from services.adaptive_coaching_v26.flags import enabled as adaptive_enabled
        if not adaptive_enabled():
            return
        try:
            from ui.adaptive_coaching_center_v26 import AdaptiveCoachingCenterV26
            AdaptiveCoachingCenterV26(self).exec()
        except Exception as exc:
            QMessageBox.warning(self, 'Adaptif Koçluk',
                f'Koçluk merkezi açılamadı. Ödev Takip ve Ödev Kontrol etkilenmedi.\\n{exc}')

    def _ogrenci_ac(self): self._show_dialog(OgrenciFormu)''')
    ])
    patch(root / 'ui/dashboard_widget.py', [
        ('''    sig_open_overdue = pyqtSignal()''',
         '''    sig_open_overdue = pyqtSignal()
    sig_open_adaptive = pyqtSignal()'''),
        ('''        main_layout.addWidget(self.info_board)

        # Üst Sıra''',
         '''        main_layout.addWidget(self.info_board)
        # V26: visible decision workflow; never calculates false mastery scores.
        from services.adaptive_coaching_v26.flags import enabled as adaptive_v26_enabled
        if adaptive_v26_enabled():
            coachbar = QFrame()
            coachbar.setStyleSheet("QFrame {background:#eaf1fb;border:1px solid #d5e3f4;border-radius:9px;}")
            coachrow = QHBoxLayout(coachbar)
            coachrow.setContentsMargins(12,7,12,7)
            prompt = QLabel('🧠  Öğretmen Karar Masası · Önce kazanımı ölç, sonra kişisel ödev öner')
            prompt.setWordWrap(True)
            prompt.setStyleSheet('font-size:12px;font-weight:600;color:#173354;border:0;background:transparent;')
            coachrow.addWidget(prompt,1)
            opencoach = QPushButton('Adaptif Koçluk Merkezi  →')
            opencoach.setStyleSheet('background:white;color:#1d4ed8;padding:8px 10px;border:1px solid #b9cfee;border-radius:7px;font-weight:700;')
            opencoach.clicked.connect(self.sig_open_adaptive.emit)
            coachrow.addWidget(opencoach)
            main_layout.addWidget(coachbar)

        # Üst Sıra''')
    ])
    patch(root / 'ui/student360_panel_v16.py', [
        ('''        bar.addWidget(self.btn_topic_evidence)
        bar.addStretch()''',
         '''        bar.addWidget(self.btn_topic_evidence)
        from services.adaptive_coaching_v26.flags import enabled as adaptive_v26_enabled
        self.btn_adaptive_v26 = QPushButton('🧠 Adaptif Koçluk')
        self.btn_adaptive_v26.setVisible(adaptive_v26_enabled())
        self.btn_adaptive_v26.clicked.connect(self.open_adaptive_v26)
        bar.addWidget(self.btn_adaptive_v26)
        bar.addStretch()'''),
        ('''    def copy_summary(self):''',
         '''    def open_adaptive_v26(self):
        if self.student_id is None:
            self.output.setPlainText('Önce bir öğrenci seçin.')
            return
        try:
            from ui.adaptive_coaching_dialog_v25 import AdaptiveCoachingDialogV25
            AdaptiveCoachingDialogV25(self.student_id, parent=self, host=None).exec()
            self.refresh()
        except Exception as exc:
            self.output.append(f'\\nAdaptif Koçluk açılamadı: {exc}')

    def copy_summary(self):'''),
        ('''                academic_target = read_saved_target(con, sid)''',
         '''                academic_target = read_saved_target(con, sid)
                # Read-only optional decision summary. Missing V25 schema is a normal state.
                adaptive_text = None
                try:
                    from services.adaptive_coaching_v26.flags import enabled as adaptive_v26_enabled
                    if adaptive_v26_enabled():
                        from services.adaptive_coaching_v26.decision import student_decisions, concise_summary
                        con.row_factory = sqlite3.Row
                        adaptive_text = concise_summary(student_decisions(con, sid), n=3)
                except (sqlite3.Error, ValueError, KeyError, TypeError) as exc:
                    adaptive_text = f'Adaptif öğrenme özeti şu an okunamadı: {exc}' '''),
        ('''        parts += [f'• {x}' for x in suggestions(data)]''',
         '''        parts += [f'• {x}' for x in suggestions(data)]
        if adaptive_text:
            parts += ['', adaptive_text]''')
    ])


if __name__ == '__main__':
    import sys
    run(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1])
