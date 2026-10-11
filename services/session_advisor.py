# -*- coding: utf-8 -*-
"""Conservative one-click session advisor, not a duration-tracking device.

Only explicit, date-distinct teacher/student observations can change a session
length. Homework completion is read-only context and is NEVER treated as proof
of actual uninterrupted study minutes. No background task or database writes.
"""
from __future__ import annotations

from datetime import date, timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Any

from services.plan_profile_store import profile_path

RATINGS = {"hard": "Zorlandı", "ok": "Uygundu", "easy": "Rahat çalıştı"}


def feedback_path() -> Path:
    return profile_path().with_name("plan_session_feedback.json")


def _sid(student_id: Any) -> str:
    sid = str(student_id).strip() if student_id is not None else ""
    if not sid or len(sid) > 128:
        raise ValueError("Öğrencinin kayıtlı kimliği gerekli.")
    return sid


def _read_store(path: Path) -> dict:
    if not path.is_file():
        return {"version": 1, "students": {}}
    with path.open("r", encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("students"), dict):
        raise ValueError("Etüt geri bildirim dosyası geçersiz; üzerine yazılmadı.")
    for sid, entries in data["students"].items():
        if not isinstance(sid, str) or not isinstance(entries, dict):
            raise ValueError("Etüt geri bildirim dosyası hatalı; üzerine yazılmadı.")
        if not all(isinstance(k, str) and v in RATINGS for k,v in entries.items()):
            raise ValueError("Etüt geri bildirim dosyası hatalı; üzerine yazılmadı.")
    return data


def _write_store(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".etut-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def record_feedback(student_id: Any, rating: str, *, path: Path | None = None,
                    day: date | None = None) -> dict:
    """A new click on the same day replaces the day's observation, never boosts N."""
    sid = _sid(student_id)
    if rating not in RATINGS:
        raise ValueError("Geçersiz geri bildirim.")
    path = path or feedback_path()
    data = _read_store(path)
    current = day or date.today()
    entries = data["students"].setdefault(sid, {})
    entries[current.isoformat()] = rating
    # Retain a bounded, recent set; invalid dates are ignored, not counted.
    latest = max(current, date.today())
    cutoff = latest - timedelta(days=90)
    for k in list(entries):
        try:
            if not cutoff <= date.fromisoformat(k) <= latest:
                entries.pop(k, None)
        except ValueError:
            entries.pop(k, None)
    if len(entries) > 90:
        for k in sorted(entries)[:-90]:
            entries.pop(k, None)
    _write_store(path, data)
    return dict(entries)


def recent_feedback(student_id: Any, *, path: Path | None = None,
                    today: date | None = None, horizon: int = 28) -> dict:
    sid = _sid(student_id)
    stored = _read_store(path or feedback_path())["students"].get(sid, {})
    current = today or date.today()
    cutoff = current - timedelta(days=horizon)
    result = {}
    for k, v in stored.items():
        try:
            if cutoff <= date.fromisoformat(k) <= current and v in RATINGS:
                result[k] = v
        except (ValueError, TypeError):
            pass
    return dict(sorted(result.items()))


def homework_summary(con: sqlite3.Connection, student_id: Any, *, today: date | None = None) -> dict:
    """Read-only due homework context; cannot estimate actual focus duration."""
    sid = _sid(student_id)
    current = today or date.today()
    since = current - timedelta(days=60)
    summary = {"available": False, "due": 0, "done": 0, "note": "Ödev verisine ulaşılamadı."}
    try:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "odev_kume" not in tables:
            return summary
        table = "odev_satir" if "odev_satir" in tables else "odev" if "odev" in tables else None
        if not table:
            return summary
        # Restrict to fully elapsed due dates and recent sets; no future unfinished
        # tasks are mislabeled as underperformance.
        rows = con.execute(f"""SELECT lower(trim(COALESCE(o.durum,''))) AS durum
            FROM {table} o JOIN odev_kume k ON k.id = o.kume_id
            WHERE o.ogrenci_id=? AND date(k.bitis_tarihi) >= ?
            AND date(k.bitis_tarihi) < ? LIMIT 301""",
            (sid, since.isoformat(), current.isoformat())).fetchall()
        if len(rows) > 300:
            return {"available": False,"due": 0,"done": 0,
                    "note": "Çok sayıda ödev var; eksiksiz oran hesaplanmadı."}
        done_words = {"tamam", "tamamlandı", "tamamlandi", "yapıldı", "yapildi", "bitti", "bitirildi", "done", "ok"}
        summary.update(available=True, due=len(rows),
                       done=sum(1 for r in rows if r[0] in done_words),
                       note="Son 60 gündeki vadesi geçmiş ödev kayıtları (süre ölçümü değildir).")
        return summary
    except (sqlite3.DatabaseError, ValueError, TypeError) as exc:
        summary["note"] = f"Ödev durumları okunamadı ({type(exc).__name__})."
        return summary


