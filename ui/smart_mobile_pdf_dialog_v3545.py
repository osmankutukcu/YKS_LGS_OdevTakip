# -*- coding: utf-8 -*-
"""Separate fourth Cep Ajandasi menu action - no change to prior dialogs."""
from __future__ import annotations
import datetime as dt
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QFileDialog, QMessageBox, QApplication
)


class _PDFExportWorker(QThread):
    """Separate read-only DB connection: never share the UI's SQLite cursor."""
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, target, schedule, days, db_path, student_message, parent_message,
                 group_filter="Tümü", days_count=7):
        super().__init__()
        self.target, self.schedule, self.days = target, schedule, days
        self.db_path = db_path
        self.group_filter = group_filter
        self.days_count = days_count
        self.student_message, self.parent_message = student_message, parent_message

    def run(self):
        try:
            from services.mobile_pdf_system_bridge_v3546 import collect_mobile_pdf_context
            from services.smart_mobile_pdf_v3545 import render_smart_pocket_pdf
            if self.days_count > 7:
                from services.mobile_pdf_schedule_range_v3549 import fetch_mobile_pdf_schedule_range
                self.schedule, self.days = fetch_mobile_pdf_schedule_range(
                    self.db_path, group_filter=self.group_filter, days_count=self.days_count)
            context = collect_mobile_pdf_context(self.db_path, self.schedule, self.days)
            result = render_smart_pocket_pdf(
                self.target, self.schedule, self.days,
                student_message=self.student_message,
                parent_message=self.parent_message,
                academic_context=context)
            self.completed.emit({'result':result, 'context':context})
        except Exception:
            # Avoid exposing student data or local DB paths in an error dialog.
            self.failed.emit('PDF hazırlanamadı. Veri bağlantısını ve çıktı klasörünü kontrol edin.')


