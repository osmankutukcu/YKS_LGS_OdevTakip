from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QWidget, QMessageBox,
    QInputDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QDateTimeEdit, QCalendarWidget, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QSize, QTimer, QDate
from PyQt6.QtGui import QPainter, QPen, QColor
import datetime
import db


# -----------------------------
# Mini Risk Grafiği (Sparkline)
# -----------------------------
class RiskSparkline(QWidget):
    """
    7 günlük risk değerlerini (0-100) minik sparkline olarak çizer.
    points: list[int|None] (None => o gün snapshot yok)
    """
    def __init__(self, points=None, parent=None):
        super().__init__(parent)
        self.points = points or []
        self.setFixedSize(120, 30)

    def set_points(self, points):
        self.points = points or []
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w, h = self.width(), self.height()
        pad = 3

        if not self.points or len(self.points) < 2:
            pen = QPen(QColor("#94A3B8"))
            pen.setWidth(2)
            p.setPen(pen)
            p.drawLine(pad, h // 2, w - pad, h // 2)
            return

        def y_from(v):
            v = max(0, min(100, int(v)))
            return pad + int((100 - v) * (h - 2 * pad) / 100)

        n = len(self.points)
        xs = [pad + int(i * (w - 2 * pad) / (n - 1)) for i in range(n)]

        pen = QPen(QColor("#0F172A"))
        pen.setWidth(2)
        p.setPen(pen)

        last = None
        for i in range(n):
            v = self.points[i]
            if v is None:
                continue
            x, y = xs[i], y_from(v)
            if last is not None:
                p.drawLine(last[0], last[1], x, y)
            last = (x, y)

        pen2 = QPen(QColor("#0F172A"))
        pen2.setWidth(4)
        p.setPen(pen2)
        for i in range(n):
            v = self.points[i]
            if v is None:
                continue
            p.drawPoint(xs[i], y_from(v))


# -----------------------------
# Risk Detay Penceresi
# -----------------------------
# -----------------------------
# Detay Penceresi (Risk / Başarı)
# -----------------------------
class RiskDetailDialog(QDialog):
    def __init__(self, student_name: str, risk_points: list, reasons=None, dtype="risk", parent=None):
        super().__init__(parent)
        self.dtype = dtype
        
        title_text = "Risk Detayı"
        graph_title = f"📊 {student_name} • Son 7 Gün Risk Grafiği"
        
        if dtype == "star":
            title_text = "Başarı Detayı"
            graph_title = f"🌟 {student_name} • Haftalık Başarı/Risk Grafiği"
        elif dtype == "birthday":
            title_text = "Doğum Günü"
            graph_title = f"🎂 {student_name} • Durum Özeti"

        self.setWindowTitle(title_text)
        self.resize(430, 280)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel(graph_title)
        title.setStyleSheet("font-size: 14px; font-weight: 700; color: #0F172A;")
        layout.addWidget(title)

        spark = RiskSparkline(risk_points)
        spark.setFixedSize(370, 70)
        layout.addWidget(spark, alignment=Qt.AlignmentFlag.AlignCenter)

        vals = [v for v in risk_points if isinstance(v, int)]
        if vals:
            avg = sum(vals) / len(vals)
            last = vals[-1]
            info = QLabel(f"Ortalama Risk Puanı: {avg:.1f} • Güncel: {last}")
            info.setStyleSheet("color:#334155;")
            info.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(info)

        if reasons:
            hdr = "🤖 Neden bu öneri gösterildi?"
            if dtype == "star": hdr = "🌟 Neden 'Haftanın Yıldızı' seçildi?"
            
            layout.addWidget(QLabel(hdr))
            box = QLabel("• " + "\n• ".join(reasons))
            box.setWordWrap(True)
            box.setStyleSheet(
                "background:#F1F5F9; border:1px solid #CBD5E1; border-radius:10px; padding:10px; color:#0F172A;"
            )
            layout.addWidget(box)

        btn = QPushButton("Kapat")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignRight)


# -----------------------------
# Tarih Zaman Seçici (Custom)
# -----------------------------
class DateTimeSelectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Zamanlama Seç")
        self.resize(320, 200)
        
        layout = QVBoxLayout(self)
        
        lbl = QLabel("Mesajın gönderileceği zaman:")
        layout.addWidget(lbl)
        
        self.dt_edit = QDateTimeEdit(datetime.datetime.now())
        self.dt_edit.setCalendarPopup(True) # Takvim açılır
        self.dt_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        # Biraz daha büyük font
        self.dt_edit.setStyleSheet("font-size: 14px; padding: 5px;")
        layout.addWidget(self.dt_edit)
        
        # Hazır butonlar (+1 saat, +1 gün gibi)
        quick_layout = QHBoxLayout()
        btn_1h = QPushButton("+1 Saat")
        btn_tmrw = QPushButton("Yarın sabah")
        
        btn_1h.clicked.connect(self._add_1_hour)
        btn_tmrw.clicked.connect(self._set_tomorrow_morning)
        
        quick_layout.addWidget(btn_1h)
        quick_layout.addWidget(btn_tmrw)
        layout.addLayout(quick_layout)

        layout.addStretch()

        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bbox.accepted.connect(self.accept)
        bbox.rejected.connect(self.reject)
        layout.addWidget(bbox)
    
    def _add_1_hour(self):
        cur = self.dt_edit.dateTime().toPyDateTime()
        new_dt = cur + datetime.timedelta(hours=1)
        self.dt_edit.setDateTime(new_dt)
        
    def _set_tomorrow_morning(self):
        cur = datetime.datetime.now()
        tmrw = cur + datetime.timedelta(days=1)
        tmrw = tmrw.replace(hour=9, minute=30, second=0)
        self.dt_edit.setDateTime(tmrw)

    def get_datetime(self):
        return self.dt_edit.dateTime().toPyDateTime()



