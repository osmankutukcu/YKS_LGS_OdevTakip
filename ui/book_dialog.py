# -*- coding: utf-8 -*-
"""
Kitap Ekle / Sil Dialog – PyQt6
+ Sağ tık: “Kitap Detayı…”
+ Sağ tık: “Kitap Özellikleri…”
+ Özellik penceresi: Hızlı alan butonları (+ Sayfa, + Soru Sayısı, + Test Sayısı, + Yayın, + Baskı Yılı)
+ Özellik editörü: Geniş satır / büyük editör (yazarken metin kesilmez)
+ “Kitap Adları” yanında: “Özellikleri Düzenle…” (metindeki veya havuzdaki kitaplar için)
+ İlerleme % = konu_istatistik’ten, DISTINCT konu üstünden
+ ogrenci_kitap.eklenme_tarih otomatik (yoksa kolon eklenir)
+ Tüm uyarılar/mesajlar: şık toast
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QTextEdit, QListWidget,
    QPushButton, QRadioButton, QWidget, QListWidgetItem, QSplitter,
    QMenu, QApplication, QLineEdit, QButtonGroup, QAbstractItemView, QTableWidget,
    QTableWidgetItem, QHeaderView, QToolButton, QStyleOptionViewItem, QStyledItemDelegate,
    QGroupBox, QFrame, QCheckBox
)
from PyQt6.QtCore import Qt, QPoint, QSettings, QTimer, QRect, QModelIndex
from PyQt6.QtGui import QColor, QFont
import re, sqlite3
import db  # mevcut db yardımcılarınızı kullanır

_BADGE_RE = re.compile(r"\s*[•·]\s*\d+\s*$")  # " • 7" gibi rozet soneklerini temizler


# =========================
#  Küçük Toast Bileşeni
# =========================
class _Toast(QWidget):
    def __init__(self, parent: QWidget, text: str, kind: str = "info", msec: int = 2400):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.ToolTip)
        self.setObjectName("_toast")
        self._lbl = QLabel(text, self); self._lbl.setWordWrap(True)
        pad = 12; self._lbl.move(pad, pad); self._lbl.setMinimumWidth(260)
        bg = {"info": "#111827", "ok": "#16a34a", "warn": "#92400e", "err": "#dc2626"}.get(kind, "#111827")
        self.setStyleSheet(f"""
            QWidget#_toast {{ background-color: {bg} !important; color: #ffffff !important; border-radius: 8px; border: none; }}
            QLabel {{ color: #ffffff !important; font-size: 13px; background: transparent; }}
        """)
        self._lbl.adjustSize()
        w = max(280, self._lbl.width()+2*pad); h = self._lbl.height()+2*pad
        self.resize(w, h)
        if parent:
            r = parent.rect(); m = 18; self.move(r.right()-w-m, r.bottom()-h-m)
        self.show(); QTimer.singleShot(msec, self.close)


# =========================
#  Yardımcı: Şema güvencesi
# =========================
def _ensure_column(con: sqlite3.Connection, table: str, col: str, coltype: str):
    try:
        cols = [c[1] for c in con.execute(f"PRAGMA table_info({table})")]
        if col not in cols:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")
            con.commit()
    except Exception:
        pass

def _ensure_table_kitap_ozellik(con: sqlite3.Connection):
    con.execute("""
        CREATE TABLE IF NOT EXISTS kitap_ozellik (
            ders TEXT NOT NULL,
            kitap_ad TEXT NOT NULL,
            key TEXT NOT NULL,
            val TEXT,
            PRIMARY KEY (ders, kitap_ad, key)
        )
    """)
    con.commit()


# =========================
#  Özellik Editörü Delegate
#  (çift tıklayınca büyük editor)
# =========================
class EditorDelegate(QStyledItemDelegate):
    _ROW_H = 34  # daha rahat yazım yüksekliği

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex):
        sz = super().sizeHint(option, index)
        if sz.height() < self._ROW_H:
            sz.setHeight(self._ROW_H)
        return sz

    def createEditor(self, parent, option, index):
        # Tek satırlık ama yüksek editör (yazarken kesilmesin)
        ed = QLineEdit(parent)
        ed.setMinimumHeight(self._ROW_H - 6)
        ed.setContentsMargins(6, 3, 6, 3)
        return ed

    def updateEditorGeometry(self, editor, option, index):
        # Editör tüm hücreyi güzelce kaplasın
        rect: QRect = option.rect
        rect.adjust(2, 2, -2, -2)
        editor.setGeometry(rect)


# =========================
#  Özellikler Dialogu
# =========================
class KitapOzellikDialog(QDialog):
    QUICK_KEYS = [
        ("SAYFA", "—"),
        ("SORU_SAYISI", "—"),
        ("TEST_SAYISI", "—"),
        ("YAYIN", "—"),
        ("BASKI_YILI", "—"),
    ]

    def __init__(self, con, ders: str, kitap: str, ebeveyn=None):
        super().__init__(ebeveyn)
        self.setWindowTitle("Kitap Özellikleri")
        self.resize(620, 460)
        self.con, self.ders, self.kitap = con, ders, kitap

        root = QVBoxLayout(self)
        root.addWidget(QLabel(f"<b>Ders:</b> {ders} — <b>Kitap:</b> {kitap}"))

        # Hızlı alan butonları
        fast = QHBoxLayout()
        fast.addWidget(QLabel("Hızlı ekle:"))
        self._fast_btns = []
        for title, _ in self.QUICK_KEYS:
            b = QToolButton(self); b.setText(f"+ {title.replace('_',' ').title()}")
            b.clicked.connect(lambda _, k=title: self._quick_add(k))
            self._fast_btns.append(b); fast.addWidget(b)
        fast.addStretch(1)
        root.addLayout(fast)

        # Tablo
        self.tbl = QTableWidget(0, 2, self)
        self.tbl.setItemDelegate(EditorDelegate(self.tbl))
        self.tbl.setHorizontalHeaderLabels(["Özellik", "Değer"])
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl.setAlternatingRowColors(True)
        root.addWidget(self.tbl, 1)

        # Alt butonlar
        hb = QHBoxLayout()
        btnAdd = QPushButton("➕ Ekle"); btnDel = QPushButton("➖ Sil")
        hb.addWidget(btnAdd); hb.addWidget(btnDel); hb.addStretch(1)
        btnOk = QPushButton("💾 Kaydet"); btnCancel = QPushButton("❌ Kapat")
        
        btnAdd.setObjectName("btnPrimary"); btnDel.setObjectName("btnDanger")
        btnOk.setObjectName("btnAction"); btnCancel.setObjectName("btnStandard")

        hb.addWidget(btnOk); hb.addWidget(btnCancel); root.addLayout(hb)
        btnAdd.clicked.connect(lambda: self._insert_row())
        btnDel.clicked.connect(self._del_rows)
        btnOk.clicked.connect(self._save)
        btnCancel.clicked.connect(self.close)

        self._apply_modern_visuals()
        self._load()

    def _apply_modern_visuals(self):
        self.setStyleSheet("""
            QDialog, QWidget { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; font-size: 13px; background-color: #f8fafc; color: #1e293b; }
            QLabel { font-weight: 500; color: #334155; }
            QTableWidget { border: 1px solid #e2e8f0; border-radius: 8px; background: white; gridline-color: #f1f5f9; }
            QHeaderView::section { background-color: #f1f5f9; padding: 6px; border: none; border-bottom: 2px solid #e2e8f0; font-weight: 600; color: #475569; }
            
            /* Buttons */
            QPushButton { border-radius: 6px; padding: 6px 12px; font-weight: 600; background: white; border: 1px solid #cbd5e1; color: #475569; }
            QPushButton:hover { background: #f1f5f9; border-color: #94a3b8; }
            
            QPushButton#btnAction { background-color: #059669; color: white; border: 1px solid #047857; }
            QPushButton#btnAction:hover { background-color: #047857; }
            
            QPushButton#btnPrimary { background-color: #2563eb; color: white; border: 1px solid #1d4ed8; }
            QPushButton#btnPrimary:hover { background-color: #1d4ed8; }
            
            QPushButton#btnDanger { background-color: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }
            QPushButton#btnDanger:hover { background-color: #fecaca; }

            QPushButton#btnStandard { background-color: #ffffff; color: #374151; border: 1px solid #d1d5db; }
            QPushButton#btnStandard:hover { background-color: #f3f4f6; }
        """)

    def _insert_row(self, key: str = "", val: str = ""):
        i = self.tbl.rowCount()
        self.tbl.insertRow(i)
        self.tbl.setRowHeight(i, EditorDelegate._ROW_H)
        self.tbl.setItem(i, 0, QTableWidgetItem(key))
        self.tbl.setItem(i, 1, QTableWidgetItem(val))
        # Düzenlemeyi rahat başlat
        self.tbl.setCurrentCell(i, 0 if key else 0)
        self.tbl.editItem(self.tbl.item(i, 0 if key else 0))

    def _quick_add(self, key: str):
        # varsa odaklan, yoksa ekle
        for r in range(self.tbl.rowCount()):
            it = self.tbl.item(r, 0)
            if it and (it.text().strip().upper() == key.upper()):
                self.tbl.setCurrentCell(r, 1)
                self.tbl.editItem(self.tbl.item(r, 1))
                return
        self._insert_row(key, dict(self.QUICK_KEYS).get(key, "—"))

    def _load(self):
        _ensure_table_kitap_ozellik(self.con)
        rows = self.con.execute(
            "SELECT key, val FROM kitap_ozellik WHERE ders=? AND kitap_ad=? ORDER BY key",
            (self.ders, self.kitap)
        ).fetchall()
        self.tbl.setRowCount(0)
        for r in rows:
            k = r["key"] if hasattr(r, "keys") else r[0]
            v = r["val"] if hasattr(r, "keys") else r[1]
            self._insert_row(k or "", v or "")

    def _del_rows(self):
        sel = self.tbl.selectionModel().selectedRows()
        for idx in sorted((i.row() for i in sel), reverse=True):
            self.tbl.removeRow(idx)

    def _save(self):
        _ensure_table_kitap_ozellik(self.con)
        self.con.execute("DELETE FROM kitap_ozellik WHERE ders=? AND kitap_ad=?", (self.ders, self.kitap))
        rows = []
        for i in range(self.tbl.rowCount()):
            k = (self.tbl.item(i, 0).text() if self.tbl.item(i,0) else "").strip()
            v = (self.tbl.item(i, 1).text() if self.tbl.item(i,1) else "").strip()
            if k:
                rows.append((self.ders, self.kitap, k, v))
        if rows:
            self.con.executemany("INSERT OR REPLACE INTO kitap_ozellik(ders, kitap_ad, key, val) VALUES (?,?,?,?)", rows)
        self.con.commit()
        self.accept()


# =========================
#  Detay Dialogu
# =========================
class KitapDetayDialog(QDialog):
    _DONE_VALUES = {"1","true","evet","✓","✔","x","bitti","tamam","yapıldı","yapildi"}
    _STATUS_COLS = ("durum","tamam","bitirildi","yapildi","yuzde","progress","tamamlanan_yuzde")

    def __init__(self, con, ders: str, kitaplar: list[str], ebeveyn=None):
        super().__init__(ebeveyn)
        self.setWindowTitle("Kitap Detayı")
        self.resize(820, 560)
        self.con, self.ders, self.kitaplar = con, ders, kitaplar

        root = QVBoxLayout(self)
        self.lblTitle = QLabel(f"<b>Ders:</b> {ders}  —  <b>Kitap:</b> {', '.join(kitaplar)}"); root.addWidget(self.lblTitle)
        self.lblSummary = QLabel("Özet yükleniyor…"); root.addWidget(self.lblSummary)

        self.table = QTableWidget(0, 4, self)
        self.table.setHorizontalHeaderLabels(["Öğrenci", "Kitap", "Kayıt Tarihi", "İlerleme %"])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False); self.table.setAlternatingRowColors(True)
        root.addWidget(self.table, 1)

        self._apply_modern_visuals()
        self._load()

    def _apply_modern_visuals(self):
        self.setStyleSheet("""
            QDialog, QWidget { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; font-size: 13px; background-color: #f8fafc; color: #1e293b; }
            QLabel { font-weight: 500; color: #334155; }
            QTableWidget { border: 1px solid #e2e8f0; border-radius: 8px; background: white; gridline-color: #f1f5f9; }
            QHeaderView::section { background-color: #f1f5f9; padding: 6px; border: none; border-bottom: 2px solid #e2e8f0; font-weight: 600; color: #475569; }
        """)

    @staticmethod
    def _get(row, *names):
        if hasattr(row, "keys"):
            for n in names:
                if n in row.keys(): return row[n]
        for n in names:
            try: return row[n]
            except Exception: pass
        return None

    def _total_topics(self, ders: str, kitap: str) -> int:
        try:
            q = "SELECT COUNT(DISTINCT konu) FROM konu_istatistik WHERE ders=? AND kitap_ad=?"
            val = self.con.execute(q, (ders, kitap)).fetchone()
            c = val[0] if val else 0
            return int(c or 0)
        except Exception:
            return 0

    def _student_done(self, ogr_id: int, ders: str, kitap: str) -> int:
        try:
            for col in ("yuzde","progress","tamamlanan_yuzde"):
                try:
                    q = f"SELECT MAX({col}) FROM konu_istatistik WHERE ogrenci_id=? AND ders=? AND kitap_ad=?"
                    row = self.con.execute(q, (ogr_id, ders, kitap)).fetchone()
                    if row and row[0] is not None:
                        return -1 * float(row[0])  # doğrudan yüzde sinyali
                except Exception:
                    pass
            where_done = " OR ".join([f"LOWER(CAST({c} AS TEXT)) IN ({','.join('?'*len(self._DONE_VALUES))})"
                                      for c in self._STATUS_COLS])
            params = tuple([ogr_id, ders, kitap] + list(self._DONE_VALUES)*len(self._STATUS_COLS))
            q = f"SELECT COUNT(*) FROM konu_istatistik WHERE ogrenci_id=? AND ders=? AND kitap_ad=? AND ({where_done})"
            row = self.con.execute(q, params).fetchone()
            return int(row[0] or 0)
        except Exception:
            return 0

    def _load(self):
        ph = ",".join("?" for _ in self.kitaplar)
        rows = self.con.execute(
            f"SELECT * FROM ogrenci_kitap WHERE ders=? AND kitap_ad IN ({ph})",
            (self.ders, *self.kitaplar)
        ).fetchall()

        items, percents = [], []
        for r in rows:
            ogr_id = self._get(r, "ogrenci_id","ogr_id","ogrenci")
            kitap  = self._get(r, "kitap_ad","kitap") or ""
            tarih  = self._get(r, "eklenme_tarih","tarih","created_at","kayit_tarih") or ""
            # öğrenci adı
            ad, soy = "", ""
            if ogr_id:
                s = self.con.execute("SELECT ad, soyad FROM ogrenci WHERE id=?", (ogr_id,)).fetchone()
                if s:
                    ad = self._get(s,"ad") or ""; soy = self._get(s,"soyad") or ""
            name = (ad+" "+soy).strip() or f"Öğrenci #{ogr_id or '-'}"

            total = self._total_topics(self.ders, kitap)
            done = self._student_done(int(ogr_id or 0), self.ders, kitap) if ogr_id else 0
            if isinstance(done, float) and done < 0:
                pct = round(-done, 1)
            elif total > 0:
                pct = round(100.0 * float(done) / float(total), 1)
            else:
                pct = None

            items.append({"ogr": name, "kitap": kitap, "tarih": tarih or "—", "pct": pct})
            if pct is not None: percents.append(pct)

        self.table.setRowCount(len(items))
        for i, it in enumerate(items):
            self.table.setItem(i, 0, QTableWidgetItem(it["ogr"]))
            self.table.setItem(i, 1, QTableWidgetItem(it["kitap"]))
            self.table.setItem(i, 2, QTableWidgetItem(it["tarih"]))
            self.table.setItem(i, 3, QTableWidgetItem("—" if it["pct"] is None else f"{it['pct']}"))

        cnt = len(items)
        if percents:
            avg = round(sum(percents)/len(percents), 1); mn = round(min(percents),1); mx = round(max(percents),1)
            self.lblSummary.setText(f"<b>Toplam öğrenci:</b> {cnt}  •  <b>Ortalama %:</b> {avg}  •  <b>Min–Maks:</b> {mn}–{mx}")
        else:
            self.lblSummary.setText(f"<b>Toplam öğrenci:</b> {cnt}  •  <i>İlerleme verisi bulunamadı</i>")


# =========================
#  Kitap Silme Seçim Dialogu
# =========================
class KitapSilmeSecimDialog(QDialog):
    """
    Kitap silme seçenekleri onay penceresi:
    - Kitap havuzundan ve sistemden tamamen silme (ve opsiyonel olarak bekleyen ödevleri temizleme)
    - Sadece seçili öğrenciden kaldırma
    """
    def __init__(self, kitap_adlari: list[str], ders: str, has_students: bool = True, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kitap Silme Onayı")
        self.resize(500, 390)
        self.setModal(True)
        self._kitaplar = kitap_adlari
        self._ders = ders
        self._has_students = has_students
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(14)

        # Header
        h_row = QHBoxLayout()
        lbl_icon = QLabel("🗑️")
        lbl_icon.setStyleSheet("font-size: 32px;")
        
        v_head = QVBoxLayout()
        lbl_t = QLabel("Kitap Silme Seçenekleri")
        lbl_t.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e293b;")
        lbl_sub = QLabel(f"Ders: <b>{self._ders}</b>  •  Seçilen: <b>{len(self._kitaplar)} Kitap</b>")
        lbl_sub.setStyleSheet("font-size: 12px; color: #64748b;")
        v_head.addWidget(lbl_t)
        v_head.addWidget(lbl_sub)
        h_row.addWidget(lbl_icon)
        h_row.addSpacing(10)
        h_row.addLayout(v_head)
        h_row.addStretch(1)
        lay.addLayout(h_row)

        # Kitap Önizleme Kutusu
        fr_preview = QFrame()
        fr_preview.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;")
        lp = QVBoxLayout(fr_preview)
        lp.setContentsMargins(12, 10, 12, 10)
        lp.setSpacing(4)
        
        lbl_p_title = QLabel("İşlem Yapılacak Kitaplar:")
        lbl_p_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #475569;")
        lp.addWidget(lbl_p_title)

        max_show = 4
        shown = self._kitaplar[:max_show]
        for k in shown:
            l_item = QLabel(f"• {k}")
            l_item.setStyleSheet("font-size: 12px; color: #1e293b;")
            lp.addWidget(l_item)
        if len(self._kitaplar) > max_show:
            l_more = QLabel(f"... ve {len(self._kitaplar) - max_show} kitap daha")
            l_more.setStyleSheet("font-size: 11px; color: #94a3b8; font-style: italic;")
            lp.addWidget(l_more)
        lay.addWidget(fr_preview)

        # Seçenekler Grubu
        grp_opts = QGroupBox("Silme Kapsamı")
        grp_opts.setStyleSheet("QGroupBox { font-weight: bold; color: #334155; }")
        l_opts = QVBoxLayout(grp_opts)
        l_opts.setSpacing(8)

        # Seçenek 1: Sistemden ve Havuzdan Tamamen Sil (Varsayılan)
        self.radHavuz = QRadioButton("🗑️ Kitap Havuzundan ve Sistemden Tamamen Sil (Tavsiye Edilen)")
        self.radHavuz.setChecked(True)
        self.radHavuz.setStyleSheet("font-weight: 600; color: #b91c1c;")
        lbl_h_info = QLabel("Kitabı veri tabanından, havuzdan ve tüm öğrenci atamalarından kalıcı olarak siler.")
        lbl_h_info.setStyleSheet("color: #64748b; font-size: 11px; margin-left: 22px;")
        
        self.chkOdevleriSil = QCheckBox("Bu kitaba ait atanmış henüz tamamlanmamış bekleyen ödev kayıtlarını da temizle")
        self.chkOdevleriSil.setChecked(True)
        self.chkOdevleriSil.setStyleSheet("color: #475569; font-size: 11px; margin-left: 22px;")
        
        l_opts.addWidget(self.radHavuz)
        l_opts.addWidget(lbl_h_info)
        l_opts.addWidget(self.chkOdevleriSil)

        # Seçenek 2: Sadece Seçili Öğrenciden Kaldır
        self.radOgrenci = QRadioButton("👤 Sadece Seçili Öğrenci(ler)den Kaldır")
        self.radOgrenci.setStyleSheet("font-weight: 600; color: #1e293b;")
        lbl_o_info = QLabel("Kitap havuzda kalmaya devam eder, yalnızca seçili öğrencilerin zimmetinden kaldırılır.")
        lbl_o_info.setStyleSheet("color: #64748b; font-size: 11px; margin-left: 22px;")
        
        if not self._has_students:
            self.radOgrenci.setEnabled(False)
            lbl_o_info.setText("Hedef öğrenci seçilmediği için bu seçenek pasif.")

        l_opts.addWidget(self.radOgrenci)
        l_opts.addWidget(lbl_o_info)
        lay.addWidget(grp_opts)

        # Butonlar
        btn_bar = QHBoxLayout()
        btn_bar.addStretch(1)
        
        self.btnCancel = QPushButton("Vazgeç")
        self.btnCancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnCancel.setStyleSheet("padding: 7px 16px; border: 1px solid #cbd5e1; border-radius: 6px; background: #fff;")
        self.btnCancel.clicked.connect(self.reject)
        
        self.btnConfirm = QPushButton("🗑️ Silme İşlemini Onayla")
        self.btnConfirm.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnConfirm.setStyleSheet("""
            QPushButton {
                background-color: #dc2626; color: white; border: none;
                border-radius: 6px; padding: 7px 18px; font-weight: bold;
            }
            QPushButton:hover { background-color: #b91c1c; }
        """)
        self.btnConfirm.clicked.connect(self.accept)
        
        btn_bar.addWidget(self.btnCancel)
        btn_bar.addSpacing(10)
        btn_bar.addWidget(self.btnConfirm)
        lay.addLayout(btn_bar)

    def get_mode(self) -> str:
        return "havuz" if self.radHavuz.isChecked() else "ogrenci"

    def odevleri_temizle(self) -> bool:
        return self.chkOdevleriSil.isChecked() if self.radHavuz.isChecked() else False


# =========================
#  Ana Dialog
# =========================
class KitapDialog(QDialog):
    """Kitap Ekle / Sil penceresi (aktif derse göre açılır)."""
    def __init__(self, ogrenci_provider, aktif_ders, ebeveyn=None):
        super().__init__(ebeveyn)
        self.setWindowTitle("Kitap Ekle / Sil")
        self.ogrenci_provider = ogrenci_provider

        # Aktif ders temizleme & eşleme (rozet, emoji, sayı temizleme)
        clean_ders = str(aktif_ders or "").strip()
        clean_ders = re.sub(r'[🔴🟡]\s*\d+', '', clean_ders)
        clean_ders = re.sub(r'\(?\s*%\s*\d+\s*\)?', '', clean_ders)
        clean_ders = re.sub(r'[^\w\s]', '', clean_ders, flags=re.UNICODE).strip().lower().replace(" ", "_")

        matched_ders = None
        for d in db.DERS_TABLOLARI:
            if d.lower() == clean_ders or d.lower().replace("_", "") == clean_ders.replace("_", ""):
                matched_ders = d
                break
        if not matched_ders:
            for d in db.DERS_TABLOLARI:
                if d.lower() in clean_ders or clean_ders in d.lower():
                    matched_ders = d
                    break
        self.aktif_ders = matched_ders if matched_ders else (db.DERS_TABLOLARI[0] if db.DERS_TABLOLARI else clean_ders)
        self.son_ders = self.aktif_ders
        self._degisiklik_oldu = False

        self.settings = QSettings("EduApps", "YKS_LGS_HomeworkManager")
        self._density = self.settings.value("kitapdlg/havuz_density", "orta")
        self._check_mode = self.settings.value("kitapdlg/havuz_check_mode", "1") == "1"

        self._first_show = True

        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            w = min(940, int(avail.width() * 0.90))
            h = min(660, int(avail.height() * 0.88))
            self.resize(w, h)
        else:
            self.resize(900, 620)
        self.setMinimumSize(700, 500)

        self._build_ui()
        self._apply_styles() # Old style method
        self._apply_modern_visuals() # New modern visuals
        self._build_context_menus()

        self._ogr_listesini_yukle()
        self._yenile_havuz()
        self._apply_havuz_mode()
        self._toggle_ogr_panel()

        self._restore_split_sizes()
        self.split.splitterMoved.connect(lambda *_: self._save_split_sizes())

        # Şema güvence
        con = db.get_conn()
        _ensure_column(con, "ogrenci_kitap", "eklenme_tarih", "TEXT")
        _ensure_table_kitap_ozellik(con)

    # ------------- Toast helper -------------
    def _toast(self, text: str, kind: str = "info", msec: int = 2400):
        _Toast(self, text, kind=kind, msec=msec)

    # ---------------- UI ----------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        # --- Kompakt Birleşik Üst Bar (Header & Ders Seçimi) ---
        top_bar = QFrame()
        top_bar.setStyleSheet("""
            QFrame {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
        """)
        top_lay = QHBoxLayout(top_bar)
        top_lay.setContentsMargins(12, 8, 12, 8)
        top_lay.setSpacing(12)

        lbl_icon = QLabel("📚")
        lbl_icon.setStyleSheet("font-size: 24px;")
        top_lay.addWidget(lbl_icon)

        v_head = QVBoxLayout()
        v_head.setSpacing(2)
        lbl_title = QLabel("Kitap Ekle / Sil & Havuz Yönetimi")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #1e293b;")
        lbl_desc = QLabel("Öğrencilere kitap atayın, kaldırın veya ders havuzundaki kitapları düzenleyin.")
        lbl_desc.setStyleSheet("color: #64748b; font-size: 11px;")
        v_head.addWidget(lbl_title)
        v_head.addWidget(lbl_desc)
        top_lay.addLayout(v_head)

        top_lay.addStretch(1)

        # Ders Seçimi aynı barda sağda
        top_lay.addWidget(QLabel("<b>Ders:</b>"))
        self.cmbDers = QComboBox()
        self.cmbDers.addItems(db.DERS_TABLOLARI)
        self.cmbDers.setCurrentText(self.aktif_ders)
        self.cmbDers.setMinimumWidth(160)
        self.cmbDers.currentTextChanged.connect(self._yenile_havuz)
        top_lay.addWidget(self.cmbDers)

        root.addWidget(top_bar)

        # --- Ana Splitter ---
        self.split = QSplitter(Qt.Orientation.Horizontal)
        self.split.setChildrenCollapsible(False)
        self.split.setHandleWidth(8)
        root.addWidget(self.split, 1)

        # === SOL PANEL ===
        self.left = QWidget(); l_main = QVBoxLayout(self.left)
        l_main.setContentsMargins(0, 0, 5, 0)
        l_main.setSpacing(8)

        # 1. Kitap Girişi (Kompakt)
        grp_input = QGroupBox("Yeni Kitap Girişi")
        grp_input.setStyleSheet("QGroupBox { font-weight: bold; color: #334155; }")
        l_in = QVBoxLayout(grp_input)
        l_in.setContentsMargins(8, 8, 8, 8)
        l_in.setSpacing(4)

        row_tools = QHBoxLayout()
        row_tools.addWidget(QLabel("Kitap Adları:"))
        row_tools.addStretch(1)
        self.btnOpenProps = QToolButton(self.left)
        self.btnOpenProps.setText("⚙️ Özellikler")
        self.btnOpenProps.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnOpenProps.setStyleSheet("border:none; color:#2563eb; font-weight:bold;")
        self.btnOpenProps.clicked.connect(self._open_props_picker)
        row_tools.addWidget(self.btnOpenProps)
        l_in.addLayout(row_tools)

        self.txtKitaplar = QTextEdit()
        self.txtKitaplar.setPlaceholderText("Örn: 345 TYT Matematik (Her satıra bir kitap)")
        self.txtKitaplar.setMaximumHeight(50)
        l_in.addWidget(self.txtKitaplar)
        l_main.addWidget(grp_input, 0)
        
        # 2. Kitap Havuzu
        grp_pool = QGroupBox("Kitap Havuzu")
        grp_pool.setStyleSheet("QGroupBox { font-weight: bold; color: #334155; }")
        l_pool = QVBoxLayout(grp_pool)

        # Arama ve Sayaç Satırı
        row_pool_tools = QHBoxLayout()
        self.txtHavuzAra = QLineEdit()
        self.txtHavuzAra.setPlaceholderText("🔍 Havuzda kitap ara...")
        self.txtHavuzAra.setClearButtonEnabled(True)
        self.txtHavuzAra.textChanged.connect(self._filtrele_havuz)

        self.lblHavuzSayisi = QLabel("0 kitap")
        self.lblHavuzSayisi.setStyleSheet("color: #2563eb; font-size: 11px; font-weight: bold; padding: 2px 6px; background: #eff6ff; border-radius: 6px; border: 1px solid #bfdbfe;")

        row_pool_tools.addWidget(self.txtHavuzAra, 1)
        row_pool_tools.addWidget(self.lblHavuzSayisi)
        l_pool.addLayout(row_pool_tools)

        self.lstHavuz = QListWidget()
        self.lstHavuz.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.lstHavuz.setAlternatingRowColors(True)
        self.lstHavuz.setMinimumHeight(240)
        l_pool.addWidget(self.lstHavuz, 1)

        # Havuz Hızlı Seçim & Silme Butonları
        row_havuz_sel = QHBoxLayout()
        self.btnHavuzTumuSec = QPushButton("Tümünü Seç")
        self.btnHavuzTumuSec.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnHavuzTumuSec.setStyleSheet("padding: 3px 8px; font-size: 11px;")
        self.btnHavuzTumuSec.clicked.connect(lambda: self._havuz_check_all(True))

        self.btnHavuzTemizle = QPushButton("Temizle")
        self.btnHavuzTemizle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnHavuzTemizle.setStyleSheet("padding: 3px 8px; font-size: 11px;")
        self.btnHavuzTemizle.clicked.connect(lambda: self._havuz_check_all(False))

        self.btnHavuzdanSil = QPushButton("🗑️ Havuzdan Sil")
        self.btnHavuzdanSil.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnHavuzdanSil.setStyleSheet("padding: 3px 8px; font-size: 11px; color: #dc2626; border-color: #fecaca; background: #fef2f2;")
        self.btnHavuzdanSil.clicked.connect(self._sil)

        row_havuz_sel.addWidget(self.btnHavuzTumuSec)
        row_havuz_sel.addWidget(self.btnHavuzTemizle)
        row_havuz_sel.addStretch(1)
        row_havuz_sel.addWidget(self.btnHavuzdanSil)
        l_pool.addLayout(row_havuz_sel)

        l_main.addWidget(grp_pool, 3) # Dominant esnek alan

        # 3. Hedef Seçimi
        fr_target = QFrame()
        fr_target.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px;")
        l_target = QHBoxLayout(fr_target)
        l_target.setContentsMargins(10, 5, 10, 5)
        l_target.addWidget(QLabel("Hedef:"))
        self.radTek = QRadioButton("Seçili Öğrenci")
        self.radSecilen = QRadioButton("Seçilenler")
        self.radTum = QRadioButton("Tümü")
        self.radTek.setChecked(True)
        self._pillGroup = QButtonGroup(self)
        for rb in (self.radTek, self.radSecilen, self.radTum):
            self._pillGroup.addButton(rb)
            l_target.addWidget(rb)
        l_target.addStretch(1)
        l_main.addWidget(fr_target)

        # === SAĞ PANEL ===
        self.right = QWidget(); r_main = QVBoxLayout(self.right)
        r_main.setContentsMargins(5, 0, 0, 0)
        
        grp_users = QGroupBox("Öğrenci Listesi")
        grp_users.setStyleSheet("QGroupBox { font-weight: bold; color: #334155; }")
        r_lay = QVBoxLayout(grp_users)
        
        # Arama ve Filtre
        row_filter = QHBoxLayout()
        self.txtOgrAra = QLineEdit()
        self.txtOgrAra.setPlaceholderText("🔍 Öğrenci ara...")
        self.txtOgrAra.textChanged.connect(self._apply_filter)
        
        self.cmbGrupFilter = QComboBox()
        self.cmbGrupFilter.setMinimumWidth(120)
        
        row_filter.addWidget(self.txtOgrAra)
        row_filter.addWidget(self.cmbGrupFilter)
        r_lay.addLayout(row_filter)
        
        # Liste
        self.lstOgr = QListWidget()
        self.lstOgr.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.lstOgr.setAlternatingRowColors(True)
        self.lstOgr.setMinimumHeight(240)
        self.lstOgr.itemClicked.connect(self._on_ogr_item_clicked)
        r_lay.addWidget(self.lstOgr, 1)
        
        # Seçim Butonları (ListWidget altına ufak)
        row_sel_btns = QHBoxLayout()
        self.btnTumunuSec = QPushButton("Tümünü Seç"); self.btnTumunuSec.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnTumunuKaldir = QPushButton("Temizle"); self.btnTumunuKaldir.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Ufak boyut
        self.btnTumunuSec.setStyleSheet("padding: 4px 8px; font-size: 11px;")
        self.btnTumunuKaldir.setStyleSheet("padding: 4px 8px; font-size: 11px;")
        
        row_sel_btns.addStretch(1)
        row_sel_btns.addWidget(self.btnTumunuSec)
        row_sel_btns.addWidget(self.btnTumunuKaldir)
        r_lay.addLayout(row_sel_btns)
        
        r_main.addWidget(grp_users)

        self.split.addWidget(self.left)
        self.split.addWidget(self.right)
        
        # --- Alt Aksiyon Butonları ---
        action_bar = QHBoxLayout()
        
        self.btnEkle = QPushButton("✅ EKLE")
        self.btnEkle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnEkle.setMinimumHeight(40)
        
        self.btnSil = QPushButton("🗑️ SİL")
        self.btnSil.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnSil.setMinimumHeight(40)

        # ID atamaları (StyleSheet için)
        self.btnEkle.setObjectName("btnAction")
        self.btnSil.setObjectName("btnDanger")
        
        action_bar.addStretch(1)
        action_bar.addWidget(self.btnSil, 1) # Sola yasla demiyelim, stretch ile orantılı olsun
        action_bar.addSpacing(20)
        action_bar.addWidget(self.btnEkle, 2) # Ekle butonu daha büyük
        
        root.addLayout(action_bar)

        # Filtreleri doldur
        self._grup_opsiyonlari = [
            "Tüm Öğrenciler","Boş Olanlar","YKS-Sayısal","YKS-Say-Mezun","YKS-Say-12.sınıf",
            "YKS-EA","YKS-SÖZ","11.SINIF","mezun-say","mezun-ea","mezun-söz","12-say","12-ea","12-söz",
            "11-say","11-ea","11-söz","10.sınıf","9.sınıf","8.sınıf","7.sınıf","6.sınıf",
        ]
        self.cmbGrupFilter.addItems(self._grup_opsiyonlari)
        self.cmbGrupFilter.setCurrentIndex(0)
        self.cmbGrupFilter.currentIndexChanged.connect(self._apply_filter)

        # Sinyaller
        self.btnTumunuSec.clicked.connect(lambda: self._ogr_check_all(True))
        self.btnTumunuKaldir.clicked.connect(lambda: self._ogr_check_all(False))
        self.btnEkle.clicked.connect(self._ekle)
        self.btnSil.clicked.connect(self._sil)
        self.radSecilen.toggled.connect(self._toggle_ogr_panel)
        self.radTek.toggled.connect(self._toggle_ogr_panel)
        self.radTum.toggled.connect(self._toggle_ogr_panel)

    def showEvent(self, ev):
        super().showEvent(ev)
        if self._first_show:
            try:
                sizes = QSettings("EduApps","YKS_LGS_HomeworkManager").value("kitapdlg/split_sizes", None)
                if not (isinstance(sizes,list) and len(sizes)==2 and all(isinstance(x,int) for x in sizes)):
                    self.split.setSizes([420,760])
            except Exception:
                self.split.setSizes([420,760])
            self._apply_havuz_mode(); self._apply_density(); self._first_show = False

    def _apply_modern_visuals(self):
        # Inject modern styles similar to main app
        # Eski statik 'light' değerleri
        bg_dlg   = "#f9fafb"
        bg_btn   = "#f3f4f6"
        bg_hover = "#e5e7eb"
        fg_btn   = "#1f2937"
        bdr_btn  = "#d1d5db"
        fg_input = "#111827"
        bg_input = "#ffffff"
        bdr_input = "#d1d5db"
        hdr_bg = "#f9fafb"
        hdr_bdr = "#e5e7eb"
        
        self.setStyleSheet(self.styleSheet() + f"""
            QWidget {{ font-family: 'Segoe UI', sans-serif; font-size: 13px; }}
            QDialog {{ background-color: {bg_dlg}; color: {fg_input}; }}
            QLabel {{ color: {fg_input}; }}

            QPushButton {{ 
                border-radius: 6px; padding: 6px 16px; font-weight: 600;
                background-color: {bg_btn}; border: 1px solid {bdr_btn}; color: {fg_btn};
            }}
            QPushButton:hover {{ background-color: {bg_hover}; }}

            QPushButton#btnAction {{ background-color: #059669; color: white; border: none; }}
            QPushButton#btnAction:hover {{ background-color: #047857; }}

            QPushButton#btnPrimary {{ background-color: #2563eb; color: white; border: none; }}
            QPushButton#btnPrimary:hover {{ background-color: #1d4ed8; }}

            QPushButton#btnDanger {{ background-color: #fee2e2; color: #dc2626; border: 1px solid #fecaca; }}
            QPushButton#btnDanger:hover {{ background-color: #fecaca; }}

            QPushButton#btnStandard {{ background-color: {bg_input}; color: {fg_input}; border: 1px solid {bdr_btn}; }}
            QPushButton#btnStandard:hover {{ background-color: {bg_btn}; }}
            
            QLineEdit, QTextEdit, QListWidget, QTableWidget {{
                border: 1px solid {bdr_input}; border-radius: 6px; padding: 4px; 
                background: {bg_input}; color: {fg_input};
            }}
            QLineEdit:focus, QTextEdit:focus, QListWidget:focus, QTableWidget:focus {{
                border-color: #2563eb;
            }}
            QHeaderView::section {{ 
                background-color: {hdr_bg}; padding: 4px; border: none; 
                border-bottom: 2px solid {hdr_bdr}; font-weight: bold; color: {fg_input};
            }}
            QGroupBox {{ color: {fg_input}; }}
        """)

    # ---------- Stil ----------
    def _apply_styles(self):
        self.split.setStyleSheet("""
            QSplitter::handle { background: rgba(0,0,0,90); border:1px solid rgba(0,0,0,140);
                                margin:4px 0; border-radius:3px; }
            QSplitter::handle:hover { background: rgba(0,120,215,170); }
            QSplitter::handle:pressed { background: rgba(0,120,215,220); }
        """)
        list_qss = """
            QListWidget { border:1px solid #e5e7eb; border-radius:8px; padding:4px; background:#fff; }
            QListWidget::item { padding:5px 8px; border-radius:4px; }
            QListWidget::item:selected { background:#eff6ff; color:#1e40af; font-weight:600; }
            QListWidget::item:hover:!selected { background:#f8fafc; }
            QListWidget::indicator {
                width: 16px;
                height: 16px;
                border: 1.5px solid #94a3b8;
                border-radius: 3.5px;
                background-color: #ffffff;
            }
            QListWidget::indicator:hover {
                border-color: #2563eb;
            }
            QListWidget::indicator:checked {
                background-color: #2563eb;
                border: 1.5px solid #1d4ed8;
                image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 16 16'><path fill='none' stroke='white' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round' d='M3.2 8.2l3.4 3.4L13 4.2'/></svg>");
            }
        """
        self.lstHavuz.setStyleSheet(list_qss); self.lstOgr.setStyleSheet(list_qss)
        text_qss = "QTextEdit, QLineEdit { border:1px solid #e5e7eb; border-radius:8px; padding:6px; background:#fff; }"
        self.txtKitaplar.setStyleSheet(text_qss); self.txtOgrAra.setStyleSheet(text_qss)
        self.setStyleSheet(self.styleSheet()+"""
            QMenu { border:1px solid #e5e7eb; border-radius:8px; padding:4px; background:#fff; }
            QMenu::item { padding:6px 14px; border-radius:6px; }
            QMenu::item:selected { background:#e8f0fe; color:#111827; }
            QMenu::separator { height:1px; background:#e5e7eb; margin:6px 8px; }
            QRadioButton { background:#f3f4f6; color:#111827; border:1px solid #e5e7eb; border-radius:14px;
                           padding:6px 12px; margin-right:6px; }
            QRadioButton::indicator { width:0; height:0; }
            QRadioButton:hover { background:#eef2ff; }
            QRadioButton:checked { background:#dbeafe; color:#1e40af; border-color:#2563eb; font-weight:bold; }
        """)
        self._apply_density()

    def _apply_density(self):
        pad = {"sıkı":3, "orta":6, "geniş":10}.get(self._density,6)
        self.lstHavuz.setStyleSheet(self.lstHavuz.styleSheet()+f"\nQListWidget::item{{padding:{pad}px 8px;}}\n")

    # ---------- Sağ tık menüleri ----------
    def _build_context_menus(self):
        self.lstHavuz.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.lstHavuz.customContextMenuRequested.connect(self._show_havuz_menu)
        self.lstOgr.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.lstOgr.customContextMenuRequested.connect(self._show_ogr_menu)
        self.txtKitaplar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.txtKitaplar.customContextMenuRequested.connect(self._show_text_menu)

    def _show_havuz_menu(self, pos: QPoint):
        menu = QMenu(self)
        act_add_to_text = menu.addAction("📝 Seçili kitapları metne ekle")
        act_copy = menu.addAction("📋 Kopyala")
        act_del_pool = menu.addAction("🗑️ Seçiliyi Havuzdan / Sistemden Sil")
        menu.addSeparator()
        act_detail = menu.addAction("ℹ️ Kitap Detayı…")
        act_props  = menu.addAction("⚙️ Kitap Özellikleri…")
        menu.addSeparator()
        density = menu.addMenu("👁️ Görünüm (satır aralığı)")
        d_siki = density.addAction("Sıkı"); d_orta = density.addAction("Orta"); d_genis = density.addAction("Geniş")
        sel_menu = menu.addMenu("🖱️ Seçim modu"); m_check = sel_menu.addAction("Onay kutulu"); m_plain = sel_menu.addAction("Normal (kutusuz)")
        if self._check_mode: m_check.setCheckable(True); m_check.setChecked(True)
        else: m_plain.setCheckable(True); m_plain.setChecked(True)
        menu.addSeparator()
        act_check_all = menu.addAction("✅ Hepsini işaretle")
        act_uncheck_all = menu.addAction("🔳 İşaretleri kaldır")
        act_invert = menu.addAction("🔄 Ters çevir")

        chosen = menu.exec(self.lstHavuz.mapToGlobal(pos))
        if not chosen: return

        if chosen in (d_siki,d_orta,d_genis):
            self._density = "sıkı" if chosen is d_siki else "geniş" if chosen is d_genis else "orta"
            self.settings.setValue("kitapdlg/havuz_density", self._density); self._apply_density(); return
        if chosen in (m_check,m_plain):
            self._check_mode = (chosen is m_check)
            self.settings.setValue("kitapdlg/havuz_check_mode", "1" if self._check_mode else "0")
            self._apply_havuz_mode(); return
        if chosen is act_add_to_text: self._append_selected_havuz_to_text(); return
        if chosen is act_copy: self._copy_selected_havuz(); return
        if chosen is act_del_pool: self._sil(); return

        if chosen is act_detail:
            kitaplar = self._selected_books_from_pool(pos)
            if not kitaplar: self._toast("Detay için en az bir kitap seçin.","warn"); return
            con = db.get_conn(); dlg = KitapDetayDialog(con, self.cmbDers.currentText(), kitaplar, self); dlg.exec(); return

        if chosen is act_props:
            kitaplar = self._selected_books_from_pool(pos)
            if not kitaplar: self._toast("Özellik düzenlemek için bir kitap seçin.","warn"); return
            con = db.get_conn()
            for k in kitaplar:
                _ensure_table_kitap_ozellik(con)
                dlg = KitapOzellikDialog(con, self.cmbDers.currentText(), k, self); dlg.exec()
            return

        if chosen is act_check_all:
            for i in range(self.lstHavuz.count()): self.lstHavuz.item(i).setCheckState(Qt.CheckState.Checked)
        elif chosen is act_uncheck_all:
            for i in range(self.lstHavuz.count()): self.lstHavuz.item(i).setCheckState(Qt.CheckState.Unchecked)
        elif chosen is act_invert:
            for i in range(self.lstHavuz.count()):
                it = self.lstHavuz.item(i)
                it.setCheckState(Qt.CheckState.Unchecked if it.checkState()==Qt.CheckState.Checked else Qt.CheckState.Checked)

    def _selected_books_from_pool(self, pos: QPoint) -> list[str]:
        names = []
        it_at = self.lstHavuz.itemAt(pos)
        if it_at:
            names.append(self._pure_book_name(it_at.data(Qt.ItemDataRole.UserRole) or it_at.text()))
        for it in self.lstHavuz.selectedItems():
            nm = self._pure_book_name(it.data(Qt.ItemDataRole.UserRole) or it.text())
            if nm not in names: names.append(nm)
        if self._check_mode:
            marked = []
            for i in range(self.lstHavuz.count()):
                it = self.lstHavuz.item(i)
                if it.checkState()==Qt.CheckState.Checked:
                    nm = self._pure_book_name(it.data(Qt.ItemDataRole.UserRole) or it.text())
                    if nm not in marked: marked.append(nm)
            if marked: names = marked
        return [n for n in names if n]

    def _apply_havuz_mode(self):
        self.lstHavuz.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        for i in range(self.lstHavuz.count()):
            it = self.lstHavuz.item(i)
            flags = (it.flags() | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            if self._check_mode:
                flags |= Qt.ItemFlag.ItemIsUserCheckable
                if it.checkState() not in (Qt.CheckState.Checked, Qt.CheckState.Unchecked):
                    it.setCheckState(Qt.CheckState.Unchecked)
            else:
                flags &= ~Qt.ItemFlag.ItemIsUserCheckable
            it.setFlags(flags)

    def _show_ogr_menu(self, pos: QPoint):
        menu = QMenu(self)
        act_toggle = menu.addAction("Seçiliyi işaretle/işareti kaldır"); menu.addSeparator()
        act_check_all = menu.addAction("Tümünü işaretle"); act_uncheck_all = menu.addAction("Tüm işaretleri kaldır")
        act_invert = menu.addAction("Seçimi ters çevir")
        chosen = menu.exec(self.lstOgr.mapToGlobal(pos))
        if not chosen: return
        if chosen is act_toggle:
            it = self.lstOgr.itemAt(pos)
            if it:
                it.setCheckState(Qt.CheckState.Unchecked if it.checkState()==Qt.CheckState.Checked else Qt.CheckState.Checked)
        elif chosen is act_check_all: self._ogr_check_all(True)
        elif chosen is act_uncheck_all: self._ogr_check_all(False)
        elif chosen is act_invert:
            for i in range(self.lstOgr.count()):
                it = self.lstOgr.item(i)
                it.setCheckState(Qt.CheckState.Unchecked if it.checkState()==Qt.CheckState.Checked else Qt.CheckState.Checked)

    def _show_text_menu(self, pos: QPoint):
        menu = QMenu(self)
        act_paste = menu.addAction("Yapıştır"); act_clear = menu.addAction("Temizle"); menu.addSeparator()
        act_clean = menu.addAction("Satırları ayıkla (boşluk kırp & tekilleştir)"); act_sort = menu.addAction("Satırları sırala (A→Z)")
        chosen = menu.exec(self.txtKitaplar.mapToGlobal(pos))
        if not chosen: return
        if chosen is act_paste: self.txtKitaplar.paste()
        elif chosen is act_clear: self.txtKitaplar.clear()
        elif chosen is act_clean: self._normalize_text_lines()
        elif chosen is act_sort: self._sort_text_lines()

    # ---------- Yardımcılar ----------
    def _append_selected_havuz_to_text(self):
        items = self.lstHavuz.selectedItems()
        if not items: self._toast("Önce havuzdan kitap seçin.","warn"); return
        current = self.txtKitaplar.toPlainText().strip()
        lines = [self._pure_book_name(it.data(Qt.ItemDataRole.UserRole) or it.text())
                 for it in items if (it.text() or "").strip()]
        new_text = (current + ("\n" if current else "") + "\n".join(lines)).strip()
        self.txtKitaplar.setPlainText(new_text); self._toast("Seçili kitaplar metne eklendi.","ok")

    def _copy_selected_havuz(self):
        items = self.lstHavuz.selectedItems()
        if not items: self._toast("Kopyalamak için kitap seçin.","warn"); return
        txt = "\n".join([self._pure_book_name(it.data(Qt.ItemDataRole.UserRole) or it.text()) for it in items])
        QApplication.clipboard().setText(txt); self._toast("Kitap adları panoya kopyalandı.","ok")

    def _normalize_text_lines(self):
        raw = self.txtKitaplar.toPlainText(); parts = []
        for line in raw.splitlines():
            for p in line.split(","):
                p = self._pure_book_name(p);
                if p: parts.append(p)
        seen=set(); uniq=[]
        for p in parts:
            if p not in seen: seen.add(p); uniq.append(p)
        self.txtKitaplar.setPlainText("\n".join(uniq)); self._toast("Satırlar ayıklandı ve tekilleştirildi.","ok")

    def _sort_text_lines(self):
        raw = [self._pure_book_name(ln) for ln in self.txtKitaplar.toPlainText().splitlines() if ln.strip()]
        raw.sort(key=lambda s: s.lower()); self.txtKitaplar.setPlainText("\n".join(raw)); self._toast("Satırlar A→Z sıralandı.","ok")

    def _pure_book_name(self, s): return _BADGE_RE.sub("", (s or "").strip())

    def _save_split_sizes(self):
        try:
            QSettings("EduApps","YKS_LGS_HomeworkManager").setValue("kitapdlg/split_sizes", self.split.sizes())
        except Exception: pass

    def _restore_split_sizes(self):
        try:
            sizes = QSettings("EduApps","YKS_LGS_HomeworkManager").value("kitapdlg/split_sizes", None)
            if isinstance(sizes,list) and len(sizes)==2 and all(isinstance(x,int) for x in sizes): self.split.setSizes(sizes)
            else: self.split.setSizes([420,760])
        except Exception: self.split.setSizes([420,760])

    # ---------------- Veriler ----------------
    def _on_ogr_item_clicked(self, it: QListWidgetItem):
        it.setCheckState(Qt.CheckState.Unchecked if it.checkState()==Qt.CheckState.Checked else Qt.CheckState.Checked)

    def _ogr_listesini_yukle(self):
        _, ogrenciler = self.ogrenci_provider(); self._ogr_all = list(ogrenciler); self._apply_filter()

    def _apply_filter(self):
        search = (self.txtOgrAra.text() or "").strip().lower()
        _, ogrenciler = self.ogrenci_provider(); secim = (self.cmbGrupFilter.currentText() or "").strip()
        grup_map = {"YKS-Sayısal":{"mezun-say","12-say"},"YKS-Say-Mezun":{"mezun-say"},"YKS-Say-12.sınıf":{"12-say"},
                    "YKS-EA":{"mezun-ea","12-ea"},"YKS-SÖZ":{"mezun-söz","12-söz"},"11.SINIF":{"11-say","11-ea","11-söz"}}
        self.lstOgr.clear()

        def _f(row, name):
            try:
                if name in row.keys(): return row[name]
            except Exception: pass
            try: return row[name]
            except Exception: return None

        def _ok(row):
            ag = (_f(row,"alt_grup") or "").strip(); an = (_f(row,"ana_grup") or "").strip()
            if secim=="Tüm Öğrenciler": grp=True
            elif secim=="Boş Olanlar": grp = (not ag) and (not an)
            elif secim in grup_map: grp = ag in grup_map[secim]
            else: grp = (ag==secim)
            if not grp: return False
            if not search: return True
            return search in f"{(_f(row,'ad') or '')} {(_f(row,'soyad') or '')}".lower()

        for r in ogrenciler:
            if not _ok(r): continue
            ad = (_f(r,"ad") or "").strip(); soy = (_f(r,"soyad") or "").strip()
            etiket = (_f(r,"alt_grup") or "") or (_f(r,"ana_grup") or "")
            text = f"{ad} {soy} [{etiket}]"
            it = QListWidgetItem(text)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            it.setCheckState(Qt.CheckState.Unchecked)
            try: it.setData(Qt.ItemDataRole.UserRole, int(_f(r,"id") or 0))
            except Exception: pass
            self.lstOgr.addItem(it)

    def _toggle_ogr_panel(self):
        self.right.setEnabled(self.radSecilen.isChecked())

    def _book_usage_map(self):
        con = db.get_conn(); ders = self.cmbDers.currentText(); usage = {}
        try:
            rows = con.execute("SELECT kitap_ad, COUNT(*) AS cnt FROM ogrenci_kitap WHERE ders=? GROUP BY kitap_ad",(ders,)).fetchall()
            for r in rows:
                try: nm=r["kitap_ad"]; ct=r["cnt"]
                except Exception: nm,ct=r[0],r[1]
                usage[str(nm or "")]=int(ct or 0)
        except Exception:
            try: usage = dict(db.kitap_kullanim_sayisi(con, ders) or {})
            except Exception: usage = {}
        return usage

    def _filtrele_havuz(self):
        query = (self.txtHavuzAra.text() or "").strip().lower() if hasattr(self, "txtHavuzAra") else ""
        visible_cnt = 0
        total = self.lstHavuz.count()
        for i in range(total):
            it = self.lstHavuz.item(i)
            txt = (it.text() or "").lower()
            match = (query in txt) if query else True
            it.setHidden(not match)
            if match:
                visible_cnt += 1
        if hasattr(self, "lblHavuzSayisi"):
            if query:
                self.lblHavuzSayisi.setText(f"{visible_cnt}/{total} kitap")
            else:
                self.lblHavuzSayisi.setText(f"{total} kitap")

    def _havuz_check_all(self, check: bool):
        st = Qt.CheckState.Checked if check else Qt.CheckState.Unchecked
        for i in range(self.lstHavuz.count()):
            it = self.lstHavuz.item(i)
            if not it.isHidden():
                if self._check_mode:
                    it.setCheckState(st)
                else:
                    it.setSelected(check)

    def _yenile_havuz(self):
        if not hasattr(self, "lstHavuz"): return
        self.lstHavuz.clear()
        con = db.get_conn()
        ders = self.cmbDers.currentText()
        usage = self._book_usage_map()
        for r in db.kitap_havuzu(con, ders):
            try: ad = r["ad"]
            except Exception: ad = r[0]
            ad = ad or ""
            badge = usage.get(ad, 0)
            txt = f"{ad}  • {badge}" if badge else ad
            it = QListWidgetItem(txt)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Unchecked)
            it.setData(Qt.ItemDataRole.UserRole, ad)
            self.lstHavuz.addItem(it)
        self._apply_havuz_mode()
        if hasattr(self, "lblHavuzSayisi"):
            self.lblHavuzSayisi.setText(f"{self.lstHavuz.count()} kitap")
        if hasattr(self, "txtHavuzAra") and self.txtHavuzAra.text().strip():
            self._filtrele_havuz()

    def _ogr_check_all(self, check):
        st = Qt.CheckState.Checked if check else Qt.CheckState.Unchecked
        for i in range(self.lstOgr.count()): self.lstOgr.item(i).setCheckState(st)

    # ---- Özellikleri Düzenle akışı (sol panel butonundan) ----
    def _open_props_picker(self):
        # Metin kutusundaki adları + havuzdaki seçili/işaretli adları topla
        names = set()
        for ln in self.txtKitaplar.toPlainText().splitlines():
            for p in ln.split(","):
                nm = self._pure_book_name(p)
                if nm: names.add(nm)
        for it in self.lstHavuz.selectedItems():
            nm = self._pure_book_name(it.data(Qt.ItemDataRole.UserRole) or it.text())
            if nm: names.add(nm)
        if self._check_mode:
            for i in range(self.lstHavuz.count()):
                it = self.lstHavuz.item(i)
                if it.checkState() == Qt.CheckState.Checked:
                    nm = self._pure_book_name(it.data(Qt.ItemDataRole.UserRole) or it.text())
                    if nm: names.add(nm)

        names = sorted(names, key=lambda s: s.lower())
        if not names:
            self._toast("Önce bir kitap adı yazın veya havuzdan seçin.", "warn")
            return

        # Küçük bir seçim menüsü
        menu = QMenu(self)
        acts = [menu.addAction(n) for n in names]
        chosen = menu.exec(self.btnOpenProps.mapToGlobal(self.btnOpenProps.rect().bottomLeft()))
        if not chosen: return
        selected_name = chosen.text()
        con = db.get_conn()
        _ensure_table_kitap_ozellik(con)
        KitapOzellikDialog(con, self.cmbDers.currentText(), selected_name, self).exec()

    # ---------------- İşlemler ----------------
    def _toplanan_kitaplar(self):
        adlar = []
        raw = self.txtKitaplar.toPlainText().strip()
        if raw:
            parts = []
            for line in raw.splitlines():
                parts.extend([self._pure_book_name(p) for p in line.split(",")])
            adlar.extend([p for p in parts if p])
        for i in range(self.lstHavuz.count()):
            it = self.lstHavuz.item(i)
            if (self._check_mode and it.checkState() == Qt.CheckState.Checked) or (not self._check_mode and it.isSelected()):
                name = it.data(Qt.ItemDataRole.UserRole) or it.text()
                adlar.append(self._pure_book_name(name))
        uniq, seen = [], set()
        for a in adlar:
            if a and a not in seen: seen.add(a); uniq.append(a)
        return uniq

    def _hedef_ogrenci_idleri(self):
        secili_id, ogr_liste = self.ogrenci_provider()
        if self.radTek.isChecked(): return [secili_id] if secili_id else []
        elif self.radTum.isChecked(): return [int(r["id"]) for r in ogr_liste]
        else:
            ids = []
            for i in range(self.lstOgr.count()):
                it = self.lstOgr.item(i)
                if it.checkState() == Qt.CheckState.Checked:
                    ids.append(it.data(Qt.ItemDataRole.UserRole))
            return ids

    def _stamp_eklenme_tarih(self, con, ogr_ids, ders, kitaplar):
        try:
            if not ogr_ids or not kitaplar: return
            ph_k = ",".join("?" for _ in kitaplar)
            ph_o = ",".join("?" for _ in ogr_ids)
            q = f"""UPDATE ogrenci_kitap
                    SET eklenme_tarih = COALESCE(eklenme_tarih, date('now'))
                    WHERE ders=? AND kitap_ad IN ({ph_k}) AND ogrenci_id IN ({ph_o})"""
            con.execute(q, (ders, *kitaplar, *ogr_ids))
            con.commit()
        except Exception:
            pass

    def _ekle(self):
        ders = self.cmbDers.currentText()
        kitaplar = self._toplanan_kitaplar()
        if not kitaplar:
            self._toast("Eklenecek kitap adı girin veya havuzdan seçin.", "warn")
            return
        ogr_ids = self._hedef_ogrenci_idleri()
        if not ogr_ids:
            self._toast("Hedef öğrenci seçilmedi.", "warn")
            return
        con = db.get_conn()
        _ensure_column(con, "ogrenci_kitap", "eklenme_tarih", "TEXT")
        db.kitap_ekle_havuz(con, ders, kitaplar)
        db.ogrenciye_kitap_ekle(con, ogr_ids, ders, kitaplar)
        self._stamp_eklenme_tarih(con, ogr_ids, ders, kitaplar)
        self.txtKitaplar.clear()
        self.son_ders = ders
        self._degisiklik_oldu = True
        self._toast(f"{len(kitaplar)} kitap başarıyla eklendi.", "ok")
        self.accept()

    def _sil(self):
        ders = self.cmbDers.currentText()
        kitaplar = self._toplanan_kitaplar()
        if not kitaplar:
            self._toast("Silinecek kitap seçilmedi. Lütfen havuzdan veya listeden kitap seçin.", "warn")
            return

        secili_id, ogr_liste = self.ogrenci_provider()
        ogr_ids = self._hedef_ogrenci_idleri()
        has_students = bool(ogr_ids or secili_id)

        dlg = KitapSilmeSecimDialog(kitaplar, ders, has_students=has_students, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        mode = dlg.get_mode()
        odevleri_sil = dlg.odevleri_temizle()
        con = db.get_conn()

        if mode == "havuz":
            db.kitap_sil_havuz(con, ders, kitaplar, odevleri_de_temizle=odevleri_sil)
            # Metin kutusunda varsa temizle
            raw = self.txtKitaplar.toPlainText()
            for k in kitaplar:
                raw = re.sub(rf"(?m)^\s*{re.escape(k)}\s*$", "", raw)
            self.txtKitaplar.setPlainText(raw.strip())
            
            self._yenile_havuz()
            self.son_ders = ders
            self._degisiklik_oldu = True
            self._toast(f"{len(kitaplar)} kitap sistemden ve havuzdan tamamen silindi.", "ok")
        else:
            if not ogr_ids:
                if secili_id:
                    ogr_ids = [secili_id]
                else:
                    self._toast("Öğrenciden silmek için lütfen hedef öğrenci seçin.", "warn")
                    return
            db.ogrenciden_kitap_sil(con, ogr_ids, ders, kitaplar)
            self._yenile_havuz()
            self.son_ders = ders
            self._degisiklik_oldu = True
            self._toast(f"{len(kitaplar)} kitap seçili öğrenciden kaldırıldı.", "ok")