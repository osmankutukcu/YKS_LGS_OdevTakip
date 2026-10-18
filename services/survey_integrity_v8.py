# -*- coding: utf-8 -*-
"""V8: non-diagnostic, immutable survey-answer validation for the existing 9 surveys.

No database writes, no scores or student labels.  Incomplete responses remain
visible as history but are never treated as complete self-reports.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping, Iterable

# General-profile summaries must not include sensitive well-being responses.
GENERAL_CODES = frozenset({
    'vark_learning', 'procrastination', 'study_habits', 'self_efficacy',
    'time_management', 'mindset_resilience', 'digital_distraction',
})
SENSITIVE_CODES = frozenset({'exam_anxiety', 'sleep_energy'})

@dataclass(frozen=True)
class SurveyAudit:
    expected: int
    answered: int
    invalid_keys: tuple[str, ...]
    valid_answers: dict[str, int]
    @property
    def complete(self) -> bool:
        return self.expected > 0 and self.answered == self.expected and not self.invalid_keys
    @property
    def partial(self) -> bool:
        return not self.complete


def _rating(v: Any) -> int | None:
    if type(v) is int and 1 <= v <= 5:
        return v
    # Historical JSON may contain string digits; never silently impute a missing value.
    if type(v) is str and len(v) == 1 and v in '12345':
        return int(v)
    return None


def inspect_answers(questions: Iterable[Any], answers: Any) -> SurveyAudit:
    questions = list(questions)
    keys = [getattr(q, 'key', q) for q in questions]
    if not isinstance(answers, Mapping):
        return SurveyAudit(len(keys), 0, ('__malformed__',), {})
    valid: dict[str, int] = {}
    invalid = []
    for k in keys:
        if k not in answers:
            continue
        value = _rating(answers[k])
        if value is None:
            invalid.append(k)
        else:
            valid[k] = value
    return SurveyAudit(len(keys), len(valid), tuple(invalid), valid)


def complete_self_reports(catalog: Mapping[str, Any], records: Mapping[str, Any]) -> dict[str, dict]:
    """Return only fully answered known codes; never fabricate missing values."""
    output = {}
    for code, payload in (records or {}).items():
        definition = catalog.get(code)
        if definition is None:
            continue
        answers = payload.get('answers', payload) if isinstance(payload, dict) else payload
        audit = inspect_answers(definition.questions, answers)
        if audit.complete:
            output[code] = {'answers': audit.valid_answers,
                            'date': payload.get('date') if isinstance(payload, dict) else None}
    return output


def safe_general_rows(catalog: Mapping[str, Any], complete_records: Mapping[str, Any]) -> list[dict]:
    """Teacher-facing self-report summary; not a validated scale or diagnosis."""
    rows = []
    for code, payload in complete_self_reports(catalog, complete_records).items():
        if code not in GENERAL_CODES:
            continue
        definition = catalog[code]
        answers = payload['answers']
        # Raw response mean: reverse-coded survey statistics would be misleading.
        mean = sum(answers.values()) / len(answers)
        rows.append({'code': code, 'title': definition.title, 'answered': len(answers),
                     'response_mean': round(mean, 2), 'date': payload.get('date')})
    return rows
