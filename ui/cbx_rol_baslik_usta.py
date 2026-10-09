from __future__ import annotations
# ui/cbx_rol_baslik_usta.py
from PyQt6.QtCore import Qt, QTimer, QObject
from PyQt6.QtWidgets import (
    QAbstractItemView, QTableWidget, QTableView, QTableWidgetItem,
    QHeaderView, QCheckBox, QStyledItemDelegate, QApplication, QStyle,
    QStyleOption, QStyleOptionViewItem
)
from PyQt6.QtCore import QRect, QEvent

class _MerkezCheckDelegesi(QStyledItemDelegate):
    """Rol tabanlı checkbox'ı hücre merkezine çizer; veri/flags/renkleri değiştirmez."""
    def paint(self, painter, option: QStyleOptionViewItem, index):
        flags = index.flags()
        if not (flags & Qt.ItemFlag.ItemIsUserCheckable):
            return super().paint(painter, option, index)
        cs = index.data(Qt.ItemDataRole.CheckStateRole)
        if cs is None:
            return super().paint(painter, option, index)

        base = QStyleOptionViewItem(option)
        base.features &= ~QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator  # soldaki varsayılanı kapat
        super().paint(painter, base, index)  # arkaplan/selection senin rollerine göre

        style = option.widget.style() if option.widget else QApplication.style()
        ind = style.subElementRect(QStyle.SubElement.SE_ItemViewItemCheckIndicator, base, option.widget)
        r = option.rect
        hedef = QRect(r.x() + (r.width() - ind.width()) // 2,
                      r.y() + (r.height() - ind.height()) // 2,
                      ind.width(), ind.height())

        st = QStyle.StateFlag.State_Enabled if (flags & Qt.ItemFlag.ItemIsEnabled) else QStyle.StateFlag(0)
        if cs == Qt.CheckState.Checked:            st |= QStyle.StateFlag.State_On
        elif cs == Qt.CheckState.PartiallyChecked: st |= QStyle.StateFlag.State_NoChange
        else:                                      st |= QStyle.StateFlag.State_Off

        opt = QStyleOption(); opt.rect = hedef; opt.state = st
        style.drawPrimitive(QStyle.PrimitiveElement.PE_IndicatorItemViewItemCheck, opt, painter, option.widget)

    def editorEvent(self, event, model, option, index):
        if not (index.flags() & Qt.ItemFlag.ItemIsUserCheckable): return False
        if not (index.flags() & Qt.ItemFlag.ItemIsEnabled):       return False
        t = event.type()
        if t in (QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick, QEvent.Type.KeyPress):
            cs = index.data(Qt.ItemDataRole.CheckStateRole)
            if cs is None: return False
            yeni = Qt.CheckState.Unchecked if cs == Qt.CheckState.Checked else Qt.CheckState.Checked
            return model.setData(index, yeni, Qt.ItemDataRole.CheckStateRole)
        return False


