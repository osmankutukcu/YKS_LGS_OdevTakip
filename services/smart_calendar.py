from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta, datetime
from typing import Any, Dict, List, Optional, Tuple
import re

from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtGui import QTextDocument, QPageSize
from PyQt6.QtCore import QUrl


@dataclass
class _Task:
    raw: Dict[str, Any]
    ders: str
    konu: str
    kitap: str
    sure: int            # dakika
    zorluk: int          # 1-5
    priority: int        # 1-5
    deadline: Optional[date] = None
    kind: str = ""
    splitable: bool = True


@dataclass
class _DayPlan:
    label: str
    date_: date
    tasks: List[_Task]
    is_school_day: bool = False
    day_cap: int = 0
    day_target: int = 0

    @property
    def total_minutes(self) -> int:
        return sum(t.sure for t in self.tasks)

    def count_lesson(self, ders: str) -> int:
        return sum(1 for t in self.tasks if t.ders == ders)

    def hard_count(self) -> int:
        return sum(1 for t in self.tasks if t.zorluk >= 4)

    def last_lesson(self) -> Optional[str]:
        if not self.tasks:
            return None
        return self.tasks[-1].ders


class SmartCalendarService:
    """
    ✅ UI/DB yapısına dokunmaz.
    ✅ create_weekly_plan_pdf imzası korunur.
    ✅ details/homework_list yoksa bile akıllı tahminle kişisel plan çıkarır.
    """

    POLICY = {
        "DAYS": 7,
        "TR_DAYS": ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"],

        # Günlük hedef sınırları (AI güvenlik sınırları)
        "MIN_DAILY_TARGET": 35,
        "MAX_DAILY_TARGET": 220,

        # Sert üst sınır (ne olursa olsun)
        "HARD_DAY_CAP": 300,

        # Gün tiplerine göre esneklik
        "WEEKEND_CAP_FACTOR": 1.18,
        "SCHOOL_CAP_FACTOR": 0.85,   # okul günü cap biraz düşer

        # Hafta içi / hafta sonu hedef kaydırma
        "WEEKDAY_TARGET_FACTOR": 0.95,
        "WEEKEND_TARGET_FACTOR": 1.07,

        # Telafi günü (hafif gün)
        "ENABLE_LIGHT_DAY": True,
        "LIGHT_DAY_TARGET_FACTOR": 0.60,
        "LIGHT_DAY_WEEKDAY_PREF": 2,  # Çarşamba

        # Çeşitlilik
        "AVOID_SAME_LESSON_STREAK": True,
        "MAX_SAME_LESSON_PER_DAY": 2,

        # Zor görev limiti
        "MAX_HARD_TASKS_PER_DAY": 2,

        # Uzun ödevleri bölme
        "SPLIT_THRESHOLD": 75,
        "SPLIT_CHUNK_MIN": 35,
        "SPLIT_CHUNK_MAX": 55,

        # Çok az iş varsa boş gün olabilir
        "ALLOW_EMPTY_DAYS": True,
        "EMPTY_DAY_IF_TOTAL_LESS_THAN": 120,

        # Önerilen saat aralıkları (metin)
        "SCHOOL_DAY_SUGGEST": "18:30–21:00",
        "NON_SCHOOL_WEEKDAY_SUGGEST": "10:30–13:00 / 18:00–20:00",
        "WEEKEND_SUGGEST": "11:00–14:00 / 16:00–18:00",
    }

    # ---------------- PUBLIC API ----------------

    @staticmethod
    def create_weekly_plan_pdf(student_name, homework_list, details=None):
        if not homework_list:
            return None

        # 1. Görevleri Normalize Et
        tasks = SmartCalendarService._normalize_tasks(homework_list)
        if not tasks:
            return None

        # 2. Profili Çıkar (Okul günleri, hedefler vb.)
        profile = SmartCalendarService._extract_profile(details, homework_list, tasks)

        # 3. Günleri Hazırla
        days = SmartCalendarService._build_days(profile)

        # 4. Dağıt
        SmartCalendarService._smart_distribute(tasks, days, profile)

        # 5. HTML Üret
        return SmartCalendarService._build_html(student_name, details, days, profile)

    # ---------------- PROFILE (SORU SORMADAN OTOMATİK) ----------------

    @staticmethod
    def _extract_profile(details: Optional[str], homework_list: List[Dict[str, Any]], tasks: List[_Task]) -> Dict[str, Any]:
        p = SmartCalendarService.POLICY
        
        # Default değerler
        school_days = None
        school_hours = None
        course_hours = None
        focus_subjects = []
        
        daily_max = None
        weekday_target = None
        weekend_target = None

        # 1) homework_list parametreleri (eski uyumluluk)
        for x in homework_list:
            if not isinstance(x, dict): continue
            if school_days is None and "school_days" in x:
                school_days = SmartCalendarService._parse_school_days(x.get("school_days"))
            if daily_max is None and ("daily_max" in x or "gunluk_max" in x):
                daily_max = SmartCalendarService._parse_minutes(x.get("daily_max") or x.get("gunluk_max"))

        # 2) details parsing (Regex ile zengin veriyi al)
        if details:
            text = str(details).lower()
            
            # Okul Günleri / Saatleri
            if "okul: yok" in text or "okul yok" in text:
                school_days = set()
                school_hours = "Yok"
            else:
                m_sch = re.search(r"okul\s*[:=]\s*([0-9]{1,2}[:.][0-9]{2})\s*-\s*([0-9]{1,2}[:.][0-9]{2})", text)
                if m_sch:
                    school_hours = f"{m_sch.group(1)} - {m_sch.group(2)}"
                    school_days = {0, 1, 2, 3, 4} 
                elif school_days is None:
                    school_days = SmartCalendarService._parse_school_days(details)

            # Kurs Saatleri
            if "kurs: yok" in text or "kurs yok" in text:
                course_hours = "Yok"
            else:
                m_crs = re.search(r"kurs\s*[:=]\s*([0-9]{1,2}[:.][0-9]{2})\s*-\s*([0-9]{1,2}[:.][0-9]{2})", text)
                if m_crs:
                    course_hours = f"{m_crs.group(1)} - {m_crs.group(2)}"
                    
            # Odak Dersler
            m_foc = re.search(r"odak\s*[:=]\s*([^|]*)", text)
            if m_foc:
                raw_foc = m_foc.group(1).replace("ve", ",").split(",")
                for f in raw_foc:
                    cl = f.strip().lower()
                    if cl: focus_subjects.append(cl)

            # Engelleri Parse Et (Zorunlu)
            blocked_map = {0:0, 1:0, 2:0, 3:0, 4:0, 5:0, 6:0}
            m_blk = re.search(r"engel.*[:=]\s*(.*)", text)
            if m_blk:
                # Format: Pazartesi [18:00-20:00] Desc ; Salı ...
                blks = m_blk.group(1).split(";")
                # Mapping
                d_map = {
                    "pzt":0,"pazartesi":0,"pts":0,
                    "sal":1,"salı":1,"sali":1,
                    "çar":2,"çarşamba":2,"carsamba":2,
                    "per":3,"perşembe":3,"persembe":3,
                    "cum":4,"cuma":4,
                    "cmt":5,"cumartesi":5,"ctesi":5,
                    "paz":6,"pazar":6
                }
                for b in blks:
                    b_low = b.lower().strip()
                    # Find day
                    day_idx = -1
                    for k,v in d_map.items():
                        if k in b_low:
                            day_idx = v
                            break
                    # Find time [HH:MM-HH:MM]
                    m_t = re.search(r"\[(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\]", b_low)
                    if day_idx != -1 and m_t:
                        try:
                            h1, m1, h2, m2 = map(int, m_t.groups())
                            start_min = h1*60 + m1
                            end_min = h2*60 + m2
                            dur = end_min - start_min
                            if dur > 0: blocked_map[day_idx] += dur
                        except: pass

            # Hedefler
            if daily_max is None:
                daily_max = SmartCalendarService._parse_minutes(details)
            if weekday_target is None:
                weekday_target = SmartCalendarService._parse_weekday_weekend_target(details, which="weekday")
            if weekend_target is None:
                weekend_target = SmartCalendarService._parse_weekday_weekend_target(details, which="weekend")

        # 3) Fallback Logic
        if school_days is None:
            school_days = {0, 1, 2, 3, 4} 
        
        # Günlük Max 
        if daily_max is None:
            total = sum(t.sure for t in tasks)
            if total >= 720: daily_max = 200
            elif total >= 480: daily_max = 170
            else: daily_max = 140
        daily_max = max(60, min(int(daily_max), p["HARD_DAY_CAP"]))

        # Hedef Süreler
        if weekday_target is None or weekend_target is None:
            total = sum(t.sure for t in tasks)
            base = int(round(total / 7))
            base = max(p["MIN_DAILY_TARGET"], min(base, p["MAX_DAILY_TARGET"]))
            
            wday = int(round(base * p["WEEKDAY_TARGET_FACTOR"]))
            wend = int(round(base * p["WEEKEND_TARGET_FACTOR"]))
            
            if course_hours and course_hours != "Yok":
                wend = int(wend * 0.8)

            weekday_target = max(p["MIN_DAILY_TARGET"], min(wday, int(daily_max * 0.95)))
            weekend_target = max(p["MIN_DAILY_TARGET"], min(wend, daily_max))

        weekday_target = max(p["MIN_DAILY_TARGET"], min(int(weekday_target), daily_max))
        weekend_target = max(p["MIN_DAILY_TARGET"], min(int(weekend_target), daily_max))
        
        # Önceliklendirme (Focus)
        for t in tasks:
            d_lower = t.ders.lower()
            if any(f in d_lower for f in focus_subjects):
                t.priority = 5
                t.kind = "odak"
                
        # Hafif gün
        enable_light = p["ENABLE_LIGHT_DAY"]
        if sum(t.sure for t in tasks) < 240:
            enable_light = False

        return {
            "school_days": school_days,
            "school_hours": school_hours,
            "course_hours": course_hours,
            "daily_max": daily_max,
            "weekday_target": weekday_target,
            "weekend_target": weekend_target,
            "enable_light_day": enable_light,
            "focus_subjects": focus_subjects,
            "blocked_map": blocked_map if 'blocked_map' in locals() else {}
        }

    @staticmethod
    def _parse_weekday_weekend_target(details: str, which: str) -> Optional[int]:
        if not details:
            return None
        text = str(details).lower()

        patterns = []
        if which == "weekday":
            patterns = [
                r"hafta\s*içi\s*hedef\s*[:=]\s*([0-9]+)\s*(dk|dak|dakika|min)",
                r"hafta\s*içi\s*hedef\s*[:=]\s*([0-9]+)\s*saat",
                r"weekday\s*target\s*[:=]\s*([0-9]+)\s*(dk|dak|dakika|min|m)",
                r"weekday\s*target\s*[:=]\s*([0-9]+)\s*saat",
            ]
        else:
            patterns = [
                r"hafta\s*sonu\s*hedef\s*[:=]\s*([0-9]+)\s*(dk|dak|dakika|min)",
                r"hafta\s*sonu\s*hedef\s*[:=]\s*([0-9]+)\s*saat",
                r"weekend\s*target\s*[:=]\s*([0-9]+)\s*(dk|dak|dakika|min|m)",
                r"weekend\s*target\s*[:=]\s*([0-9]+)\s*saat",
            ]

        for pat in patterns:
            m = re.search(pat, text)
            if m:
                num = int(m.group(1))
                unit = m.group(2) if m.group(2) else "dk" # group 2 optional
                if "saat" in str(unit).lower():
                    return num * 60
                return num
        return None

    @staticmethod
    def _parse_school_days(src: Any) -> Optional[set]:
        if not src:
            return None
        if isinstance(src, (list, tuple, set)):
            try:
                s = set(int(x) for x in src)
                s = {x for x in s if 0 <= x <= 6}
                return s if s else None
            except Exception:
                return None

        text = str(src).lower()
        mapping = {
            "pzt": 0, "pazartesi": 0, "pts": 0,
            "sal": 1, "salı": 1, "sali": 1,
            "çar": 2, "çarş": 2, "cars": 2, "çarşamba": 2, "carsamba": 2,
            "per": 3, "perş": 3, "pers": 3, "perşembe": 3, "persembe": 3,
            "cum": 4, "cuma": 4,
            "cmt": 5, "cumartesi": 5, "ctesi": 5,
            "paz": 6, "pazar": 6,
        }

        found = set()
        tokens = re.split(r"[\s,;/\-|\.]+", text)
        for tok in tokens:
            tok = tok.strip()
            if tok in mapping:
                found.add(mapping[tok])
        return found if found else None

    @staticmethod
    def _parse_minutes(src: Any) -> Optional[int]:
        if not src: return None
        if isinstance(src, (int, float)): return int(src)

        text = str(src).lower()
        m = re.search(r"(\d+)\s*saat", text)
        if m: return int(m.group(1)) * 60
        m = re.search(r"(\d+)\s*(dk|dak|dakika|min)", text)
        if m: return int(m.group(1))
        m = re.search(r"(daily_max|gunluk_max|max)\s*[:=]\s*(\d+)", text)
        if m: return int(m.group(2))
        return None

    # ---------------- TASK NORMALIZATION ----------------

    @staticmethod
    def _normalize_tasks(homework_list: List[Dict[str, Any]]) -> List[_Task]:
        out: List[_Task] = []
        for x in homework_list:
            if not isinstance(x, dict): continue
            ders = str(x.get("ders", "") or "").strip()
            konu = str(x.get("konu", "") or "").strip()
            if not ders: continue
            if not konu: konu = "Genel Tekrar / Çalışma"

            kitap = str(x.get("kitap", "") or "").strip()
            sure = SmartCalendarService._safe_int(x.get("sure", 30), default=30)
            sure = max(5, min(sure, 600))

            zorluk = SmartCalendarService._safe_int(x.get("zorluk", x.get("difficulty")), default=0)
            if zorluk <= 0:
                if sure <= 25: zorluk = 2
                elif sure <= 45: zorluk = 3
                elif sure <= 70: zorluk = 4
                else: zorluk = 5
            zorluk = max(1, min(zorluk, 5))

            deadline = SmartCalendarService._parse_date(x.get("deadline") or x.get("bitis") or x.get("bitis_tarihi"))

            priority = SmartCalendarService._safe_int(x.get("priority"), default=0)
            if priority <= 0:
                priority = 3
                if deadline:
                    days_left = (deadline - date.today()).days
                    if days_left <= 2: priority = 5
                    elif days_left <= 5: priority = 4
                if zorluk >= 4:
                    priority = max(priority, 4)
            priority = max(1, min(priority, 5))

            kind = str(x.get("type") or x.get("kind") or "").strip()
            splitable = bool(x.get("splitable", True))

            t = _Task(
                raw=x, ders=ders, konu=konu, kitap=kitap, sure=sure,
                zorluk=zorluk, priority=priority, deadline=deadline,
                kind=kind, splitable=splitable
            )

            out.extend(SmartCalendarService._split_task_if_needed(t))

        out.sort(key=lambda t: (
            SmartCalendarService._deadline_score(t.deadline),
            -t.priority,
            -t.zorluk,
            -t.sure
        ))
        return out

    @staticmethod
    def _split_task_if_needed(t: _Task) -> List[_Task]:
        p = SmartCalendarService.POLICY
        if (not t.splitable) or t.sure < p["SPLIT_THRESHOLD"]:
            return [t]

        total = t.sure
        chunk_min = p["SPLIT_CHUNK_MIN"]
        chunk_max = p["SPLIT_CHUNK_MAX"]

        n = max(2, int(round(total / 45)))
        n = min(n, 6)

        base = total // n
        base = max(chunk_min, min(base, chunk_max))

        parts: List[_Task] = []
        remaining = total
        while remaining > 0:
            piece = min(base, remaining)
            if remaining - piece != 0 and remaining - piece < chunk_min:
                piece = max(chunk_min, piece - (chunk_min - (remaining - piece)))
            parts.append(_Task(
                raw=t.raw, ders=t.ders, konu=t.konu, kitap=t.kitap, sure=piece,
                zorluk=t.zorluk, priority=t.priority, deadline=t.deadline,
                kind=t.kind, splitable=False
            ))
            remaining -= piece
            if len(parts) > 12: break

        total_parts = len(parts)
        for i, part in enumerate(parts, start=1):
            if total_parts > 1:
                part.konu = f"{part.konu} ({i}/{total_parts})"
        return parts

    # ---------------- DAYS ----------------

    @staticmethod
    def _build_days(profile: Dict[str, Any]) -> List[_DayPlan]:
        p = SmartCalendarService.POLICY
        today = date.today()
        days: List[_DayPlan] = []

        school_days = profile["school_days"]
        daily_max = profile["daily_max"]

        for i in range(p["DAYS"]):
            curr = today + timedelta(days=i)
            wd = curr.weekday()
            is_weekend = wd in (5, 6)
            is_school = wd in school_days if school_days else False

            day_name = p["TR_DAYS"][wd]
            day_str = curr.strftime("%d.%m.%Y")
            label = f"{day_name} <span style='font-size:10pt; font-weight:normal;'>({day_str})</span>"

            cap = daily_max
            if is_weekend:
                cap = int(round(cap * p["WEEKEND_CAP_FACTOR"]))
            if is_school:
                cap = int(round(cap * p["SCHOOL_CAP_FACTOR"]))
            
            # Engelli süreleri (Constraints) düş
            blk = profile.get("blocked_map", {}).get(wd, 0)
            if blk > 0:
                cap -= blk
                
            cap = max(45, min(cap, p["HARD_DAY_CAP"]))

            days.append(_DayPlan(
                label=label,
                date_=curr,
                tasks=[],
                is_school_day=is_school,
                day_cap=cap,
                day_target=0
            ))
        return days

    # ---------------- DISTRIBUTION ----------------

    @staticmethod
    def _smart_distribute(tasks: List[_Task], days: List[_DayPlan], profile: Dict[str, Any]) -> None:
        p = SmartCalendarService.POLICY
        total_time = sum(t.sure for t in tasks)
        if total_time <= 0: return

        weekday_target = profile["weekday_target"]
        weekend_target = profile["weekend_target"]

        # 1) Gün hedeflerini doldur
        for d in days:
            wd = d.date_.weekday()
            is_weekend = wd in (5, 6)
            base_target = weekend_target if is_weekend else weekday_target
            d.day_target = max(p["MIN_DAILY_TARGET"], min(int(base_target), d.day_cap))

        allow_empty = p["ALLOW_EMPTY_DAYS"] and total_time < p["EMPTY_DAY_IF_TOTAL_LESS_THAN"]

        # Telafi günü
        light_day_idx = None
        if profile.get("enable_light_day", True) and not allow_empty:
            light_day_idx = SmartCalendarService._pick_light_day(days, preferred_weekday=p["LIGHT_DAY_WEEKDAY_PREF"])
            if light_day_idx is not None:
                days[light_day_idx].day_target = int(round(days[light_day_idx].day_target * p["LIGHT_DAY_TARGET_FACTOR"]))
                days[light_day_idx].day_target = max(p["MIN_DAILY_TARGET"], min(days[light_day_idx].day_target, days[light_day_idx].day_cap))

        last_global_lesson = None

        # 2) Ana Dağıtım
        for t in tasks:
            best_idx = 0
            best_cost = None

            for idx, d in enumerate(days):
                after = d.total_minutes + t.sure

                overflow = max(0, after - d.day_cap)
                overflow_penalty = 0 if overflow == 0 else (1600 + overflow * 16)

                target_distance = abs(after - d.day_target)

                same_count = d.count_lesson(t.ders)
                same_penalty = 0
                if same_count >= p["MAX_SAME_LESSON_PER_DAY"]:
                    same_penalty += 280
                if p["AVOID_SAME_LESSON_STREAK"]:
                    if d.last_lesson() == t.ders: same_penalty += 95
                    if last_global_lesson and last_global_lesson == t.ders: same_penalty += 65

                hard_penalty = 0
                if t.zorluk >= 4 and d.hard_count() >= p["MAX_HARD_TASKS_PER_DAY"]:
                    hard_penalty += 255

                deadline_bonus = 0
                if t.deadline:
                    days_left = (t.deadline - d.date_).days
                    if days_left < 0: deadline_bonus = -280
                    elif days_left <= 1: deadline_bonus = -200
                    elif days_left <= 3: deadline_bonus = -105

                empty_bias = 0
                if allow_empty and idx >= 5 and d.total_minutes == 0:
                    empty_bias = 15

                school_bias = 0
                if d.is_school_day and t.zorluk >= 4:
                    school_bias = 35

                cost = (
                    overflow_penalty + target_distance * 1.6 + same_penalty + hard_penalty + 
                    empty_bias + school_bias + deadline_bonus - (t.priority * 9) - (t.zorluk * 2)
                )

                if best_cost is None or cost < best_cost:
                    best_cost = cost
                    best_idx = idx

            days[best_idx].tasks.append(t)
            last_global_lesson = t.ders

        # 3) Re-balance
        SmartCalendarService._rebalance(days, light_day_idx)

        # 4) Gün içi sıralama
        for d in days:
            d.tasks.sort(key=lambda t: (-t.zorluk, -t.priority, -t.sure))

    @staticmethod
    def _pick_light_day(days: List[_DayPlan], preferred_weekday: int = 2) -> int:
        for i, d in enumerate(days):
            if d.date_.weekday() == preferred_weekday:
                return i
        return min(3, len(days) - 1)

    @staticmethod
    def _rebalance(days: List[_DayPlan], light_day_idx: Optional[int]) -> None:
        def is_light(i: int) -> bool:
            return light_day_idx is not None and i == light_day_idx

        for _ in range(3):
            order = sorted(range(len(days)), key=lambda i: days[i].total_minutes)
            lo = order[0]
            hi = order[-1]
            if days[hi].total_minutes - days[lo].total_minutes < 45: break

            moved = False
            for t in sorted(days[hi].tasks, key=lambda x: x.sure):
                if t.sure > 55: continue
                if is_light(lo) and (days[lo].total_minutes + t.sure) > int(days[lo].day_target * 1.05): continue
                if days[lo].count_lesson(t.ders) >= 2: continue
                
                days[hi].tasks.remove(t)
                days[lo].tasks.append(t)
                moved = True
                break
            if not moved: break

    # ---------------- HTML ----------------

    @staticmethod
    def _build_html(student_name: str, details: Optional[str], days: List[_DayPlan], profile: Dict[str, Any]) -> str:
        p = SmartCalendarService.POLICY
        total_time = sum(d.total_minutes for d in days)

        daily_max = profile.get("daily_max", 180)
        weekday_target = profile.get("weekday_target", 150)
        weekend_target = profile.get("weekend_target", 180)
        
        # Meta Bilgi
        meta_parts = []
        sch_h = profile.get("school_hours")
        if sch_h and sch_h != "Yok": 
            meta_parts.append(f"🏫 <b>Okul:</b> {sch_h}")
        else:
            sd = profile.get("school_days")
            if sd: 
                meta_parts.append(f"🏫 <b>Okul Günleri:</b> {SmartCalendarService._school_days_str(sd)}")
            
        crs_h = profile.get("course_hours")
        if crs_h and crs_h != "Yok": 
            meta_parts.append(f"🚀 <b>Sabit Rutin:</b> {crs_h}")
             
        focs = profile.get("focus_subjects")
        if focs:
            f_str = ", ".join(f.title() for f in focs)
            meta_parts.append(f"🔥 <b>Öncelikli Odak:</b> {f_str}")
            
        meta_parts.append(f"⏱ <b>Maksimum Hedef:</b> {daily_max} dk/gün")
        meta_parts.append(f"🎯 <b>Ortalama Tempo:</b> H.İçi ~{weekday_target} dk | H.Sonu ~{weekend_target} dk")
        
        meta_html = " &nbsp;&nbsp;|&nbsp;&nbsp; ".join(meta_parts)
        coach_note = SmartCalendarService._coach_note(days, "", daily_max, weekday_target, weekend_target)
        
        # Ders İkonları
        LESSON_ICONS = {
            "tyt_matematik": "📐", "ayt_matematik": "📈", "problemler": "🧩", "geometri": "📏",
            "fizik": "⚡", "kimya": "🧪", "biyoloji": "🧬", "turkce": "📖", "paragraf": "📑",
            "tarih": "🏛️", "cografya": "🌍", "felsefe": "💭", "edebiyat": "📜", "din": "🕌",
            "ingilizce": "🇬🇧", "lgs_matematik": "📐", "lgs_fen": "🔬", "lgs_turkce": "📖",
            "lgs_inkilap": "🏛️", "lgs_dinkulturu": "🕌", "lgs_ingilizce": "🇬🇧"
        }

        # Tablo bazlı 7 günlük layout (4 sütun satır 1, 4 sütun satır 2)
        # 8. hücre: Haftalık Koçluk ve İmza Değerlendirme Kartı
        cells_html = []
        for i, d in enumerate(days):
            tasks = d.tasks
            day_mins = d.total_minutes
            focus = SmartCalendarService._day_focus(tasks, d)
            suggest = SmartCalendarService._suggest_time_window(d)
            
            raw_day = p["TR_DAYS"][d.date_.weekday()]
            raw_date = d.date_.strftime("%d.%m.%Y")
            
            # Gün Başlık Rengi: Hafta sonu mor/lacivert, hafta içi kurumsal mavi
            header_bg = "#1e40af" if d.date_.weekday() in (5, 6) else "#2563eb"
            header_sub = "HAFTA SONU" if d.date_.weekday() in (5, 6) else "HAFTA İÇİ"

            c_html = f"""
            <td width="25%" valign="top" style="padding: 5px;">
                <table width="100%" cellpadding="0" cellspacing="0" style="border: 1px solid #cbd5e1; border-radius: 8px; background-color: #ffffff;">
                    <tr>
                        <td style="background-color: {header_bg}; color: #ffffff; padding: 8px 10px; border-top-left-radius: 7px; border-top-right-radius: 7px; text-align: center;">
                            <div style="font-size: 13pt; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px;">{raw_day}</div>
                            <div style="font-size: 8.5pt; opacity: 0.9; margin-top: 2px;">📅 {raw_date} &nbsp;•&nbsp; {header_sub}</div>
                        </td>
                    </tr>
                    <tr>
                        <td style="background-color: #f1f5f9; padding: 5px 8px; border-bottom: 1px solid #e2e8f0; font-size: 8.5pt; color: #334155;">
                            <b>⏱ {day_mins} dk</b> <font color="#64748b">/ {d.day_cap} dk</font> &nbsp;|&nbsp; <b>🎯 {focus}</b>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 8px; font-size: 8pt; color: #64748b; text-align: center; border-bottom: 1px dashed #e2e8f0; background: #fafafa;">
                            🕒 Önerilen Zaman: <b>{suggest}</b>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; min-height: 140px;" valign="top">
            """

            if not tasks:
                c_html += """
                    <div style="text-align: center; color: #94a3b8; padding: 25px 5px; font-size: 9pt;">
                        ☕ <i>Serbest Gün / Dinlenme & Tekrar</i>
                    </div>
                """
            else:
                for t in tasks:
                    key = t.ders.lower().strip()
                    icon = LESSON_ICONS.get(key, "📘")
                    ders = (t.ders or "").replace('_', ' ').title()
                    
                    border_color = "#3b82f6"
                    bg_color = "#f8fafc"
                    if t.zorluk >= 4:
                        border_color = "#ef4444"
                        bg_color = "#fef2f2"
                    elif t.zorluk == 3:
                        border_color = "#f59e0b"
                        bg_color = "#fffbeb"
                    elif t.kind == "odak":
                        border_color = "#8b5cf6"
                        bg_color = "#f5f3ff"
                    
                    konu = t.konu or "Genel Tekrar"
                    kitap = t.kitap or "Kaynak Kitap"
                    
                    c_html += f"""
                    <div style="margin-bottom: 6px; padding: 6px 8px; border-left: 3.5px solid {border_color}; background-color: {bg_color}; border-radius: 4px; border-top: 1px solid #f1f5f9; border-right: 1px solid #f1f5f9; border-bottom: 1px solid #f1f5f9;">
                        <table width="100%" cellpadding="0" cellspacing="0">
                            <tr>
                                <td style="font-size: 8pt; font-weight: bold; color: #1e293b;">
                                    {icon} {ders}
                                </td>
                                <td align="right" style="font-size: 7.5pt; color: #64748b;">
                                    ⏳ <b>{t.sure} dk</b> &nbsp; <span style="font-size: 9pt; color: #94a3b8;">☐</span>
                                </td>
                            </tr>
                        </table>
                        <div style="font-size: 8.5pt; font-weight: 600; color: #0f172a; margin-top: 2px;">{konu}</div>
                        <div style="font-size: 7.5pt; color: #64748b; margin-top: 1px;">📚 {kitap}</div>
                    </div>
                    """

            c_html += """
                        </td>
                    </tr>
                </table>
            </td>
            """
            cells_html.append(c_html)

        # 8. Hücre: Değerlendirme & Koçluk Kartı
        summary_cell = f"""
        <td width="25%" valign="top" style="padding: 5px;">
            <table width="100%" cellpadding="0" cellspacing="0" style="border: 1px solid #cbd5e1; border-radius: 8px; background-color: #f0fdf4;">
                <tr>
                    <td style="background-color: #059669; color: #ffffff; padding: 8px 10px; border-top-left-radius: 7px; border-top-right-radius: 7px; text-align: center;">
                        <div style="font-size: 13pt; font-weight: bold; letter-spacing: 0.5px;">🎯 HAFTALIK ÖZET</div>
                        <div style="font-size: 8.5pt; opacity: 0.9; margin-top: 2px;">Başarı & Tamamlama Takibi</div>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 10px 12px; font-size: 8.5pt; color: #1e293b; line-height: 1.6;" valign="top">
                        <div style="margin-bottom: 6px;"><b>📊 Toplam Hedef:</b> {int(total_time/60)} saat {total_time%60} dk</div>
                        <div style="margin-bottom: 6px;"><b>📋 Görev Sayısı:</b> {sum(len(d.tasks) for d in days)} adet ödev</div>
                        <hr style="border: none; border-top: 1px dashed #cbd5e1; margin: 8px 0;"/>
                        <div style="margin-bottom: 6px;"><b>🌟 Öğrenci Tamamlama:</b></div>
                        <div>[ &nbsp; ] Tüm ödevler eksiksiz bitti</div>
                        <div>[ &nbsp; ] %80 ve üzeri tamamlandı</div>
                        <div>[ &nbsp; ] Telafi edilmesi gerekenler var</div>
                        <hr style="border: none; border-top: 1px dashed #cbd5e1; margin: 8px 0;"/>
                        <table width="100%" cellpadding="0" cellspacing="0" style="margin-top: 8px;">
                            <tr>
                                <td style="font-size: 8pt; color: #64748b;"><b>Öğretmen / Koç:</b><br/>...........................</td>
                                <td align="right" style="font-size: 8pt; color: #64748b;"><b>Öğrenci / Veli:</b><br/>...........................</td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </td>
        """
        cells_html.append(summary_cell)

        # Tablo satırlarını oluştur (2 satır x 4 sütun)
        row1_cells = "".join(cells_html[:4])
        row2_cells = "".join(cells_html[4:8])

        html = f"""
        <html>
        <head>
            <meta charset="utf-8"/>
            <style>
                body {{
                    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
                    margin: 15px;
                    color: #1e293b;
                    background-color: #ffffff;
                }}
                .header-table {{
                    width: 100%;
                    border-bottom: 2px solid #2563eb;
                    margin-bottom: 12px;
                    padding-bottom: 8px;
                }}
                h1 {{
                    color: #1e3a8a;
                    margin: 0;
                    font-size: 20pt;
                    font-weight: 800;
                }}
                h2 {{
                    color: #475569;
                    margin: 2px 0 0 0;
                    font-size: 12pt;
                    font-weight: 600;
                }}
                .meta-box {{
                    background-color: #f8fafc;
                    border: 1px solid #e2e8f0;
                    border-radius: 6px;
                    padding: 8px 12px;
                    font-size: 8.5pt;
                    color: #334155;
                    margin-bottom: 10px;
                    text-align: center;
                }}
                .coach-box {{
                    background-color: #eff6ff;
                    border-left: 4px solid #2563eb;
                    border-radius: 4px;
                    padding: 8px 12px;
                    font-size: 8.5pt;
                    color: #1e40af;
                    margin-bottom: 12px;
                    line-height: 1.4;
                }}
                .main-table {{
                    width: 100%;
                    border-collapse: collapse;
                }}
                .footer {{
                    margin-top: 14px;
                    text-align: center;
                    font-size: 8pt;
                    color: #94a3b8;
                    border-top: 1px solid #e2e8f0;
                    padding-top: 6px;
                }}
            </style>
        </head>
        <body>
            <table class="header-table" cellpadding="0" cellspacing="0">
                <tr>
                    <td>
                        <h1>📅 HAFTALIK ÇALIŞMA PLANI & TAKVİMİ</h1>
                        <h2>Öğrenci: {student_name}</h2>
                    </td>
                    <td align="right" valign="bottom" style="font-size: 9pt; color: #64748b;">
                        <b>Akademik Koçluk & Ödev Takip Sistemi</b><br/>
                        Düzenleme Tarihi: {date.today().strftime("%d.%m.%Y")}
                    </td>
                </tr>
            </table>

            <div class="meta-box">
                {meta_html}
            </div>

            <div class="coach-box">
                <b>💡 Yapay Zeka Koçluk & Çalışma Tavsiyesi:</b> {coach_note}
            </div>

            <table class="main-table" cellpadding="0" cellspacing="0">
                <tr>
                    {row1_cells}
                </tr>
                <tr>
                    {row2_cells}
                </tr>
            </table>

            <div class="footer">
                Toplam Planlanan Çalışma: <b>{int(total_time/60)} saat {total_time%60} dakika</b> &nbsp;|&nbsp; 
                <i>"Başarı, her gün tekrarlanan küçük disiplinlerin toplamıdır."</i> &nbsp;|&nbsp; 
                Öğrenci Takip v2.0
            </div>
        </body>
        </html>
        """
        return html

    @staticmethod
    def _suggest_time_window(d: _DayPlan) -> str:
        p = SmartCalendarService.POLICY
        wd = d.date_.weekday()
        if wd in (5, 6): return p["WEEKEND_SUGGEST"]
        if d.is_school_day: return p["SCHOOL_DAY_SUGGEST"]
        return p["NON_SCHOOL_WEEKDAY_SUGGEST"]

    @staticmethod
    def _day_focus(tasks: List[_Task], d: _DayPlan) -> str:
        if not tasks: return "Dinlenme"
        total = sum(t.sure for t in tasks)
        hard = sum(1 for t in tasks if t.zorluk >= 4)
        short = sum(1 for t in tasks if t.sure <= 25)

        if d.is_school_day and total >= int(d.day_cap * 0.85): return "Okul+Etüt"
        if hard >= 2 and total >= 90: return "Derin Odak"
        if short >= 2 and total <= 80: return "Hızlı Pratik"
        if total >= 150: return "Yoğun Kamp"
        return "Normal Akış"

    @staticmethod
    def _coach_note(days: List[_DayPlan], school_days_str: str, daily_max: int, weekday_target: int, weekend_target: int) -> str:
        totals = [d.total_minutes for d in days]
        total = sum(totals)
        if total <= 0: return "Henüz planlanacak ödev yok."

        spread = max(totals) - min(totals)
        school_load = sum(d.total_minutes for d in days if d.is_school_day)
        weekend_load = sum(d.total_minutes for d in days if d.date_.weekday() in (5, 6))

        msg = []
        if spread <= 45: msg.append("Bu hafta dağılımın dengeli, istikrarlı gitmelisin.")
        elif spread <= 90: msg.append("Yoğun günlerde (Deep Work) çalışmayı 45 dk'lık bloklara böl.")
        else: msg.append("Haftalık yükün dalgalı. Enerjini iyi yönet.")

        if weekend_load > school_load: msg.append("Hafta sonuna daha fazla yük koydum.")
        else: msg.append("Hafta içi tempon iyi.")
        return " ".join(msg)

    @staticmethod
    def _school_days_str(s: set) -> str:
        names = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
        if not s: return "Yok"
        if len(s) == 5 and all(x in s for x in [0,1,2,3,4]): return "Hafta İçi Tam"
        lst = sorted(list(s))
        return ", ".join(names[i] for i in lst)

    @staticmethod
    def _safe_int(x: Any, default: int = 0) -> int:
        try:
            if x is None: return default
            return int(x)
        except Exception: return default

    @staticmethod
    def _parse_date(x: Any) -> Optional[date]:
        if not x: return None
        if isinstance(x, date): return x
        s = str(x).strip()
        if not s: return None
        try: return datetime.fromisoformat(s[:19]).date()
        except Exception: pass
        try: return datetime.strptime(s[:10], "%Y-%m-%d").date()
        except Exception: pass
        try: return datetime.strptime(s[:10], "%d.%m.%Y").date()
        except Exception: return None

    @staticmethod
    def _deadline_score(d: Optional[date]) -> int:
        if not d: return 9999
        return (d - date.today()).days
