# -*- coding: utf-8 -*-
"""Verification tests for AciklanabilirRaporlarFormu chart enhancements."""
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QDate

from ui.safe_reports_v3589 import AciklanabilirRaporlarFormu

ROOT = Path(__file__).resolve().parents[1]


class SafeReportsV3594Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.form = AciklanabilirRaporlarFormu()

    def tearDown(self):
        self.form.close()

    def test_combo_change_triggers_goster(self):
        with patch.object(self.form, "_goster") as mock_goster:
            idx = (self.form.cmbTur.currentIndex() + 1) % self.form.cmbTur.count()
            self.form.cmbTur.setCurrentIndex(idx)
            self.assertTrue(mock_goster.called)

    def test_konu_verimi_uses_horizontal_bar_method(self):
        with patch.object(self.form, "_goster_konu_verimi_yatay") as mock_yatay:
            idx = self.form.cmbTur.findText("Konu Verimi (dk/konu)")
            self.assertGreaterEqual(idx, 0)
            self.form.cmbTur.setCurrentIndex(idx)
            self.form._goster()
            self.assertTrue(mock_yatay.called)

    def test_konu_verimi_yatay_execution_with_mock_data(self):
        idx = self.form.cmbTur.findText("Konu Verimi (dk/konu)")
        self.form.cmbTur.setCurrentIndex(idx)

        mock_data = [
            ("biyoloji - Nükleik Asitler ve ATP", 75.0),
            ("fizik - Düzgün Çembersel Hareket", 50.0),
            ("mat - Trigonometri", 30.0),
        ]
        with patch.object(self.form, "_konu_verimi", return_value=mock_data), \
             patch.object(self.form, "_generate_smart_insights") as mock_insights:
            self.form._goster_konu_verimi_yatay()
            self.assertEqual(len(self.form._last_table_rows), 3)
            self.assertEqual(self.form._last_table_rows[0][0], "biyoloji - Nükleik Asitler ve ATP")
            self.assertTrue(mock_insights.called)

    def test_date_validation_prevents_rendering(self):
        self.form.dtpBas.setDate(QDate(2026, 12, 1))
        self.form.dtpBit.setDate(QDate(2026, 1, 1))
        with patch("ui.safe_reports_v3589.QMessageBox.warning") as mock_warn:
            self.form._goster()
            self.assertTrue(mock_warn.called)

    def test_protected_hashes_intact(self):
        manifest = json.loads((ROOT / "tests/v42_protected_hashes.json").read_text("utf-8"))
        for rel_path, expected_hash in manifest.items():
            content = (ROOT / rel_path).read_bytes()
            actual_hash = hashlib.sha256(content).hexdigest()
            self.assertEqual(actual_hash, expected_hash, f"Protected file corrupted: {rel_path}")


if __name__ == "__main__":
    unittest.main()
