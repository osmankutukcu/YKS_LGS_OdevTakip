"""Offline synthetic-data-only regression suite: cannot transmit WhatsApp."""
import ast
import hashlib
import hmac
import json
from pathlib import Path

import pytest

from services.whatsapp_queue.baileys_bulk_v258 import (
    prepare_recipients, SuppressionRegistry, BatchValidationError,
    MAX_RECIPIENTS, mark_batch, batch_transport, TRANSPORT_MARKER,
    baileys_queue_path_for,
)
from services.whatsapp_queue.secure_queue_v250 import ProtectedWhatsAppQueue
from services.whatsapp_queue.queue_v246 import SafeWhatsAppQueue, queue_path_for, PENDING, UNKNOWN
from services.whatsapp_queue.transport_v249 import BAILEYS_BULK, HEADLESS_DISABLED, validate_choice


class SyntheticProtector:
    """Test double; not actual encryption."""
    def seal(self, value: bytes) -> bytes:
        return hmac.digest(b'test', value, 'sha256') + value[::-1]
    def open(self, value: bytes) -> bytes:
        data = value[32:][::-1]
        assert hmac.compare_digest(value[:32],hmac.digest(b'test',data,'sha256'))
        return data


def item(index, phone=None, text=None):
    return {'student_id':index+1, 'recipient':phone or f'905{index:09d}',
            'message':text or f'Öğrenci {index} ödev bildirimi', 'country_code':'90'}


def test_recipients_150_maximum(tmp_path):
    reg=SuppressionRegistry(tmp_path/'ret.json')
    valid=[item(i) for i in range(150)]
    jobs,notes=prepare_recipients(valid,'90',reg)
    assert len(jobs)==150 and notes['invalid']==0
    with pytest.raises(BatchValidationError):prepare_recipients(valid+[item(150)],'90',reg)


def test_same_phone_other_student_skipped_entirely(tmp_path):
    reg=SuppressionRegistry(tmp_path/'ret.json')
    jobs,notes=prepare_recipients([item(0),item(1,phone=item(0)['recipient']),item(2)],'90',reg)
    assert len(jobs)==1 and notes['shared_phone']==1
    assert jobs[0]['student_id']==3


def test_dedup_and_invalid_numbers_fail_closed(tmp_path):
    reg=SuppressionRegistry(tmp_path/'ret.json')
    first=item(0)
    jobs,notes=prepare_recipients([first,dict(first),item(1,phone='bad'),item(2,text='x'*3001)],'90',reg)
    assert len(jobs)==1 and notes=={
        'invalid':1,'oversize_or_empty':1,'excluded':0,'duplicate':1,'shared_phone':0}


def test_optout_is_stored_without_number_and_persists(tmp_path):
    f=tmp_path/'ret.json'
    reg=SuppressionRegistry(f)
    number='905321234567'
    reg.add(number)
    assert number not in f.read_text()
    assert SuppressionRegistry(f).contains(number)
    jobs, notes=prepare_recipients([item(1,phone=number),item(0)],'90',SuppressionRegistry(f))
    assert len(jobs)==1 and notes['excluded']==1


def test_corrupt_optout_aborts(tmp_path):
    f=tmp_path/'ret.json';f.write_text('{"salt":"wrong","digests":[]}',encoding='utf8')
    with pytest.raises((BatchValidationError, ValueError)):
        SuppressionRegistry(f)


def test_baileys_queue_is_separate_and_protected(tmp_path):
    db=str(tmp_path/'fake.db'); app=str(tmp_path)
    legacy=queue_path_for(db,app)
    protected=baileys_queue_path_for(db,app)
    assert legacy!=protected and 'baileys_v258' in protected
    q=ProtectedWhatsAppQueue(protected,protector=SyntheticProtector())
    batch=q.create_batch(db,[item(0)])
    mark_batch(q,batch)
    assert batch_transport(q,batch)==TRANSPORT_MARKER
    job=q.claim_next(batch)
    assert q.counts(batch)=={'DENENIYOR':1}
    assert q.recover_interrupted(batch)==1
    assert q.counts(batch)=={UNKNOWN:1}
    assert q.claim_next(batch) is None
    data=Path(protected).read_bytes()
    assert item(0)['message'].encode() not in data
    assert item(0)['recipient'].encode() not in data
    assert SafeWhatsAppQueue(legacy).latest_batch(db) is None


def test_no_silent_fallback_and_prior_methods_unchanged():
    assert validate_choice(BAILEYS_BULK).automated
    with pytest.raises(Exception):validate_choice(HEADLESS_DISABLED)
    from services.whatsapp_queue.transport_v249 import SELENIUM, DESKTOP_LINK, WEB_LINK
    for mode in [SELENIUM,DESKTOP_LINK,WEB_LINK]:
        assert validate_choice(mode).enabled


def test_gui_routes_to_modal_without_touching_core():
    root=Path(__file__).resolve().parents[1]
    a=(root/'ui/mail_send_whatsapp.py').read_text('utf8')
    b=(root/'ui/baileys_bulk_v258.py').read_text('utf8')
    ast.parse(a);ast.parse(b)
    assert 'self._open_baileys_bulk_v258(raw_jobs=jobs)' in a
    assert 'self._open_baileys_bulk_v258(resume_batch=batch)' in a
    assert 'transport_key=self._selected_transport()' in a
    assert 'open_baileys_queue(db_path, appdata_dir)' in b
    assert 'self.q.claim_next(self._batch)' in b
    assert 'self.q.finish(' in b
    assert 'BAILEYS_BULK' in a


def test_old_single_test_unmodified():
    root=Path(__file__).resolve().parents[1]
    assert 'claimed=true' in (root/'services/whatsapp_queue/baileys_node_v257/bridge.mjs').read_text()
    assert 'send-test' in (root/'services/whatsapp_queue/baileys_node_v257/rules.mjs').read_text()
