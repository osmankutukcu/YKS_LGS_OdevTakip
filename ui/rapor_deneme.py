
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton
from db import get_conn
import io
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import QByteArray
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt

class RaporDeneme(QDialog):
    def __init__(self, ebeveyn=None):
        super().__init__(ebeveyn); self.setWindowTitle('Deneme Raporları'); self.resize(900, 600)
        lay = QVBoxLayout(self)
        top = QHBoxLayout(); self.cmbOgr = QComboBox(); self.cmbTur = QComboBox(); self.cmbTur.addItems(['TYT','AYT','Tümü']); self.btn = QPushButton('Uygula')
        top.addWidget(QLabel('Öğrenci:')); top.addWidget(self.cmbOgr); top.addWidget(QLabel('Tür:')); top.addWidget(self.cmbTur); top.addStretch(1); top.addWidget(self.btn)
        lay.addLayout(top)
        self.img1 = QLabel(); self.img2 = QLabel()
        lay.addWidget(self.img1); lay.addWidget(self.img2)
        self._load_filters(); self.btn.clicked.connect(self._draw); self._draw()

    def _load_filters(self):
        con = get_conn(); self.cmbOgr.addItem('Tümü','*')
        for i,ad,soy in con.execute("SELECT id, ad, soyad FROM ogrenci ORDER BY ad,soyad"):
            self.cmbOgr.addItem(f"{ad} {soy}", i)

    def _draw(self):
        con = get_conn()
        where = []; params = []
        if self.cmbOgr.currentData()!='*': where.append('d.ogrenci_id=?'); params.append(self.cmbOgr.currentData())
        tur = self.cmbTur.currentText()
        if tur!='Tümü': where.append('d.tur=?'); params.append(tur)
        wh = ('WHERE '+ ' AND '.join(where)) if where else ''
        # Trend: tarih bazlı toplam net (tüm derslerin toplamı)
        q = f"""
        SELECT d.tarih, SUM(s.net) FROM deneme d
        JOIN deneme_sonuc s ON s.deneme_id = d.id
        {wh}
        GROUP BY d.tarih ORDER BY d.tarih
        """
        xs, ys = [], []
        for t, n in con.execute(q, tuple(params)):
            xs.append(t); ys.append(float(n or 0))
        fig1, ax1 = plt.subplots(); ax1.plot(xs, ys, marker='o'); ax1.set_title('Toplam Net Trend'); ax1.set_xlabel('Tarih'); ax1.set_ylabel('Net'); ax1.grid(True)
        buf1 = io.BytesIO(); fig1.tight_layout(); fig1.savefig(buf1, format='png'); plt.close(fig1)
        pm1 = QPixmap(); pm1.loadFromData(QByteArray(buf1.getvalue())); self.img1.setPixmap(pm1); self.img1.setScaledContents(True); self.img1.setMinimumHeight(220)

        # Isı haritası: ders x deneme (net); son 10 deneme
        q2 = f"""
        SELECT d.ad, s.ders, s.net FROM deneme d
        JOIN deneme_sonuc s ON s.deneme_id = d.id
        {wh}
        ORDER BY d.tarih DESC, d.id DESC LIMIT 200
        """
        rows = list(con.execute(q2, tuple(params)))
        # pivot
        dersler = sorted(set(r[1] for r in rows))
        denemeler = []
        for ad, _, _ in rows:
            if ad not in denemeler: denemeler.append(ad)
            if len(denemeler)>=10: break
        data = [[0.0]*len(denemeler) for _ in dersler]
        for ad, ders, net in rows:
            if ad in denemeler:
                i = dersler.index(ders); j = denemeler.index(ad); data[i][j] = float(net or 0)
        fig2, ax2 = plt.subplots()
        im = ax2.imshow(data, aspect='auto')
        ax2.set_xticks(range(len(denemeler))); ax2.set_xticklabels(denemeler, rotation=45, ha='right')
        ax2.set_yticks(range(len(dersler))); ax2.set_yticklabels(dersler)
        ax2.set_title('Ders Bazlı Net Isı Haritası (Son 10)')
        plt.colorbar(im, ax=ax2, fraction=0.046, pad=0.04)
        buf2 = io.BytesIO(); fig2.tight_layout(); fig2.savefig(buf2, format='png'); plt.close(fig2)
        pm2 = QPixmap(); pm2.loadFromData(QByteArray(buf2.getvalue())); self.img2.setPixmap(pm2); self.img2.setScaledContents(True); self.img2.setMinimumHeight(260)
