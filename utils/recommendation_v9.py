"""Öğretmen onaylı öneri paketlemesi, Qt/veritabanı bağımsız."""
from __future__ import annotations

def select_within_capacity(items, target_minutes, tolerance=0, diverse_books=False):
    """Düzenli, stabil greedy: hedef+tolerans ASLA aşılmaz, işlem sadece seçimdir."""
    limit = max(0, int(target_minutes)) + max(0, int(tolerance))
    from utils.wizard_integrity_v8 import exact_task_key
    selected, seen_books, seen_tasks, used = [], set(), set(), 0
    for t in items or []:
        if not isinstance(t, dict):
            continue
        try:
            minutes = int(t.get('dk') or 0)
        except (TypeError, ValueError):
            continue
        if minutes <= 0 or used + minutes > limit:
            continue
        key = exact_task_key(t.get('ders'), t.get('kitap'), t.get('konu'))
        if not all(key) or key in seen_tasks:
            continue
        book = key[1]
        if diverse_books and book in seen_books:
            continue
        selected.append(t)
        used += minutes
        seen_tasks.add(key)
        seen_books.add(book)
    return selected
