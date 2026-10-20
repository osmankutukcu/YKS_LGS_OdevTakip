# -*- coding: utf-8 -*-
import os
import sys
import tempfile
import unittest

from PyQt6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from services.weekly_calendar_export_v35 import (
    _get_coach_name,
    _sanitize_filename,
    normalize_phone_number,
    export_html_to_pdf_file,
    WeeklyPlanWhatsAppDialog,
)
from services.smart_calendar import SmartCalendarService
from utils import settings as appset


class TestWeeklyCalendarExportV35(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_coach_name_in_html(self):
        # Verify settings egitim_kocu
        old_coach = appset.ayar_get("egitim_kocu", "")
        try:
            appset.ayar_set("egitim_kocu", "Osman Kütükçü")
            bundle = SmartCalendarService.create_weekly_plan_data(
                "Berna Fırat",
                [{"ders": "Fizik", "kitap": "FİZİK1", "konu": "Basınç", "sure": 75}],
                {"daily_max": 300},
            )
            html = bundle["html"]
            self.assertIn("Osman Kütükçü", html)
            self.assertIn("Koç / Öğretmen:", html)
        finally:
            appset.ayar_set("egitim_kocu", old_coach)

    def test_sanitize_filename(self):
        self.assertEqual(_sanitize_filename("Berna Fırat"), "Berna_Fırat")
        self.assertEqual(_sanitize_filename("Ali / Veli: Test*?"), "Ali__Veli_Test")

    def test_phone_normalization(self):
        self.assertEqual(normalize_phone_number("05464416905"), "905464416905")
        self.assertEqual(normalize_phone_number("5464416905"), "905464416905")
        self.assertEqual(normalize_phone_number("+90 546 441 69 05"), "905464416905")
        self.assertIsNone(normalize_phone_number("123"))

    def test_export_html_to_pdf(self):
        out_pdf = os.path.join(self.tmp_dir.name, "test_plan.pdf")
        html = "<html><body><h1>Haftalık Çalışma Planı</h1><p>Test İçerik</p></body></html>"
        path = export_html_to_pdf_file(html, out_pdf)
        self.assertTrue(os.path.exists(path))
        self.assertGreater(os.path.getsize(path), 500)

    def test_whatsapp_dialog_init(self):
        out_pdf = os.path.join(self.tmp_dir.name, "test_plan.pdf")
        with open(out_pdf, "w") as f:
            f.write("%PDF-1.4 mock")
        dlg = WeeklyPlanWhatsAppDialog(None, 1, "Berna Fırat", out_pdf)
        self.assertIn("Berna Fırat", dlg.txt_message.toPlainText())
        self.assertTrue(dlg.rb_desktop.isChecked())


if __name__ == "__main__":
    unittest.main()