class CheckBoxRolVeBaslikUsta(QObject):
    """
    Tek çağrıyla:
      - QCheckBox widget -> CheckStateRole (yıkımsız)
      - Sadece checkbox kolonlarını başlık kadar yap (Fixed + resizeSection)
      - Checkbox'ları merkezde çizen delegeyi atar
      - Geometri/sinyal değişimlerinde kendini pekiştirir
    """

    def __init__(self, ebeveyn=None):
        super().__init__(ebeveyn)
        self._delegate = _MerkezCheckDelegesi(self)
        self._takip = {}  # view_id -> {cols, conn}

    # ----- dış API -----
    def kur(self, tablo: QAbstractItemView, hedef_kolonlar: list[int] | None = None,
            padding: int = 28, min_w: int = 46, max_w: int = 320):
        if not tablo or not hasattr(tablo, "model") or tablo.model() is None:
            return

        vid = id(tablo)
        self._takip.setdefault(vid, {"cols": [], "conns": []})

        def _apply():
            cols = self._ensure_role_and_find_cols(tablo, hedef_kolonlar)
            if not cols:
                return
            self._takip[vid]["cols"] = cols
            self._apply_delegate(tablo, cols)
            self._apply_header_widths(tablo, cols, padding, min_w, max_w)

        # İlk uygulama + 50ms pekiştirme (başka kodlar müdahale ediyorsa)
        QTimer.singleShot(0, _apply)
        QTimer.singleShot(50, _apply)

        # Bir kez bağla: header/model değişince yeniden uygula
        if not self._takip[vid]["conns"]:
            h = getattr(tablo, "horizontalHeader", lambda: None)()
            m = tablo.model()
            conns = []
            if h:
                conns.append(h.sectionResized.connect(lambda *_: _apply))
                conns.append(h.geometriesChanged.connect(_apply))
            # model sinyalleri
            for sig in ("modelReset", "layoutChanged", "dataChanged", "rowsInserted", "rowsRemoved",
                        "columnsInserted", "columnsRemoved"):
                if hasattr(m, sig):
                    getattr(m, sig).connect(lambda *args, _=_apply: _())
                    conns.append(True)
            self._takip[vid]["conns"] = conns

    # ----- iç: role + kolon tespiti -----
    def _ensure_role_and_find_cols(self, tablo, hedef_kolonlar):
        m = tablo.model()
        rows, cols = m.rowCount(), m.columnCount()
        if rows == 0 or cols == 0:
            return []

        # 1) hedefleri belirle
        if hedef_kolonlar is None:
            hedef_kolonlar = self._guess_checkbox_cols(tablo, min(12, rows))

        # 2) varsa widget -> role (yalnızca checkable flag ekler; enabled aynen kalır)
        for c in hedef_kolonlar:
            if c < 0 or c >= cols: continue
            for r in range(rows):
                self._widget_to_role(tablo, r, c)

        return hedef_kolonlar

    def _guess_checkbox_cols(self, tablo, tarama_satir=8):
        m = tablo.model()
        cols = m.columnCount()
        rows = min(m.rowCount(), tarama_satir)
        aday = set()

        # Role ile checkable olanlar
        for c in range(cols):
            for r in range(rows):
                idx = m.index(r, c)
                if (idx.flags() & Qt.ItemFlag.ItemIsUserCheckable) and \
                   (m.data(idx, Qt.ItemDataRole.CheckStateRole) is not None):
                    aday.add(c); break

        # Widget barındıranlar
        for c in range(cols):
            for r in range(rows):
                w = self._get_widget(tablo, r, c)
                if isinstance(w, QCheckBox) or (w and w.findChild(QCheckBox)):
                    aday.add(c); break

        return sorted(aday)

    def _get_widget(self, tablo, r, c):
        if isinstance(tablo, QTableWidget):
            return tablo.cellWidget(r, c)
        if isinstance(tablo, QTableView):
            idx = tablo.model().index(r, c)
            return tablo.indexWidget(idx)
        return None

    def _remove_widget(self, tablo, r, c):
        if isinstance(tablo, QTableWidget):
            if tablo.cellWidget(r, c):
                tablo.removeCellWidget(r, c)
        elif isinstance(tablo, QTableView):
            idx = tablo.model().index(r, c)
            tablo.setIndexWidget(idx, None)

    def _widget_to_role(self, tablo, r, c):
        m = tablo.model()
        w = self._get_widget(tablo, r, c)
        if not w:
            return
        cb = w if isinstance(w, QCheckBox) else w.findChild(QCheckBox)
        if not cb:
            return

        state = Qt.CheckState.Checked if cb.isChecked() else Qt.CheckState.Unchecked

        if isinstance(tablo, QTableWidget):
            it = tablo.item(r, c)
            if it is None:
                it = QTableWidgetItem()
                # Metne dokunma (boş bırak; varsa korunur)
                tablo.setItem(r, c, it)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)  # sadece checkable ekle
            ok = m.setData(m.index(r, c), state, Qt.ItemDataRole.CheckStateRole)
            if ok:
                self._remove_widget(tablo, r, c)
        else:  # QTableView
            idx = m.index(r, c)
            ok = m.setData(idx, state, Qt.ItemDataRole.CheckStateRole)
            if ok:
                self._remove_widget(tablo, r, c)

    # ----- iç: delege + başlık genişliği -----
    def _apply_delegate(self, tablo, cols):
        for c in cols:
            tablo.setItemDelegateForColumn(c, self._delegate)

    def _apply_header_widths(self, tablo, cols, padding, min_w, max_w):
        header = getattr(tablo, "horizontalHeader", lambda: None)()
        m = tablo.model()
        if not header or not m:
            return
        fm = header.fontMetrics()
        for c in cols:
            if c < 0 or c >= m.columnCount(): continue
            txt = str(m.headerData(c, Qt.Orientation.Horizontal) or "")
            w = fm.horizontalAdvance(txt) + padding
            w = max(min_w, min(max_w, w))
            header.setSectionResizeMode(c, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(c, w)
