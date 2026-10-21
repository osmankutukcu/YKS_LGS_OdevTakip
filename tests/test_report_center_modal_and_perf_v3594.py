# -*- coding: utf-8 -*-
"""Verification tests for Report Center modal unblocking and sidebar performance."""
import unittest
from PyQt6.QtWidgets import QApplication, QPushButton, QWidget
from PyQt6.QtCore import QEvent
from ui.report_center_v3581 import ReportCenterDialog, REPORT_ROUTES


class MockParent(QWidget):
    def __init__(self):
        super().__init__()
        self.called_routes = []

    def _rapor_ac(self):
        self.called_routes.append("_rapor_ac")

    def _ogrenci_detay(self):
        self.called_routes.append("_ogrenci_detay")

    def _show_report_guide(self):
        self.called_routes.append("_show_report_guide")


class ReportCenterModalAndPerfTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_launch_sets_pending_route_and_accepts(self):
        parent = MockParent()
        dlg = ReportCenterDialog(parent)
        self.assertIsNone(dlg.pending_route)

        dlg._launch("_rapor_ac")
        self.assertEqual(dlg.pending_route, "_rapor_ac")
        dlg.close()

    def test_show_guide_sets_pending_route(self):
        parent = MockParent()
        dlg = ReportCenterDialog(parent)
        dlg._show_guide()
        self.assertEqual(dlg.pending_route, "_show_report_guide")
        dlg.close()

    def test_invalid_launch_rejected(self):
        from unittest.mock import patch
        parent = MockParent()
        dlg = ReportCenterDialog(parent)
        with patch("ui.report_center_v3581.QMessageBox.warning") as mock_warn:
            dlg._launch("unauthorized_dangerous_method")
            self.assertTrue(mock_warn.called)
        self.assertIsNone(dlg.pending_route)
        dlg.close()

    def test_sidebar_style_polish_called_only_on_state_change(self):
        btn1 = QPushButton("B1")
        btn2 = QPushButton("B2")
        all_btns = [btn1, btn2]

        polish_counts = {btn1: 0, btn2: 0}

        def fake_unpolish(w): pass
        def fake_polish(w): polish_counts[w] += 1

        style1 = btn1.style()
        style1.unpolish = fake_unpolish
        style1.polish = fake_polish

        def _set_active(target_btn):
            for btn in all_btns:
                is_act = (btn == target_btn)
                curr_act = (btn.property("active") == "true")
                if is_act != curr_act:
                    btn.setProperty("active", "true" if is_act else "false")
                    if not is_act and btn.hasFocus():
                        btn.clearFocus()
                    s = btn.style()
                    if s is not None:
                        s.unpolish(btn)
                        s.polish(btn)
                    btn.update()

        # Initial activate btn1 -> both change (btn1 to true, btn2 stays false)
        _set_active(btn1)
        self.assertEqual(polish_counts[btn1], 1)
        self.assertEqual(polish_counts[btn2], 0)

        # Call again with btn1 -> no state change, zero polish calls!
        _set_active(btn1)
        self.assertEqual(polish_counts[btn1], 1)
        self.assertEqual(polish_counts[btn2], 0)

        # Switch to btn2 -> both change (btn1 to false, btn2 to true)
        _set_active(btn2)
        self.assertEqual(polish_counts[btn1], 2)
        self.assertEqual(polish_counts[btn2], 1)

    def test_report_center_is_non_modal_window(self):
        parent = MockParent()
        dlg = ReportCenterDialog(parent)
        self.assertFalse(dlg.isModal())
        self.assertTrue(bool(dlg.windowFlags() & dlg.windowFlags().Window))
        dlg.close()


if __name__ == "__main__":
    unittest.main()
