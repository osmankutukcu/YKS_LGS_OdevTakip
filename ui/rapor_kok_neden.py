from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHBoxLayout, QLabel, QComboBox, QPushButton, QDateEdit
)
from PyQt6.QtCore import QDate
from db import get_conn


class RaporKokNeden(QDialog):
    def __init__(self, ebeveyn=None):
        super().__init__(ebeveyn)
        self.setWindowTitle('Kök Neden Analizi')
        self.resize(720, 560)

        lay = QVBoxLayout(self)

        # --- Filtre barı
        top = QHBoxLayout()
        self.cmbOgr = QComboBox()
        self.cmbDers = QComboBox()
        self.cmbKoc = QComboBox()
        self.dtMin = QDateEdit()
        self.dtMax = QDateEdit()
        self.dtMin.setCalendarPopup(True)
        self.dtMax.setCalendarPopup(True)
        # Varsayılan: son 90 gün
        self.dtMax.setDate(QDate.currentDate())
        self.dtMin.setDate(QDate.currentDate().addDays(-90))

        btn = QPushButton('Uygula')

        top.addWidget(QLabel('Öğrenci:')); top.addWidget(self.cmbOgr)
        top.addWidget(QLabel('Ders:'));     top.addWidget(self.cmbDers)
        top.addWidget(QLabel('Koç:'));      top.addWidget(self.cmbKoc)
        top.addWidget(QLabel('Başlangıç:')); top.addWidget(self.dtMin)
        top.addWidget(QLabel('Bitiş:'));     top.addWidget(self.dtMax)
        top.addStretch(1)
        top.addWidget(btn)
        lay.addLayout(top)

        # --- Tablolar
        self.tab = QTableWidget(0, 3)
        self.tab.setHorizontalHeaderLabels(['Gerekçe', 'Adet', 'Oran %'])
        lay.addWidget(self.tab)

        self.tabKoc = QTableWidget(0, 2)
        self.tabKoc.setHorizontalHeaderLabels(['Koç', 'Adet'])
        lay.addWidget(self.tabKoc)

        btn.clicked.connect(self._draw)
        self._load_filters()
        self._draw()

    def _load_filters(self):
        con = get_conn()

        # Öğrenciler
        self.cmbOgr.clear()
        self.cmbOgr.addItem('Tümü', '*')
        try:
            for i, ad, soy in con.execute("SELECT id, ad, soyad FROM ogrenci ORDER BY ad, soyad"):
                self.cmbOgr.addItem(f"{ad} {soy}", i)
        except Exception:
            pass

        # Dersler
        self.cmbDers.clear()
        self.cmbDers.addItem('Tümü', '*')
        for d in [
            'tyt_matematik', 'problemler', 'ayt_matematik', 'geometri', 'fizik',
            'kimya', 'biyoloji', 'turkce', 'paragraf', 'tarih', 'cografya',
            'felsefe', 'edebiyat', 'lgs_matematik', 'lgs_fen', 'lgs_turkce',
            'lgs_inkilap', 'lgs_din', 'lgs_ingilizce'
        ]:
            self.cmbDers.addItem(d, d)

        # Koçlar
        self.cmbKoc.clear()
        self.cmbKoc.addItem('Tümü', '*')
        try:
            rows = con.execute(
                "SELECT DISTINCT COALESCE(koc,'') FROM odev_satir WHERE koc IS NOT NULL AND koc<>''"
            ).fetchall()
            for (k,) in rows:
                self.cmbKoc.addItem(k, k)
        except Exception:
            pass

    def _draw(self):
        con = get_conn()

        where = []
        params = []

        ogr = self.cmbOgr.currentData()
        ders = self.cmbDers.currentData()
        koc = self.cmbKoc.currentData()
        dmin = self.dtMin.date().toString('yyyy-MM-dd') if self.dtMin.date() else None
        dmax = self.dtMax.date().toString('yyyy-MM-dd') if self.dtMax.date() else None

        if ogr != '*' and ogr is not None:
            where.append('ogrenci_id = ?'); params.append(ogr)
        if ders != '*' and ders is not None:
            where.append('ders = ?'); params.append(ders)
        if koc != '*' and koc is not None:
            where.append("COALESCE(koc,'') = ?"); params.append(koc)
        if dmin:
            where.append('tarih >= ?'); params.append(dmin)
        if dmax:
            where.append('tarih <= ?'); params.append(dmax)

        wh = ('WHERE ' + ' AND '.join(where)) if where else ''

        # Gerekçe dağılımı
        if wh:
            q = (
                f"SELECT COALESCE(gerekce,'(belirtilmedi)'), COUNT(*) AS adet "
                f"FROM odev_satir {wh} AND (durum!='tamam' OR durum IS NULL) "
                f"GROUP BY gerekce ORDER BY adet DESC"
            )
        else:
            q = (
                "SELECT COALESCE(gerekce,'(belirtilmedi)'), COUNT(*) AS adet "
                "FROM odev_satir WHERE (durum!='tamam' OR durum IS NULL) "
                "GROUP BY gerekce ORDER BY adet DESC"
            )

        rows = list(con.execute(q, tuple(params)))
        total = sum(r[1] for r in rows) or 1

        self.tab.setRowCount(0)
        for g, a in rows:
            r = self.tab.rowCount()
            self.tab.insertRow(r)
            self.tab.setItem(r, 0, QTableWidgetItem(g or '(belirtilmedi)'))
            self.tab.setItem(r, 1, QTableWidgetItem(str(a)))
            self.tab.setItem(r, 2, QTableWidgetItem(str(round(100 * a / total, 1))))

        # Koç kırılımı
        if wh:
            qk = (
                f"SELECT COALESCE(koc,'(bilinmiyor)'), COUNT(*) "
                f"FROM odev_satir {wh} AND (durum!='tamam' OR durum IS NULL) "
                f"GROUP BY COALESCE(koc,'(bilinmiyor)') ORDER BY 2 DESC"
            )
        else:
            qk = (
                "SELECT COALESCE(koc,'(bilinmiyor)'), COUNT(*) "
                "FROM odev_satir WHERE (durum!='tamam' OR durum IS NULL) "
                "GROUP BY COALESCE(koc,'(bilinmiyor)') ORDER BY 2 DESC"
            )

        krows = list(con.execute(qk, tuple(params)))
        self.tabKoc.setRowCount(0)
        for k, a in krows:
            r = self.tabKoc.rowCount()
            self.tabKoc.insertRow(r)
            self.tabKoc.setItem(r, 0, QTableWidgetItem(k or '(bilinmiyor)'))
            self.tabKoc.setItem(r, 1, QTableWidgetItem(str(a)))
