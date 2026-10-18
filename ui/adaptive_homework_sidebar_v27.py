# -*- coding: utf-8 -*-
"""Opt-in right side view; no legacy assignment, checkbox, or save handlers.

Only real learner evidence goes into the recommendation UI. The independent
V25 dialog remains responsible for capturing evidence and proposing plans.
"""
from __future__ import annotations
import sqlite3
from contextlib import closing
from urllib.parse import quote
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTabWidget,
    QScrollArea, QFrame, QMessageBox, QSizePolicy, QApplication,
)
from services.adaptive_coaching_v27.presenter import sidebar_data


class AdaptiveHomeworkSidebarV27(QWidget):
    def __init__(self, host, parent=None):
        super().__init__(parent)
        self.host = host
        self._student_id = None
        self._dirty = True
        self._active = False
        self._cached = None
        self.setObjectName('adaptiveSidebarV27')
        self.setMinimumWidth(265)
        self.setStyleSheet('''
          QWidget#adaptiveSidebarV27 {background:#f8fafc;}
          QLabel {color:#233047; background:transparent;}
          QFrame#coachCardV27 {border:1px solid #dce4ef;border-radius:9px;
            background:#ffffff;}
          QPushButton {padding:6px 9px; background:#fff; border:1px solid #cbd5e1;
            border-radius:6px; color:#334155; font-weight:600;}
          QPushButton:hover {background:#eff6ff; border-color:#93c5fd;
                color: #15191E;}
          QTabWidget::pane {border:none;background:#f8fafc;}
          QTabBar::tab {padding:7px 9px; font-size:11px;}
          QTabBar::tab:selected {color:#1d4ed8;font-weight:700;}
        ''')
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 7, 8, 7)
        root.setSpacing(6)
        header = QHBoxLayout()
        header.addWidget(self._heading('🧠 Adaptif Koçluk', 14), 1)
        btn_close = QPushButton('✕')
        btn_close.setFixedWidth(28)
        btn_close.setToolTip('Verilen ödevlere geri dön')
        btn_close.clicked.connect(self.return_to_assignments)
        header.addWidget(btn_close)
        root.addLayout(header)
        self.identity = QLabel('Öğrenci seçiniz')
        self.identity.setWordWrap(True)
        root.addWidget(self.identity)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.blocks = {}
        for caption in ('Genel Bakış', 'Öneriler', 'Tekrar', 'Tıkanıklık'):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            inner = QWidget()
            stack = QVBoxLayout(inner)
            stack.setContentsMargins(2, 9, 2, 6)
            stack.setSpacing(8)
            stack.addStretch(1)
            scroll.setWidget(inner)
            self.tabs.addTab(scroll, caption)
            self.blocks[caption] = stack
        footer = QHBoxLayout()
        b_refresh = QPushButton('↻ Yenile')
        b_refresh.clicked.connect(self.refresh)
        footer.addWidget(b_refresh)
        b_observation = QPushButton('🔎 Kazanım Teşhisi')
        b_observation.clicked.connect(lambda: self.open_v25('Kazanım Teşhisi'))
        footer.addWidget(b_observation)
        root.addLayout(footer)
        self._reset('Bu panel salt okunurdur. Ödev verme, kontrol ve kaydetme işlemlerini değiştirmez.')

    @staticmethod
    def _heading(text, size=12):
        l = QLabel(text)
        l.setWordWrap(True)
        l.setStyleSheet(f'font-weight:750;font-size:{size}px;color:#142b4b;')
        return l

    @staticmethod
    def _plain(text, *, subdued=False):
        l = QLabel(str(text))
        l.setWordWrap(True)
        l.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        if subdued:
            l.setStyleSheet('color:#64748b;font-size:11px;')
        return l

    def _clear_tab(self, name):
        layout = self.blocks[name]
        # Clear children except the stretch at the bottom.
        while layout.count() > 1:
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # Only add direct widgets to avoid recursively clearing nested items.
                pass

    def _card(self, tab, title, lines, *, button=None, callback=None):
        card = QFrame()
        card.setObjectName('coachCardV27')
        lay = QVBoxLayout(card)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(5)
        lay.addWidget(self._heading(title))
        for line in lines:
            lay.addWidget(self._plain(line))
        if button and callback:
            btn = QPushButton(button)
            btn.clicked.connect(callback)
            lay.addWidget(btn)
        self.blocks[tab].insertWidget(self.blocks[tab].count() - 1, card)

    def _reset(self, message):
        for name in self.blocks:
            self._clear_tab(name)
        self._card('Genel Bakış', 'Bilgi', [message])
        self._cached = None

    def set_student(self, sid):
        sid = int(sid) if type(sid) is int and sid > 0 else None
        if self._student_id == sid:
            return
        self._student_id = sid
        self._dirty = True
        self.identity.setText('Öğrenci verisi bekleniyor…' if sid else 'Öğrenci seçiniz')
        # Clear all old student information synchronously (privacy safety).
        self._reset('Öğrenci seçildi; güncel analiz hazırlanıyor.' if sid else 'Önce öğrenci seçiniz.')
        if self._active:
            QTimer.singleShot(0, lambda expected=sid: self._refresh_current(expected))

    def _refresh_current(self, expected):
        if self._active and self._student_id == expected and self._dirty:
            self.refresh()

    def set_active(self, active):
        self._active = bool(active)
        if active and self._dirty:
            self.refresh()

    def mark_dirty(self):
        self._dirty = True
        if self._active:
            QTimer.singleShot(0, lambda expected=self._student_id: self._refresh_current(expected))

    def refresh(self):
        sid = self._student_id
        self._dirty = False
        if not self._active or sid is None:
            if sid is None:
                self.identity.setText('Öğrenci seçiniz')
                self._reset('Önce öğrenci seçiniz.')
            else:
                self._dirty = True
            return
        try:
            from db import DB_PATH
            uri = 'file:' + quote(str(DB_PATH.resolve()), safe='/') + '?mode=ro'
            with closing(sqlite3.connect(uri, uri=True, timeout=4)) as con:
                con.row_factory = sqlite3.Row
                con.execute('PRAGMA query_only=ON')
                data = sidebar_data(con, sid)
        except (sqlite3.Error, OSError, ValueError, KeyError) as exc:
            self._dirty = True  # Later toggles can retry a temporary database read error.
            if sid == self._student_id:
                self._reset('Öğrenme özeti okunamadı. Mevcut ödevler etkilenmedi.\n' + str(exc))
            return
        if sid != self._student_id or not self._active:
            return
        self._cached = data
        self.identity.setText(f"{data['name']} · Öğretmen karar desteği")
        for name in self.blocks:
            self._clear_tab(name)
        m = data['metrics']
        self._card('Genel Bakış', 'Öğrenme Kanıtı', [
            f"{data['evidence_count']} gözlem · {m.get('measured', 0)} ölçülen konu",
            f"{m.get('without_evidence', 0)} konu için yeni ölçüm öneriliyor.",
            'Ödevin bitmiş olması öğrenmenin kanıtı değildir.',
        ])
        journey = data.get('learning_journey_v34')
        if journey is not None:
            lead = journey['priorities'][0]
            self._card('Genel Bakış', '🔗 V34 · Öğrenme Döngüsü', [
                journey['evidence_label'],
                f"Öncelik: {lead['title']}",
                f"Sonraki adım: {lead['next_step']}",
                'Ödev verme ve Kaydet işlemleri değiştirilmez.',
            ])
        self._card('Genel Bakış', '💡 Bugünün Önceliği', [
            data['actions'][0]['title'] if data['actions'] else data['status'],
            data['actions'][0]['next_step'] if data['actions'] else data['guidance'],
        ], button='Kazanım Teşhisi Aç', callback=lambda: self.open_v25('Kazanım Teşhisi'))
        # V29: compact, teacher-reviewed next step; source is an explicit V28 note.
        if data.get('next_steps'):
            next_item = data['next_steps'][0]
            self._card('Genel Bakış', '🧠 Kontrol Sonrası Sonraki Adım', [
                next_item['lesson']+' / '+next_item['topic'],
                next_item['title']+': '+next_item['next_step'],
                'Öğretmen notu temelli öneri; ödevleri veya tikleri değiştirmez.',
            ])
        self._card('Genel Bakış', 'Spiral Çalışma • Öneri Ayarı', [
            f"%{data['suggested_current_percent']} güncel odak + %{data['suggested_review_percent']} tekrar",
            f"Haftalık hedef: {data['weekly_minutes']} dk · Oturum: {data['suggested_session_minutes']} dk",
            'Bu bir öneri oranıdır; uygulanmış ödev dağılımı değildir.',
        ], button='Taslak Ödev Hazırla', callback=lambda: self.open_v25('Spiral Ödev Taslağı'))
        # V30: an OPTIONAL review window; normal Verilen Ödevler stays alive.
        try:
            from services.adaptive_coaching_v30.flags import enabled as v30_enabled
            if v30_enabled() and callable(getattr(self.host, '_wizard_transfer_tasks', None)):
                self._card('Genel Bakış', '⚡ V30 · Öğretmen Onaylı Taslak', [
                    'Mevcut kazanım ve ödev kayıtlarından kısa bir taslak göster.',
                    'Kitap/konu eşleşmesini kontrol et; yalnızca seçtiklerin eski tik akışına eklenir.',
                    'Aktarım otomatik Kaydet değildir; tek tıkla geri alınabilir.'
                ], button='Taslağı İncele ve Seç', callback=self.open_v30)
        except ImportError:
            pass  # An optional module must never break the homework sidebar.
        ctx = data['context']
        if ctx:
            self._card('Genel Bakış','Hedef ve Koçluk',[
                f"Hedef: {ctx.get('target','—')}",
                f"Haftalık plan: {ctx.get('coaching_plan','—')}",
            ])
        self._card('Genel Bakış','Öğretmen Onayı',[
            'Öneriler kendiliğinden ödev yazmaz, tikleri değiştirmez veya ödev borcunu devretmez.'
        ], button='Verilen Ödevleri Göster', callback=self.return_to_assignments)
        for suggestion in data.get('next_steps', []):
            self._card('Öneriler', '🧠 '+suggestion['title']+' · '+suggestion['topic'], [
                suggestion['reason'], suggestion['next_step'],
                'Dayanak: son 14 günün açık öğretmen notu; öğretmen onayı gerekir.'
            ])
        if data['actions']:
            for action in data['actions']:
                self._card('Öneriler',f"{action['category']} · {action['title']}",[
                    action['reason'], f"Önerilen adım: {action['next_step']}",
                    f"Veri kaynağı: {action['source']}"
                ])
        else:
            self._card('Öneriler','Henüz öneri yok',[data['guidance']])
        if data['groups']['Aralıklı tekrar']:
            for item in data['groups']['Aralıklı tekrar']:
                self._card('Tekrar',item['title'],[item['reason'], item['next_step']])
        else:
            self._card('Tekrar','Tekrar Zamanı',[
                'Kaydedilmiş ölçüm tarihlerine göre bugün için belirlenmiş tekrar önerisi yok.',
                'Öğrenme kanıtı yoksa varsayımsal 2. veya 4. hafta tarihleri gösterilmez.',
            ])
        # V28 optional one-click notes; not classified as proof of mastery.
        for item in data.get('quick_notes', []):
            self._card('Tıkanıklık', '⚡ '+item['label'], [
                f"{item['lesson']} / {item['topic']}",
                'Öğretmen hızlı notu; öğrenme düzeyi veya psikolojik tanı değildir.',
            ])
        if data['blockers']:
            for item in data['blockers']:
                self._card('Tıkanıklık',item['reason'],[
                    item['detail'] or 'Ayrıntı belirtilmedi.',
                    'Koç müdahalesi: ' + item['resolution'],
                ])
        elif not data.get('quick_notes'):
            self._card('Tıkanıklık','Tıkanıklık Kaydı Yok',[
                'Son 14 günde bu öğrenci için kayıtlı tıkanıklık bulunmadı.',
                'Bu durum öğrencinin zorluk yaşamadığının kanıtı değildir.',
            ], button='Tıkanıklık Kaydet', callback=lambda: self.open_v25('Tıkanıklık'))

    def open_v25(self, tab_name):
        sid = self._student_id
        # Guard against switching to another learner while the view is open.
        if sid is None or int(self.host._secili_ogrenci_id() or 0) != sid:
            QMessageBox.warning(self,'Öğrenci değişti','Önce öğrenciyi yeniden seçip analizi yenileyin.')
            return
        try:
            from ui.adaptive_coaching_dialog_v25 import AdaptiveCoachingDialogV25
            dlg = AdaptiveCoachingDialogV25(sid, parent=self, host=self.host)
            for i in range(dlg.tabs.count()):
                if dlg.tabs.tabText(i) == tab_name:
                    dlg.tabs.setCurrentIndex(i)
                    break
            dlg.exec()
            self.mark_dirty()
        except Exception as exc:
            QMessageBox.warning(self,'Adaptif Koçluk',f'Modül açılamadı; mevcut ödevler değişmedi.\n{exc}')

    def open_v30(self):
        sid = self._student_id
        if sid is None or int(self.host._secili_ogrenci_id() or 0) != sid:
            QMessageBox.warning(self, 'Öğrenci değişti',
                                'Önce öğrenciyi yeniden seçip analizi yenileyin.')
            return
        try:
            from services.adaptive_coaching_v30.flags import enabled as enabled_v30
            if not enabled_v30():
                return
            from ui.adaptive_draft_review_v30 import AdaptiveDraftReviewV30
            AdaptiveDraftReviewV30(sid, self.host, parent=self).exec()
            self.mark_dirty()
        except Exception as exc:
            QMessageBox.warning(self, 'Ödev Taslağı',
                'Taslak açılamadı. Mevcut ödevler değişmedi.\n' + str(exc))

    def return_to_assignments(self):
        switch = getattr(self.host,'_adaptive_bridge_v27',None)
        if switch is not None:
            switch.show_assignments()
