# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sqlite3
import datetime as dt
from typing import Optional, Dict, Any, List, Tuple

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QFormLayout,
    QDoubleSpinBox, QPushButton, QComboBox, QDateEdit, QMessageBox, QFrame, QDialog, QScrollArea
)
from PyQt6.QtGui import QDesktopServices

# Matplotlib (Trend Grafiği)
try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    class FigureCanvas(QWidget):
        def __init__(self, fig): super().__init__()
    class Figure:
        def __init__(self, figsize=None): pass
        def add_subplot(self, *args): return None
        def clear(self): pass
        def autofmt_xdate(self): pass

# -------------------------------------------------------------
#  A) Resmi ÖSYM & MEB Verileri ve Yıllık Projeksiyonlar (2024, 2025, 2026)
# -------------------------------------------------------------
OFFICIAL_2024_YKS_AVG = {
    "TYT_TURKCE": 21.43,
    "TYT_SOSYAL": 9.00,
    "TYT_MAT": 7.96,
    "TYT_FEN": 3.48,
    "AYT_MAT": 5.55,
    "AYT_FIZIK": 2.25,
    "AYT_KIMYA": 1.46,
    "AYT_BIYO": 2.32,
    "AYT_EDEB": 5.94,
    "AYT_TAR1": 2.48,
    "AYT_COG1": 2.10,
    "AYT_TAR2": 2.08,
    "AYT_COG2": 2.42,
    "AYT_FELSEFE": 1.96,
    "AYT_DKAB_EK": 1.28,
    "YDT_INGILIZCE": 35.60
}

OFFICIAL_2024_LGS_AVG = {
    "LGS_TURKCE": 9.63,
    "LGS_MAT": 6.54,
    "LGS_FEN": 8.63,
    "LGS_INKILAP": 4.68,
    "LGS_DIN": 5.74,
    "LGS_INGILIZCE": 5.15,
}

CACHED_2025_YKS_AVG = {
    "TYT_TURKCE": 22.10,
    "TYT_SOSYAL": 9.25,
    "TYT_MAT": 8.15,
    "TYT_FEN": 3.75,
    "AYT_MAT": 5.85,
    "AYT_FIZIK": 2.40,
    "AYT_KIMYA": 1.60,
    "AYT_BIYO": 2.45,
    "AYT_EDEB": 6.20,
    "AYT_TAR1": 2.55,
    "AYT_COG1": 2.15,
    "AYT_TAR2": 2.15,
    "AYT_COG2": 2.48,
    "AYT_FELSEFE": 2.05,
    "AYT_DKAB_EK": 1.35,
    "YDT_INGILIZCE": 36.80
}

CACHED_2025_LGS_AVG = {
    "LGS_TURKCE": 9.85,
    "LGS_MAT": 6.80,
    "LGS_FEN": 8.90,
    "LGS_INKILAP": 4.85,
    "LGS_DIN": 5.90,
    "LGS_INGILIZCE": 5.30,
}

PROJ_2026_YKS_AVG = {
    "TYT_TURKCE": 22.50,
    "TYT_SOSYAL": 9.50,
    "TYT_MAT": 8.50,
    "TYT_FEN": 4.10,
    "AYT_MAT": 6.20,
    "AYT_FIZIK": 2.60,
    "AYT_KIMYA": 1.75,
    "AYT_BIYO": 2.60,
    "AYT_EDEB": 6.50,
    "AYT_TAR1": 2.65,
    "AYT_COG1": 2.25,
    "AYT_TAR2": 2.25,
    "AYT_COG2": 2.55,
    "AYT_FELSEFE": 2.15,
    "AYT_DKAB_EK": 1.45,
    "YDT_INGILIZCE": 37.50
}

PROJ_2026_LGS_AVG = {
    "LGS_TURKCE": 10.10,
    "LGS_MAT": 7.10,
    "LGS_FEN": 9.15,
    "LGS_INKILAP": 5.00,
    "LGS_DIN": 6.05,
    "LGS_INGILIZCE": 5.50,
}


def get_national_averages(year: int = 2025, is_lgs: bool = False) -> Dict[str, float]:
    """Seçilen yıl için ulusal ortalamaları döndürür."""
    if is_lgs:
        if year == 2024: return dict(OFFICIAL_2024_LGS_AVG)
        if year == 2026: return dict(PROJ_2026_LGS_AVG)
        return dict(CACHED_2025_LGS_AVG)
    else:
        if year == 2024: return dict(OFFICIAL_2024_YKS_AVG)
        if year == 2026: return dict(PROJ_2026_YKS_AVG)
        return dict(CACHED_2025_YKS_AVG)


def _get_default_history_db_path() -> str:
    try:
        import db
        return str(db.get_db_path().parent / "deneme_history.db")
    except Exception:
        from pathlib import Path
        import os
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "YKS_LGS_HomeworkManager"
        base.mkdir(parents=True, exist_ok=True)
        return str(base / "deneme_history.db")

