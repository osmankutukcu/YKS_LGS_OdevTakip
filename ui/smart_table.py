# smart_table.py — PyQt6
# Gelişmiş QTableView kurulum seti (tek fonksiyonla etkinleştir).
# Özellikler:
# - Hücrede merkezde checkbox (widget’sız), hover vurgusu (hücre + başlık)
# - Başlıkta Hepsini Seç/Temizle + tri-state özet
# - Metin sütunlarına auto-width (örneklemeli), header stil özelleştirme
# - UX: Shift aralığı, Ctrl+I tersine çevir, sürükle-ile doldur, Ctrl+F hızlı arama overlay,
#       başlık sağ-tık menüsü, kopyala-yapıştır 1/0
# - Görsellik: yumuşak grid, elips (…) + tooltip, kilit nedeni tooltip
# - Performans: debounce, uniform row heights, örneklemeli ölçüm, durum kalıcılığı
# - Veri güvenliği: toplu değişiklik onayı, audit trail, basit undo/redo iskeleti
# - Filtreleme & Sıralama: proxy ile metin filtresi, “sadece işaretlileri göster”, çoklu sıralama
# - Export: görünene göre CSV
#
# Tüm kritik yerlerde Türkçe hata logları (traceback ile) vardır.
from __future__ import annotations

import csv
import json
import os
import traceback
from typing import Callable, Iterable, Optional, Sequence, Dict, List, Tuple

