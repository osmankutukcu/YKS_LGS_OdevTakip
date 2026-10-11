# -*- coding: utf-8 -*-
import os
import unittest
from pathlib import Path
from PyQt6.QtWidgets import QApplication
import sys

# Ensure QApplication exists for tests
app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

from app import ModernSplash
from services.web_service import _fallback_cache_path
from utils.error_manager import _log_dir
from utils.settings import _get_conn
from ui.mobile_schedule import MobileScheduleGenerator, ScheduleActionDialog, SmartMobileSchedulePreviewDialog


class TestV3516Fixes(unittest.TestCase):
    def test_splash_developer_credits(self):
        splash = ModernSplash()
        self.assertIn("Osman Kütükçü", "Osman Kütükçü")
        self.assertTrue(hasattr(splash, "font_author"))

    def test_permission_denied_safe_locations(self):
        # 1. error_manager._log_dir
        ld = _log_dir()
        self.assertTrue(os.path.isabs(ld))
        self.assertFalse(ld.startswith("logs/"))

        # 2. web_service._fallback_cache_path
        fcp = _fallback_cache_path()
        self.assertTrue(os.path.isabs(fcp))
        self.assertFalse("services/web_cache.db" in fcp)

    def test_mobile_schedule_pdf_contains_whatsapp_and_call_links(self):
        gen = MobileScheduleGenerator(None)
        dummy_schedule = {
            "Pazartesi": [
                {
                    "tip": "Teslim",
                    "ad": "Ahmet Yılmaz",
                    "saat": "18:00",
                    "tel_ogr": "05551234567",
                    "tel_veli": "05559876543",
                    "detay": "Matematik Ödevi",
                    "renk": "#3b82f6",
                    "meta": {
                        "lines": ["Polinomlar Test 1"],
                        "nice_date": "12.10.2026"
                    }
                }
            ]
        }
        next_7_days = [("2026-10-12", "Pazartesi")]
        
        # Test PDF HTML generation
        pdf_html = gen._build_html(dummy_schedule, next_7_days, for_pdf=True)
        self.assertIn("https://wa.me/905551234567", pdf_html)
        self.assertIn("tel:905551234567", pdf_html)
        self.assertIn("WhatsApp Raporu", pdf_html)
        self.assertIn("Ara", pdf_html)

    def test_schedule_action_dialog_scroll_and_geometry(self):
        dlg = ScheduleActionDialog(None, MobileScheduleGenerator(None), lambda: None, lambda: None, lambda: None)
        self.assertEqual(dlg.width(), 520)
        self.assertIsNotNone(dlg.maximumHeight())
        self.assertLessEqual(dlg.maximumHeight(), 650)
        dlg.close()


if __name__ == "__main__":
    unittest.main()
