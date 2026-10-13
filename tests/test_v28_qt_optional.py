# -*- coding: utf-8 -*-
"""Real Qt smoke test runs on Windows CI; omitted where PyQt6 unavailable."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QTableWidget, QTableWidgetItem
    from PyQt6.QtCore import Qt
except (ImportError, AttributeError):
    QApplication = None


@unittest.skipUnless(QApplication is not None, 'PyQt6 runtime not available')
class V28QtIntegrationSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_flow_insertion_and_original_checkbox_untouched(self):
        from ui.quick_coaching_bridge_v28 import install
        from ui.odev_kontrol import USERROLE
        from ui.odev_kontrol import FlowLayout
        class MinimalControl(QWidget):
            ogr_id = 1
            def __init__(self):
                super().__init__()
                root=QVBoxLayout(self)
                frame=QWidget()
                frame_layout=QVBoxLayout(frame)
                bar=QWidget()
                flow=FlowLayout(bar)
                existing=QPushButton('Kaydet')
                flow.addWidget(existing)
                frame_layout.addWidget(bar)
                root.addWidget(frame)
                self.tab=QTableWidget(1,6)
                cell=QTableWidgetItem()
                cell.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                cell.setCheckState(Qt.CheckState.Unchecked)
                self.tab.setItem(0,0,cell)
                idcell=QTableWidgetItem('Fizik')
                idcell.setData(USERROLE,31)
                self.tab.setItem(0,1,idcell)
                self.tab.setItem(0,3,QTableWidgetItem('Enerji'))
                root.addWidget(self.tab)
                self.existing=existing
        wnd=MinimalControl()
        try:
            b=install(wnd)
            self.assertEqual(b._homework_at(0),31)
            self.assertEqual(wnd.tab.item(0,0).checkState(),Qt.CheckState.Unchecked)
            self.assertEqual(wnd.existing.text(),'Kaydet')
            self.assertEqual(b.button.text(),'⚡ Hızlı Teşhis')
        finally:
            wnd.close()

if __name__=='__main__':
    unittest.main()