# -----------------------------
#  B) Deneme Geçmişi Deposu
# -----------------------------
class DenemeStore:
    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or _get_default_history_db_path()
        self._init_db()

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._conn() as con:
            con.execute("""
            CREATE TABLE IF NOT EXISTS deneme (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                d TEXT NOT NULL,
                exam TEXT NOT NULL,
                alan TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """)
            con.commit()

    def add(self, date_: dt.date, exam: str, alan: str, payload: Dict[str, Any]) -> None:
        with self._conn() as con:
            con.execute(
                "INSERT INTO deneme(d, exam, alan, payload) VALUES(?,?,?,?)",
                (date_.isoformat(), exam, alan, json.dumps(payload, ensure_ascii=False))
            )
            con.commit()

    def list_last(self, exam: str, alan: str, n: int = 20) -> List[Tuple[dt.date, Dict[str, Any]]]:
        with self._conn() as con:
            cur = con.execute(
                "SELECT d, payload FROM deneme WHERE exam=? AND alan=? ORDER BY d ASC, id ASC LIMIT ?",
                (exam, alan, n)
            )
            rows = cur.fetchall()
        out = []
        for d_s, p_s in rows:
            try:
                out.append((dt.date.fromisoformat(d_s), json.loads(p_s)))
            except Exception:
                continue
        return out


# -----------------------------
#  C) Trend Grafiği
# -----------------------------
class TrendPlot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        
        if MATPLOTLIB_AVAILABLE:
            self.fig = Figure(figsize=(5, 3.2), dpi=100)
            self.canvas = FigureCanvas(self.fig)
            self.canvas.setStyleSheet("background-color: transparent;")
            self.fig.patch.set_facecolor('#ffffff')
            lay.addWidget(self.canvas)
        else:
            self.lbl_fallback = QLabel("Grafik görünümü için 'matplotlib' kütüphanesi hazır değil.")
            self.lbl_fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(self.lbl_fallback)

    def set_series(self, dates: List[dt.date], values: List[float], title: str, target_val: Optional[float] = None):
        if not MATPLOTLIB_AVAILABLE:
            if hasattr(self, "lbl_fallback"):
                self.lbl_fallback.setText(f"📊 {title}: {len(values)} Deneme Kayıtlı\nSon Net: {values[-1] if values else '-'}")
            return
        
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        ax.set_facecolor('#f8fafc')
        
        if dates and values:
            date_labels = [d.strftime("%d.%m") for d in dates]
            ax.plot(date_labels, values, marker="o", linestyle="-", color="#2563eb", linewidth=2.2, markersize=5, label="Gerçekleşen")
            
            # Trend çizgisi (en az 3 nokta varsa)
            if len(values) >= 3:
                try:
                    import numpy as np
                    x_idx = np.arange(len(values))
                    poly = np.polyfit(x_idx, values, 1)
                    trend_vals = poly[0] * x_idx + poly[1]
                    ax.plot(date_labels, trend_vals, linestyle=":", color="#10b981", linewidth=1.8, label="Gelişim Trendi")
                except Exception:
                    pass
            
            # Hedef çizgisi
            if target_val:
                ax.axhline(y=target_val, color='#ef4444', linestyle='--', linewidth=1.8, label=f'Hedef: {target_val:.1f}')
                
            ax.legend(loc='upper left', fontsize=8, frameon=True, facecolor='#ffffff')
        else:
            ax.text(0.5, 0.5, "Henüz Kayıtlı Deneme Verisi Yok", ha='center', va='center', color='#94a3b8', fontsize=11)
            
        ax.set_title(title, fontsize=10, fontweight='bold', color='#1e293b', pad=10)
        ax.tick_params(axis='x', rotation=35, labelsize=8)
        ax.tick_params(axis='y', labelsize=8)
        ax.grid(True, linestyle='--', alpha=0.5, color='#cbd5e1')
        
        for spine in ['top', 'right']:
            ax.spines[spine].set_visible(False)
        ax.spines['left'].set_color('#cbd5e1')
        ax.spines['bottom'].set_color('#cbd5e1')

        self.fig.tight_layout()
        self.canvas.draw()


