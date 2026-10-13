"""V35 dashboard read-only metric snapshot.

All counts are homework *items* except ``due_today_sets`` (legacy navigation
contract: sets due today).  A due-date cohort is NOT a learning or a completion-
date chart.  No database mutation, guesses or historical study-time fabrication.
This module deliberately has no Qt and no application ``db`` import.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
import sqlite3
from typing import Optional


DONE_STATES = ("yapildi", "tamam", "tamamlandı", "tamamlandi")
_DONE = "lower(trim(coalesce(od.durum, ''))) IN ('yapildi','tamam','tamamlandı','tamamlandi')"
_OPEN = f"NOT ({_DONE})"


@dataclass(frozen=True)
class DashboardSnapshot:
    computed_for: date
    active_students: int
    due_today_sets: int
    overdue_items: int
    total_items: int
    done_items: int
    completion_pct: Optional[float]
    trend: list[dict] = field(default_factory=list)
    alerts: list[dict] = field(default_factory=list)
    top_worker: Optional[dict] = None
    top_ratio: Optional[dict] = None
    # Existing DB only records planned minutes and does not timestamp every
    # completion through the primary save path.  Therefore no actual studied
    # minutes or daily streak may be asserted from these sources.
    verified_study_minutes: Optional[int] = None
    verified_streak_days: Optional[int] = None

    def to_gamification_stats(self) -> dict:
        return {
            "success_rate": int(self.completion_pct or 0),
            "total_homeworks": self.total_items,
            "total_students": self.active_students,
            "streak_days": 0,  # no reliable activity dates
            "weekly_minutes": 0,  # planned assignment duration != actual study
            "alerts": self.alerts,
            "top_worker": self.top_worker,
            "top_ratio": self.top_ratio,
            "top_marathon": None,
        }


def _deleted_clause(con: sqlite3.Connection) -> str:
    """Legacy installations may not have the soft-delete column yet."""
    cols = {row[1] for row in con.execute("PRAGMA table_info(odev)")}
    return " AND COALESCE(od.silindi, 0) = 0" if "silindi" in cols else ""


def _day_value(value: object) -> str:
    return str(value or "")[:10]


def build_snapshot(con: sqlite3.Connection, *, today: Optional[date] = None) -> DashboardSnapshot:
    """Read consistent dashboard data from an existing connection.

    Use one SQLite read transaction when possible. Callers own and close the
    connection. Query errors propagate, so the UI never shows invented zeros.
    """
    today = today or date.today()
    ds = today.isoformat()
    start = (today - timedelta(days=6)).isoformat()
    deleted = _deleted_clause(con)
    active = int(con.execute("SELECT COUNT(*) FROM ogrenci WHERE aktif = 1").fetchone()[0])

    row = con.execute(f"""
        SELECT COUNT(od.id),
               COALESCE(SUM(CASE WHEN {_DONE} THEN 1 ELSE 0 END),0),
               COALESCE(SUM(CASE WHEN {_OPEN} AND substr(k.bitis_tarihi,1,10) < ?
                       AND substr(k.bitis_tarihi,1,10) >= '1900-01-01'
                       THEN 1 ELSE 0 END),0)
          FROM odev od
          JOIN odev_kume k ON k.id = od.kume_id
          JOIN ogrenci o ON o.id = k.ogrenci_id
         WHERE o.aktif = 1 {deleted}
    """, (ds,)).fetchone()
    total, done, overdue = map(int, row)
    completion = (100.0 * done / total) if total else None

    # Preserve the old "today" card's navigation granularity: homework SETS
    # with one or more pending item, not completed tasks today.
    today_sets = int(con.execute(f"""
        SELECT COUNT(DISTINCT k.id)
          FROM odev_kume k JOIN ogrenci o ON o.id = k.ogrenci_id
         WHERE o.aktif=1 AND substr(k.bitis_tarihi,1,10)=?
           AND EXISTS (SELECT 1 FROM odev od WHERE od.kume_id=k.id
                       AND {_OPEN} {deleted})
    """, (ds,)).fetchone()[0])

    # Due-date cohort completion. Do NOT call this 'completed on this day'.
    rows_trend = con.execute(f"""
        SELECT substr(k.bitis_tarihi,1,10), COUNT(od.id),
               COALESCE(SUM(CASE WHEN {_DONE} THEN 1 ELSE 0 END),0)
          FROM odev od
          JOIN odev_kume k ON k.id=od.kume_id
          JOIN ogrenci o ON o.id=k.ogrenci_id
         WHERE o.aktif=1 AND substr(k.bitis_tarihi,1,10) BETWEEN ? AND ? {deleted}
         GROUP BY substr(k.bitis_tarihi,1,10)
    """, (start, ds)).fetchall()
    by_day = {_day_value(r[0]): (int(r[1]), int(r[2])) for r in rows_trend}
    labels = ("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz")
    trend = []
    for offset in range(6, -1, -1):
        d = today - timedelta(days=offset)
        n, ok = by_day.get(d.isoformat(), (0, 0))
        trend.append({"day": labels[d.weekday()], "val": (100 * ok / n if n else 0),
                      "total": n, "done": ok, "date": d.isoformat()})

    alerts = []
    for ad, soyad, cnt in con.execute(f"""
        SELECT o.ad, o.soyad, COUNT(od.id) AS pending_items
          FROM odev od
          JOIN odev_kume k ON k.id=od.kume_id
          JOIN ogrenci o ON o.id=k.ogrenci_id
         WHERE o.aktif=1 AND {_OPEN}
           AND substr(k.bitis_tarihi,1,10) < ?
           AND substr(k.bitis_tarihi,1,10) >= '1900-01-01' {deleted}
         GROUP BY o.id
         ORDER BY pending_items DESC, o.id
         LIMIT 3
    """, (ds,)):
        first, last, n = (ad or "").strip(), (soyad or "").strip(), int(cnt)
        display = f"{first} {last[:1]}." if last else first
        alerts.append({"text": f"{display} - {n} ödev gecikmiş",
                       "severity": "high" if n > 5 else "medium",
                       "tip": "Öğrenciyle yük ve tıkanıklık nedenini görüş." if n > 5
                       else "Kısa bir durum kontrolü yap."})

    # Student-level aggregates support existing achievement badges, but are
    # completion evidence only; no hours or learning-mastery claims.
    rows_students = con.execute(f"""
        SELECT o.id, o.ad, COUNT(od.id) AS assigned,
               COALESCE(SUM(CASE WHEN {_DONE} THEN 1 ELSE 0 END),0) AS done
          FROM odev od
          JOIN odev_kume k ON k.id=od.kume_id
          JOIN ogrenci o ON o.id=k.ogrenci_id
         WHERE o.aktif=1 {deleted}
         GROUP BY o.id
    """).fetchall()
    workers = [(int(r[0]), str(r[1] or ""), int(r[2]), int(r[3])) for r in rows_students]
    top_worker = None
    best_ratio = None
    if workers:
        worker = sorted(workers, key=lambda x: (-x[3], x[0]))[0]
        if worker[3]:
            top_worker = {"name": worker[1], "val": worker[3]}
        qualified = [x for x in workers if x[2] >= 5]
        if qualified:
            best = sorted(qualified, key=lambda x: (-x[3] / x[2], x[0]))[0]
            best_ratio = {"name": best[1], "val": int(100 * best[3] / best[2])}

    return DashboardSnapshot(today, active, today_sets, overdue, total, done,
                             completion, trend, alerts, top_worker, best_ratio)


def build_teacher_insight(snapshot: DashboardSnapshot) -> str:
    """A grounded teacher action, NOT a calibrated risk score or diagnosis."""
    if snapshot.active_students == 0:
        return "Öğrenci Kaydı bölümünden ilk öğrenciyi ekleyerek takibe başlayın."
    if snapshot.overdue_items:
        if snapshot.alerts:
            lead = snapshot.alerts[0]["text"]
            return (f"Öncelikli görüşme: {lead}. Biriken görevlerin nedenini sorun; "
                    "gerekirse haftalık yükü sadeleştirin. Öğretmen onayıyla ilerleyin.")
        return (f"{snapshot.overdue_items} açık gecikmiş ödev var. Önce gecikme "
                "nedenlerini kontrol edin; eski ödevleri otomatik yığmayın.")
    if snapshot.due_today_sets:
        return (f"Bugün kontrol bekleyen {snapshot.due_today_sets} ödev kümesi var. "
                "Kontrolden sonra gerekli konular için kısa kazanım yoklaması planlayın.")
    if snapshot.total_items == 0:
        return "Aktif öğrenciler için henüz ödev kaydı yok. Ödev Takip'ten ilk planı hazırlayın."
    return ("Bugün acil gecikme görünmüyor. Tekrar zamanı gelen kazanımları "
            "Adaptif Koçluk'ta doğrulayın. Ödev tamamlama, öğrenmenin kanıtı değildir.")
