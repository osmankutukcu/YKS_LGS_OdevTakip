# -*- coding: utf-8 -*-
"""Windows CI Qt offscreen smoke: V30 opens without touching old checkboxes."""
import unittest
from unittest.mock import patch

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication, QComboBox, QTableWidget, QTableWidgetItem
except (ImportError, AttributeError):
    QApplication = None

@unittest.skipUnless(QApplication is not None, 'PyQt6 runtime not available')
class V30QtSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_new_preview_reads_matrix_without_changing_assignment(self):
        from ui.adaptive_draft_review_v30 import AdaptiveDraftReviewV30
        from services.adaptive_coaching_v30.drafts import fingerprint
        class Host:
            def __init__(self):
                self._loaded_student_id=1
                self.cmbAd=QComboBox()
                self.cmbSoyad=QComboBox()
                for widget in (self.cmbAd,self.cmbSoyad):
                    widget.addItem('Osman',1)
                self.verilen=QTableWidget(0,5)
                self.matrix=QTableWidget(1,2)
                self.matrix.setHorizontalHeaderLabels(['Konu','345'])
                self.matrix.setItem(0,0,QTableWidgetItem('Enerji'))
                self.check=QTableWidgetItem('')
                self.check.setFlags(Qt.ItemFlag.ItemIsUserCheckable|Qt.ItemFlag.ItemIsEnabled)
                self.check.setCheckState(Qt.CheckState.Unchecked)
                self.matrix.setItem(0,1,self.check)
                self._ders_tablolari={'Fizik':self.matrix}
            def _secili_ogrenci_id(self): return self.cmbAd.currentData()
            def _vtext(self,row,col): return self.verilen.item(row,col).text()
        host=Host()
        item={'lesson':'Fizik','book':'345','topic':'Enerji','minutes':15,'mode':'Geri getirme',
              'details':'Kısa hatırlama','level':'Ölçüm gerekli','category':'Güncel odak',
              'note':None,'transferable':True,'default_selected':True,'reason':''}
        draft={'student_id':1,'generated_on':'2026-10-13','preferences':{},'items':[item],
               'overload_note':False,'proposed_minutes':15}
        draft['fingerprint']=fingerprint(draft)
        with patch.object(AdaptiveDraftReviewV30,'_build_on_demand',return_value=draft):
            dlg=AdaptiveDraftReviewV30(1,host)
            try:
                self.assertEqual(dlg.grid.rowCount(),1)
                self.assertTrue(dlg.apply.isEnabled())
                self.assertEqual(host.check.checkState(), Qt.CheckState.Unchecked)
                self.assertEqual(host.verilen.rowCount(),0)
                host.cmbSoyad.clear()
                host.cmbSoyad.addItem('Başka Öğrenci',2)
                dlg.refresh()
                self.assertFalse(dlg.apply.isEnabled())
                self.assertEqual(host.check.checkState(), Qt.CheckState.Unchecked)
            finally:
                dlg.close()

if __name__=='__main__': unittest.main()
