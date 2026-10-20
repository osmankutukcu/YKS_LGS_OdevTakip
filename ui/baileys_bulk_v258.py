# -*- coding: utf-8 -*-
"""V25.8 Windows-only, explicit-consent Baileys batch wizard.

All events are processed in the GUI event loop. No GUI freeze, data DB writes
or changes to Homework Follow-up / Homework Control source files.
"""
from __future__ import annotations

import io
import json
import os
import shutil
from pathlib import Path

from PyQt6.QtCore import Qt, QProcess, QProcessEnvironment, QTimer, QUrl
from PyQt6.QtGui import QPixmap, QDesktopServices
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QProgressBar, QPushButton, QVBoxLayout,
)

from services.whatsapp_queue.baileys_runtime_v3576 import (
    detect_runtime, enriched_path, setup_failure_message,
)
from services.whatsapp_queue.queue_v246 import (
    SafeWhatsAppQueue, queue_path_for, QueueBusyError, PENDING, INVALID,
    FAILED, UNKNOWN, UI_UNVERIFIED,
)
from services.whatsapp_queue.baileys_bulk_v258 import (
    SuppressionRegistry, BatchValidationError, bulk_prerequisites,
    prepare_recipients, masked_phone, MAX_RECIPIENTS, TRANSPORT_MARKER,
    mark_batch, batch_transport, open_baileys_queue, bulk_bridge_dir, stage_bulk_bridge,
)

# This pacing is a conservative default, NOT a guarantee that WhatsApp won't
# restrict the account. The bridge additionally enforces a 15-second floor.
PACE_MS = 20000


