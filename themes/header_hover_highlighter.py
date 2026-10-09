# ui/theme/header_hover_highlighter.py
from PyQt6.QtCore import QObject, Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import QAbstractItemView

class HeaderHoverHighlighter(QObject):
    """
    Hücre üzerinde fare gezerken ilgili sütun ve satır başlığını (header)
    FG/BG olarak renklendirir, ayrılınca geri alır.
    """
    def __init__(self, view: QAbstractItemView,
                 text_color="#2d89ef", bg_color="#E8F1FF",
                 head_default_fg="#2B2F33", head_default_bg="#FFFFFF"):
        super().__init__(view)
        self.view = view
        self.text_color = QColor(text_color)
        self.bg_color = QColor(bg_color)
        self.default_fg = QColor(head_default_fg)
        self.default_bg = QColor(head_default_bg)
        self._prev_col = -1
        self._prev_row = -1
        self._installed = False

    def install(self):
        if self._installed:
            return
        v = self.view
        v.viewport().installEventFilter(self)
        v.viewport().setMouseTracking(True)
        v.setMouseTracking(True)
        if v.model():
            v.model().modelReset.connect(self._reset_all, Qt.ConnectionType.UniqueConnection)
            v.model().layoutChanged.connect(self._reset_all, Qt.ConnectionType.UniqueConnection)
            v.model().headerDataChanged.connect(lambda *a, **k: None, Qt.ConnectionType.UniqueConnection)
        if v.selectionModel():
            v.selectionModel().selectionChanged.connect(self._on_selection_changed, Qt.ConnectionType.UniqueConnection)
            v.selectionModel().currentChanged.connect(self._on_current_changed, Qt.ConnectionType.UniqueConnection)
        self._installed = True

    # === event filter ===
    def eventFilter(self, obj, event):
        et = event.type()
        name = getattr(et, "name", None)
        if name is None:
            name = str(et)
        if "MouseMove" in name:
            self._on_mouse_move(event)
        elif "Leave" in name or "Hide" in name:
            self._clear_hover()
        return super().eventFilter(obj, event)

    # === helpers ===
    def _on_mouse_move(self, event):
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        idx = self.view.indexAt(pos)
        if not idx.isValid():
            self._clear_hover()
            return
        self._highlight(idx.column(), idx.row())

    def _on_selection_changed(self, *_):
        idx = self.view.currentIndex()
        if idx and idx.isValid():
            self._highlight(idx.column(), idx.row())

    def _on_current_changed(self, current, _):
        if current and current.isValid():
            self._highlight(current.column(), current.row())
        else:
            self._clear_hover()

    def _reset_all(self):
        self._apply_header(self._prev_col, horizontal=True,  fg=self.default_fg, bg=self.default_bg)
        self._apply_header(self._prev_row, horizontal=False, fg=self.default_fg, bg=self.default_bg)
        self._prev_col = self._prev_row = -1

    def _clear_hover(self):
        self._reset_all()

    def _highlight(self, col, row):
        if col != self._prev_col:
            self._apply_header(self._prev_col, horizontal=True,  fg=self.default_fg, bg=self.default_bg)
            self._apply_header(col,        horizontal=True,  fg=self.text_color, bg=self.bg_color)
            self._prev_col = col
        if row != self._prev_row:
            self._apply_header(self._prev_row, horizontal=False, fg=self.default_fg, bg=self.default_bg)
            self._apply_header(row,        horizontal=False, fg=self.text_color, bg=self.bg_color)
            self._prev_row = row

    def _apply_header(self, section, *, horizontal, fg: QColor, bg: QColor):
        if section is None or section < 0:
            return
        m = self.view.model()
        if not m:
            return
        orient = Qt.Orientation.Horizontal if horizontal else Qt.Orientation.Vertical
        m.setHeaderData(section, orient, QBrush(fg), Qt.ItemDataRole.ForegroundRole)
        m.setHeaderData(section, orient, QBrush(bg), Qt.ItemDataRole.BackgroundRole)