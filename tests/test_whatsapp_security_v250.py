"""Synthetic data only; never connects to WhatsApp or reads student DBs."""
import hashlib
import hmac
import os
from pathlib import Path
import sqlite3
import pytest
from services.whatsapp_queue.queue_v246 import SafeWhatsAppQueue, PENDING, UNKNOWN, UI_UNVERIFIED
from services.whatsapp_queue.dpapi_v250 import WindowsDPAPI, PlatformProtectionUnavailable, ProtectionError
from services.whatsapp_queue.secure_queue_v250 import ProtectedWhatsAppQueue, LegacyQueueNeedsReview
from services.whatsapp_queue.secure_vault_v250 import SecureLocalVault

class FakeProtector:
    """TEST-ONLY authenticator; NOT cryptographic encryption/production DPAPI."""
    def __init__(self,key=b'fake_test_only_key'): self.key=key
    def seal(self, data):
        # HMAC authenticates payload but intentionally does not encrypt.
        return hmac.digest(self.key,data,'sha256') + data[::-1]
    def open(self,blob):
        val=blob[32:][::-1]
        if not hmac.compare_digest(blob[:32],hmac.digest(self.key,val,'sha256')):
            raise ProtectionError('test integrity error')
        return val

@pytest.fixture
def path(tmp_path): return str(tmp_path/'queue.sqlite3')

def item(student=1,phone='05321234567',message='Private Grade 71'):
    return {'student_id':student,'recipient':phone,'message':message}

def test_unsupported_windows_encryption_refuses_linux():
    if os.name != 'nt':
        with pytest.raises(PlatformProtectionUnavailable): WindowsDPAPI()

def test_windows_real_dpapi_roundtrip():
    if os.name != 'nt': pytest.skip('Real DPAPI requires Windows test machine')
    p=WindowsDPAPI('real-unit-test-v250'); val=b'hello-secret'
    assert p.open(p.seal(val))==val
    with pytest.raises(ProtectionError): WindowsDPAPI('wrong-purpose').open(p.seal(val))

def test_secure_new_batch_roundtrip_and_state(path):
    p=ProtectedWhatsAppQueue(path,FakeProtector())
    b=p.create_batch('/tmp/student.db',[item()])
    assert p.counts(b)=={PENDING:1}
    assert p.rows(b)[0]['message']=='Private Grade 71'
    j=p.claim_next(b)
    assert j['recipient']=='905321234567'
    p.finish(j['id'],j['attempt_token'],UI_UNVERIFIED,'no delivery receipt')
    assert p.counts(b)=={UI_UNVERIFIED:1}
    assert p.rows(b)[0]['detail']=='no delivery receipt'

def test_sqlite_does_not_store_plaintext_recipient_message_details(path):
    p=ProtectedWhatsAppQueue(path,FakeProtector())
    b=p.create_batch('/tmp/student.db',[item(message='PRIVATE_SENTINEL_NOT_IN_SQLITE')])
    job=p.claim_next(b); p.finish(job['id'],job['attempt_token'],UNKNOWN,'PRIVATE_DETAIL_SENTINEL')
    with sqlite3.connect(path) as c:
        row=c.execute('SELECT recipient,message,detail FROM jobs').fetchone()
    assert all(str(x).startswith('dpapi:v250:') for x in row)
    raw=Path(path).read_bytes()
    for raw_piece in (b'905321234567',b'PRIVATE_SENTINEL_NOT_IN_SQLITE',b'PRIVATE_DETAIL_SENTINEL'):
        assert raw_piece not in raw

def test_wrong_account_purpose_refuses_decryption_without_claiming(path):
    first=ProtectedWhatsAppQueue(path,FakeProtector(b'correct'))
    batch=first.create_batch('/tmp/student.db',[item()])
    second=ProtectedWhatsAppQueue(path,FakeProtector(b'wrong'))
    with pytest.raises(ProtectionError): second.claim_next(batch)
    assert first.counts(batch)=={PENDING:1}

def test_tampering_refuses_and_keeps_pending(path):
    p=ProtectedWhatsAppQueue(path,FakeProtector()); batch=p.create_batch('/tmp/student.db',[item()])
    with sqlite3.connect(path) as c:
        c.execute("UPDATE jobs SET message=?", ('dpapi:v250:QUJDRA==',))
    with pytest.raises(ProtectionError): p.claim_next(batch)
    assert p.counts(batch)=={PENDING:1}

