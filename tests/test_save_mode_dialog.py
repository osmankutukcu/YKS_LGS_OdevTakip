"""Tests for ModernSaveModeDialog."""
import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QDate

app = QApplication.instance() or QApplication([])

from ui.save_mode_dialog import ModernSaveModeDialog, show_modern_save_mode_dialog


class SaveModeDialogTest(unittest.TestCase):
    def test_initial_state_defaults_to_yeni(self):
        dlg = ModernSaveModeDialog(None, ogr_id=1, initial_date=QDate(2026, 10, 27))
        self.assertEqual(dlg.selected_mode, "yeni")
        self.assertFalse(dlg.cmbKume.isEnabled())
        self.assertFalse(dlg.chkBitis.isChecked())
        self.assertFalse(dlg.dtBitis.isEnabled())
        self.assertIsNone(dlg.get_result())

    def test_accepted_yeni_returns_correct_contract(self):
        dlg = ModernSaveModeDialog(None, ogr_id=1, initial_date=QDate(2026, 10, 27))
        dlg.done(1)  # Accepted
        res = dlg.get_result()
        self.assertIsNotNone(res)
        self.assertEqual(res["mode"], "yeni")
        self.assertIsNone(res["kume_id"])
        self.assertFalse(res["bitis_guncelle"])
        self.assertIsNone(res["bitis_tarihi"])

    def test_switch_to_ekle_mode_and_enable_kume(self):
        dlg = ModernSaveModeDialog(None, ogr_id=5, initial_date=QDate(2026, 10, 27))
        dlg._set_mode("ekle")
        self.assertEqual(dlg.selected_mode, "ekle")
        self.assertTrue(dlg.cmbKume.isEnabled())
        dlg.done(1)
        res = dlg.get_result()
        self.assertEqual(res["mode"], "ekle")
        if dlg.cmbKume.count() > 0 and dlg.cmbKume.currentData() is not None:
            self.assertEqual(res["kume_id"], dlg.cmbKume.currentData())

    def test_date_update_flag_propagates_iso_date(self):
        dlg = ModernSaveModeDialog(None, ogr_id=1, initial_date=QDate(2026, 10, 30))
        dlg.chkBitis.setChecked(True)
        self.assertTrue(dlg.dtBitis.isEnabled())
        dlg.done(1)
        res = dlg.get_result()
        self.assertTrue(res["bitis_guncelle"])
        self.assertEqual(res["bitis_tarihi"], "2026-10-30")

    def test_rejected_dialog_returns_none(self):
        dlg = ModernSaveModeDialog(None, ogr_id=1)
        dlg.done(0)  # Rejected / Cancelled
        self.assertIsNone(dlg.get_result())


if __name__ == "__main__":
    unittest.main()
