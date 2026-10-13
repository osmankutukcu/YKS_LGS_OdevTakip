"""Read-only capture of homework rows for the weekly calendar.

Hidden rows are filter state only. Never mutate the table or mark any homework
as completed. This service is Qt-free and can be verified with dummy tables.
"""
from __future__ import annotations

from datetime import date
from typing import Any


def snapshot_homework_table(table: Any, *, deadline: date | None = None) -> list[dict]:
    if deadline is not None and deadline < date.today():
        raise ValueError('Ödevin bitiş tarihi geçmiş. Önce bitiş tarihini güncelleyin.')
    if table is None or table.rowCount() == 0:
        return []
    result = []
    for r in range(table.rowCount()):
        def cell(col: int) -> str:
            item = table.item(r, col)
            return (item.text() if item is not None else '').strip()
        ders, kitap, konu, minute_text = (cell(col) for col in range(4))
        if not ders or not konu:
            raise ValueError(f'{r+1}. ödev satırında ders veya konu eksik.')
        if not minute_text.isdecimal() or not 5 <= int(minute_text) <= 600:
            raise ValueError(f'{r+1}. ödev satırının süresi 5–600 dakika arasında sayı olmalı.')
        task = {'ders': ders, 'kitap': kitap, 'konu': konu, 'sure': int(minute_text)}
        if deadline is not None:
            task['deadline'] = deadline.isoformat()
        result.append(task)
    return result
