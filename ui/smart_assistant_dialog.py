from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QWidget, QMessageBox,
    QInputDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QDateTimeEdit, QCalendarWidget, QDialogButtonBox, QPlainTextEdit, QApplication
)
from PyQt6.QtCore import Qt, QSize, QTimer, QDate
from PyQt6.QtGui import QPainter, QPen, QColor
import datetime
import sqlite3
import db
from services.daily_coach_v10 import collect_student_facts, make_suggestions, tracking_indicator
from services.daily_brief_v11 import (ensure_review_table, load_reviewed, set_reviewed,
                                       review_identity, daily_brief, brief_stats)
from services.daily_followup_v12 import load_open_homework, make_followup_draft, draft_text
from services.plan_profile_store import load_profiles, load_assignments


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
                last = None  # Missing day: don't draw a misleading continuous trend.
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
        
        title_text = "Takip Kaydı Detayı"
        graph_title = f"📊 {student_name} • Son 7 Gün Takip Göstergesi"
        
        if dtype == "star":
            title_text = "Tamamlanan Ödev Kaydı"
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
            info = QLabel(f"Ortalama Takip Göstergesi: {avg:.1f} • Güncel: {last}")
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
        self.btn_retry = QPushButton("↻ Yeniden Onaya Al")
        self.btn_close = QPushButton("Kapat")
        btn_row.addWidget(self.btn_refresh)
        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_retry)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_close)
        layout.addLayout(btn_row)

        self.btn_close.clicked.connect(self.accept)
        self.btn_refresh.clicked.connect(self.load)
        self.btn_cancel.clicked.connect(self.cancel_selected)
        self.btn_retry.clicked.connect(self.retry_selected)

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

    def retry_selected(self):
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.information(self, "Seçim Yok", "Bir mesaj seçin.")
            return
        row = selected[0].row()
        qid = self.table.item(row, 0).text()
        con = db.get_conn()
        try:
            con.execute("UPDATE whatsapp_queue SET status='pending' WHERE id=? AND status='needs_review'", (qid,))
            con.commit()
        finally:
            con.close()
        self.load()

    def cancel_selected(self):
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.information(self, "Seçim Yok", "İptal etmek için bir satır seçin.")
            return
        row = selected[0].row()
        qid = self.table.item(row, 0).text()

        con = db.get_conn()
        con.execute("UPDATE whatsapp_queue SET status='cancelled' WHERE id=? AND status='pending'", (qid,))
        con.commit()
        self.load()


