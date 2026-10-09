# -*- coding: utf-8 -*-
"""
HomeworkManager için Gelişmiş Öneri Motoru.

Bu dosya: Kullanıcının mevcut dosyası BOZULMADAN genişletilmiş sürümdür.
Eklenenler:
🎨 Yönetici panelinde AI karar görselleştirme (admin_ai_dashboard_data)
📈 Öğrenciye özel haftalık strateji planı (weekly_strategy_plan)
🤖 GPT destekli motivasyon mesajı üretimi (gpt_motivation_message)
🧪 A/B testli öneri motoru (pro_recommendations_ab, ab_record_outcome, ab_metrics)
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, Tuple, Optional, List, Any, Set
import random
import hashlib
import json

import db


# -------------------------------
# KONFIGURASYON (PROFOSYONEL AYARLAR)
# -------------------------------
RECOM_CONFIG = {
    # Puanlama Ağırlıkları
    "WEIGHT_DIFFICULTY": 2.5,   # Zorluk seviyesinin puana etkisi
    "WEIGHT_OVERDUE": 1.5,      # Gecikme gün sayısının etkisi
    "SCORE_NEVER_DONE": 100,    # Hiç yapılmamış konunun taban puanı
    "SCORE_STARTED": 80,        # Başlanmış ama bitmemiş

    # (Yeni - profesyonel harman)
    "WEIGHT_NEGLECT": 1.2,
    "WEIGHT_WEAK": 1.8,
    "WEIGHT_RECENCY": 0.6,

    # Spaced repetition (aralıklı tekrar)
    "SPACED_REVIEW_TARGET_DAYS": 7,
    "SPACED_REVIEW_MAX_BONUS": 120,

    # Süre Sınırları
    "DAYS_NEGLECTED": 12,       # Bir derse kaç gün bakılmazsa "ihmal edilmiş" sayılır?
    "DAYS_TO_EXAM_WARN": 3,     # Sınava/Bitişe kaç gün kala uyarı verilsin?

    # Liste limitleri
    "MAX_RETURN_DEFAULT": 50,
    "MAX_SUGGESTIONS_DEFAULT": 8,

    # Metin Şablonları
    "TXT_MISSING": "Eksik konu: Hiç çalışılmamış",
    "TXT_NEGLECTED": "Tekrar Zamanı: {days} gündür bu derse bakmadın! (Son: {date})",
    "TXT_FAVORITE": "🚀 Formunu Koru: En başarılı olduğun ders.",
    "TXT_REVIEW": "Genel Tekrar: Bilgileri taze tutmak için.",
    "TXT_WEAK": "⚠️ Kritik: {ders} başarısı düşük (%{ratio}). Acil takviye!",
    "TXT_DEADLINE": "Yaklaşan bitiş ({bitis}) için takviye",

    # Audit / Log
    "ENABLE_AUDIT_LOG": True,
    "AUDIT_TABLE": "ai_log",

    # Çeşitlilik / denge
    "MAX_PER_LESSON_IN_FINAL": 2,      # Final öneride bir dersten max kaç öneri
    "AVOID_REPEAT_TOPIC_DAYS": 5,       # Aynı (ders, konu) çok yakın tekrar gelmesin
    "MIN_CONFIDENCE_TO_SHOW": 0.12,     # Çok düşük güvenli öneriyi buda

    # Deterministik seçim
    "DETERMINISTIC_SELECTION": True,
    "DET_SALT": "COACH_V3",
}


# -------------------------------
# Yardımcılar
# -------------------------------

def _today() -> date:
    return date.today()


def _safe_int(x: Any, default: int = 0) -> int:
    try:
        if x is None:
            return default
        return int(x)
    except Exception:
        return default


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    s = str(s).strip()
    try:
        return datetime.fromisoformat(s[:19]).date()
    except Exception:
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d").date()
        except Exception:
            return None


@dataclass
class TopicPerf:
    ders: str
    kitap: str
    konu: str
    done: int = 0
    total: int = 0
    last_done: Optional[date] = None
    last_status: str = ""
    total_dk: int = 0
    avg_dk: float = 0.0
    overdue_count: int = 0
    success_rate: float = 0.0  # 0.0 - 1.0 (Başarı oranı)


# -------------------------------
# 0.1 Helper functions (Pro)
# -------------------------------

def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def _iso(d: Optional[date]) -> str:
    return d.isoformat() if d else ""

def _hash01(text: str, salt: str = "") -> float:
    """
    Deterministik 0-1 arası sayı (random yerine).
    Aynı text -> aynı sayı.
    """
    h = hashlib.sha256((salt + ":" + text).encode("utf-8")).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF

def _stable_pick(items: List[Dict[str, Any]], key_field: str, salt: str) -> Optional[Dict[str, Any]]:
    """
    Random yerine deterministik seçim:
    - key_field üzerinden hash ile seçer.
    """
    if not items:
        return None
    scored = []
    for it in items:
        k = str(it.get(key_field, ""))
        r = _hash01(k, salt=salt)
        scored.append((r, it))
    scored.sort(key=lambda x: x[0])
    return scored[0][1]

def _spaced_review_bonus(last_seen: Optional[date]) -> float:
    """
    Aralıklı tekrar: son çalışma üzerinden hedef güne yaklaşınca bonus artar.
    """
    if last_seen is None:
        return float(RECOM_CONFIG["SPACED_REVIEW_MAX_BONUS"]) * 0.6

    days = (_today() - last_seen).days
    target = RECOM_CONFIG["SPACED_REVIEW_TARGET_DAYS"]
    if days <= 0:
        return 0.0

    # target gün civarı en yüksek
    if days <= target:
        return (days / target) * (RECOM_CONFIG["SPACED_REVIEW_MAX_BONUS"] * 0.9)
    return float(RECOM_CONFIG["SPACED_REVIEW_MAX_BONUS"])

def _lesson_risk_score(ratio: int, last_seen: Optional[date]) -> float:
    """
    Ders bazlı risk skoru.
    """
    r = _clamp((50 - ratio) / 50.0, 0.0, 1.2)
    neglect = 0.0
    if last_seen is None:
        neglect = 1.0
    else:
        days = (_today() - last_seen).days
        if days > RECOM_CONFIG["DAYS_NEGLECTED"]:
            neglect = _clamp(days / 30.0, 0.0, 1.2)
    return 0.7 * r + 0.3 * neglect

def _avoid_recent_repeat(con, ogrenci_id: int, ders: str, konu: str, days: int) -> bool:
    """
    Aynı (ders, konu) çok yakın zamanda önerildiyse tekrar verme.
    """
    table = RECOM_CONFIG.get("AUDIT_TABLE", "ai_log")
    try:
        row = con.execute(f"""
            SELECT created_at
            FROM {table}
            WHERE ogrenci_id=? AND ders=? AND konu=?
            ORDER BY created_at DESC
            LIMIT 1
        """, (ogrenci_id, ders, konu)).fetchone()
        if not row:
            return False
        val = row["created_at"] if hasattr(row, "__getitem__") else getattr(row, "created_at", None)
        last = _parse_date(val)
        if not last:
            return False
        return (_today() - last).days < days
    except Exception:
        return False

def _apply_diversity_filter(items: List[Dict[str, Any]], max_per_lesson: int) -> List[Dict[str, Any]]:
    """
    Aynı derse yığılmayı engeller.
    """
    counts: Dict[str, int] = {}
    out: List[Dict[str, Any]] = []
    for it in items:
        ders = str(it.get("ders", "")).strip()
        if not ders:
            continue
        counts.setdefault(ders, 0)
        if counts[ders] >= max_per_lesson:
            continue
        counts[ders] += 1
        out.append(it)
    return out


# -------------------------------
# 0. Akıllı Süre Hesaplayıcı (Smart Duration)
# -------------------------------

def _calculate_smart_duration(student_group: str, subject: str, task_type: str, base_difficulty: int = 3) -> int:
    """
    Öğrenci seviyesi, dersin doğası ve görev tipine göre
    en ideal çalışma süresini (blok süresi) hesaplar.
    """
    group = (student_group or "").upper()
    subj = (subject or "").lower()
    
    # 1. Baz Süre (Okul Seviyesi)
    # LGS / Ortaokul: Daha kısa dikkat süresi (30dk baz)
    # YKS / Lise: Standart (40dk baz)
    # Mezun: Daha yoğun (50dk baz)
    duration = 40
    if "LGS" in group or "8." in group or "7." in group or "6." in group:
        duration = 30
    elif "MEZUN" in group or "12." in group:
        duration = 45 # Mezun/12 biraz daha uzun blok sever

    # 2. Ders Zorluğu / Bilişsel Yük
    # Sayısal dersler +10 dk, Sözel dersler standart
    if any(x in subj for x in ["mat", "fiz", "geo", "kim", "fen"]):
        duration += 10
    
    # 3. Görev Tipi (Task Type)
    if task_type in ["review", "neglected"]:
        # Tekrarlar daha hızlı olabilir
        duration = int(duration * 0.75) 
    elif task_type == "deadline":
        # Sınav öncesi son takviye: Odaklanmış kısa blok
        duration -= 5
    elif task_type == "risk" or task_type == "weak":
        # Zayıf olunan konuda acele edilmez
        duration += 5
    elif task_type == "missing":
        # Yeni konu öğrenimi, tam süre
        pass
    elif task_type == "motivation":
        duration = 25 # Ödül/Kolay çalışma kısa olur
        
    # 4. Konu Zorluğu (Veri tabanından geliyorsa)
    if base_difficulty >= 4:
        duration += 5
    elif base_difficulty <= 2:
        duration -= 5

    # Yuvarlama (5'in katları estetik durur)
    duration = 5 * round(duration / 5)

    # Güvenlik Sınırları (Min 20 dk, Max 90 dk)
    return max(20, min(duration, 90))


# -------------------------------
# 1. Eksik Konular (Smart Missing Topics)
# -------------------------------

def smart_missing_topics(con, ogrenci_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Öğrencinin hiç yapmadığı veya başarısız olduğu konuları getirir.
    Sıralama: Öncelik (Ders Ağırlığı * Konu Önemi)
    """

    rows = con.execute("""
        SELECT DISTINCT ders, kitap_ad
        FROM ogrenci_kitap
        WHERE ogrenci_id=?
    """, (ogrenci_id,)).fetchall()

    info = con.execute("SELECT ana_grup FROM ogrenci WHERE id=?", (ogrenci_id,)).fetchone()
    group = info['ana_grup'] if info else ""

    tasks: List[Dict[str, Any]] = []

    active_rows = con.execute(
        "SELECT ders, konu_ad FROM odev WHERE ogrenci_id=? AND durum='devam'",
        (ogrenci_id,)
    ).fetchall()
    active_keys = {(r['ders'], r['konu_ad']) for r in active_rows}

    # (Yeni) Ders bazlı istatistik: zayıf/ihmal sinyali ile puanı zenginleştirmek için
    try:
        stats_cache = get_detailed_stats(con, ogrenci_id)
    except Exception:
        stats_cache = {}

    for r in rows:
        ders = r['ders']
        if not _is_lesson_relevant(group, ders):
            continue

        kitap = r['kitap_ad']
        konular = db.ders_konularini_cek(con, ders)

        # deterministik: konu listesi kararlı olsun
        if RECOM_CONFIG.get("DETERMINISTIC_SELECTION"):
            # sqlite3.Row fix
            konular = sorted(konular, key=lambda x: str(x["konu"] if "konu" in x.keys() else "").lower())

        for k_row in konular:
            konu = k_row['konu']
            if not konu: continue
            konu = str(konu).strip()

            if (ders, konu) in active_keys:
                continue

            stat = con.execute("""
                SELECT COUNT(*) as cnt,
                       SUM(CASE WHEN durum='tamam' THEN 1 ELSE 0 END) as done,
                       MAX(date(tarih)) as last_seen
                FROM odev_satir
                WHERE ogrenci_id=? AND ders=? AND konu=?
            """, (ogrenci_id, ders, konu)).fetchone()

            total = _safe_int(stat['cnt'], 0)
            done = _safe_int(stat['done'], 0)
            # sqlite3.Row fix
            last_seen = _parse_date(stat["last_seen"]) if stat and "last_seen" in stat.keys() else None

            zorluk = (k_row['zorluk'] if 'zorluk' in k_row.keys() else 3) or 3
            smart_dk = _calculate_smart_duration(group, ders, "missing", base_difficulty=zorluk)

            if total == 0:
                score = RECOM_CONFIG["SCORE_NEVER_DONE"] + (zorluk * RECOM_CONFIG["WEIGHT_DIFFICULTY"])
                reason = "missing_or_not_done"
            elif done == 0:
                score = float(RECOM_CONFIG["SCORE_STARTED"])
                reason = "missing_or_not_done"
            else:
                continue

            # Ders bazlı sinyaller
            if ders in stats_cache:
                ratio = stats_cache[ders].get("ratio", 0)
                last_lesson_seen = stats_cache[ders].get("last_seen")

                if ratio < 50:
                    score += (50 - ratio) * RECOM_CONFIG["WEIGHT_WEAK"]

                if last_lesson_seen is None:
                    score += 10 * RECOM_CONFIG["WEIGHT_NEGLECT"]
                else:
                    days_diff = (_today() - last_lesson_seen).days
                    if days_diff > RECOM_CONFIG["DAYS_NEGLECTED"]:
                        score += min(days_diff, 60) * RECOM_CONFIG["WEIGHT_NEGLECT"]
                    else:
                        score -= min(RECOM_CONFIG["DAYS_NEGLECTED"] - days_diff, 12) * RECOM_CONFIG["WEIGHT_RECENCY"]

            # Spaced repetition bonus (konu bazında)
            score += _spaced_review_bonus(last_seen)

            # Güven / açıklama alanları
            confidence = _clamp(score / 600.0, 0.05, 0.95)

            tasks.append({
                "ders": ders,
                "kitap": kitap,
                "konu": konu,
                "dk": smart_dk,
                "aciklama": RECOM_CONFIG["TXT_MISSING"],
                "score": float(score),
                "reason": reason,
                "confidence": float(confidence),
                "why_now": "Eksik konu + tekrar zamanlaması",
                "next_action": "Konu özeti → 20 soru → yanlış analizi (3 madde)",
            })

    tasks.sort(key=lambda x: x.get('score', 0), reverse=True)
    return tasks[:limit]


