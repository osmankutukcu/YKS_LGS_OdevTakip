"""Idempotent, narrow UI bridge patch. No checkbox/storage handlers are overwritten."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def insert_once(path, needle, replacement, guard):
    s = path.read_text(encoding='utf-8')
    if guard in s:
        return False
    if s.count(needle) != 1:
        raise RuntimeError(f'Beklenen tek entegrasyon noktası yok: {path.name} {s.count(needle)}')
    path.write_text(s.replace(needle, replacement, 1), encoding='utf-8')
    return True


homework = ROOT / 'ui/homework_form.py'
insert_once(homework,
'''    def _open_smart_wizard(self):''',
'''    def _open_adaptive_v25(self):
        """Optional, student-scoped module; never overwrites legacy homework handlers."""
        from services.adaptive_coaching_v25.flags import enabled
        if not enabled():
            return
        student_id = self._secili_ogrenci_id()
        if not student_id:
            QMessageBox.warning(self, 'Öğrenci Seçiniz', 'Önce öğrenci seçiniz.')
            return
        try:
            from ui.adaptive_coaching_dialog_v25 import AdaptiveCoachingDialogV25
            AdaptiveCoachingDialogV25(int(student_id), parent=self, host=self).exec()
        except Exception as exc:
            QMessageBox.warning(self, 'Bilimsel Koçluk',
                                'Modül açılamadı; mevcut ödev formu etkilenmedi.\\n' + str(exc))

    def _open_smart_wizard(self):''',
'    def _open_adaptive_v25(self):')
insert_once(homework,
'''        self.btnVeriDenetimi = QPushButton("🔎 Denetim")''',
'''        self.btnAdaptifV25 = QPushButton('🧠 Öğrenme')
        self.btnAdaptifV25.setToolTip('Ayrı kazanım teşhisi, aralıklı tekrar ve adaptif ödev taslakları')
        from services.adaptive_coaching_v25.flags import enabled as adaptive_v25_enabled
        self.btnAdaptifV25.setVisible(adaptive_v25_enabled())
        self.btnVeriDenetimi = QPushButton("🔎 Denetim")''',
'        self.btnAdaptifV25 = QPushButton(')
insert_once(homework,
'''        for b in (self.btnDetayRapor, self.btnOneriEksik, self.btnOneriTakviye, self.btnSihirbaz, self.btnVeriDenetimi):''',
'''        for b in (self.btnDetayRapor, self.btnOneriEksik, self.btnOneriTakviye,
                  self.btnSihirbaz, self.btnAdaptifV25, self.btnVeriDenetimi):''',
'                  self.btnSihirbaz, self.btnAdaptifV25, self.btnVeriDenetimi):')
insert_once(homework,
'''        self.btnSihirbaz.clicked.connect(self._open_smart_wizard)''',
'''        self.btnSihirbaz.clicked.connect(self._open_smart_wizard)
        self.btnAdaptifV25.clicked.connect(self._open_adaptive_v25)''',
'        self.btnAdaptifV25.clicked.connect(self._open_adaptive_v25)')

control = ROOT / 'ui/odev_kontrol.py'
insert_once(control,
'''    def _open_scoped_control_v234(self):''',
'''    def _open_adaptive_v25(self):
        """Optional insight dialog. Checking/completing homework remains unchanged."""
        from services.adaptive_coaching_v25.flags import enabled
        if not enabled():
            return
        try:
            homework_id = None
            selected = self.tab.currentRow()
            if selected >= 0:
                item = self.tab.item(selected, 1)
                if item is not None:
                    homework_id = item.data(USERROLE)
            from ui.adaptive_coaching_dialog_v25 import AdaptiveCoachingDialogV25
            AdaptiveCoachingDialogV25(self.ogr_id, parent=self,
                                      initial_homework_id=homework_id).exec()
        except Exception as exc:
            QMessageBox.warning(self, 'Bilimsel Koçluk',
                                'Modül açılamadı; mevcut ödev kontrol etkilenmedi.\\n' + str(exc))

    def _open_scoped_control_v234(self):''',
'    def _open_adaptive_v25(self):')
insert_once(control,
'''        flow.addWidget(self.btnScopedV234)
        btnBarLayout.addWidget(btnBar)''',
'''        flow.addWidget(self.btnScopedV234)
        self.btnAdaptiveV25 = _mk('🧠 Öğrenme Analizi', 'btnInfo')
        self.btnAdaptiveV25.setToolTip('Kazanım/hata nedenleri kaydı; ödev tiklerinden ayrı tutulur')
        from services.adaptive_coaching_v25.flags import enabled as adaptive_v25_enabled
        self.btnAdaptiveV25.setVisible(adaptive_v25_enabled())
        self.btnAdaptiveV25.clicked.connect(self._open_adaptive_v25)
        flow.addWidget(self.btnAdaptiveV25)
        btnBarLayout.addWidget(btnBar)''',
'        self.btnAdaptiveV25 = _mk(')
print('V25 entegrasyon noktaları hazır; ikinci çalıştırmada tekrarlanmaz.')
