"""V2: fast links to EXISTING Homework Form actions; never create duplicate engines.

The adapter only constructs menu actions and routes explicit clicks to the
already-connected form QPushButtons. No SQLite, network or matrix writes here.
It never selects a student, flips checkboxes or bypasses legacy lock controls.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExistingCenter:
    key: str
    title: str
    button: str
    explanation: str


CENTERS = (
    ExistingCenter('wizard', '✨ Akıllı Ödev Sihirbazı', 'btnSihirbaz',
                   'Mevcut öğrenciye bağlı Akıllı Ödev Sihirbazını açar; aktarma kendi onayıyla yapılır.'),
    ExistingCenter('learning', '🧠 Öğrenme ve Kazanım Teşhisi', 'btnOgrenme',
                   'Mevcut adaptif öğrenme penceresini açar.'),
    ExistingCenter('coach', '🧭 Adaptif Koçluk Merkezi', 'btnAdaptifKocluk',
                   'Mevcut kurum koçluk merkezine geçer; yeni değerlendirme motoru üretmez.'),
    ExistingCenter('weekly', '🗓️ Haftalık Planlayıcı', 'btnPlan',
                   'Mevcut Haftalık Plan düğmesinin aynısını çalıştırır; önizleme/onay kuralları korunur.'),
    ExistingCenter('missing', '⚠️ Eksik Konular', 'btnOneriEksik',
                   'Mevcut Eksikler düğmesini açar.'),
    ExistingCenter('support', '⏰ Takviye Önerileri', 'btnOneriTakviye',
                   'Mevcut Takviye düğmesini açar.'),
    ExistingCenter('detail', '📄 Öğrenci Detay Raporu', 'btnDetayRapor',
                   'Mevcut Rapor düğmesinin işlemini kullanır.'),
    ExistingCenter('audit', '🔎 Veri Bütünlüğü Denetimi', 'btnVeriDenetimi',
                   'Mevcut salt-okunur öğrenci/veri denetimini açar.'),
)


def selected_student_id(form: Any) -> int | None:
    """Read active student ID; never fall back to similar names or first student."""
    try:
        sid = form._secili_ogrenci_id()
        if type(sid) is not int or sid <= 0:
            return None
        return sid
    except (AttributeError, ValueError, TypeError):
        return None


def student_still_current(form: Any, expected_id: int | None) -> bool:
    if expected_id is None or selected_student_id(form) != expected_id:
        return False
    # Require that full-name selectors agree when they are exposed by the form.
    try:
        ad = form.cmbAd.currentData()
        soyad = form.cmbSoyad.currentData()
        if int(ad) != expected_id or int(soyad) != expected_id:
            return False
    except (AttributeError, TypeError, ValueError):
        # A test double / previous-compatible implementation may lack these.
        # We do not bypass an actual mismatch.
        if hasattr(form, 'cmbAd') or hasattr(form, 'cmbSoyad'):
            return False
    return True


def execute_existing(form: Any, key: str, expected_id: int | None) -> bool:
    """Explicit-click only. Return success of *dispatch*, not task outcome."""
    if not student_still_current(form, expected_id):
        _warn(form, 'Öğrenci seçimi değişti veya eşleşmiyor. Öğrenciyi tekrar seçip deneyin.')
        return False
    if key in {'wizard', 'weekly', 'missing', 'support'}:
        # Matrix-dependent workflows must not read previous student's visible cells.
        # Unlike the old form code, the menu does not reset the loaded student.
        try:
            loaded = getattr(form, '_loaded_student_id')
        except AttributeError:
            loaded = expected_id  # older version/test double: legacy handler owns guard
        if loaded != expected_id:
            _warn(form, 'Konu tablosu bu öğrenciye ait değil veya henüz yüklenmemiş. Bilgileri Getir ile yenileyin.')
            return False
    if key == 'student360':
        bridge = getattr(form, '_workspace_v21', None)
        panel = getattr(bridge, 'panel', None)
        if panel is None:
            return False
        # Source V21 sets student using an ID and wipes the previous student's output.
        if getattr(panel, '_student_id', None) != expected_id:
            bridge.selection_changed()
        if not getattr(panel, '_is_open', False):
            bridge.toggle()  # calls the ORIGINAL V21 toggle and responsive update
        elif getattr(panel, '_dirty', False):
            panel.refresh()
        return True
    if key == 'topics':
        bridge = getattr(form, '_workspace_v21', None)
        panel = getattr(bridge, 'panel', None)
        if panel is None:
            return False
        if getattr(panel, '_student_id', None) != expected_id:
            bridge.selection_changed()
        # Existing topic evidence pane; this does not claim preselection of row/topic.
        panel.open_topics()
        return True
    for center in CENTERS:
        if center.key != key:
            continue
        button = getattr(form, center.button, None)
        if button is None or not callable(getattr(button, 'click', None)):
            return False
        if callable(getattr(button, 'isEnabled', None)) and not button.isEnabled():
            return False
        button.click()  # ONE existing callback chain, not a clone of its implementation
        return True
    return False


def _warn(form: Any, message: str) -> None:
    try:
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.warning(form, 'Akıllı Menü · Öğrenci Kontrolü', message)
    except ImportError:
        pass


def available_existing(form: Any, center: ExistingCenter) -> bool:
    button = getattr(form, center.button, None)
    return button is not None and callable(getattr(button, 'click', None))


def install_existing_centers(menu: Any, host: Any):
    """Use standard QMenu APIs so V1's original QAction objects remain intact."""
    sid = selected_student_id(host)
    parent = menu.addMenu('🧭  Mevcut Merkezlere Git · Öğrenci 360° / Koçluk')
    parent.setToolTip('Hazır modüllere kısa yol. Hiçbir işlev yeniden yazılmaz.')
    parent.setToolTipsVisible(True)

    def action(target, label: str, key: str, description: str, available: bool):
        a = target.addAction(label)
        a.setToolTip(description)
        a.setEnabled(sid is not None and available)
        a.triggered.connect(lambda _checked=False, k=key, frozen=sid: execute_existing(host, k, frozen))
        return a

    bridge = getattr(host, '_workspace_v21', None)
    ready_360 = getattr(bridge, 'panel', None) is not None
    action(parent, '🧭 Öğrenci 360° Yan Panelini Aç', 'student360',
           'Zaten mevcut olan V21 Öğrenci 360° yan panelini açar; öğrenci değişmez.', ready_360)
    action(parent, '📎 Öğrencinin Konu Kanıtları', 'topics',
           'Var olan Konu Kanıtları ekranını açar. Sağ tıklanan konuyu otomatik seçmez.', ready_360)
    # v3.5.68: one optional group INSIDE the already-existing right-click
    # menu. Nothing is added to the homework form layout or checkbox handlers.
    # Snapshot is produced asynchronously by the optional research sidecar.
    try:
        from datetime import date
        research = getattr(bridge, 'research_coach', None)
        snapshot_method = getattr(research, 'navigation_recommendations_v3568', None)
        suggested = snapshot_method(sid, date.today()) if callable(snapshot_method) else ()
        if suggested and not isinstance(suggested, tuple):
            suggested = ()
        if suggested:
            import os
            # Opt-out without modifying existing QSettings user preferences.
            enabled = os.environ.get('KOCPILOT_COACH_NAV_V3568', '1').strip().lower()
            try:
                from PyQt6.QtCore import QSettings
                setting = str(QSettings('EduTrack', 'HomeworkManagerV2').value(
                    'coaching_navigation_v3568_enabled', '1')).strip().lower()
            except ImportError:
                setting = '1'  # Headless tests; actual Windows app has Qt.
            if (enabled not in ('0', 'false', 'off', 'no')
                and setting not in ('0', 'false', 'off', 'no')):
                recommendation_menu = parent.addMenu('🧠 Koçluk önerisinden işleme geç')
                recommendation_menu.setToolTipsVisible(True)
                for suggestion in suggested[:2]:
                    if (not isinstance(suggestion, dict)
                        or suggestion.get('student_id') != sid
                        or suggestion.get('as_of') != date.today().isoformat()
                        or suggestion.get('read_only') is not True
                        or suggestion.get('key') not in ('learning','wizard')):
                        continue
                    dest = suggestion['key']
                    button = next((x for x in CENTERS if x.key == dest), None)
                    if button is None:
                        continue
                    action(recommendation_menu, suggestion['label'], dest,
                           str(suggestion.get('detail') or '') +
                           ' · Yalnızca mevcut ekrana geçer; kayıt/aktarım yapmaz.',
                           available_existing(host, button))
    except (AttributeError, TypeError, ValueError, ImportError):
        pass  # Existing navigation remains exactly as before.
    parent.addSeparator()
    for center in CENTERS[:3]:
        action(parent, center.title, center.key, center.explanation, available_existing(host, center))
    planned = parent.addMenu('📅  Planlama / Eksikler / Takviye')
    for center in CENTERS[3:6]:
        action(planned, center.title, center.key, center.explanation, available_existing(host, center))
    reports = parent.addMenu('📄  Raporlar / Veri Denetimi')
    for center in CENTERS[6:]:
        action(reports, center.title, center.key, center.explanation, available_existing(host, center))
    return parent