# -------------------------------
# 2. Yaklaşan Bitiş Takviyesi (Deadline Reinforcement)
# -------------------------------

def smart_deadline_reinforcement(con, ogrenci_id: int) -> List[Dict[str, Any]]:
    """
    Bitiş tarihi yaklaşan ödev kümelerine bakar.
    O derslerden 'kolay/hızlı' pekiştirme konuları önerir.
    """
    today = _today()
    limit_date = today + timedelta(days=RECOM_CONFIG.get("DAYS_TO_EXAM_WARN", 3))

    info = con.execute("SELECT ana_grup FROM ogrenci WHERE id=?", (ogrenci_id,)).fetchone()
    group = info['ana_grup'] if info else ""

    kume_rows = con.execute("""
        SELECT id, bitis_tarihi
        FROM odev_kume
        WHERE ogrenci_id=?
          AND bitis_tarihi IS NOT NULL
          AND date(bitis_tarihi) >= date(?)
          AND date(bitis_tarihi) <= date(?)
    """, (ogrenci_id, today, limit_date)).fetchall()

    if not kume_rows:
        return []

    suggestions: List[Dict[str, Any]] = []

    for k in kume_rows:
        ders_rows = con.execute(
            "SELECT DISTINCT ders FROM odev_satir WHERE kume_id=?",
            (k['id'],)
        ).fetchall()

        for d in ders_rows:
            ders = d['ders']
            target_topic = con.execute("""
                SELECT konu
                FROM odev_satir
                WHERE ogrenci_id=? AND ders=? AND durum!='tamam'
                ORDER BY tarih ASC, id ASC LIMIT 1
            """, (ogrenci_id, ders)).fetchone()

            if target_topic:
                if any(s.get('ders') == ders and s.get('konu') == target_topic['konu'] for s in suggestions):
                    continue
                
                # Deadline tipi süre
                smart_dk = _calculate_smart_duration(group, ders, "deadline")
                score = 520.0  # deadline her zaman üstte kalsın ama abartmasın

                suggestions.append({
                    "ders": ders,
                    "kitap": "Takviye Kaynağı",
                    "konu": target_topic['konu'],
                    "dk": smart_dk,
                    "aciklama": RECOM_CONFIG["TXT_DEADLINE"].format(bitis=k['bitis_tarihi']),
                    "reason": "deadline",
                    "score": score,
                    "bitis": k['bitis_tarihi'],
                    "confidence": 0.85,
                    "why_now": "Bitiş tarihi yaklaşıyor",
                    "next_action": "Kısa tekrar + 10 hedef soru + kontrol",
                })

    return suggestions


# -------------------------------
# 3. Genel Akıllı Öneriler (Advanced Suggestions)
# -------------------------------

def _is_lesson_relevant(student_group: str, lesson_name: str) -> bool:
    """
    Dersin öğrenci grubuyla uyumlu olup olmadığını kontrol eder.
    Profesyonel filtreleme mantığı.
    """
    if not lesson_name:
        return False
    group = (student_group or "").upper()
    lesson = lesson_name.lower()

    if "LGS" in group:
        return lesson.startswith("lgs_") or "lgs" in lesson
    else:
        if lesson.startswith("lgs_") or "lgs" in lesson:
            return False
        return True


def get_detailed_stats(con, ogrenci_id: int):
    """
    Öğrencinin ders bazlı detaylı istatistiklerini çıkarır.
    Filtreleme uygular.
    """
    info = con.execute("SELECT ana_grup FROM ogrenci WHERE id=?", (ogrenci_id,)).fetchone()
    group = info['ana_grup'] if info else ""

    stats: Dict[str, Dict[str, Any]] = {}

    sql1 = "SELECT ders, durum, tarih FROM odev_satir WHERE ogrenci_id=?"
    rows1 = []
    try:
        rows1 = con.execute(sql1, (ogrenci_id,)).fetchall()
    except Exception:
        pass

    sql2 = "SELECT ders, durum, NULL as tarih FROM odev WHERE ogrenci_id=?"
    rows2 = []
    try:
        rows2 = con.execute(sql2, (ogrenci_id,)).fetchall()
    except Exception:
        pass

    rows = rows1 + rows2

    for r in rows:
        d = r['ders']
        if not _is_lesson_relevant(group, d):
            continue

        if d not in stats:
            stats[d] = {'total': 0, 'done': 0, 'last_seen': None}

        stats[d]['total'] += 1

        is_done = (r['durum'] in ['tamam', 'yapildi'])
        if is_done:
            stats[d]['done'] += 1

        tarih_str = r['tarih']
        if tarih_str:
            try:
                t_date = _parse_date(tarih_str)
                if t_date:
                    current_last = stats[d]['last_seen']
                    if current_last is None or t_date > current_last:
                        stats[d]['last_seen'] = t_date
            except Exception:
                pass

    for d, val in stats.items():
        if val['total'] > 0:
            val['ratio'] = int((val['done'] / val['total']) * 100)
        else:
            val['ratio'] = 0

    return stats


