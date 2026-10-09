# utils/table_tune.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Iterable, List, Set, Optional
from PyQt6 import sip
from PyQt6.QtCore import Qt, QEvent, QPoint, QObject, QRect
from PyQt6.QtGui import QFontMetrics, QPainter, QColor, QBrush, QAction
from PyQt6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QStyledItemDelegate,
    QStyle, QApplication, QAbstractItemView, QTabWidget, QStyleOptionViewItem
)

# ---------------- 1) 'Konu' sütununu içeriğe göre genişlet ----------------
def autosize_konu_column(
    t: QTableWidget,
    header_text: str = "Konu",
    padding: int = 28,
    min_w: int = 140,
    max_w: int = 580,
) -> None:
    if not t or t.columnCount() == 0:
        return

    hh = t.horizontalHeader()
    hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

    col = -1
    for c in range(t.columnCount()):
        it = t.horizontalHeaderItem(c)
        if it and (it.text() or "").strip().lower() == header_text.lower():
            col = c
            break
    if col < 0:
        return

    fm = QFontMetrics(t.font())
    base_text = t.horizontalHeaderItem(col).text() if t.horizontalHeaderItem(col) else header_text
    w = fm.horizontalAdvance(base_text) + padding

    for r in range(t.rowCount()):
        it = t.item(r, col)
        if it is None:
            continue
        w = max(w, fm.horizontalAdvance(it.text()) + padding)

    t.setColumnWidth(col, max(min_w, min(w, max_w)))


# -------- 2) Satır ve sütun başlıklarını hover’da renklendir (QObject) ------

class HeaderHoverHighlighter(QObject):
    def __init__(self, table: QTableWidget, row_color: str = "#eef6ff", col_color: str = "#eef6ff"):
        super().__init__(table)
        self.t: Optional[QTableWidget] = table
        self._row_brush = QBrush(QColor(row_color))
        self._col_brush = QBrush(QColor(col_color))
        self._last: tuple[int, int] = (-1, -1)

        hh, vh = self.t.horizontalHeader(), self.t.verticalHeader()
        for c in range(self.t.columnCount()):
            if self.t.horizontalHeaderItem(c) is None:
                self.t.setHorizontalHeaderItem(c, QTableWidgetItem(""))
        for r in range(self.t.rowCount()):
            if self.t.verticalHeaderItem(r) is None:
                self.t.setVerticalHeaderItem(r, QTableWidgetItem(""))

        vp = self.t.viewport()
        vp.setMouseTracking(True)
        vp.installEventFilter(self)

        self.t.destroyed.connect(self._on_table_destroyed)

    def _on_table_destroyed(self, *_):
        self.t = None

    def _paint(self, r: int, c: int):
        if not self.t or sip.isdeleted(self.t):
            return
        
        old_r, old_c = self._last
        if old_r != -1 and old_r < self.t.rowCount():
            it = self.t.verticalHeaderItem(old_r)
            if it: it.setBackground(Qt.GlobalColor.transparent)
        if old_c != -1 and old_c < self.t.columnCount():
            it = self.t.horizontalHeaderItem(old_c)
            if it: it.setBackground(Qt.GlobalColor.transparent)

        if 0 <= r < self.t.rowCount():
            it = self.t.verticalHeaderItem(r)
            if it: it.setBackground(self._row_brush)
        if 0 <= c < self.t.columnCount():
            it = self.t.horizontalHeaderItem(c)
            if it: it.setBackground(self._col_brush)
            
        self.t.horizontalHeader().viewport().update()
        self.t.verticalHeader().viewport().update()

    def eventFilter(self, obj, ev):
        if not self.t or sip.isdeleted(self.t):
            return False

        if obj is self.t.viewport():
            if ev.type() == QEvent.Type.MouseMove:
                pos: QPoint = ev.position().toPoint()
                r = self.t.rowAt(pos.y())
                c = self.t.columnAt(pos.x())
                if (r, c) != self._last:
                    self._paint(r, c)
                    self._last = (r, c)
            elif ev.type() in (QEvent.Type.Leave, QEvent.Type.Hide):
                old_r, old_c = self._last
                if old_r != -1 and old_r < self.t.rowCount():
                    it = self.t.verticalHeaderItem(old_r)
                    if it: it.setBackground(Qt.GlobalColor.transparent)
                if old_c != -1 and old_c < self.t.columnCount():
                    it = self.t.horizontalHeaderItem(old_c)
                    if it: it.setBackground(Qt.GlobalColor.transparent)
                self.t.horizontalHeader().viewport().update()
                self.t.verticalHeader().viewport().update()
                self._last = (-1, -1)
                
        return False

