from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem
from PyQt6.QtGui import QColor
class RaporIsiHaritasi(QDialog):
    def __init__(self, ebeveyn=None):
        super().__init__(ebeveyn); self.setWindowTitle('Konu Isı Haritası')
        lay = QVBoxLayout(self)
        self.tab = QTableWidget(0, 4); self.tab.setHorizontalHeaderLabels(['Ders','Konu','Tamam %','Gecikme %'])
        lay.addWidget(self.tab)
    def yukle(self, veriler):
        self.tab.setRowCount(0)
        for v in veriler:
            r = self.tab.rowCount(); self.tab.insertRow(r)
            self.tab.setItem(r,0, QTableWidgetItem(v['ders']))
            self.tab.setItem(r,1, QTableWidgetItem(v['konu']))
            t = QTableWidgetItem(str(v['tamam'])) ; g = QTableWidgetItem(str(v['gecikme']))
            # renk
            c = QColor(198,239,206) if v['tamam']>=80 else (QColor(255,235,156) if v['tamam']>=50 else QColor(255,204,204))
            t.setBackground(c)
            self.tab.setItem(r,2, t); self.tab.setItem(r,3, g)
