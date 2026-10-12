"""V13.5: minimal, read-only integrity report opened explicitly by teacher."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QMessageBox,
)

from services.homework_integrity_v135 import AuditResult, audit_database, audit_draft_matrix


def snapshot_form(form) -> tuple[list[dict], list[dict]]:
    cells = []
    for lesson, table in (getattr(form, "_ders_tablolari", {}) or {}).items():
        for row in range(table.rowCount()):
            topic = table.item(row, 0)
            if topic is None:
                continue
            for col in range(1, table.columnCount()):
                book = table.horizontalHeaderItem(col)
                cell = table.item(row, col)
                if book is None or cell is None:
                    continue
                cells.append({
                    "ders": lesson, "kitap": book.text(), "konu": topic.text(),
                    "checked": cell.checkState() == Qt.CheckState.Checked,
                    "locked": not bool(cell.flags() & Qt.ItemFlag.ItemIsUserCheckable),
                })
    tasks = []
    table = getattr(form, "verilen", None)
    if table is not None:
        # Read source rows; do not filter by current visual sort, search or selection.
        for row in range(table.rowCount()):
            texts = []
            for col in range(3):
                item = table.item(row, col)
                texts.append(item.text() if item is not None else "")
            if any(texts):
                tasks.append(dict(zip(("ders", "kitap", "konu"), texts)))
    return cells, tasks


def open_readonly_database(path: Path) -> sqlite3.Connection:
    path = Path(path).expanduser().resolve(strict=True)
    # SQLite's read-only URI, without immutable=1 (which would ignore WAL updates).
    con = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)
    con.execute("PRAGMA query_only=ON")
    return con


def summarize(result: AuditResult, title: str) -> str:
    lines = [title, "=" * len(title)]
    for item in result.findings:
        lines.append(f"[{item.severity.upper()}] {item.message}  |  Adet: {item.count}")
        if item.references:
            lines.append("  Örnek kayıt/hücre: " + "; ".join(item.references))
        if item.guidance:
            lines.append("  Öneri: " + item.guidance)
    if not result.findings:
        lines.append("Kontrol edilen veri alanlarında sorun bulunmadı.")
    if result.notes:
        lines.append("\nSınırlar ve açıklamalar:")
        lines.extend("- " + note for note in result.notes)
    return "\n".join(lines)


class IntegrityDialog(QDialog):
    def __init__(self, form, db_path: Path, parent=None):
        super().__init__(parent or form)
        self.setWindowTitle("🔎 Ödev Veri Denetimi — V13.5")
        self.resize(760, 550)
        layout = QVBoxLayout(self)
        head = QLabel("Öğrenci bazlı taslak denetimi + veritabanı bağlantı kontrolü")
        head.setStyleSheet("font-weight:600; font-size:14px;")
        layout.addWidget(head)
        note = QLabel("Salt okunur: Tikler, ödevler, öğrenci kayıtları ve veritabanı değiştirilmez.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.content = QPlainTextEdit(self)
        self.content.setReadOnly(True)
        layout.addWidget(self.content)
        row = QHBoxLayout()
        copy = QPushButton("Raporu Kopyala")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.content.toPlainText()))
        close = QPushButton("Kapat")
        close.clicked.connect(self.accept)
        row.addStretch(1)
        row.addWidget(copy)
        row.addWidget(close)
        layout.addLayout(row)
        self._run(form, db_path)

    def _run(self, form, db_path):
        # Database scan intentionally independent from student selection.
        parts = []
        try:
            with open_readonly_database(db_path) as con:
                parts.append(summarize(audit_database(con), "VERİTABANI BAĞLANTILARI"))
        except Exception as exc:
            parts.append("VERİTABANI: Salt okunur açma / kontrol başarısız: " + str(exc))
        try:
            selected = form._secili_ogrenci_id()
            loaded = getattr(form, "_loaded_student_id", None)
            cells, tasks = snapshot_form(form)
            report = audit_draft_matrix(cells, tasks,
                                        selected_student=selected, loaded_student=loaded)
            parts.append(summarize(report, "SEÇİLİ ÖĞRENCİNİN KAYDEDİLMEMİŞ TASLAĞI"))
        except Exception as exc:
            parts.append("TASLAK: Ekran görüntüsü kontrol edilemedi: " + str(exc))
        parts.append("ÖNEMLİ: Bu sonuçlar otomatik düzeltme talimatı değildir. "
                     "Kayıtlı sarı/yeşil hücreler ile tarihsel ödevler ayrı korunur.")
        self.content.setPlainText("\n\n".join(parts))
