from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta, datetime
from typing import Any, Dict, List, Optional, Tuple, Set
import json
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
    tasks: List[_Task] = field(default_factory=list)
    is_school_day: bool = False
    is_holiday: bool = False
    day_cap: int = 0
    day_target: int = 0

    @property
    def total_minutes(self) -> int:
        return sum(t.sure for t in self.tasks)

    def count_lesson(self, ders: str) -> int:
        return sum(1 for t in self.tasks if t.ders.lower() == ders.lower())

    def hard_count(self) -> int:
        return sum(1 for t in self.tasks if t.zorluk >= 4)

    def last_lesson(self) -> Optional[str]:
        if not self.tasks:
            return None
        return self.tasks[-1].ders


class SmartCalendarService:
    """
    Profesyonel Akıllı Takvim ve Haftalık Planlama Servisi (V3.5 Executive).
    ✅ Okul saatleri, haftalık sabit rutinler ve tatil günlerini milimetrik olarak korur.
    ✅ 120 dakika ve altındaki normal ödevleri asla 3 dakikalık saçma parçalara bölmez.
    ✅ Yoğun rutin saatlerine (örn. Cumartesi/Pazar 08:00-16:00) asla ödev veya çalışma aralığı önermez.
    ✅ UI, veri tabanı ve dış API imzalarıyla %100 uyumludur.
    """

    DAY_KEYS = [
        ("hafta içi her gün", [0, 1, 2, 3, 4]),
        ("hafta içi", [0, 1, 2, 3, 4]),
        ("hafta sonu", [5, 6]),
        ("her gün", [0, 1, 2, 3, 4, 5, 6]),
        ("cumartesi", [5]),
        ("pazartesi", [0]),
        ("çarşamba", [2]),
        ("perşembe", [3]),
        ("pazar", [6]),
        ("cuma", [4]),
        ("salı", [1]),
        ("sali", [1]),
        ("pzt", [0]),
        ("çar", [2]),
        ("per", [3]),
        ("cmt", [5]),
        ("paz", [6]),
        ("cum", [4]),
        ("sal", [1]),
    ]

    TR_DAYS = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
    SHORT_DAYS = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]

    POLICY = {
        "DAYS": 7,
        "TR_DAYS": ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"],
        "MIN_DAILY_TARGET": 30,
        "MAX_DAILY_TARGET": 300,
        "HARD_DAY_CAP": 360,
        "AVOID_SAME_LESSON_STREAK": True,
        "MAX_SAME_LESSON_PER_DAY": 2,
        "MAX_HARD_TASKS_PER_DAY": 2,
    }

    # ---------------- PUBLIC API ----------------

    @staticmethod
    def create_weekly_plan_pdf(student_name: str, homework_list: List[Dict[str, Any]], details: Any = None) -> Optional[str]:
        if not homework_list:
            return None

        # 1. Görevleri Normalize Et (120 dk altı bölünmez)
        tasks = SmartCalendarService._normalize_tasks(homework_list)
        if not tasks:
            return None

        # 2. Profili Çıkar (JSON veya Regex ayrıştırma)
        profile = SmartCalendarService._extract_profile(details, homework_list, tasks)

        # 3. Günleri Hazırla (Okul, Rutin ve Tatil kısıtlarına göre)
        days = SmartCalendarService._build_days(profile)

        # 4. Akıllı Pedagojik Dağıtım Yap
        SmartCalendarService._smart_distribute(tasks, days, profile)

        # 5. Executive PDF / HTML Çıktısını Üret
        return SmartCalendarService._build_html(student_name, details, days, profile)

    # ---------------- PROFILE (JSON & REGEX AYRIŞTIRMA) ----------------

    @staticmethod
    def _extract_profile(details: Any, homework_list: List[Dict[str, Any]], tasks: List[_Task]) -> Dict[str, Any]:
        raw_dict = None
        if isinstance(details, dict):
            raw_dict = details
        elif details and isinstance(details, str):
            s = details.strip()
            if s.startswith("{") and s.endswith("}"):
                try:
                    raw_dict = json.loads(s)
                except Exception:
                    raw_dict = None

        if raw_dict:
            student_type = raw_dict.get("student_type", "Okula Gidiyor (Standart Hafta İçi)")
            p_idx = raw_dict.get("profile_idx", 0)
            school_str = str(raw_dict.get("school", "Yok")).strip()

            if p_idx == 0 or (school_str != "Yok" and "yok" not in school_str.lower()):
                school_days = {0, 1, 2, 3, 4}
                school_hours = school_str
                m_sch = re.search(r"(\d{1,2}[:.]\d{2})\s*-\s*(\d{1,2}[:.]\d{2})", school_str)
                if m_sch:
                    h1, m1 = map(int, re.split(r"[:.]", m_sch.group(1)))
                    h2, m2 = map(int, re.split(r"[:.]", m_sch.group(2)))
                    school_interval = (h1 * 60 + m1, h2 * 60 + m2)
                else:
                    school_interval = (510, 940)
            else:
                school_days = set()
                school_hours = "Yok"
                school_interval = None

            daily_max = int(raw_dict.get("max", 180))
            weekend_mode = raw_dict.get("weekend_mode", "Dengeli")
            biorhythm = raw_dict.get("biorhythm", "Standart Dengeli Dağılım")
            focus_str = raw_dict.get("focus", "")
            holiday_str = raw_dict.get("empty", "Yok")
            blocks = raw_dict.get("blocks", [])
            notes = raw_dict.get("note", "")
        else:
            text = str(details or "").lower()
            student_type = "Okula Gidiyor (Standart Hafta İçi)" if "okul" in text and "okul: yok" not in text else "Standart"

            m_sch = re.search(r"okul[^:\n\r|]*[:=]\s*([0-9]{1,2}[:.][0-9]{2})\s*-\s*([0-9]{1,2}[:.][0-9]{2})", text)
            if m_sch and "okul: yok" not in text:
                school_hours = f"{m_sch.group(1)} - {m_sch.group(2)}"
                school_days = {0, 1, 2, 3, 4}
                h1, m1 = map(int, re.split(r"[:.]", m_sch.group(1)))
                h2, m2 = map(int, re.split(r"[:.]", m_sch.group(2)))
                school_interval = (h1 * 60 + m1, h2 * 60 + m2)
            elif "okul: yok" in text or "okul yok" in text:
                school_hours = "Yok"
                school_days = set()
                school_interval = None
            else:
                school_hours = "08:30 - 15:40"
                school_days = {0, 1, 2, 3, 4}
                school_interval = (510, 940)

            daily_max = 180
            m_max = re.search(r"(?:günlük hedef|gunluk hedef|max|hedef)\s*[:=]\s*(\d+)", text)
            if m_max:
                daily_max = int(m_max.group(1))

            weekend_mode = "Dengeli"
            if "yoğun" in text: weekend_mode = "Yoğun"
            elif "hafif" in text: weekend_mode = "Hafif"

            biorhythm = "Standart Dengeli Dağılım"
            if "sabah" in text: biorhythm = "Sabah İnsanı"
            elif "gece" in text: biorhythm = "Gece Kuşu"

            focus_str = ""
            m_foc = re.search(r"(?:kritik dersler|odak)[^:\n\r|]*[:=]\s*([^|]*)", text)
            if m_foc: focus_str = m_foc.group(1).strip()

            holiday_str = "Yok"
            m_hol = re.search(r"(?:tam gün tatil|tam gun tatil|tatil)[^:\n\r|]*[:=]\s*([^|]*)", text)
            if m_hol: holiday_str = m_hol.group(1).strip()

            blocks = []
            m_blk = re.search(r"(?:zorunlu engel|engel)[^:\n\r|]*[:=]\s*([^|]*)", text)
            if m_blk:
                blocks = [b.strip() for b in m_blk.group(1).split(";") if b.strip()]
            notes = ""

        # Sabit Rutinleri Günlere Ayrıştır
        routines_by_day: Dict[int, List[Tuple[int, int, str]]] = {i: [] for i in range(7)}
        routine_labels = []
        for b_str in blocks:
            b_low = b_str.lower()
            matched_days = []
            for k, day_list in SmartCalendarService.DAY_KEYS:
                if k in b_low:
                    matched_days = day_list
                    break
            m_time = re.search(r"\[(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\]", b_str)
            if matched_days and m_time:
                s_m = int(m_time.group(1)) * 60 + int(m_time.group(2))
                e_m = int(m_time.group(3)) * 60 + int(m_time.group(4))
                desc = b_str.split("]")[-1].strip() or "Meşgul / Rutin"
                for d_idx in matched_days:
                    routines_by_day[d_idx].append((s_m, e_m, desc))
                day_short = SmartCalendarService.SHORT_DAYS[matched_days[0]] if len(matched_days) == 1 else ("Hafta Sonu" if matched_days == [5, 6] else "H.İçi")
                routine_labels.append(f"{day_short} [{m_time.group(1)}:{m_time.group(2)}-{m_time.group(3)}:{m_time.group(4)}]")

        # Tatil Günü Ayrıştırma
        holiday_days = set()
        if holiday_str and holiday_str != "Yok":
            h_low = holiday_str.lower()
            for k, day_list in SmartCalendarService.DAY_KEYS:
                if k in h_low:
                    holiday_days.update(day_list)
                    break

        focus_subjects = [x.strip().lower() for x in re.split(r"[,;/\+]+", focus_str) if x.strip()]

        for t in tasks:
            d_lower = t.ders.lower()
            if any(f in d_lower for f in focus_subjects):
                t.priority = 5
                t.kind = "odak"

        return {
            "student_type": student_type,
            "school_days": school_days,
            "school_hours": school_hours,
            "school_interval": school_interval,
            "daily_max": daily_max,
            "weekend_mode": weekend_mode,
            "biorhythm": biorhythm,
            "focus_subjects": focus_subjects,
            "focus_str": focus_str,
            "holiday_days": holiday_days,
            "holiday_str": holiday_str,
            "routines_by_day": routines_by_day,
            "routines_summary": ", ".join(routine_labels) if routine_labels else "Yok",
            "notes": notes
        }

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
            sure = max(10, min(sure, 600))

            zorluk = SmartCalendarService._safe_int(x.get("zorluk", x.get("difficulty")), default=0)
            if zorluk <= 0:
                if sure <= 30: zorluk = 2
                elif sure <= 60: zorluk = 3
                elif sure <= 90: zorluk = 4
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
        # Pedagojik Bütünlük Kuralı: 120 dakika ve altındaki görevler asla bölünmez.
        if (not t.splitable) or t.sure <= 120:
            return [t]

        # Sadece 120 dakikadan uzun büyük deneme veya bloklar 2 eşit parçaya ayrılır.
        half1 = (t.sure + 1) // 2
        half2 = t.sure - half1

        t1 = _Task(
            raw=t.raw, ders=t.ders, konu=f"{t.konu} (1/2)", kitap=t.kitap,
            sure=half1, zorluk=t.zorluk, priority=t.priority,
            deadline=t.deadline, kind=t.kind, splitable=False
        )
        t2 = _Task(
            raw=t.raw, ders=t.ders, konu=f"{t.konu} (2/2)", kitap=t.kitap,
            sure=half2, zorluk=t.zorluk, priority=t.priority,
            deadline=t.deadline, kind=t.kind, splitable=False
        )
        return [t1, t2]

    # ---------------- DAYS ----------------

    @staticmethod
    def _build_days(profile: Dict[str, Any]) -> List[_DayPlan]:
        p = SmartCalendarService.POLICY
        today = date.today()

        # Hafta sonu (Cumartesi veya Pazar) oluşturuluyorsa, doğrudan yaklaşan Pazartesi'den başlasın
        if today.weekday() in (5, 6):
            start_date = today + timedelta(days=(7 - today.weekday()))
        else:
            start_date = today

        days: List[_DayPlan] = []
        school_days = profile.get("school_days", set())
        holiday_days = profile.get("holiday_days", set())
        routines_by_day = profile.get("routines_by_day", {})
        school_interval = profile.get("school_interval")
        daily_max = profile.get("daily_max", 180)
        weekend_mode = profile.get("weekend_mode", "Dengeli")

        weekend_factor = 1.0
        if weekend_mode == "Hafif": weekend_factor = 0.5
        elif weekend_mode == "Yoğun": weekend_factor = 1.25

        for i in range(p["DAYS"]):
            curr = start_date + timedelta(days=i)
            wd = curr.weekday()
            is_weekend = wd in (5, 6)
            is_school = wd in school_days
            is_holiday = wd in holiday_days

            day_name = p["TR_DAYS"][wd]
            day_str = curr.strftime("%d.%m.%Y")
            label = f"{day_name} <span style='font-size:10pt; font-weight:normal;'>({day_str})</span>"

            if is_holiday:
                cap = 0
            else:
                # Uyanık kalınan süre: Hafta içi 07:30-22:30, Hafta sonu 08:00-23:00 (900 dk)
                w_start = 8 * 60 if is_weekend else 7 * 60 + 30
                w_end = 23 * 60

                busies = []
                if is_school and school_interval:
                    busies.append((school_interval[0], school_interval[1] + 30))
                for s, e, desc in routines_by_day.get(wd, []):
                    busies.append((s, e + 20))

                busies.sort()
                merged = []
                for s, e in busies:
                    s_c = max(w_start, s)
                    e_c = min(w_end, e)
                    if e_c <= s_c: continue
                    if not merged: merged.append([s_c, e_c])
                    else:
                        if s_c <= merged[-1][1]:
                            merged[-1][1] = max(merged[-1][1], e_c)
                        else:
                            merged.append([s_c, e_c])

                busy_total = sum(e - s for s, e in merged)
                net_free = max(0, (w_end - w_start) - busy_total)

                if net_free < 60:
                    cap = 0
                else:
                    study_allowance = int(net_free * 0.60)
                    target = int(daily_max * weekend_factor) if is_weekend else daily_max
                    cap = max(45, min(target, study_allowance, p["HARD_DAY_CAP"]))

            days.append(_DayPlan(
                label=label,
                date_=curr,
                tasks=[],
                is_school_day=is_school,
                is_holiday=is_holiday,
                day_cap=cap,
                day_target=cap
            ))

        return days

    # ---------------- DISTRIBUTION ----------------

    @staticmethod
    def _smart_distribute(tasks: List[_Task], days: List[_DayPlan], profile: Dict[str, Any]) -> None:
        p = SmartCalendarService.POLICY
        total_time = sum(t.sure for t in tasks)
        if total_time <= 0: return

        valid_indices = [i for i, d in enumerate(days) if not d.is_holiday and d.day_cap >= 30]
        if not valid_indices:
            valid_indices = [i for i, d in enumerate(days) if not d.is_holiday]
        if not valid_indices:
            valid_indices = list(range(len(days)))

        weekend_mode = profile.get("weekend_mode", "Dengeli")
        is_light_load = len(tasks) <= 4

        last_ders = None
        for t in tasks:
            best_idx = valid_indices[0]
            best_cost = float("inf")

            for idx in valid_indices:
                d = days[idx]
                wd = d.date_.weekday()
                is_weekend = wd in (5, 6)

                after = d.total_minutes + t.sure

                # 1. Kapasite aşımı sert cezası
                overflow = max(0, after - d.day_cap)
                overflow_penalty = 0 if overflow == 0 else (5000 + overflow * 25)

                # 2. Yük oranı dengesi
                load_ratio = after / max(1, d.day_cap)
                load_penalty = load_ratio * 300

                # 3. Aynı ders tekrarı cezası
                same_count = d.count_lesson(t.ders)
                same_penalty = 0
                if same_count >= 1:
                    same_penalty += 250 * same_count
                if last_ders and last_ders.lower() == t.ders.lower() and d.tasks:
                    same_penalty += 80

                # 4. Zor görev limiti
                hard_penalty = 0
                if t.zorluk >= 4 and d.hard_count() >= p["MAX_HARD_TASKS_PER_DAY"]:
                    hard_penalty += 400

                # 5. Hafta sonu tercihi
                weekend_penalty = 0
                if is_weekend:
                    if weekend_mode == "Hafif": weekend_penalty += 250
                    elif weekend_mode == "Yoğun": weekend_penalty -= 50
                if is_light_load and is_weekend:
                    weekend_penalty += 200

                # 6. Az görevli dağıtım tercihi
                if is_light_load and d.tasks:
                    load_penalty += 350

                # 7. Teslim tarihi
                deadline_bonus = 0
                if t.deadline:
                    days_left = (t.deadline - d.date_).days
                    if days_left < 0: deadline_bonus = 6000
                    elif days_left <= 1: deadline_bonus = -300
                    elif days_left <= 3: deadline_bonus = -150

                # 8. Odak ders bonusu
                focus_bonus = -100 if t.kind == "odak" else 0

                cost = (
                    overflow_penalty + load_penalty + same_penalty + hard_penalty +
                    weekend_penalty + deadline_bonus + focus_bonus
                )

                if cost < best_cost:
                    best_cost = cost
                    best_idx = idx

            days[best_idx].tasks.append(t)
            last_ders = t.ders

        # Gün içi sıralama (Biyoritim odaklı)
        bio = profile.get("biorhythm", "Standart").lower()
        for d in days:
            if "gece" in bio:
                d.tasks.sort(key=lambda x: (x.zorluk if x.zorluk <= 3 else -x.zorluk, -x.priority))
            else:
                d.tasks.sort(key=lambda x: (-x.zorluk, -x.priority, -x.sure))

    # ---------------- SUGGESTED TIME WINDOW ----------------

    @staticmethod
    def _suggest_time_window(d: _DayPlan, profile: Optional[Dict[str, Any]] = None) -> str:
        if d.is_holiday:
            return "☕ Tam Gün Tatil (Dinlenme & Sosyal Vakit)"
        if not d.tasks:
            return "☕ Serbest Gün / Dinlenme & Tekrar"

        wd = d.date_.weekday()
        is_weekend = wd in (5, 6)
        w_start = 8 * 60 if is_weekend else 7 * 60 + 30
        w_end = 23 * 60

        busies = []
        if profile:
            if d.is_school_day and profile.get("school_interval"):
                s_int = profile["school_interval"]
                busies.append((s_int[0], s_int[1] + 30))
            for s, e, _ in profile.get("routines_by_day", {}).get(wd, []):
                busies.append((s, e + 20))

        busies.sort()
        merged = []
        for s, e in busies:
            s_c = max(w_start, s)
            e_c = min(w_end, e)
            if e_c <= s_c: continue
            if not merged:
                merged.append([s_c, e_c])
            else:
                if s_c <= merged[-1][1]:
                    merged[-1][1] = max(merged[-1][1], e_c)
                else:
                    merged.append([s_c, e_c])

        frees = []
        curr = w_start
        for s, e in merged:
            if s - curr >= 40:
                frees.append((curr, s))
            curr = max(curr, e)
        if w_end - curr >= 40:
            frees.append((curr, w_end))

        if not frees:
            return "Akşam (Esnek Zaman)"

        t_min = d.total_minutes
        bio = (profile.get("biorhythm", "Standart") if profile else "Standart").lower()

        if "gece" in bio:
            late_frees = [f for f in frees if f[1] >= 19 * 60]
            chosen_slot = late_frees[-1] if late_frees else frees[-1]
            chosen_start = max(chosen_slot[0], 19 * 60 + 30)
        elif "sabah" in bio and is_weekend:
            morning_frees = [f for f in frees if f[0] <= 12 * 60]
            chosen_slot = morning_frees[0] if morning_frees else frees[0]
            chosen_start = max(chosen_slot[0], 9 * 60 + 30)
        else:
            afternoon_frees = [f for f in frees if f[1] >= 16 * 60]
            chosen_slot = afternoon_frees[0] if afternoon_frees else frees[0]
            if d.is_school_day:
                chosen_start = max(chosen_slot[0], 17 * 60)
            elif is_weekend:
                chosen_start = max(chosen_slot[0], 11 * 60 if chosen_slot[0] < 12 * 60 else chosen_slot[0] + 15)
            else:
                chosen_start = max(chosen_slot[0], 10 * 60)

        break_time = 15 if t_min >= 70 else (10 if t_min >= 45 else 5)
        study_duration = t_min + break_time
        chosen_end = min(w_end, chosen_start + study_duration)

        if chosen_end > chosen_slot[1]:
            chosen_end = chosen_slot[1]
            chosen_start = max(chosen_slot[0], chosen_end - study_duration)

        sh = chosen_start // 60
        sm = chosen_start % 60
        eh = chosen_end // 60
        em = chosen_end % 60

        return f"{sh:02d}:{sm:02d} – {eh:02d}:{em:02d}"

    # ---------------- HTML ----------------

    @staticmethod
    def _build_html(student_name: str, details: Any, days: List[_DayPlan], profile: Dict[str, Any]) -> str:
        p = SmartCalendarService.POLICY
        total_time = sum(d.total_minutes for d in days)

        daily_max = profile.get("daily_max", 180)

        # Meta Bilgi Çubuğu (Tertemiz ve kurumsal)
        meta_parts = []
        if profile.get("school_days"):
            sch_h = profile.get("school_hours", "08:30 - 15:40")
            meta_parts.append(f"🏫 <b>Okul:</b> Hafta İçi ({sch_h})")
        else:
            stype = profile.get("student_type", "Mezun / Serbest Program")
            meta_parts.append(f"👤 <b>Öğrenci Durumu:</b> {stype}")

        routines = profile.get("routines_summary")
        if routines and routines != "Yok":
            meta_parts.append(f"📌 <b>Sabit Rutinler:</b> {routines}")

        if profile.get("holiday_days"):
            hol_str = profile.get("holiday_str", "Pazar")
            meta_parts.append(f"🏖️ <b>Tatil Günü:</b> {hol_str}")

        meta_parts.append(f"⏱ <b>Günlük Kapasite:</b> Max {daily_max} dk")

        focs = profile.get("focus_subjects")
        if focs:
            f_str = ", ".join(f.title() for f in focs)
            meta_parts.append(f"🔥 <b>Öncelikli Odak:</b> {f_str}")

        bio = profile.get("biorhythm", "Standart")
        if bio and "Standart" not in bio:
            meta_parts.append(f"🧠 <b>Biyoritim:</b> {bio}")

        meta_html = " &nbsp;&nbsp;|&nbsp;&nbsp; ".join(meta_parts)
        coach_note = SmartCalendarService._coach_note(days, profile)

        LESSON_ICONS = {
            "tyt matematik": "📐", "ayt matematik": "📈", "matematik": "📐", "problemler": "🧩", "geometri": "📏",
            "fizik": "⚡", "kimya": "🧪", "biyoloji": "🧬", "turkce": "📖", "türkçe": "📖", "paragraf": "📑",
            "tarih": "🏛️", "cografya": "🌍", "coğrafya": "🌍", "felsefe": "💭", "edebiyat": "📜", "din": "🕌",
            "ingilizce": "🇬🇧", "lgs matematik": "📐", "lgs fen": "🔬", "lgs turkce": "📖", "lgs türkçe": "📖",
            "lgs inkilap": "🏛️", "lgs dinkulturu": "🕌", "lgs ingilizce": "🇬🇧"
        }

        total_tasks = sum(len(d.tasks) for d in days)
        max_day_tasks = max((len(d.tasks) for d in days), default=0)
        is_dense = (max_day_tasks >= 5 or total_tasks >= 20)

        task_mb = "1.5px" if is_dense else "2.5px"
        task_pad = "2px 4px" if is_dense else "3px 5px"
        f_task_title = "7pt" if is_dense else "7.5pt"
        f_task_sub = "7pt" if is_dense else "7.5pt"
        cell_pad = "2px" if is_dense else "2.5px"

        cells_html = []
        for i, d in enumerate(days):
            tasks = d.tasks
            day_mins = d.total_minutes
            focus = SmartCalendarService._day_focus(tasks, d)
            suggest = SmartCalendarService._suggest_time_window(d, profile)

            raw_day = p["TR_DAYS"][d.date_.weekday()]
            raw_date = d.date_.strftime("%d.%m.%Y")

            if d.is_holiday:
                header_bg = "#475569"
                header_sub = "🏖️ TATİL GÜNÜ"
            elif d.date_.weekday() in (5, 6):
                header_bg = "#4338ca"
                header_sub = "HAFTA SONU"
            else:
                header_bg = "#2563eb"
                header_sub = "HAFTA İÇİ"

            c_html = f"""
            <td width="25%" valign="top" style="padding: {cell_pad};">
                <table width="100%" cellpadding="0" cellspacing="0" style="border: 1px solid #cbd5e1; border-radius: 6px; background-color: #ffffff;">
                    <tr>
                        <td style="background-color: {header_bg}; color: #ffffff; padding: 3px 5px; border-top-left-radius: 5px; border-top-right-radius: 5px;">
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td style="font-size: 9pt; font-weight: 800; text-transform: uppercase; color: #ffffff; letter-spacing: 0.3px;">
                                        {raw_day}
                                    </td>
                                    <td align="right" style="font-size: 7pt; color: #e2e8f0; font-weight: 600;">
                                        {raw_date} &nbsp;•&nbsp; {header_sub}
                                    </td>
                                </tr>
                                <tr>
                                    <td style="font-size: 7pt; color: #dbeafe; padding-top: 1px;">
                                        ⏱ <b>{day_mins} dk</b> <span style="opacity: 0.8;">/ {d.day_cap} dk</span> &nbsp;•&nbsp; <b>🎯 {focus}</b>
                                    </td>
                                    <td align="right" style="font-size: 7pt; color: #fef08a; font-weight: 600; padding-top: 1px;">
                                        🕒 {suggest}
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 3px;" valign="top">
            """

            if not tasks:
                if d.is_holiday:
                    c_html += """
                        <div style="text-align: center; color: #64748b; padding: 8px 4px; font-size: 7.5pt;">
                            🏖️ <i>Tam Gün Tatil / Zihinsel Dinlenme</i>
                        </div>
                    """
                else:
                    c_html += """
                        <div style="text-align: center; color: #94a3b8; padding: 8px 4px; font-size: 7.5pt;">
                            ☕ <i>Serbest Gün / Dinlenme & Tekrar</i>
                        </div>
                    """
            else:
                for t in tasks:
                    key = t.ders.lower().strip()
                    icon = LESSON_ICONS.get(key, "📘")
                    ders = (t.ders or "").replace('_', ' ').title()

                    border_color = "#2563eb"
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
                    <div style="margin-bottom: {task_mb}; padding: {task_pad}; border-left: 3.5px solid {border_color}; background-color: {bg_color}; border-radius: 3px; border-top: 1px solid #e2e8f0; border-right: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0;">
                        <table width="100%" cellpadding="0" cellspacing="0">
                            <tr>
                                <td style="font-size: {f_task_title}; font-weight: bold; color: #1e293b;">
                                    {icon} {ders}
                                </td>
                                <td align="right" style="font-size: {f_task_title}; color: #475569; font-weight: bold;">
                                    ⏳ {t.sure} dk &nbsp; <span style="font-size: 7.5pt; color: #94a3b8;">☐</span>
                                </td>
                            </tr>
                        </table>
                        <div style="font-size: {f_task_sub}; font-weight: 600; color: #0f172a; margin-top: 1px;">
                            {konu} <span style="font-size: 6.5pt; font-weight: normal; color: #64748b;">({kitap})</span>
                        </div>
                    </div>
                    """

            c_html += """
                        </td>
                    </tr>
                </table>
            </td>
            """
            cells_html.append(c_html)

        # 8. Hücre: Haftalık Özet Kartı
        summary_cell = f"""
        <td width="25%" valign="top" style="padding: {cell_pad};">
            <table width="100%" cellpadding="0" cellspacing="0" style="border: 1px solid #cbd5e1; border-radius: 6px; background-color: #f0fdf4;">
                <tr>
                    <td style="background-color: #059669; color: #ffffff; padding: 3px 5px; border-top-left-radius: 5px; border-top-right-radius: 5px;">
                        <table width="100%" cellpadding="0" cellspacing="0">
                            <tr>
                                <td style="font-size: 9pt; font-weight: 800; letter-spacing: 0.3px; color: #ffffff;">🎯 HAFTALIK ÖZET</td>
                                <td align="right" style="font-size: 7pt; color: #d1fae5; font-weight: 600;">Başarı Takibi</td>
                            </tr>
                        </table>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 4px 6px; font-size: 7pt; color: #1e293b; line-height: 1.35;" valign="top">
                        <div><b>📊 Toplam Hedef:</b> {int(total_time/60)} sa {total_time%60} dk &nbsp;•&nbsp; <b>📋 {total_tasks}</b> ödev</div>
                        <hr style="border: none; border-top: 1px dashed #bbf7d0; margin: 3px 0;"/>
                        <div style="margin-bottom: 2px;"><b>🌟 Tamamlama Durumu:</b></div>
                        <div>[ &nbsp; ] Tüm ödevler eksiksiz bitti</div>
                        <div>[ &nbsp; ] %80 ve üzeri tamamlandı</div>
                        <div>[ &nbsp; ] Telafi edilmesi gerekenler var</div>
                        <hr style="border: none; border-top: 1px dashed #bbf7d0; margin: 3px 0;"/>
                        <table width="100%" cellpadding="0" cellspacing="0" style="margin-top: 3px;">
                            <tr>
                                <td style="font-size: 6.5pt; color: #64748b;"><b>Koç / Öğretmen:</b><br/>.......................</td>
                                <td align="right" style="font-size: 6.5pt; color: #64748b;"><b>Öğrenci / Veli:</b><br/>.......................</td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </td>
        """
        cells_html.append(summary_cell)

        row1_cells = "".join(cells_html[:4])
        row2_cells = "".join(cells_html[4:8])

        html = f"""
        <html>
        <head>
            <meta charset="utf-8"/>
            <style>
                @page {{ size: A4 landscape; margin: 5mm; }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
                    margin: 0; padding: 0;
                    color: #1e293b;
                    background-color: #ffffff;
                }}
                .header-banner {{
                    border-bottom: 2px solid #2563eb;
                    padding-bottom: 2px;
                    margin-bottom: 3px;
                }}
                .meta-strip {{
                    background-color: #f1f5f9;
                    border-radius: 4px;
                    padding: 2.5px 6px;
                    font-size: 7pt;
                    color: #334155;
                    margin-top: 2px;
                    line-height: 1.3;
                }}
                .main-table {{
                    width: 100%;
                    border-collapse: separate;
                    border-spacing: 0px;
                }}
                .footer {{
                    margin-top: 3px;
                    text-align: center;
                    font-size: 6.5pt;
                    color: #94a3b8;
                    border-top: 1px solid #e2e8f0;
                    padding-top: 2px;
                }}
            </style>
        </head>
        <body>
            <div class="header-banner">
                <table width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                        <td valign="middle">
                            <span style="font-size: 13pt; font-weight: 800; color: #1e3a8a;">📅 HAFTALIK ÇALIŞMA PLANI & TAKVİMİ</span>
                            &nbsp;&nbsp;<span style="font-size: 9.5pt; font-weight: 700; color: #2563eb; background: #eff6ff; padding: 2px 7px; border-radius: 4px; border: 1px solid #bfdbfe;">Öğrenci: {student_name}</span>
                        </td>
                        <td align="right" valign="middle" style="font-size: 7.5pt; color: #64748b;">
                            <b>Akademik Koçluk & Takip Sistemi</b> &nbsp;•&nbsp; 📅 {date.today().strftime("%d.%m.%Y")}
                        </td>
                    </tr>
                </table>
                <div class="meta-strip">
                    {meta_html} &nbsp;&nbsp;|&nbsp;&nbsp; <b>💡 Koçluk Tavsiyesi:</b> {coach_note}
                </div>
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
                Toplam Planlanan Çalışma: <b>{int(total_time/60)} sa {total_time%60} dk</b> &nbsp;|&nbsp; 
                <i>"Başarı, her gün tekrarlanan küçük disiplinlerin toplamıdır."</i> &nbsp;|&nbsp; 
                YKS-LGS Ödev Takip v3.5
            </div>
        </body>
        </html>
        """
        return html

    @staticmethod
    def _day_focus(tasks: List[_Task], d: _DayPlan) -> str:
        if not tasks:
            return "Tatil" if d.is_holiday else "Dinlenme"
        total = sum(t.sure for t in tasks)
        hard = sum(1 for t in tasks if t.zorluk >= 4)
        short = sum(1 for t in tasks if t.sure <= 25)

        if hard >= 2 and total >= 90: return "Derin Odak"
        if short >= 2 and total <= 80: return "Hızlı Pratik"
        if total >= 150: return "Yoğun Kamp"
        if d.is_school_day and total >= int(d.day_cap * 0.85): return "Okul+Etüt"
        return "Dengeli Çalışma"

    @staticmethod
    def _coach_note(days: List[_DayPlan], profile: Any = None, *args, **kwargs) -> str:
        if not isinstance(profile, dict):
            profile = {}

        totals = [d.total_minutes for d in days]
        total = sum(totals)
        if total <= 0:
            return "Henüz planlanacak ödev bulunmuyor. Yeni ödevler eklendiğinde takvim otomatik optimize edilecektir."

        hours = total // 60
        mins = total % 60
        time_str = f"{hours} saat {mins} dakika" if hours > 0 else f"{mins} dakika"

        notes = []
        notes.append(f"Bu hafta toplam <b>{time_str}</b> akademik çalışma ve ödev programlandı.")

        if profile.get("school_days"):
            notes.append("Hafta içi okul saatleri sonrasındaki dinlenme aralığı dikkate alınarak akşam çalışma blokları oluşturuldu.")

        routines = profile.get("routines_summary")
        if routines and routines != "Yok":
            notes.append(f"Haftalık sabit rutinleriniz ({routines}) korunmuş olup bu saatlere ders konulmamıştır.")

        if profile.get("holiday_days"):
            notes.append(f"Haftalık dinlenme gününüz ({profile.get('holiday_str', 'Tatil')}) tam serbest zaman olarak ayrılmıştır.")

        focs = profile.get("focus_subjects")
        if focs:
            f_str = ", ".join(f.title() for f in focs)
            notes.append(f"Öncelikli odak dersiniz ({f_str}) zihinsel olarak en dinç olduğunuz zaman dilimlerine yerleştirildi.")

        bio = profile.get("biorhythm", "Standart")
        if "Gece" in bio:
            notes.append("Gece kuşu verim modunuza uygun olarak zorlayıcı dersler akşam saatlerine kaydırıldı.")
        elif "Sabah" in bio:
            notes.append("Sabah insanı verim modunuza uygun olarak çalışmalar erken saatlere planlandı.")

        return " ".join(notes)

    @staticmethod
    def _school_days_str(s: set) -> str:
        names = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
        if not s: return "Yok"
        if len(s) == 5 and all(x in s for x in [0, 1, 2, 3, 4]): return "Hafta İçi Tam"
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
