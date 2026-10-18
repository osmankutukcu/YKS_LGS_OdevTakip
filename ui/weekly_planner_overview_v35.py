"""Optional, read-only summary tab for the existing weekly planner dialog.

This module does not create plans, edit homework, or persist profile changes.
Buttons navigate to the existing proven settings tabs only.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QGroupBox, QLabel, QPushButton, QFrame,
                             QCheckBox, QComboBox)
from PyQt6.QtCore import Qt
from services.weekly_planner_presentation_v35 import overview
from services.planning_constraints import availability_for_week, free_minutes


class WeeklyPlannerOverview(QWidget):
    def __init__(self, dialog, homework_list):
        super().__init__(dialog)
        self.dialog = dialog
        self.homework_list = list(homework_list or [])
        self._make_ui()

    @staticmethod
    def _lbl(value=''):
        label = QLabel(value)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setStyleSheet('font-size:12px;color:#334155;')
        return label

    @staticmethod
    def _group(title):
        g = QGroupBox(title)
        g.setStyleSheet('QGroupBox{font-size:13px;font-weight:700;color:#1d4ed8;'
                        'background:white;border:1px solid #dbeafe;border-radius:8px;'
                        'margin-top:12px;padding-top:10px;} '
                        'QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 4px;}')
        return g

    def _go(self, index):
        self.dialog.tabs.setCurrentIndex(index)

    def _make_ui(self):
        body = QVBoxLayout(self)
        body.setContentsMargins(16, 12, 16, 12)
        body.setSpacing(10)
        headline = self._lbl('Verilen Ödevler, öğrenci koşulları ve planlama ayarları')
        headline.setStyleSheet('font-size:15px;font-weight:700;color:#0f172a;')
        body.addWidget(headline)
        hint = self._lbl('Bu ekran yalnızca önizleme yapar. Görevlerin dağılımı “Haftalık Planı Oluştur”'
                         ' düğmesine basılınca hesaplanır; ödev tikleri değişmez.')
        hint.setStyleSheet('font-size:11px;color:#64748b;')
        body.addWidget(hint)

        grid = QGridLayout()
        grid.setSpacing(10)
        assignments = self._group('1. Verilen Ödevler')
        a = QVBoxLayout(assignments)
        self.tasks_count = self._lbl()
        self.tasks_preview = self._lbl()
        a.addWidget(self.tasks_count)
        a.addWidget(self.tasks_preview)
        grid.addWidget(assignments, 0, 0)

        school = self._group('2. Okul ve Sabit Rutinler')
        b = QVBoxLayout(school)
        self.school_info = self._lbl()
        b.addWidget(self.school_info)
        btn_sec_style = ("QPushButton { background-color: #f8fafc; color: #334155; border: 1px solid #cbd5e1; "
                         "border-radius: 6px; padding: 5px 10px; font-weight: 600; font-size: 11px; } "
                         "QPushButton:hover { background-color: #f1f5f9; border-color: #94a3b8; color: #0f172a; }")
        jump_school = QPushButton('🕒 Okul ve Rutinleri Düzenle')
        jump_school.setStyleSheet(btn_sec_style)
        jump_school.clicked.connect(lambda: self._go(1))
        b.addWidget(jump_school)
        grid.addWidget(school, 0, 1)

        tempo = self._group('3. Uyku, Dinlenme ve Kapasite')
        c = QVBoxLayout(tempo)
        self.tempo_info = self._lbl()
        c.addWidget(self.tempo_info)
        jump_tempo = QPushButton('⏱️ Uyku ve Limitleri Düzenle')
        jump_tempo.setStyleSheet(btn_sec_style)
        jump_tempo.clicked.connect(lambda: self._go(2))
        c.addWidget(jump_tempo)
        grid.addWidget(tempo, 1, 0)

        planning = self._group('4. Ders Öncelikleri ve Akıllı Kurallar')
        d = QVBoxLayout(planning)
        self.rules_info = self._lbl()
        d.addWidget(self.rules_info)
        jump_rules = QPushButton('⚙️ Öncelik ve Kuralları Düzenle')
        jump_rules.setStyleSheet(btn_sec_style)
        jump_rules.clicked.connect(lambda: self._go(2))
        d.addWidget(jump_rules)
        # Optional: reads existing teacher notes only after an explicit click.
        adaptive_btn = QPushButton('🧠 Adaptif Koçluk Önerilerini İncele')
        adaptive_btn.setStyleSheet("QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #8b5cf6); "
                                   "color: #ffffff; border: none; border-radius: 6px; padding: 7px 12px; font-weight: 700; font-size: 11.5px; } "
                                   "QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #7c3aed); }")
        adaptive_btn.setToolTip('Mevcut ödev konuları için kayıtlı gözlemleri inceler. '
                                'Onay vermeden ders önceliği değişmez.')
        adaptive_btn.clicked.connect(self._offer_adaptive_focus)
        d.addWidget(adaptive_btn)
        self.clear_topic_focus_btn = QPushButton('✖ Bu Planın Adaptif Konu Önceliğini Kaldır')
        self.clear_topic_focus_btn.setStyleSheet("QPushButton { background-color: #ffffff; color: #dc2626; border: 1px solid #fecaca; "
                                                "border-radius: 6px; padding: 5px 10px; font-weight: 600; font-size: 11px; } "
                                                "QPushButton:hover { background-color: #fef2f2; border-color: #f87171; }")
        self.clear_topic_focus_btn.setToolTip('Kaydedilmiş ders önceliklerini veya ödevleri değiştirmez.')
        self.clear_topic_focus_btn.clicked.connect(self._clear_topic_focus)
        d.addWidget(self.clear_topic_focus_btn)
        grid.addWidget(planning, 1, 1)

        routine_group = self._group('5. Günlük Temel Alışkanlık Rutinleri (Paragraf & Problem)')
        r_box = QVBoxLayout(routine_group)
        r_box.setContentsMargins(12, 10, 12, 10)
        r_box.setSpacing(8)

        r_top = QHBoxLayout()
        r_top.setSpacing(10)

        self.chk_routine_spread = QCheckBox('🎯 Rutinleri Günlük Alışkanlık Olarak Her Güne Dağıt')
        self.chk_routine_spread.setChecked(True)
        self.chk_routine_spread.setStyleSheet('font-size: 12.5px; font-weight: 700; color: #047857;')
        self.chk_routine_spread.setToolTip('Paragraf ve Problem ödevlerini tek güne yığmak yerine haftanın günlerine dengeli alışkanlık olarak dağıtır.')
        r_top.addWidget(self.chk_routine_spread)

        r_top.addStretch(1)

        cmb_style = ("QComboBox { background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; "
                     "padding: 4px 8px; font-size: 11.5px; font-weight: 600; color: #1e293b; min-width: 135px; } "
                     "QComboBox:disabled { background-color: #f1f5f9; color: #94a3b8; border-color: #e2e8f0; } "
                     "QComboBox::drop-down { border: none; }")

        lbl_days = QLabel('Hedef:')
        lbl_days.setStyleSheet('font-size: 11px; font-weight: 600; color: #475569;')
        r_top.addWidget(lbl_days)

        self.cmb_routine_days = QComboBox()
        self.cmb_routine_days.setStyleSheet(cmb_style)
        self.cmb_routine_days.addItem('7 Gün (Tüm Hafta)', 7)
        self.cmb_routine_days.addItem('5 Gün (Hafta İçi)', 5)
        r_top.addWidget(self.cmb_routine_days)

        lbl_time = QLabel('Zaman:')
        lbl_time.setStyleSheet('font-size: 11px; font-weight: 600; color: #475569;')
        r_top.addWidget(lbl_time)

        self.cmb_routine_time = QComboBox()
        self.cmb_routine_time.setStyleSheet(cmb_style)
        self.cmb_routine_time.addItem('🕒 Okul/Rutin Sonrası', 'after_school')
        self.cmb_routine_time.addItem('🌅 Sabah Erken', 'morning')
        self.cmb_routine_time.addItem('🌙 Akşam Etüdü', 'evening')
        self.cmb_routine_time.addItem('⚡ Esnek / Otomatik', 'auto')
        r_top.addWidget(self.cmb_routine_time)

        r_box.addLayout(r_top)

        self.lbl_routine_status = QLabel()
        self.lbl_routine_status.setStyleSheet('font-size: 11.5px; color: #065f46; background: #ecfdf5; '
                                              'border: 1px solid #a7f3d0; border-radius: 6px; padding: 6px 10px;')
        self.lbl_routine_status.setWordWrap(True)
        r_box.addWidget(self.lbl_routine_status)

        self.chk_routine_spread.toggled.connect(self._on_routine_toggled)
        self.cmb_routine_days.currentIndexChanged.connect(lambda _: self._update_routine_status())

        grid.addWidget(routine_group, 2, 0, 1, 2)

        print_group = self._group('6. Sayfa & Yazıcı Çıktı Tercihleri (A4 Yatay Takvim)')
        p_box = QVBoxLayout(print_group)
        p_box.setContentsMargins(12, 10, 12, 10)
        p_box.setSpacing(6)

        p_row = QHBoxLayout()
        p_row.setSpacing(14)

        self.chk_include_task_details = QCheckBox('📋 Gün ve Saat Bazında Detaylı Görev Tablosunu Ekle')
        self.chk_include_task_details.setChecked(False)
        self.chk_include_task_details.setStyleSheet('font-size: 11.5px; font-weight: 600; color: #1e293b;')
        self.chk_include_task_details.setToolTip('İşaretlenirse takvimin arkasına tüm ödevlerin başlangıç-bitiş saatlerini listeleyen detay tablosu eklenir.')
        p_row.addWidget(self.chk_include_task_details)

        self.chk_include_constraints = QCheckBox('⚙️ Planlama Kısıtları & Kural Özet Tablosunu Ekle')
        self.chk_include_constraints.setChecked(False)
        self.chk_include_constraints.setStyleSheet('font-size: 11.5px; font-weight: 600; color: #1e293b;')
        self.chk_include_constraints.setToolTip('İşaretlenirse okul, uyku ve sabit rutin kurallarını gösteren tablo eklenir.')
        p_row.addWidget(self.chk_include_constraints)

        p_row.addStretch(1)
        p_box.addLayout(p_row)

        self.lbl_pages_hint = QLabel('📄 Çıktı Modu: Tek Sayfa (1/1) • Yalnızca A4 Yatay Çalışma Takvimi yazdırılır (Hızlı ve ekonomik baskı).')
        self.lbl_pages_hint.setStyleSheet('font-size: 11px; color: #047857; background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 5px; padding: 5px 8px; font-weight: 500;')
        self.lbl_pages_hint.setWordWrap(True)
        p_box.addWidget(self.lbl_pages_hint)

        self.chk_include_task_details.toggled.connect(self._update_print_hint)
        self.chk_include_constraints.toggled.connect(self._update_print_hint)

        grid.addWidget(print_group, 3, 0, 1, 2)

        body.addLayout(grid)
        box = QFrame()
        box.setStyleSheet('QFrame{background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;}')
        lay = QVBoxLayout(box)
        self.capacity_info = self._lbl()
        self.capacity_info.setStyleSheet('font-size:12px;font-weight:600;color:#1e40af;')
        lay.addWidget(self.capacity_info)
        body.addWidget(box)
        body.addStretch(1)

    def _on_routine_toggled(self, checked: bool):
        self.cmb_routine_days.setEnabled(checked)
        self.cmb_routine_time.setEnabled(checked)
        self._update_routine_status()

    def _update_routine_status(self):
        if not self.chk_routine_spread.isChecked():
            self.lbl_routine_status.setText('⚪ Rutin dağıtımı kapalı: Paragraf ve problem ödevleri normal ders ödevi gibi tek parça planlanacaktır.')
            self.lbl_routine_status.setStyleSheet('font-size: 11.5px; color: #64748b; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 6px 10px;')
            return

        from services.smart_calendar import SmartCalendarService
        routines = [h for h in self.homework_list if SmartCalendarService._is_routine_task(h)]
        days_count = self.cmb_routine_days.currentData() or 7
        if routines:
            total_m = sum(int(h.get('sure') or 0) for h in routines)
            daily_m = total_m // days_count
            self.lbl_routine_status.setText(
                f'✨ Tespit Edildi: {len(routines)} rutin ödevi (Toplam {total_m} dk) ➜ '
                f'{days_count} güne bölünerek günde ~{daily_m} dk alışkanlık olarak yerleştirilecek.'
            )
            self.lbl_routine_status.setStyleSheet('font-size: 11.5px; color: #065f46; background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 6px; padding: 6px 10px; font-weight: 500;')
        else:
            self.lbl_routine_status.setText(
                'ℹ️ Verilen ödevler arasında "Paragraf" veya "Problem" ödevi tespit edildiğinde otomatik her güne alışkanlık olarak dağıtılır.'
            )
            self.lbl_routine_status.setStyleSheet('font-size: 11.5px; color: #0277b3; background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 6px; padding: 6px 10px;')

    def get_routine_settings(self) -> dict:
        return {
            'routine_spread_enabled': self.chk_routine_spread.isChecked(),
            'routine_spread_days': self.cmb_routine_days.currentData() or 7,
            'routine_time_preference': self.cmb_routine_time.currentData() or 'after_school',
        }

    def set_routine_settings(self, settings: dict):
        if not isinstance(settings, dict):
            return
        if 'routine_spread_enabled' in settings:
            self.chk_routine_spread.setChecked(bool(settings['routine_spread_enabled']))
        if 'routine_spread_days' in settings:
            idx = self.cmb_routine_days.findData(settings['routine_spread_days'])
            if idx >= 0:
                self.cmb_routine_days.setCurrentIndex(idx)
        if 'routine_time_preference' in settings:
            idx = self.cmb_routine_time.findData(settings['routine_time_preference'])
            if idx >= 0:
                self.cmb_routine_time.setCurrentIndex(idx)
        self._update_routine_status()

    def get_print_preferences(self) -> dict:
        return {
            'include_task_details': self.chk_include_task_details.isChecked(),
            'include_constraints': self.chk_include_constraints.isChecked(),
        }

    def set_print_preferences(self, prefs: dict):
        if not isinstance(prefs, dict):
            return
        if 'include_task_details' in prefs:
            self.chk_include_task_details.setChecked(bool(prefs['include_task_details']))
        if 'include_constraints' in prefs:
            self.chk_include_constraints.setChecked(bool(prefs['include_constraints']))
        self._update_print_hint()

    def _update_print_hint(self):
        inc_t = self.chk_include_task_details.isChecked()
        inc_c = self.chk_include_constraints.isChecked()
        if not inc_t and not inc_c:
            self.lbl_pages_hint.setText('📄 Çıktı Modu: Tek Sayfa (1/1) • Yalnızca A4 Yatay Çalışma Takvimi yazdırılır (Hızlı ve ekonomik baskı).')
            self.lbl_pages_hint.setStyleSheet('font-size: 11px; color: #047857; background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 5px; padding: 5px 8px; font-weight: 500;')
        else:
            parts = []
            if inc_t: parts.append('Detaylı Görev Listesi')
            if inc_c: parts.append('Kısıtlar & Kurallar')
            self.lbl_pages_hint.setText(f'📑 Çıktı Modu: Çok Sayfalı Rapor • Ana takvime ek olarak: {", ".join(parts)} sayfaları eklenecek.')
            self.lbl_pages_hint.setStyleSheet('font-size: 11px; color: #1e40af; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 5px; padding: 5px 8px; font-weight: 500;')

    def _offer_adaptive_focus(self):
        from ui.weekly_planner_adaptive_bridge_v35 import offer_focus_suggestions
        offer_focus_suggestions(self.dialog)

    def _clear_topic_focus(self):
        self.dialog._approved_topic_focus = []
        self.refresh()

    def refresh(self):
        try:
            data = self.dialog._gather_data()
            s = overview(self.homework_list, data)
            self.tasks_count.setText(f'{s["count"]} görev • {s["minutes"]} dakika '
                                     f'({s["minutes"] // 60} sa {s["minutes"] % 60} dk)')
            lines = [f'{h.get("ders", "?")} / {h.get("konu", "?")} / '
                     f'{h.get("kitap", "-")} — {h.get("sure", "?")} dk'
                     for h in self.homework_list[:4]]
            if len(self.homework_list) > 4:
                lines.append(f'... ve {len(self.homework_list)-4} diğer görev')
            self.tasks_preview.setText('\n'.join(lines) if lines else 'Verilen Ödevler listesi boş.')
            self.school_info.setText(f'{s["school_days"]} okul günü • {s["routines"]} sabit rutin\n'
                                     f'Okul sonrası geçiş: {s["after_school"]} dk\n'
                                     f'Rutin sonrası geçiş: {s["after_routine"]} dk')
            self.tempo_info.setText(f'Uyku: {s["sleep"]} • Uyanma: {s["wake"]}\n'
                                     f'Günlük üst sınır: {s["daily_max"]} dk\n'
                                     f'Oturum: {s["session_minutes"]} dk + '
                                     f'{s["session_break"]} dk mola '
                                     f'({"bölünebilir" if s["split_enabled"] else "isteğe bağlı"})')
            approved = getattr(self.dialog, '_approved_topic_focus', [])
            selected = ', '.join(f'{r["lesson"]} / {r["topic"]}' for r in approved)
            self.clear_topic_focus_btn.setEnabled(bool(approved))
            self.rules_info.setText(f'Öncelikli dersler: {s["focus"] or "Belirtilmedi"}\n'
                                     f'Bu plana özel adaptif konu: {selected or "Onaylanmadı"}\n'
                                     'Planlama: okul, rutin, uyku, teslim tarihi, '
                                     'günlük sınır ve varsa oturum kuralları')
            availability = availability_for_week(data)
            advanced = data.get('advanced_days', {}) if data.get('advanced_enabled') else {}
            older = data.get('day_overrides', {}) if data.get('advanced_enabled') else {}
            cap = sum(min(s['daily_max'],
                          int((advanced.get(str(day)) or older.get(str(day)) or {}).get('max',
                              s['daily_max'])), free_minutes(intervals))
                      for day, intervals in availability.items())
            self.capacity_info.setText(f'Haftalık teorik çalışma kapasitesi: {cap} dk  •  '
                                       f'Gereken: {s["minutes"]} dk\n'
                                       'Bu değer yalnızca üst sınırdır; yerleştirme başarısı veya '
                                       'uygun gün/saat garantisi değildir.')
            self._update_routine_status()
        except (ValueError, KeyError, TypeError) as err:
            self.capacity_info.setText('Saat veya rutin ayarlarını kontrol edin: ' + str(err))
