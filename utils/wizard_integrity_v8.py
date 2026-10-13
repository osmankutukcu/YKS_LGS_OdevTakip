"""Akıllı Sihirbaz için kimlik ve birebir eşleşme denetimleri (Qt bağımsız)."""
from __future__ import annotations
from functools import lru_cache

def normalized_identity(value):
    try:
        if value is None or isinstance(value, bool):
            return None
        ident = int(str(value).strip())
        return ident if ident > 0 else None
    except (TypeError, ValueError):
        return None

def same_student(a, b):
    aa, bb = normalized_identity(a), normalized_identity(b)
    return aa is not None and aa == bb

@lru_cache(maxsize=4096)
def _normalized_string(text: str) -> str:
    """V31: cache deterministic name normalization; bounded for institutions."""
    # Unicode 'İ' -> 'i' + combining dot; eşleşme bu yüzden bozulmasın.
    return " ".join(text.split()).casefold().replace("\u0307", "").replace("ı", "i")


def normalized_name(value):
    # Convert BEFORE cache access: preserves legacy support for arbitrary,
    # even unhashable input objects. This never caches student records.
    return _normalized_string(str(value or ""))

def exact_task_key(ders, kitap, konu):
    return (normalized_name(ders), normalized_name(kitap), normalized_name(konu))

def valid_task(task):
    if not isinstance(task, dict):
        return False
    return all(exact_task_key(task.get("ders"), task.get("kitap"), task.get("konu")))

def find_exact_cell(matrix, lesson, book, topic):
    """Sadece birebir kitap/konu adı eşleşmesi; kısmi isim/substring yok."""
    target_lesson = normalized_name(lesson)
    target_book = normalized_name(book)
    target_topic = normalized_name(topic)
    if not all((target_lesson, target_book, target_topic)):
        return (None, None, None)
    table = next((t for d, t in (matrix or {}).items()
                  if normalized_name(d) == target_lesson), None)
    if table is None:
        return (None, None, None)
    col = next((j for j in range(1, table.columnCount())
                if table.horizontalHeaderItem(j) is not None
                and normalized_name(table.horizontalHeaderItem(j).text()) == target_book), None)
    row = next((i for i in range(table.rowCount())
                if table.item(i, 0) is not None
                and normalized_name(table.item(i, 0).text()) == target_topic), None)
    return (table, row, col) if row is not None and col is not None else (None, None, None)
