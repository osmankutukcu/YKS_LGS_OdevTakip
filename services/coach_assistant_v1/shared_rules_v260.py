# -*- coding: utf-8 -*-
"""V26.0 shared, read-only coach signal and course-scoping rules.

Do not infer a TYT course from an LGS course or a vague 'Matematik' label.
There are deliberately no DB writes, API calls or student records here.
"""
from __future__ import annotations
import re
import unicodedata

LOW_ACCURACY_THRESHOLD = 55.0
MIN_RELIABLE_ATTEMPTS = 5


def fold(value: str) -> str:
    source = unicodedata.normalize('NFKD', str(value or '').casefold().replace('ı', 'i'))
    source = ''.join(ch for ch in source if unicodedata.category(ch) != 'Mn')
    return ' '.join(re.findall(r'[a-z0-9]+', source))


def lesson_key(value: str) -> str:
    """Exact alias with course-level kept intact. Format-only normalization."""
    return fold(value)


def scoped_topics(topics, lesson: str):
    requested = lesson_key(lesson)
    if not requested:
        return tuple(topics)
    return tuple(t for t in topics if lesson_key(t.lesson) == requested)


def is_low_accuracy(accuracy, *, attempts=None, reliable_only=False) -> bool:
    try:
        if accuracy is None or isinstance(accuracy, bool):
            return False
        score = float(accuracy)
        if not (0.0 <= score <= 100.0):
            return False
        if reliable_only and (attempts is None or int(attempts) < MIN_RELIABLE_ATTEMPTS):
            return False
        return score < LOW_ACCURACY_THRESHOLD
    except (TypeError, ValueError, OverflowError):
        return False


def question_lesson(topics, question: str):
    """Detect a course only if unambiguous; no cross-exam-level guesses.

    Full course labels in the question beat single word references. Generic
    'matematikte' is resolved only if ONE distinct mathematics course exists.
    """
    keys = {lesson_key(t.lesson) for t in topics if lesson_key(t.lesson)}
    q = ' ' + fold(question) + ' '
    explicit = [k for k in keys if re.search(r'\b' + re.escape(k).replace(r'\ ', r'\s+') + r'\b', q)]
    if explicit:
        longest = max(len(k.split()) for k in explicit)
        strongest = sorted(k for k in explicit if len(k.split()) == longest)
        return (strongest[0], False) if len(strongest) == 1 else (None, True)
    # A generic lesson name with a Turkish suffix (matematikte, fizikte, etc.)
    # remains ambiguous if both TYT and AYT variants exist.
    candidates = set()
    for key in keys:
        base = key.split()[-1]
        if re.search(r'\b' + re.escape(base) + r'(?:te|ta|de|da|ten|tan|den|dan|in|nin)?\b', q):
            candidates.add(key)
    if len(candidates) == 1:
        return next(iter(candidates)), False
    return None, len(candidates) > 1
