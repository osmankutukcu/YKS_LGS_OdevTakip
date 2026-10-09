# tablewidget_extras.py
# PyQt6 için "akıllı tablo" yardımcıları:
# - Checkbox'ları (CheckStateRole) ÜSLÜP BOZMADAN ortalar (delegate)
# - Tablolara modern hover/başlık görünümü ekler
# - Sütun/satır boyutlarını makul ayarlar
# - Host nesnesindeki _ders_tablolari üzerinde hepsini tek seferde uygular

from __future__ import annotations
from typing import Optional, Dict

from PyQt6.QtCore import Qt, QRect, QEvent
from PyQt6.QtWidgets import (
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QStyle,
    QTableWidget,
    QHeaderView,
    QWidget,
)
from PyQt6.QtGui import QMouseEvent, QKeyEvent


# -----------------------------
# 1) Checkbox'ı ortalayan delegate
# -----------------------------
class CenteredCheckDelegate(QStyledItemDelegate):
    """
    QTableWidgetItem üzerinde CheckStateRole kullanan hücrelerin checkbox'ını
    YATAY ve DİKEY merkezde çizer ve tıklama/space ile toggle eder.
    """

    def paint(self, painter, option: QStyleOptionViewItem, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        # Hücre checkable mı?
        if not (index.flags() & Qt.ItemFlag.ItemIsUserCheckable):
            # Normal hücre
            return super().paint(painter, opt, index)

        # Mevcut stil üzerinden checkbox indicator rect'ini al
        style = opt.widget.style() if opt.widget else None
        if style is None:
            style = QStyledItemDelegate().parent()

        # Gösterilecek checkbox durumu
        check_state = index.data(Qt.ItemDataRole.CheckStateRole)
        checked = (check_state == Qt.CheckState.Checked)

        # Checkbox kutusunun doğal boyutu
        ind_rect = opt.widget.style().subElementRect(
            QStyle.SubElement.SE_ItemViewItemCheckIndicator, opt, opt.widget
        )
        # Hücre rect'inde merkezle
        x = opt.rect.left() + (opt.rect.width() - ind_rect.width()) // 2
        y = opt.rect.top() + (opt.rect.height() - ind_rect.height()) // 2
        rect = QRect(x, y, ind_rect.width(), ind_rect.height())

        # Çizim durumu (on/off, enabled, active vs.)
        ind_opt = QStyleOptionViewItem(opt)
        ind_opt.rect = rect
        ind_opt.state = QStyle.StateFlag.State_Enabled
        if checked:
            ind_opt.state |= QStyle.StateFlag.State_On
        else:
            ind_opt.state |= QStyle.StateFlag.State_Off
        if opt.state & QStyle.StateFlag.State_MouseOver:
            ind_opt.state |= QStyle.StateFlag.State_MouseOver
        if opt.state & QStyle.StateFlag.State_HasFocus:
            ind_opt.state |= QStyle.StateFlag.State_HasFocus

        opt.widget.style().drawPrimitive(
            QStyle.PrimitiveElement.PE_IndicatorItemViewItemCheck, ind_opt, painter, opt.widget
        )

    def editorEvent(self, event: QEvent, model, option, index):
        """
        Tıklama / Space ile CheckStateRole değerini değiştir.
        """
        if not (index.flags() & Qt.ItemFlag.ItemIsUserCheckable):
            return super().editorEvent(event, model, option, index)

        # Fare bırakma veya Space tuşu
        if event.type() == QEvent.Type.MouseButtonRelease:
            me: QMouseEvent = event  # type: ignore
            if not option.rect.contains(me.position().toPoint()):
                return False
            return self._toggle(model, index)

        if event.type() == QEvent.Type.KeyPress:
            ke: QKeyEvent = event  # type: ignore
            if ke.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
                return self._toggle(model, index)

        return False

    @staticmethod
    def _toggle(model, index):
        cur = index.data(Qt.ItemDataRole.CheckStateRole)
        nxt = Qt.CheckState.Unchecked if cur == Qt.CheckState.Checked else Qt.CheckState.Checked
        ok = model.setData(index, nxt, Qt.ItemDataRole.CheckStateRole)
        return ok


# -----------------------------
# 2) Tek tabloya "akıllı ayarları" uygula
# -----------------------------
def tune_table(table: QTableWidget, center_checks_from_col: int = 1) -> None:
    """
    - Header görünümü ve resize modları
    - Alternating + hover stilleri (kalıcı değil, CSS tabanlı)
    - Checkable hücreler için checkbox'ı merkezleyen delegate
    """
    if not isinstance(table, QTableWidget):
        return

    # Header / resize
    hh: QHeaderView = table.horizontalHeader()
    hh.setStretchLastSection(True)
    # İçeriğe göre makul (ilk sütun "Konu" olabilir)
    for c in range(table.columnCount()):
        if c == 0:
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        else:
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)

    table.setAlternatingRowColors(True)
    table.setWordWrap(False)

    # Hafif, modern görünüm + hover
    # Not: Sadece hover sırasında renklenir; kalıcı vurgulama yapmaz.
    base_css = """
    QTableWidget {
        gridline-color: #e5e7eb;
        selection-background-color: #dbeafe;
        selection-color: black;
        alternate-background-color: #fafafa;
    }
    QTableWidget::item:hover {
        background-color: #eef6ff;
    }
    QHeaderView::section {
        background-color: #f5f7fa;
        padding: 6px;
        border: 0px;
        border-bottom: 1px solid #e5e7eb;
        font-weight: 600;
    }
    """
    # Var olan stylesheet'e ekle (ezmeden)
    merged = (table.styleSheet() + "\n" + base_css).strip()
    table.setStyleSheet(merged)

    # Checkbox merkezleme delegate (1..N sütunlar genelde kitap sütunları)
    delegate = CenteredCheckDelegate(table)
    for c in range(center_checks_from_col, table.columnCount()):
        table.setItemDelegateForColumn(c, delegate)

    # Boyutları bir defa içeriklere uydur
    table.resizeColumnsToContents()
    table.resizeRowsToContents()