class BaileysBulkDialog(QDialog):
    def __init__(self, parent, db_path: str, appdata_dir: str,
                 raw_jobs: list[dict] | None = None, resume_batch: str | None = None):
        super().__init__(parent)
        if (raw_jobs is None) == (resume_batch is None):
            raise ValueError('Yeni işler veya eski parti seçilmelidir')
        self.setWindowTitle('V25.8 – Baileys izinli toplu gönderim')
        self.resize(680, 750)
        self.setMinimumWidth(530)
        self.db_path = db_path
        self.q = open_baileys_queue(db_path, appdata_dir)
        self.suppressed = SuppressionRegistry(os.path.join(appdata_dir, 'wa_iptal_v258.json'))
        self._resume_batch = resume_batch
        self._batch = None
        self._lock = None
        self._process = None
        self._setup_process = None
        self._setup_phase = ''
        self._buffer = b''
        self._active = None
        self._connected = False
        self._halting = False
        self._started = False
        self._scheduled = False
        self._jobs = []
        self._skips = {}
        self._raw_jobs = raw_jobs

        if resume_batch:
            if batch_transport(self.q, resume_batch) != TRANSPORT_MARKER:
                raise BatchValidationError('Bu parti Baileys toplu gönderimine ait değil')
            records = self.q.rows(resume_batch)
            if len(records) > MAX_RECIPIENTS:
                raise BatchValidationError('Kaydedilmiş parti güvenlik sınırını aşıyor')
            self._jobs = [r for r in records if r['state'] == PENDING]
        else:
            self._refresh_candidates()

        layout = QVBoxLayout(self)
        title = QLabel('İzinli WhatsApp alıcıları – 1–150 telefon / parti')
        title.setStyleSheet('font-size: 16px; font-weight: 600;')
        layout.addWidget(title)
        self.info = QLabel('Baileys resmî API değildir. Hesap kısıtlaması mümkündür. '\
                           'Yalnızca WhatsApp üzerinden bilgilendirme izni olan veli/öğrencilere gönderin. '\
                           'Teslimat garantisi yoktur.')
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMaximumHeight(160)
        layout.addWidget(self.preview)

        optout = QHBoxLayout()
        self.reject_number = QLineEdit()
        self.reject_number.setPlaceholderText('Mesaj istemeyen numarayı buraya yazın (kalıcı hariç tut)')
        self.reject_button = QPushButton('Ret listesine ekle')
        self.reject_button.clicked.connect(self._add_suppressed)
        optout.addWidget(self.reject_number, 1)
        optout.addWidget(self.reject_button)
        layout.addLayout(optout)

        self.approval = QCheckBox('Seçilen HER alıcının bu WhatsApp bildirimleri için izni olduğunu '
                                  've ret taleplerini kontrol ettiğimi onaylıyorum.')
        self.approval.setToolTip('Alıcı rızası sistem tarafından varsayılmaz; gönderici teyit etmelidir.')
        layout.addWidget(self.approval)
        self.qr = QLabel('Başlatıldığında bağlantı QR kodu burada görünecek.')
        self.qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr.setMinimumHeight(290)
        self.qr.setWordWrap(True)
        layout.addWidget(self.qr, 1)
        self.status = QLabel('Henüz hiçbir mesaj gönderilmedi.')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        row = QHBoxLayout()
        self.setup_btn = QPushButton('Baileys Windows Motorunu Kur / Güncelle')
        self.setup_btn.clicked.connect(self._install)
        layout.addWidget(self.setup_btn)
        self.start_btn = QPushButton('İzinli partiyi başlat / QR')
        self.stop_btn = QPushButton('Durdur / kalanları beklet')
        self.done_btn = QPushButton('Kapat')
        self.stop_btn.setEnabled(False)
        row.addWidget(self.start_btn)
        row.addWidget(self.stop_btn)
        row.addWidget(self.done_btn)
        layout.addLayout(row)
        self.start_btn.clicked.connect(self._start)
        self.stop_btn.clicked.connect(self._stop)
        self.done_btn.clicked.connect(self.close)
        self._update_preview()

    def _refresh_candidates(self):
        self._jobs, self._skips = prepare_recipients(self._raw_jobs, '90', self.suppressed)

    def _update_preview(self):
        pending = len(self._jobs)
        totals = self._skips
        lines = [f'Seçili farklı alıcı: {pending}',
                 f'Atlanan: geçersiz {totals.get("invalid",0)} · ret {totals.get("excluded",0)} · '
                 f'çakışan aile telefonu {totals.get("shared_phone",0)} · '
                 f'boş/uzun metin {totals.get("oversize_or_empty",0)} · '
                 f'aynı kayıt {totals.get("duplicate",0)}',
                 'Görüntülenen numaralar gizlenmiştir; mesajı ana pencerede kontrol edin.', '']
        for item in self._jobs[:MAX_RECIPIENTS]:
            lines.append(f"• {masked_phone(item['recipient'])} / öğrenci #{item.get('student_id','?')}")
        if self._jobs:
            sample = str(self._jobs[0].get('message', '')).replace('\n', ' ↵ ')
            lines.extend(['', 'İlk alıcı için mesaj örneği (en fazla 220 karakter):', sample[:220]])
        self.preview.setPlainText('\n'.join(lines))
        self.progress.setMaximum(max(pending,1))
        self.progress.setValue(0)

    def _add_suppressed(self):
        if self._started:
            QMessageBox.information(self, 'Ret kaydı', 'Gönderim sürerken yeni ret kaydını sonraki partiden önce ekleyin.')
            return
        try:
            self.suppressed.add(self.reject_number.text())
            self.reject_number.clear()
            if self._raw_jobs is not None:
                self._refresh_candidates()
            else:
                self._jobs = [j for j in self._jobs if not self.suppressed.contains(j['recipient'])]
            self._update_preview()
        except (ValueError, OSError) as e:
            QMessageBox.warning(self, 'Ret listesi', str(e))

    def _install(self):
        """One consented setup; detect Node/npm before initiating npm operations."""
        if self._started or self._setup_process is not None:
            return
        runtime = detect_runtime()
        if not runtime.ready:
            if not runtime.winget:
                answer = QMessageBox.question(
                    self, 'Node.js kurulumu gerekiyor',
                    runtime.reason + '\n\nBu bilgisayarda otomatik Windows paket yöneticisi '
                    '(winget) bulunamadı. Resmî Node.js indirme sayfası açılsın mı? '
                    'Kurulumdan sonra tekrar Kur / Güncelle düğmesine basabilirsiniz.',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes)
                if answer == QMessageBox.StandardButton.Yes:
                    QDesktopServices.openUrl(QUrl('https://nodejs.org/en/download'))
                self.status.setText(runtime.reason)
                return
            if QMessageBox.question(
                    self, 'Node.js LTS otomatik kurulum izni',
                    runtime.reason + '\n\nWindows paket yöneticisi (winget), resmî '
                    'OpenJS.NodeJS.LTS paketini indirecek ve yalnızca bu Windows '
                    'kullanıcısı için kurmayı deneyecek. Ağ bağlantısı gereklidir; '
                    'gerekirse Windows ayrıca izin isteyebilir. '
                    'Bu işlem WhatsApp mesajı göndermez. Devam edilsin mi?',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return
            self._run_setup_process('node', runtime.winget,
                                    ['install', '--id', 'OpenJS.NodeJS.LTS', '--exact',
                                     '--scope', 'user', '--silent',
                                     '--accept-package-agreements', '--accept-source-agreements'],
                                    'Node.js LTS kuruluyor; işlem biraz sürebilir.')
            return
        self._confirm_dependencies(runtime)

    def _confirm_dependencies(self, runtime):
        if QMessageBox.question(
                self, 'Baileys bağımlılıkları',
                f'{runtime.node_version} ve npm doğrulandı.\n'
                'Yalnızca kullanıcı profilindeki Baileys klasörüne, sabitlenmiş '
                'paketlerin npm üzerinden kurulmasına ve gönderimsiz protokol '
                'testlerinin çalıştırılmasına izin veriyor musunuz?\n'
                'WhatsApp hesabınıza bağlanılmayacak; mesaj gönderilmeyecek.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        self._begin_dependency_setup(runtime)

    def _begin_dependency_setup(self, runtime):
        try:
            folder = stage_bulk_bridge()
        except Exception as exc:
            QMessageBox.warning(self, 'Kurulum dosyaları', str(exc))
            return
        child_env = QProcessEnvironment.systemEnvironment()
        child_env.insert('PATH', enriched_path(runtime, child_env.value('PATH')))
        child_env.insert('BAILEYS_SETUP_APPROVED', '1')
        self._run_setup_process('deps', os.environ.get('ComSpec', 'cmd.exe'),
                                ['/d', '/c', str(folder / 'Windows_Hazirla_V258.cmd')],
                                'Baileys paketleri hazırlanıyor ve protokol testleri yapılıyor.',
                                cwd=str(folder), process_env=child_env)

    def _run_setup_process(self, phase, program, arguments, description,
                           cwd=None, process_env=None):
        self._setup_phase = phase
        self.setup_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.status.setText(description)
        self.qr.setText('Kurulum sürüyor. Gönderim başlatılamaz.')
        proc = QProcess(self)
        if cwd:
            proc.setWorkingDirectory(cwd)
        if process_env is not None:
            proc.setProcessEnvironment(process_env)
        proc.setProgram(program)
        proc.setArguments(arguments)
        # Never show raw npm / Node output; future logs might include local paths.
        proc.readyReadStandardOutput.connect(lambda: proc.readAllStandardOutput())
        proc.readyReadStandardError.connect(lambda: proc.readAllStandardError())
        proc.finished.connect(self._setup_finished)
        proc.errorOccurred.connect(self._setup_error)
        self._setup_process = proc
        proc.start()
        # Do not allow a stuck external installer to block the dialog forever.
        QTimer.singleShot(300000, lambda: self._setup_timeout(proc))

    def _setup_timeout(self, proc):
        if self._setup_process is proc and proc.state() != QProcess.ProcessState.NotRunning:
            proc.kill()
            self.status.setText('Kurulum zaman aşımına uğradı. Hiçbir mesaj gönderilmedi.')

    def _setup_error(self, _error):
        proc = self._setup_process
        if proc is not None:
            self.status.setText('Kurulum işlemi Windows tarafından başlatılamadı. '
                                'Yetkileri ve sistem paket yöneticisini kontrol edin.')
            if proc.state() == QProcess.ProcessState.NotRunning:
                QTimer.singleShot(0, lambda: self._setup_finished(-1, QProcess.ExitStatus.CrashExit)
                                  if self._setup_process is proc else None)

    def _setup_finished(self, exit_code, exit_status):
        if self._setup_process is None:
            return
        phase = self._setup_phase
        proc = self._setup_process
        self._setup_process = None
        self._setup_phase = ''
        proc.deleteLater()
        self.setup_btn.setEnabled(True)
        self.start_btn.setEnabled(True)
        success = (exit_code == 0 and exit_status == QProcess.ExitStatus.NormalExit)
        if not success:
            self.status.setText(
                setup_failure_message(phase, exit_code)
                + f' (Kod: {exit_code}). Hiçbir mesaj gönderilmedi.')
            QMessageBox.warning(self, 'Kurulum tamamlanamadı', self.status.text())
            return
        if phase == 'node':
            runtime = detect_runtime()
            if not runtime.ready:
                self.status.setText('Windows paket kurulumu tamamlandı fakat Node.js/npm '
                                    'doğrulanamadı. Programı yeniden açın veya Node.js '
                                    'LTS kurulumunu onarın. Hiçbir mesaj gönderilmedi.')
                return
            self.status.setText('Node.js bulundu. Baileys paketleri için ayrıca izin gerekiyor.')
            self._confirm_dependencies(runtime)
            return
        ok, explanation = bulk_prerequisites()
        if ok:
            self.status.setText('Baileys motoru ve testler hazır. '
                                'WhatsApp eşleştirmesi ve gönderim için ayrıca açık onay gereklidir.')
            self.qr.setText('Hazır. QR bağlantısını ayrı düğmeden başlatabilirsiniz.')
            QMessageBox.information(self, 'Kurulum doğrulandı', self.status.text())
        else:
            self.status.setText('Kurulum işlemi sonlandı fakat güvenlik kontrolü başarısız: '
                                + explanation + ' Hiçbir mesaj gönderilmedi.')
            QMessageBox.warning(self, 'Motor henüz hazır değil', self.status.text())

    def _start(self):
        if self._setup_process is not None:
            QMessageBox.information(self, 'Kurulum sürüyor', 'Kurulum tamamlanmadan gönderim başlatılamaz.')
            return
        if self._started or not self._jobs:
            QMessageBox.information(self, 'Alıcı', 'İşlenecek izinli alıcı bulunamadı.')
            return
        if not self.approval.isChecked():
            QMessageBox.warning(self, 'İzin onayı', 'Her alıcının önceden verdiği izni doğrulayın.')
            return
        ok,reason = bulk_prerequisites()
        if not ok:
            QMessageBox.warning(self, 'Windows Baileys bileşeni hazır değil', reason)
            return
        if QMessageBox.question(self, 'Son gönderim onayı',
                f'{len(self._jobs)} farklı alıcı için otomatik gönderim denemesi yapılacak. '\
                'WhatsApp hesabınızın kısıtlanması mümkündür. '\
                'İşlenen alıcılar ASLA kendiliğinden tekrar denenmeyecek. '\
                'Tüm alıcıların izinli olduğunu onaylıyor musunuz?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            self._lock = self.q.acquire_lock()
            if self._resume_batch:
                self._batch = self._resume_batch
            else:
                if self.q.current_batch(self.db_path):
                    raise BatchValidationError('Eski kuyrukta bekleyen işler var. Önce bu kuyruğu gözden geçirin.')
                self._batch = self.q.create_batch(self.db_path, self._jobs)
                mark_batch(self.q, self._batch)
            self.q.recover_interrupted(self._batch)
            if self.q.counts(self._batch).get(PENDING, 0) < 1:
                raise BatchValidationError('Bekleyen iş kalmadı')
        except Exception as exc:
            self._unlock()
            QMessageBox.warning(self, 'Kuyruk koruması', str(exc))
            return
        self._started = True
        self.start_btn.setEnabled(False)
        self.setup_btn.setEnabled(False)
        self.reject_button.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.done_btn.setEnabled(False)
        self.approval.setEnabled(False)
        self.status.setText('Baileys oturumu açılıyor; QR kodunu yalnızca kendi telefonunuzdan okutun.')
        self._buffer = b''
        process = QProcess(self)
        process.setWorkingDirectory(str(bulk_bridge_dir()))
        runtime = detect_runtime()
        if not runtime.ready:
            self._unlock()
            self._started = False
            self.start_btn.setEnabled(True)
            self.setup_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.done_btn.setEnabled(True)
            self.approval.setEnabled(True)
            self.reject_button.setEnabled(True)
            self.status.setText(runtime.reason)
            return
        process.setProgram(runtime.node)
        process.setArguments([str(bulk_bridge_dir() / 'bulk_bridge_v258.mjs')])
        process.readyReadStandardOutput.connect(self._read)
        process.readyReadStandardError.connect(lambda: process.readAllStandardError())
        process.finished.connect(self._finished)
        process.errorOccurred.connect(lambda _err: self._stop())
        self._process = process
        process.start()

    def _read(self):
        if self._process is None:
            return
        self._buffer += bytes(self._process.readAllStandardOutput())
        if len(self._buffer)>20000:
            self.status.setText('Bağlantı protokolü beklenmeyen uzunlukta; işlem durduruldu.')
            self._stop()
            return
        while b'\n' in self._buffer:
            line,self._buffer = self._buffer.split(b'\n',1)
            try:
                msg=json.loads(line.decode('utf-8'))
            except (UnicodeError, ValueError):
                self._stop()
                return
            typ=msg.get('type')
            if typ=='qr' and not self._halting:
                try:
                    import qrcode
                    qr=qrcode.QRCode(border=2,box_size=6)
                    qr.add_data(msg['qr']); qr.make(fit=True)
                    image=qr.make_image(fill_color='black',back_color='white')
                    stream=io.BytesIO();image.save(stream,format='PNG')
                    pix=QPixmap();pix.loadFromData(stream.getvalue(),'PNG')
                    self.qr.setPixmap(pix.scaled(290,290,Qt.AspectRatioMode.KeepAspectRatio))
                except Exception:
                    self.status.setText('QR üretilemedi. Python qrcode paketini kontrol edin.')
                    self._stop()
            elif typ=='connected' and not self._halting:
                self._connected=True
                self.qr.clear();self.qr.setText('WhatsApp bağlantısı hazır. Gönderim başladı.')
                self._next()
            elif typ=='attempting':
                self.status.setText('Gönderim denemesi yapılıyor; teslim kanıtı değildir.')
            elif typ=='result':
                self._result(msg)
            elif typ in ('rejected','stopped','error'):
                self.status.setText(str(msg.get('reason','Oturum kapandı.')))
                self._stop()

    def _next(self):
        self._scheduled = False
        if self._halting or not self._connected or self._active is not None:
            return
        try:
            job = self.q.claim_next(self._batch)
            # On an opt-out recorded since batch creation, record NOT SENT.
            while job is not None and self.suppressed.contains(job['recipient']):
                self.q.finish(job['id'],job['attempt_token'],FAILED,'Ret listesinde; gönderilmedi')
                job=self.q.claim_next(self._batch)
            if job is None:
                self.status.setText('Partideki tüm bekleyen işler işlendi; teslimatlar ayrıca doğrulanmalıdır.')
                self._stop()
                return
            self._active = job
            payload = {'cmd':'send-one','id':job['id'],'phone':job['recipient'],
                       'text':job['message'],'approval':'IZINLI_TOPLU_V258'}
            written=self._process.write((json.dumps(payload,ensure_ascii=False)+'\n').encode('utf-8'))
            if written<0:
                raise IOError('Baileys köprüsüne gönderim isteği yazılamadı')
        except Exception:
            self.status.setText('Kuyruk / bağlantı hatası; devam eden iş belirsiz ve otomatik tekrarlanmayacak.')
            self._stop()

    def _result(self,msg):
        if not self._active:
            self._stop();return
        job = self._active
        if msg.get('id') != job['id']:
            self._stop();return
        result=(UI_UNVERIFIED if msg.get('status')=='ISTEMCI_KABUL_ETTI_TESLIM_BELIRSIZ'
                else UNKNOWN)
        try:
            self.q.finish(job['id'],job['attempt_token'],result,
                          'Baileys istemci kabulü; teslim doğrulanmadı' if result==UI_UNVERIFIED else
                          'Baileys sonucu doğrulanamadı; tekrar yok')
            self._active=None
            counts=self.q.counts(self._batch)
            pending=counts.get(PENDING,0)
            processed=sum(counts.values())-pending
            self.progress.setMaximum(sum(counts.values()))
            self.progress.setValue(processed)
            self.status.setText(f'İşlenen: {processed}, bekleyen: {pending}. '
                f'İstemci kabulü (teslim belirsiz): {counts.get(UI_UNVERIFIED,0)}, '
                f'sonucu belirsiz: {counts.get(UNKNOWN,0)}.')
            if result==UNKNOWN:
                self._stop()
            elif not self._halting:
                self._scheduled=True
                QTimer.singleShot(PACE_MS, self._next)
        except Exception:
            self.status.setText('Sonuç kuyruğa kaydedilemedi. Gönderim durduruldu; otomatik tekrar yok.')
            self._stop()

    def _stop(self):
        if self._halting:
            return
        self._halting=True
        self.stop_btn.setEnabled(False)
        self._connected=False
        if self._process is not None:
            process=self._process
            if process.state()!=QProcess.ProcessState.NotRunning:
                process.write(b'{"cmd":"stop"}\n')
                QTimer.singleShot(800, lambda: process.kill() if
                                  process.state()!=QProcess.ProcessState.NotRunning else None)
            else:
                self._finished()
        else:
            self._finished()

    def _finished(self, *args):
        # A process crash while a message is in flight is ALWAYS UNKNOWN, not
        # a retriable 'failed' status. Pending recipients stay in the queue.
        if self._active:
            try:
                self.q.finish(self._active['id'],self._active['attempt_token'],UNKNOWN,
                              'İşlem kesildi: sonuç belirsiz; otomatik tekrar yok')
            except Exception:
                try:
                    self.q.recover_interrupted(self._batch)
                except Exception:
                    pass
            self._active=None
        self._connected=False
        self._halting=True
        self._process=None
        self._unlock()
        if self._batch:
            try:
                counts=self.q.counts(self._batch)
                self.status.setText(
                    'Oturum sonlandı. İstemci kabulü (teslim belirsiz): '
                    f'{counts.get(UI_UNVERIFIED,0)} | sonuç belirsiz: {counts.get(UNKNOWN,0)} | '
                    f'bekleyen: {counts.get(PENDING,0)} | geçersiz/gönderilmeyen: '
                    f'{counts.get(INVALID,0)+counts.get(FAILED,0)}. '
                    'Bekleyenler yalnızca yeniden açık onayla sürdürülür.')
                total=sum(counts.values());self.progress.setMaximum(max(total,1))
                self.progress.setValue(total-counts.get(PENDING,0))
            except Exception:
                pass
        self.stop_btn.setEnabled(False)
        self.done_btn.setEnabled(True)

    def _unlock(self):
        if self._lock is not None:
            try:
                self.q.release_lock(self._lock)
            finally:
                self._lock=None

    def closeEvent(self,event):
        if self._setup_process is not None:
            QMessageBox.information(self, 'Kurulum sürüyor',
                'Güvenli kurulum tamamlanana kadar bu pencere açık kalmalıdır.')
            event.ignore()
            return
        if self._process is not None:
            self._stop()
            event.ignore()
            return
        self._unlock()
        super().closeEvent(event)
