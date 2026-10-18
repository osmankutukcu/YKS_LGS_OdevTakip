# -*- coding: utf-8 -*-
"""Teacher-owned question *templates* only. No student identity or answer storage.

A user must explicitly save a question. Recent queries stay in process memory.
Persistence is per OS profile, not shared by a classroom or server.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata

MAX_QUESTIONS = 25
MAX_LENGTH = 180
MAX_FILE_BYTES = 16_384

# Obvious personal identifiers are never persisted. A name is hard to detect,
# so the UI tells teachers not to save names or other identifiable details.
_PRIVATE_PATTERN = re.compile(
    r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|"
    r"(?<!\d)(?:\+?90\s*)?(?:0\s*)?5\d{2}[\s-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}(?!\d)|"
    r"(?<!\d)\d{11}(?!\d)",
    re.IGNORECASE,
)


def normalize_question(raw: str) -> str:
    if not isinstance(raw, str):
        raise ValueError("Soru metin olmalıdır.")
    value = " ".join(raw.split())
    if not value:
        raise ValueError("Kaydedilecek bir soru yazın.")
    if len(value) > MAX_LENGTH:
        raise ValueError(f"Soru en fazla {MAX_LENGTH} karakter olabilir.")
    if _PRIVATE_PATTERN.search(value):
        raise ValueError("Kimlik/telefon/e-posta içeren sorular kaydedilemez.")
    return value


def comparison_key(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.casefold().replace("ı", "i"))
    return "".join(c for c in folded if unicodedata.category(c) != "Mn")


class QuestionLibrary:
    """Bounded atomic JSON store; deliberately independent of SQLite/DB APIs."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def list_questions(self) -> list[str]:
        try:
            if self.path.stat().st_size > MAX_FILE_BYTES:
                return []
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or raw.get("version") != 1:
                return []
            questions = raw.get("questions", [])
            if not isinstance(questions, list):
                return []
            result, seen = [], set()
            for item in questions[:MAX_QUESTIONS]:
                try:
                    q = normalize_question(item)
                except ValueError:
                    continue
                key = comparison_key(q)
                if key not in seen:
                    seen.add(key)
                    result.append(q)
            return result
        except (FileNotFoundError, OSError, ValueError, TypeError, UnicodeError):
            return []

    def _persist(self, items: list[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = json.dumps({"version": 1, "questions": items}, ensure_ascii=False, indent=2)
        fd, tmp = tempfile.mkstemp(prefix=".coach_queries_", suffix=".tmp", dir=self.path.parent)
        try:
            if os.name == "posix":
                os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def add(self, question: str) -> bool:
        q = normalize_question(question)
        items = self.list_questions()
        if any(comparison_key(value) == comparison_key(q) for value in items):
            return False
        if len(items) >= MAX_QUESTIONS:
            raise ValueError(f"En fazla {MAX_QUESTIONS} soru kaydedilebilir. Önce eski bir soruyu silin.")
        self._persist(items + [q])
        return True

    def remove(self, question: str) -> bool:
        q = normalize_question(question)
        items = self.list_questions()
        kept = [item for item in items if comparison_key(item) != comparison_key(q)]
        if len(kept) == len(items):
            return False
        self._persist(kept)
        return True


class RecentQuestions:
    """Session-only history. No student ID and no answers are stored."""

    def __init__(self, limit: int = 8):
        self.limit = limit
        self._items: list[str] = []

    def add(self, question: str) -> None:
        question = " ".join(str(question or "").split())[:600]
        if not question:
            return
        self._items = [q for q in self._items if q.casefold() != question.casefold()]
        self._items.insert(0, question)
        del self._items[self.limit:]

    def list_questions(self) -> list[str]:
        return list(self._items)