def advanced_suggestions(con, ogrenci_id: int, available_books: Dict[str, List[str]] = None) -> List[Dict[str, Any]]:
    """
    İstatistiksel analiz yaparak karma öneriler sunar.
    Profesyonel Versiyon: En zayıf derslere öncelik verir.
    """
    suggestions: List[Dict[str, Any]] = []
    stats = get_detailed_stats(con, ogrenci_id)
    
    info = con.execute("SELECT ana_grup FROM ogrenci WHERE id=?", (ogrenci_id,)).fetchone()
    group = info['ana_grup'] if info else ""

    # En riskli 2 dersi seç (ratio düşük + ihmal)
    risky_lessons = sorted(
        stats.items(),
        key=lambda kv: _lesson_risk_score(kv[1].get("ratio", 0), kv[1].get("last_seen")),
        reverse=True
    )
    risky_lessons = [k for k, v in risky_lessons if v.get("total", 0) >= 2][:2]

    for ders in risky_lessons:
        topic_list = db.ders_konularini_cek(con, ders) or []
        if not topic_list:
            continue

        # deterministik konu seçimi
        if RECOM_CONFIG.get("DETERMINISTIC_SELECTION"):
            # sqlite3.Row fix: use index access or keys
            topic_list = sorted(topic_list, key=lambda x: str(x["konu"] if "konu" in x.keys() else "").lower())
            
            # Helper to safely get from row
            def _safe_get(row, key, default=None):
                if key in row.keys(): return row[key]
                return default

            # Custom stable pick for Rows
            def _stable_pick_row(items, key_field, salt):
                if not items: return None
                scored = []
                for it in items:
                    k = str(_safe_get(it, key_field, ""))
                    r = _hash01(k, salt=salt)
                    scored.append((r, it))
                scored.sort(key=lambda x: x[0])
                return scored[0][1]

            t = _stable_pick_row(topic_list, "konu", salt=f"{RECOM_CONFIG['DET_SALT']}:{ogrenci_id}:{ders}") or topic_list[0]
        else:
            t = random.choice(topic_list)

        book = "Genel Tekrar"
        if available_books and ders in available_books and available_books[ders]:
            book = available_books[ders][0]

        smart_dk = _calculate_smart_duration(group, ders, "weak")
        ratio = stats[ders].get("ratio", 0)

        score = 320.0
        if ratio < 50:
            score += (50 - ratio) * 2.2

        # Spaced repetition dersi bazında bonus
        score += _spaced_review_bonus(stats[ders].get("last_seen"))

        confidence = _clamp(score / 650.0, 0.10, 0.92)

        suggestions.append({
            "ders": ders,
            "kitap": book,
            # sqlite3.Row might need dict access
            "konu": t["konu"] if "konu" in t.keys() else "",
            "dk": smart_dk,
            "aciklama": RECOM_CONFIG["TXT_WEAK"].format(ders=ders, ratio=ratio),
            "reason": "low_success",
            "score": float(score),
            "ders_ratio": ratio,
            "confidence": float(confidence),
            "why_now": "Zayıf ders + tekrar zamanı",
            "next_action": "Konu özeti (10dk) → 25 soru → yanlış defteri 3 madde",
        })

    # İhmal edilen dersler
    for ders, data in stats.items():
        last_seen = data.get('last_seen')

        if last_seen is None:
            days_diff = 999
            last_display = "Hiç"
            msg = "Bu dersten henüz hiç ödev kaydı bulunmuyor."
        else:
            days_diff = (_today() - last_seen).days
            last_display = last_seen.strftime("%d.%m.%Y")
            msg = RECOM_CONFIG["TXT_NEGLECTED"].format(days=days_diff, date=last_display)

        if days_diff > RECOM_CONFIG["DAYS_NEGLECTED"]:
            konular = db.ders_konularini_cek(con, ders) or []
            if not konular:
                continue

            if RECOM_CONFIG.get("DETERMINISTIC_SELECTION"):
                konular = sorted(konular, key=lambda x: str(x["konu"] if "konu" in x.keys() else "").lower())
                
                # Helper to safely get from row
                def _safe_get(row, key, default=None):
                    if key in row.keys(): return row[key]
                    return default
                    
                def _stable_pick_row(items, key_field, salt):
                    if not items: return None
                    scored = []
                    for it in items:
                        k = str(_safe_get(it, key_field, ""))
                        r = _hash01(k, salt=salt)
                        scored.append((r, it))
                    scored.sort(key=lambda x: x[0])
                    return scored[0][1]

                topic_obj = _stable_pick_row(konular, "konu", salt=f"{RECOM_CONFIG['DET_SALT']}:{ogrenci_id}:{ders}:neg") or konular[0]
            else:
                topic_obj = random.choice(konular)

            target_book = "Genel Tekrar"
            if available_books and ders in available_books and available_books[ders]:
                target_book = available_books[ders][0]

            smart_dk = _calculate_smart_duration(group, ders, "neglected")

            base = 250 + min(days_diff, 60)
            score = float(base) + _spaced_review_bonus(last_seen)
            confidence = _clamp(score / 700.0, 0.08, 0.90)

            suggestions.append({
                "ders": ders,
                "kitap": target_book,
                "konu": topic_obj["konu"] if "konu" in topic_obj.keys() else "",
                "dk": smart_dk,
                "aciklama": msg,
                "reason": "neglected",
                "score": float(score),
                "days": days_diff,
                "confidence": float(confidence),
                "why_now": "Uzun süredir bakılmadı",
                "next_action": "Kısa tekrar → 15 soru → 5 dk kontrol",
            })

    # Motivasyon / ödül
    if len(suggestions) < 3 and stats:
        best_lessons = sorted(stats.keys(), key=lambda k: stats[k].get('ratio', 0), reverse=True)
        fav = best_lessons[0] if best_lessons else None
        if fav:
            smart_dk = _calculate_smart_duration(group, fav, "motivation")
            suggestions.append({
                "ders": fav,
                "kitap": "Ödül Testi",
                "konu": "Serbest Çalışma",
                "dk": smart_dk,
                "aciklama": RECOM_CONFIG["TXT_FAVORITE"],
                "reason": "motivation",
                "score": 180,
                "confidence": 0.55,
                "why_now": "Motivasyon ve süreklilik",
                "next_action": "Kolay-orta 15 soru, süre tut",
            })

    return suggestions


def performance_summary(con, ogrenci_id: int) -> str:
    """
    Öğrenci hakkında HTML formatında zengin bir durum özeti döndürür.
    V2.0: Ders bazlı progress bar ve öğrenci profili içerir.
    """
    info = con.execute("SELECT ad, soyad, ana_grup FROM ogrenci WHERE id=?", (ogrenci_id,)).fetchone()
    if not info:
        return "Öğrenci bulunamadı."

    ad_soyad = f"{info['ad']} {info['soyad']}"
    grup = info['ana_grup'] or "Belirsiz"

    stats = get_detailed_stats(con, ogrenci_id)

    total_tasks = sum(s['total'] for s in stats.values())
    done_tasks = sum(s['done'] for s in stats.values())
    global_ratio = int((done_tasks / total_tasks * 100)) if total_tasks > 0 else 0

    profil = "Dengeli Öğrenci"
    if global_ratio > 85:
        profil = "🏆 Yıldız Ogrenci"
    elif global_ratio < 40:
        profil = "⚠️ Destek Gerekiyor"
    elif "matematik" in stats and stats["matematik"]["ratio"] > 70 and "turkce" in stats and stats["turkce"]["ratio"] < 50:
        profil = "🧮 Sayisal Agirlikli"

    html = f"""
    <div style="font-family: Arial, sans-serif; color: #333;">
        <h3 style="color: #4f46e5; margin: 0 0 10px 0;">👤 {ad_soyad}</h3>
        <div style="font-size: 13px; color: #666; margin-bottom: 15px;">
            Grup: <b>{grup}</b> | Profil: <span style="color:#d97706; font-weight:bold;">{profil}</span>
        </div>

        <div style="background-color: #f1f5f9; padding: 10px; border-radius: 8px; margin-bottom: 20px;">
            <div style="font-size: 12px; color: #555;">Genel Basari</div>
            <div style="font-size: 24px; font-weight: bold; color: #059669;">%{global_ratio}</div>
            <div style="font-size: 11px; color: #888;">{done_tasks}/{total_tasks} Odev Tamamlandi</div>
        </div>

        <h4 style="border-bottom: 1px solid #ddd; padding-bottom: 5px; margin-bottom: 10px;">Ders Bazli Performans</h4>
        <table style="width: 100%; font-size: 12px; border-collapse: collapse;">
    """

    sorted_lessons = sorted(stats.items(), key=lambda x: x[1]['ratio'], reverse=True)

    try:
        trend_rows = con.execute("""
            SELECT ders, durum
            FROM odev_satir
            WHERE ogrenci_id=? AND durum IN ('tamam', 'yapildi', 'yapilmadi', 'eksik')
            ORDER BY tarih DESC, id DESC
        """, (ogrenci_id,)).fetchall()

        trends = {}
        for r in trend_rows:
            d = r['ders']
            if d not in trends:
                trends[d] = []
            if len(trends[d]) < 5:
                is_success = 1 if r['durum'] in ['tamam', 'yapildi'] else 0
                trends[d].append(is_success)
    except Exception:
        trends = {}

    sorted_lessons = sorted(stats.items(), key=lambda x: x[1]['ratio'], reverse=True)
    has_trend = False 
    
    for ders, data in sorted_lessons:
        if data['total'] == 0:
            continue

        ratio = data['ratio']
        color = "#22c55e"
        if ratio < 50:
            color = "#ef4444"
        elif ratio < 75:
            color = "#eab308"

        trend_icon = ""
        if ders in trends and len(trends[ders]) >= 2:
            recent_avg = sum(trends[ders]) / len(trends[ders]) * 100
            diff = recent_avg - ratio
            if diff > 10:
                trend_icon = "📈"
                has_trend = True
            elif diff < -10:
                trend_icon = "📉"
                has_trend = True
            else:
                trend_icon = "➖"

        html += f"""
            <tr>
                <td style="padding: 4px 0; width: 45%;">
                    <span style="font-size:11px;">{ders.replace('_',' ').title()}</span>
                    <span style="font-size:10px; margin-left:4px;">{trend_icon if trend_icon != "➖" else ""}</span>
                </td>
                <td style="padding: 4px 0; width: 55%;">
                    <div style="background-color: #e5e7eb; width: 100%; height: 14px; border-radius: 4px;">
                        <div style="background-color: {color}; width: {ratio}%; height: 14px; border-radius: 4px; text-align: center; color: white; font-size: 9px; line-height: 14px;">
                            %{ratio}
                        </div>
                    </div>
                </td>
            </tr>
        """

    html += "</table>"
    
    if has_trend:
        html += """
        <div style="margin-top: 15px; font-size: 10px; color: #666; font-style: italic;">
            * 📈: Son zamanlarda performans artışı.<br>
            * 📉: Son zamanlarda performans düşüşü.
        </div>
        """
    
    html += "</div>"
    return html


