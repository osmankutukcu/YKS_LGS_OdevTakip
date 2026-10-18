# -*- coding: utf-8 -*-
"""V30 optional one-click teacher review. Never intercept legacy checkboxes.

The only assignment operation delegates to the already-tested
host._wizard_transfer_tasks, which invokes the ORIGINAL itemChanged workflow.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QHeaderView,
)
from services.adaptive_coaching_v30.drafts import (
    build_draft, evaluate_candidates, select_transfer_tasks,
)
from utils.homework_integrity_v133 import unique_exact_cell
from utils.wizard_integrity_v8 import exact_task_key, same_student
import db


class AdaptiveDraftReviewV30(QDialog):
    """Fixed student identity and explicit approval; all preview is read-only."""
    def __init__(self, student_id, host, parent=None):
        super().__init__(parent)
        self.student_id = int(student_id)
        self.host = host
        self._draft = None
        self._rows = []
        self.setWindowTitle('V30 · Kişisel Ödev Taslağını İncele')
        self.setMinimumSize(790, 440)
        self.resize(1030, 580)
        self.setStyleSheet('''
        QDialog{background:#f8fafc;color:#172b4d;}
        QLabel{color:#334155;}
        QPushButton{background:white;border:1px solid #cbd5e1;border-radius:7px;
            padding:7px 12px;color:#1e293b;font-weight:650;}
        QPushButton:hover{background:#eff6ff;
                color: #15191E;}
        QTableWidget{background:white;alternate-background-color:#f8fafc;
            border:1px solid #dbe4ef;gridline-color:#e2e8f0;
                color: #15191E;}
        QHeaderView::section{background:#eef2f7;padding:7px;font-weight:650;}
        ''')
        body = QVBoxLayout(self)
        title = QLabel('🧠 Öğretmen Onaylı Adaptif Ödev Taslağı')
        title.setStyleSheet('font-size:17px;font-weight:750;color:#1e3a8a;')
        body.addWidget(title)
        subtitle = QLabel('Mevcut verilen ödevler ve checkbox kuralları korunur. '
            'Öneriler otomatik kaydedilmez; önce öğretmen seçer, sonra eski Kaydet düğmesini kullanır.')
        subtitle.setWordWrap(True)
        body.addWidget(subtitle)
        self.summary = QLabel('Öneriler hazırlanıyor…')
        self.summary.setWordWrap(True)
        body.addWidget(self.summary)
        self.grid = QTableWidget(0, 6)
        self.grid.setHorizontalHeaderLabels(['Seç','Ders','Kitap','Konu','Dakika','Uygunluk / gerekçe'])
        self.grid.setAlternatingRowColors(True)
        self.grid.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.grid.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.grid.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.grid.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        body.addWidget(self.grid, 1)
        controls = QHBoxLayout()
        self.reload = QPushButton('↻ Öneriyi Yenile')
        self.reload.clicked.connect(self.refresh)
        controls.addWidget(self.reload)
        controls.addStretch(1)
        close = QPushButton('Vazgeç')
        close.clicked.connect(self.reject)
        controls.addWidget(close)
        self.apply = QPushButton('✓ Seçilenleri Verilen Ödevlere Ekle')
        self.apply.setToolTip('Standart hücre işaretleme akışıyla forma ekler; veritabanına kaydetmez.')
        self.apply.clicked.connect(self.transfer)
        controls.addWidget(self.apply)
        body.addLayout(controls)
        self.refresh()

    def _check_student(self):
        h = self.host
        if not same_student(h._secili_ogrenci_id(), self.student_id) or not same_student(
                getattr(h, '_loaded_student_id', None), self.student_id):
            raise ValueError('Öğrenci değişti veya ders tablosu yüklenmemiş.')
        if not same_student(h.cmbAd.currentData(), h.cmbSoyad.currentData()):
            raise ValueError('Ad/Soyad seçimleri uyuşmuyor.')

    def _availability(self, record):
        """Read existing UI state; final application rechecks all rules itself."""
        h = self.host
        self._check_student()
        key = exact_task_key(record['lesson'], record['book'], record['topic'])
        for row in range(h.verilen.rowCount()):
            if exact_task_key(h._vtext(row, 0), h._vtext(row, 1), h._vtext(row, 2)) == key:
                return False, 'Zaten Verilen Ödevler tablosunda'
        table, r, col = unique_exact_cell(getattr(h, '_ders_tablolari', {}), *(
            record['lesson'], record['book'], record['topic']))
        if table is None:
            return False, 'Eşsiz ders/kitap/konu hücresi bulunamadı'
        cell = table.item(r, col)
        if (cell is None or not (cell.flags() & Qt.ItemFlag.ItemIsEnabled)
                or not (cell.flags() & Qt.ItemFlag.ItemIsUserCheckable)):
            return False, 'Hücre kilitli veya düzenlenemez'
        if cell.checkState() == Qt.CheckState.Checked:
            return False, 'Hücre daha önce işaretlenmiş'
        # Mirror the existing transfer guard; final guard is authoritative.
        try:
            if cell.background().color().name().lower() in {
                '#a5d6a7','#fff59d','#c8e6c9','#fca5a5',
                '#fecaca','#ffcdd2','#f8d7da'}:
                return False, 'Kayıtlı / korunan hücre'
        except (AttributeError, TypeError):
            pass
        return True, 'Aktarılabilir · son Kaydet öğretmende'

    @staticmethod
    def _build_on_demand(student_id):
        # V25 tables are initialized lazily after an EXPLICIT teacher action;
        # neither old homework tables nor their rows are migrated or modified.
        from services.adaptive_coaching_v25 import engine
        con = db.get_conn()
        try:
            names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'adaptive_%_v25'")}
            if not {'adaptive_observation_v25','adaptive_profile_v25','adaptive_blocker_v25'}.issubset(names):
                engine.ensure_schema(con)  # New optional tables only, once.
            return build_draft(con, student_id)
        finally:
            con.close()

    def refresh(self):
        self.apply.setEnabled(False)
        self._rows = []
        self._draft = None
        self.grid.setRowCount(0)
        try:
            self._check_student()
            draft = self._build_on_demand(self.student_id)
            rows = evaluate_candidates(draft['items'], self._availability)
        except Exception as exc:
            self.summary.setText('Taslak hazırlanamadı. Eski ödevler etkilenmedi. ' + str(exc))
            return
        self._draft, self._rows = draft, rows
        self.grid.setRowCount(len(rows))
        available = sum(r['eligible'] for r in rows)
        self.summary.setText(
            f"{len(rows)} öneri · {available} eşleşen hücre · "
            f"{draft['proposed_minutes']} dk öneri. "
            + ('İş yükü notu: varsayılan yalnız ilk iki uygun öneri seçildi. ' if draft['overload_note'] else '')
            + 'Herhangi bir öneriyi seçmek zorunlu değildir.'
        )
        for i, item in enumerate(rows):
            check = QTableWidgetItem('')
            flags = Qt.ItemFlag.ItemIsEnabled
            if item['eligible']:
                flags |= Qt.ItemFlag.ItemIsUserCheckable
                check.setCheckState(Qt.CheckState.Checked if item['default_selected']
                                    else Qt.CheckState.Unchecked)
            check.setFlags(flags)
            self.grid.setItem(i, 0, check)
            values = (item['lesson'],item['book'] or '—',item['topic'],
                      str(item['minutes']),item['reason'] if not item['eligible']
                      else (item['note'] or item['level'] + ' · ' + item['category']))
            for col, value in enumerate(values,1):
                widget_item = QTableWidgetItem(str(value))
                widget_item.setToolTip(item['details'] + ('\n' + item['note'] if item['note'] else ''))
                self.grid.setItem(i,col,widget_item)
        self.apply.setEnabled(available > 0)

    def transfer(self):
        if not self._draft:
            return
        try:
            self._check_student()
            checked = {exact_task_key(x['lesson'],x['book'],x['topic'])
                 for i,x in enumerate(self._rows) if x['eligible'] and
                 self.grid.item(i,0).checkState()==Qt.CheckState.Checked}
            if not checked:
                QMessageBox.information(self,'Seçim yok','En az bir aktarılabilir öneri seçin.')
                return
            fresh = self._build_on_demand(self.student_id)
            tasks = select_transfer_tasks(self._draft, checked,
                expected_student_id=self.student_id, fresh_draft=fresh)
            # Re-evaluate live matrix immediately before invoking legacy transfer.
            availability = [self._availability(next(r for r in self._rows if
                 exact_task_key(r['lesson'],r['book'],r['topic']) == key))
                 for key in checked]
            if not all(ok for ok, _ in availability):
                raise ValueError('Ödevlerin uygunluğu değişti; taslağı yenileyin.')
        except Exception as exc:
            QMessageBox.warning(self,'Aktarım iptal edildi',str(exc))
            self.refresh()
            return
        total = sum(t['dk'] for t in tasks)
        answer = QMessageBox.question(self,'Öğretmen Onayı',
            f'{len(tasks)} öneri ({total} dk) mevcut tik mekanizmasıyla '
            'Verilen Ödevler tablosuna eklenecek.\n'
            'Yeni ödevlerin gerçek Kaydet işlemi, Ödev Takip Formu içindeki '
            'eski Kaydet düğmesiyle yapılacak. Onaylıyor musunuz?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            # Only one write boundary: the *existing* assignment form signal flow.
            result = self.host._wizard_transfer_tasks(tasks,expected_student_id=self.student_id)
        except Exception as exc:
            QMessageBox.warning(self,'Aktarım hatası',
                'Mevcut ödev kaydı değiştirilmedi. Formu kontrol edin.\n'+str(exc))
            return
        if result and result.get('added'):
            bridge=getattr(self.host,'_adaptive_bridge_v27',None)
            if bridge is not None:
                bridge.show_assignments()
            self.accept()
        else:
            self.refresh()
