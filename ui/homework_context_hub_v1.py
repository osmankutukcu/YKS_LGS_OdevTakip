"""Context-sensitive, additive UX hub for the homework matrix (V1).

Contract:
- Uses EXISTING QAction objects (same triggered callbacks) for ALL legacy commands.
- Reads matrix state for brief and plan preview, never calls setData()/setCheckState().
- No SQLite/database import, no network call before explicit user action.
- Restores full legacy menu if any construction fails.
- Backward switch: ODEV_CONTEXT_MENU_LEGACY=1 environment variable.
"""
from __future__ import annotations
import datetime
import os
import webbrowser

from ui.homework_context_logic_v1 import summarize_topic, official_resource_links, create_study_plan


def _read_context(table, index, subject):
    topic = ''
    book = ''
    if index is not None and index.isValid():
        row = index.row()
        first = table.item(row, 0)
        if first is not None:
            topic = first.text().strip()
        if index.column() > 0:
            header = table.horizontalHeaderItem(index.column())
            if header is not None:
                book = header.text().strip()
    return topic, book, str(subject or '')


def _topic_snapshot(table, index, subject, locked_index=None):
    from PyQt6.QtCore import Qt
    if index is None or not index.isValid():
        return None
    row = index.row()
    first = table.item(row, 0)
    if first is None:
        return None
    entries = []
    for col in range(1, table.columnCount()):
        header = table.horizontalHeaderItem(col)
        item = table.item(row, col)
        if not header or not item:
            continue
        is_checked = item.checkState() == Qt.CheckState.Checked
        if locked_index is not None:
            # Ask the existing lock policy rather than creating a new rule.
            is_checkable = not locked_index(table.model().index(row, col))
        else:
            is_checkable = bool(item.flags() & Qt.ItemFlag.ItemIsUserCheckable)
        entries.append((header.text(), is_checked, is_checkable))
    return summarize_topic(first.text(), subject, entries)


def _show_topic_brief(table, index, subject, locked_index=None):
    from PyQt6.QtWidgets import QMessageBox
    snapshot = _topic_snapshot(table, index, subject, locked_index)
    if snapshot is None:
        return
    lines = [f'{snapshot.subject} · {snapshot.topic}', '',
             f'Görünür kitap: {len(snapshot.cells)}',
             f'İşaretli (değiştirilebilir): {snapshot.checked}',
             f'Boş (değiştirilebilir): {snapshot.empty}',
             f'Kilitli: {snapshot.locked}', '', 'Kitaplara göre:']
    icons = {'locked': '🔒 Kilitli', 'checked': '☑ İşaretli', 'empty': '☐ Boş'}
    lines += [f'• {cell.book}: {icons[cell.state]}' for cell in snapshot.cells]
    lines += ['', 'Bu özet yalnızca açık ödev matrisini okur.',
              'Kilitli hücrelerin tamamlandı/devam ayrımı burada hesaplanmaz.',
              'Kaydedilmiş ödevlerin ayrıntısı için Verilen Ödevler bölümünü kullanın.']
    QMessageBox.information(table, 'Konu Durumu • Salt Okunur', '\n'.join(lines))