# ============================
# Smart Assistant (Gelişmiş)
# ============================
class SmartAssistantDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("YKS/LGS Akıllı Koç Asistanı")
        self.resize(780, 800)
        self.setMinimumWidth(740)

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

        self._watch_conn = db.get_conn()
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
        filter_layout.setSpacing(6)
        
        self.filter_btn_group = {}
        filters = [
            ("priority", "⭐ Bugünün 5’i"),
            ("all", "Tümü"),
            ("risk", "⚠️ Riskler"),
            ("star", "🌟 Başarılar"),
            ("birthday", "🎂 Kutlamalar"),
            ("silent", "👻 Sessizler")
        ]
        
        self.active_filter = "priority"
        self._reviewed_today = set()

        for f_key, f_label in filters:
            btn = QPushButton(f_label)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            # Modern "Chip" stili butonlar
            btn.setStyleSheet("""
                QPushButton {
                    background-color: white; border: 1px solid #CBD5E1; 
                    border-radius: 14px; padding: 5px 11px; color: #475569; font-weight: 600; font-size: 12px;
                    white-space: nowrap;
                }
                QPushButton:checked {
                    background-color: #3B82F6; border: 1px solid #3B82F6; color: white;
                }
                QPushButton:hover:!checked { background-color: #F1F5F9; }
            """)
            btn.clicked.connect(lambda checked, k=f_key: self._apply_filter(k))
            filter_layout.addWidget(btn)
            self.filter_btn_group[f_key] = btn
        
        self.filter_btn_group["priority"].setChecked(True)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        self.brief_header = QLabel("Öncelikler hazırlanıyor…")
        self.brief_header.setStyleSheet("color:#475569; font-size:12px; font-weight:600;")
        self.brief_header.setWordWrap(True)
        layout.addWidget(self.brief_header)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        footer_lbl = QLabel("Ödev kayıtlarına dayalı öğretmen kontrol listesi. Akademik/psikolojik tanı değildir.")
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
        con.execute("""
            CREATE TABLE IF NOT EXISTS coach_tracking_snapshot_v10 (
                snapshot_date TEXT NOT NULL,
                student_id INTEGER NOT NULL,
                indicator INTEGER NOT NULL,
                overdue_count INTEGER NOT NULL DEFAULT 0,
                assigned_days_ago INTEGER,
                completed_recent_set INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (snapshot_date, student_id)
            )
        """)
        ensure_review_table(con)
        con.commit()
        con.close()

    def done(self, result):
        # Dialog has MainWindow as QObject parent: timers otherwise survive close
        # and can reprocess the WhatsApp queue on subsequent dialog openings.
        for name in ("_queue_timer", "_snapshot_timer", "_db_watch_timer", "_snapshot_debounce"):
            timer = getattr(self, name, None)
            if timer is not None:
                timer.stop()
        conn = getattr(self, "_watch_conn", None)
        self._watch_conn = None
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        super().done(result)

    def notify_data_changed(self):
        self._schedule_force_snapshot(reason="manual-notify")

    def _db_watch_tick(self):
        try:
            # PRAGMA data_version must be read from the SAME persistent
            # connection; a new connection on every poll cannot detect changes.
            r = self._watch_conn.execute("PRAGMA data_version").fetchone()
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
        except Exception:
            try:
                self._watch_conn.close()
            except Exception:
                pass
            self._watch_conn = db.get_conn()
            self._db_last_data_version = None

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
        self._snapshot_timer.start(min(ms, 2_000_000_000))

    def _snapshot_daily_and_reschedule(self):
        try:
            self.capture_today_risk_snapshot_if_needed(force=True)
        finally:
            self.schedule_daily_snapshot(hour=2, minute=10)

    def capture_today_risk_snapshot_if_needed(self, force: bool = False):
        con = db.get_conn()
        try:
            today = datetime.date.today().isoformat()
            if not force:
                exists = con.execute(
                    "SELECT 1 FROM coach_tracking_snapshot_v10 WHERE snapshot_date=? LIMIT 1",
                    (today,)).fetchone()
                if exists:
                    return
            for sig in collect_student_facts(con, datetime.date.today()):
                score = self.compute_risk_score(sig)
                if score is None:
                    continue  # A missing record isn't 0/100 or 20/100 risk.
                con.execute("""
                    INSERT INTO coach_tracking_snapshot_v10
                        (snapshot_date, student_id, indicator, overdue_count,
                         assigned_days_ago, completed_recent_set)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(snapshot_date, student_id) DO UPDATE SET
                        indicator=excluded.indicator,
                        overdue_count=excluded.overdue_count,
                        assigned_days_ago=excluded.assigned_days_ago,
                        completed_recent_set=excluded.completed_recent_set
                    WHERE indicator != excluded.indicator
                       OR overdue_count != excluded.overdue_count
                       OR COALESCE(assigned_days_ago, -1) != COALESCE(excluded.assigned_days_ago, -1)
                       OR completed_recent_set != excluded.completed_recent_set
                """, (today, int(sig['id']), int(score),
                      int(sig.get('overdue_recent') or 0) + int(sig.get('overdue_old') or 0),
                      sig.get('days_since_assigned'),
                      int(sig.get('completed_in_recent_set') or 0)))
            con.commit()
        finally:
            con.close()

    def compute_risk_score(self, signals: dict) -> int | None:
        # Conservative FOLLOW-UP indicator, not academic or psychological risk.
        return tracking_indicator(signals)

    def get_weekly_risk_points(self, student_id: int) -> list:
        con = db.get_conn()
        today = datetime.date.today()
        start = today - datetime.timedelta(days=6)
        rows = con.execute("""
            SELECT snapshot_date, indicator
            FROM coach_tracking_snapshot_v10
            WHERE student_id=?
              AND date(snapshot_date) BETWEEN date(?) AND date(?)
            ORDER BY date(snapshot_date) ASC
        """, (student_id, start.isoformat(), today.isoformat())).fetchall()
        mp = {r["snapshot_date"]: int(r["indicator"]) for r in rows}
        pts = []
        for i in range(7):
            d = (start + datetime.timedelta(days=i)).isoformat()
            pts.append(mp.get(d, None))
        return pts

    def _compute_signals_for_student(self, student_id: int) -> dict:
        con = db.get_conn()
        try:
            return next((f for f in collect_student_facts(con) if int(f['id']) == int(student_id)), {})
        finally:
            con.close()

    def should_show_today(self, key: str, min_days_gap: int = 3) -> bool:
        # Geriye uyumluluk için tutuldu; V10 listeleme bu logu kullanmaz.
        # Görüntülemek bir uyarıyı kapatmaz; yalnızca açık kullanıcı işlemi kapatmalıdır.
        con = db.get_conn()
        row = con.execute(
            "SELECT tarih FROM sistem_log WHERE anahtar=? ORDER BY tarih DESC LIMIT 1",
            (key,)
        ).fetchone()
        if not row: return True
        try:
            last = datetime.datetime.fromisoformat(row["tarih"]).date()
            return (datetime.date.today() - last).days >= min_days_gap
        except Exception: return True

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
            key = (sid, s.get("type"))
            if key in seen:
                continue
            seen.add(key)
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
                claim = con.execute("UPDATE whatsapp_queue SET status='sending' WHERE id=? AND status='pending'", (qid,))
                con.commit()
                if claim.rowcount != 1:
                    continue  # Another active instance claimed this queue item first.
                try:
                    from ui.whatsapp_sender_dialog import WhatsAppGonderDialog
                    target = [(r["student_name"], r["phone"])]
                    dlg = WhatsAppGonderDialog(alicilar=target, mesaj=r["message"], parent=self, auto_send=True)
                    outcome = dlg.exec()
                    if outcome == QDialog.DialogCode.Accepted and not getattr(dlg, "gonderildi", False):
                        dlg.mesajlari_gonder()
                    status = 'sent' if outcome == QDialog.DialogCode.Accepted else 'needs_review'
                    con.execute("UPDATE whatsapp_queue SET status=? WHERE id=?", (status, qid))
                    con.commit()
                    if status == 'needs_review':
                        break  # User did not confirm send; don't immediately re-open.
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
        try:
            con = db.get_conn()
            try:
                facts = collect_student_facts(con)
            finally:
                con.close()
            self.all_suggestions = make_suggestions(facts)
            con = db.get_conn()
            try:
                self._reviewed_today = load_reviewed(con)
            finally:
                con.close()
        except Exception as exc:
            self.all_suggestions = [{
                "type": "error", "priority": 0, "title": "Analiz yapılamadı",
                "desc": str(exc), "icon": "❌", "color": "#FEE2E2",
                "border": "#DC2626", "action": None,
                "reasons": [str(exc)], "data": {}
            }]
        self.refresh_ui_list()

    def refresh_ui_list(self):
        self.list_widget.clear()
        
        errors = [s for s in self.all_suggestions if s.get("type") == "error"]
        if errors:
            self.brief_header.setText("Analiz yapılamadı; detay ve yeniden deneme için aşağıdaki hata kartını inceleyin.")
        else:
            stats = brief_stats(self.all_suggestions, self._reviewed_today)
            self.brief_header.setText(
                f"Bugün: {stats['priority_count']} öncelik  •  "
                f"Gecikme kontrolü: {stats['overdue_students']} öğrenci  •  "
                f"İncelenen: {stats['reviewed_count']}  •  "
                f"Verisi olmayan: {stats['no_history_count']} (bilgi)"
            )
        filtered = []
        if errors:
            filtered = errors
        elif self.active_filter == "priority":
            filtered = daily_brief(self.all_suggestions, self._reviewed_today)
        elif self.active_filter == "all":
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
            elif self.active_filter == "priority":
                item = QListWidgetItem()
                lbl = QLabel("Bugün işlem bekleyen öncelikli kayıt yok.\n"
                             "Diğer kayıtlar için Tümü veya kategori filtrelerini kullanabilirsiniz.")
                lbl.setWordWrap(True)
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setStyleSheet("color:#64748B; padding:18px;")
                item.setSizeHint(QSize(400, 95))
                self.list_widget.addItem(item)
                self.list_widget.setItemWidget(item, lbl)
            else:
                item = QListWidgetItem()
                lbl = QLabel("Bu kategoride öneri yok ✅")
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setStyleSheet("color: #94A3B8; margin-top: 30px; font-size: 14px;")
                item.setSizeHint(QSize(400, 80))
                self.list_widget.addItem(item)
                self.list_widget.setItemWidget(item, lbl)
            return

        max_cards = 5 if self.active_filter == "priority" else (25 if self.active_filter == "all" else 100)
        for data in filtered[:max_cards]:
            self._add_card(data)
        if len(filtered) > max_cards:
            item = QListWidgetItem()
            label = QLabel(f"{len(filtered) - max_cards} ek kayıt var. Kategori filtresiyle görüntüleyebilirsiniz.")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setSizeHint(QSize(400, 52))
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, label)


    
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
            row.addWidget(QLabel("Takip geçmişi:"))

            if not valid_pts:
                lbl_info = QLabel("Henüz analiz verisi yok ⏳")
                lbl_info.setStyleSheet("font-size: 11px; color: #94A3B8; font-style: italic;")
                row.addWidget(lbl_info)
            elif len(valid_pts) < 2:
                # Tek veri var, grafik çizilmez
                val = valid_pts[-1]
                lbl_val = QLabel(f"Takip göstergesi: {val}/100")
                lbl_val.setToolTip("Yalnızca kayıtlardaki açık gecikmelerden türetilen takip göstergesi; akademik başarı ölçümü değildir.")
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
            action_label = ('Ödev Formuna Git' if data.get('type') == 'silent'
                            else 'Kutlama Mesajı' if data.get('type') == 'birthday' and data['action'] == 'Planla'
                            else data['action'])
            btn = QPushButton(action_label)
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

        # V12: A calendar preview is a distinct operation, never a WhatsApp send.
        if data.get('type') in ('overdue', 'silent'):
            btn_plan = QPushButton('📅 Planla')
            btn_plan.setObjectName('ActionBtn')
            btn_plan.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_plan.setFixedSize(110, 28)
            btn_plan.setToolTip('Kayıtlı öğrenci rutininden salt okunur etüt taslağı hazırlar.')
            btn_plan.clicked.connect(lambda checked=False, d=data: self.show_followup_draft(d))
            right_col.addWidget(btn_plan)

        identity = review_identity(data)
        if identity is not None:
            was_reviewed = identity in self._reviewed_today
            btn_review = QPushButton("↶ Geri Al" if was_reviewed else "✓ İnceledim")
            btn_review.setObjectName("ActionBtn")
            btn_review.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_review.setToolTip("Yalnızca bugünkü koçluk kontrol listesini işaretler. Ödevin durumunu değiştirmez.")
            btn_review.setFixedSize(110, 28)
            btn_review.clicked.connect(lambda checked=False, d=data, mark=not was_reviewed: self._set_card_reviewed(d, mark))
            right_col.addWidget(btn_review)

        h_layout.addLayout(right_col)

        # Dinamik boyut hesaplama
        widget.adjustSize() 
        hint = widget.sizeHint()
        # Kartın içeriğinin (özellikle sağdaki 3 butonun) sıkışmaması için minimum yükseklik garantisi
        card_h = max(hint.height() + 16, 136)
        item.setSizeHint(QSize(560, card_h))
        
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, widget)

    def _set_card_reviewed(self, data, reviewed: bool):
        # Explicit teacher review; not a completion or status change.
        con = db.get_conn()
        try:
            ensure_review_table(con)
            if not set_reviewed(con, data, reviewed):
                QMessageBox.information(self, "Kayıt", "Bu kart inceleme durumuna alınamıyor.")
                return
            con.commit()
            self._reviewed_today = load_reviewed(con)
        except Exception as exc:
            QMessageBox.warning(self, "Kaydedilemedi", f"İnceleme işareti kaydedilemedi: {exc}")
            return
        finally:
            con.close()
        self.refresh_ui_list()

    def _add_empty_state(self):
        item = QListWidgetItem()
        w = QLabel(
            "Kayıtlı verilerde bu filtre için yeni kontrol bulunamadı.\n\n"
            "Bu durum öğrencilerin akademik durumunun ölçüldüğü anlamına gelmez.\n"
            "Dilerseniz ödev ve deneme kayıtlarını gözden geçirin."
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

    def show_followup_draft(self, data):
        """V12 preview: strictly selected student, no calendar/assignment writes."""
        if data.get('type') not in ('overdue', 'silent'):
            return
        student = data.get('data') or {}
        try:
            sid = int(student.get('id') or student.get('ogrenci_id'))
            if sid <= 0:
                raise ValueError('Kayıtlı öğrenci kimliği bulunamadı.')
            con = db.get_conn()
            try:
                evidence = load_open_homework(con, sid)
            finally:
                con.close()
            # Do not default to a shared/other student's profile on missing ID.
            draft = make_followup_draft(sid, evidence, load_profiles(), load_assignments())
        except (ValueError, OSError, sqlite3.Error, TypeError) as exc:
            QMessageBox.warning(self, 'Takip Planı Oluşturulamadı',
                                f'Plan verisi doğrulanamadı. Hiçbir kayıt değiştirilmedi.\n{exc}')
            return
        text = draft_text(draft)
        dlg = QDialog(self)
        dlg.setWindowTitle('📅 Öğrenciye Özel Takip Planı • Taslak')
        dlg.resize(660, 520)
        layout = QVBoxLayout(dlg)
        notice = QLabel('Bu ekran yalnızca önizlemedir. Mevcut ödevler ve onaylı takvim korunur.')
        notice.setWordWrap(True)
        layout.addWidget(notice)
        preview = QPlainTextEdit()
        preview.setReadOnly(True)
        preview.setPlainText(text)
        layout.addWidget(preview)
        row = QHBoxLayout()
        btn_copy = QPushButton('📋 Taslağı Kopyala')
        btn_copy.clicked.connect(lambda: QApplication.clipboard().setText(text))
        row.addWidget(btn_copy)
        parent = self.parent()
        if parent is not None and hasattr(parent, 'open_homework_for_student'):
            btn_open = QPushButton('Ödev Takip Formuna Git')
            def go_to_student():
                dlg.accept()
                self.accept()
                QTimer.singleShot(0, lambda p=parent, student_id=sid:
                                  p.open_homework_for_student(student_id))
            btn_open.clicked.connect(go_to_student)
            row.addWidget(btn_open)
        btn_close = QPushButton('Kapat')
        btn_close.clicked.connect(dlg.reject)
        row.addWidget(btn_close)
        layout.addLayout(row)
        dlg.exec()

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
            if sid and parent and hasattr(parent, "open_homework_for_student"):
                self.accept()
                # Avoid opening nested modal windows while the brief is still active.
                QTimer.singleShot(0, lambda p=parent, stid=int(sid): p.open_homework_for_student(stid))
                return
            QMessageBox.information(self, "Öğrenciye Git", "Ödev formuna geçiş bağlantısı bulunamadı.")
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
            target = []
            if tel:
                target.append((f"{ad} (Veli)", tel))
            v2 = (r.get("veli_tel2") or "").strip()
            if v2 and v2 != tel:
                target.append((f"{ad} (Veli 2)", v2))
            ot = (r.get("ogrenci_tel") or "").strip()
            if ot and ot not in (tel, v2):
                target.append((f"{ad} (Öğrenci)", ot))
            if not target and tel:
                target = [(ad, tel)]

            dlg = WhatsAppGonderDialog(alicilar=target, mesaj=final_msg, parent=self, auto_send=True)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                if not getattr(dlg, "gonderildi", False):
                    dlg.mesajlari_gonder()
        except ImportError:
            QMessageBox.warning(self, "Hata", "WhatsApp modülü yüklenemedi.")
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