# -----------------------------
#  D) Ana Analitik Paneli
# -----------------------------
class AdvancedNetAndTrendPanel(QWidget):
    def __init__(self, parent=None, db_path: Optional[str] = None, student_id: Optional[int] = None):
        super().__init__(parent)
        self.student_id = student_id
        self.store = DenemeStore(db_path)
        self.current_target = None
        self._build_ui()

    def set_student_id(self, student_id: int):
        self.student_id = student_id
        self._auto_sync_student_denemes()

    def _spin(self, maxv: float) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(0.0, maxv)
        s.setSingleStep(0.25)
        s.setDecimals(2)
        s.setStyleSheet("background: white; border: 1px solid #cbd5e1; border-radius: 6px; padding: 4px; font-weight: 600;")
        return s

    def _build_ui(self):
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        content_widget = QWidget()
        root = QVBoxLayout(content_widget)
        root.setSpacing(16)
        root.setContentsMargins(20, 20, 20, 20)

        # Başlık ve Açıklama Kartı
        info_frame = QFrame()
        info_frame.setStyleSheet("background: #eff6ff; border-radius: 10px; border: 1px solid #bfdbfe;")
        ilay = QVBoxLayout(info_frame)
        ilay.setContentsMargins(16, 12, 16, 12)
        
        title = QLabel("📈 Akıllı Performans Takibi ve Çok Yıllı Trend Analizi (2024 / 2025 / 2026)")
        title.setStyleSheet("font-size:15px; font-weight:bold; color:#1e40af;")
        hint = QLabel(
            "Deneme sınavı sonuçlarınızı kaydedin, gelişim trendinizi takip edin ve resmi ÖSYM / MEB Türkiye ortalamaları ile anlık kıyaslama yapın."
        )
        hint.setStyleSheet("color:#1e3a8a; font-size: 12px;")
        hint.setWordWrap(True)
        
        ilay.addWidget(title)
        ilay.addWidget(hint)
        root.addWidget(info_frame)

        # İki sütun
        h_content = QHBoxLayout()
        h_content.setSpacing(16)
        
        # --- SOL SÜTUN (Girişler) ---
        input_col = QVBoxLayout()
        input_col.setSpacing(12)
        
        # Alan ve Referans Yıl Seçimi
        top_ctrl_frame = QFrame()
        top_ctrl_frame.setStyleSheet("background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 6px;")
        f_top = QVBoxLayout(top_ctrl_frame)
        f_top.setContentsMargins(8, 8, 8, 8)
        
        row_alan = QHBoxLayout()
        row_alan.addWidget(QLabel("<b>Alan:</b>"))
        self.cmb_alan = QComboBox()
        self.cmb_alan.addItems(["SAY", "EA", "SÖZ", "DİL", "LGS"])
        self.cmb_alan.setStyleSheet("padding: 4px; font-weight: bold;")
        self.cmb_alan.currentTextChanged.connect(self._on_alan_changed)
        row_alan.addWidget(self.cmb_alan, 1)
        f_top.addLayout(row_alan)

        row_year = QHBoxLayout()
        row_year.addWidget(QLabel("<b>Ort. Yılı:</b>"))
        self.cmb_ref_year = QComboBox()
        self.cmb_ref_year.addItems(["2025 Güncel Yerleştirme", "2026 Akıllı Projeksiyon", "2024 ÖSYM/MEB Resmi"])
        self.cmb_ref_year.setStyleSheet("padding: 4px;")
        row_year.addWidget(self.cmb_ref_year, 1)
        f_top.addLayout(row_year)
        
        input_col.addWidget(top_ctrl_frame)

        # 1. Grup Girişleri (TYT veya LGS Sözel)
        self.gb_tyt = QGroupBox("TYT Netleri")
        self.gb_tyt.setStyleSheet("""
            QGroupBox { font-weight: bold; color: #1e293b; border: 1px solid #cbd5e1; border-radius: 8px; margin-top: 10px; background: white; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """)
        self.f1 = QFormLayout(self.gb_tyt)
        self.lbl_t1 = QLabel("Türkçe (40):"); self.sp_tr = self._spin(40); self.f1.addRow(self.lbl_t1, self.sp_tr)
        self.lbl_t2 = QLabel("Sosyal (20):"); self.sp_sos = self._spin(20); self.f1.addRow(self.lbl_t2, self.sp_sos)
        self.lbl_t3 = QLabel("Matematik (40):"); self.sp_mat = self._spin(40); self.f1.addRow(self.lbl_t3, self.sp_mat)
        self.lbl_t4 = QLabel("Fen Bilimleri (20):"); self.sp_fen = self._spin(20); self.f1.addRow(self.lbl_t4, self.sp_fen)
        input_col.addWidget(self.gb_tyt)

        # 2. Grup Girişleri (AYT, YDT veya LGS Sayısal)
        self.gb_ayt = QGroupBox("AYT Netleri")
        self.gb_ayt.setStyleSheet(self.gb_tyt.styleSheet())
        self.f2 = QFormLayout(self.gb_ayt)

        self.lbl_a1 = QLabel("Matematik (40):"); self.sp_a1 = self._spin(40); self.f2.addRow(self.lbl_a1, self.sp_a1)
        self.lbl_a2 = QLabel("Fizik (14):"); self.sp_a2 = self._spin(14); self.f2.addRow(self.lbl_a2, self.sp_a2)
        self.lbl_a3 = QLabel("Kimya (13):"); self.sp_a3 = self._spin(13); self.f2.addRow(self.lbl_a3, self.sp_a3)
        self.lbl_a4 = QLabel("Biyoloji (13):"); self.sp_a4 = self._spin(13); self.f2.addRow(self.lbl_a4, self.sp_a4)

        input_col.addWidget(self.gb_ayt)

        # Aksiyonlar
        gb_save = QGroupBox("İşlemler")
        gb_save.setStyleSheet(self.gb_tyt.styleSheet())
        save_lay = QVBoxLayout(gb_save)
        
        row_date = QHBoxLayout()
        row_date.addWidget(QLabel("Tarih:"))
        self.dt_date = QDateEdit()
        self.dt_date.setCalendarPopup(True)
        self.dt_date.setDate(dt.date.today())
        row_date.addWidget(self.dt_date, 1)
        save_lay.addLayout(row_date)
        
        self.btn_save = QPushButton("💾 Denemeyi Kaydet")
        self.btn_save.setStyleSheet("background-color: #059669; color: white; font-weight: bold; padding: 8px; border-radius: 6px;")
        self.btn_save.clicked.connect(self._save_deneme)
        save_lay.addWidget(self.btn_save)

        self.btn_sync = QPushButton("📥 Sistemdeki Denemelerden Yükle")
        self.btn_sync.setStyleSheet("background-color: #0284c7; color: white; font-weight: bold; padding: 8px; border-radius: 6px;")
        self.btn_sync.clicked.connect(self._auto_sync_student_denemes)
        save_lay.addWidget(self.btn_sync)

        self.btn_analyze = QPushButton("🧠 Türkiye Ortalamaları ile Kıyasla")
        self.btn_analyze.setStyleSheet("background-color: #4f46e5; color: white; font-weight: bold; padding: 8px; border-radius: 6px;")
        self.btn_analyze.clicked.connect(self._analyze)
        save_lay.addWidget(self.btn_analyze)

        self.btn_suggest = QPushButton("♟️ Nokta Atışı: Eksik Konu Kapat")
        self.btn_suggest.setStyleSheet("background-color: #d97706; color: white; font-weight: bold; padding: 8px; border-radius: 6px;")
        self.btn_suggest.clicked.connect(self._suggest_resources)
        save_lay.addWidget(self.btn_suggest)
        
        input_col.addWidget(gb_save)
        input_col.addStretch()
        
        # --- SAĞ SÜTUN (Grafik ve Sonuçlar) ---
        right_col = QVBoxLayout()
        right_col.setSpacing(12)
        
        self.plot = TrendPlot()
        self.plot.setMinimumHeight(260)
        right_col.addWidget(self.plot)
        
        self.lbl_trend = QLabel("Henüz yeterli deneme verisi yok.")
        self.lbl_trend.setStyleSheet("font-size: 12px; color: #475569; font-weight: 600; padding: 4px 8px; background: white; border-radius: 6px; border: 1px solid #e2e8f0;")
        right_col.addWidget(self.lbl_trend)

        self.lbl_out = QLabel("📊 Deneme sonuçlarınızı girip 'Türkiye Ortalamaları ile Kıyasla' butonuna tıklayarak kapsamlı rapor alabilirsiniz.")
        self.lbl_out.setWordWrap(True)
        self.lbl_out.setStyleSheet("""
            QLabel {
                background: white;
                border: 1px solid #cbd5e1;
                padding: 16px;
                border-radius: 10px;
                font-size: 13px;
                color: #1e293b;
                line-height: 1.5;
            }
        """)
        self.lbl_out.setAlignment(Qt.AlignmentFlag.AlignTop)
        right_col.addWidget(self.lbl_out, 1)

        h_content.addLayout(input_col, 38)
        h_content.addLayout(right_col, 62)
        root.addLayout(h_content)
        
        scroll.setWidget(content_widget)
        main_lay.addWidget(scroll)

        self._on_alan_changed(self.cmb_alan.currentText())
        self._refresh_trend()

    def _get_selected_ref_year(self) -> int:
        txt = self.cmb_ref_year.currentText()
        if "2024" in txt: return 2024
        if "2026" in txt: return 2026
        return 2025

    def _on_alan_changed(self, alan: str):
        is_lgs = (alan == "LGS")
        is_dil = (alan == "DİL")
        
        if is_lgs:
            self.gb_tyt.setTitle("LGS Sözel Bölüm Netleri")
            self.lbl_t1.setText("Türkçe (20):"); self.sp_tr.setRange(0, 20)
            self.lbl_t2.setText("T.C. İnkılap (10):"); self.sp_sos.setRange(0, 10)
            self.lbl_t3.setText("Din Kültürü (10):"); self.sp_mat.setRange(0, 10)
            self.lbl_t4.setText("Yabancı Dil (10):"); self.sp_fen.setRange(0, 10)
            
            self.gb_ayt.setTitle("LGS Sayısal Bölüm Netleri")
            self.lbl_a1.setText("Matematik (20):"); self.sp_a1.setRange(0, 20)
            self.lbl_a2.setText("Fen Bilimleri (20):"); self.sp_a2.setRange(0, 20)
            self.lbl_a3.setVisible(False); self.sp_a3.setVisible(False)
            self.lbl_a4.setVisible(False); self.sp_a4.setVisible(False)
            
        elif is_dil:
            self.gb_tyt.setTitle("TYT Netleri")
            self.lbl_t1.setText("Türkçe (40):"); self.sp_tr.setRange(0, 40)
            self.lbl_t2.setText("Sosyal (20):"); self.sp_sos.setRange(0, 20)
            self.lbl_t3.setText("Matematik (40):"); self.sp_mat.setRange(0, 40)
            self.lbl_t4.setText("Fen Bilimleri (20):"); self.sp_fen.setRange(0, 20)
            
            self.gb_ayt.setTitle("YDT (Yabancı Dil Testi)")
            self.lbl_a1.setText("İngilizce / YDT (80):"); self.sp_a1.setRange(0, 80)
            self.lbl_a2.setVisible(False); self.sp_a2.setVisible(False)
            self.lbl_a3.setVisible(False); self.sp_a3.setVisible(False)
            self.lbl_a4.setVisible(False); self.sp_a4.setVisible(False)
            
        else: # SAY, EA, SÖZ
            self.gb_tyt.setTitle("TYT Netleri")
            self.lbl_t1.setText("Türkçe (40):"); self.sp_tr.setRange(0, 40)
            self.lbl_t2.setText("Sosyal (20):"); self.sp_sos.setRange(0, 20)
            self.lbl_t3.setText("Matematik (40):"); self.sp_mat.setRange(0, 40)
            self.lbl_t4.setText("Fen Bilimleri (20):"); self.sp_fen.setRange(0, 20)
            
            self.gb_ayt.setTitle(f"AYT Netleri ({alan})")
            self.lbl_a2.setVisible(True); self.sp_a2.setVisible(True)
            self.lbl_a3.setVisible(True); self.sp_a3.setVisible(True)
            self.lbl_a4.setVisible(True); self.sp_a4.setVisible(True)
            
            if alan == "SAY":
                self.lbl_a1.setText("Matematik (40):"); self.sp_a1.setRange(0, 40)
                self.lbl_a2.setText("Fizik (14):");     self.sp_a2.setRange(0, 14)
                self.lbl_a3.setText("Kimya (13):");     self.sp_a3.setRange(0, 13)
                self.lbl_a4.setText("Biyoloji (13):");  self.sp_a4.setRange(0, 13)
            elif alan == "EA":
                self.lbl_a1.setText("Matematik (40):"); self.sp_a1.setRange(0, 40)
                self.lbl_a2.setText("Edebiyat (24):");  self.sp_a2.setRange(0, 24)
                self.lbl_a3.setText("Tarih-1 (10):");   self.sp_a3.setRange(0, 10)
                self.lbl_a4.setText("Coğrafya-1 (6):"); self.sp_a4.setRange(0, 6)
            else: # SÖZ
                self.lbl_a1.setText("Edebiyat (24):");  self.sp_a1.setRange(0, 24)
                self.lbl_a2.setText("Tarih-1 (10):");   self.sp_a2.setRange(0, 10)
                self.lbl_a3.setText("Coğrafya-1 (6):"); self.sp_a3.setRange(0, 6)
                self.lbl_a4.setText("Sosyal-2 (40):");  self.sp_a4.setRange(0, 40)

        self._refresh_trend()

    def set_target(self, target_data: Dict[str, Any]):
        """Dışarıdan gelen hedef verisini bağlar."""
        self.current_target = target_data
        self._refresh_trend()

    def _auto_sync_student_denemes(self):
        """Ana veritabanından öğrencinin deneme sınavı sonuçlarını trende aktarır."""
        try:
            import db
            con = db.get_conn()
            
            # Öğrenci id kontrol
            s_id = self.student_id
            if not s_id:
                row = con.execute("SELECT id FROM ogrenci LIMIT 1").fetchone()
                if row: s_id = row[0]
                
            if not s_id:
                QMessageBox.information(self, "Bilgi", "Sistemde kayıtlı öğrenci bulunamadı.")
                return

            rows = con.execute("""
                SELECT d.tarih, d.deneme_adi, d.tur, ds.ders_adi, ds.net
                FROM deneme_sonuclari ds
                JOIN denemeler d ON d.id = ds.deneme_id
                WHERE ds.ogrenci_id = ?
                ORDER BY d.tarih ASC
            """, (s_id,)).fetchall()

            if not rows:
                QMessageBox.information(self, "Bilgi", "Bu öğrenciye ait kayıtlı deneme sonucu bulunamadı.")
                return

            # Denemelere göre grupla
            by_exam = {}
            for r in rows:
                tarih = r[0]
                d_adi = r[1]
                key = (tarih, d_adi)
                if key not in by_exam:
                    by_exam[key] = {"tarih": tarih, "tur": r[2] or "YKS", "netler": {}}
                by_exam[key]["netler"][r[3]] = float(r[4] or 0)

            alan = self.cmb_alan.currentText()
            exam_type = "LGS" if alan == "LGS" else "YKS"
            added_count = 0

            for (tarih, d_adi), info in by_exam.items():
                try:
                    d_obj = dt.datetime.strptime(tarih, "%Y-%m-%d").date()
                except Exception:
                    d_obj = dt.date.today()
                    
                netler = info["netler"]
                total_net = sum(netler.values())
                
                payload = {
                    "tyt_total": total_net if exam_type == "LGS" else sum(v for k, v in netler.items() if "TYT" in k.upper()),
                    "ayt_total": 0 if exam_type == "LGS" else sum(v for k, v in netler.items() if "AYT" in k.upper() or "YDT" in k.upper()),
                    "deneme_adi": d_adi
                }
                self.store.add(d_obj, exam_type, alan, payload)
                added_count += 1

            QMessageBox.information(self, "Başarılı", f"Sistemden {added_count} deneme sonucu trend grafiğine başarıyla aktarıldı!")
            self._refresh_trend()

        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Denemeler çekilirken sorun oluştu: {e}")

    def _save_deneme(self):
        try:
            date_ = self.dt_date.date().toPyDate()
            alan = self.cmb_alan.currentText()
            exam_type = "LGS" if alan == "LGS" else "YKS"
            
            if alan == "LGS":
                sozel = self.sp_tr.value() + self.sp_sos.value() + self.sp_mat.value() + self.sp_fen.value()
                sayisal = self.sp_a1.value() + self.sp_a2.value()
                payload = {
                    "tyt_total": sozel + sayisal, # LGS'de tyt_total alanını toplam net olarak tutuyoruz
                    "ayt_total": 0,
                    "sozel": sozel,
                    "sayisal": sayisal
                }
            elif alan == "DİL":
                tyt_tot = self.sp_tr.value() + self.sp_sos.value() + self.sp_mat.value() + self.sp_fen.value()
                ydt_tot = self.sp_a1.value()
                payload = {"tyt_total": tyt_tot, "ayt_total": ydt_tot}
            else:
                tyt_tot = self.sp_tr.value() + self.sp_sos.value() + self.sp_mat.value() + self.sp_fen.value()
                ayt_tot = self.sp_a1.value() + self.sp_a2.value() + self.sp_a3.value() + self.sp_a4.value()
                payload = {"tyt_total": tyt_tot, "ayt_total": ayt_tot}
                
            self.store.add(date_, exam_type, alan, payload)
            QMessageBox.information(self, "Başarılı", "Deneme sonucu kaydedildi ve trend güncellendi.")
            self._refresh_trend()
        except Exception as e:
            QMessageBox.warning(self, "Hata", str(e))

    def _refresh_trend(self):
        alan = self.cmb_alan.currentText()
        exam_type = "LGS" if alan == "LGS" else "YKS"
        rows = self.store.list_last(exam_type, alan, n=20)
        
        if not rows:
            self.plot.set_series([], [], f"Henüz Veri Yok ({alan})")
            self.lbl_trend.setText("Henüz kayıtlı deneme sonucu bulunmuyor.")
            return
            
        dates = [d for d, _ in rows]
        totals = [p.get("tyt_total", 0) + p.get("ayt_total", 0) for _, p in rows]
        
        target_total = None
        if hasattr(self, "current_target") and self.current_target:
            t = self.current_target
            if "req_net" in t:
                target_total = t.get("req_net", 0)
            elif "req_tyt" in t:
                target_total = t.get("req_tyt", 0) + t.get("req_ayt", 0)

        title = f"Toplam Net Gelişim Trendi ({alan})"
        self.plot.set_series(dates, totals, title, target_val=target_total)
        
        if len(rows) >= 2:
            last = totals[-1]
            prev = totals[-2]
            diff = last - prev
            icon = "📈" if diff > 0 else ("📉" if diff < 0 else "➖")
            
            # Eğim (Haftalık Artış Hızı)
            x_days = [(d - dates[0]).days for d in dates]
            if max(x_days) > 0:
                slope_per_week = ((totals[-1] - totals[0]) / max(1, max(x_days))) * 7
                rate_text = f" • Haftalık Ortalama Hız: <b>{slope_per_week:+.1f} Net</b>"
            else:
                rate_text = ""
                
            self.lbl_trend.setText(f"Son Deneme: <b>{last:.1f} Net</b> ({icon} {diff:+.1f} Net) {rate_text}")

    def _analyze(self):
        alan = self.cmb_alan.currentText()
        year = self._get_selected_ref_year()
        is_lgs = (alan == "LGS")
        ref = get_national_averages(year, is_lgs=is_lgs)
        
        def check_row(label: str, my_val: float, ref_val: float) -> str:
            diff = my_val - ref_val
            pct = ((my_val / max(0.1, ref_val)) - 1.0) * 100
            c = "#16a34a" if diff >= 0 else "#dc2626"
            sign = "+" if diff >= 0 else ""
            return (
                f"<tr>"
                f"<td style='padding:4px 8px; font-weight:600;'>{label}</td>"
                f"<td style='padding:4px 8px; text-align:center;'><b>{my_val:.2f}</b></td>"
                f"<td style='padding:4px 8px; text-align:center; color:#64748b;'>{ref_val:.2f}</td>"
                f"<td style='padding:4px 8px; text-align:right; color:{c}; font-weight:bold;'>{sign}{diff:.2f} (%{pct:+.0f})</td>"
                f"</tr>"
            )

        html = f"<b>📊 {year} Türkiye Sınav Ortalamaları ile Karşılaştırma ({alan})</b><br>"
        html += "<table border='0' cellspacing='0' cellpadding='4' style='width:100%; border-collapse:collapse; margin-top:8px; font-size:12px;'>"
        html += "<tr style='background:#f1f5f9; color:#475569; font-weight:bold;'><td style='padding:6px 8px;'>Test Adı</td><td style='text-align:center;'>Senin Netin</td><td style='text-align:center;'>Türkiye Ort.</td><td style='text-align:right;'>Fark (Performans)</td></tr>"

        if is_lgs:
            tot_my = (self.sp_tr.value() + self.sp_sos.value() + self.sp_mat.value() + self.sp_fen.value() + self.sp_a1.value() + self.sp_a2.value())
            tot_ref = sum(ref.values())
            html += check_row("Türkçe (20)", self.sp_tr.value(), ref["LGS_TURKCE"])
            html += check_row("T.C. İnkılap (10)", self.sp_sos.value(), ref["LGS_INKILAP"])
            html += check_row("Din Kültürü (10)", self.sp_mat.value(), ref["LGS_DIN"])
            html += check_row("Yabancı Dil (10)", self.sp_fen.value(), ref["LGS_INGILIZCE"])
            html += check_row("Matematik (20)", self.sp_a1.value(), ref["LGS_MAT"])
            html += check_row("Fen Bilimleri (20)", self.sp_a2.value(), ref["LGS_FEN"])
            html += f"<tr style='background:#f8fafc; font-weight:bold;'><td style='padding:6px 8px;'>TOPLAM NET (90)</td><td style='text-align:center;'>{tot_my:.2f}</td><td style='text-align:center;'>{tot_ref:.2f}</td><td style='text-align:right; color:#2563eb;'>{tot_my - tot_ref:+.2f}</td></tr>"
        elif alan == "DİL":
            tot_my = (self.sp_tr.value() + self.sp_sos.value() + self.sp_mat.value() + self.sp_fen.value() + self.sp_a1.value())
            html += check_row("TYT Türkçe (40)", self.sp_tr.value(), ref["TYT_TURKCE"])
            html += check_row("TYT Sosyal (20)", self.sp_sos.value(), ref["TYT_SOSYAL"])
            html += check_row("TYT Matematik (40)", self.sp_mat.value(), ref["TYT_MAT"])
            html += check_row("TYT Fen (20)", self.sp_fen.value(), ref["TYT_FEN"])
            html += check_row("YDT İngilizce (80)", self.sp_a1.value(), ref["YDT_INGILIZCE"])
        else:
            html += check_row("TYT Türkçe (40)", self.sp_tr.value(), ref["TYT_TURKCE"])
            html += check_row("TYT Sosyal (20)", self.sp_sos.value(), ref["TYT_SOSYAL"])
            html += check_row("TYT Matematik (40)", self.sp_mat.value(), ref["TYT_MAT"])
            html += check_row("TYT Fen (20)", self.sp_fen.value(), ref["TYT_FEN"])
            
            if alan == "SAY":
                html += check_row("AYT Matematik (40)", self.sp_a1.value(), ref["AYT_MAT"])
                html += check_row("AYT Fizik (14)", self.sp_a2.value(), ref["AYT_FIZIK"])
                html += check_row("AYT Kimya (13)", self.sp_a3.value(), ref["AYT_KIMYA"])
                html += check_row("AYT Biyoloji (13)", self.sp_a4.value(), ref["AYT_BIYO"])
            elif alan == "EA":
                html += check_row("AYT Matematik (40)", self.sp_a1.value(), ref["AYT_MAT"])
                html += check_row("AYT Edebiyat (24)", self.sp_a2.value(), ref["AYT_EDEB"])
                html += check_row("AYT Tarih-1 (10)", self.sp_a3.value(), ref["AYT_TAR1"])
                html += check_row("AYT Coğrafya-1 (6)", self.sp_a4.value(), ref["AYT_COG1"])
            else: # SÖZ
                html += check_row("AYT Edebiyat (24)", self.sp_a1.value(), ref["AYT_EDEB"])
                html += check_row("AYT Tarih-1 (10)", self.sp_a2.value(), ref["AYT_TAR1"])
                html += check_row("AYT Coğrafya-1 (6)", self.sp_a3.value(), ref["AYT_COG1"])
                html += check_row("AYT Tarih-2 (11)", self.sp_a4.value(), ref["AYT_TAR2"])

        html += "</table>"
        
        # Hedef Kıyaslama
        if hasattr(self, "current_target") and self.current_target:
            t = self.current_target
            name = t.get("name", "Hedef")
            html += f"<div style='margin-top:12px; padding:10px; background:#f0fdf4; border-radius:6px; border:1px solid #bbf7d0;'>"
            html += f"<b>🎯 Seçili Hedef Kıyası: {name}</b><br>"
            if "req_net" in t:
                curr = (self.sp_tr.value() + self.sp_sos.value() + self.sp_mat.value() + self.sp_fen.value() + self.sp_a1.value() + self.sp_a2.value())
                diff = curr - t["req_net"]
                c = "#16a34a" if diff >= 0 else "#dc2626"
                html += f"Hedef LGS Net: <b>{t['req_net']}</b> | Senin Netin: <b>{curr:.2f}</b> (<font color='{c}'><b>{diff:+.2f}</b></font>)"
            elif "req_tyt" in t:
                curr_tyt = (self.sp_tr.value() + self.sp_sos.value() + self.sp_mat.value() + self.sp_fen.value())
                curr_ayt = (self.sp_a1.value() + self.sp_a2.value() + self.sp_a3.value() + self.sp_a4.value())
                d_tyt = curr_tyt - t["req_tyt"]
                d_ayt = curr_ayt - t["req_ayt"]
                c_tyt = "#16a34a" if d_tyt >= 0 else "#dc2626"
                c_ayt = "#16a34a" if d_ayt >= 0 else "#dc2626"
                html += f"TYT: {t['req_tyt']} | Senin: <b>{curr_tyt:.1f}</b> (<font color='{c_tyt}'>{d_tyt:+.1f}</font>) &nbsp;•&nbsp; AYT: {t['req_ayt']} | Senin: <b>{curr_ayt:.1f}</b> (<font color='{c_ayt}'>{d_ayt:+.1f}</font>)"
            html += "</div>"

        self.lbl_out.setText(html)

    def _suggest_resources(self):
        alan = self.cmb_alan.currentText()
        is_lgs = (alan == "LGS")
        year = self._get_selected_ref_year()
        ref = get_national_averages(year, is_lgs=is_lgs)
        
        checks = []
        if is_lgs:
            checks = [
                ("LGS Matematik", self.sp_a1, "LGS_MAT"),
                ("LGS Fen Bilimleri", self.sp_a2, "LGS_FEN"),
                ("LGS Türkçe", self.sp_tr, "LGS_TURKCE"),
                ("LGS İnkılap", self.sp_sos, "LGS_INKILAP"),
            ]
        elif alan == "DİL":
            checks = [
                ("YDT Yabancı Dil", self.sp_a1, "YDT_INGILIZCE"),
                ("TYT Matematik", self.sp_mat, "TYT_MAT"),
                ("TYT Türkçe", self.sp_tr, "TYT_TURKCE"),
            ]
        elif alan == "SAY":
            checks = [
                ("AYT Matematik", self.sp_a1, "AYT_MAT"),
                ("AYT Fizik", self.sp_a2, "AYT_FIZIK"),
                ("AYT Kimya", self.sp_a3, "AYT_KIMYA"),
                ("AYT Biyoloji", self.sp_a4, "AYT_BIYO"),
                ("TYT Matematik", self.sp_mat, "TYT_MAT"),
                ("TYT Fen", self.sp_fen, "TYT_FEN"),
            ]
        elif alan == "EA":
            checks = [
                ("AYT Matematik", self.sp_a1, "AYT_MAT"),
                ("AYT Edebiyat", self.sp_a2, "AYT_EDEB"),
                ("TYT Matematik", self.sp_mat, "TYT_MAT"),
                ("AYT Tarih-1", self.sp_a3, "AYT_TAR1"),
            ]
        else: # SÖZ
            checks = [
                ("AYT Edebiyat", self.sp_a1, "AYT_EDEB"),
                ("AYT Sosyal-2", self.sp_a4, "AYT_TAR2"),
                ("TYT Türkçe", self.sp_tr, "TYT_TURKCE"),
            ]

        deficits = []
        for name, spin, key in checks:
            ref_val = ref.get(key, 0)
            val = spin.value()
            diff = ref_val - val
            deficits.append((name, diff, val, ref_val))

        # En kritik 3 alanı seç
        deficits.sort(key=lambda x: x[1], reverse=True)
        top3 = deficits[:3]

        dlg = QDialog(self)
        dlg.setWindowTitle("♟️ Nokta Atışı: Kritik Alanlar ve Kaynak Önerileri")
        dlg.setMinimumWidth(480)
        dlg.setStyleSheet("QDialog { background-color: #f8fafc; }")
        
        d_lay = QVBoxLayout(dlg)
        d_lay.setSpacing(14)
        d_lay.setContentsMargins(20, 20, 20, 20)
        
        t_lbl = QLabel(f"📢 {alan} İçin Öncelikli Çalışılması Gereken Alanlar")
        t_lbl.setStyleSheet("font-size:15px; font-weight:bold; color:#1e40af;")
        d_lay.addWidget(t_lbl)
        
        d_lay.addWidget(QLabel("Mevcut netlerinize ve Türkiye ortalamalarına göre en çok puan kazandıracak dersler:"))
        
        for name, diff, my_val, ref_val in top3:
            card = QFrame()
            card.setStyleSheet("background:white; border:1px solid #e2e8f0; border-radius:8px; padding:6px;")
            c_lay = QHBoxLayout(card)
            
            if diff > 0:
                sub = f"<span style='color:#dc2626; font-size:11px;'>Ortalamanın <b>{diff:.1f} net</b> gerisindesin (Sen: {my_val:.1f} / Ort: {ref_val:.1f})</span>"
            else:
                sub = f"<span style='color:#16a34a; font-size:11px;'>Ortalamanın <b>{abs(diff):.1f} net</b> önündesin, netini zirveye taşı!</span>"
                
            info = QLabel(f"<b>{name}</b><br>{sub}")
            info.setStyleSheet("border:none;")
            c_lay.addWidget(info, 1)
            
            btn_yt = QPushButton("📺 Taktikler & Video")
            btn_yt.setStyleSheet("background:#dc2626; color:white; font-weight:bold; border-radius:6px; padding:6px 12px;")
            btn_yt.setCursor(Qt.CursorShape.PointingHandCursor)
            
            def make_open(query_name=name):
                return lambda: QDesktopServices.openUrl(QUrl(f"https://www.youtube.com/results?search_query={query_name}+net+artırma+taktikleri+2025+2026"))
                
            btn_yt.clicked.connect(make_open(name))
            c_lay.addWidget(btn_yt)
            
            d_lay.addWidget(card)
            
        d_lay.addStretch()
        btn_ok = QPushButton("Kapat")
        btn_ok.setStyleSheet("background:#334155; color:white; font-weight:bold; padding:8px; border-radius:6px;")
        btn_ok.clicked.connect(dlg.accept)
        d_lay.addWidget(btn_ok)
        
        dlg.exec()
