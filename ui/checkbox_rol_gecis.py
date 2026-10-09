from __future__ import annotations
# ui/checkbox_rol_gecis.py
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QTableWidget, QTableView, QTableWidgetItem, QCheckBox, QAbstractItemView
)

class CheckBoxRolDonusturucu:
    """
    Hücreye widget olarak yerleştirilmiş QCheckBox'ları,
    rol tabanlı (ItemIsUserCheckable + CheckStateRole) hücrelere dönüştürür.
    """

    def uygula(self, gorunum: QAbstractItemView, kolonlar: list[int] | None = None, ui_hazir_sonra: bool = True):
        if not gorunum or not gorunum.model():
            return
        if ui_hazir_sonra:
            QTimer.singleShot(0, lambda: self._uygula_ic(gorunum, kolonlar))
        else:
            self._uygula_ic(gorunum, kolonlar)

    # ------------- iç -------------
    def _uygula_ic(self, gorunum: QAbstractItemView, kolonlar: list[int] | None):
        m = gorunum.model()
        rows, cols = m.rowCount(), m.columnCount()
        if kolonlar is None:
            kolonlar = self._tahmin_checkbox_kolonlari(gorunum, cols)

        for c in kolonlar:
            if c < 0 or c >= cols:
                continue
            for r in range(rows):
                self._donustur_hucre(gorunum, r, c)

    def _get_widget(self, gorunum, r, c):
        if isinstance(gorunum, QTableWidget):
            return gorunum.cellWidget(r, c)
        if isinstance(gorunum, QTableView):
            idx = gorunum.model().index(r, c)
            return gorunum.indexWidget(idx)
        return None

    def _remove_widget(self, gorunum, r, c):
        if isinstance(gorunum, QTableWidget):
            if gorunum.cellWidget(r, c):
                gorunum.removeCellWidget(r, c)
        elif isinstance(gorunum, QTableView):
            idx = gorunum.model().index(r, c)
            gorunum.setIndexWidget(idx, None)

    def _donustur_hucre(self, gorunum, r, c):
        w = self._get_widget(gorunum, r, c)
        if w is None:
            return

        cb = w if isinstance(w, QCheckBox) else w.findChild(QCheckBox)
        if cb is None:
            return

        state = Qt.CheckState.Checked if cb.isChecked() else Qt.CheckState.Unchecked

        if isinstance(gorunum, QTableWidget):
            it = gorunum.item(r, c)
            if it is None:
                it = QTableWidgetItem()
                gorunum.setItem(r, c, it)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            it.setCheckState(state)
            self._remove_widget(gorunum, r, c)

        elif isinstance(gorunum, QTableView):
            idx = gorunum.model().index(r, c)
            gorunum.model().setData(idx, state, Qt.ItemDataRole.CheckStateRole)
            self._remove_widget(gorunum, r, c)

    def _tahmin_checkbox_kolonlari(self, gorunum, col_count: int, taranacak_satir: int = 10) -> list[int]:
        m = gorunum.model()
        rows = min(m.rowCount(), taranacak_satir)
        aday = set()
        for c in range(col_count):
            for r in range(rows):
                w = self._get_widget(gorunum, r, c)
                if not w:
                    continue
                if isinstance(w, QCheckBox) or w.findChild(QCheckBox):
                    aday.add(c); break
        return sorted(aday)
