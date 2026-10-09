
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QGridLayout, QLabel, QComboBox, QDateEdit, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QMessageBox, QHBoxLayout
from PyQt6.QtCore import QDate
from db import get_conn

TYT_DERSLER = ['Türkçe','Sosyal','Matematik','Fen']
AYT_DERSLER = ['Matematik','Fizik','Kimya','Biyoloji','Edebiyat','Tarih','Coğrafya','Felsefe','Din','Dil']

class DenemeSonuclari(QDialog):
    def __init__(self, ebeveyn=None):
        super().__init__(ebeveyn); self.setWindowTitle('Deneme Sonuçları'); self.resize(920, 600)
        v = QVBoxLayout(self); g = QGridLayout(); v.addLayout(g)
        self.cmbOgr = QComboBox(); self.cmbTur = QComboBox(); self.cmbTur.addItems(['TYT','AYT'])
        self.dt = QDateEdit(); self.dt.setCalendarPopup(True); self.dt.setDate(QDate.currentDate())
        self.txtAd = QLineEdit()
        r=0
        g.addWidget(QLabel('Öğrenci'), r,0); g.addWidget(self.cmbOgr, r,1); r+=1
        g.addWidget(QLabel('Tür'), r,0); g.addWidget(self.cmbTur, r,1); r+=1
        g.addWidget(QLabel('Tarih'), r,0); g.addWidget(self.dt, r,1); r+=1
        g.addWidget(QLabel('Deneme Adı'), r,0); g.addWidget(self.txtAd, r,1); r+=1

        self.tab = QTableWidget(0, 4); self.tab.setHorizontalHeaderLabels(['Ders','Doğru','Yanlış','Net'])
        v.addWidget(self.tab)
        hb = QHBoxLayout(); self.btnHesap = QPushButton('Netleri Hesapla'); self.btnKaydet = QPushButton('Kaydet'); hb.addStretch(1); hb.addWidget(self.btnHesap); hb.addWidget(self.btnKaydet); v.addLayout(hb)

        self.cmbTur.currentTextChanged.connect(self._yukle_dersler)
        self.btnHesap.clicked.connect(self._hesapla)
        self.btnKaydet.clicked.connect(self._kaydet)
        self._yukle_ogr()
        self._yukle_dersler()

    def _yukle_ogr(self):
        con = get_conn()
        for i,ad,soy in con.execute("SELECT id, ad, soyad FROM ogrenci ORDER BY ad,soyad"):
            self.cmbOgr.addItem(f"{ad} {soy}", i)

    def _yukle_dersler(self):
        dersler = TYT_DERSLER if self.cmbTur.currentText()=='TYT' else AYT_DERSLER
        self.tab.setRowCount(0)
        for d in dersler:
            r = self.tab.rowCount(); self.tab.insertRow(r)
            self.tab.setItem(r,0, QTableWidgetItem(d))
            self.tab.setItem(r,1, QTableWidgetItem('0'))
            self.tab.setItem(r,2, QTableWidgetItem('0'))
            self.tab.setItem(r,3, QTableWidgetItem('0'))

    def _hesapla(self):
        for r in range(self.tab.rowCount()):
            try:
                dog = int(self.tab.item(r,1).text())
                yan = int(self.tab.item(r,2).text())
                net = dog - yan/4.0
            except Exception:
                net = 0.0
            self.tab.setItem(r,3, QTableWidgetItem(f"{net:.2f}"))

    def _kaydet(self):
        con = get_conn()
        ogr = self.cmbOgr.currentData(); tur = self.cmbTur.currentText()
        ad = self.txtAd.text().strip() or f"{tur} Deneme"
        tarih = self.dt.date().toString('yyyy-MM-dd')
        cur = con.execute("INSERT INTO deneme(ogrenci_id, tur, ad, tarih) VALUES(?,?,?,?)", (ogr, tur, ad, tarih))
        did = cur.lastrowid
        for r in range(self.tab.rowCount()):
            ders = self.tab.item(r,0).text()
            try: dog = int(self.tab.item(r,1).text())
            except Exception: dog = 0
            try: yan = int(self.tab.item(r,2).text())
            except Exception: yan = 0
            try: net = float(self.tab.item(r,3).text())
            except Exception: net = dog - yan/4.0
            con.execute("INSERT INTO deneme_sonuc(deneme_id, ders, dogru, yanlis, net) VALUES(?,?,?,?,?)", (did, ders, dog, yan, net))
        con.commit()
        QMessageBox.information(self, 'Kaydedildi', 'Deneme sonuçları kaydedildi.')
