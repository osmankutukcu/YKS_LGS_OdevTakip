# ui/widgets/quick_stats.py
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt
import db, datetime

class QuickStats(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        h = QHBoxLayout(self); h.setContentsMargins(0,0,8,0); h.setSpacing(18)
        self.l1, self.l2, self.l3 = QLabel(), QLabel(), QLabel()
        for l in (self.l1, self.l2, self.l3):
            l.setStyleSheet("font-weight:600; color:#3a3a3a;")
            h.addWidget(l); h.addStretch(1)
        self.refresh()

    def refresh(self):
        try:
            con = db.get_conn()
            toplam = con.execute("SELECT COUNT(*) FROM ogrenci").fetchone()[0]
            hafta = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
            verilen = con.execute("SELECT COUNT(*) FROM odev_kume WHERE verilis_tarihi>=?", (hafta,)).fetchone()[0]
            # kaba tamamlama: durum 'yapildi' oranı
            done = con.execute("SELECT COUNT(*) FROM odev WHERE LOWER(COALESCE(durum,'')) IN ('yapildi','tamam')").fetchone()[0]
            allc = con.execute("SELECT COUNT(*) FROM odev").fetchone()[0] or 1
            self.l1.setText(f"👥 Öğrenci: {toplam}")
            self.l2.setText(f"🗂️ Son 7 gün verilen küme: {verilen}")
            self.l3.setText(f"✅ Tamamlama: %{int(100*done/allc)}")
        except Exception:
            pass