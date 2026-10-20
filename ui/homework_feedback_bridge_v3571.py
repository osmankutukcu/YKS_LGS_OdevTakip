# -*- coding: utf-8 -*-
"""Optional V3.5.71 actions beneath EXISTING SurveyManager online button.

No changes to homework tracking, control form, or quick teacher diagnosis.
The teacher can only copy a one-time link, then review/reject a self-report.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (QApplication,QDialog,QHBoxLayout,QInputDialog,QLabel,
    QListWidget,QListWidgetItem,QMessageBox,QPushButton,QTextEdit,QVBoxLayout)
from services import homework_feedback_v3571 as feedback


class _CloudWorker(QThread):
    """Keep HTTPS requests off the GUI thread; never touch widgets inside run()."""
    finished_result=pyqtSignal(object, object)

    def __init__(self, operation, args, parent=None):
        super().__init__(parent)
        self.operation=operation
        self.args=args

    def run(self):
        try:result=self.operation(*self.args)
        except Exception as exc:self.finished_result.emit(None,str(exc))
        else:self.finished_result.emit(result,None)


def _background(panel, operation, args, done):
    # Parent-held references preserve worker lifetime until completion.
    if not hasattr(panel,'_feedback_cloud_workers'):
        panel._feedback_cloud_workers=[]
    worker=_CloudWorker(operation,args,panel)
    panel._feedback_cloud_workers.append(worker)
    worker.finished_result.connect(done)
    def cleanup():
        try:panel._feedback_cloud_workers.remove(worker)
        except ValueError:pass
        worker.deleteLater()
    worker.finished.connect(cleanup)
    worker.start()


def _selected_student(panel):
    sid=panel.current_student_id
    if type(sid) is not int or sid<=0:
        QMessageBox.warning(panel,'Ödev Geri Bildirimi','Önce öğrenciyi seçiniz.')
        return None
    return sid


def send_link(panel,respondent):
    sid=_selected_student(panel)
    if sid is None:return
    try:
        work=feedback.list_homeworks(sid)
        if not work:
            QMessageBox.information(panel,'Ödev Geri Bildirimi','Bu öğrencide kayıtlı bir ödev bulunamadı.')
            return
        labels=[f"#{x['homework_id']} · {x['lesson']} / {x['topic']}" for x in work]
        choice,ok=QInputDialog.getItem(panel,'Ödev Geri Bildirimi',
            'Geri bildirim istenecek ödevi seçiniz:',labels,0,False)
        if not ok:return
        homework=work[labels.index(choice)]
        from services import homework_feedback_cloud_bridge_v3573 as cloud
        if cloud.configured():
            def done(result,error):
                if panel.current_student_id!=sid:
                    QMessageBox.warning(panel,'Geri Bildirim','Öğrenci değişti; bağlantı gösterilmiyor.')
                    return
                if error:
                    QMessageBox.warning(panel,'Çevrim İçi Anket',error)
                    return
                QApplication.clipboard().setText(result['url'])
                whom='öğrenciye' if respondent=='student' else 'veliye'
                QMessageBox.information(panel,'Güvenli Bağlantı Hazır',
                    f"Anket bağlantısı kopyalandı. Mevcut WhatsApp paylaşımıyla {whom} gönderebilirsiniz.\n"
                    'Gönderim otomatik yapılmadı; süreli ve tek kullanımlıktır.')
            _background(panel,cloud.create_link,(sid,homework['homework_id'],respondent),done)
            return
        result=feedback.create_link(sid,homework['homework_id'],respondent)
    except (ValueError,OSError,RuntimeError) as exc:
        QMessageBox.warning(panel,'Ödev Geri Bildirimi',str(exc))
        return
    QApplication.clipboard().setText(result['url'])
    whom='öğrenciye' if respondent=='student' else 'veliye'
    QMessageBox.information(panel,'Bağlantı Kopyalandı',
        f"Seçilen ödevin tek kullanımlık geri bildirim bağlantısı panoya kopyalandı.\n"
        f"Bağlantıyı {whom} mevcut WhatsApp veya başka kanalınızdan gönderebilirsiniz.\n"
        "48 saat geçerlidir. Gönderim otomatik yapılmadı.")


def review_feedback(panel, _after_sync=False):
    sid=_selected_student(panel)
    if sid is None:return
    if not _after_sync:
        from services import homework_feedback_cloud_bridge_v3573 as cloud
        if cloud.configured():
            def done(result,error):
                if panel.current_student_id!=sid:return
                if error:
                    QMessageBox.warning(panel,'Geri Bildirim Senkronizasyonu',
                        'İnternet yanıtları şu anda alınamadı. Yerel bekleyen yanıtlar gösterilecek.\n'+error)
                review_feedback(panel,_after_sync=True)
            _background(panel,cloud.sync_replies,(),done)
            return
    dialog=QDialog(panel)
    dialog.setWindowTitle('Ödev Hızlı Geri Bildirimleri — Öğretmen İncelemesi')
    dialog.resize(670,490)
    layout=QVBoxLayout(dialog)
    layout.addWidget(QLabel('Yanıtlar öğrenci/veli beyanıdır; Hızlı Teşhis öğretmen notunu, ödev durumunu veya başarıyı değiştirmez.'))
    items=QListWidget()
    details=QTextEdit();details.setReadOnly(True)
    layout.addWidget(items);layout.addWidget(details)
    bar=QHBoxLayout()
    approve=QPushButton('İncele ve Onayla')
    reject=QPushButton('Reddet')
    refresh=QPushButton('Yenile')
    for button in (approve,reject,refresh):bar.addWidget(button)
    layout.addLayout(bar)
    current=[]

    def reload():
        items.clear(); details.clear();current.clear()
        try:current.extend(feedback.list_feedback(sid))
        except (ValueError,OSError) as exc:
            QMessageBox.warning(dialog,'Geri Bildirim',str(exc));return
        for record in current:
            who='Öğrenci' if record['respondent']=='student' else 'Veli'
            item=QListWidgetItem(f"{who} · #{record['homework_id']} {record['lesson']} / {record['topic']} · {record['received_at'][:16]}")
            item.setData(Qt.ItemDataRole.UserRole,record['reply_id'])
            items.addItem(item)
        if not current:
            try:
                approved=feedback.approved_summary(sid)
                lines=['Bekleyen yanıt yok.']
                if approved:
                    lines.append('\nSon onaylanan öğrenci/veli bildirimleri (tanı değildir):')
                    for summary in approved[:5]:
                        lines.append(f"• {summary['source']} · {summary['lesson']} / {summary['topic']}: {summary['obstacle_label']}")
                details.setPlainText('\n'.join(lines))
            except (ValueError,OSError):
                details.setPlainText('Bekleyen geri bildirim bulunmuyor.')

    def selected():
        item=items.currentItem()
        return next((x for x in current if x['reply_id']==item.data(Qt.ItemDataRole.UserRole)),None) if item else None

    def show_detail():
        r=selected()
        if not r:return
        a=r['answers']
        who='Öğrenci beyanı' if r['respondent']=='student' else 'Veli gözlemi'
        details.setPlainText(f"{who}\nÖdev: {r['lesson']} / {r['topic']}\n"
            f"Çalışma ilerlemesi (beyan): {a['completion']}/5\n"
            f"Anlama rahatlığı (beyan): {a['understanding']}/5\n"
            f"Süre uygunluğu (beyan): {a['time_fit']}/5\n"
            f"Bildirilen güçlük: {feedback.OBSTACLES.get(a['obstacle'],'Belirsiz')}\n\n"
            "Bu değerlendirme, öğretmen gözlemi veya bağımsız öğrenme kanıtı değildir.\n"
            "Gerekiyorsa öğrenci ile görüşün ve kısa kazanım kontrolü yapın.")

    def act(decision):
        r=selected()
        if not r:
            QMessageBox.information(dialog,'Geri Bildirim','Önce bir yanıt seçiniz.');return
        if panel.current_student_id!=sid:
            QMessageBox.warning(dialog,'Geri Bildirim','Öğrenci değişti. Lütfen yeniden açın.');return
        verb='onaylansın' if decision=='approved' else 'reddedilsin'
        if QMessageBox.question(dialog,'İşlemi Doğrula',f'Seçili geri bildirim {verb}?') != QMessageBox.StandardButton.Yes:return
        try:feedback.decide(sid,r['reply_id'],decision)
        except (ValueError,OSError) as exc:
            QMessageBox.warning(dialog,'Geri Bildirim',str(exc));return
        reload()

    items.currentItemChanged.connect(lambda *_:show_detail())
    refresh.clicked.connect(reload)
    approve.clicked.connect(lambda:act('approved'))
    reject.clicked.connect(lambda:act('rejected'))
    reload();dialog.exec()