# =====================================================================================
# =========================  YENİ: AI KOÇ KATMANI (EK)  ================================
# =====================================================================================

def analyze_study_behavior(con, ogrenci_id: int) -> Dict[str, Any]:
    """
    Öğrencinin çalışma alışkanlığını özetler:
    - completion_ratio
    - risk
    - neglected_lessons
    """
    stats = get_detailed_stats(con, ogrenci_id)
    total = sum(v.get('total', 0) for v in stats.values())
    done = sum(v.get('done', 0) for v in stats.values())

    if total == 0:
        return {
            "profile": "Yeni Öğrenci",
            "risk": "Bilinmiyor",
            "completion_ratio": 0.0,
            "neglected_lessons": 0,
            "lessons_count": 0,
            "notes": "Henüz yeterli ödev verisi yok."
        }

    ratio = done / total
    if ratio > 0.85:
        profile = "Disiplinli"
        risk = "Düşük"
    elif ratio > 0.6:
        profile = "Dalgalı"
        risk = "Orta"
    else:
        profile = "Dağınık"
        risk = "Yüksek"

    neglected_count = 0
    for _, v in stats.items():
        ls = v.get('last_seen')
        if ls is None:
            neglected_count += 1
        else:
            if (_today() - ls).days > RECOM_CONFIG["DAYS_NEGLECTED"]:
                neglected_count += 1

    return {
        "profile": profile,
        "risk": risk,
        "completion_ratio": round(ratio, 2),
        "neglected_lessons": neglected_count,
        "lessons_count": len(stats),
    }


def explain_suggestion(reason: str, payload: Dict[str, Any]) -> str:
    """
    Önerinin sebebini öğrenci dilinde açıklar.
    """
    reason = (reason or "").strip().lower()

    if reason == "low_success":
        ders = payload.get("ders", "Bu ders")
        ratio = payload.get("ders_ratio", payload.get("ratio", ""))
        if ratio != "":
            return f"{ders} dersindeki başarı oranı düşük olduğu için (%{ratio}) takviye önerildi."
        return f"{ders} dersindeki başarı düşük olduğu için takviye önerildi."

    if reason == "neglected":
        # Öncelik: Çağrıdan gelen hazır açıklamayı (tarih/gün içeren) kullan
        if payload.get("aciklama"):
            txt = str(payload["aciklama"])
            # 999 gün görürsen düzelt
            if "999" in txt:
                return f"{payload.get('ders', 'Bu ders')} dersi için sistemde kayıtlı çalışma bulunamadığı için önerildi."
            return txt

        # Fallback
        ders = payload.get("ders", "Bu ders")
        days = payload.get("days")
        if days is not None:
            if days >= 999:
                 return f"{ders} dersi için sistemde kayıtlı çalışma bulunamadığı veya çok uzun süredir çalışılmadığı için önerildi."
            return f"{ders} dersi {days} gündür çalışılmadığı için tekrar önerildi."
        return f"{ders} dersi uzun süredir çalışılmadığı için tekrar önerildi."

    if reason == "deadline":
        ders = payload.get("ders", "Bu ders")
        bitis = payload.get("bitis") or payload.get("bitis_tarihi") or ""
        if bitis:
            return f"{ders} için bitiş tarihi yaklaştığı için ({bitis}) kısa takviye önerildi."
        return f"{ders} için bitiş tarihi yaklaştığı için takviye önerildi."

    if reason == "missing_or_not_done":
        ders = payload.get("ders", "Bu ders")
        konu = payload.get("konu", "Bu konu")
        return f"{ders} dersinde {konu} konusu hiç çalışılmadığı/bitirilmediği için önerildi."

    if reason == "risk":
        return "Genel ilerleme riski yüksek göründüğü için kısa ve etkili bir öneri üretildi."

    if reason == "motivation":
        return "Motivasyonu korumak için güçlü olduğun ders üzerinden ödül niteliğinde bir çalışma önerildi."

    if reason == "gpt_motivation":
        return "Öğrencinin durumuna göre GPT destekli motivasyon mesajı üretildi."

    return "Genel akademik dengeyi sağlamak için önerildi."


