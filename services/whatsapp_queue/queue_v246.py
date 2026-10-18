# -*- coding: utf-8 -*-
"""V24.6 WhatsApp gönderim günlüğü ve kuyruk.

Bu modül *asla* WhatsApp'a mesaj göndermez; taşımacı sürücüsü ayrı tutulur.
Uygulama çökerse IN_FLIGHT işler UNKNOWN olur; tekrar otomatik gönderilmez.
WhatsApp'ın kişisel istemcisinden gerçek teslim onayı elde edildiğini iddia etmez.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import os
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Dict, Iterable, List, Optional

PENDING = "BEKLIYOR"
IN_FLIGHT = "DENENIYOR"
UI_UNVERIFIED = "ARAYUZ_KABUL_ETTI_TESLIM_BELIRSIZ"
UNKNOWN = "SONUC_BELIRSIZ"
INVALID = "GECERSIZ_NUMARA"
FAILED = "GONDERILMEDI"
BLOCKED = "OTURUM_GEREKLI"
TERMINAL = frozenset((UI_UNVERIFIED, UNKNOWN, INVALID, FAILED))

class QueueBusyError(RuntimeError):
    pass


def _utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_phone(raw: str, country_code: str = "90") -> Optional[str]:
    """Tek bir telefon numarasını sıkı biçimde doğrula; bilinmeyeni tahmin etme."""
    value = (raw or "").strip()
    cc = re.sub(r"\D", "", country_code or "")
    if not cc or len(cc) > 3 or not value:
        return None
    # Bir hücrede birden fazla numara varsa birleştirip yanlış kişiye gönderme.
    if any(x in value for x in ("/", ";", ",", "\n")):
        return None
    if re.search(r"[^\d+()\s.\-]", value) or value.count("+") > 1 or ("+" in value and not value.startswith("+")):
        return None
    if value.startswith("00"):
        value = "+" + value[2:]
    digits = re.sub(r"\D", "", value)
    if value.startswith("+"):
        if not digits.startswith(cc):
            # Seçili ülke kodu dışında numara için sessiz dönüştürme yok.
            return None
    elif digits.startswith("0"):
        digits = cc + digits[1:]
    elif not digits.startswith(cc):
        digits = cc + digits
    # E.164 en fazla 15 hane; TR için 90 + 10 hane, 5 ile başlayan cep numarası.
    if cc == "90":
        if len(digits) != 12 or not digits.startswith("905"):
            return None
    elif not (8 <= len(digits) <= 15):
        return None
    return digits


def queue_path_for(db_path: str, appdata_dir: str) -> str:
    """Ayrı test/proje DB'lerinin gönderimlerini aynı kuyruğa karıştırma."""
    real = os.path.normcase(os.path.realpath(db_path))
    digest = hashlib.sha256(real.encode("utf-8")).hexdigest()[:16]
    return os.path.join(appdata_dir, f"wa_kuyruk_{digest}.sqlite3")


