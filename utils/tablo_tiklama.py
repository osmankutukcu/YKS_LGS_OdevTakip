from PyQt6 import QtCore, QtGui, QtWidgets

class _FastCheckboxFilter(QtCore.QObject):
    """Ultra hızlı ve kararlı checkbox tıklama filtresi (Windows/macOS uyumlu)."""
    def __init__(self, table, checkbox_columns, locked_colors=None):
        super().__init__(table)
        self.table = table
        self.checkbox_columns = set(checkbox_columns)
        self.locked_colors = {c.lower() for c in (locked_colors or set())}

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Type.MouseButtonPress and event.button() == QtCore.Qt.MouseButton.LeftButton:
            index = self.table.indexAt(event.pos())
            if not index.isValid() or index.column() not in self.checkbox_columns:
                return False

            it = self.table.item(index.row(), index.column())
            if not it:
                return False

            # Kilitli renkleri tespit et (ör. sarı veya yeşil hücreler)
            try:
                bg = it.background().color().name().lower()
                if bg in self.locked_colors:
                    return True  # kilitliyse olayı yut, değişme
            except Exception:
                pass

            # Toggle işlemi — tek satırda ultra hızlı
            st = it.data(QtCore.Qt.ItemDataRole.CheckStateRole)
            new_st = QtCore.Qt.CheckState.Unchecked if st == QtCore.Qt.CheckState.Checked else QtCore.Qt.CheckState.Checked
            it.setData(QtCore.Qt.ItemDataRole.CheckStateRole, new_st)

            # Görseli yalnızca tek hücre için yenile (performans)
            try:
                rect = self.table.visualRect(index)
                self.table.viewport().update(rect)
            except Exception:
                self.table.viewport().update()

            return True
        return False


def install_safe_checkbox_click(table, checkbox_columns, locked_colors=None):
    """
    Tüm tabloya hızlı checkbox tıklama desteği ekler.
    - checkbox_columns: tıklanabilir sütun indeksleri listesi (ör. [1,2,3])
    - locked_colors: tiklenmesi engellenecek arka plan renkleri (ör. {"#A5D6A7","#FFF59D"})
    """
    if not isinstance(table, QtWidgets.QTableWidget):
        return

    # Eski filtreleri kaldır
    for f in table.findChildren(_FastCheckboxFilter):
        table.removeEventFilter(f)

    filt = _FastCheckboxFilter(table, checkbox_columns, locked_colors)
    table.installEventFilter(filt)
    table._fast_checkbox_filter = filt  # GC koruması

    # Küçük optimizasyon: performans ve UX
    table.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
    table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
    table.setMouseTracking(False)
    table.viewport().setAttribute(QtCore.Qt.WidgetAttribute.WA_Hover, False)