def _show_preview_plan(table, index, locked_index=None):
    """Read editable checked cells, or selected topic if none; NEVER mutate table."""
    from PyQt6.QtWidgets import QMessageBox, QInputDialog, QDialog, QVBoxLayout, QLabel, QTextEdit, QHBoxLayout, QPushButton
    from PyQt6.QtCore import Qt

    lines = []
    for r in range(table.rowCount()):
        title_item = table.item(r, 0)
        if not title_item:
            continue
        for c in range(1, table.columnCount()):
            it = table.item(r, c)
            head = table.horizontalHeaderItem(c)
            if it and head and it.checkState() == Qt.CheckState.Checked:
                idx = table.model().index(r, c)
                if locked_index is not None and locked_index(idx):
                    continue  # completed / locked are not active draft assignments
                lines.append((title_item.text(), head.text()))
    if not lines and index is not None and index.isValid():
        first = table.item(index.row(), 0)
        head = table.horizontalHeaderItem(index.column()) if index.column() > 0 else None
        if first and head and (locked_index is None or not locked_index(index)):
            lines.append((first.text(), head.text()))
    if not lines:
        QMessageBox.information(table, 'Plan Önizlemesi',
                                'Önce bir konu hücresine sağ tıklayın veya matriste işaretlenmiş konular bulundurun.')
        return
    if len(lines) > 3000:
        QMessageBox.warning(table, 'Plan Önizlemesi', 'Bu önizlemede en fazla 3000 konu kullanılabilir.')
        return
    per_day, ok = QInputDialog.getInt(table, 'Güvenli Kamp Planı',
                                     f'{len(lines)} konu görüldü. Günde kaç konu planlansın?', 3, 1, 30, 1)
    if not ok:
        return
    text = create_study_plan(lines, per_day, datetime.date.today())
    dialog = QDialog(table)
    dialog.setWindowTitle('Güvenli Çalışma Planı • Yalnızca Önizleme')
    dialog.resize(650, 530)
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel('Bu pencere, mevcut işaretlemeleri ve ödev kayıtlarını değiştirmez.'))
    preview = QTextEdit(dialog)
    preview.setReadOnly(True)
    preview.setPlainText(text)
    layout.addWidget(preview)
    buttons = QHBoxLayout()
    copy_btn = QPushButton('Metni Kopyala', dialog)
    copy_btn.clicked.connect(lambda: _copy_text(text))
    close_btn = QPushButton('Kapat', dialog)
    close_btn.clicked.connect(dialog.accept)
    buttons.addWidget(copy_btn)
    buttons.addWidget(close_btn)
    layout.addLayout(buttons)
    dialog.exec()


def _copy_text(content):
    from PyQt6.QtWidgets import QApplication
    QApplication.clipboard().setText(content)


def _help(table):
    from PyQt6.QtWidgets import QMessageBox
    QMessageBox.information(
        table, 'Akıllı Konu Menüsü • Yardım',
        '• Tek sol tık ile ödev işaretleme davranışı değiştirilmedi.\n'
        '• Bu menü konu karnelerine, resmî kaynaklara ve planlamaya ulaşmak içindir.\n'
        '• Konu Durumu ve Güvenli Plan Önizlemesi salt okunurdur.\n'
        '• Resmî kaynak bağlantıları yalnızca seçtiğinizde tarayıcıda açılır.\n'
        '• Mevcut toplu işlemler eskisi gibi çalışır ve kilit kuralları aynıdır.\n'
        '• Eski kamp planlayıcısı, mevcut sürümde işaretsiz hücreleri de işaretleyebilir.\n'
        '• Bu menüyü beğenmezseniz alttaki Görünüm düğmesiyle eski düzene dönebilirsiniz.'
    )


