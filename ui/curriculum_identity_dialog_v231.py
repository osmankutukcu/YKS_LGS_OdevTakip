"""V23.1 salt okunur konu kimliği ve çakışma görüntüleyicisi.

Ödev kaydı, müfredat tablosu ya da tik durumu değiştirmez.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPlainTextEdit, QDialogButtonBox, QMessageBox
from PyQt6.QtGui import QGuiApplication

from services.curriculum_v231 import effective_topics
import db


def open_identity_audit(editor):
    scope, opts = editor._current_scope()
    ders = opts.get('ders')
    if not ders:
        QMessageBox.information(editor, 'Konu Kimliği', 'Önce ders seçiniz.')
        return
    kwargs = {'ders': ders}
    if scope == 'Grup':
        kwargs.update(ana_grup=opts.get('ana_grup'), alt_grup=opts.get('alt_grup'))
    elif scope == 'Öğrenci':
        kwargs['ogrenci_id'] = opts.get('ogrenci_id')
        if not kwargs['ogrenci_id']:
            QMessageBox.information(editor, 'Konu Kimliği', 'Önce öğrenci seçiniz.')
            return
    con = db.get_conn()
    try:
        snapshot = effective_topics(con, **kwargs)
    except Exception as exc:
        QMessageBox.warning(editor, 'Konu Kimliği Denetimi', f'Denetim tamamlanamadı: {exc}')
        return
    finally:
        con.close()

    dlg = QDialog(editor)
    dlg.setWindowTitle('Konu Kimliği ve Çakışma Denetimi – V23.1')
    layout = QVBoxLayout(dlg)
    layout.addWidget(QLabel('Bu rapor salt okunurdur. Eski ödevler, tikler ve konu kayıtları değiştirilmez.'))
    view = QPlainTextEdit(dlg)
    view.setReadOnly(True)
    lines = [f'Ders: {ders} | Kapsam: {scope}',
             f'Görünen konu sayısı: {len(snapshot.topics)}',
             f'Kayıtlı kaynak sayısı: {len(snapshot.all_sources)}',
             '', 'ETKİN KONU LİSTESİ']
    for index, item in enumerate(snapshot.topics, 1):
        topic = item.record
        source = topic.identity
        lines.append(f'{index:03}. {topic.name} — {source.scope} / ID {source.row_id}')
        if item.overridden:
            lines.append('       Öncelikte geride kalan kapsamlar: ' +
                         ', '.join(f'{i.scope} #{i.row_id}' for i in item.overridden))
    if snapshot.warnings:
        lines.extend(['', 'İNCELEME UYARILARI', *('- ' + warning for warning in snapshot.warnings)])
    lines.extend(['', 'Not: Aynı addaki genel/grup/öğrenci konuları ayrı kimliklerdir.',
                  'Bu rapor eski ödevleri isim benzerliğiyle otomatik ilişkilendirmez.'])
    view.setPlainText('\n'.join(lines))
    layout.addWidget(view, 1)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dlg.reject)
    layout.addWidget(buttons)
    screen = QGuiApplication.primaryScreen()
    if screen:
        rect = screen.availableGeometry()
        dlg.resize(min(690, max(300, rect.width() - 48)), min(510, max(250, rect.height() - 70)))
    dlg.exec()