# -----------------------------
# WhatsApp Zamanlama Kuyruğu
# -----------------------------
class WhatsAppQueueDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔔 WhatsApp Zamanlama Kuyruğu")
        self.resize(780, 360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["ID", "Öğrenci", "Telefon", "Tür", "Gönderim Zamanı", "Durum", "Mesaj (kısa)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        self.btn_refresh = QPushButton("🔄 Yenile")
        self.btn_cancel = QPushButton("🗑️ Seçileni İptal Et")
        self.btn_close = QPushButton("Kapat")
        btn_row.addWidget(self.btn_refresh)
        btn_row.addWidget(self.btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_close)
        layout.addLayout(btn_row)

        self.btn_close.clicked.connect(self.accept)
        self.btn_refresh.clicked.connect(self.load)
        self.btn_cancel.clicked.connect(self.cancel_selected)

        self.load()

    def load(self):
        con = db.get_conn()
        try:
            rows = con.execute("""
                SELECT id, student_name, phone, stype, send_at, status, message
                FROM whatsapp_queue
                ORDER BY datetime(send_at) ASC
                LIMIT 200
            """).fetchall()
        except:
             return

        self.table.setRowCount(0)
        for r in rows:
            row_i = self.table.rowCount()
            self.table.insertRow(row_i)

            msg_short = (r["message"] or "")[:80].replace("\n", " ")
            items = [
                str(r["id"]),
                r["student_name"] or "",
                r["phone"] or "",
                r["stype"] or "",
                r["send_at"] or "",
                r["status"] or "",
                msg_short
            ]
            for c, val in enumerate(items):
                self.table.setItem(row_i, c, QTableWidgetItem(val))

    def cancel_selected(self):
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.information(self, "Seçim Yok", "İptal etmek için bir satır seçin.")
            return
        row = selected[0].row()
        qid = self.table.item(row, 0).text()

        con = db.get_conn()
        con.execute("UPDATE whatsapp_queue SET status='cancelled' WHERE id=?", (qid,))
        con.commit()
        self.load()


# ============================
# Smart Assistant (Gelişmiş)
# ============================
class SmartAssistantDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("YKS/LGS Akıllı Koç Asistanı")
        self.resize(660, 780)
        self.setMinimumWidth(630)

        self.setStyleSheet("""
            QDialog { background-color: #F8FAFC; }
            QLabel#Title {
                font-family: 'Segoe UI', sans-serif;
                font-size: 22px;
                font-weight: bold;
                color: #1E293B;
            }
            QLabel#Subtitle {
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px;
                color: #64748B;
                margin-bottom: 10px;
            }
            QListWidget { border: none; background-color: transparent; outline: none; }
            QPushButton#RefreshBtn {
                background-color: #EFF6FF;
                color: #3B82F6;
                border: 1px solid #DBEAFE;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: 600;
            }
            QPushButton#RefreshBtn:hover { background-color: #DBEAFE; }
        """)

        self._ensure_tables()

        # -----------------------------
        # WhatsApp kuyruğu işleyici
        # -----------------------------
        self._queue_timer = QTimer(self)
        self._queue_timer.timeout.connect(self._process_whatsapp_queue_tick)
        self._queue_timer.start(20_000)

        # -----------------------------
        # Risk snapshot günlük otomasyon
        # -----------------------------
        self._snapshot_timer = QTimer(self)
        self._snapshot_timer.setSingleShot(True)
        self._snapshot_timer.timeout.connect(self._snapshot_daily_and_reschedule)

        # -----------------------------
        # ✅ Gün içi canlı güncelleme
        # -----------------------------
        self._db_watch_timer = QTimer(self)
        self._db_watch_timer.timeout.connect(self._db_watch_tick)
        self._db_watch_timer.start(10_000)

        self._db_last_data_version = None
        self._snapshot_debounce = QTimer(self)
        self._snapshot_debounce.setSingleShot(True)
        self._snapshot_debounce.timeout.connect(self._force_snapshot_debounced)

        self._last_force_snapshot_at = None
        self._force_cooldown_seconds = 120

        # İlk açılışta garanti et
        self.capture_today_risk_snapshot_if_needed(force=False)
        self.schedule_daily_snapshot(hour=2, minute=10)

        # UI
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 25, 20, 20)

        header_layout = QHBoxLayout()

        title_box = QVBoxLayout()
        title = QLabel("🧠 Günün Akıllı Özeti")
        title.setObjectName("Title")

        d = QDate.currentDate()
        months = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
        days = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        
        # d.dayOfWeek() -> 1=Mon, 7=Sun. Python index 0-6.
        day_str = days[d.dayOfWeek() - 1]
        mon_str = months[d.month() - 1]
        today_str = f"{d.day()} {mon_str} {d.year()}, {day_str}"

        subtitle = QLabel(f"Bugün • {today_str}")
        subtitle.setObjectName("Subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        header_layout.addLayout(title_box)
        header_layout.addStretch()

        self.btn_queue = QPushButton("🔔 Kuyruk")
        self.btn_queue.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_queue.clicked.connect(self.open_queue)
        header_layout.addWidget(self.btn_queue)

        self.btn_refresh = QPushButton("🔄 Taze Oku")
        self.btn_refresh.setObjectName("RefreshBtn")
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh.clicked.connect(self.run_analysis)
        header_layout.addWidget(self.btn_refresh)

        layout.addLayout(header_layout)

        # -----------------------------
        # 🔽 AKILLI FİLTRELER (Smart Filters)
        # -----------------------------
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)
        
        self.filter_btn_group = {}
        filters = [
            ("all", "Tümü"),
            ("risk", "⚠️ Riskler"),
            ("star", "🌟 Başarılar"),
            ("birthday", "🎂 Kutlamalar"),
            ("silent", "👻 Sessizler")
        ]
        
        self.active_filter = "all"

        for f_key, f_label in filters:
            btn = QPushButton(f_label)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            # Modern "Chip" stili butonlar
            btn.setStyleSheet("""
                QPushButton {
                    background-color: white; border: 1px solid #CBD5E1; 
                    border-radius: 15px; padding: 5px 15px; color: #475569; font-weight: 600; font-size: 13px;
                }
                QPushButton:checked {
                    background-color: #3B82F6; border: 1px solid #3B82F6; color: white;
                }
                QPushButton:hover:!checked { background-color: #F1F5F9; }
            """)
            btn.clicked.connect(lambda checked, k=f_key: self._apply_filter(k))
            filter_layout.addWidget(btn)
            self.filter_btn_group[f_key] = btn
        
        self.filter_btn_group["all"].setChecked(True)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        footer_lbl = QLabel("Bu öneriler öğrenci verilerine dayanarak oluşturulmuştur.")
        footer_lbl.setStyleSheet("color: #94A3B8; font-size: 11px; font-style: italic;")
        footer_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer_lbl)

        QTimer.singleShot(120, self.run_analysis)

    def _ensure_tables(self):
        con = db.get_conn()
        con.execute("""
            CREATE TABLE IF NOT EXISTS sistem_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                anahtar TEXT NOT NULL,
                tarih TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS whatsapp_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER,
                student_name TEXT,
                phone TEXT,
                stype TEXT,
                message TEXT,
                send_at TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS risk_snapshot (
                snapshot_date TEXT NOT NULL,
                student_id INTEGER NOT NULL,
                risk_score INTEGER NOT NULL,
                overdue_count INTEGER DEFAULT 0,
                silent_days INTEGER DEFAULT 0,
                completed_last_week INTEGER DEFAULT 0,
                birthday_today INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (snapshot_date, student_id)
            )
        """)
        con.commit()

    def notify_data_changed(self):
        self._schedule_force_snapshot(reason="manual-notify")

    def _db_watch_tick(self):
        try:
            con = db.get_conn()
            r = con.execute("PRAGMA data_version").fetchone()
            if not r: return
            current = None
            try: current = int(r[0])
            except: 
                try: current = int(list(r)[0])
                except: return

            if self._db_last_data_version is None:
                self._db_last_data_version = current
                return
            if current != self._db_last_data_version:
                self._db_last_data_version = current
                self._schedule_force_snapshot(reason="db-change-detected")
        except: 
            pass

    def _schedule_force_snapshot(self, reason: str = ""):
        self._snapshot_debounce.start(7_000)

    def _force_snapshot_debounced(self):
        now = datetime.datetime.now()
        if self._last_force_snapshot_at is not None:
            delta = (now - self._last_force_snapshot_at).total_seconds()
            if delta < self._force_cooldown_seconds:
                return
        self._last_force_snapshot_at = now
        self.capture_today_risk_snapshot_if_needed(force=True)
        if self.isVisible():
            self.run_analysis()

    def schedule_daily_snapshot(self, hour: int = 2, minute: int = 10):
        now = datetime.datetime.now()
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_run <= now:
            next_run = next_run + datetime.timedelta(days=1)
        ms = int((next_run - now).total_seconds() * 1000)
        self._snapshot_timer.start(ms)

    def _snapshot_daily_and_reschedule(self):
        try:
            self.capture_today_risk_snapshot_if_needed(force=True)
        finally:
            self.schedule_daily_snapshot(hour=2, minute=10)

    def capture_today_risk_snapshot_if_needed(self, force: bool = False):
        con = db.get_conn()
        today = datetime.date.today().isoformat()
        row = con.execute("SELECT 1 FROM risk_snapshot WHERE snapshot_date=? LIMIT 1", (today,)).fetchone()
        if row and not force:
            return
        students = con.execute("SELECT id FROM ogrenci WHERE aktif=1").fetchall()
        for s in students:
            sid = int(s["id"])
            sig = self._compute_signals_for_student(sid)
            risk = self.compute_risk_score(sig)
            con.execute("""
                INSERT INTO risk_snapshot (
                    snapshot_date, student_id, risk_score,
                    overdue_count, silent_days, completed_last_week, birthday_today
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(snapshot_date, student_id) DO UPDATE SET
                    risk_score=excluded.risk_score,
                    overdue_count=excluded.overdue_count,
                    silent_days=excluded.silent_days,
                    completed_last_week=excluded.completed_last_week,
                    birthday_today=excluded.birthday_today,
                    created_at=datetime('now')
            """, (today, sid, int(risk),
                  int(sig.get("overdue_count", 0)),
                  int(sig.get("silent_days", 0)),
                  int(sig.get("completed_last_week", 0)),
                  1 if sig.get("birthday_today", False) else 0))
        con.commit()

    def compute_risk_score(self, signals: dict) -> int:
        score = 0
        overdue = int(signals.get("overdue_count", 0))
        silent_days = int(signals.get("silent_days", 0))
        done_week = int(signals.get("completed_last_week", 0))
        birthday_today = bool(signals.get("birthday_today", False))
        score += min(overdue * 8, 40)
        score += 20 if silent_days >= 14 else 0
        score -= min(done_week * 5, 20)
        score += 10 if birthday_today else 0
        return max(0, min(score, 100))

    def get_weekly_risk_points(self, student_id: int) -> list:
        con = db.get_conn()
        today = datetime.date.today()
        start = today - datetime.timedelta(days=6)
        rows = con.execute("""
            SELECT snapshot_date, risk_score
            FROM risk_snapshot
            WHERE student_id=?
              AND date(snapshot_date) BETWEEN date(?) AND date(?)
            ORDER BY date(snapshot_date) ASC
        """, (student_id, start.isoformat(), today.isoformat())).fetchall()
        mp = {r["snapshot_date"]: int(r["risk_score"]) for r in rows}
        pts = []
        for i in range(7):
            d = (start + datetime.timedelta(days=i)).isoformat()
            pts.append(mp.get(d, None))
        return pts

    def _compute_signals_for_student(self, student_id: int) -> dict:
        con = db.get_conn()
        row = con.execute("SELECT dogum_tarihi FROM ogrenci WHERE id=?", (student_id,)).fetchone()
        birthday_today = False
        if row and row["dogum_tarihi"]:
            dob_str = row["dogum_tarihi"]
            try:
                if "-" in dob_str:
                    dt_dob = datetime.datetime.strptime(dob_str, "%Y-%m-%d").date()
                elif "." in dob_str:
                    dt_dob = datetime.datetime.strptime(dob_str, "%d.%m.%Y").date()
                else: dt_dob = None
                if dt_dob:
                    t = datetime.date.today()
                    birthday_today = (dt_dob.month == t.month and dt_dob.day == t.day)
            except: pass

        r_over = con.execute("""
            SELECT COUNT(*) AS c
            FROM odev o
            JOIN odev_kume k ON k.id=o.kume_id
            WHERE o.ogrenci_id=? AND o.durum='devam'
              AND date(k.bitis_tarihi) < date('now')
              AND date(k.bitis_tarihi) > date('now', '-30 days')
        """, (student_id,)).fetchone()
        overdue_count = int(r_over["c"]) if r_over else 0

        r_last = con.execute("""
            SELECT MAX(date(verilis_tarihi)) AS d
            FROM odev_kume WHERE ogrenci_id=?
        """, (student_id,)).fetchone()
        silent_days = 999
        if r_last and r_last["d"]:
            try:
                last_date = datetime.date.fromisoformat(r_last["d"])
                silent_days = (datetime.date.today() - last_date).days
            except: silent_days = 999

        r_done = con.execute("""
            SELECT COUNT(*) AS c
            FROM odev o
            WHERE o.ogrenci_id=?
              AND o.durum IN ('tamam','yapildi','bitti')
              AND o.kume_id IN (
                SELECT id FROM odev_kume
                WHERE date(verilis_tarihi) > date('now', '-7 days')
              )
        """, (student_id,)).fetchone()
        completed_last_week = int(r_done["c"]) if r_done else 0

        r_problem = con.execute("""
            SELECT o.ders, COUNT(*) as c
            FROM odev o
            JOIN odev_kume k ON k.id=o.kume_id
            WHERE o.ogrenci_id=? AND o.durum='devam'
              AND date(k.bitis_tarihi) < date('now')
            GROUP BY o.ders
            ORDER BY c DESC LIMIT 1
        """, (student_id,)).fetchone()
        problem_lesson = r_problem["ders"] if r_problem else None
        problem_count = int(r_problem["c"]) if r_problem else 0

        r_best = con.execute("""
            SELECT o.ders, COUNT(*) as c
            FROM odev o
            JOIN odev_kume k ON k.id=o.kume_id
            WHERE o.ogrenci_id=? 
              AND o.durum IN ('tamam','yapildi','bitti')
              AND date(k.verilis_tarihi) > date('now', '-7 days')
            GROUP BY o.ders
            ORDER BY c DESC LIMIT 1
        """, (student_id,)).fetchone()
        best_lesson = r_best["ders"] if r_best else None
        best_count = int(r_best["c"]) if r_best else 0

        # En son yapılan iş (Tarih ve Ders)
        last_date_str = None
        last_lesson_name = None
        if r_last and r_last["d"]:
             last_date_str = r_last["d"]
             # O tarihteki dersi bulalım
             r_last_d = con.execute("""
                SELECT ders FROM odev_kume k
                JOIN odev o ON o.kume_id = k.id
                WHERE k.ogrenci_id=? AND date(k.verilis_tarihi) = ?
                LIMIT 1
             """, (student_id, last_date_str)).fetchone()
             if r_last_d: last_lesson_name = r_last_d["ders"]

        return {
            "overdue_count": overdue_count,
            "silent_days": silent_days,
            "completed_last_week": completed_last_week,
            "birthday_today": birthday_today,
            "problem_lesson": problem_lesson,
            "problem_count": problem_count,
            "best_lesson": best_lesson,
            "best_count": best_count,
            "last_date": last_date_str,
            "last_lesson": last_lesson_name
        }

    def should_show_today(self, key: str, min_days_gap: int = 3) -> bool:
        # TEST MODU: Her zaman göster
        return True
        """
        con = db.get_conn()
        row = con.execute(
            "SELECT tarih FROM sistem_log WHERE anahtar=? ORDER BY tarih DESC LIMIT 1",
            (key,)
        ).fetchone()
        if not row: return True
        try:
            last = datetime.datetime.fromisoformat(row["tarih"]).date()
            return (datetime.date.today() - last).days >= min_days_gap
        except: return True
        """

    def log_shown(self, key: str):
        con = db.get_conn()
        con.execute("INSERT INTO sistem_log (anahtar, tarih) VALUES (?, ?)",
                    (key, datetime.datetime.now().isoformat()))
        con.commit()

    def suppress_conflicts(self, suggestions):
        seen = set()
        out = []
        for s in sorted(suggestions, key=lambda x: x["priority"]):
            r = s.get("data") or {}
            if hasattr(r, "keys"):
                r = dict(r)
            sid = r.get("id") or r.get("ogrenci_id") if isinstance(r, dict) else None
            if not sid:
                out.append(s)
                continue
            if sid in seen:
                continue
            seen.add(sid)
            out.append(s)
        return out

    def ai_generate_message(self, stype: str, student_name: str, reasons: list[str], base_message: str) -> str:
        reason_text = "\n" + "\n".join([f"• {x}" for x in reasons]) if reasons else ""
        if stype == "overdue":
            return base_message + "\n\n🔎 Bu mesaj, takip verilerine göre otomatik oluşturuldu." + reason_text
        if stype == "silent":
            return base_message + "\n\n🔎 Son günlerde akış az göründüğü için kontrol amaçlıdır." + reason_text
        if stype == "star":
            return base_message + "\n\n💡 Bu sonuç, son 7 gün tamamlanan çalışmalara göre hesaplandı." + reason_text
        if stype == "birthday":
            return base_message + "\n\n🎉 Mutlu yıllar dileklerimizle!" + reason_text
        return base_message

    def schedule_whatsapp(self, student_id: int | None, student_name: str, phone: str, stype: str,
                          message: str, send_at: datetime.datetime):
        con = db.get_conn()
        con.execute("""
            INSERT INTO whatsapp_queue (student_id, student_name, phone, stype, message, send_at, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
        """, (student_id, student_name, phone, stype, message, send_at.isoformat(timespec="seconds")))
        con.commit()

    def open_queue(self):
        dlg = WhatsAppQueueDialog(self)
        dlg.exec()

    def _process_whatsapp_queue_tick(self):
        try:
            con = db.get_conn()
            rows = con.execute("""
                SELECT id, student_name, phone, stype, message, send_at
                FROM whatsapp_queue
                WHERE status='pending' AND datetime(send_at) <= datetime('now')
                ORDER BY datetime(send_at) ASC
                LIMIT 3
            """).fetchall()
            if not rows: return
            for r in rows:
                qid = r["id"]
                con.execute("UPDATE whatsapp_queue SET status='sending' WHERE id=?", (qid,))
                con.commit()
                try:
                    from ui.whatsapp_sender_dialog import WhatsAppGonderDialog
                    target = [(r["student_name"], r["phone"])]
                    dlg = WhatsAppGonderDialog(alicilar=target, mesaj=r["message"], parent=self)
                    dlg.exec()
                    con.execute("UPDATE whatsapp_queue SET status='sent' WHERE id=?", (qid,))
                    con.commit()
                except ImportError:
                    con.execute("UPDATE whatsapp_queue SET status='failed' WHERE id=?", (qid,))
                    con.commit()
                except Exception:
                    con.execute("UPDATE whatsapp_queue SET status='failed' WHERE id=?", (qid,))
                    con.commit()
        except: pass

    def _apply_filter(self, key):
        self.active_filter = key
        for k, btn in self.filter_btn_group.items():
            btn.setChecked(k == key)
        self.refresh_ui_list()

    def run_analysis(self):
        self.capture_today_risk_snapshot_if_needed(force=False)
        self.list_widget.clear()
        
        self.all_suggestions = [] # Reset data

        item = QListWidgetItem()
        loading_lbl = QLabel("Veriler analiz ediliyor...\nTrendler hesaplanıyor...")
        loading_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_lbl.setStyleSheet("color: #64748B; margin-top: 20px; font-size: 14px;")
        item.setSizeHint(QSize(400, 80))
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, loading_lbl)
        
        QTimer.singleShot(100, self._perform_analysis)

    def _perform_analysis(self):
        # self.list_widget.clear()  <-- Artık silmiyoruz, refresh_ui_list silecek
        suggestions = []

        def to_dict(row):
            return {k: row[k] for k in row.keys()} if row else {}

        # Trend hesaplama yardimcisi
        def get_trend_arrow(sid):
            pts = [p for p in self.get_weekly_risk_points(sid) if p is not None]
            if len(pts) < 2: return ""
            prev, curr = pts[-2], pts[-1]
            if curr > prev + 5: return " 📈" # Kötüye gidiş (Risk arttı)
            if curr < prev - 5: return " 📉" # İyiye gidiş (Risk azaldı)
            return "" # " ➖"

        try:
            con = db.get_conn()
            today = datetime.date.today()
            tomorrow = today + datetime.timedelta(days=1)

            rows = con.execute("SELECT id, ad, soyad, dogum_tarihi, veli_tel1 FROM ogrenci WHERE aktif=1").fetchall()
            for r_raw in rows:
                r = to_dict(r_raw)
                dob_str = r['dogum_tarihi']
                if not dob_str: continue
                try:
                    if "-" in dob_str:
                        dt_dob = datetime.datetime.strptime(dob_str, "%Y-%m-%d").date()
                    elif "." in dob_str:
                        dt_dob = datetime.datetime.strptime(dob_str, "%d.%m.%Y").date()
                    else: continue
                    is_today = (dt_dob.month == today.month and dt_dob.day == today.day)
                    is_tmrw = (dt_dob.month == tomorrow.month and dt_dob.day == tomorrow.day)
                    if is_today and self.should_show_today(f"birthday_{r['id']}", min_days_gap=1):
                        suggestions.append({
                            "type": "birthday",
                            "priority": 1,
                            "title": f"İyi ki Doğdun {r['ad']}!",
                            "desc": f"Bugün {r['ad']} {r['soyad']} öğrencimizin doğum günü.",
                            "icon": "🎂",
                            "color": "#FCE7F3",
                            "border": "#EC4899",
                            "action": "Kutla",
                            "data": r,
                            "reasons": ["Doğum tarihi bugün ile eşleşti"],
                        })
                        self.log_shown(f"birthday_{r['id']}")
                    elif is_tmrw and self.should_show_today(f"birthday_tmrw_{r['id']}", min_days_gap=1):
                        suggestions.append({
                            "type": "birthday",
                            "priority": 2,
                            "title": f"Yarın {r['ad']}'in Doğum Günü",
                            "desc": "Yarın için küçük bir sürpriz veya mesaj hazırlayabilirsiniz.",
                            "icon": "🎁",
                            "color": "#F3E8FF",
                            "border": "#A855F7",
                            "action": "Planla",
                            "data": r,
                            "reasons": ["Doğum tarihi yarın ile eşleşti"],
                        })
                        self.log_shown(f"birthday_tmrw_{r['id']}")
                except: pass

            cur = con.execute("""
                SELECT o.ogrenci_id as id, ogr.ad, ogr.soyad, COUNT(*) as gecikme_sayisi, ogr.veli_tel1
                FROM odev o
                JOIN odev_kume k ON k.id = o.kume_id
                JOIN ogrenci ogr ON ogr.id = o.ogrenci_id
                WHERE o.durum = 'devam'
                  AND date(k.bitis_tarihi) < date('now')
                  AND date(k.bitis_tarihi) > date('now', '-30 days')
                GROUP BY o.ogrenci_id
                HAVING gecikme_sayisi >= 5
                ORDER BY gecikme_sayisi DESC
            """)
            for r_raw in cur.fetchall():
                r = to_dict(r_raw)
                key = f"overdue_{r['id']}"
                if not self.should_show_today(key, min_days_gap=3): continue
                sig = self._compute_signals_for_student(r["id"])
                risk = self.compute_risk_score(sig)
                
                # Akıllı Sebep Üretimi
                reasons = [f"Son 30 günde toplam {r['gecikme_sayisi']} ödev gecikti."]
                if sig.get("problem_lesson"):
                    reasons.append(f"⚠️ En çok aksayan ders: {sig['problem_lesson']} ({sig['problem_count']} eksik).")
                
                if sig['silent_days'] >= 7:
                    if sig['silent_days'] > 365:
                        reasons.append(f"⏱️ Uzun süredir sisteme veri girişi yapılmadı.")
                    else:
                        reasons.append(f"⏱️ Son {sig['silent_days']} gündür sisteme veri girişi yapılmadı.")
                elif sig['completed_last_week'] > 0:
                    reasons.append(f"✅ Yine de son 7 günde {sig['completed_last_week']} çalışma tamamladı (Çaba var).")

                trend_icon = get_trend_arrow(r['id'])
                suggestions.append({
                    "type": "overdue",
                    "priority": 3,
                    "title": f"⚠️ {r['ad']} Ödevleri Biriktiriyor{trend_icon}",
                    "desc": f"{sig.get('problem_lesson', 'Genel')} dersinde yoğunlaşan eksikler var. (Risk: {risk}/100)",
                    "icon": "⏳",
                    "color": "#FFEDD5",
                    "border": "#F97316",
                    "action": "Uyar",
                    "data": r,
                    "risk": risk,
                    "reasons": reasons
                })
                self.log_shown(key)

            cur = con.execute("""
                SELECT ogr.id, ogr.ad, ogr.soyad, COUNT(*) as biten, ogr.veli_tel1
                FROM odev o
                JOIN ogrenci ogr ON ogr.id = o.ogrenci_id
                WHERE o.durum IN ('tamam', 'yapildi', 'bitti')
                  AND o.kume_id IN (SELECT id FROM odev_kume WHERE date(verilis_tarihi) > date('now', '-7 days'))
                GROUP BY ogr.id
                ORDER BY biten DESC
                LIMIT 3
            """)
            rank = 1
            for r_raw in cur.fetchall():
                r = to_dict(r_raw)
                if r['biten'] < 5: continue
                key = f"star_{r['id']}"
                if not self.should_show_today(key, min_days_gap=2): continue
                
                sig = self._compute_signals_for_student(r["id"])
                risk = self.compute_risk_score(sig)
                
                # Akıllı Sebep Üretimi
                reasons = [f"Bu hafta toplam {r['biten']} çalışma tamamladı."]
                if sig.get("best_lesson"):
                    reasons.append(f"🔥 En yüksek performans: {sig['best_lesson']} ({sig['best_count']} tamamlandı).")
                
                reasons.append(f"🏆 Haftalık sıralamada {rank}. oldu.")
                reasons.append("Düzenli çalışma disiplini koruyor.")

                icon = "🥇" if rank == 1 else ("🥈" if rank == 2 else "🥉")
                trend_icon = get_trend_arrow(r['id'])
                
                suggestions.append({
                    "type": "star",
                    "priority": 4,
                    "title": f"{icon} Haftanın Yıldızı: {r['ad']}{trend_icon}",
                    "desc": f"{sig.get('best_lesson', 'Genel')} dersinde harika gidiyor! (Başarı Puanı: {100-risk})",
                    "icon": "🌟",
                    "color": "#FEF3C7",
                    "border": "#F59E0B",
                    "action": "Tebrik Et",
                    "data": r,
                    "risk": risk,
                    "reasons": reasons
                })
                self.log_shown(key)
                rank += 1

            cur = con.execute("""
                SELECT id, ad, soyad, veli_tel1
                FROM ogrenci
                WHERE aktif=1
                  AND id NOT IN (
                      SELECT DISTINCT ogrenci_id
                      FROM odev_kume
                      WHERE date(verilis_tarihi) > date('now', '-14 days')
                  )
            """)
            for r_raw in cur.fetchall():
                r = to_dict(r_raw)
                key = f"silent_{r['id']}"
                if not self.should_show_today(key, min_days_gap=4): continue
                sig = self._compute_signals_for_student(r["id"])
                risk = self.compute_risk_score(sig)
                
                if sig['silent_days'] > 365:
                    day_text = "Uzun süredir"
                    desc_text = "Sisteme henüz veri girişi yapılmamış veya çok eski."
                else:
                    day_text = f"Son {sig['silent_days']} gündür"
                    desc_text = f"Son {sig['silent_days']} gündür hareket yok."

                reasons = [
                    f"{day_text} yeni ödev/çalışma girişi yok.",
                ]
                if sig.get("last_date"):
                    reasons.append(f"📅 En son işlem: {sig['last_date']} ({sig.get('last_lesson', 'Bilinmeyen Ders')})")
                else:
                    reasons.append("⚠️ Öğrenciye ait geçmiş kayıt bulunamadı.")
                
                if sig['overdue_count'] > 0:
                     reasons.append(f"❌ Ayrıca {sig['overdue_count']} birikmiş eski ödevi var.")

                trend_icon = get_trend_arrow(r['id'])
                suggestions.append({
                    "type": "silent",
                    "priority": 2,
                    "title": f"👻 {r['ad']} Unutuldu mu?{trend_icon}",
                    "desc": desc_text + (f" En son {sig.get('last_lesson', '')} çalışılmış." if sig.get("last_lesson") else ""),
                    "icon": "🕸️",
                    "color": "#F1F5F9",
                    "border": "#64748B",
                    "action": "Planla",
                    "data": r,
                    "risk": risk,
                    "reasons": reasons
                })
                self.log_shown(key)

        except Exception as e:
            suggestions.append({
                "type": "error",
                "priority": 0,
                "title": "Sorgu Hatası",
                "desc": str(e),
                "icon": "❌",
                "color": "#FEE2E2",
                "border": "red",
                "action": None,
                "reasons": [str(e)]
            })

        suggestions = self.suppress_conflicts(suggestions)
        suggestions.sort(key=lambda x: x['priority'])
        
        self.all_suggestions = suggestions
        self.refresh_ui_list()

    def refresh_ui_list(self):
        self.list_widget.clear()
        
        filtered = []
        if self.active_filter == "all":
            filtered = self.all_suggestions
        elif self.active_filter == "risk":
            filtered = [s for s in self.all_suggestions if s["type"] == "overdue"]
        elif self.active_filter == "star":
            filtered = [s for s in self.all_suggestions if s["type"] == "star"]
        elif self.active_filter == "birthday":
            filtered = [s for s in self.all_suggestions if s["type"] == "birthday"]
        elif self.active_filter == "silent":
            filtered = [s for s in self.all_suggestions if s["type"] == "silent"]

        if not filtered:
            if self.active_filter == "all":
                self._add_empty_state()
            else:
                item = QListWidgetItem()
                lbl = QLabel("Bu kategoride öneri yok ✅")
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setStyleSheet("color: #94A3B8; margin-top: 30px; font-size: 14px;")
                item.setSizeHint(QSize(400, 80))
                self.list_widget.addItem(item)
                self.list_widget.setItemWidget(item, lbl)
            return

        for data in filtered:
            self._add_card(data)


    
    def _add_card(self, data):
        item = QListWidgetItem()
        widget = QWidget()

        widget.setStyleSheet(f"""
            QWidget#Card {{
                background-color: {data['color']};
                border: 1px solid {data['border']};
                border-radius: 12px;
            }}
            QLabel#Icon {{ font-size: 28px; background: transparent; border: none; }}
            QLabel#Title {{
                font-size: 15px; font-weight: bold; color: #1E293B;
                font-family: 'Segoe UI'; border: none; background: transparent;
            }}
            QLabel#Desc {{
                font-size: 13px; color: #475569;
                font-family: 'Segoe UI'; border: none; background: transparent;
            }}
            QPushButton#ActionBtn {{
                background-color: white;
                color: {data['border']};
                border: 1.5px solid {data['border']};
                border-radius: 7px;
                font-weight: 600;
                font-size: 12px;
                padding: 2px 8px;
            }}
            QPushButton#ActionBtn:hover {{
                background-color: {data['border']};
                color: white;
            }}
            QPushButton#WhyBtn {{
                background-color: rgba(255, 255, 255, 0.75);
                color: #334155;
                border: 1px dashed #94A3B8;
                border-radius: 7px;
                font-weight: 500;
                font-size: 12px;
                padding: 2px 8px;
            }}
            QPushButton#WhyBtn:hover {{
                background-color: white;
                border: 1px solid #64748B;
                color: #0F172A;
            }}
        """)
        widget.setObjectName("Card")

        h_layout = QHBoxLayout(widget)
        h_layout.setContentsMargins(15, 15, 15, 15)
        h_layout.setSpacing(12)

        lbl_icon = QLabel(data['icon'])
        lbl_icon.setObjectName("Icon")
        lbl_icon.setFixedSize(40, 40)
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h_layout.addWidget(lbl_icon)

        v_layout = QVBoxLayout()
        v_layout.setSpacing(3)

        lbl_title = QLabel(data['title'])
        lbl_title.setObjectName("Title")

        lbl_desc = QLabel(data['desc'])
        lbl_desc.setObjectName("Desc")
        lbl_desc.setWordWrap(True)

        v_layout.addWidget(lbl_title)
        v_layout.addWidget(lbl_desc)

        sid = (data.get("data") or {}).get("id") or (data.get("data") or {}).get("ogrenci_id")
        if sid:
            pts = self.get_weekly_risk_points(int(sid))
            valid_pts = [p for p in pts if p is not None]

            row = QHBoxLayout()
            row.setSpacing(8)
            row.addWidget(QLabel("Haftalık Risk:"))

            if not valid_pts:
                lbl_info = QLabel("Henüz analiz verisi yok ⏳")
                lbl_info.setStyleSheet("font-size: 11px; color: #94A3B8; font-style: italic;")
                row.addWidget(lbl_info)
            elif len(valid_pts) < 2:
                # Tek veri var, grafik çizilmez
                val = valid_pts[-1]
                lbl_val = QLabel(f"Risk Puanı: {val}/100")
                lbl_val.setToolTip("Risk Puanı Nedir?\n• 0-30: Düşük Risk (Güvenli)\n• 30-70: Orta Risk (Takip Gerekir)\n• 70-100: Yüksek Risk (Müdahale Gerekir)")
                lbl_val.setStyleSheet("font-weight: bold; color: #475569;")
                row.addWidget(lbl_val)
                
                lbl_info = QLabel("(Trend için veri bekleniyor)")
                lbl_info.setStyleSheet("font-size: 10px; color: #94A3B8; font-style: italic;")
                row.addWidget(lbl_info)
            else:
                # Yeterli veri var
                row.addWidget(RiskSparkline(pts))
                
                # Yanına son durumu ok işaretiyle koyalım
                last = valid_pts[-1]
                prev = valid_pts[-2]
                diff = last - prev
                
                arrow = ""
                if diff > 0: arrow = "🔺" # Risk artıyor
                elif diff < 0: arrow = "🔻" # Risk azalıyor
                
                lbl_trend = QLabel(f"{last} {arrow}")
                lbl_trend.setStyleSheet("font-weight: bold; color: #334155;")
                row.addWidget(lbl_trend)

            row.addStretch()
            v_layout.addLayout(row)

        h_layout.addLayout(v_layout)
        h_layout.addStretch()

        right_col = QVBoxLayout()
        right_col.setSpacing(6)
        right_col.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        if data.get("reasons") and data.get("type") != "error":
            btn_why = QPushButton("Neden?")
            btn_why.setObjectName("WhyBtn")
            btn_why.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_why.setFixedSize(110, 26)
            btn_why.clicked.connect(lambda: self.show_why(data))
            right_col.addWidget(btn_why)

        if data.get('action'):
            btn = QPushButton(data['action'])
            btn.setObjectName("ActionBtn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedSize(110, 28)
            btn.clicked.connect(lambda: self.handle_action(data))
            right_col.addWidget(btn)

            btn_time = QPushButton("⏰ Zamanla")
            btn_time.setObjectName("ActionBtn")
            btn_time.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_time.setFixedSize(110, 28)
            btn_time.clicked.connect(lambda: self.handle_schedule(data))
            right_col.addWidget(btn_time)

        h_layout.addLayout(right_col)

        # Dinamik boyut hesaplama
        widget.adjustSize() 
        hint = widget.sizeHint()
        # Kartın içeriğinin (özellikle sağdaki 3 butonun) sıkışmaması için minimum yükseklik garantisi
        card_h = max(hint.height() + 16, 136)
        item.setSizeHint(QSize(560, card_h))
        
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, widget)

    def _add_empty_state(self):
        item = QListWidgetItem()
        w = QLabel(
            "✨ Harika! Şu an acil bir durum görünmüyor.\n\n"
            "📘 Proaktif öneri:\n"
            "• Haftalık tekrar planı oluştur\n"
            "• Mini deneme + eksik konu analizi\n"
            "• Bir sonraki ödev setini önceden planla"
        )
        w.setAlignment(Qt.AlignmentFlag.AlignCenter)
        w.setWordWrap(True)
        w.setStyleSheet("color: #64748B; font-size: 14px; padding: 35px;")
        item.setSizeHint(QSize(400, 170))
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, w)

    def show_why(self, data):
        r = data.get("data", {}) or {}
        if hasattr(r, "keys"):
            r = dict(r)
        name = ((r.get("ad", "") or "") + " " + (r.get("soyad", "") or "")).strip() or (r.get("ad") or "Öğrenci")
        sid = r.get("id") or r.get("ogrenci_id")
        pts = self.get_weekly_risk_points(int(sid)) if sid else []
        
        dtype = data.get("type", "risk")
        dlg = RiskDetailDialog(student_name=name, risk_points=pts, reasons=data.get("reasons", []), dtype=dtype, parent=self)
        dlg.exec()

    def _build_base_message(self, stype: str, ad: str, cnt_text: str = "") -> str:
        if stype == "birthday":
            return (f"Mutlu Yıllar! 🎂\n\n"
                    f"Sevgili {ad} öğrencimizin doğum gününü en içten dileklerimizle kutlar, "
                    f"başarı ve sağlık dolu bir yaş dileriz.")
        if stype == "overdue":
            suffix = f" ({cnt_text} adet gecikme)" if cnt_text else ""
            return (f"Sayın Velimiz,\n\n"
                    f"Öğrencimiz {ad}'in son dönemde ödev teslimlerinde aksamalar olduğunu fark ettik{suffix}. "
                    f"Başarı grafiğini korumak adına evde desteğinizi rica ederiz.")
        if stype == "star":
            return (f"Harika Haber! 🌟\n\n"
                    f"{ad}, bu hafta en çok çalışma tamamlayan öğrencilerimiz arasına girdi! "
                    f"Bu azmini ve başarısını tebrik ediyoruz. 👏")
        if stype == "silent":
            return (f"Sayın Velimiz,\n\n"
                    f"{ad} öğrencimizin ödev girişlerinde bir durgunluk fark ettik. Her şey yolunda mı?")
        return ""

    def handle_action(self, data):
        stype = data.get('type')
        r = data.get('data', {}) or {}
        if hasattr(r, "keys"):
            r = dict(r)
        ad = (r.get('ad', "") or "").strip()
        tel = (r.get('veli_tel1', "") or "").strip()
        sid = r.get("id") or r.get("ogrenci_id")

        if stype == "silent":
            parent = self.parent()
            if parent and hasattr(parent, "select_student_by_id"):
                parent.select_student_by_id(sid)
                self.close()
                return

        if not tel:
            QMessageBox.warning(self, "Eksik Bilgi", f"{ad} öğrencisinin veli telefonu kayıtlı değil.")
            return

        cnt_text = ""
        if stype == "overdue":
            try:
                cnt = data.get("data", {}).get("gecikme_sayisi")
                if cnt is not None:
                    cnt_text = str(cnt)
            except:
                cnt_text = ""

        base_msg = self._build_base_message(stype, ad, cnt_text)
        final_msg = self.ai_generate_message(stype, ad, data.get("reasons", []), base_msg)

        try:
            from ui.whatsapp_sender_dialog import WhatsAppGonderDialog
            target = [(ad, tel)]
            dlg = WhatsAppGonderDialog(alicilar=target, mesaj=final_msg, parent=self)
            dlg.exec()
        except ImportError:
            QMessageBox.warning(self, "Hata", "WhatsApp modülü yüklenemedi (ui.homework_form bulunamadı).")
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"İşlem sırasında hata oluştu:\n{e}")

    def handle_schedule(self, data):
        stype = data.get('type')
        if stype in ("error", None):
            return

        r = data.get("data", {}) or {}
        if hasattr(r, "keys"):
            r = dict(r)
        ad = (r.get('ad', "") or "").strip()
        soyad = (r.get('soyad', "") or "").strip()
        full_name = (ad + " " + soyad).strip()
        tel = (r.get('veli_tel1', "") or "").strip()
        sid = r.get("id") or r.get("ogrenci_id")

        if not tel:
            QMessageBox.warning(self, "Eksik Bilgi", f"{ad} öğrencisinin veli telefonu kayıtlı değil.")
            return

        base_msg = self._build_base_message(stype, ad, "")
        final_msg = self.ai_generate_message(stype, ad, data.get("reasons", []), base_msg)

        # Takvimli dialog aç
        dlg = DateTimeSelectionDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        send_at = dlg.get_datetime()
        if send_at < datetime.datetime.now():
            QMessageBox.warning(self, "Geçersiz Zaman", "Geçmiş bir zamana planlama yapılamaz.")
            return

        self.schedule_whatsapp(
            student_id=int(sid) if sid else None,
            student_name=full_name or ad,
            phone=tel,
            stype=stype,
            message=final_msg,
            send_at=send_at
        )
        QMessageBox.information(self, "Planlandı", f"Mesaj kuyruğa eklendi.\nGönderim: {send_at}")
