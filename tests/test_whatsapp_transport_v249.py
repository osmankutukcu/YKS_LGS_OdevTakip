# -*- coding: utf-8 -*-
"""V24.9 alternatif WhatsApp aktarımı; gerçek ağa veya WhatsApp'a bağlanmaz."""
import ast
from pathlib import Path
import urllib.parse
import pytest

from services.whatsapp_queue.transport_v249 import (
    CHOICES, SELENIUM, DESKTOP_LINK, WEB_LINK, HEADLESS_DISABLED,
    validate_choice, chat_url, open_chat_link, UnsafeTransportError,
)
from services.whatsapp_queue.queue_v246 import SafeWhatsAppQueue, PENDING, UNKNOWN, INVALID
from services.whatsapp_queue.manual_handoff_v249 import open_one_pending_chat


def q(tmp_path):
    return SafeWhatsAppQueue(str(tmp_path/'wa.sqlite'))


def jobs(n=3):
    return [{'student_id':i+1,'recipient':f'0532123456{i+1}','message':f'Ödev {i+1}'} for i in range(n)]


def test_registry_keys_are_unique():
    assert len({t.key for t in CHOICES}) == len(CHOICES)


def test_old_selenium_still_default_and_enabled():
    assert CHOICES[0].key == SELENIUM
    assert validate_choice(SELENIUM).automated is True


@pytest.mark.parametrize('key',[DESKTOP_LINK,WEB_LINK])
def test_manual_options_are_not_automatic(key):
    assert validate_choice(key).automated is False


def test_headless_is_quarantined():
    with pytest.raises(UnsafeTransportError): validate_choice(HEADLESS_DISABLED)


def test_unknown_transport_is_rejected():
    with pytest.raises(UnsafeTransportError): validate_choice('random-other-channel')


def test_link_never_accepts_selenium_or_headless():
    for key in [SELENIUM, HEADLESS_DISABLED, 'missing']:
        with pytest.raises(UnsafeTransportError): chat_url(key,'905321234567','Hi')


@pytest.mark.parametrize('phone', ['+905321234567','0','', '90532123456&recipient=other','abc'])
def test_link_rejects_invalid_phone(phone):
    with pytest.raises(ValueError): chat_url(WEB_LINK,phone,'Ödev')


def test_message_encoded_and_target_exact():
    u=chat_url(WEB_LINK,'905321234567','Üslü sayılar & grafik?\nÖdev')
    assert u.startswith('https://web.whatsapp.com/send?')
    parts=urllib.parse.parse_qs(urllib.parse.urlparse(u).query)
    assert parts=={'phone':['905321234567'],'text':['Üslü sayılar & grafik?\nÖdev']}


def test_desktop_has_protocol_scheme():
    assert chat_url(DESKTOP_LINK,'905321234567','Test').startswith('whatsapp://send?')


def test_empty_message_rejected():
    with pytest.raises(ValueError): chat_url(WEB_LINK,'905321234567','  ')


def test_opener_injection_without_real_whatsapp():
    urls=[]
    open_chat_link(DESKTOP_LINK,'905321234567','Test',opener=urls.append)
    assert len(urls)==1 and urls[0].startswith('whatsapp://send?')


def test_only_one_of_three_chats_opened_per_click(tmp_path):
    queue=q(tmp_path); batch=queue.create_batch('/tmp/example.db',jobs())
    links=[]
    result=open_one_pending_chat(queue,batch,WEB_LINK,opener=links.append)
    assert result.attempted and result.pending==2
    assert len(links)==1
    assert queue.counts(batch)=={UNKNOWN:1,PENDING:2}


def test_method_switch_does_not_retry_unknown(tmp_path):
    queue=q(tmp_path); batch=queue.create_batch('/tmp/example.db',jobs(2))
    links=[]
    open_one_pending_chat(queue,batch,WEB_LINK,opener=links.append)
    open_one_pending_chat(queue,batch,DESKTOP_LINK,opener=links.append)
    assert len(links)==2
    assert links[0].startswith('https://') and links[1].startswith('whatsapp://')
    assert queue.counts(batch)=={UNKNOWN:2}
    assert open_one_pending_chat(queue,batch,WEB_LINK,opener=links.append).attempted is False
    assert len(links)==2


def test_opener_raises_uncertainty_no_retry(tmp_path):
    queue=q(tmp_path); batch=queue.create_batch('/tmp/example.db',jobs(2))
    def bad(url): raise RuntimeError('private token and message should not appear')
    result=open_one_pending_chat(queue,batch,WEB_LINK,opener=bad)
    assert result.attempted and result.pending==1
    rows=queue.rows(batch)
    assert rows[0]['state']==UNKNOWN
    assert 'private token' not in rows[0]['detail']


def test_invalid_recipients_skip_without_block(tmp_path):
    queue=q(tmp_path)
    batch=queue.create_batch('/tmp/example.db',[
        {'student_id':7,'recipient':'not a phone','message':'Hello'},*jobs(2)])
    urls=[]
    result=open_one_pending_chat(queue,batch,WEB_LINK,opener=urls.append)
    assert len(urls)==1 and result.pending==1
    assert queue.counts(batch)=={INVALID:1,UNKNOWN:1,PENDING:1}


def test_blocked_method_does_not_claim_job(tmp_path):
    queue=q(tmp_path); batch=queue.create_batch('/tmp/example.db',jobs(1))
    with pytest.raises(UnsafeTransportError):
        open_one_pending_chat(queue,batch,HEADLESS_DISABLED,opener=lambda _:None)
    assert queue.counts(batch)=={PENDING:1}


def test_selenium_not_hijacked_by_manual_helper(tmp_path):
    queue=q(tmp_path); batch=queue.create_batch('/tmp/example.db',jobs(1))
    with pytest.raises(ValueError): open_one_pending_chat(queue,batch,SELENIUM,opener=lambda _: None)
    assert queue.counts(batch)=={PENDING:1}


def test_not_marked_as_delivered_after_manual_handoff(tmp_path):
    queue=q(tmp_path); batch=queue.create_batch('/tmp/example.db',jobs(1))
    open_one_pending_chat(queue,batch,WEB_LINK,opener=lambda _:True)
    states=[r['state'] for r in queue.rows(batch)]
    assert states==[UNKNOWN] and 'OK' not in states


def test_gui_keeps_old_send_flow_but_adds_selector():
    path=Path(__file__).resolve().parents[1]/'ui'/'mail_send_whatsapp.py'
    content=path.read_text('utf8')
    ast.parse(content)
    assert 'QComboBox' in content
    assert 'self._selected_transport()' in content
    assert 'transport_key=self._selected_transport()' in content
    assert '_try_import_selenium' in content
    assert 'open_one_pending_chat' in content
    assert 'WhatsAppWorker' in content
    assert 'self.cmbWAMethod.model().item' in content


def test_core_sources_still_exist_and_are_not_imported_by_manual_helper():
    path=Path(__file__).resolve().parents[1]/'services'/'whatsapp_queue'/'manual_handoff_v249.py'
    source=path.read_text('utf8')
    assert 'homework_form' not in source
    assert 'odev_kontrol' not in source
    assert 'selenium' not in source


@pytest.mark.parametrize('key',[DESKTOP_LINK, WEB_LINK])
def test_link_call_can_be_rejected_cleanly(key,tmp_path):
    queue=q(tmp_path); batch=queue.create_batch('/tmp/example.db',jobs(1))
    def reject(url): raise FileNotFoundError('No registered application')
    res=open_one_pending_chat(queue,batch,key,opener=reject)
    assert res.attempted
    assert queue.rows(batch)[0]['state']==UNKNOWN