def test_no_plaintext_auto_migration(path):
    legacy=SafeWhatsAppQueue(path); b=legacy.create_batch('/tmp/student.db',[item()])
    with pytest.raises(LegacyQueueNeedsReview): ProtectedWhatsAppQueue(path,FakeProtector())
    assert legacy.counts(b)=={PENDING:1}
    assert legacy.rows(b)[0]['message']=='Private Grade 71'

def test_migration_requires_consent(path):
    legacy=SafeWhatsAppQueue(path); legacy.create_batch('/tmp/student.db',[item()])
    p=ProtectedWhatsAppQueue(path,FakeProtector(),allow_legacy_review=True)
    with pytest.raises(PermissionError): p.migrate_legacy_to_encrypted()
    with sqlite3.connect(path) as c:
        assert not c.execute("SELECT message FROM jobs").fetchone()[0].startswith('dpapi:')
    assert p.migrate_legacy_to_encrypted(explicit_consent=True)==1
    p2=ProtectedWhatsAppQueue(path,FakeProtector())
    assert p2.rows(p2.latest_batch('/tmp/student.db'))[0]['message']=='Private Grade 71'

def test_inflight_cannot_migrate(path):
    old=SafeWhatsAppQueue(path); b=old.create_batch('/tmp/student.db',[item()]); old.claim_next(b)
    p=ProtectedWhatsAppQueue(path,FakeProtector(),allow_legacy_review=True)
    with pytest.raises(Exception,match='Gönderim sürerken'): p.migrate_legacy_to_encrypted(explicit_consent=True)
    assert old.counts(b)

def test_mixed_encrypted_and_legacy_queues_fail_closed(path):
    old=SafeWhatsAppQueue(path); old.create_batch('/tmp/student.db',[item()])
    p=ProtectedWhatsAppQueue(path,FakeProtector(),allow_legacy_review=True)
    with pytest.raises(LegacyQueueNeedsReview): p.create_batch('/tmp/student.db',[item(student=2)])

def test_recover_interrupted_and_does_not_retry(path):
    p=ProtectedWhatsAppQueue(path,FakeProtector()); b=p.create_batch('/tmp/student.db',[item()])
    p.claim_next(b)
    assert p.recover_interrupted(b)==1
    assert p.claim_next(b) is None
    assert p.rows(b)[0]['state']==UNKNOWN
    assert p.rows(b)[0]['detail']

def test_invalid_phone_does_not_block_valid(path):
    p=ProtectedWhatsAppQueue(path,FakeProtector())
    b=p.create_batch('/tmp/student.db',[item(phone='wrong'),item(student=2)])
    assert p.claim_next(b)['student_id']==2

def test_duplicate_dedup_before_encryption(path):
    p=ProtectedWhatsAppQueue(path,FakeProtector()); b=p.create_batch('/tmp/student.db',[item(),item()])
    assert len(p.rows(b))==1

def test_vault_atomic_roundtrip(tmp_path):
    v=SecureLocalVault(str(tmp_path/'secret_dir'),protector=FakeProtector())
    v.put('device_auth',b'DEVICE_TEST_SECRET')
    assert v.get('device_auth')==b'DEVICE_TEST_SECRET'
    assert b'DEVICE_TEST_SECRET' not in (tmp_path/'secret_dir'/'device_auth.dpapi').read_bytes()
    assert v.delete('device_auth')
    assert not v.delete('device_auth')

def test_vault_rejects_path_traversal(tmp_path):
    v=SecureLocalVault(str(tmp_path/'vault'),protector=FakeProtector())
    for name in ('../../temp','../other','name.with.dot',''):
        with pytest.raises(ValueError): v.put(name,b'xx')

def test_vault_corruption_or_wrong_key_denied(tmp_path):
    folder=tmp_path/'vault'; v=SecureLocalVault(str(folder),protector=FakeProtector(b'k1'))
    v.put('auth',b'secret')
    with pytest.raises(ProtectionError): SecureLocalVault(str(folder),protector=FakeProtector(b'k2')).get('auth')
    (folder/'auth.dpapi').write_bytes(b'bad')
    with pytest.raises(ProtectionError): v.get('auth')

def test_no_automatic_headless_whatsapp_unlock(tmp_path):
    # These are additions only. Existing V24.9 transport deliberately remains locked.
    from services.whatsapp_queue.transport_v249 import HEADLESS_DISABLED,validate_choice
    with pytest.raises(Exception): validate_choice(HEADLESS_DISABLED)
