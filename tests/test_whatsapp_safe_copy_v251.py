"""All tests use fake synthetic contacts; FakeProtector is NOT encryption."""
import hashlib
import hmac
from pathlib import Path
import sqlite3
import pytest

from services.whatsapp_queue.queue_v246 import SafeWhatsAppQueue, PENDING, IN_FLIGHT, UNKNOWN, UI_UNVERIFIED
from services.whatsapp_queue.secure_queue_v250 import ProtectedWhatsAppQueue
from services.whatsapp_queue.dpapi_v250 import ProtectionError
from services.whatsapp_queue.safe_copy_v251 import assess_legacy, create_encrypted_copy, MigrationBlocked

class FakeProtector:
    def seal(self, payload):
        return hmac.digest(b'test-only',payload,'sha256') + payload[::-1]
    def open(self, blob):
        value = blob[32:][::-1]
        if not hmac.compare_digest(hmac.digest(b'test-only',value,'sha256'),blob[:32]):
            raise ProtectionError('Invalid test content')
        return value

@pytest.fixture
def queues(tmp_path):
    return tmp_path/'old.sqlite3', tmp_path/'new.sqlite3'

def make_old(path, count=3):
    old=SafeWhatsAppQueue(str(path))
    jobs=[{'student_id':i,'recipient':('invalid' if i==0 else '05321234567'),
           'message':f'SYNTHETIC-SENSITIVE-MESSAGE-{i}'} for i in range(count)]
    batch=old.create_batch('/fake/student.db',jobs)
    return old,batch

def test_preflight_exposes_only_counts(queues):
    src,_=queues;make_old(src)
    st=assess_legacy(src)
    assert st['jobs']==3 and st['safe_to_copy']
    assert 'message' not in str(st) and '0532' not in str(st)

def test_copy_keeps_origin_bytes_and_job_status(queues):
    src,dst=queues
    old,b=make_old(src)
    claimed=old.claim_next(b)
    old.finish(claimed['id'],claimed['attempt_token'],UI_UNVERIFIED,'SYNTHETIC-DETAIL')
    before=hashlib.sha256(src.read_bytes()).hexdigest()
    r=create_encrypted_copy(src,dst,explicit_consent=True,protector=FakeProtector())
    assert r['jobs']==3 and not r['sending_enabled']
    assert hashlib.sha256(src.read_bytes()).hexdigest()==before
    sec=ProtectedWhatsAppQueue(str(dst),protector=FakeProtector())
    assert sec.rows(b)==old.rows(b)  # exact status and content
    for data in [dst.read_bytes()]:
        assert b'SYNTHETIC-SENSITIVE-MESSAGE-' not in data
        assert b'SYNTHETIC-DETAIL' not in data
    assert not list(dst.parent.glob('*.pending-*.sqlite3'))

def test_explicit_consent_required(queues):
    src,dst=queues;make_old(src)
    with pytest.raises(PermissionError):create_encrypted_copy(src,dst,protector=FakeProtector())
    assert not dst.exists()

def test_inflight_blocks_copy_without_side_effect(queues):
    src,dst=queues;old,b=make_old(src);old.claim_next(b)
    with pytest.raises(MigrationBlocked,match='Gönderim'):
        create_encrypted_copy(src,dst,explicit_consent=True,protector=FakeProtector())
    assert not dst.exists()
    assert old.counts(b).get(IN_FLIGHT)==1

def test_existing_destination_is_never_overwritten(queues):
    src,dst=queues;make_old(src);dst.write_bytes(b'KEEP_TARGET_BYTES')
    with pytest.raises(MigrationBlocked):create_encrypted_copy(src,dst,explicit_consent=True,protector=FakeProtector())
    assert dst.read_bytes()==b'KEEP_TARGET_BYTES'

def test_broken_protector_leaves_no_published_file(queues):
    src,dst=queues;make_old(src)
    class Broken(FakeProtector):
        def seal(self,payload):raise ProtectionError('refuse')
    with pytest.raises(ProtectionError):create_encrypted_copy(src,dst,explicit_consent=True,protector=Broken())
    assert not dst.exists()

def test_bad_schema_fails_closed(queues):
    src,dst=queues
    with sqlite3.connect(src) as c:c.execute('CREATE TABLE strange(x)')
    with pytest.raises(MigrationBlocked):create_encrypted_copy(src,dst,explicit_consent=True,protector=FakeProtector())
    assert not dst.exists()

def test_partial_encrypted_old_file_rejected(queues):
    src,dst=queues;make_old(src)
    with sqlite3.connect(src) as con:con.execute("UPDATE jobs SET message='dpapi:v250:fake' LIMIT 1")
    with pytest.raises(MigrationBlocked):create_encrypted_copy(src,dst,explicit_consent=True,protector=FakeProtector())
    assert not dst.exists()

def test_second_copy_not_allowed(queues):
    src,dst=queues;make_old(src)
    create_encrypted_copy(src,dst,explicit_consent=True,protector=FakeProtector())
    with pytest.raises(MigrationBlocked):create_encrypted_copy(src,dst,explicit_consent=True,protector=FakeProtector())

def test_symlink_destination_denied(queues):
    src,dst=queues;make_old(src)
    real=dst.parent/'real';real.write_text('safe')
    dst.symlink_to(real)
    with pytest.raises(MigrationBlocked):create_encrypted_copy(src,dst,explicit_consent=True,protector=FakeProtector())
    assert real.read_text()=='safe'

def test_foreign_key_mismatch_rejected(queues):
    src,dst=queues;old,b=make_old(src)
    with sqlite3.connect(src) as c:c.execute("UPDATE jobs SET batch_id='nonexistent' LIMIT 1")
    with pytest.raises(MigrationBlocked):create_encrypted_copy(src,dst,explicit_consent=True,protector=FakeProtector())

def test_absent_source_fails_closed(queues):
    src,dst=queues
    with pytest.raises(MigrationBlocked):assess_legacy(src)