class SafeWhatsAppQueue:
    def __init__(self, path: str):
        self.path = str(Path(path).expanduser())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._init()
        if os.name != "nt":
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.path, timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout = 15000")
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def _init(self):
        with self.connect() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS batches (
                id TEXT PRIMARY KEY, created TEXT NOT NULL, updated TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ACTIVE', source_db TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES batches(id),
                student_id INTEGER, recipient TEXT NOT NULL, message TEXT NOT NULL,
                state TEXT NOT NULL, attempt_token TEXT, created TEXT NOT NULL,
                updated TEXT NOT NULL, detail TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS wa_jobs_state ON jobs(batch_id, state);
            """)

    def acquire_lock(self):
        """Tek bilgisayarda aynı kullanıcı/proje için iki gönderici çalışmasın.

        Bayat kilit ancak sahibi işlem artık çalışmıyorsa temizlenir.
        """
        lock_path = self.path + ".worker.lock"
        for attempt in range(2):
            try:
                fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                os.write(fd, str(os.getpid()).encode("ascii"))
                return fd
            except FileExistsError:
                if attempt:
                    raise QueueBusyError("Başka bir WhatsApp gönderici hâlâ çalışıyor")
                try:
                    with open(lock_path, "rt", encoding="ascii") as f:
                        pid = int(f.read().strip())
                    if pid == os.getpid():
                        raise QueueBusyError("Başka bir WhatsApp gönderici hâlâ çalışıyor")
                    try:
                        os.kill(pid, 0)
                    except ProcessLookupError:
                        os.unlink(lock_path)
                    except PermissionError:
                        raise QueueBusyError("Gönderim kilidinin sahibi doğrulanamıyor")
                    except OSError:
                        # Windows'ta pid yoksa os.kill(pid, 0) OSError da verebilir.
                        os.unlink(lock_path)
                    else:
                        raise QueueBusyError("Başka bir WhatsApp gönderici hâlâ çalışıyor")
                except (ValueError, FileNotFoundError):
                    raise QueueBusyError("Gönderim kilidi okunamıyor; otomatik silinmedi")
        raise QueueBusyError("Gönderim kilidi alınamadı")

    def release_lock(self, fd):
        try:
            os.close(fd)
        finally:
            try:
                os.unlink(self.path + ".worker.lock")
            except FileNotFoundError:
                pass

    def create_batch(self, db_path: str, jobs: Iterable[dict]) -> str:
        items = list(jobs)
        if not items:
            raise ValueError("Kuyrukta alıcı yok")
        batch = uuid.uuid4().hex
        now = _utc()
        # Bütün mesaj metinleri gönderimden ÖNCE tek işlemde kaydedilir.
        with self.connect() as c:
            c.execute("INSERT INTO batches VALUES(?,?,?,?,?)", (batch, now, now, "ACTIVE", os.path.realpath(db_path)))
            seen = set()
            for entry in items:
                student_id = entry.get("student_id")
                raw = str(entry.get("recipient", ""))
                msg = str(entry.get("message", ""))
                phone = normalize_phone(raw, str(entry.get("country_code", "90")))
                fingerprint = (student_id, phone or raw, msg)
                if fingerprint in seen:
                    continue
                seen.add(fingerprint)
                state = PENDING if phone and msg.strip() else INVALID if not phone else FAILED
                detail = "" if state == PENDING else "Numara biçimi geçersiz" if state == INVALID else "Mesaj boş"
                c.execute("""INSERT INTO jobs
                    (id,batch_id,student_id,recipient,message,state,attempt_token,created,updated,detail)
                    VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (uuid.uuid4().hex, batch, student_id, phone or raw, msg, state, None, now, now, detail))
        return batch

    def recover_interrupted(self, batch: str) -> int:
        """Önceki çalışmadan kalan DENENIYOR satırları kesinlikle otomatik tekrarlanmaz."""
        with self.connect() as c:
            q = c.execute("""UPDATE jobs SET state=?,detail=?,updated=?
                              WHERE batch_id=? AND state=?""",
                          (UNKNOWN, "Program kapandı; gönderim durumu doğrulanamıyor", _utc(), batch, IN_FLIGHT))
            return q.rowcount

    def claim_next(self, batch: str):
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            # Bu batch üzerinde başka gönderim iş parçacığı varsa ikinci gönderici başlatma.
            if c.execute("SELECT 1 FROM jobs WHERE batch_id=? AND state=? LIMIT 1", (batch, IN_FLIGHT)).fetchone():
                raise QueueBusyError("Aynı kuyruk başka bir işlem tarafından kullanılıyor")
            row = c.execute("SELECT * FROM jobs WHERE batch_id=? AND state=? ORDER BY rowid LIMIT 1",
                            (batch, PENDING)).fetchone()
            if row is None:
                return None
            token = uuid.uuid4().hex
            c.execute("""UPDATE jobs SET state=?,attempt_token=?,updated=? WHERE id=? AND state=?""",
                      (IN_FLIGHT, token, _utc(), row["id"], PENDING))
            return {**dict(row), "attempt_token": token}

    def finish(self, job_id: str, token: str, result: str, detail: str = ""):
        if result not in (UI_UNVERIFIED, UNKNOWN, INVALID, FAILED):
            raise ValueError("Tanımsız gönderim sonucu")
        with self.connect() as c:
            q = c.execute("""UPDATE jobs SET state=?, detail=?, updated=?
                             WHERE id=? AND state=? AND attempt_token=?""",
                          (result, (detail or "")[:300], _utc(), job_id, IN_FLIGHT, token))
            if q.rowcount != 1:
                raise QueueBusyError("Gönderim işi eş zamanlı değişti")

    def latest_batch(self, db_path: str) -> Optional[str]:
        """Tamamlanmış işler de dâhil son parti; öğretmenin sonuç görmesi için."""
        with self.connect() as c:
            row = c.execute("SELECT id FROM batches WHERE source_db=? ORDER BY rowid DESC LIMIT 1",
                            (os.path.realpath(db_path),)).fetchone()
            return row[0] if row else None

    def current_batch(self, db_path: str) -> Optional[str]:
        with self.connect() as c:
            row = c.execute("""SELECT b.id FROM batches b
                WHERE b.source_db=? AND EXISTS (
                    SELECT 1 FROM jobs j WHERE j.batch_id=b.id AND j.state IN (?,?))
                ORDER BY b.rowid DESC LIMIT 1""", (os.path.realpath(db_path), PENDING, IN_FLIGHT)).fetchone()
            return row[0] if row else None

    def counts(self, batch: str) -> Dict[str, int]:
        with self.connect() as c:
            result = {str(r[0]): int(r[1]) for r in c.execute(
                "SELECT state, COUNT(*) FROM jobs WHERE batch_id=? GROUP BY state", (batch,))}
        return result

    def rows(self, batch: str) -> List[dict]:
        with self.connect() as c:
            return [dict(r) for r in c.execute("SELECT * FROM jobs WHERE batch_id=? ORDER BY rowid", (batch,))]
