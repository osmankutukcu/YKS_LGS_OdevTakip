"""V25.3 simulated 2-account test. NOT a live Windows security attestation."""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
from pathlib import Path
import pytest

from services.whatsapp_queue.isolation_v253 import (
    CHALLENGE, FINAL, WITNESS, IsolationTestError, prepare, verify_other,
    finalize, cleanup, TTL_SECONDS,
)
from services.whatsapp_queue.dpapi_v250 import ProtectionError

NOW = 1781620000

class FakeUserProtector:
    """NOT cryptography. Mimics access control to exercise application logic."""
    def __init__(self, sid): self.sid = sid
    def seal(self, data):
        raw = bytes(data)
        return hmac.digest(self.sid.encode('utf8'), raw, 'sha256') + raw[::-1]
    def open(self, blob):
        result=blob[32:][::-1]
        if not hmac.compare_digest(blob[:32],hmac.digest(self.sid.encode('utf8'),result,'sha256')):
            raise ProtectionError('synthetic access denied')
        return result


def test_complete_three_step_cross_user(tmp_path):
    first = prepare(tmp_path, 'sid-A', FakeUserProtector('A'), NOW)
    assert first['phase']=='PREPARED_BY_USER_A'
    second=verify_other(tmp_path,'sid-B',FakeUserProtector('B'),NOW+1)
    assert second['phase']=='SECOND_USER_REJECTED'
    report=finalize(tmp_path,'sid-A',FakeUserProtector('A'),NOW+2)
    assert report['result']=='PASS_TWO_USERS_SYNTHETIC_DPAPI'
    assert not report['sending_enabled'] and report['baileys_status']=='DISABLED'
    text=''.join(p.read_text() for p in tmp_path.iterdir())
    assert 'sid-A' not in text and 'sid-B' not in text
    assert 'message_delivery' in report and report['message_delivery']=='NOT_ATTEMPTED'
    assert cleanup(tmp_path)['phase']=='SYNTHETIC_FILES_REMOVED'
    assert not list(tmp_path.iterdir())


def test_creator_cannot_masquerade_as_second_user(tmp_path):
    prepare(tmp_path,'sid-A',FakeUserProtector('A'),NOW)
    with pytest.raises(IsolationTestError,match='aynı Windows'):
        verify_other(tmp_path,'sid-A',FakeUserProtector('A'),NOW+1)
    assert not (tmp_path/WITNESS).exists()


def test_second_user_can_decrypt_never_passes(tmp_path):
    prepare(tmp_path,'sid-A',FakeUserProtector('A'),NOW)
    with pytest.raises(IsolationTestError,match='GÜVENLİK BAŞARISIZ'):
        verify_other(tmp_path,'sid-B',FakeUserProtector('A'),NOW+1)
    assert not (tmp_path/WITNESS).exists()


def test_wrong_creator_for_finalize(tmp_path):
    prepare(tmp_path,'sid-A',FakeUserProtector('A'),NOW)
    verify_other(tmp_path,'sid-B',FakeUserProtector('B'),NOW+1)
    with pytest.raises(IsolationTestError,match='ilk Windows'):
        finalize(tmp_path,'sid-B',FakeUserProtector('B'),NOW+2)


def test_no_witness_no_success(tmp_path):
    prepare(tmp_path,'sid-A',FakeUserProtector('A'),NOW)
    with pytest.raises(IsolationTestError):finalize(tmp_path,'sid-A',FakeUserProtector('A'),NOW+1)


def test_tampered_cipher_failed(tmp_path):
    prepare(tmp_path,'sid-A',FakeUserProtector('A'),NOW)
    p=tmp_path/CHALLENGE
    data=json.loads(p.read_text());data['cipher_b64']=base64.b64encode(b'tampered').decode()
    p.write_text(json.dumps(data))
    with pytest.raises(IsolationTestError,match='değiştirilmiş'):
        verify_other(tmp_path,'sid-B',FakeUserProtector('B'),NOW+1)