# ---------------- 3) Checkbox Ortalayıcı Delegate ------------------

class CenteredCheckDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        check_state = index.data(Qt.ItemDataRole.CheckStateRole)
        
        if check_state is None:
            super().paint(painter, option, index)
            return

        text = index.data(Qt.ItemDataRole.DisplayRole)
        has_text = bool(text and str(text).strip())
        
        self.initStyleOption(option, index)
        widget = option.widget
        style = widget.style() if widget else QApplication.style()

        style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, option, painter, widget)

        chk_rect = self.getCheckBoxRect(option)
        chk_opt = QStyleOptionViewItem(option)
        chk_opt.rect = chk_rect
        chk_opt.state = chk_opt.state & ~QStyle.StateFlag.State_HasFocus

        state_val = check_state
        if state_val == Qt.CheckState.Checked.value:
            chk_opt.state |= QStyle.StateFlag.State_On
        elif state_val == Qt.CheckState.PartiallyChecked.value:
            chk_opt.state |= QStyle.StateFlag.State_NoChange
        else:
            chk_opt.state |= QStyle.StateFlag.State_Off

        style.drawPrimitive(QStyle.PrimitiveElement.PE_IndicatorItemViewItemCheck, chk_opt, painter, widget)

        if has_text:
            super().paint(painter, option, index)
            return

    def getCheckBoxRect(self, option):
        widget = option.widget
        style = widget.style() if widget else QApplication.style()
        chk_rect_def = style.subElementRect(QStyle.SubElement.SE_ItemViewItemCheckIndicator, option, widget)
        w = chk_rect_def.width()
        h = chk_rect_def.height()
        
        center_x = option.rect.x() + option.rect.width() // 2
        center_y = option.rect.y() + option.rect.height() // 2
        
        return QRect(center_x - w//2, center_y - h//2, w, h)

    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.Type.MouseButtonRelease:
            if event.button() == Qt.MouseButton.LeftButton:
                text = index.data(Qt.ItemDataRole.DisplayRole)
                has_text = bool(text and str(text).strip())
                check_state = index.data(Qt.ItemDataRole.CheckStateRole)
                
                if check_state is not None and not has_text:
                    new_state = Qt.CheckState.Unchecked if check_state == Qt.CheckState.Checked.value else Qt.CheckState.Checked
                    model.setData(index, new_state, Qt.ItemDataRole.CheckStateRole)
                    return True 
        return super().editorEvent(event, model, option, index)


# ---------------- 4) Toplu Uygulayıcı ------------------

def _collect_left_tables(owner) -> List[QTableWidget]:
    seen: Set[int] = set()
    out: List[QTableWidget] = []
    for t in (getattr(owner, "_ders_tablolari", {}) or {}).values():
        if isinstance(t, QTableWidget) and id(t) not in seen:
            out.append(t)
            seen.add(id(t))
    for name, val in vars(owner).items():
        if isinstance(val, QTableWidget) and name.endswith("_tablosu") and id(val) not in seen:
            out.append(val)
            seen.add(id(val))
    return out


def apply_simple_tuning_to_left_tables(
    owner,
    konu_header: str = "Konu",
    hover_row_color: str = "#d8e1f0",
    hover_col_color: str = "#d8e1f0",
) -> None:
    tables = _collect_left_tables(owner)
    if not tables:
        return

    if not hasattr(owner, "_center_chk_delegate"):
        owner._center_chk_delegate = CenteredCheckDelegate(owner)
    center_delegate = owner._center_chk_delegate

    for t in tables:
        autosize_konu_column(t, header_text=konu_header)
        t._vis_highlighter = HeaderHoverHighlighter(t, hover_row_color, hover_col_color)
        t.setAlternatingRowColors(True)
        t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        t.setItemDelegate(center_delegate)

    tabw: QTabWidget | None = getattr(owner, "tabWidget", None) or getattr(owner, "tab", None)
    if isinstance(tabw, QTabWidget):
        def _recalc_on_change(_idx: int):
            for t in tables:
                autosize_konu_column(t, header_text=konu_header)
        try:
            tabw.currentChanged.disconnect(_recalc_on_change)
        except: pass
        tabw.currentChanged.connect(_recalc_on_change)

def polish_left_table_visual_gaps(t: QTableWidget) -> None:
    if not t:
        return
    t.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    t.setStyleSheet(
        """
        QTableCornerButton::section { width: 0px; height: 0px; border: 0px; background: transparent; }
        QHeaderView::section { padding-left: 6px; padding-right: 6px; }
        """
    )
    t.horizontalHeader().setStyleSheet("")
    t.verticalHeader().setStyleSheet("")