class SmartMobilePDFDialog(QDialog):
    def __init__(self, parent, generator):
        super().__init__(parent)
        self.generator = generator
        self.setWindowTitle('Akıllı Mobil PDF Asistanı — Ayrı PDF')
        self.setMinimumWidth(445)
        self.setMaximumWidth(600)
        root=QVBoxLayout(self)
        root.setContentsMargins(22,22,22,22)
        root.setSpacing(13)
        title=QLabel('📱  AKILLI MOBİL PDF ASİSTANI')
        title.setWordWrap(True)
        title.setStyleSheet('font-size:20px;font-weight:800;color:#173c8b;')
        root.addWidget(title)
        subtitle=QLabel('Mevcut haftalık PDF ajandanızdan tamamen ayrı hazırlanır. Telefon ekranında rahat okuma, akademik özet, gün/öğrenci dizini ve gerçek WhatsApp/Ara bağlantıları sunar.')
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet('color:#475569;font-size:12px;')
        root.addWidget(subtitle)
        row=QHBoxLayout()
        row.addWidget(QLabel('Hedef grup:'))
        self.group=QComboBox()
        self.group.addItems(['Tümü','YKS','LGS','Ara Sınıf'])
        row.addWidget(self.group,1)
        root.addLayout(row)
        length_row=QHBoxLayout()
        length_row.addWidget(QLabel('Ajanda süresi:'))
        self.days_count=QComboBox()
        self.days_count.addItem('7 gün (mevcut haftalık veri yolu)', 7)
        self.days_count.addItem('10 gün', 10)
        self.days_count.addItem('14 gün', 14)
        length_row.addWidget(self.days_count,1)
        root.addLayout(length_row)
        scope=QLabel('Kapsam: Seçilen günlerdeki kayıtlı teslimler ve koçluk görüşmeleri. '
                     'Dönemlik mesajlar önceden PDF içine hazırlanır ve sonradan değişmez.')
        scope.setWordWrap(True)
        scope.setStyleSheet('color:#64748b;font-size:12px;')
        root.addWidget(scope)
        privacy=QLabel('🔒 ÖNEMLİ: PDF öğrenci adı, ödev ve iletişim bilgisi içerebilir. Yalnızca yetkili kişilere gönderin. PDF içindeki bilgiler oluşturulduğu ana aittir; kendi kendini güncellemez. WhatsApp düğmesi mesajı otomatik göndermez.')
        privacy.setWordWrap(True)
        privacy.setStyleSheet('background:#f3f7ff;border-radius:9px;padding:12px;color:#334155;')
        root.addWidget(privacy)
        live_status=QLabel('🌐 Canlı akademik bağlantılar: Henüz etkin değil. Ayrı bir kimlik doğrulamalı HTTPS sunucu kurulmadan öğrenci verileri internete açılmaz. PDF çevrimdışı çalışmaya devam eder.')
        live_status.setWordWrap(True)
        live_status.setStyleSheet('color:#475569;font-size:11px;padding:6px;')
        root.addWidget(live_status)
        feedback_status=QLabel('↩ Öğrenci / Veli Durum Bildirimi: Güvenli alıcı oturumu ve HTTPS sunucusu bağlanmadan kapalıdır. İleride verilen yanıtlar doğrudan ödevi tamamlamaz; öğretmenin inceleme kuyruğuna düşer.')
        feedback_status.setWordWrap(True)
        feedback_status.setStyleSheet('color:#475569;font-size:11px;padding:6px;')
        root.addWidget(feedback_status)
        # V3.5.51: A separate review surface. It does not enable the web gateway,
        # fabricate a teacher session or write to the homework database.
        inbox_button = QPushButton('📥 Öğretmen Geri Bildirim Merkezi')
        inbox_button.setToolTip('Öğrenci/veli beyanlarını öğretmen onayıyla incele')
        inbox_button.clicked.connect(self._open_feedback_center)
        root.addWidget(inbox_button)
        actions=QHBoxLayout()
        self.create=QPushButton('📄 Ayrı Mobil PDF Oluştur ve Aç')
        self.create.setCursor(Qt.CursorShape.PointingHandCursor)
        self.create.setStyleSheet('background:#1d4ed8;color:white;font-weight:800;padding:12px;border-radius:8px;')
        self.create.clicked.connect(self._export)
        self._worker = None
        actions.addWidget(self.create,1)
        cancel=QPushButton('Kapat')
        cancel.clicked.connect(self.close)
        actions.addWidget(cancel)
        root.addLayout(actions)

    def _open_feedback_center(self):
        """Explicit auth-provider boundary; never infer identities from student data.

        The host application may provide a *verified* session bridge named
        mobile_pdf_feedback_center_provider on the main window. Until this
        integration exists, the inbox stays disabled instead of granting
        unauthenticated access to other students' responses.
        """
        provider = getattr(self.generator.parent, 'mobile_pdf_feedback_center_provider', None)
        if not callable(provider):
            QMessageBox.information(self, 'Öğretmen Geri Bildirim Merkezi',
                'Canlı geri bildirim merkezi henüz etkin değil. '
                'Kuruma ait doğrulanmış öğretmen oturumu ve güvenli HTTPS servis bağlantısı gerekir. '
                'WhatsApp, Ara ve mevcut PDF işlemleri normal şekilde kullanılabilir.')
            return
        try:
            from services.mobile_pdf_feedback_center_v3551 import FeedbackCenter
            center = provider()
            if not isinstance(center, FeedbackCenter):
                raise PermissionError('Oturum servisi hazır değil.')
            # Force an authorization check *before* opening any UI.
            center.snapshot(include_reviewed=False, limit=1)
            from ui.mobile_pdf_feedback_center_v3551 import MobileFeedbackCenterDialog
            dialog = MobileFeedbackCenterDialog(self, center)
            dialog.exec()
        except Exception:
            QMessageBox.warning(self, 'Erişim kapalı',
                'Öğretmen oturumu veya yanıt servis bağlantısı doğrulanamadı. '
                'Güvenli erişim kurulmadan öğrenci yanıtları görüntülenmez.')

    def _export(self):
        if self._worker is not None and self._worker.isRunning():
            return
        file_name = f'akilli_mobil_pdf_asistani_{dt.date.today():%Y_%m_%d}.pdf'
        target, _ = QFileDialog.getSaveFileName(self, 'Ayrı Mobil PDF Kaydet', file_name, 'PDF (*.pdf)')
        if not target:
            return
        if not target.lower().endswith('.pdf'):
            target += '.pdf'
        try:
            # Only the preexisting schedule is queried on the UI thread.
            # The new independent bridge opens its own read-only connection.
            import db
            period = self.days_count.currentData()
            if period == 7:
                schedule, days = self.generator._fetch_data(
                    group_filter=self.group.currentText(), include_all_active=False)
            else:
                schedule, days = None, None
            self._worker = _PDFExportWorker(target, schedule, days, db.DB_PATH,
                                            self.generator._build_msg_single,
                                            self.generator._build_parent_msg,
                                            group_filter=self.group.currentText(), days_count=period)
            self._worker.completed.connect(self._export_completed)
            self._worker.failed.connect(self._export_failed)
            self._worker.finished.connect(self._export_cleanup)
            self.create.setEnabled(False)
            self.group.setEnabled(False)
            self.days_count.setEnabled(False)
            self.create.setText('⏳ PDF güvenli biçimde hazırlanıyor…')
            self._worker.start()
        except Exception:
            self._export_failed('Ajanda verileri okunamadı. Kaynak bağlantılarını kontrol edin.')

    def _export_cleanup(self):
        self.create.setEnabled(True)
        self.group.setEnabled(True)
        self.days_count.setEnabled(True)
        self.create.setText('📄 Ayrı Mobil PDF Oluştur ve Aç')
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

    def _export_completed(self, payload):
        result, ctx = payload['result'], payload['context']
        status = 'Kısmi / doğrulama gerekli' if ctx['source_state'] != 'LOCAL_VERIFIED' else 'Yerel kayıtlar doğrulandı'
        QMessageBox.information(self, 'Mobil PDF oluşturuldu',
            f'{result["students"]} öğrenci · {result["pages"]} sayfa\n'
            f'Akademik kayıt kontrolü: {ctx["verified_count"]}/{ctx["student_count"]}\n'
            f'Durum: {status}\n\n{result["path"]}')
        self.generator._open_file(result['path'])

    def _export_failed(self, message):
        QMessageBox.warning(self, 'PDF oluşturulamadı', message)

    def closeEvent(self, event):
        # Prevent deleting a live QThread whose writer is still in progress.
        if self._worker is not None and self._worker.isRunning():
            event.ignore()
            return
        super().closeEvent(event)
