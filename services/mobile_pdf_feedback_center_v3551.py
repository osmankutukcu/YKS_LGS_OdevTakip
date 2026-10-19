# -*- coding: utf-8 -*-
"""V3.5.51 — Teacher review presenter for the isolated PDF feedback inbox.

Read-only by default. The ONLY mutation is reviewing a feedback-submission row.
No homework, student or teacher tables are ever written by this module.

SECURITY: The principal must come from a VERIFIED external teacher session.
A TeacherPrincipal object is a data carrier, NOT proof of authentication.
Caller must revalidate teacher membership and student access on each request.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone

from services.mobile_pdf_feedback_v3550 import FeedbackInbox, STATUS, REASONS, ROLES
from services.mobile_pdf_secure_portal_v3548 import TeacherPrincipal

PRIORITY = {'need_help': 0, 'meeting_request': 1, 'completed_claim': 2, 'started': 3}


@dataclass(frozen=True)
class TeacherInboxSnapshot:
    groups: tuple
    visible_count: int
    pending_count: int
    reviewed_count: int
    is_partial: bool
    generated_at: float


class FeedbackCenter:
    """Small presentation boundary; no implicit user identity or global DB access."""

    def __init__(self, inbox: FeedbackInbox, *, principal_provider,
                 authorize_student, student_label=None, clock=None):
        if not isinstance(inbox, FeedbackInbox):
            raise TypeError('Yalnızca ayrı geri bildirim deposu desteklenir.')
        if not callable(principal_provider) or not callable(authorize_student):
            raise ValueError('Doğrulanmış oturum ve öğrenci yetkilendirmesi gerekir.')
        if student_label is not None and not callable(student_label):
            raise TypeError('Öğrenci etiketi sağlayıcısı geçersiz.')
        self.inbox = inbox
        self.principal_provider = principal_provider
        self.authorize_student = authorize_student
        self.student_label = student_label
        self.clock = clock or inbox.clock

    def _principal(self):
        principal = self.principal_provider()
        if (not isinstance(principal, TeacherPrincipal)
                or principal.expires_at <= float(self.clock())):
            raise PermissionError('Öğretmen oturumu doğrulanamadı veya süresi doldu.')
        return principal

    def _allowed(self, principal, sid):
        try:
            return self.authorize_student(principal, sid) is True
        except Exception:
            return False

    def snapshot(self, *, include_reviewed=True, limit=200):
        principal = self._principal()
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError('Geçersiz kayıt sınırı.')
        # Request a complete bounded page, then group locally.
        rows = self.inbox.teacher_inbox(principal=principal, limit=limit)
        grouped = OrderedDict()
        allowed_rows = []
        for row in rows:
            sid = row['student_id']
            if type(sid) is not int or sid <= 0 or not self._allowed(principal, sid):
                continue
            allowed_rows.append(row)
            if row['reviewed_at'] is not None and not include_reviewed:
                continue
            clean = {
                'id': row['id'], 'student_id': sid,
                'recipient': 'Öğrenci' if row['recipient_role'] == 'student' else 'Veli',
                'status': STATUS.get(row['status'], 'Bilinmeyen bildirim'),
                'reason': REASONS.get(row['reason'], 'Belirtilmemiş'),
                'status_code': row['status'], 'received_at': float(row['received_at']),
                'reviewed': row['reviewed_at'] is not None,
                'priority': PRIORITY.get(row['status'], 9),
            }
            grouped.setdefault(sid, []).append(clean)
        pending = sum(r['reviewed_at'] is None for r in allowed_rows)
        reviewed = len(allowed_rows) - pending
        groups = []
        for sid, records in grouped.items():
            label = f'Öğrenci kaydı #{sid}'
            if self.student_label is not None:
                try:
                    resolved = self.student_label(principal, sid)
                    if isinstance(resolved, str) and 0 < len(resolved.strip()) <= 120:
                        label = resolved.strip()
                except Exception:
                    pass
            records.sort(key=lambda r: (r['reviewed'], r['priority'], -r['received_at'], -r['id']))
            groups.append({'student_id': sid, 'label': label,
                           'pending': sum(not x['reviewed'] for x in records),
                           'items': tuple(records)})
        groups.sort(key=lambda g: (g['pending'] == 0,
                                   min((r['priority'] for r in g['items'] if not r['reviewed']), default=9),
                                   g['label'].casefold(), g['student_id']))
        return TeacherInboxSnapshot(groups=tuple(groups), visible_count=sum(len(g['items']) for g in groups),
            pending_count=pending, reviewed_count=reviewed,
            is_partial=len(rows) >= limit, generated_at=float(self.clock()))

    def review(self, response_id):
        principal = self._principal()
        if type(response_id) is not int or response_id < 1:
            raise ValueError('Geçersiz bildirim numarası.')
        # Check current student access rather than trusting an old GUI selection.
        rows = self.inbox.teacher_inbox(principal=principal, limit=200)
        selected = next((r for r in rows if r['id'] == response_id), None)
        if selected is None or not self._allowed(principal, selected['student_id']):
            raise PermissionError('Bildirim için güncel öğrenci erişim izni yok.')
        if selected['reviewed_at'] is not None:
            return False
        return self.inbox.mark_reviewed(response_id, principal=principal)


def readable_time(timestamp):
    """Stable UTC display; caller may localize separately, never guesses TZ."""
    return datetime.fromtimestamp(float(timestamp), tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
