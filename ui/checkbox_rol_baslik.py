from __future__ import annotations
# ui/checkbox_rol_baslik.py
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QAbstractItemView, QTableWidget, QTableView, QTableWidgetItem,
    QHeaderView, QCheckBox
)

class CheckBoxRolVeBaslikAyarlayici:
    """
    - Hücrede QCheckBox widget varsa güvenle CheckStateRole'a çevirir.
      * SADECE checkable flag ekler; enabled/disabled flags'a dokunmaz.
      * Metin/renk/tooltip gibi roller aynen kalır.
    - Sadece checkbox kolonlarının genişliğini, başlık metni kadar ayarlar.
      * Bu kolonları Fixed yapar; diğer kolonların modlarına dokunmaz.
    - Tablo henüz dolmadıysa 0 ms sonra kendini tekrar dener.
    """

    def uygula(self, tablo: QAbstractItemView,
               hedef_kolonlar: list[int] | None = None,
               padding: int = 28, min_w: int = 46, max_w: int = 320,
               pekistir_ms: int = 0):
        if not tablo or not hasattr(tablo, "model") or tablo.model() is None:
            return

        m = tablo.model()
        rows, cols = m.rowCount(), m.columnCount()

        # Veri henüz yoksa bir tik sonra tekrar dene
        if rows == 0 or cols == 0:
            QTimer.singleShot(0, lambda: self.uygula(tablo, hedef_kolonlar, padding, min_w, max_w, pekistir_ms))
            return

        # 1) Hedef checkbox kolonlarını bul
        if hedef_kolonlar is None:
            hedef_kolonlar = self._tahmin_checkbox_kolonlari(tablo, tarama_satir=min(12, rows))

        if not hedef_kolonlar:
            # Checkbox kolonu yoksa yalnızca çık
            return

        # 2) QCheckBox widget -> role (yalnızca başarı olursa widget'ı kaldır)
        for c in hedef_kolonlar:
            if c < 0 or c >= cols:
                continue
            for r in range(rows):
                self._widgeti_role_cevir(tablo, r, c)

        # 3) Başlık genişliği: SADECE bu kolonlar Fixed + header metni kadar
        self._checkbox_kolon_genislikleri(tablo, hedef_kolonlar, padding, min_w, max_w)

        # 4) Pekiştir: başka yerler header modunu değiştiriyorsa kısa gecikme ile tekrar uygula
        if pekistir_ms > 0:
            QTimer.singleShot(pekistir_ms,
                              lambda: self._checkbox_kolon_genislikleri(tablo, hedef_kolonlar, padding, min_w, max_w))

    # ---------- yardımcılar ----------
    def _tahmin_checkbox_kolonlari(self, tablo, tarama_satir=8) -> list[int]:
        m = tablo.model()
        cols = m.columnCount()
        rows = min(m.rowCount(), tarama_satir)
        aday = set()

        # 1) Role ile işaretli hücre var mı?
        for c in range(cols):
            for r in range(rows):
                idx = m.index(r, c)
                if (idx.flags() & Qt.ItemFlag.ItemIsUserCheckable) and \
                   (m.data(idx, Qt.ItemDataRole.CheckStateRole) is not None):
                    aday.add(c); break

        # 2) Widget tabanlı checkbox var mı? (eski düzen)
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

    def _widgeti_role_cevir(self, tablo, r, c):
        m = tablo.model()
        w = self._get_widget(tablo, r, c)
        if w is None:
            return

        cb = w if isinstance(w, QCheckBox) else w.findChild(QCheckBox)
        if cb is None:
            return

        state = Qt.CheckState.Checked if cb.isChecked() else Qt.CheckState.Unchecked

        if isinstance(tablo, QTableWidget):
            it = tablo.item(r, c)
            if it is None:
                it = QTableWidgetItem()
                tablo.setItem(r, c, it)
            # SADECE checkable ekle; enabled/disabled mevcut neyse o kalsın
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            ok = m.setData(m.index(r, c), state, Qt.ItemDataRole.CheckStateRole)
            if ok:
                self._remove_widget(tablo, r, c)

        elif isinstance(tablo, QTableView):
            idx = m.index(r, c)
            ok = m.setData(idx, state, Qt.ItemDataRole.CheckStateRole)
            if ok:
                self._remove_widget(tablo, r, c)

    def _checkbox_kolon_genislikleri(self, tablo, kolonlar, padding, min_w, max_w):
        header = getattr(tablo, "horizontalHeader", lambda: None)()
        m = tablo.model()
        if not header or not m:
            return
        fm = header.fontMetrics()
        for c in kolonlar:
            if c < 0 or c >= m.columnCount():
                continue
            txt = str(m.headerData(c, Qt.Orientation.Horizontal) or "")
            w = fm.horizontalAdvance(txt) + padding
            w = max(min_w, min(max_w, w))
            # SADECE bu kolonları Fixed yapıp genişliği uygula
            header.setSectionResizeMode(c, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(c, w)