def install_hub(menu, table, index, subject, commands, locked_index=None, host=None):
    """Refactor QMenu presentation exclusively; return True when installed.

    commands MUST be original QAction instances with already connected slots.
    """
    from PyQt6.QtWidgets import QMenu
    from PyQt6.QtGui import QAction
    from PyQt6.QtCore import QSettings
    names = ('toggle','row_give','row_clear','col_give','col_clear','col_clean',
             'book_status','lesson_analyze','gap_analyze','smart_analyze',
             'yt','gg','review','plan','parent_report')
    if not all(commands.get(key) is not None for key in names):
        return False  # untouched old menu
    if os.getenv('ODEV_CONTEXT_MENU_LEGACY', '').strip() == '1':
        return False

    saved = list(menu.actions())
    settings = QSettings('OdevTakip', 'HomeworkContextV1')
    expert = settings.value('expert', False, type=bool)
    topic, book, subject = _read_context(table, index, subject)
    try:
        for a in saved:
            menu.removeAction(a)
        menu.setToolTipsVisible(True)
        if expert:
            # Original old order preserved as alternative UX (same QAction objects).
            for a in saved:
                menu.addAction(a)
            menu.addSeparator()
            tools = menu.addMenu('✨ Yeni araçlar (salt okunur)')
        else:
            meta = menu.addAction(f'📍  {subject or "Ders"}  ›  {topic or "Bir konu seçin"}')
            meta.setEnabled(False)
            menu.addSeparator()
            topic_action = menu.addAction('📊  Bu Konunun Durumunu Gör')
            topic_action.setEnabled(bool(topic))
            topic_action.setToolTip('Açık matriste bu konuya ait kitap/işaret/kilit özetini gösterir; kayıt değiştirmez.')
            topic_action.triggered.connect(lambda _checked=False: _show_topic_brief(table, index, subject, locked_index))
            menu.addAction(commands['gap_analyze'])
            menu.addAction(commands['book_status'])
            menu.addSeparator()
            tools = menu

        if expert:
            topic_action = tools.addAction('📊  Bu Konunun Durumunu Gör')
            topic_action.setEnabled(bool(topic))
            topic_action.triggered.connect(lambda _checked=False: _show_topic_brief(table, index, subject, locked_index))

        if host is not None:
            # V2: visible shortcuts to existing engines, before optional V1 tools.
            from ui.homework_context_integrations_v2 import install_existing_centers
            install_existing_centers(tools, host)

        resources = tools.addMenu('🌐  Resmî Kaynaklar ve İnternette Ara')
        resources.setToolTipsVisible(True)
        for title, url, explanation in official_resource_links(subject, topic):
            a = resources.addAction(title)
            a.setToolTip(explanation)
            a.triggered.connect(lambda _checked=False, href=url: webbrowser.open(href))
        resources.addSeparator()
        if not expert:
            resources.addAction(commands['yt'])
            resources.addAction(commands['gg'])
        resources.setToolTip('Seçilen konu internette aranabilir. Hiçbir öğrenci bilgisi gönderilmez.')

        if not expert:
            coaching = tools.addMenu('🧠  Tekrar / Veli İletişimi')
            reports = tools.addMenu('📈  Ayrıntılı Raporlar')
            legacy = tools.addMenu('📋  Toplu Ödev İşlemleri (mevcut kurallar)')
            coaching.setToolTipsVisible(True)
            coaching.addAction(commands['review'])
            coaching.addAction(commands['parent_report'])
            reports.addAction(commands['lesson_analyze'])
            reports.addAction(commands['smart_analyze'])
            for key in ('toggle','row_give','row_clear','col_give','col_clear','col_clean'):
                legacy.addAction(commands[key])
            # Preserve V1 utilities, but keep them distinct from the native planner.
            old_plans = tools.addMenu('🧰  Alternatif Eski Kamp Araçları')
            safe_plan = old_plans.addAction('🗓  Güvenli Kamp Planı Önizle (tik değiştirmez)')
            safe_plan.setToolTip('V1 basit metin taslağı. Gelişmiş program için yukarıdaki hazır Haftalık Planlayıcıyı kullanın.')
            safe_plan.triggered.connect(lambda _checked=False: _show_preview_plan(table, index, locked_index))
            old_plans.addAction(commands['plan'])
            commands['plan'].setToolTip('DİKKAT: Eski kamp planlayıcısı plan oluştururken işaretsiz hücreleri işaretleyebilir.')
        else:
            old_plans = tools.addMenu('🧰  Alternatif V1 Kamp Araçları')
            safe_plan = old_plans.addAction('🗓  Güvenli Kamp Planı Önizle (tik değiştirmez)')
            safe_plan.triggered.connect(lambda _checked=False: _show_preview_plan(table, index, locked_index))

        menu.addSeparator()
        how = menu.addAction('❔  Bu menü nasıl kullanılır?')
        how.triggered.connect(lambda _checked=False: _help(table))
        switch = menu.addAction('⚙️  ' + ('Sade menüye geç' if expert else 'Tüm işlemleri göster (uzman)'))
        switch.triggered.connect(lambda _checked=False, new=not expert: settings.setValue('expert', new))
        return True
    except Exception:
        # Irrespective of grouping problems keep the original feature map intact.
        menu.clear()
        for action in saved:
            menu.addAction(action)
        raise
