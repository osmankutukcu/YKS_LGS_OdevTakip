"""No real WhatsApp and no real student data. Test cipher is NOT encryption."""
from pathlib import Path
import hashlib
import hmac
import json
import pytest
from services.whatsapp_queue.readiness_v252 import (
    windows_offline_readiness, inspect_legacy_counts,
)
from services.whatsapp_queue.queue_v246 import SafeWhatsAppQueue

class FakeProtector:
    def __init__(self, purpose): self.key=purpose.encode('utf-8')
    def seal(self, data):
        return hmac.digest(self.key, data, 'sha256') + data[::-1]
    def open(self, payload):
        original=payload[32:][::-1]
        if not hmac.compare_digest(hmac.digest(self.key,original,'sha256'),payload[:32]):
            raise ValueError('test rejected')
        return original

class BrokenProtector(FakeProtector):
    def seal(self, payload):raise ValueError('synthetic secret must not leak')

def test_non_windows_refuses_actual_test():
    r=windows_offline_readiness(platform_name='posix')
    assert r['result']=='NOT_RUN_WINDOWS_REQUIRED'
    assert r['passed_checks']==[]

def test_synthetic_comprehensive_checks():
    r=windows_offline_readiness(protector_factory=FakeProtector, platform_name='posix')
    assert r['result']=='PASS_TEST_DOUBLE_ONLY'
    assert len(r['passed_checks']) == 6
    assert '905321234567' not in str(r)
    assert 'V252_TEST_MESSAGE' not in str(r)
    assert r['headless_baileys']=='DISABLED'

def test_broken_protector_fails_closed_with_no_exception_detail():
    r=windows_offline_readiness(protector_factory=BrokenProtector, platform_name='nt')
    assert r['result']=='FAIL_CLOSED' and r['passed_checks']==[]
    assert 'synthetic secret' not in str(r)

def test_result_does_not_mislabel_fake_provider_as_real_windows():
    # Simulation is only allowed for unit test. Readiness output distinguishes
    # fake provider when simulation uses a non-Windows platform.
    r=windows_offline_readiness(protector_factory=FakeProtector, platform_name='posix')
    assert r['requires_real_windows'] and r['result']!='PASS_WINDOWS_SYNTHETIC_TEST'

def test_legacy_report_contains_only_counts(tmp_path):
    p=tmp_path/'legacy.sqlite3'
    q=SafeWhatsAppQueue(str(p))
    q.create_batch('/fictitious/student.db',[{'student_id':123,
        'recipient':'05321234567','message':'PRIVATE_SENTINEL'}])
    report=inspect_legacy_counts(str(p))
    assert report['jobs']==1
    assert 'PRIVATE' not in str(report) and '0532' not in str(report)
    assert '/fictitious' not in str(report)
    assert report['will_send'] is False and report['will_migrate'] is False

def test_corrupt_legacy_fails_closed(tmp_path):
    p=tmp_path/'broken.sqlite3';p.write_bytes(b'not sqlite')
    r=inspect_legacy_counts(str(p))
    assert r['result']=='REQUIRES_MANUAL_REVIEW'

def test_missing_legacy_fails_closed(tmp_path):
    assert inspect_legacy_counts(str(tmp_path/'missing.db'))['result']=='REQUIRES_MANUAL_REVIEW'

def test_no_legacy_auto_scanning(tmp_path):
    p=tmp_path/'secret_queue.sqlite3';p.write_bytes(b'wrong')
    r=windows_offline_readiness(protector_factory=FakeProtector,platform_name='posix')
    assert 'legacy_queue' not in r

def test_no_server_or_whatsapp_actions():
    r=windows_offline_readiness(protector_factory=FakeProtector,platform_name='posix')
    assert r['whatsapp_connection']=='NOT_ATTEMPTED'
    assert r['message_delivery']=='NOT_ATTEMPTED'
    assert r['personal_data_access']=='NONE'