def test_creator_original_decrypt_fails_in_last_step(tmp_path):
    prepare(tmp_path,'sid-A',FakeUserProtector('A'),NOW)
    verify_other(tmp_path,'sid-B',FakeUserProtector('B'),NOW+1)
    with pytest.raises(IsolationTestError,match='açamadı'):
        finalize(tmp_path,'sid-A',FakeUserProtector('C'),NOW+2)


def test_expired_challenge_denied(tmp_path):
    prepare(tmp_path,'sid-A',FakeUserProtector('A'),NOW)
    with pytest.raises(IsolationTestError,match='süresi'):
        verify_other(tmp_path,'sid-B',FakeUserProtector('B'),NOW+TTL_SECONDS+2)


def test_duplicate_creation_rejected(tmp_path):
    prepare(tmp_path,'sid-A',FakeUserProtector('A'),NOW)
    with pytest.raises(IsolationTestError):prepare(tmp_path,'sid-A',FakeUserProtector('A'),NOW+1)


def test_duplicate_second_user_rejected(tmp_path):
    prepare(tmp_path,'sid-A',FakeUserProtector('A'),NOW)
    verify_other(tmp_path,'sid-B',FakeUserProtector('B'),NOW+1)
    with pytest.raises(IsolationTestError):verify_other(tmp_path,'sid-C',FakeUserProtector('C'),NOW+2)


def test_invalid_test_folder(tmp_path):
    with pytest.raises(IsolationTestError):prepare(tmp_path/'not_there','sid-A',FakeUserProtector('A'),NOW)


def test_report_no_real_identity_or_secret(tmp_path):
    prepare(tmp_path,'Windows-sensitive-name',FakeUserProtector('A'),NOW)
    verify_other(tmp_path,'other-account-name',FakeUserProtector('B'),NOW+1)
    final=finalize(tmp_path,'Windows-sensitive-name',FakeUserProtector('A'),NOW+2)
    blob=json.dumps(final)
    assert 'Windows-sensitive-name' not in blob and 'other-account-name' not in blob
    assert 'phone' not in blob and 'test_message' not in blob


def test_changed_witness_denied(tmp_path):
    prepare(tmp_path,'sid-A',FakeUserProtector('A'),NOW)
    verify_other(tmp_path,'sid-B',FakeUserProtector('B'),NOW+1)
    p=tmp_path/WITNESS
    obj=json.loads(p.read_text());obj['challenge_sha256']='0'*64;p.write_text(json.dumps(obj))
    with pytest.raises(IsolationTestError,match='uyuşmuyor'):
        finalize(tmp_path,'sid-A',FakeUserProtector('A'),NOW+2)


def test_cleanup_refuses_other_version(tmp_path):
    p=tmp_path/CHALLENGE;p.write_text(json.dumps({'version':'OTHER'}))
    with pytest.raises(IsolationTestError):cleanup(tmp_path)
    assert p.exists()


def test_symlink_folder_rejected(tmp_path):
    real=tmp_path/'real';real.mkdir()
    linked=tmp_path/'link'
    try: linked.symlink_to(real,target_is_directory=True)
    except OSError:pytest.skip('No symlink support')
    with pytest.raises(IsolationTestError):prepare(linked,'sid-A',FakeUserProtector('A'),NOW)


def test_cleanup_never_touches_unrelated_files(tmp_path):
    (tmp_path/'student_data.txt').write_text('KEEP')
    prepare(tmp_path,'sid-A',FakeUserProtector('A'),NOW)
    verify_other(tmp_path,'sid-B',FakeUserProtector('B'),NOW+1)
    finalize(tmp_path,'sid-A',FakeUserProtector('A'),NOW+2)
    cleanup(tmp_path)
    assert (tmp_path/'student_data.txt').read_text()=='KEEP'
