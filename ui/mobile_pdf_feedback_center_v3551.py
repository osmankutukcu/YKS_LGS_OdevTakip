# -*- coding: utf-8 -*-
"""Opt-in PyQt feedback inbox. Only constructed with a trusted FeedbackCenter.

No user authentication is invented here. If the desktop application has not
connected an external verified teacher session provider, this screen MUST stay
unavailable. Student/homework tables are never changed by this UI.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTreeWidget,
    QTreeWidgetItem, QComboBox, QMessageBox,
)
from services.mobile_pdf_feedback_center_v3551 import FeedbackCenter, readable_time


class MobileFeedbackCenterDialog(QDialog):
    def __init__(self, parent, center: FeedbackCenter):
        if not isinstance(center, FeedbackCenter):
            raise TypeError('Doğrulanmış öğretmen bildirim merkezi gerekir.')
        super().__init__(parent)
        self.center = center
        self.setWindowTitle('Akıllı PDF — Öğretmen Geri Bildirim Merkezi')
        self.resize(750, 530)
        self.setMinimumSize(520, 380)
        root = QVBoxLayout(self)
        root.setSpacing(10)
        title = QLabel('📥 Öğretmen Geri Bildirim Merkezi')
        title.setStyleSheet('font-size:19px;font-weight:800;color:#173c8b;')
        root.addWidget(title)
        note = QLabel('Öğrenci/veli beyanları yalnızca inceleme içindir. '
                      '“İncelendi” işlemi ödev durumunu, checkbox renklerini veya kilitleri değiştirmez.')
        note.setWordWrap(True)
        root.addWidget(note)
        bar = QHBoxLayout()
        self.status = QLabel('Bağlantı kontrol ediliyor…')
        bar.addWidget(self.status, 1)
        self.filter = QComboBox()
        self.filter.addItem('Bekleyenler', False)
        self.filter.addItem('Tümü', True)
        self.filter.currentIndexChanged.connect(self.refresh)
        bar.addWidget(self.filter)
        self.refresh_btn = QPushButton('↻ Yenile')
        self.refresh_btn.clicked.connect(self.refresh)
        bar.addWidget(self.refresh_btn)
        root.addLayout(bar)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['Öğrenci / bildirim', 'Gönderen', 'Durum', 'Geliş zamanı (UTC)'])
        self.tree.setColumnWidth(0, 260)
        self.tree.setColumnWidth(1, 105)
        self.tree.setColumnWidth(2, 170)
        self.tree.itemSelectionChanged.connect(self._selection)
        root.addWidget(self.tree, 1)
        bottom = QHBoxLayout()
        self.review_btn = QPushButton('✓ Seçileni İncelendi İşaretle')
        self.review_btn.clicked.connect(self.mark_reviewed)
        self.review_btn.setEnabled(False)
        bottom.addWidget(self.review_btn)
        bottom.addStretch()
        close_btn = QPushButton('Kapat')
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)
        root.addLayout(bottom)
        self.auto = QTimer(self)
        self.auto.setInterval(60000)
        self.auto.timeout.connect(self.refresh)
        self.auto.start()
        self.refresh()

    def refresh(self, *_):
        self.review_btn.setEnabled(False)
        self.tree.clear()
        try:
            snap = self.center.snapshot(include_reviewed=self.filter.currentData())
        except Exception:
            self.status.setText('Erişim kapalı: doğrulanmış öğretmen oturumu veya servis bağlantısı gerekli.')
            self.auto.stop()
            self.refresh_btn.setEnabled(False)
            return
        self.refresh_btn.setEnabled(True)
        partial = ' · Son 200 kayıt gösteriliyor (devamı olabilir)' if snap.is_partial else ''
        self.status.setText(f'{snap.pending_count} bekleyen · {snap.reviewed_count} incelenmiş{partial}')
        for group in snap.groups:
            group_item = QTreeWidgetItem([f'{group["label"]} — {group["pending"]} bekleyen'])
            self.tree.addTopLevelItem(group_item)
            for item in group['items']:
                caption = '✓ ' if item['reviewed'] else '• '
                child = QTreeWidgetItem([caption + item['status'], item['recipient'],
                                         item['reason'], readable_time(item['received_at'])])
                child.setData(0, Qt.ItemDataRole.UserRole, (item['id'], item['reviewed']))
                group_item.addChild(child)
            group_item.setExpanded(True)

    def _selection(self):
        selected = self.tree.selectedItems()
        info = selected[0].data(0, Qt.ItemDataRole.UserRole) if selected else None
        self.review_btn.setEnabled(bool(info and not info[1]))

    def mark_reviewed(self):
        selected = self.tree.selectedItems()
        info = selected[0].data(0, Qt.ItemDataRole.UserRole) if selected else None
        if not info or info[1]:
            return
        try:
            result = self.center.review(info[0])
        except Exception:
            QMessageBox.warning(self, 'Erişim reddedildi',
                'Oturum/öğrenci erişimi yeniden doğrulanamadı. Bildirim değiştirilmedi.')
            self.refresh()
            return
        if not result:
            QMessageBox.information(self, 'Bildirim', 'Bu bildirim daha önce incelenmiş.')
        self.refresh()
