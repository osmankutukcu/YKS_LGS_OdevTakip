# -*- coding: utf-8 -*-
"""Manual/scheduled deletion of MINIMAL relay records.

Default: delete received replies older than 90 days AND invitations already
submitted/rejected/expired. Uncollected replies older than 90 days WILL be
removed. Configure retention with the education institution and legal counsel.
Backup retention, incident response and access logs must be configured on host.
Usage: python -m tools.feedback_relay_cleanup_v3573 --dry-run
       python -m tools.feedback_relay_cleanup_v3573 --apply
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
import argparse
from services.feedback_relay_v3573 import _conn


def cleanup(retention_days=90, *,apply=False):
    days=int(retention_days)
    if not 7<=days<=365:raise ValueError('Saklama süresi 7–365 gün olmalı.')
    cutoff=(datetime.now(timezone.utc)-timedelta(days=days)).isoformat(timespec='seconds')
    con=_conn()
    try:
        old_replies=con.execute('SELECT COUNT(*) FROM replies WHERE received_at<?',(cutoff,)).fetchone()[0]
        old_invites=con.execute('SELECT COUNT(*) FROM invites WHERE expires_at<? AND state!=\'issued\' AND id NOT IN (SELECT invite_id FROM replies WHERE received_at>=?)', (cutoff,cutoff)).fetchone()[0]
        if apply:
            con.execute('BEGIN IMMEDIATE')
            con.execute('DELETE FROM replies WHERE received_at<?',(cutoff,))
            con.execute("DELETE FROM invites WHERE expires_at<? AND id NOT IN (SELECT invite_id FROM replies)",(cutoff,))
            con.commit()
        return {'apply':apply,'retention_days':days,'expired_replies':old_replies,
                'expired_invites_at_least':old_invites}
    finally:con.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--dry-run',action='store_true')
    group.add_argument('--apply',action='store_true')
    parser.add_argument('--days',type=int,default=90)
    args=parser.parse_args()
    print(cleanup(args.days,apply=args.apply))
