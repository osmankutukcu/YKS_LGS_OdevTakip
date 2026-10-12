"""V13.6: manual, evidence-preserving repair proposals applied ONLY to a new DB copy.

No automatic repair of orphaned homework links.  Operators explicitly choose a
resolution, justify it, and approve before an isolated, transactional copy is
created. The source SQLite database is never opened writable.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import unicodedata
from typing import Any

from services.homework_integrity_v135 import audit_database

REVIEW = "review"
UNLINK = "unlink"
RELINK = "relink"
ACKNOWLEDGEMENT = "ONAYLI_KOPYA_OLUSTUR"
FIELDS = ("id", "ogrenci_id", "kume_id", "odev_id", "ders", "kitap", "konu", "kitap_ad", "konu_ad", "durum", "silindi")


class ReconciliationError(ValueError):
    """Refuse an unsafe or out-of-date reconciliation plan."""


def _json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")


def _digest(value: Any) -> str:
    return sha256(_json(value)).hexdigest()


def _read_connection(path: Path) -> sqlite3.Connection:
    if not path.is_file() or not path.stat().st_size:
        raise ReconciliationError("Kaynak veritabanı bulunamadı veya boş.")
    con = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    return con


def _check_schema(con: sqlite3.Connection) -> None:
    for table, columns in {"odev_satir": set(FIELDS), "odev": {"id", "ogrenci_id", "kume_id", "ders", "kitap_ad", "konu_ad"}}.items():
        actual = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
        if not columns.issubset(actual):
            raise ReconciliationError(f"{table} tablosunda beklenen alanlar eksik: {sorted(columns - actual)}")
    if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise ReconciliationError("Kaynak veritabanının SQLite bütünlük testi başarısız.")


def _row(con: sqlite3.Connection, sid: int) -> dict | None:
    result = con.execute(f"SELECT {', '.join(FIELDS)} FROM odev_satir WHERE id=?", (sid,)).fetchone()
    return dict(result) if result else None


def _canon(x: Any) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(x or "")).strip().replace("İ", "i").replace("I", "ı").casefold().split())


def _label(row: dict) -> tuple[str, str, str]:
    return (_canon(row.get("ders")), _canon(row.get("kitap_ad") or row.get("kitap")), _canon(row.get("konu_ad") or row.get("konu")))


def _matching_candidates(con: sqlite3.Connection, row: dict) -> list[int]:
    """Possible review evidence, not a decision or automated match."""
    if row.get("ogrenci_id") is None or row.get("kume_id") is None:
        return []
    matches = []
    for parent in con.execute("SELECT id,ders,kitap_ad,konu_ad FROM odev WHERE ogrenci_id=? AND kume_id=? ORDER BY id", (row["ogrenci_id"], row["kume_id"])):
        if _label(row) == _label(dict(parent)) and all(_label(row)):
            used = con.execute("SELECT 1 FROM odev_satir WHERE odev_id=? LIMIT 1", (parent["id"],)).fetchone()
            if not used:
                matches.append(int(parent["id"]))
    return matches[:25]


def build_review_manifest(db_path: str | Path) -> dict:
    """Read-only review list. Contains IDs/hashes, never pupil names or contact info."""
    source = Path(db_path)
    con = _read_connection(source)
    try:
        _check_schema(con)
        cases = []
        for entry in con.execute("""SELECT s.id FROM odev_satir s LEFT JOIN odev o ON o.id=s.odev_id
                                    WHERE s.odev_id IS NOT NULL AND o.id IS NULL ORDER BY s.id""").fetchall():
            row = _row(con, entry["id"])
            cases.append({"satir_id": row["id"], "ogrenci_id": row["ogrenci_id"],
                          "kume_id": row["kume_id"], "eski_odev_id": row["odev_id"],
                          "satir_ozeti_sha256": _digest(row), "olasi_aday_idleri": _matching_candidates(con, row),
                          "islem": REVIEW, "yeni_odev_id": None, "gerekce": ""})
        return {"format": "odev-link-review-v136", "olusturma_utc": datetime.now(timezone.utc).isoformat(),
                "uyari": "Adaylar kanıt değildir. İncelemeden islem değiştirmeyin. Kaynak dosya değiştirilmez.",
                "kayitlar": cases}
    finally:
        con.close()


def _validate_item(con: sqlite3.Connection, item: dict) -> tuple[int, int | None, int | None] | None:
    if not isinstance(item, dict):
        raise ReconciliationError("Plan satırı nesne olmalı.")
    action = item.get("islem")
    if action == REVIEW:
        return None
    if action not in (UNLINK, RELINK):
        raise ReconciliationError("Bilinmeyen işlem; yalnızca review/unlink/relink geçerli.")
    if not isinstance(item.get("gerekce"), str) or len(item["gerekce"].strip()) < 15:
        raise ReconciliationError("Her değişiklik için en az 15 karakter gerekçe zorunlu.")
    sid = item.get("satir_id")
    if type(sid) is not int or sid <= 0:
        raise ReconciliationError("Geçersiz satır ID.")
    row = _row(con, sid)
    if not row or row["odev_id"] is None:
        raise ReconciliationError(f"Satır {sid} bulunamadı veya artık kopuk bağlantı değil.")
    if any(item.get(key) != row[key2] for key, key2 in (("ogrenci_id", "ogrenci_id"), ("kume_id", "kume_id"), ("eski_odev_id", "odev_id"))):
        raise ReconciliationError(f"Satır {sid} öğrenci, küme veya eski bağlantı değişmiş.")
    if item.get("satir_ozeti_sha256") != _digest(row):
        raise ReconciliationError(f"Satır {sid} incelemeden sonra değişmiş; yeni inceleme oluşturun.")
    if con.execute("SELECT 1 FROM odev WHERE id=?", (row["odev_id"],)).fetchone():
        raise ReconciliationError(f"Satır {sid}: eski bağlantı artık geçerli; işlem reddedildi.")
    new_id = None
    if action == RELINK:
        new_id = item.get("yeni_odev_id")
        if type(new_id) is not int or new_id <= 0:
            raise ReconciliationError("Yeniden bağlama için açık hedef ödev ID gerekli.")
        parent = con.execute("SELECT id,ogrenci_id,kume_id,ders,kitap_ad,konu_ad FROM odev WHERE id=?", (new_id,)).fetchone()
        if not parent:
            raise ReconciliationError(f"Hedef ödev {new_id} mevcut değil.")
        parent = dict(parent)
        if parent["ogrenci_id"] != row["ogrenci_id"] or parent["kume_id"] != row["kume_id"]:
            raise ReconciliationError("Hedef ödev farklı öğrenciye veya kümeye ait.")
        if not all(_label(row)) or _label(row) != _label(parent):
            raise ReconciliationError("Hedef ödevin ders–kitap–konu eşleşmesi birebir değil.")
        if con.execute("SELECT 1 FROM odev_satir WHERE odev_id=? AND id<>? LIMIT 1", (new_id,sid)).fetchone():
            raise ReconciliationError("Hedef ödev başka satırla zaten bağlı; çoğaltma engellendi.")
    elif item.get("yeni_odev_id") is not None:
        raise ReconciliationError("Bağlantıyı boşaltma işleminde hedef ID girilmemeli.")
    return sid, row["odev_id"], new_id


def _validate_plan(con: sqlite3.Connection, plan: dict) -> list[tuple[int, int, int | None]]:
    if not isinstance(plan, dict) or plan.get("format") != "odev-link-review-v136":
        raise ReconciliationError("Geçersiz inceleme dosyası formatı.")
    items = plan.get("kayitlar")
    if not isinstance(items, list) or not items:
        raise ReconciliationError("Boş inceleme dosyası.")
    all_orphan_ids = {r[0] for r in con.execute("""SELECT s.id FROM odev_satir s LEFT JOIN odev o ON o.id=s.odev_id
                      WHERE s.odev_id IS NOT NULL AND o.id IS NULL""")}
    listed: set[int] = set()
    actions = []
    for item in items:
        sid = item.get("satir_id") if isinstance(item, dict) else None
        if type(sid) is not int or sid in listed:
            raise ReconciliationError("İnceleme dosyasında geçersiz/tekrarlı satır ID.")
        listed.add(sid)
        if sid not in all_orphan_ids:
            raise ReconciliationError("İnceleme dosyası eskimiş veya satır artık kopuk değil.")
        change = _validate_item(con, item)
        if change:
            actions.append(change)
    if listed != all_orphan_ids:
        raise ReconciliationError("İnceleme sonrası kopuk kayıt listesi değişmiş. Yeni inceleme oluşturun.")
    if not actions:
        raise ReconciliationError("Açık onaylanmış düzeltme yok; kopya üretilmeyecek.")
    targets = [new for _, _, new in actions if new is not None]
    if len(set(targets)) != len(targets):
        raise ReconciliationError("İki satır aynı hedef ödeve bağlanamaz.")
    return actions


def apply_to_new_copy(db_path: str | Path, plan: dict, output_path: str | Path, *,
                      approver: str, acknowledgement: str) -> dict:
    """Create and modify ONLY a new, previously non-existent SQLite file.

    Source is read-only, and an existing destination will never be overwritten.
    The sidecar journal is written with IDs, old/new link IDs and row hashes only.
    """
    if acknowledgement != ACKNOWLEDGEMENT or len(approver.strip()) < 3:
        raise ReconciliationError("Yönetici adı ve açık onay ifadesi zorunludur.")
    source, target = Path(db_path).resolve(), Path(output_path).resolve()
    if source == target:
        raise ReconciliationError("Kaynak dosyanın üzerine yazılamaz.")
    if target.suffix.lower() not in (".db", ".sqlite", ".sqlite3"):
        raise ReconciliationError("Çıktı bir SQLite veritabanı dosyası olmalı.")
    journal_path = target.with_name(target.name + '.uzlastirma.json')
    if target.exists() or journal_path.exists():
        raise ReconciliationError("Çıktı veya günlük dosyası zaten var; üzerine yazılmayacak.")
    if not target.parent.is_dir():
        raise ReconciliationError("Hedef klasör yok.")
    original = _read_connection(source)
    created = False
    try:
        _check_schema(original)
        # Reserve destination name exclusively; an existing output cannot be clobbered.
        fd = os.open(str(target), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        created = True
        dest = sqlite3.connect(target)
        try:
            original.backup(dest)
            dest.row_factory = sqlite3.Row
            dest.execute('BEGIN IMMEDIATE')
            changes = _validate_plan(dest, plan)  # checks the exact consistent snapshot
            prior = audit_database(dest)
            applied = []
            for sid, old_id, new_id in changes:
                cur = dest.execute('UPDATE odev_satir SET odev_id=? WHERE id=? AND odev_id=?',
                                   (new_id, sid, old_id))
                if cur.rowcount != 1:
                    raise ReconciliationError(f'Satır {sid} güvenli biçimde değiştirilemedi.')
                applied.append({'satir_id':sid,'eski_odev_id':old_id,'yeni_odev_id':new_id})
            after = audit_database(dest)
            before_codes = {x.code: x.count for x in prior.findings}
            for item in after.findings:
                if item.count > before_codes.get(item.code, 0):
                    raise ReconciliationError(f'Düzeltme yeni tutarsızlık oluşturdu: {item.code}')
            if dest.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ReconciliationError('Yeni veritabanının bütünlüğü başarısız.')
            dest.commit()
        except BaseException:
            dest.rollback()
            raise
        finally:
            dest.close()
        result = {'format':'odev-link-reconciliation-v136','created_utc':datetime.now(timezone.utc).isoformat(),
                  'approver':approver.strip(), 'source_modified':False, 'output_file':target.name,
                  'plan_sha256':_digest(plan), 'changes':applied,
                  'remaining_findings':after.as_dict(),
                  'instruction':'Orijinal dosya korunmuştur. Canlıya geçiş ancak ayrıca yedek ve uygulama testiyle yapılmalı.'}
        # Exclusive create prevents silently replacing an earlier audit journal.
        with open(journal_path,'x',encoding='utf-8') as out:
            json.dump(result,out,ensure_ascii=False,indent=2)
        return result
    except BaseException:
        if created:
            try: target.unlink(missing_ok=True)
            except OSError: pass
        raise
    finally:
        original.close()
