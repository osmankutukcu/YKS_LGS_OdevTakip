"""services/routine_homework_helper.py

Paragraf ve Problemler için koç tercihlerini (soru sayısı, süre, gün) hatırlayan
ve öğrencinin kitaplarına göre otomatik haftalık rutin ödev taslağı oluşturan yardımcı servis.
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

DAYS_7 = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
DAYS_5 = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma"]

DEFAULT_ROUTINE_PREFS = {
    "paragraf": {"soru": 20, "sure": 25, "gun": 7},
    "problemler": {"soru": 15, "sure": 30, "gun": 7},
}


def _get_routine_settings_file() -> Path:
    """Windows (%LOCALAPPDATA%), macOS ve Linux standartlarında güvenli kullanıcı ayar dosyası.

    Program Files (x86) izin hatasını (Permission Denied) kesin olarak engeller.
    """
    target_dir: Optional[Path] = None

    # 1. Öncelik: Merkezi platform veri dizini (Windows'ta %LOCALAPPDATA%\YKS_LGS_HomeworkManager)
    try:
        from db import _platform_appdata_dir
        target_dir = _platform_appdata_dir()
    except Exception:
        pass

    # 2. Öncelik: Windows doğrudan LOCALAPPDATA / APPDATA kontrolü
    if target_dir is None:
        if sys.platform == "win32":
            local_base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
            if local_base:
                target_dir = Path(local_base) / "YKS_LGS_HomeworkManager"
        elif sys.platform == "darwin":
            target_dir = Path.home() / "Library" / "Application Support" / "YKS_LGS_HomeworkManager"
        else:
            xdg = os.environ.get("XDG_DATA_HOME")
            target_dir = (Path(xdg) if xdg else Path.home() / ".local" / "share") / "YKS_LGS_HomeworkManager"

    if target_dir is None:
        target_dir = Path.home() / ".yks_lgs_manager"

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    target_file = target_dir / "routine_defaults.json"

    # Eski konumlarda dosya varsa otomatik yeni güvenli konuma taşı/aktar
    if not target_file.exists():
        legacy_candidates = [
            Path.home() / ".yks_lgs_manager" / "routine_defaults.json",
            Path.home() / "AppData" / "Roaming" / "YKS_LGS_OdevTakip" / "routine_defaults.json",
            Path.cwd() / "routine_defaults.json",
        ]
        for old_file in legacy_candidates:
            if old_file.exists() and old_file != target_file:
                try:
                    target_file.write_text(old_file.read_text(encoding="utf-8"), encoding="utf-8")
                    break
                except Exception:
                    pass

    return target_file


def load_routine_defaults(lesson: str) -> Dict[str, int]:
    """Koçun ilgili ders için son kaydettiği soru, süre ve gün tercihlerini yükler."""
    lesson_key = (lesson or "").strip().lower()
    fallback = DEFAULT_ROUTINE_PREFS.get(lesson_key, {"soru": 20, "sure": 25, "gun": 7}).copy()
    fpath = _get_routine_settings_file()
    if not fpath.exists():
        return fallback
    try:
        data = json.loads(fpath.read_text(encoding="utf-8"))
        if isinstance(data, dict) and lesson_key in data:
            val = data[lesson_key]
            if isinstance(val, dict):
                return {
                    "soru": int(val.get("soru", fallback["soru"])),
                    "sure": int(val.get("sure", fallback["sure"])),
                    "gun": int(val.get("gun", fallback["gun"])),
                }
    except Exception:
        pass
    return fallback


def save_routine_defaults(lesson: str, soru: int, sure: int, gun: int = 7) -> None:
    """Koç soru veya süre değerini değiştirdiğinde kalıcı olarak kaydeder."""
    lesson_key = (lesson or "").strip().lower()
    fpath = _get_routine_settings_file()
    all_data = {}
    if fpath.exists():
        try:
            all_data = json.loads(fpath.read_text(encoding="utf-8"))
            if not isinstance(all_data, dict):
                all_data = {}
        except Exception:
            all_data = {}
    all_data[lesson_key] = {
        "soru": max(1, int(soru)),
        "sure": max(5, int(sure)),
        "gun": 5 if gun == 5 else 7,
    }
    try:
        fpath.write_text(json.dumps(all_data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        print("Rutin tercihleri kaydedilemedi:", exc)


def generate_routine_tasks(
    lesson: str,
    books: List[str],
    selected_book_mode: str,
    days_count: int,
    questions_per_day: int,
    duration_minutes: int,
    table: Any
) -> List[Dict[str, Any]]:
    """Tablodaki sıradaki haftalık satırı (1 satır = 1 hafta rutini) tespit ederek

    haftalık ödev görev(ler)i üretir. 40 satır = 40 haftalık tüm sezona yeter.
    """
    from PyQt6.QtCore import Qt

    if not books or table is None:
        return []

    active_books = [b for b in books if b and b.strip()]
    if not active_books:
        return []

    # Kitap - Kolon eşleştirmesi
    book_col_map = {}
    for col in range(1, table.columnCount()):
        hdr = table.horizontalHeaderItem(col)
        if hdr:
            book_col_map[hdr.text().strip()] = col

    def _find_next_available_row(col_idx: int) -> tuple[int, str]:
        for r in range(table.rowCount()):
            item = table.item(r, col_idx)
            if item is None:
                continue
            # Kilitli mi?
            if not (item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                continue
            # Zaten işaretli mi?
            if item.checkState() == Qt.CheckState.Checked:
                continue
            # Renk kilidi var mı?
            bg = item.background().color() if hasattr(item.background(), "color") else None
            if bg and bg.name().lower() in {"#a5d6a7", "#c8e6c9", "#fff59d", "#fca5a5", "#fecaca"}:
                continue

            topic_item = table.item(r, 0)
            if not topic_item:
                continue
            topic_name = topic_item.text().strip()
            if not topic_name:
                continue
            return r, topic_name
        return -1, ""

    tasks: List[Dict[str, Any]] = []
    days = 5 if days_count == 5 else 7
    is_alternating = (selected_book_mode == "__ALL_ALTERNATING__" or (len(active_books) > 1 and selected_book_mode == ""))

    if is_alternating and len(active_books) > 1:
        # Çoklu kitap: Günleri kitaplar arasında paylaştır ama AYNI HAFTAYA (sıradaki boş haftalık satıra) ata
        num_books = len(active_books)
        base_days = days // num_books
        rem_days = days % num_books

        for b_idx, book_name in enumerate(active_books):
            target_col = book_col_map.get(book_name)
            if target_col is None:
                continue

            r, topic_name = _find_next_available_row(target_col)
            if r < 0:
                continue

            b_days = base_days + (1 if b_idx < rem_days else 0)
            if b_days <= 0:
                continue

            b_questions = b_days * questions_per_day
            b_duration = b_days * duration_minutes
            aciklama = f"🎯 {b_questions} Soru / {b_duration} dk (Dönüşümlü: {b_days} Gün x {questions_per_day})"

            tasks.append({
                "ders": lesson,
                "kitap": book_name,
                "konu": topic_name,
                "dk": b_duration,
                "aciklama": aciklama,
                "_row": r,
                "_col": target_col,
            })
    else:
        # Tek kitap: Sıradaki 1 haftalık satırı seç (1 Satır = 1 Hafta)
        target_book = selected_book_mode if selected_book_mode in active_books else active_books[0]
        target_col = book_col_map.get(target_book)
        if target_col is not None:
            r, topic_name = _find_next_available_row(target_col)
            if r >= 0:
                total_q = days * questions_per_day
                total_duration = days * duration_minutes
                days_label = "7 Gün" if days == 7 else "5 Gün"
                aciklama = f"🎯 {total_q} Soru / {total_duration} dk ({days_label}: Günde {questions_per_day})"

                tasks.append({
                    "ders": lesson,
                    "kitap": target_book,
                    "konu": topic_name,
                    "dk": total_duration,
                    "aciklama": aciklama,
                    "_row": r,
                    "_col": target_col,
                })

    return tasks


