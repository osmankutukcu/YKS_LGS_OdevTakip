from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QDateEdit, QFrame
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import QByteArray
import io
import matplotlib
matplotlib.use('Agg')  # GUI olmadan render
import matplotlib.pyplot as plt
from db import get_conn


class RaporTrend(QDialog):
    def __init__(self, ebeveyn=None):
        super().__init__(ebeveyn)
        self.setWindowTitle('Haftalık Trendler')
        self.resize(820, 600)

        # ----- Ana layout
        self.lay = QVBoxLayout(self)

        # ----- Filtre barı (ÖNCE widget'ları oluşturuyoruz)
        top = QHBoxLayout()
        self.cmbOgr = QComboBox()
        self.cmbGrup = QComboBox()   # Şimdilik kullanılmıyor ama korunuyor
        self.cmbDers = QComboBox()
        self.dtMin = QDateEdit()
        self.dtMax = QDateEdit()
        self.dtMin.setCalendarPopup(True)
        self.dtMax.setCalendarPopup(True)
        self.btnFiltre = QPushButton('Uygula')

        top.addWidget(QLabel('Öğrenci:'));   top.addWidget(self.cmbOgr)
        top.addWidget(QLabel('Grup:'));      top.addWidget(self.cmbGrup)
        top.addWidget(QLabel('Ders:'));      top.addWidget(self.cmbDers)
        top.addWidget(QLabel('Başlangıç:')); top.addWidget(self.dtMin)
        top.addWidget(QLabel('Bitiş:'));     top.addWidget(self.dtMax)
        top.addStretch(1)
        top.addWidget(self.btnFiltre)
        self.lay.addLayout(top)

        # ----- Combobox/veri doldurma ARTIK widget'lar hazırken çağrılıyor
        self._load_filters()

        # ----- Sinyal
        self.btnFiltre.clicked.connect(self._draw)

        # ----- İlk çizim
        self._draw()

    # ---------------------------------------------------------------------

    def _load_filters(self):
        con = get_conn()

        # Öğrenciler
        self.cmbOgr.clear()
        self.cmbOgr.addItem('Tümü', '*')
        try:
            for i, ad, soy in con.execute(
                "SELECT id, ad, soyad FROM ogrenci ORDER BY ad, soyad"
            ):
                self.cmbOgr.addItem(f"{ad} {soy}", i)
        except Exception:
            pass

        # Dersler
        self.cmbDers.clear()
        self.cmbDers.addItem('Tümü', '*')
        for d in [
            'tyt_matematik', 'problemler', 'ayt_matematik', 'geometri',
            'fizik', 'kimya', 'biyoloji', 'turkce', 'paragraf', 'tarih',
            'cografya', 'felsefe', 'edebiyat', 'lgs_matematik', 'lgs_fen',
            'lgs_turkce', 'lgs_inkilap', 'lgs_din', 'lgs_ingilizce'
        ]:
            self.cmbDers.addItem(d, d)

    # ---------------------------------------------------------------------

    def _draw(self):
        # Filtre barı harici tüm widget'ları temizle
        while self.lay.count() > 1:
            item = self.lay.itemAt(1)
            w = item.widget()
            if w is not None:
                w.setParent(None)
            else:
                # (ör: spacer/layout olursa)
                self.lay.removeItem(item)
                break

        con = get_conn()
        where, params = [], []

        ogr = self.cmbOgr.currentData()
        ders = self.cmbDers.currentData()
        if ogr not in (None, '*'):
            where.append('ogrenci_id = ?'); params.append(ogr)
        if ders not in (None, '*'):
            where.append('ders = ?'); params.append(ders)

        wh = ('WHERE ' + ' AND '.join(where)) if where else ''
        q1 = f"""
            SELECT strftime('%Y-%W', tarih) AS hafta,
                   SUM(COALESCE(sure,0)) AS toplam_sure,
                   SUM(CASE WHEN durum='tamam' THEN 1 ELSE 0 END) AS tamam_say,
                   SUM(CASE WHEN durum='gecikmis' THEN 1 ELSE 0 END)*1.0/NULLIF(COUNT(*),0) AS gecikme_oran
            FROM odev_satir
            {wh}
            GROUP BY hafta
            ORDER BY hafta
        """

        haftalar, sureler, tamams, gecikmeler = [], [], [], []
        for w, s, t, g in con.execute(q1, tuple(params)):
            haftalar.append(w or '')
            sureler.append(float(s or 0))
            tamams.append(int(t or 0))
            gecikmeler.append(float(g or 0))

        # ---------- Grafikler
        # 1) Toplam süre
        fig1, ax1 = plt.subplots()
        ax1.plot(haftalar, sureler, marker='o')
        ax1.set_title('Haftalık Toplam Süre (dk)')
        ax1.set_xlabel('Hafta'); ax1.set_ylabel('Dakika'); ax1.grid(True)
        buf1 = io.BytesIO(); fig1.tight_layout(); fig1.savefig(buf1, format='png'); plt.close(fig1)

        # 2) Tamamlanan ödev
        fig2, ax2 = plt.subplots()
        ax2.bar(haftalar, tamams)
        ax2.set_title('Haftalık Tamamlanan Ödev Sayısı')
        ax2.set_xlabel('Hafta'); ax2.set_ylabel('Adet'); ax2.grid(True, axis='y')
        buf2 = io.BytesIO(); fig2.tight_layout(); fig2.savefig(buf2, format='png'); plt.close(fig2)

        # 3) Gecikme oranı
        fig3, ax3 = plt.subplots()
        ax3.plot(haftalar, [g*100 for g in gecikmeler], marker='s')
        ax3.set_title('Haftalık Gecikme Oranı (%)')
        ax3.set_xlabel('Hafta'); ax3.set_ylabel('%'); ax3.grid(True)
        buf3 = io.BytesIO(); fig3.tight_layout(); fig3.savefig(buf3, format='png'); plt.close(fig3)

        # ---------- Görselleri layout'a ekle
        for buf, title in [(buf1, 'Toplam Süre'), (buf2, 'Tamamlanan'), (buf3, 'Gecikme Oranı')]:
            lbl = QLabel(title)
            lbl.setStyleSheet('font-weight:bold;margin:8px 0;')
            self.lay.addWidget(lbl)

            img = QLabel()
            pm = QPixmap()
            # PyQt6: bytes vermek yeterli
            pm.loadFromData(buf.getvalue())
            img.setPixmap(pm)
            img.setScaledContents(True)
            img.setMinimumHeight(180)
            self.lay.addWidget(img)

            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            self.lay.addWidget(line)