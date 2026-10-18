# -*- coding: utf-8 -*-
"""V24.6 kalıcı WhatsApp kuyruğu testleri: gerçek numaralara gönderim yapmaz."""
import ast
from pathlib import Path
import sqlite3
import pytest

from services.whatsapp_queue.queue_v246 import (
    SafeWhatsAppQueue, queue_path_for, normalize_phone, QueueBusyError,
    PENDING, IN_FLIGHT, UI_UNVERIFIED, UNKNOWN, INVALID, FAILED,
)


def queue(tmp_path):
    return SafeWhatsAppQueue(str(tmp_path/'queue.sqlite3'))


def items():
    return [
        {'student_id': 5, 'recipient': '05321234567', 'message': 'Ali icin odev'},
        {'student_id': 6, 'recipient': '05321234568', 'message': 'Beyza icin odev'},
    ]


@pytest.mark.parametrize('raw', ['05321234567', '5321234567', '+905321234567', '00905321234567', '90 532 123 45 67'])
def test_turkish_phone_valid(raw):
    assert normalize_phone(raw) == '905321234567'


@pytest.mark.parametrize('raw', ['0532', '', 'abcd', '05321234567/05321234568', '+995321234567', '02121234567', '1234567890123456789'])
def test_reject_ambiguous_wrong_or_nonmobile(raw):
    assert normalize_phone(raw) is None


def test_distinct_batches_from_distinct_databases(tmp_path):
    folder = str(tmp_path)
    assert queue_path_for(folder+'/a.sqlite3', folder) != queue_path_for(folder+'/b.sqlite3', folder)


def test_atomic_batch_persists_before_attempt(tmp_path):
    q=queue(tmp_path)
    bid=q.create_batch('/tmp/ogrenciler.db', items())
    q2=queue(tmp_path)
    assert q2.counts(bid)=={PENDING:2}
    assert len(q2.rows(bid))==2
    assert q2.rows(bid)[0]['message']=='Ali icin odev'


def test_dedup_same_student_number_message(tmp_path):
    q=queue(tmp_path)
    x=items()[0]
    bid=q.create_batch('/tmp/ogrenciler.db', [x,x,dict(x, recipient='+905321234567')])
    assert len(q.rows(bid))==1


def test_same_phone_two_students_remain_distinct(tmp_path):
    q=queue(tmp_path)
    second=dict(items()[1],recipient='05321234567')
    bid=q.create_batch('/tmp/ogrenciler.db', [items()[0],second])
    assert len(q.rows(bid))==2


def test_invalid_does_not_block_other_jobs(tmp_path):
    q=queue(tmp_path)
    bid=q.create_batch('/tmp/ogrenciler.db', [dict(items()[0],recipient='no phone'),items()[1]])
    assert q.counts(bid)[INVALID]==1
    assert q.claim_next(bid)['recipient']=='905321234568'


def test_inflight_recovered_but_not_resent(tmp_path):
    q=queue(tmp_path)
    bid=q.create_batch('/tmp/ogrenciler.db', items()[:1])
    job=q.claim_next(bid)
    assert q.counts(bid)=={IN_FLIGHT:1}
    assert q.recover_interrupted(bid)==1
    assert q.counts(bid)=={UNKNOWN:1}
    assert q.claim_next(bid) is None


def test_double_claim_rejected(tmp_path):
    q=queue(tmp_path)
    bid=q.create_batch('/tmp/ogrenciler.db', items())
    q.claim_next(bid)
    with pytest.raises(QueueBusyError):
        q.claim_next(bid)


def test_confirmed_completion_only_once(tmp_path):
    q=queue(tmp_path)
    bid=q.create_batch('/tmp/ogrenciler.db', items()[:1])
    job=q.claim_next(bid)
    with pytest.raises(ValueError):
        q.finish(job['id'],job['attempt_token'],'OK')
    q.finish(job['id'],job['attempt_token'], UI_UNVERIFIED)
    with pytest.raises(QueueBusyError):
        q.finish(job['id'],job['attempt_token'], UI_UNVERIFIED)
    assert q.counts(bid)=={UI_UNVERIFIED:1}


def test_no_unverified_auto_retry(tmp_path):
    q=queue(tmp_path)
    bid=q.create_batch('/tmp/ogrenciler.db', items()[:1])
    job=q.claim_next(bid)
    q.finish(job['id'],job['attempt_token'],UNKNOWN,'DOM degisti')
    assert q.claim_next(bid) is None


def test_non_routable_number_stays_in_journal(tmp_path):
    q=queue(tmp_path)
    bid=q.create_batch('/tmp/ogrenciler.db',[{'student_id':7,'recipient':'','message':'Test'}])
    assert q.counts(bid)=={INVALID:1}
    assert len(q.rows(bid))==1


def test_current_batch_scoped_to_source_database(tmp_path):
    q=queue(tmp_path)
    a=str(tmp_path/'a.db')
    b=str(tmp_path/'b.db')
    x=q.create_batch(a,items()[:1])
    q.create_batch(b,items()[:1])
    assert q.current_batch(a)==x


def test_older_pending_not_lost_on_new_batch(tmp_path):
    q=queue(tmp_path)
    x=q.create_batch('/tmp/ogrenciler.db',items())
    y=q.create_batch('/tmp/ogrenciler.db',items()[:1])
    assert len(q.rows(x))==2
    assert len(q.rows(y))==1


def test_lock_rejects_parallel_sender(tmp_path):
    q=queue(tmp_path)
    fd=q.acquire_lock()
    try:
        with pytest.raises(QueueBusyError):
            q.acquire_lock()
    finally:
        q.release_lock(fd)
    fd2=q.acquire_lock(); q.release_lock(fd2)


def test_ui_code_does_not_mark_unknown_as_ok_or_auto_install(tmp_path):
    p=Path(__file__).resolve().parents[1]/'ui'/'mail_send_whatsapp.py'
    source=p.read_text(encoding='utf8')
    ast.parse(source)
    assert 'subprocess.check_call' not in source
    assert 'return "OK"' not in source
    assert 'return "INVALID"' not in source
    assert '"FAIL", result' in source
    assert 'WhatsAppWorker' in source


def test_queue_file_owner_only_posix(tmp_path):
    import os
    q=queue(tmp_path)
    if os.name=='nt': pytest.skip('Unix permissions')
    assert os.stat(q.path).st_mode & 0o077 == 0


def test_latest_batch_visible_when_completed(tmp_path):
    q=queue(tmp_path)
    db=str(tmp_path/'students.db')
    bid=q.create_batch(db,items()[:1])
    job=q.claim_next(bid)
    q.finish(job['id'],job['attempt_token'],UI_UNVERIFIED)
    assert q.current_batch(db) is None
    assert q.latest_batch(db)==bid
