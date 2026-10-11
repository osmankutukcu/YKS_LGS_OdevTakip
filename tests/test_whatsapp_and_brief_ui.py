# -*- coding: utf-8 -*-
"""
Tests for WhatsApp sending mode options (Desktop vs Web) and Günün Akıllı Özeti UI sizing.
"""
import pytest
from unittest.mock import patch, MagicMock
from PyQt6.QtWidgets import QApplication, QDialog

# Ensure single QApplication instance
app = QApplication.instance() or QApplication([])

def test_whatsapp_dialog_channels_and_defaults():
    from ui.whatsapp_dialog import WhatsAppGonderDialog

    target = [("Test Öğrenci", "05464416905")]
    msg = "Test mesajı"

    with patch("utils.settings.ayar_get", return_value="desktop"):
        dlg = WhatsAppGonderDialog(target, msg, auto_send=False)

    # 1. Radio buttons exist
    assert hasattr(dlg, "rbDesktop")
    assert hasattr(dlg, "rbWeb")
    assert dlg.rbDesktop.isChecked()
    assert not dlg.rbWeb.isChecked()
    assert dlg.gonderim_modu() == "desktop"
    assert "WhatsApp ile Gönder" in dlg.btnSend.text()

    # 2. Switch to Web mode
    dlg.rbWeb.setChecked(True)
    assert dlg.gonderim_modu() == "web"
    assert "Web WhatsApp ile Gönder" in dlg.btnSend.text()

    # 3. Switch back to Desktop mode
    dlg.rbDesktop.setChecked(True)
    assert dlg.gonderim_modu() == "desktop"
    assert "WhatsApp ile Gönder" in dlg.btnSend.text()

def test_whatsapp_gonder_web_dispatch():
    from utils import whatsapp

    numaralar = ["05464416905"]
    mesaj = "Merhaba velimiz"

    with patch("webbrowser.open") as mock_browser, \
         patch("utils.whatsapp._after_send_check_and_log", return_value=True):
        res = whatsapp.whatsapp_gonder(numaralar, mesaj, mode="web")

        assert res["gonderilen"] == 1
        assert len(res["ok"]) == 1
        assert mock_browser.called
        call_url = mock_browser.call_args[0][0]
        assert "web.whatsapp.com/send" in call_url
        assert "phone=905464416905" in call_url

def test_whatsapp_dialog_auto_send_on_click():
    from ui.whatsapp_dialog import WhatsAppGonderDialog

    target = [("Öğrenci", "05464416905")]
    msg = "Ödev hatırlatması"

    dlg = WhatsAppGonderDialog(target, msg, auto_send=True)
    with patch.object(dlg, "mesajlari_gonder", return_value={"ok": ["905464416905"], "gonderilen": 1}) as mock_send, \
         patch.object(dlg, "accept") as mock_accept:
        dlg._on_send_clicked()
        assert mock_send.called
        assert mock_accept.called

def test_smart_assistant_dialog_geometry_and_chips():
    from ui.smart_assistant_dialog import SmartAssistantDialog

    dlg = SmartAssistantDialog()

    # Geometry checks: wider dialog
    assert dlg.width() >= 740
    assert dlg.minimumWidth() >= 740

    # All 6 chips are present with complete labels
    expected_chips = {
        "priority": "⭐ Bugünün 5’i",
        "all": "Tümü",
        "risk": "⚠️ Riskler",
        "star": "🌟 Başarılar",
        "birthday": "🎂 Kutlamalar",
        "silent": "👻 Sessizler"
    }
    for key, label in expected_chips.items():
        assert key in dlg.filter_btn_group
        btn = dlg.filter_btn_group[key]
        assert btn.text() == label
