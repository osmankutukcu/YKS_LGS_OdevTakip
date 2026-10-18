from pathlib import Path
from unittest.mock import patch
import json
import subprocess
import sys
import pytest
from services.whatsapp_queue.baileys_v257 import prerequisites

ROOT = Path(__file__).resolve().parents[1]
NODE_DIR = ROOT/'services'/'whatsapp_queue'/'baileys_node_v257'


def test_no_platform_or_node_is_not_green():
    if sys.platform != 'win32':
        ok,why = prerequisites()
        assert not ok and 'Windows' in why


def test_node_package_pinned():
    assert json.loads((NODE_DIR/'package.json').read_text())['dependencies']['@whiskeysockets/baileys']=='7.0.0-rc14'


def test_preflight_fails_without_lock(monkeypatch,tmp_path):
    monkeypatch.setattr(sys,'platform','win32')
    (tmp_path/'package.json').write_text((NODE_DIR/'package.json').read_text())
    (tmp_path/'bridge.mjs').write_text('placeholder')
    with patch('services.whatsapp_queue.baileys_v257.subprocess.run',return_value=subprocess.CompletedProcess([],0,'v22.16.0','')):
        ok,why=prerequisites(node='node.exe',folder=tmp_path)
    assert not ok and 'kurulmamış' in why


def test_preflight_rejects_bad_integrity(monkeypatch,tmp_path):
    monkeypatch.setattr(sys,'platform','win32')
    (tmp_path/'package.json').write_text((NODE_DIR/'package.json').read_text())
    (tmp_path/'bridge.mjs').write_text('placeholder')
    (tmp_path/'package-lock.json').write_text(json.dumps({'packages':{'node_modules/@whiskeysockets/baileys':{'version':'7.0.0-rc14','integrity':'bad'}}}))
    with patch('services.whatsapp_queue.baileys_v257.subprocess.run',return_value=subprocess.CompletedProcess([],0,'v22.16.0','')):
        ok,why=prerequisites(node='node.exe',folder=tmp_path)
    assert not ok and 'kilidi' in why


def test_old_transport_stays_disabled():
    from services.whatsapp_queue.transport_v249 import HEADLESS_DISABLED, validate_choice, UnsafeTransportError
    with pytest.raises(UnsafeTransportError): validate_choice(HEADLESS_DISABLED)


def test_user_ui_keeps_previous_sender():
    source=(ROOT/'ui/mail_send_whatsapp.py').read_text()
    assert 'self.btnBaileysTest.clicked.connect(self._open_baileys_test_v257)' in source
    assert 'transport_key=self._selected_transport()' in source
    assert 'WhatsAppWebClient(' in source
    assert '_open_baileys_test_v257' in source
    assert 'sender' not in (ROOT/'ui/baileys_test_v257.py').read_text()[:25]


def test_node_bridge_rejects_unsolicited_bulk():
    bridge=(NODE_DIR/'bridge.mjs').read_text()
    assert 'checkCommand(JSON.parse(line))' in bridge
    assert 'claimed=true' in bridge
    assert 'sendMessage(req.phone' in bridge
    assert 'useMultiFileAuthState' not in bridge
    assert 'checkCommand' in bridge and "emit('qr'" in bridge