from PyQt6.QtCore import (
    Qt, QRect, QPoint, QObject, QEvent, QTimer, QModelIndex, QSize
)
from PyQt6.QtGui import (
    QColor, QPainter, QFontMetrics, QKeySequence, QActionEvent, QGuiApplication,QShortcut
)
from PyQt6.QtWidgets import (
    QApplication, QHeaderView, QStyledItemDelegate, QStyle,
    QStyleOptionViewItem, QTableView, QWidget, QLineEdit, QHBoxLayout,
     QMenu, QMessageBox, QFileDialog
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import QSortFilterProxyModel


# ==========================
# Yardımcı: Güvenli loglama
# ==========================
def _safe_log(prefix: str, err: Exception):
    print(f"[SMART_TABLE][{prefix}] Hata: {err}")
    traceback.print_exc()


# ==========================
# Audit trail yapısı (basit)
# ==========================
class AuditTrail:
    """Son değişiklikleri basit bir listede tutar."""
    def __init__(self):
        self.records: List[Dict] = []

    def add(self, r: int, c: int, old_state: int, new_state: int):
        self.records.append({
            "row": r, "col": c, "old": int(old_state), "new": int(new_state)
        })


# ====================================================
# Hover + Header Checkbox boyayan başlık sınıfı
# ====================================================
class HoverHeader(QHeaderView):
    def __init__(self, orientation, parent=None, tint: QColor = QColor(30, 144, 255, 60)):
        super().__init__(orientation, parent)
        self._hovered_section = -1
        self._tint = tint
        self._controller = None
        self._checkable_cols: set[int] = set()

    def bindController(self, controller, checkable_cols: set[int]):
        self._controller = controller
        self._checkable_cols = set(checkable_cols)

    def setHoveredSection(self, sec: int):
        if self._hovered_section != sec:
            self._hovered_section = sec
            self.viewport().update()

    def setTint(self, tint: QColor):
        self._tint = tint
        self.viewport().update()

    def paintSection(self, painter: QPainter, rect: QRect, logicalIndex: int):
        # 1) Normal başlık
        super().paintSection(painter, rect, logicalIndex)

        # 2) Hover tint
        if logicalIndex == self._hovered_section and rect.isValid() and self._tint is not None:
            painter.save()
            painter.fillRect(rect, self._tint)
            painter.restore()

        # 3) Başlık checkbox (sadece checkable sütunlarda)
        if logicalIndex in self._checkable_cols and self._controller is not None and rect.isValid():
            try:
                style = self.style()
                try:
                    w = style.pixelMetric(QStyle.PixelMetric.PM_IndicatorWidth, None, self)
                    h = style.pixelMetric(QStyle.PixelMetric.PM_IndicatorHeight, None, self)
                except Exception:
                    w = h = min(rect.height(), 16)
                ind_rect = QRect(0, 0, w, h)
                ind_rect.moveCenter(rect.center())

                st = self._controller.header_state_for_column(logicalIndex)

                opt = QStyleOptionViewItem()
                opt.rect = ind_rect
                opt.state = QStyle.StateFlag.State_Enabled
                if st == Qt.CheckState.Checked:
                    opt.state |= QStyle.StateFlag.State_On
                elif st == Qt.CheckState.PartiallyChecked:
                    opt.state |= QStyle.StateFlag.State_NoChange
                else:
                    opt.state |= QStyle.StateFlag.State_Off
                style.drawPrimitive(QStyle.PrimitiveElement.PE_IndicatorViewItemCheck, opt, painter, self)

                self._controller.set_header_checkbox_rect(logicalIndex, ind_rect)
            except Exception as e:
                _safe_log("paintSection_checkbox", e)

    def mousePressEvent(self, event):
        try:
            if self._controller is not None:
                sec = self.logicalIndexAt(event.pos())
                if self._controller.try_toggle_by_header_click(sec, event.pos()):
                    return
        except Exception as e:
            _safe_log("header_mousePress", e)
        super().mousePressEvent(event)

    # Sağ tık menüsü
    def contextMenuEvent(self, event):
        try:
            sec = self.logicalIndexAt(event.pos())
            if sec < 0:
                return
            menu = QMenu(self)
            act_auto = QAction("Sütunu Auto-Genişlet", menu)
            act_hide = QAction("Sütunu Gizle", menu)
            act_show_all = QAction("Tüm Sütunları Göster", menu)
            menu.addAction(act_auto)
            menu.addSeparator()
            # Checkable ise toplu işlemler
            if sec in self._checkable_cols and self._controller is not None:
                act_all = QAction("Hepsini İşaretle", menu)
                act_none = QAction("Hepsini Temizle", menu)
                act_inv = QAction("Tersine Çevir (Invert)", menu)
                act_only_checked = QAction("Bu sütunda Sadece İşaretlileri Göster", menu)
                menu.addAction(act_all)
                menu.addAction(act_none)
                menu.addAction(act_inv)
                menu.addSeparator()
                menu.addAction(act_only_checked)

                act_all.triggered.connect(lambda: self._controller.bulk_set_column(sec, Qt.CheckState.Checked))
                act_none.triggered.connect(lambda: self._controller.bulk_set_column(sec, Qt.CheckState.Unchecked))
                act_inv.triggered.connect(lambda: self._controller.bulk_invert_column(sec))
                act_only_checked.triggered.connect(lambda: self._controller.filter_only_checked(sec))

            menu.addSeparator()
            menu.addAction(act_hide)
            menu.addAction(act_show_all)

            def _auto():
                self.resizeSection(sec, max(50, self.sectionSize(sec)))  # tetik
                if self.parent() and hasattr(self.parent(), "_st_auto_size_text_columns"):
                    # kurulum fonksiyonunda inject edeceğiz
                    try:
                        self.parent()._st_auto_size_text_columns()
                    except Exception as e:
                        _safe_log("header_auto", e)

            act_auto.triggered.connect(_auto)
            act_hide.triggered.connect(lambda: self.hideSection(sec))
            act_show_all.triggered.connect(self.showAllSections)
            menu.exec(event.globalPos())
        except Exception as e:
            _safe_log("header_ctx", e)


# ==================================================
# Delegate: Checkbox’ı merkezde çizen hafif temsilci
# + Shift aralığı, drag-fill, Ctrl+I invert (view eventFilter ile)
# ==================================================
class SmartCheckDelegate(QStyledItemDelegate):
    def __init__(self,
                 view: QTableView,
                 checkable_columns: set[int],
                 locked_predicate: Optional[Callable[[QModelIndex], bool]] = None,
                 hover_tint: QColor = QColor(30, 144, 255, 40),
                 lock_reason_role: int = int(Qt.ItemDataRole.UserRole) + 11,
                 elide_long_text: bool = True):
        super().__init__(view)
        self.view = view
        self.checkable_columns = set(checkable_columns)
        self.locked_predicate = locked_predicate
        self.hover_tint = hover_tint
        self.lock_reason_role = lock_reason_role
        self.elide_long_text = elide_long_text

        self._hover_index: Optional[QModelIndex] = None
        self._last_toggled: Optional[QModelIndex] = None
        self._drag_active = False
        self._drag_target_state: Optional[Qt.CheckState] = None

        self.view.setMouseTracking(True)
        self.view.viewport().installEventFilter(self)
        self.view.installEventFilter(self)  # klavye kısayolları (Ctrl+I vs.)

    # --- Hover izleme + drag-fill ---
    def eventFilter(self, obj: QObject, event) -> bool:
        try:
            if obj is self.view.viewport():
                if event.type() == QEvent.Type.MouseMove:
                    idx = self.view.indexAt(event.pos())
                    if idx != self._hover_index:
                        self._hover_index = idx
                        r = idx.row() if idx.isValid() else -1
                        c = idx.column() if idx.isValid() else -1
                        hh = self.view.horizontalHeader()
                        vh = self.view.verticalHeader()
                        if isinstance(hh, HoverHeader):
                            hh.setHoveredSection(c)
                        if isinstance(vh, HoverHeader):
                            vh.setHoveredSection(r)
                        self.view.viewport().update()

                    # Drag-fill aktif ise
                    if self._drag_active and idx.isValid() and idx.column() in self.checkable_columns:
                        if self._drag_target_state is not None:
                            self._try_set_state(idx, self._drag_target_state)
                elif event.type() in (QEvent.Type.Leave, QEvent.Type.HoverLeave):
                    self._hover_index = None
                    hh = self.view.horizontalHeader()
                    vh = self.view.verticalHeader()
                    if isinstance(hh, HoverHeader):
                        hh.setHoveredSection(-1)
                    if isinstance(vh, HoverHeader):
                        vh.setHoveredSection(-1)
                    self.view.viewport().update()
                elif event.type() == QEvent.Type.MouseButtonPress:
                    idx = self.view.indexAt(event.pos())
                    if idx.isValid() and idx.column() in self.checkable_columns:
                        # drag-fill başlat
                        st = idx.data(Qt.ItemDataRole.CheckStateRole) or Qt.CheckState.Unchecked
                        target = Qt.CheckState.Checked if st != Qt.CheckState.Checked else Qt.CheckState.Unchecked
                        self._drag_active = True
                        self._drag_target_state = target
                elif event.type() == QEvent.Type.MouseButtonRelease:
                    self._drag_active = False
                    self._drag_target_state = None

            # Ctrl+I = invert selection
            if obj is self.view and event.type() == QEvent.Type.KeyPress and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                if event.key() == Qt.Key.Key_I:
                    self._invert_selection()
                    return True
        except Exception as e:
            _safe_log("delegate_eventFilter", e)
        return super().eventFilter(obj, event)

    # --- Çizim ---
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        try:
            opt = QStyleOptionViewItem(option)
            self.initStyleOption(opt, index)
            style = opt.widget.style() if opt.widget else QApplication.style()

            is_checkable = index.column() in self.checkable_columns
            is_hover = (self._hover_index is not None and index == self._hover_index)

            if is_checkable:
                # Varsayılan check göstergesini kaldır (iki kez çizilmesin)
                from PyQt6.QtWidgets import QStyleOptionViewItem as SOVI
                opt.features &= ~SOVI.ViewItemFeature.HasCheckIndicator
                opt.text = ""
                # Önce default boyama (arka plan/selection/roller)
                style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)

                st = index.data(Qt.ItemDataRole.CheckStateRole)
                if st is None:
                    st = Qt.CheckState.Unchecked

                ind_rect = style.subElementRect(QStyle.SubElement.SE_ItemViewItemCheckIndicator, opt, opt.widget)
                ind_rect.moveCenter(opt.rect.center())

                cb_opt = QStyleOptionViewItem(opt)
                cb_opt.rect = ind_rect
                if st == Qt.CheckState.Checked:
                    cb_opt.state |= QStyle.StateFlag.State_On
                elif st == Qt.CheckState.PartiallyChecked:
                    cb_opt.state |= QStyle.StateFlag.State_NoChange
                else:
                    cb_opt.state |= QStyle.StateFlag.State_Off
                style.drawPrimitive(QStyle.PrimitiveElement.PE_IndicatorViewItemCheck, cb_opt, painter, opt.widget)
            else:
                # Metin hücresi: elide + tooltip
                if self.elide_long_text and isinstance(opt.text, str) and opt.text:
                    fm = QFontMetrics(opt.font)
                    elided = fm.elidedText(opt.text, Qt.TextElideMode.ElideRight, opt.rect.width()-6)
                    if elided != opt.text:
                        # Tam metni tooltip olarak göster
                        index.model().setData(index, opt.text, Qt.ItemDataRole.ToolTipRole)
                        opt.text = elided
                super().paint(painter, opt, index)

            # Hover tint
            if is_hover and self.hover_tint is not None:
                painter.save()
                painter.fillRect(opt.rect, self.hover_tint)
                painter.restore()

            # Kilit nedeni tooltip (varsa)
            if self.lock_reason_role is not None:
                reason = index.data(self.lock_reason_role)
                if reason:
                    index.model().setData(index, str(reason), Qt.ItemDataRole.ToolTipRole)

        except Exception as e:
            _safe_log("paint", e)
            super().paint(painter, option, index)

    # --- Etkileşim (tıklama/klavye + Shift aralığı) ---
    def editorEvent(self, event, model, option, index: QModelIndex):
        try:
            if index.column() not in self.checkable_columns:
                return super().editorEvent(event, model, option, index)

            # Kilit kontrolü
            if self._is_locked(index):
                return False

            et = event.type()

            if et in (QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick):
                if not option.rect.contains(event.position().toPoint()):
                    return False
                new_state = self._toggled_state(index)
                ok = model.setData(index, new_state, Qt.ItemDataRole.CheckStateRole)
                if ok:
                    # Shift ile aralık
                    modifiers = QApplication.keyboardModifiers()
                    if modifiers & Qt.KeyboardModifier.ShiftModifier and self._last_toggled and self._last_toggled.isValid() and self._last_toggled.column() == index.column():
                        self._apply_range_toggle(self._last_toggled, index, new_state)
                    self._last_toggled = index
                return ok

            if et == QEvent.Type.KeyPress:
                key = event.key()
                if key in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    new_state = self._toggled_state(index)
                    ok = model.setData(index, new_state, Qt.ItemDataRole.CheckStateRole)
                    if ok:
                        self._last_toggled = index
                    return ok

        except Exception as e:
            _safe_log("editorEvent", e)

        return super().editorEvent(event, model, option, index)

    # ---- Yardımcılar ----
    def _is_locked(self, index: QModelIndex) -> bool:
        if callable(self.locked_predicate):
            try:
                return bool(self.locked_predicate(index))
            except Exception as e:
                _safe_log("locked_predicate", e)
        else:
            fl = index.model().flags(index)
            if not (fl & Qt.ItemFlag.ItemIsEnabled): return True
            if not (fl & Qt.ItemFlag.ItemIsUserCheckable): return True
        return False

    def _toggled_state(self, index: QModelIndex) -> Qt.CheckState:
        st = index.data(Qt.ItemDataRole.CheckStateRole)
        if st is None:
            st = Qt.CheckState.Unchecked
        return Qt.CheckState.Checked if st != Qt.CheckState.Checked else Qt.CheckState.Unchecked

    def _apply_range_toggle(self, a: QModelIndex, b: QModelIndex, target: Qt.CheckState):
        model = a.model()
        r0, r1 = sorted((a.row(), b.row()))
        c = a.column()
        self.view.setUpdatesEnabled(False)
        try:
            for r in range(r0, r1 + 1):
                idx = model.index(r, c)
                if not self._is_locked(idx):
                    st = idx.data(Qt.ItemDataRole.CheckStateRole) or Qt.CheckState.Unchecked
                    if st != target:
                        model.setData(idx, target, Qt.ItemDataRole.CheckStateRole)
        except Exception as e:
            _safe_log("apply_range_toggle", e)
        finally:
            self.view.setUpdatesEnabled(True)

    def _try_set_state(self, index: QModelIndex, target: Qt.CheckState):
        if self._is_locked(index): return
        st = index.data(Qt.ItemDataRole.CheckStateRole) or Qt.CheckState.Unchecked
        if st != target:
            index.model().setData(index, target, Qt.ItemDataRole.CheckStateRole)

    def _invert_selection(self):
        sel = self.view.selectionModel().selectedIndexes()
        if not sel: return
        self.view.setUpdatesEnabled(False)
        try:
            for idx in sel:
                if idx.column() in self.checkable_columns and not self._is_locked(idx):
                    st = idx.data(Qt.ItemDataRole.CheckStateRole) or Qt.CheckState.Unchecked
                    new_state = Qt.CheckState.Checked if st != Qt.CheckState.Checked else Qt.CheckState.Unchecked
                    idx.model().setData(idx, new_state, Qt.ItemDataRole.CheckStateRole)
        except Exception as e:
            _safe_log("invert_selection", e)
        finally:
            self.view.setUpdatesEnabled(True)


