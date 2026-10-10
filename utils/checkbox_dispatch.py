# -*- coding: utf-8 -*-
"""Tıklama kuyruğunun Qt bağımsız ve test edilebilir parçası.

Her hücrenin sadece *son* kullanıcı seçim sonucu işlenir. Farklı hücreler
ilk olay sırasını korur. Nihai işaretler sağdaki ödev listesini belirler.
"""
from collections import OrderedDict


class PendingCheckboxChanges:
    def __init__(self):
        self._items = OrderedDict()

    def push(self, row: int, col: int) -> None:
        self._items[(int(row), int(col))] = None

    def drain(self):
        keys = tuple(self._items)
        self._items.clear()
        return keys

    def __bool__(self):
        return bool(self._items)

    def __len__(self):
        return len(self._items)
