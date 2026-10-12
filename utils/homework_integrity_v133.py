"""V13.3: Strict row matching and read-only student-scoped completion queries.

No schema mutation. No guessing from another student's history.
"""
from __future__ import annotations

from utils.wizard_integrity_v8 import normalized_identity, normalized_name, find_exact_cell

DONE_STATES = ("yapildi", "yapıldı", "tamam", "bitti")


def unique_exact_cell(matrix, lesson, book, topic):
    """Fail closed on ambiguous duplicate book headers or topic rows."""
    table, row, col = find_exact_cell(matrix, lesson, book, topic)
    if table is None:
        return None, None, None
    expected_topic = normalized_name(topic)
    expected_book = normalized_name(book)
    expected_lesson = normalized_name(lesson)
    matching_lessons = [t for d, t in (matrix or {}).items()
                        if normalized_name(d) == expected_lesson]
    if len(matching_lessons) != 1:
        return None, None, None
    rows = [i for i in range(table.rowCount())
            if table.item(i, 0) is not None
            and normalized_name(table.item(i, 0).text()) == expected_topic]
    cols = [j for j in range(1, table.columnCount())
            if table.horizontalHeaderItem(j) is not None
            and normalized_name(table.horizontalHeaderItem(j).text()) == expected_book]
    if len(rows) != 1 or len(cols) != 1:
        return None, None, None
    return table, row, col


def _table_columns(conn, table):
    """Query only from trusted, fixed table identifiers."""
    if table not in ("odev", "odev_satir"):
        return set()
    try:
        return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}
    except Exception:
        return set()


def student_completed_task(conn, student_id, lesson, book, topic):
    """True only for a recorded completed task belonging to this student.

    Both historical homework tables are checked if available. Deleted rows
    never count, and a task without a student ID cannot prove completion.
    """
    sid = normalized_identity(student_id)
    fields = (normalized_name(lesson), normalized_name(book), normalized_name(topic))
    if sid is None or not all(fields) or conn is None:
        return False
    for table, book_col, topic_col in (
        ("odev", "kitap_ad", "konu_ad"),
        ("odev_satir", "kitap", "konu"),
    ):
        cols = _table_columns(conn, table)
        required = {"ogrenci_id", "ders", "durum", book_col, topic_col}
        if not required.issubset(cols):
            continue
        deleted_filter = " AND COALESCE(silindi, 0)=0" if "silindi" in cols else ""
        # Case normalization for Turkish dotted/undotted I is finalized in
        # Python rather than relying on SQLite's ASCII-only LOWER().
        sql = f"""SELECT ders, {book_col}, {topic_col}, durum
                    FROM {table}
                   WHERE ogrenci_id=? AND durum IS NOT NULL{deleted_filter}"""
        try:
            rows = conn.execute(sql, (sid,))
            for record in rows:
                row = tuple(record)
                if (normalized_name(row[0]), normalized_name(row[1]), normalized_name(row[2])) != fields:
                    continue
                if normalized_name(row[3]) in {normalized_name(s) for s in DONE_STATES}:
                    return True
        except Exception:
            # An unavailable historical table must never become "completed".
            continue
    return False
