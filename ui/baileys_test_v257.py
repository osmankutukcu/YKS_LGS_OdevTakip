# -*- coding: utf-8 -*-
"""V25.7: QR + one recipient test. Separate from queue and bulk sending.

Never stores auth, QR, phone or message; QProcess private standard I/O only.
"""
from __future__ import annotations
import io
import json
import os
import shutil

from PyQt6.QtCore import Qt, QProcess, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QMessageBox, QGroupBox
)
from services.whatsapp_queue.baileys_v257 import bridge_dir, prerequisites


class BaileysSingleTestDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Baileys – kontrollü bağlantı ve TEK mesaj testi')
        self.resize(520, 690)
        self._process = None
        self._out = b''
        self._connected = False
        self._sent = False
        self._qr = None
        layout = QVBoxLayout(self)
        head=QLabel('Baileys kişisel WhatsApp için resmî olmayan bir pilot yöntemdir.\n'
                    'Hesap kısıtlama riski vardır. Bu ekrandan toplu mesaj gönderilemez.')
        head.setWordWrap(True)
        layout.addWidget(head)
        self.status=QLabel('Kontrol bekleniyor.')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.qr=QLabel('QR kodu bağlanınca burada görünecek.')
        self.qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr.setMinimumHeight(310)
        self.qr.setWordWrap(True)
        layout.addWidget(self.qr,1)
        entry=QGroupBox('Tek izinli test alıcısı (gerçek veli / öğrenci numarası kullanmayın)')
        sub=QVBoxLayout(entry)
        self.number=QLineEdit()
        self.number.setPlaceholderText('Örnek biçim: +905XXXXXXXXX')
        sub.addWidget(self.number)
        self.risk=QCheckBox('Riskleri anladım; yalnızca kendi / izinli test numaramı kullanıyorum.')
        sub.addWidget(self.risk)
        layout.addWidget(entry)
        buttons=QHBoxLayout()
        self.connect_btn=QPushButton('QR Bağlantısını Başlat')
        self.send_btn=QPushButton('TEK Test Mesajı Gönder')
        self.send_btn.setEnabled(False)
        self.stop_btn=QPushButton('Durdur')
        buttons.addWidget(self.connect_btn)
        buttons.addWidget(self.send_btn)
        buttons.addWidget(self.stop_btn)
        layout.addLayout(buttons)
        note=QLabel('Mesaj metni sabittir; öğrenci verisi okunmaz. İstemci onayı, teslim onayı değildir.\n'
                    'Oturum diske kaydedilmez; yeni testte QR yeniden istenebilir.')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.connect_btn.clicked.connect(self._start)
        self.send_btn.clicked.connect(self._send)
        self.stop_btn.clicked.connect(self._stop)

    def _status(self, text):
        self.status.setText(text)

    def _start(self):
        ok,why=prerequisites()
        if not ok:
            QMessageBox.information(self,'Baileys pilotu hazır değil',why)
            self._status(why)
            return
        if not self.risk.isChecked():
            QMessageBox.information(self,'Onay gerekiyor','Test risklerini kabul ettiğinizi işaretleyin.')
            return
        if self._process is not None:
            return
        self._connected=False
        self._sent=False
        self._out=b''
        self._qr=None
        self.qr.setText('Bağlantı bekleniyor...')
        process=QProcess(self)
        process.setWorkingDirectory(str(bridge_dir()))
        process.setProgram(shutil.which('node'))
        process.setArguments([str(bridge_dir()/'bridge.mjs')])
        process.readyReadStandardOutput.connect(self._read)
        process.readyReadStandardError.connect(lambda: process.readAllStandardError())
        process.finished.connect(self._finished)
        self._process=process
        self.connect_btn.setEnabled(False)
        self._status('Baileys oturumu başlatılıyor...')
        process.start()
        QTimer.singleShot(185000, self._expiry)

    def _expiry(self):
        if self._process is not None:
            self._status('Bağlantı zaman aşımı. Tekrar test başlatabilirsiniz.')
            self._stop()

    def _read(self):
        if self._process is None:
            return
        self._out += bytes(self._process.readAllStandardOutput())
        if len(self._out)>18000: # QR line bounded, never log raw data.
            self._status('Beklenmeyen bağlantı verisi. Test güvenle durduruldu.')
            self._stop()
            return
        while b'\n' in self._out:
            line,self._out=self._out.split(b'\n',1)
            try:
                msg=json.loads(line.decode('utf8'))
            except (UnicodeError,ValueError):
                continue
            event=msg.get('type')
            if event=='qr':
                self._qr=msg.get('qr')
                try:
                    import qrcode
                    qr=qrcode.QRCode(border=2,box_size=6,error_correction=qrcode.constants.ERROR_CORRECT_M)
                    qr.add_data(self._qr);qr.make(fit=True)
                    img=qr.make_image(fill_color='black',back_color='white')
                    b=io.BytesIO();img.save(b,format='PNG')
                    pix=QPixmap();pix.loadFromData(b.getvalue(),'PNG')
                    self.qr.setPixmap(pix.scaled(310,310,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
                except Exception:
                    self.qr.setText('QR oluşturulamadı. qrcode paketi kurulmalı. Bağlantı durduruldu.')
                    self._stop()
                self._status('Telefonda WhatsApp → Bağlı Cihazlar → Cihaz Bağla. QR kodunu paylaşmayın.')
            elif event=='connected':
                self._connected=True
                self._qr=None
                self.qr.clear()
                self.qr.setText('Bağlantı kuruldu. Henüz mesaj gönderilmedi.')
                self._status('Test WhatsApp bağlantısı kuruldu. Tek mesaj için ayrıca onay gerekiyor.')
                self.send_btn.setEnabled(not self._sent)
            elif event=='attempting':
                self._status('Tek test mesajı gönderilmeye çalışılıyor; tekrar denenmeyecek.')
            elif event=='result':
                self._status('Test sonucu: '+str(msg.get('status','SONUC_BELIRSIZ'))+'; teslimat doğrulanmadı.')
                self.send_btn.setEnabled(False)
            elif event in ('error','stopped','rejected'):
                self._status(str(msg.get('reason','Bağlantı sonlandı.')))
                if event!='rejected':self.send_btn.setEnabled(False)

    def _send(self):
        if self._process is None or not self._connected or self._sent or not self.risk.isChecked():
            return
        from services.whatsapp_queue.queue_v246 import normalize_phone
        phone=normalize_phone(self.number.text(),'90')
        if not phone:
            QMessageBox.warning(self,'Telefon numarası','Yalnızca tek geçerli Türkiye cep numarası girin.')
            return
        reply=QMessageBox.question(self,'SON ONAY',
            'Yalnızca belirtilen izinli numaraya 1 test mesajı gönderim denemesi yapılacak.\n'
            'Teslimatı kendiniz kontrol edeceksiniz. Devam edilsin mi?',
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply!=QMessageBox.StandardButton.Yes:return
        self._sent=True
        self.send_btn.setEnabled(False)
        request={'cmd':'send-test','phone':phone,'approval':'TEK TEST ONAYI'}
        self._process.write((json.dumps(request)+'\n').encode('utf8'))
        self.number.clear()

    def _finished(self,*args):
        self._process=None
        self._connected=False
        self._qr=None
        self.send_btn.setEnabled(False)
        self.connect_btn.setEnabled(True)

    def _stop(self):
        if self._process is not None:
            self._process.write(b'{"cmd":"stop"}\n')
            self._process.terminate()
            # Do not block GUI. Ensure a detached process isn't left holding auth keys.
            process=self._process
            QTimer.singleShot(900,lambda: process.kill() if process.state()!=QProcess.ProcessState.NotRunning else None)
        self.send_btn.setEnabled(False)

    def closeEvent(self,event):
        self._stop()
        super().closeEvent(event)