# -----------------------------
# 3) Host içindeki TÜM sol tabloları uygula
# -----------------------------
def apply_simple_tuning_to_left_tables(host: QWidget) -> None:
    """
    Host (form) içinde self._ders_tablolari dict'i varsa
    tüm tablolar için tune_table uygular.
    Ayrıca host.verilen varsa onun da temel görünümünü iyileştirir.
    """
    # Sol taraf (sekme tablolari)
    tablolar: Optional[Dict[str, QTableWidget]] = getattr(host, "_ders_tablolari", None)
    if isinstance(tablolar, dict):
        for _, tbl in list(tablolar.items()):
            if isinstance(tbl, QTableWidget):
                # kitap sütunları 1..N olduğundan 1'den itibaren merkezle
                tune_table(tbl, center_checks_from_col=1)

    # Sağ taraftaki "verilen" listesi
    verilen = getattr(host, "verilen", None)
    if isinstance(verilen, QTableWidget):
        # verilen'de genelde check yok; sadece görünümü toparla
        hh: QHeaderView = verilen.horizontalHeader()
        hh.setStretchLastSection(False)
        verilen.setAlternatingRowColors(True)
        verilen.setWordWrap(False)
        verilen.setStyleSheet((verilen.styleSheet() + """
        QTableWidget::item:hover { background-color: #eef6ff; }
        QHeaderView::section {
            background-color: #f5f7fa;
            padding: 6px;
            border: 0px;
            border-bottom: 1px solid #e5e7eb;
            font-weight: 600;
        }
        """).strip())
        verilen.resizeColumnsToContents()
        # "Konu"yu daha görünür yapmak istersen:
        # hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)