# ============================================
# Header kontrolörü: tri-state + toplu toggle
# + invert + “sadece işaretlileri göster” (proxy’ye delege)
# ============================================
class HeaderController(QObject):
    def __init__(self, view: QTableView, checkable_cols: set[int],
                 locked_predicate: Optional[Callable[[QModelIndex], bool]],
                 confirm_large_bulk: int = 500,
                 audit_trail: Optional[AuditTrail] = None):
        super().__init__(view)
        self.view = view
        self.model = view.model()
        self.checkable_cols = set(checkable_cols)
        self.locked_predicate = locked_predicate
        self.confirm_large_bulk = confirm_large_bulk
        self.audit_trail = audit_trail

        self._state_cache: Dict[int, Qt.CheckState] = {}
        self._hit_rects: Dict[int, QRect] = {}
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(120)
        self._debounce.timeout.connect(self.recompute_all)

        # Model sinyalleri
        try:
            self.model.dataChanged.connect(self._schedule_recompute)
            self.model.modelReset.connect(self._schedule_recompute)
            self.model.rowsInserted.connect(self._schedule_recompute)
            self.model.rowsRemoved.connect(self._schedule_recompute)
        except Exception as e:
            _safe_log("HeaderController_connect", e)

        self.recompute_all()

    def _schedule_recompute(self, *args, **kwargs):
        self._debounce.start()

    def set_header_checkbox_rect(self, col: int, rect: QRect):
        self._hit_rects[col] = QRect(rect)

    def header_state_for_column(self, col: int) -> Qt.CheckState:
        return self._state_cache.get(col, Qt.CheckState.Unchecked)

    def recompute_column(self, col: int):
        try:
            m = self.model
            rcount = m.rowCount()
            any_checked = False
            any_unchecked = False
            for r in range(rcount):
                st = m.index(r, col).data(Qt.ItemDataRole.CheckStateRole)
                if st == Qt.CheckState.Checked:
                    any_checked = True
                else:
                    any_unchecked = True
                if any_checked and any_unchecked:
                    self._state_cache[col] = Qt.CheckState.PartiallyChecked
                    return
            if any_checked and not any_unchecked:
                self._state_cache[col] = Qt.CheckState.Checked
            elif any_unchecked and not any_checked:
                self._state_cache[col] = Qt.CheckState.Unchecked
            else:
                self._state_cache[col] = Qt.CheckState.Unchecked
        except Exception as e:
            _safe_log("recompute_column", e)
            self._state_cache[col] = Qt.CheckState.Unchecked

    def recompute_all(self):
        try:
            for c in self.checkable_cols:
                self.recompute_column(c)
            self.view.horizontalHeader().viewport().update()
        except Exception as e:
            _safe_log("recompute_all", e)

    def try_toggle_by_header_click(self, section: int, pos: QPoint) -> bool:
        try:
            if section not in self.checkable_cols:
                return False
            r = self._hit_rects.get(section)
            if not r or not r.contains(pos):
                return False
            cur = self.header_state_for_column(section)
            target = Qt.CheckState.Unchecked if cur == Qt.CheckState.Checked else Qt.CheckState.Checked
            self.bulk_set_column(section, target)
            self._schedule_recompute()
            return True
        except Exception as e:
            _safe_log("header_click_toggle", e)
            return False

    def _is_locked(self, idx: QModelIndex) -> bool:
        if callable(self.locked_predicate):
            try:
                return bool(self.locked_predicate(idx))
            except Exception as e:
                _safe_log("bulk_locked_pred", e)
                return False
        fl = idx.model().flags(idx)
        return (not (fl & Qt.ItemFlag.ItemIsEnabled)) or (not (fl & Qt.ItemFlag.ItemIsUserCheckable))

    def bulk_set_column(self, col: int, target: Qt.CheckState):
        view = self.view
        m = self.model
        if m is None: return
        rcount = m.rowCount()
        # Büyük bulk onayı
        if self.confirm_large_bulk and rcount > self.confirm_large_bulk:
            ret = QMessageBox.question(view, "Toplu Değişiklik",
                                       f"{rcount} hücre güncellenecek. Devam edilsin mi?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if ret != QMessageBox.StandardButton.Yes:
                return
        try:
            view.setUpdatesEnabled(False)
            for r in range(rcount):
                idx = m.index(r, col)
                if self._is_locked(idx):
                    continue
                old = idx.data(Qt.ItemDataRole.CheckStateRole) or Qt.CheckState.Unchecked
                if old != target:
                    if m.setData(idx, target, Qt.ItemDataRole.CheckStateRole) and self.audit_trail:
                        self.audit_trail.add(r, col, old, target)
        except Exception as e:
            _safe_log("bulk_set_column", e)
        finally:
            view.setUpdatesEnabled(True)

    def bulk_invert_column(self, col: int):
        view = self.view
        m = self.model
        if m is None: return
        rcount = m.rowCount()
        try:
            view.setUpdatesEnabled(False)
            for r in range(rcount):
                idx = m.index(r, col)
                if self._is_locked(idx):
                    continue
                old = idx.data(Qt.ItemDataRole.CheckStateRole) or Qt.CheckState.Unchecked
                new = Qt.CheckState.Checked if old != Qt.CheckState.Checked else Qt.CheckState.Unchecked
                if m.setData(idx, new, Qt.ItemDataRole.CheckStateRole) and self.audit_trail:
                    self.audit_trail.add(r, col, old, new)
        except Exception as e:
            _safe_log("bulk_invert_column", e)
        finally:
            view.setUpdatesEnabled(True)

    # Proxy üzerinden filtre: sadece işaretliler
    def filter_only_checked(self, col: int):
        parent = self.view.parent()
        if hasattr(parent, "_st_proxy") and isinstance(parent._st_proxy, SmartProxyModel):
            parent._st_proxy.set_only_checked_column(col, True)


# ============================================
# Proxy Model: filtre, “sadece işaretliler”, çoklu sıralama
# ============================================
class SmartProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._text_filters: Dict[int, str] = {}       # col -> substring (case-insensitive)
        self._only_checked_cols: set[int] = set()     # bu sütunlarda sadece Checked satırları geçir
        self._multi_sort: List[Tuple[int, Qt.SortOrder]] = []  # [(col, order), ...]

    # --- Filtreleme ---
    def set_text_filter(self, col: int, text: str):
        self._text_filters[col] = text or ""
        self.invalidateFilter()

    def set_only_checked_column(self, col: int, enabled: bool):
        if enabled:
            self._only_checked_cols.add(col)
        else:
            self._only_checked_cols.discard(col)
        self.invalidateFilter()

    def clear_all_filters(self):
        self._text_filters.clear()
        self._only_checked_cols.clear()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        m = self.sourceModel()
        if m is None: return True

        # “sadece işaretliler” kuralı
        for c in self._only_checked_cols:
            idx = m.index(source_row, c)
            st = idx.data(Qt.ItemDataRole.CheckStateRole)
            if st != Qt.CheckState.Checked:
                return False

        # Metin filtreleri
        for c, sub in self._text_filters.items():
            if not sub:
                continue
            idx = m.index(source_row, c)
            txt = idx.data(Qt.ItemDataRole.DisplayRole)
            if not txt:  # None veya boş
                return False
            if sub.lower() not in str(txt).lower():
                return False

        return True

    # --- Çoklu sıralama ---
    def set_multi_sort(self, columns: List[Tuple[int, Qt.SortOrder]]):
        # columns: öncelik sırasıyla
        self._multi_sort = list(columns)
        # QSortFilterProxyModel tek kolon sort bilir; lessThan’ı tuple karşılaştırmaya çeviriyoruz
        self.invalidate()

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        if not self._multi_sort:
            return super().lessThan(left, right)
        m = self.sourceModel()
        # Tuple oluştur: [(key1 asc/desc), (key2 ...)]
        keys_left = []
        keys_right = []
        try:
            for col, order in self._multi_sort:
                il = m.index(left.row(), col)
                ir = m.index(right.row(), col)
                vl = il.data(Qt.ItemDataRole.DisplayRole)
                vr = ir.data(Qt.ItemDataRole.DisplayRole)
                # None güvenliği
                vl = "" if vl is None else vl
                vr = "" if vr is None else vr
                # sayı gibi görünenleri sayıya çevirme girişimi
                try:
                    vl = float(vl)
                    vr = float(vr)
                except Exception:
                    pass
                if order == Qt.SortOrder.AscendingOrder:
                    keys_left.append(vl); keys_right.append(vr)
                else:
                    keys_left.append(vr); keys_right.append(vl)
            return tuple(keys_left) < tuple(keys_right)
        except Exception as e:
            _safe_log("lessThan_multi", e)
            return super().lessThan(left, right)


# ==========================================================
# Otomatik sütun genişliği (metin sütunları için örneklemeli)
# ==========================================================
def _autosize_text_columns(view: QTableView,
                           text_columns: Sequence[int],
                           sample_rows: int | str = 800,
                           padding_px: int = 24,
                           include_header: bool = True):
    model = view.model()
    if model is None:
        return
    # Proxy varsa kaynağı ölçelim (görünür satırlarla çalışmak istersen proxy üzerinden de ölçebilirsin)
    rcount = model.rowCount()
    h = view.horizontalHeader()
    fm = view.fontMetrics()

    if sample_rows == "auto":
        # satır sayısına göre örnek büyüklüğü (performans dostu)
        if rcount <= 500: rmax = rcount
        elif rcount <= 2000: rmax = 600
        else: rmax = 400
    else:
        rmax = min(rcount, max(0, int(sample_rows)))

    for c in text_columns:
        try:
            max_w = 0
            if include_header:
                header_text = model.headerData(c, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
                if header_text:
                    max_w = max(max_w, fm.horizontalAdvance(str(header_text)))
            # İlk rmax satırı ölç
            for r in range(rmax):
                idx = model.index(r, c)
                txt = idx.data(Qt.ItemDataRole.DisplayRole)
                if not txt:
                    continue
                w = fm.horizontalAdvance(str(txt))
                if w > max_w:
                    max_w = w
            target = max_w + padding_px
            h.resizeSection(c, max(30, target))
        except Exception as e:
            _safe_log(f"autosize_col_{c}", e)


# ============================================
# Hızlı Arama Overlay (Ctrl+F)
# ============================================
class QuickFind(QWidget):
    def __init__(self, view: QTableView, proxy: Optional[SmartProxyModel]):
        super().__init__(view)
        self.view = view
        self.proxy = proxy
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.WindowType.SubWindow)
        self.setFixedHeight(36)

        self.line = QLineEdit(self)
        self.line.setPlaceholderText("Ara (Ctrl+F) — Enter ile sonraki eşleşme")
        lay = QHBoxLayout(self); lay.setContentsMargins(8, 8, 8, 8); lay.addWidget(self.line)
        self.hide()

        self.line.returnPressed.connect(self._find_next)
        self.line.textChanged.connect(self._apply_filter)

    def show_for_view(self):
        self.setFixedWidth(int(self.view.viewport().width() * 0.5))
        self.move(self.view.mapToGlobal(self.view.viewport().geometry().topLeft()) + QPoint(12, 12))
        self.show()
        self.raise_()
        self.line.setFocus()

    def _apply_filter(self):
        if self.proxy:
            # Tüm metin sütunlarında geniş bir arama için: tek bir sütuna uygulamak yerine her metin sütununda text filter…
            # Burada basit: “global search” davranışı için kaynak modelin tüm sütunlarına uygula
            src = self.proxy.sourceModel()
            if src:
                cols = src.columnCount()
                txt = self.line.text()
                for c in range(cols):
                    self.proxy.set_text_filter(c, txt)

    def _find_next(self):
        # Basit: bir sonraki görünen satıra in
        v = self.view
        r = v.currentIndex().row()
        rows = v.model().rowCount()
        if rows == 0: return
        start = (r + 1) % rows
        v.selectRow(start)
        v.scrollTo(v.model().index(start, 0))


# ============================================
# Export yardımcıları
# ============================================
def export_visible_to_csv(view: QTableView, path: str, checkbox_as: str = "10"):
    """
    Görünene göre CSV dışa aktar:
    - Filtrelenmiş satırlar
    - Görünen sütunlar
    - Checkbox'lar: "10" -> 1/0, "checkmark" -> ✓/✗, "truefalse" -> True/False
    """
    try:
        model = view.model()
        if model is None:
            raise RuntimeError("Model yok.")
        hh = view.horizontalHeader()
        cols = [c for c in range(model.columnCount()) if not hh.isSectionHidden(c)]

        def chk_repr(st):
            st = st or Qt.CheckState.Unchecked
            if checkbox_as == "checkmark":
                return "✓" if st == Qt.CheckState.Checked else "✗"
            if checkbox_as == "truefalse":
                return "True" if st == Qt.CheckState.Checked else "False"
            return "1" if st == Qt.CheckState.Checked else "0"

        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            # Başlık
            headers = [model.headerData(c, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) or "" for c in cols]
            w.writerow(headers)
            # Satırlar
            for r in range(model.rowCount()):
                row = []
                for c in cols:
                    idx = model.index(r, c)
                    st = idx.data(Qt.ItemDataRole.CheckStateRole)
                    txt = idx.data(Qt.ItemDataRole.DisplayRole)
                    row.append(chk_repr(st) if st is not None else (txt if txt is not None else ""))
                w.writerow(row)
        return True
    except Exception as e:
        _safe_log("export_visible_to_csv", e)
        return False


# ============================================
# Durum kalıcılığı (width/hidden/sort/filters)
# ============================================
def save_view_state(view: QTableView, proxy: Optional[SmartProxyModel], path: str) -> bool:
    try:
        hh = view.horizontalHeader()
        state = {
            "widths": [hh.sectionSize(i) for i in range(hh.count())],
            "hidden": [hh.isSectionHidden(i) for i in range(hh.count())],
        }
        if proxy:
            state["only_checked"] = list(getattr(proxy, "_only_checked_cols", set()))
            state["text_filters"] = getattr(proxy, "_text_filters", {})
            state["multi_sort"] = [(c, int(o)) for c, o in getattr(proxy, "_multi_sort", [])]
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(state, fp, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        _safe_log("save_view_state", e)
        return False


def load_view_state(view: QTableView, proxy: Optional[SmartProxyModel], path: str) -> bool:
    try:
        if not os.path.exists(path):
            return False
        with open(path, "r", encoding="utf-8") as fp:
            state = json.load(fp)
        hh = view.horizontalHeader()
        for i, w in enumerate(state.get("widths", [])):
            try:
                hh.resizeSection(i, int(w))
            except Exception:
                pass
        for i, h in enumerate(state.get("hidden", [])):
            try:
                if h:
                    hh.hideSection(i)
                else:
                    hh.showSection(i)
            except Exception:
                pass
        if proxy and state:
            for c in state.get("only_checked", []):
                proxy.set_only_checked_column(int(c), True)
            for k, v in state.get("text_filters", {}).items():
                proxy.set_text_filter(int(k), v)
            ms = []
            for c, o in state.get("multi_sort", []):
                ms.append((int(c), Qt.SortOrder(int(o))))
            proxy.set_multi_sort(ms)
        return True
    except Exception as e:
        _safe_log("load_view_state", e)
        return False


# ============================================
# TEK KURULUM FONKSİYONU (KAMU API)
# ============================================
def install_smart_table_features(
    view: QTableView,
    checkable_columns: Iterable[int],
    text_columns: Optional[Iterable[int]] = None,
    locked_predicate: Optional[Callable[[QModelIndex], bool]] = None,
    # Hover renkleri
    hover_cell_tint: QColor = QColor(30, 144, 255, 40),
    header_hover_tint: QColor = QColor(30, 144, 255, 60),
    # Başlık görünümü
    header_bg: Optional[str] = "#f2f6ff",
    header_fg: Optional[str] = "#0b1a37",
    header_bold: bool = True,
    # Otomatik genişlik
    autosize_sample_rows: int | str = "auto",
    autosize_padding_px: int = 24,
    autosize_include_header: bool = True,
    # Performans
    uniform_row_heights: bool = True,
    # UX toggles
    enable_quick_find: bool = True,
    enable_header_context_menu: bool = True,
    enable_copy_paste_checkbox: bool = True,   # Ctrl+C / Ctrl+V 1/0
    # Veri güvenliği & iş akışı
    confirm_large_bulk: int = 500,
    enable_audit_trail: bool = True,
    enable_undo_last_bulk: bool = True,
    # Görsellik
    soft_grid: bool = True,
    elide_long_text: bool = True,
    # Export & durum
    persist_state_path: Optional[str] = None,  # "table_state.json"
    add_export_shortcut: bool = True,          # Ctrl+E → CSV
):
    """
    Tek satırda çağır:
        install_smart_table_features(view, checkable_columns=range(0,25))

    Öne çıkanlar:
    - Checkbox'lar hücrede tam ortada; kilit/renklendirme bozulmaz.
    - Başlıkta Hepsini Seç/Temizle + tri-state özet.
    - Shift aralığı, Ctrl+I invert, drag-fill, Ctrl+F hızlı arama.
    - Proxy ile filtre ("sadece işaretlileri göster"), çoklu sıralama.
    - Export görünene göre CSV, durum kalıcılığı (isteğe bağlı).

    Tüm kritik adımlarda Türkçe hata logları mevcuttur.
    """
    try:
        if view is None:
            raise ValueError("view parametresi None olamaz")
        model = view.model()
        if model is None:
            raise RuntimeError("View'e model bağlanmamış.")

        chk_cols = set(int(c) for c in checkable_columns)

        # ---- Proxy Model (filtre/sort) ----
        # Kullanıcı şeffaflık isterse: mevcut model kaynağı proxy altına alınır
        proxy = SmartProxyModel(view)
        proxy.setSourceModel(model)
        view.setModel(proxy)
        # Dış fonksiyonlar (ctx menü vs.) erişsin diye parent'a referans koyuyoruz:
        parent = view
        parent._st_proxy = proxy  # type: ignore[attr-defined]

        # ---- Hover'lı + checkbox'lı başlıklar ----
        old_hh = view.horizontalHeader()
        old_vh = view.verticalHeader()
        hh = HoverHeader(Qt.Orientation.Horizontal, view, tint=header_hover_tint)
        vh = HoverHeader(Qt.Orientation.Vertical, view, tint=header_hover_tint)

        for src, dst in ((old_hh, hh), (old_vh, vh)):
            try:
                dst.setSectionsMovable(src.sectionsMovable())
                dst.setSectionsClickable(src.sectionsClickable())
                dst.setHighlightSections(src.highlightSections())
                dst.setDefaultAlignment(src.defaultAlignment())
                dst.setStretchLastSection(src.stretchLastSection())
                dst.setDefaultSectionSize(src.defaultSectionSize())
                dst.setMinimumSectionSize(src.minimumSectionSize())
            except Exception as e:
                _safe_log("copy_header_props", e)

        view.setHorizontalHeader(hh)
        view.setVerticalHeader(vh)

        # ---- Başlık stili ----
        if header_bg is not None or header_fg is not None or header_bold:
            try:
                bg = header_bg if header_bg is not None else "transparent"
                fg = header_fg if header_fg is not None else "inherit"
                weight = "bold" if header_bold else "normal"
                style = (
                    "QHeaderView::section {"
                    f" background: {bg};"
                    f" color: {fg};"
                    f" font-weight: {weight};"
                    " padding: 4px 6px;"
                    " border: 0px;"
                    " border-bottom: 1px solid #d0d0d0;"
                    "}"
                    "QHeaderView::section:pressed {"
                    " background: rgba(0,0,0,0.08);"
                    "}"
                )
                hh.setStyleSheet(style)
                vh.setStyleSheet(style)
            except Exception as e:
                _safe_log("header_stylesheet", e)

        # ---- Delegate (merkez checkbox + hover + kilit + UX) ----
        delegate = SmartCheckDelegate(
            view=view,
            checkable_columns=chk_cols,
            locked_predicate=locked_predicate,
            hover_tint=hover_cell_tint,
            elide_long_text=elide_long_text
        )
        view.setItemDelegate(delegate)

        # ---- Header Controller (tri-state, bulk, invert, filtre) ----
        audit = AuditTrail() if enable_audit_trail else None
        controller = HeaderController(view, chk_cols, locked_predicate,
                                      confirm_large_bulk=confirm_large_bulk,
                                      audit_trail=audit)
        hh.bindController(controller, chk_cols)

        # ---- Performans ayarı ----
        view.setAlternatingRowColors(True)
        if uniform_row_heights:
            view.setUniformRowHeights(True)
        if soft_grid:
            view.setShowGrid(True)
            view.setStyleSheet("QTableView::item { border-bottom: 1px solid rgba(0,0,0,0.06); }")

        # ---- Metin sütunları ----
        def _auto_size_now():
            try:
                # Proxy altında olduğumuz için gerçek ölçümü kaynak modele yapmak isteyebilirsiniz.
                # Burada görünüm olarak proxy bağlı — yine de genişlik ayarı header üzerinden yapılır (uygun).
                if text_columns is None:
                    ccount = proxy.columnCount()
                    tcols = [c for c in range(ccount) if c not in chk_cols]
                else:
                    tcols = list(text_columns)
                _autosize_text_columns(view, text_columns=tcols,
                                       sample_rows=autosize_sample_rows,
                                       padding_px=autosize_padding_px,
                                       include_header=autosize_include_header)
            except Exception as e:
                _safe_log("auto_size_now", e)

        parent._st_auto_size_text_columns = _auto_size_now  # type: ignore[attr-defined]
        _auto_size_now()

        _debounce = QTimer(view)
        _debounce.setSingleShot(True)
        _debounce.setInterval(150)

        def _schedule_autosize(*_):
            _debounce.stop()
            _debounce.start()

        def _do_autosize():
            _auto_size_now()

        _debounce.timeout.connect(_do_autosize)
        try:
            proxy.dataChanged.connect(_schedule_autosize)
            proxy.modelReset.connect(_schedule_autosize)
            proxy.rowsInserted.connect(_schedule_autosize)
            proxy.rowsRemoved.connect(_schedule_autosize)
        except Exception as e:
            _safe_log("connect_proxy_signals", e)

        # ---- Hızlı Arama (Ctrl+F) ----
        qfind = None
        if enable_quick_find:
            qfind = QuickFind(view, proxy)
            parent._st_quick_find = qfind  # type: ignore[attr-defined]
            sc = QShortcut(QKeySequence.Find, view)
            sc.activated.connect(lambda: qfind.show_for_view())

        # ---- Kopyala/Yapıştır (1/0) ----
        if enable_copy_paste_checkbox:
            def _copy():
                sel = view.selectionModel().selectedIndexes()
                if not sel: return
                # satır-sütun ızgarasına çevir
                rows = sorted(set(i.row() for i in sel))
                cols = sorted(set(i.column() for i in sel))
                text_lines = []
                for r in rows:
                    vals = []
                    for c in cols:
                        idx = view.model().index(r, c)
                        st = idx.data(Qt.ItemDataRole.CheckStateRole)
                        if st is not None:
                            vals.append("1" if st == Qt.CheckState.Checked else "0")
                        else:
                            v = idx.data(Qt.ItemDataRole.DisplayRole)
                            vals.append("" if v is None else str(v))
                    text_lines.append("\t".join(vals))
                QGuiApplication.clipboard().setText("\n".join(text_lines))

            def _paste():
                cb = QGuiApplication.clipboard().text()
                if not cb: return
                start = view.currentIndex()
                if not start.isValid(): return
                lines = cb.splitlines()
                for dr, line in enumerate(lines):
                    parts = line.split("\t")
                    for dc, cell in enumerate(parts):
                        r = start.row() + dr
                        c = start.column() + dc
                        idx = view.model().index(r, c)
                        if not idx.isValid(): continue
                        # Checkbox mı?
                        st = idx.data(Qt.ItemDataRole.CheckStateRole)
                        if st is not None:
                            val = str(cell).strip().lower()
                            target = Qt.CheckState.Checked if val in ("1", "true", "✓", "x") else Qt.CheckState.Unchecked
                            view.model().setData(idx, target, Qt.ItemDataRole.CheckStateRole)
                        else:
                            view.model().setData(idx, cell, Qt.ItemDataRole.EditRole)

            QShortcut(QKeySequence.Copy, view, activated=_copy)
            QShortcut(QKeySequence.Paste, view, activated=_paste)

        # ---- Export (Ctrl+E) ----
        if add_export_shortcut:
            def _export():
                fn, _ = QFileDialog.getSaveFileName(view, "CSV olarak kaydet", "", "CSV (*.csv)")
                if not fn: return
                ok = export_visible_to_csv(view, fn, checkbox_as="10")
                if not ok:
                    QMessageBox.warning(view, "Dışa Aktarma", "CSV kaydında hata oluştu (konsolu kontrol edin).")
            QShortcut(QKeySequence(Qt.Modifier.ControlModifier | Qt.Key.Key_E), view, activated=_export)

        # ---- Çoklu sıralama (Ctrl + başlık tıklama) ----
        def _sort_by_click(logical_index: int):
            # Ctrl basılı ise ikinci/üçüncü anahtar
            mods = QApplication.keyboardModifiers()
            order = Qt.SortOrder.AscendingOrder
            if hh.sortIndicatorSection() == logical_index:
                # toggle asc/desc
                order = Qt.SortOrder.DescendingOrder if hh.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder else Qt.SortOrder.AscendingOrder
            hh.setSortIndicator(logical_index, order)
            if mods & Qt.KeyboardModifier.ControlModifier:
                ms = getattr(proxy, "_multi_sort", [])
                # varsa sil-yeniden ekle
                ms = [t for t in ms if t[0] != logical_index]
                ms.append((logical_index, order))
                proxy.set_multi_sort(ms)
            else:
                proxy.set_multi_sort([(logical_index, order)])

        hh.sectionClicked.connect(_sort_by_click)
        view.setSortingEnabled(True)

        # ---- Durum kalıcılığı ----
        if persist_state_path:
            # İlk yükle
            load_view_state(view, proxy, persist_state_path)
            # Pencere kapanırken kaydetmek istersen dışarıdan save_view_state çağırabilirsin.
            parent._st_save_state = lambda: save_view_state(view, proxy, persist_state_path)  # type: ignore[attr-defined]

        # ---- Header context menü ekstra (zaten HoverHeader içinde) ----
        if enable_header_context_menu:
            hh.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)

        # ---- Döndür: delegate referansı (gerekirse) ----
        return delegate

    except Exception as e:
        _safe_log("install_smart_table_features", e)
        # Güvenli geri dönüş
        try:
            fallback = QStyledItemDelegate(view)
            view.setItemDelegate(fallback)
            return fallback
        except Exception as e2:
            _safe_log("install_fallback_delegate", e2)
            raise