def _dedupe_suggestions(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Aynı (ders, konu) tekrarlarını temizler.
    """
    seen: Set[Tuple[str, str]] = set()
    out: List[Dict[str, Any]] = []
    for it in items:
        key = (str(it.get("ders", "")).strip(), str(it.get("konu", "")).strip())
        if not key[0] or not key[1]:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def _audit_log_safe(con, ogrenci_id: int, decision: Dict[str, Any]) -> None:
    """
    ai_log tablosu varsa kararları kayıt altına alır.
    Tablo yoksa sessiz geçer.
    """
    if not RECOM_CONFIG.get("ENABLE_AUDIT_LOG", True):
        return

    table = RECOM_CONFIG.get("AUDIT_TABLE", "ai_log")
    meta_obj = {
        "dk": decision.get("dk"),
        "kitap": decision.get("kitap"),
        "reason": decision.get("reason"),
        "aciklama": decision.get("aciklama"),
        "score": decision.get("score"),
        "ab_variant": decision.get("ab_variant"),
        "explain": decision.get("explain"),
    }
    meta_txt = json.dumps(meta_obj, ensure_ascii=False)

    try:
        # geniş şema
        con.execute(f"""
            INSERT INTO {table} (ogrenci_id, ders, konu, reason, ab_variant, created_at, meta)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
        """, (
            ogrenci_id,
            decision.get("ders"),
            decision.get("konu"),
            decision.get("reason"),
            decision.get("ab_variant"),
            meta_txt
        ))
        try:
            con.commit()
        except Exception:
            pass
        return
    except Exception:
        pass

    try:
        # minimal şema
        con.execute(f"""
            INSERT INTO {table} (ogrenci_id, ders, konu, created_at, meta)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
        """, (
            ogrenci_id,
            decision.get("ders"),
            decision.get("konu"),
            meta_txt
        ))
        try:
            con.commit()
        except Exception:
            pass
    except Exception:
        return


def risk_based_suggestions(con, ogrenci_id: int, available_books: Dict[str, List[str]] = None) -> List[Dict[str, Any]]:
    """
    Öğrencinin genel risk durumuna göre hızlı öneri üretir.
    """
    behavior = analyze_study_behavior(con, ogrenci_id)
    stats = get_detailed_stats(con, ogrenci_id)
    suggestions: List[Dict[str, Any]] = []

    info = con.execute("SELECT ana_grup FROM ogrenci WHERE id=?", (ogrenci_id,)).fetchone()
    group = info['ana_grup'] if info else ""

    if not stats:
        return suggestions

    if behavior.get("risk") == "Yüksek":
        worst = min(stats.items(), key=lambda x: x[1].get('ratio', 0))[0]
        topics = db.ders_konularini_cek(con, worst) or []
        if topics:
            t = topics[0]
            book = "Temel Kaynak"
            if available_books and worst in available_books and available_books[worst]:
                book = available_books[worst][0]
                
            smart_dk = _calculate_smart_duration(group, worst, "risk")

            t_konu = t["konu"] if hasattr(t, "__getitem__") else getattr(t, "konu", str(t))
            suggestions.append({
                "ders": worst,
                "kitap": book,
                "konu": t_konu,
                "dk": smart_dk,
                "aciklama": "🚨 Risk Altında: Temel kazanımı kaçırmamak için kısa ama etkili çalışma.",
                "reason": "risk",
                "score": 450,
            })

    return suggestions


def pro_recommendations(
    con,
    ogrenci_id: int,
    limit: int = None,
    available_books: Dict[str, List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Tek noktadan profesyonel birleşik öneri çıktısı:
    - deadline + risk + advanced + missing harman
    - dedupe + score sorting + audit log
    """
    if limit is None:
        limit = RECOM_CONFIG.get("MAX_SUGGESTIONS_DEFAULT", 8)

    merged: List[Dict[str, Any]] = []
    try:
        merged.extend(smart_deadline_reinforcement(con, ogrenci_id))
    except Exception:
        pass

    try:
        merged.extend(risk_based_suggestions(con, ogrenci_id, available_books=available_books))
    except Exception:
        pass

    try:
        merged.extend(advanced_suggestions(con, ogrenci_id, available_books=available_books))
    except Exception:
        pass

    try:
        merged.extend(smart_missing_topics(con, ogrenci_id, limit=RECOM_CONFIG.get("MAX_RETURN_DEFAULT", 50)))
    except Exception:
        pass

    merged = _dedupe_suggestions(merged)

    # skor/reason yoksa varsayılan ekle
    for it in merged:
        rsn = (it.get("reason") or "").lower()
        if "score" not in it or it.get("score") is None:
            base = 120
            if rsn == "deadline":
                base = 520
            elif rsn == "risk":
                base = 470
            elif rsn == "low_success":
                base = 320
            elif rsn == "neglected":
                base = 260
            elif rsn == "missing_or_not_done":
                base = 220
            elif rsn == "motivation":
                base = 180
            it["score"] = base

        it["explain"] = it.get("explain") or explain_suggestion(it.get("reason", ""), it)

        # confidence yoksa üret
        if it.get("confidence") is None:
            it["confidence"] = float(_clamp(float(it.get("score", 0)) / 650.0, 0.08, 0.9))

        # çok düşük güvenli olanları buda
        if float(it.get("confidence", 0)) < RECOM_CONFIG["MIN_CONFIDENCE_TO_SHOW"]:
            it["__drop__"] = True

    merged = [x for x in merged if not x.get("__drop__")]

    # Çok yakın zamanda önerilen aynı konuyu buda
    out2: List[Dict[str, Any]] = []
    for it in merged:
        ders = str(it.get("ders", "")).strip()
        konu = str(it.get("konu", "")).strip()
        if not ders or not konu:
            continue
        if _avoid_recent_repeat(con, ogrenci_id, ders, konu, days=RECOM_CONFIG["AVOID_REPEAT_TOPIC_DAYS"]):
            continue
        out2.append(it)
    merged = out2

    merged.sort(key=lambda x: float(x.get("score", 0)), reverse=True)

    # Çeşitlilik filtresi (derse yığılma engeli)
    merged = _apply_diversity_filter(merged, max_per_lesson=RECOM_CONFIG["MAX_PER_LESSON_IN_FINAL"])

    final = merged[:limit]

    for d in final:
        _audit_log_safe(con, ogrenci_id, d)

    return final


# =====================================================================================
# 🎨 (1) YÖNETİCİ PANELİ: AI KARAR GÖRSELLEŞTİRME
# =====================================================================================

def admin_ai_dashboard_data(con, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
    """
    Yönetici panelinde grafik/tablolar için hazır data üretir.
    ai_log tablosu varsa çalışır; yoksa boş döner.
    """
    start = start_date or (_today() - timedelta(days=30)).isoformat()
    end = end_date or _today().isoformat()

    table = RECOM_CONFIG.get("AUDIT_TABLE", "ai_log")
    out = {
        "range": {"start": start, "end": end},
        "daily_counts": [],
        "reason_counts": [],
        "lesson_counts": [],
        "variant_counts": [],
        "top_students": [],
    }

    try:
        rows = con.execute(f"""
            SELECT date(created_at) as d, COUNT(*) as c
            FROM {table}
            WHERE date(created_at) >= date(?) AND date(created_at) <= date(?)
            GROUP BY date(created_at)
            ORDER BY date(created_at) ASC
        """, (start, end)).fetchall()
        out["daily_counts"] = [{"date": r["d"], "count": int(r["c"])} for r in rows]

        # reason sütunu varsa direkt say
        try:
            reason_rows = con.execute(f"""
                SELECT reason as reason, COUNT(*) as c
                FROM {table}
                WHERE date(created_at) >= date(?) AND date(created_at) <= date(?)
                GROUP BY reason
                ORDER BY c DESC
            """, (start, end)).fetchall()
            out["reason_counts"] = [{"reason": (r["reason"] or "unknown"), "count": int(r["c"])} for r in reason_rows]
        except Exception:
            # reason yoksa meta JSON içinden
            meta_rows = con.execute(f"""
                SELECT meta
                FROM {table}
                WHERE date(created_at) >= date(?) AND date(created_at) <= date(?)
            """, (start, end)).fetchall()
            counts: Dict[str, int] = {}
            for r in meta_rows:
                rsn = "unknown"
                try:
                    m = r["meta"]
                    if m:
                        obj = json.loads(m)
                        rsn = (obj.get("reason") or "unknown")
                except Exception:
                    rsn = "unknown"
                counts[rsn] = counts.get(rsn, 0) + 1
            out["reason_counts"] = [{"reason": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: x[1], reverse=True)]

        rows = con.execute(f"""
            SELECT ders, COUNT(*) as c
            FROM {table}
            WHERE date(created_at) >= date(?) AND date(created_at) <= date(?)
            GROUP BY ders
            ORDER BY c DESC
            LIMIT 12
        """, (start, end)).fetchall()
        out["lesson_counts"] = [{"ders": (r["ders"] or "unknown"), "count": int(r["c"])} for r in rows]

        try:
            rows = con.execute(f"""
                SELECT ab_variant as v, COUNT(*) as c
                FROM {table}
                WHERE date(created_at) >= date(?) AND date(created_at) <= date(?)
                GROUP BY ab_variant
                ORDER BY c DESC
            """, (start, end)).fetchall()
            out["variant_counts"] = [{"variant": (r["v"] or "NA"), "count": int(r["c"])} for r in rows]
        except Exception:
            out["variant_counts"] = []

        rows = con.execute(f"""
            SELECT ogrenci_id, COUNT(*) as c
            FROM {table}
            WHERE date(created_at) >= date(?) AND date(created_at) <= date(?)
            GROUP BY ogrenci_id
            ORDER BY c DESC
            LIMIT 10
        """, (start, end)).fetchall()
        out["top_students"] = [{"ogrenci_id": int(r["ogrenci_id"]), "count": int(r["c"])} for r in rows]

    except Exception:
        return out

    return out


# =====================================================================================
# 📈 (2) ÖĞRENCİYE ÖZEL HAFTALIK STRATEJİ PLANI
# =====================================================================================

def weekly_strategy_plan(
    con,
    ogrenci_id: int,
    available_minutes_per_day: int = 90,
    days: int = 7,
    available_books: Dict[str, List[str]] = None
) -> Dict[str, Any]:
    """
    Öğrenciye özel 7 günlük plan üretir (koç modu).
    """
    behavior = analyze_study_behavior(con, ogrenci_id)

    # limit=25 aynen kalır; ama içindeki öneriler artık daha dengeli
    base_recs = pro_recommendations(con, ogrenci_id, limit=25, available_books=available_books)

    schedule = []
    today = _today()
    
    # “Koç stratejisi”: önce deadline/risk, sonra zayıf, sonra ihmal, sonra eksik
    priority = {"deadline": 0, "risk": 1, "low_success": 2, "neglected": 3, "missing_or_not_done": 4, "motivation": 5}
    base_recs.sort(key=lambda r: (priority.get((r.get("reason") or ""), 99), -float(r.get("score", 0))))

    for i in range(days):
        day_date = (today + timedelta(days=i)).isoformat()
        remaining = available_minutes_per_day
        day_items = []
        
        used_lessons: Set[str] = set()

        for rec in base_recs:
            if remaining <= 0:
                break
            
            ders = rec.get("ders")
            dk = int(rec.get("dk", 40))
            if not ders or dk <= 0:
                continue

            # günlük çeşitlilik: aynı ders 1 günde 1 kez (mecbur kalmadıkça)
            if ders in used_lessons and any((x.get("ders") != ders) for x in base_recs):
                continue
            
            if dk > remaining:
                continue

            day_items.append({
                "ders": ders,
                "konu": rec.get("konu"),
                "kitap": rec.get("kitap"),
                "dk": dk,
                "hedef": rec.get("aciklama"),
                "neden": rec.get("explain") or explain_suggestion(rec.get("reason"), rec),
                "reason": rec.get("reason"),
                "confidence": rec.get("confidence"),
                "next_action": rec.get("next_action"),
            })
            remaining -= dk
            used_lessons.add(ders)
            
            # aynı öneriyi tekrar kullanmasın diye skorunu düşür
            rec["score"] = float(rec.get("score", 0)) * 0.3

        # gün boş kalmasın
        if not day_items and base_recs:
            r = base_recs[0]
            day_items.append({
                "ders": r.get("ders"),
                "konu": "Genel Tekrar",
                "kitap": "Kısa Tekrar",
                "dk": min(20, available_minutes_per_day),
                "hedef": "Plan boş kalmasın diye kısa tekrar",
                "neden": "Süreklilik için.",
                "reason": "continuity",
                "confidence": 0.4,
                "next_action": "10 soru + kontrol",
            })
            remaining = available_minutes_per_day - day_items[0]["dk"]

        schedule.append({
            "date": day_date,
            "available_minutes": available_minutes_per_day,
            "planned_minutes": available_minutes_per_day - remaining,
            "items": day_items
        })

    return {
        "ogrenci_id": ogrenci_id,
        "profile": behavior,
        "available_minutes_per_day": available_minutes_per_day,
        "days": days,
        "schedule": schedule
    }


# =====================================================================================
# 🤖 (3) GPT DESTEKLİ MOTİVASYON MESAJI ÜRETİMİ
# =====================================================================================

def gpt_motivation_message(
    con,
    ogrenci_id: int,
    tone: str = "enerjik",
    channel: str = "whatsapp",
    model: str = "gpt-5.2",
    api_key_env: str = "OPENAI_API_KEY"
) -> str:
    """
    GPT ile öğrenciye özel motivasyon mesajı üretir.
    - OpenAI SDK gerekir: pip install openai
    - API key ENV'den alınır (client'a koyma).
    """
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return "Motivasyon mesajı için OpenAI SDK gerekli: pip install openai"

    import os
    api_key = os.getenv(api_key_env)
    if not api_key:
        return f"{api_key_env} environment variable bulunamadı."

    info = con.execute("SELECT ad, soyad, ana_grup FROM ogrenci WHERE id=?", (ogrenci_id,)).fetchone()
    if not info:
        return "Öğrenci bulunamadı."
    ad = (info["ad"] or "").strip()
    grup = (info["ana_grup"] or "").strip()

    stats = get_detailed_stats(con, ogrenci_id)
    total_tasks = sum(s['total'] for s in stats.values())
    done_tasks = sum(s['done'] for s in stats.values())
    ratio = int((done_tasks / total_tasks) * 100) if total_tasks > 0 else 0

    weak = None
    strong = None
    if stats:
        weak = min(stats.items(), key=lambda x: x[1].get("ratio", 0))[0]
        strong = max(stats.items(), key=lambda x: x[1].get("ratio", 0))[0]

    plan = weekly_strategy_plan(con, ogrenci_id, available_minutes_per_day=75, days=7)
    todays = plan["schedule"][0]["items"] if plan["schedule"] else []
    todays_text = "; ".join([f"{i.get('ders')} - {i.get('konu')} ({i.get('dk')} dk)" for i in todays]) or "Bugün kısa bir tekrar"

    system = (
        "Sen bir eğitim koçu gibi konuşan, kısa, net, pozitif ama gerçekçi bir asistansın. "
        "Klişe sözlerden kaçın. Öğrenciyi suçlama. 1-2 somut hedef ver."
    )
    user = f"""
Öğrenci adı: {ad}
Grup: {grup}
Genel tamamlama: %{ratio}
Güçlü ders: {strong}
Zayıf ders: {weak}
Bugünkü hedefler: {todays_text}

Kanal: {channel}
Ton: {tone}

İsteğim:
- {channel} için 2-4 cümlelik motivasyon mesajı yaz.
- En sonda 1 satırda mini-hedef maddesi ekle (örn: "Hedef: ...").
""".strip()

    client = OpenAI(api_key=api_key)
    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    msg = getattr(resp, "output_text", "") or ""
    msg = msg.strip()

    _audit_log_safe(con, ogrenci_id, {
        "ders": strong or "",
        "konu": "Motivasyon",
        "dk": 0,
        "kitap": "GPT",
        "reason": "gpt_motivation",
        "aciklama": msg,
        "score": 0,
        "ab_variant": None,
        "explain": explain_suggestion("gpt_motivation", {}),
    })

    return msg


# =====================================================================================
# 🧪 (4) A/B TESTLİ ÖNERİ MOTORU + METRİKLER
# =====================================================================================

def _stable_bucket(ogrenci_id: int, salt: str = "AB_V1") -> str:
    """
    Öğrenciyi deterministik şekilde A/B kovasına atar.
    """
    h = hashlib.sha256(f"{salt}:{ogrenci_id}".encode("utf-8")).hexdigest()
    return "A" if int(h[:2], 16) < 128 else "B"


def _variant_config(variant: str) -> Dict[str, Any]:
    """
    A/B varyant parametreleri:
    A: daha agresif deadline+risk
    B: daha dengeli weak+neglected+missing
    """
    variant = (variant or "A").upper()
    if variant == "B":
        return {
            "limit": RECOM_CONFIG.get("MAX_SUGGESTIONS_DEFAULT", 8),
            "weight_deadline": 1.0,
            "weight_risk": 1.0,
            "weight_weak": 1.4,
            "weight_neglect": 1.3,
            "weight_missing": 1.2,
        }
    return {
        "limit": RECOM_CONFIG.get("MAX_SUGGESTIONS_DEFAULT", 8),
        "weight_deadline": 1.6,
        "weight_risk": 1.5,
        "weight_weak": 1.2,
        "weight_neglect": 1.1,
        "weight_missing": 1.0,
    }


def pro_recommendations_ab(
    con,
    ogrenci_id: int,
    available_books: Dict[str, List[str]] = None,
    salt: str = "AB_V1"
) -> Dict[str, Any]:
    """
    A/B testli birleşik öneri:
    - A/B varyantına göre skor harmanı değişir
    - ai_log'a ab_variant yazar (tablo uygunsa)
    """
    variant = _stable_bucket(ogrenci_id, salt=salt)
    cfg = _variant_config(variant)

    deadline = smart_deadline_reinforcement(con, ogrenci_id)
    risk = risk_based_suggestions(con, ogrenci_id, available_books=available_books)
    adv = advanced_suggestions(con, ogrenci_id, available_books=available_books)
    miss = smart_missing_topics(con, ogrenci_id, limit=RECOM_CONFIG.get("MAX_RETURN_DEFAULT", 50))

    merged: List[Dict[str, Any]] = []
    merged.extend(deadline)
    merged.extend(risk)
    merged.extend(adv)
    merged.extend(miss)

    merged = _dedupe_suggestions(merged)

    for it in merged:
        rsn = (it.get("reason") or "").lower()
        base = float(it.get("score", 100))

        if rsn == "deadline":
            base *= cfg["weight_deadline"]
        elif rsn == "risk":
            base *= cfg["weight_risk"]
        elif rsn == "low_success":
            base *= cfg["weight_weak"]
        elif rsn == "neglected":
            base *= cfg["weight_neglect"]
        elif rsn == "missing_or_not_done":
            base *= cfg["weight_missing"]

        it["score"] = base
        it["ab_variant"] = variant
        it["explain"] = it.get("explain") or explain_suggestion(it.get("reason"), it)

    merged.sort(key=lambda x: float(x.get("score", 0)), reverse=True)
    final = merged[: cfg["limit"]]

    for d in final:
        _audit_log_safe(con, ogrenci_id, d)

    return {"variant": variant, "config": cfg, "items": final}


def ab_record_outcome(con, ogrenci_id: int, variant: str, outcome: str, meta: Dict[str, Any] = None) -> None:
    """
    A/B outcome kaydı (ai_ab_events tablosu varsa):
    outcome örnekleri: completed / ignored / partial
    """
    meta = meta or {}
    try:
        con.execute("""
            INSERT INTO ai_ab_events (ogrenci_id, variant, outcome, created_at, meta)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
        """, (ogrenci_id, variant, outcome, json.dumps(meta, ensure_ascii=False)))
        try:
            con.commit()
        except Exception:
            pass
    except Exception:
        return


def ab_metrics(con, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
    """
    A/B metrik özetleri (ai_ab_events tablosu varsa):
    - counts
    - completion_rate
    """
    start = start_date or (_today() - timedelta(days=30)).isoformat()
    end = end_date or _today().isoformat()
    out = {"range": {"start": start, "end": end}, "by_variant": []}

    try:
        rows = con.execute("""
            SELECT variant, outcome, COUNT(*) as c
            FROM ai_ab_events
            WHERE date(created_at) >= date(?) AND date(created_at) <= date(?)
            GROUP BY variant, outcome
            ORDER BY variant, c DESC
        """, (start, end)).fetchall()

        tmp: Dict[str, Dict[str, int]] = {}
        for r in rows:
            v = r["variant"] or "NA"
            o = r["outcome"] or "unknown"
            tmp.setdefault(v, {})
            tmp[v][o] = tmp[v].get(o, 0) + int(r["c"])

        for v, counts in tmp.items():
            total = sum(counts.values())
            completed = counts.get("completed", 0)
            rate = (completed / total) if total > 0 else 0.0
            out["by_variant"].append({
                "variant": v,
                "counts": counts,
                "total": total,
                "completed": completed,
                "completion_rate": round(rate, 3)
            })

        out["by_variant"].sort(key=lambda x: x["variant"])
    except Exception:
        pass

    return out


# =====================================================================
# BİLİMSEL PEDAGOJİK VE DERİN ÖDEV ANALİZ MOTORU (v3.0 PRO)
# Ebbinghaus Unutma Eğrisi, Bilişsel Yük Dengesi, ÖSYM/LGS Matrisi
# =====================================================================

_CURRICULUM_CACHE = None

def get_curriculum_dict() -> Dict[str, Any]:
    """Assets altındaki curriculum.json dosyasından konu bazlı sınav ağırlıklarını döndürür."""
    global _CURRICULUM_CACHE
    if _CURRICULUM_CACHE is not None:
        return _CURRICULUM_CACHE
    import os, json
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p = os.path.join(base, "assets", "curriculum.json")
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                _CURRICULUM_CACHE = json.load(f).get("topics", {})
                return _CURRICULUM_CACHE
        except Exception:
            pass
    _CURRICULUM_CACHE = {}
    return _CURRICULUM_CACHE


def get_comprehensive_student_analytics(con, ogrenci_id: int) -> Dict[str, Any]:
    """
    Öğrencinin bitirdiği, bitirmediği, geciken ve devam eden ödevlerini,
    Ebbinghaus unutma eğrisi aralıklarını, koçluk hakimiyet durumunu ve
    ÖSYM sınav önceliklerini birleştirerek çok boyutlu analitik sunar.
    """
    out: Dict[str, Any] = {
        "student": {},
        "overall": {
            "total_assigned": 0,
            "completed_count": 0,
            "incomplete_count": 0,
            "overdue_count": 0,
            "pending_count": 0,
            "completion_ratio": 0,
            "total_dk": 0,
            "total_questions": 0,
        },
        "lesson_stats": {},
        "ebbinghaus_reviews": [],
        "overdue_remedials": [],
        "in_progress": [],
        "curriculum_gaps": [],
        "cognitive_profile": "Dengeli Öğrenci",
        "recommended_daily_minutes": 120,
    }

    # 1. Öğrenci Bilgileri
    try:
        st_row = con.execute("SELECT id, ad, soyad, ana_grup, aktif FROM ogrenci WHERE id=?", (ogrenci_id,)).fetchone()
        if st_row:
            out["student"] = {
                "id": st_row["id"],
                "ad": st_row["ad"] or "",
                "soyad": st_row["soyad"] or "",
                "ad_soyad": f"{st_row['ad'] or ''} {st_row['soyad'] or ''}".strip(),
                "ana_grup": st_row["ana_grup"] or "YKS",
            }
    except Exception:
        pass

    group = out["student"].get("ana_grup", "YKS")
    today = _today()

    # 2. Tüm Ödev Kayıtlarını Topla (odev + odev_kume ve odev_satir)
    completed_topics: Dict[Tuple[str, str], Dict[str, Any]] = {}
    overdue_list: List[Dict[str, Any]] = []
    pending_list: List[Dict[str, Any]] = []
    lesson_tally: Dict[str, Dict[str, Any]] = {}

    # odev tablosundan çek (odev_kume ile birleşik)
    try:
        rows_odev = con.execute("""
            SELECT o.id, o.ders, o.konu_ad, o.kitap_ad, o.durum, o.saat_dk,
                   o.verilis_tarihi, o.tamamlanma_tarihi,
                   k.bitis_tarihi, k.verilis_tarihi as kume_verilis
            FROM odev o
            LEFT JOIN odev_kume k ON o.kume_id = k.id
            WHERE o.ogrenci_id=?
        """, (ogrenci_id,)).fetchall()

        for r in rows_odev:
            ders = (r["ders"] or "").strip().lower()
            konu = (r["konu_ad"] or "").strip()
            kitap = (r["kitap_ad"] or "").strip()
            durum = (r["durum"] or "").strip().lower()
            dk = _safe_int(r["saat_dk"], 0)
            
            bitis_date = _parse_date(r["bitis_tarihi"])
            tamam_date = _parse_date(r["tamamlanma_tarihi"]) or bitis_date or _parse_date(r["kume_verilis"]) or _parse_date(r["verilis_tarihi"])

            if not ders or not konu:
                continue

            if ders not in lesson_tally:
                lesson_tally[ders] = {"total": 0, "done": 0, "overdue": 0, "last_date": None}
            lesson_tally[ders]["total"] += 1

            is_done = durum in ["tamam", "yapildi", "bitti"]
            if is_done:
                lesson_tally[ders]["done"] += 1
                if tamam_date:
                    if lesson_tally[ders]["last_date"] is None or tamam_date > lesson_tally[ders]["last_date"]:
                        lesson_tally[ders]["last_date"] = tamam_date

                key = (ders, konu)
                if key not in completed_topics or (tamam_date and tamam_date > (completed_topics[key].get("date") or date.min)):
                    completed_topics[key] = {
                        "ders": ders, "konu": konu, "kitap": kitap,
                        "date": tamam_date, "dk": dk
                    }
            else:
                is_overdue = (bitis_date and bitis_date < today) or (durum in ["yapilmadi", "eksik"])
                if is_overdue:
                    lesson_tally[ders]["overdue"] += 1
                    overdue_list.append({
                        "ders": ders, "konu": konu, "kitap": kitap,
                        "bitis": _iso(bitis_date),
                        "gecikme_gun": (today - bitis_date).days if bitis_date else 3,
                        "durum": durum, "dk": dk or 30
                    })
                else:
                    pending_list.append({
                        "ders": ders, "konu": konu, "kitap": kitap,
                        "bitis": _iso(bitis_date),
                        "kalan_gun": (bitis_date - today).days if bitis_date else 1,
                        "durum": durum, "dk": dk or 30
                    })
    except Exception:
        pass

    # odev_satir tablosundaki ek kayıtları da harmanla (varsa)
    try:
        rows_satir = con.execute("""
            SELECT ders, konu, kitap, durum, tarih, sure_dk, dk
            FROM odev_satir
            WHERE ogrenci_id=?
        """, (ogrenci_id,)).fetchall()
        for r in rows_satir:
            ders = (r["ders"] or "").strip().lower()
            konu = (r["konu"] or "").strip()
            kitap = (r["kitap"] or "").strip()
            durum = (r["durum"] or "").strip().lower()
            dk = _safe_int(r["sure_dk"] or r["dk"], 0)
            t_date = _parse_date(r["tarih"])
            if not ders or not konu:
                continue

            if ders not in lesson_tally:
                lesson_tally[ders] = {"total": 0, "done": 0, "overdue": 0, "last_date": None}
            
            is_done = durum in ["tamam", "yapildi", "bitti"]
            if is_done:
                key = (ders, konu)
                if key not in completed_topics:
                    lesson_tally[ders]["total"] += 1
                    lesson_tally[ders]["done"] += 1
                    completed_topics[key] = {"ders": ders, "konu": konu, "kitap": kitap, "date": t_date, "dk": dk}
    except Exception:
        pass

    # 3. Koçluk Konu Hakimiyet Kayıtları (koc_konu_takip)
    coaching_mastery: Dict[Tuple[str, str], Dict[str, Any]] = {}
    try:
        rows_koc = con.execute("""
            SELECT ders_adi, konu_adi, durum, hakimiyet_puani, cozulen_soru, hedef_soru, son_tekrar_tarihi
            FROM koc_konu_takip
            WHERE ogrenci_id=?
        """, (ogrenci_id,)).fetchall()
        for r in rows_koc:
            d = (r["ders_adi"] or "").strip().lower()
            k = (r["konu_adi"] or "").strip()
            if d and k:
                coaching_mastery[(d, k)] = {
                    "durum": _safe_int(r["durum"], 0),
                    "puan": _safe_int(r["hakimiyet_puani"], 0),
                    "cozulen": _safe_int(r["cozulen_soru"], 0),
                    "son_tekrar": _parse_date(r["son_tekrar_tarihi"]),
                }
    except Exception:
        pass

    # 4. Genel Metrikleri Hesapla
    total_assigned = sum(v["total"] for v in lesson_tally.values())
    completed_count = len(completed_topics)
    overdue_count = len(overdue_list)
    pending_count = len(pending_list)
    incomplete_count = max(0, total_assigned - completed_count)
    ratio = int(round((completed_count / total_assigned * 100))) if total_assigned > 0 else 0

    out["overall"]["total_assigned"] = total_assigned
    out["overall"]["completed_count"] = completed_count
    out["overall"]["incomplete_count"] = incomplete_count
    out["overall"]["overdue_count"] = overdue_count
    out["overall"]["pending_count"] = pending_count
    out["overall"]["completion_ratio"] = ratio
    out["overall"]["total_dk"] = sum(v.get("dk", 0) for v in completed_topics.values())
    out["overall"]["total_questions"] = sum(v.get("cozulen", 0) for v in coaching_mastery.values())

    # 5. Ders Bazlı Sağlık Durumu
    for d, val in sorted(lesson_tally.items(), key=lambda x: x[1]["done"] / max(1, x[1]["total"]), reverse=True):
        t_count = val["total"]
        d_count = val["done"]
        l_ratio = int(round((d_count / t_count * 100))) if t_count > 0 else 0
        last_d = val["last_date"]
        days_ago = (today - last_d).days if last_d else 999
        
        # Renk kodu
        c_code = "#22c55e" if l_ratio >= 75 else ("#eab308" if l_ratio >= 50 else "#ef4444")
        out["lesson_stats"][d] = {
            "name": d.replace("_", " ").title(),
            "total": t_count,
            "done": d_count,
            "overdue": val["overdue"],
            "ratio": l_ratio,
            "last_seen": _iso(last_d),
            "days_ago": days_ago,
            "color": c_code,
        }

    # 6. Ebbinghaus Unutma Eğrisi & Aralıklı Tekrar Tespiti
    ebbinghaus_list = []
    for (d, k), cdata in completed_topics.items():
        s_date = cdata.get("date")
        if not s_date:
            continue
        days = (today - s_date).days
        stage = None
        retention = 100
        urgency = "Düşük"

        if 1 <= days <= 2:
            stage = "1. Tekrar (24 Saat - Temel Hafıza)"
            retention = 65
            urgency = "Yüksek"
        elif 6 <= days <= 8:
            stage = "2. Tekrar (7. Gün - Ebbinghaus Kırılımı)"
            retention = 50
            urgency = "Kritik"
        elif 13 <= days <= 16:
            stage = "3. Tekrar (14. Gün - Pekiştirme Penceresi)"
            retention = 40
            urgency = "Orta"
        elif 28 <= days <= 35:
            stage = "4. Tekrar (30. Gün - Kalıcı Hafıza Kilidi)"
            retention = 30
            urgency = "Kritik"
        elif days > 45:
            stage = f"İhmal Tekrarı ({days} Gündür Bakılmadı!)"
            retention = 20
            urgency = "Yüksek"

        if stage:
            ebbinghaus_list.append({
                "ders": d,
                "konu": k,
                "kitap": cdata.get("kitap", "Soru Bankası"),
                "days_ago": days,
                "stage": stage,
                "estimated_retention": retention,
                "urgency": urgency,
                "recommended_minutes": 25,
                "recommended_questions": 20,
                "last_date": _iso(s_date)
            })

    ebbinghaus_list.sort(key=lambda x: (0 if x["urgency"] == "Kritik" else (1 if x["urgency"] == "Yüksek" else 2), -x["days_ago"]))
    out["ebbinghaus_reviews"] = ebbinghaus_list

    # 7. Geciken Telafi Ödevleri
    out["overdue_remedials"] = overdue_list

    # 8. Devam Eden Ödevler
    out["in_progress"] = pending_list

    # 9. Müfredat Eksikleri & ÖSYM Sınav Ağırlığı
    curriculum = get_curriculum_dict()
    curriculum_gaps = []

    # Öğrencinin grubuna uygun dersleri çek
    try:
        active_lessons = con.execute("SELECT id, ad FROM ders_tanimlari WHERE aktif=1").fetchall()
    except Exception:
        active_lessons = []

    for lrow in active_lessons:
        d_key = lrow["id"]
        d_title = lrow["ad"]
        if not _is_lesson_relevant(group, d_key):
            continue

        topics = db.ders_konularini_cek(con, d_key) or []
        for trow in topics:
            konu_name = trow["konu"] if hasattr(trow, "__getitem__") else str(trow)
            if (d_key, konu_name) in completed_topics:
                continue

            c_info = curriculum.get(konu_name, {})
            importance = c_info.get("importance", "Orta (3/5)")
            questions_text = c_info.get("questions", "1 Soru")
            tip = c_info.get("tip", "")

            # Skorlama
            score = 100
            if "5/5" in importance or "Yüksek" in importance:
                score += 150
            elif "4/5" in importance:
                score += 80

            curriculum_gaps.append({
                "ders": d_key,
                "ders_ad": d_title,
                "konu": konu_name,
                "importance": importance,
                "questions_exam": questions_text,
                "tip": tip,
                "score": score,
                "recommended_minutes": 35,
                "recommended_questions": 25,
            })

    curriculum_gaps.sort(key=lambda x: x["score"], reverse=True)
    out["curriculum_gaps"] = curriculum_gaps

    # 10. Bilişsel Profil ve Günlük Kapasite
    if ratio >= 80 and overdue_count == 0:
        out["cognitive_profile"] = "🏆 Zirve Hedefli - Hızlı İlerleme & Deneme Modu"
        out["recommended_daily_minutes"] = 180
    elif overdue_count >= 4 or ratio < 45:
        out["cognitive_profile"] = "⚠️ Destek Gerekiyor - Acil Telafi & Bilişsel Yük Azaltma"
        out["recommended_daily_minutes"] = 90
    elif len(ebbinghaus_list) >= 5:
        out["cognitive_profile"] = "🧠 Hafıza Tazeleyici - Aralıklı Tekrar & Pekiştirme Aşaması"
        out["recommended_daily_minutes"] = 140
    else:
        out["cognitive_profile"] = "🎯 Dengeli İlerleme - Müfredat & Form Koruma Modu"
        out["recommended_daily_minutes"] = 120

    return out


def generate_smart_homework_suggestions(
    con,
    ogrenci_id: int,
    available_books: Optional[Dict[str, List[str]]] = None,
    mode: str = "balanced",
    target_minutes: int = 180,
    limit: int = 12
) -> List[Dict[str, Any]]:
    """
    Öğrencinin bitirdiği, geciken ve devam eden ödevlerini inceleyerek;
    Ebbinghaus unutma eğrisi, bilişsel yük teorisi (%30 tekrar, %50 ana hedef, %20 telafi)
    ve ÖSYM soru frekansını harmanlayan üst düzey öneri paketi üretir.
    """
    analytics = get_comprehensive_student_analytics(con, ogrenci_id)
    available_books = available_books or {}
    
    overdues = analytics["overdue_remedials"]
    ebbinghaus = analytics["ebbinghaus_reviews"]
    gaps = analytics["curriculum_gaps"]
    
    candidates: List[Dict[str, Any]] = []
    seen_keys: Set[Tuple[str, str]] = set()

    # 1. Telafi Adayları (Geciken / Yapılmayanlar)
    for ov in overdues:
        k = (ov["ders"], ov["konu"])
        if k in seen_keys:
            continue
        seen_keys.add(k)
        
        # Kitap belirle
        book = ov.get("kitap") or "Temel Soru Bankası"
        if ov["ders"] in available_books and available_books[ov["ders"]]:
            if book not in available_books[ov["ders"]]:
                book = available_books[ov["ders"]][0]

        g_gun = ov.get("gecikme_gun", 2)
        candidates.append({
            "type": "remedial",
            "badge": "🚨 Telafi Ödevi",
            "badge_color": "#ef4444",
            "ders": ov["ders"],
            "kitap": book,
            "konu": ov["konu"],
            "dk": min(45, max(20, ov.get("dk", 30))),
            "soru": 25,
            "priority": 1,
            "score": 500 + g_gun * 10,
            "reason": f"Geciken ödev: {g_gun} gün önce teslim edilmeliydi. Bilişsel yükü hafifletmek için acil telafi.",
        })

    # 2. Ebbinghaus Aralıklı Tekrar Adayları (Unutma Eğrisi)
    for eb in ebbinghaus:
        k = (eb["ders"], eb["konu"])
        if k in seen_keys:
            continue
        seen_keys.add(k)

        book = eb.get("kitap") or "Tekrar Fasikülü"
        if eb["ders"] in available_books and available_books[eb["ders"]]:
            book = available_books[eb["ders"]][0]

        badge_txt = "🧠 Ebbinghaus Tekrarı"
        b_color = "#8b5cf6" # purple
        score = 400
        if eb["urgency"] == "Kritik":
            badge_txt = "🧠 Kritik Tekrar (7/30. Gün)"
            b_color = "#dc2626"
            score = 480

        candidates.append({
            "type": "ebbinghaus",
            "badge": badge_txt,
            "badge_color": b_color,
            "ders": eb["ders"],
            "kitap": book,
            "konu": eb["konu"],
            "dk": eb["recommended_minutes"],
            "soru": eb["recommended_questions"],
            "priority": 2,
            "score": score,
            "reason": f"{eb['days_ago']} gün önce çalışıldı. {eb['stage']} kapsamında bilginin kalıcı belleğe geçişi için hatırlatma.",
        })

    # 3. ÖSYM / LGS Sınav Öncelikli Eksik Konular
    for gp in gaps:
        k = (gp["ders"], gp["konu"])
        if k in seen_keys:
            continue
        seen_keys.add(k)

        book = "Soru Bankası"
        if gp["ders"] in available_books and available_books[gp["ders"]]:
            book = available_books[gp["ders"]][0]

        is_high = "5/5" in gp["importance"] or "Yüksek" in gp["importance"]
        badge_txt = "🔥 Sınavda Çok Çıkar" if is_high else "📘 Müfredat Eksik"
        b_color = "#f59e0b" if is_high else "#0ea5e9"
        
        candidates.append({
            "type": "curriculum",
            "badge": badge_txt,
            "badge_color": b_color,
            "ders": gp["ders"],
            "kitap": book,
            "konu": gp["konu"],
            "dk": gp["recommended_minutes"],
            "soru": gp["recommended_questions"],
            "priority": 3 if is_high else 4,
            "score": gp["score"],
            "reason": f"Müfredat eksik: Sınav ağırlığı {gp['importance']} ({gp['questions_exam']}). {gp.get('tip', '')}",
        })

    # 4. Moda Göre Filtrele ve Ağırlıklandır
    if mode == "remedial":
        # Sadece telafi ve riskler
        candidates = [c for c in candidates if c["type"] in ["remedial", "ebbinghaus"]]
    elif mode == "ebbinghaus":
        # Sadece tekrar odaklı
        candidates = [c for c in candidates if c["type"] == "ebbinghaus"]
    elif mode == "exam_focus":
        # Sadece yüksek soru çıkanlar
        candidates = [c for c in candidates if "🔥" in c["badge"] or c["type"] == "curriculum"]
    else:
        # Dengeli mod: Bilişsel yük dengesi (%20 telafi, %30 tekrar, %50 müfredat/sınav)
        pass

    candidates.sort(key=lambda x: x["score"], reverse=True)

    # 5. Hedef Süreye Göre Akıllı Paketleme
    selected = []
    current_minutes = 0
    lesson_counts: Dict[str, int] = {}

    for c in candidates:
        # Aynı dersten en fazla 2 ödev olsun (çeşitlilik kuralı)
        d = c["ders"]
        if lesson_counts.get(d, 0) >= 2:
            continue

        c_dk = c.get("dk", 30)
        selected.append(c)
        lesson_counts[d] = lesson_counts.get(d, 0) + 1
        current_minutes += c_dk

        if len(selected) >= limit or current_minutes >= target_minutes:
            break

    # Eğer çok az seçildiyse limit dolana kadar kalan adaylardan ekle
    if len(selected) < 6 and len(candidates) > len(selected):
        for c in candidates:
            if c not in selected:
                selected.append(c)
                if len(selected) >= min(limit, 8):
                    break

    return selected


def generate_pedagogical_pdr_report(con, ogrenci_id: int) -> Dict[str, Any]:
    """
    Yerel kural ve istatistik tabanlı, dış servislere bağımsız
    derinlemesine pedagojik PDR koçluk değerlendirmesi ve hazır WhatsApp metinleri üretir.
    """
    analytics = get_comprehensive_student_analytics(con, ogrenci_id)
    st = analytics["student"]
    name = st.get("ad_soyad") or "Öğrenci"
    ratio = analytics["overall"]["completion_ratio"]
    total = analytics["overall"]["total_assigned"]
    done = analytics["overall"]["completed_count"]
    overdue = analytics["overall"]["overdue_count"]
    ebbinghaus_cnt = len(analytics["ebbinghaus_reviews"])
    profile = analytics["cognitive_profile"]

    # Güçlü ve riskli dersler
    strong_lessons = []
    weak_lessons = []
    for d, s in analytics["lesson_stats"].items():
        if s["ratio"] >= 75 and s["total"] >= 3:
            strong_lessons.append(s["name"])
        elif s["ratio"] < 50 and s["total"] >= 2:
            weak_lessons.append(s["name"])

    strong_txt = ", ".join(strong_lessons) if strong_lessons else "Tüm derslerde dengeli ilerleme"
    weak_txt = ", ".join(weak_lessons) if weak_lessons else "Belirgin bir riskli ders tespit edilmedi"

    # Özet Rapor
    summary_text = (
        f"Sayın Koç, {name} isimli öğrencimizin sistemdeki toplam {total} ödevinden {done} tanesi tamamlanmış "
        f"olup genel ödev bitirme başarısı %{ratio} seviyesindedir. "
        f"Öğrencinin bilişsel profili: '{profile}' olarak teşhis edilmiştir. "
        f"En başarılı olunan branşlar: {strong_txt}. "
        f"Özel dikkat ve takviye bekleyen branşlar: {weak_txt}."
    )

    # WhatsApp Öğrenci Mesajı
    wa_student = (
        f"🌟 *Haftalık Koçluk Değerlendirmesi* 🌟\n\n"
        f"Sevgili *{name}*,\n"
        f"Bu haftaki çalışma analizin tamamlandı! 📊\n"
        f"• *Genel Başarı Oranın:* %{ratio} ({done}/{total} Ödev)\n"
        f"• *Güçlü Olduğun Dersler:* {strong_txt} 🚀\n"
    )
    if overdue > 0:
        wa_student += f"• *Dikkat:* {overdue} adet geciken telafi ödevin bulunuyor. Bu hafta bunları küçük parçalara bölerek eritelim.\n"
    if ebbinghaus_cnt > 0:
        wa_student += f"• *Hafıza & Tekrar:* {ebbinghaus_cnt} konuda Ebbinghaus tekrar penceresindesin. Unutmayı engellemek için hızlı testleri ihmal etme! 🧠\n"
    wa_student += (
        f"\n🎯 *Koçunun Bu Haftaki Tavsiyesi:* Günde 3x40 dk Pomodoro tekniği ile odaklanarak ilerle. "
        f"Her tamamladığın görev seni hedefine bir adım daha yaklaştırıyor. Sana inanıyorum! 💪✨"
    )

    # WhatsApp Veli Mesajı
    wa_parent = (
        f"📋 *Öğrenci Gelişim ve Koçluk Bilgilendirmesi* 📋\n\n"
        f"Sayın Velimiz, öğrencimiz *{name}*'nin haftalık ödev ve ders takip raporudur:\n"
        f"• *Ödev Bitirme Başarısı:* %{ratio}\n"
        f"• *Durum Özeti:* Öğrencimiz {strong_txt} branşlarında yüksek başarı gösterirken, "
        f"{weak_txt} konularında ek takviye ve pekiştirme planlanmıştır.\n"
        f"• *Haftalık Çalışma Disiplini:* Günlük ~{analytics['recommended_daily_minutes']} dakika odaklanmış çalışma önerilmektedir.\n\n"
        f"Öğrencimizin motivasyonunu yüksek tutmak adına evdeki çalışma ortamını desteklemenizi rica eder, "
        f"başarılar dileriz. 🎓"
    )

    return {
        "summary": summary_text,
        "profile": profile,
        "strong_lessons": strong_lessons,
        "weak_lessons": weak_lessons,
        "whatsapp_student": wa_student,
        "whatsapp_parent": wa_parent,
    }