def suggest_session_minutes(current_minutes: int, feedback: dict,
                            homework: dict | None = None,
                            last_applied_signature: str | None = None) -> dict:
    """Conservative, explainable rule; no inference from mere assignment status.

    Require ≥3 separate days. Mixed opinions or poor assignment completion
    never automatically increase a student's session length.
    """
    current = max(15, min(180, int(current_minutes)))
    valid = [(k, v) for k, v in sorted(feedback.items()) if v in RATINGS]
    digest = sha256(json.dumps(valid, ensure_ascii=False).encode("utf-8")).hexdigest()
    result = {"suggested": current, "ready": False, "reason": "", "samples": len(valid),
              "signature": digest, "direction": "keep"}
    if len(valid) < 3:
        result["reason"] = f"Henüz {len(valid)}/3 farklı gün kaydı var. Mevcut {current} dk korunuyor."
        return result
    if digest == last_applied_signature:
        result["reason"] = "Bu gözlemler daha önce uygulandı. Yeni günlerden veri bekleniyor."
        return result
    last = [v for _, v in valid[-5:]]
    hard, easy = last.count("hard"), last.count("easy")
    if hard >= 3 and hard >= easy + 2:
        new = max(15, current - 10)
        result.update(suggested=new, direction="decrease", ready=new != current,
                      reason=f"Son {len(last)} farklı günde {hard} kez zorlanma bildirildi. 10 dk daha kısa oturum denenebilir.")
    elif easy >= 3 and hard == 0:
        due = int((homework or {}).get("due", 0) or 0)
        done = int((homework or {}).get("done", 0) or 0)
        if due >= 8 and done / due < .5:
            result["reason"] = "Ödev tamamlama oranı düşük; yalnızca rahatlık bildirimine dayanarak süre artırılmadı."
        else:
            new = min(180, current + 5)
            result.update(suggested=new, direction="increase", ready=new != current,
                          reason=f"Son {len(last)} farklı günde {easy} kez rahat çalıştığı bildirildi. 5 dk artırma denenebilir.")
    else:
        result["reason"] = "Gözlemler karışık veya süre uygun görünüyor. Mevcut oturum korunuyor."
    if not result["ready"] and result["suggested"] == current:
        result["direction"] = "keep"
    return result


def personal_profile_update(profiles: dict, current_name: str, student_id: Any,
                            new_minutes: int, signature: str) -> tuple[dict, str]:
    """Pure copy-on-write specialization: a shared profile is NEVER changed."""
    sid = _sid(student_id)
    source = profiles.get(current_name)
    if not current_name or not isinstance(source, dict):
        raise ValueError("Kayıtlı bir profil seçilmelidir.")
    if not isinstance(new_minutes, int) or not 15 <= new_minutes <= 180:
        raise ValueError("Önerilen süre geçersiz.")
    if not isinstance(signature, str) or len(signature) != 64:
        raise ValueError("Öneri doğrulama kodu geçersiz.")
    if source.get("_session_advisor_owner") == sid:
        name = current_name
    else:
        base = f"{current_name} · Kişisel {sha256(sid.encode('utf-8')).hexdigest()[:8]}"
        name = base
        counter = 2
        while name in profiles and profiles[name].get("_session_advisor_owner") != sid:
            name = f"{base}-{counter}"
            counter += 1
    target = profiles.get(name, source)
    if target.get("_session_advisor_last_applied") == signature:
        raise ValueError("Aynı gözlemler bu öğrenciye daha önce uygulandı.")
    # If an existing personal profile is selected indirectly via a shared
    # template, do not replace manually edited session values with a stale one.
    if target is not source and target.get("session_minutes") != source.get("session_minutes"):
        raise ValueError("Bu öğrencinin kişisel profili zaten var. Önce o profili seçin.")
    copy = dict(target)
    copy.update(session_enabled=True, session_minutes=new_minutes,
                _session_advisor_owner=sid,
                _session_advisor_last_applied=signature,
                _session_advisor_source=source.get("_session_advisor_source", current_name))
    updated = dict(profiles)
    updated[name] = copy
    return updated, name
