"""V13.5: read-only homework integrity checks.

No table is modified and no guessed repairs are attempted.  `odev` and
`odev_satir` are separate legacy representations, not presumed equal.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable
import sqlite3
import unicodedata


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    message: str
    count: int = 1
    references: tuple[str, ...] = ()
    guidance: str = ""


@dataclass
class AuditResult:
    findings: list[Finding] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def add(self, code: str, severity: str, message: str, count: int = 1,
            references: Iterable[Any] = (), guidance: str = "") -> None:
        if count:
            self.findings.append(Finding(code, severity, message, count,
                                         tuple(str(x) for x in references), guidance))

    def as_dict(self) -> dict:
        return {"findings": [dict(code=f.code, severity=f.severity,
                 message=f.message, count=f.count, references=list(f.references),
                 guidance=f.guidance) for f in self.findings],
                "notes": list(self.notes)}


def _tables(con: sqlite3.Connection) -> set[str]:
    return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _cols(con: sqlite3.Connection, table: str) -> set[str]:
    # Only use approved project table names, never identifiers from outside input.
    if table not in {"ogrenci", "odev", "odev_satir", "odev_kume"}:
        return set()
    return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}


def _count_refs(con: sqlite3.Connection, query: str, params: tuple = (),
                sample_query: str | None = None, sample_params: tuple = (), limit: int = 5):
    number = int(con.execute(query, params).fetchone()[0])
    samples: list[str] = []
    if number and sample_query:
        samples = [str(row[0]) for row in con.execute(sample_query + " LIMIT ?", (*sample_params, limit))]
    return number, samples


def audit_database(con: sqlite3.Connection, *, sample_limit: int = 5) -> AuditResult:
    """Use SELECT and PRAGMA-only statements on an existing connection.

    No commit, BEGIN, schema migration, or foreign-key enforcement change.
    The caller is responsible for opening the connection read-only.
    """
    result = AuditResult()
    existing = _tables(con)
    required = {"ogrenci", "odev", "odev_satir", "odev_kume"}
    if missing := sorted(required - existing):
        result.add("MISSING_TABLE", "critical", "Ödev denetimi için gereken tablo eksik: " + ", ".join(missing),
                   guidance="Veritabanı sürümünü ve geri yükleme kaynağını doğrulayın.")
        return result
    cols = {t: _cols(con, t) for t in required}
    for t, expected in {
        "ogrenci": {"id"}, "odev_kume": {"id", "ogrenci_id"},
        "odev": {"id", "ogrenci_id", "kume_id"},
        "odev_satir": {"id", "ogrenci_id", "kume_id"},
    }.items():
        if not expected <= cols[t]:
            result.add("MISSING_COLUMN", "critical", f"{t} tablosunda alan eksik: {', '.join(sorted(expected - cols[t]))}")
    if any(f.code == "MISSING_COLUMN" for f in result.findings):
        return result

    limit = max(0, min(int(sample_limit), 25))
    # FK constraints are not complete in legacy databases; explicit checks below
    # cover both declared and non-declared relations, including odev_satir.odev_id.
    for source, label in (("odev_kume", "Küme"), ("odev", "Ödev"), ("odev_satir", "Ödev satırı")):
        sql = f"FROM {source} t LEFT JOIN ogrenci s ON s.id=t.ogrenci_id WHERE t.ogrenci_id IS NOT NULL AND s.id IS NULL"
        count, samples = _count_refs(con, "SELECT COUNT(*) " + sql,
                                    sample_query="SELECT t.id " + sql + " ORDER BY t.id", limit=limit)
        result.add("MISSING_STUDENT_" + source.upper(), "critical", f"{label}: bulunamayan öğrenci bağlantısı", count, samples,
                   "Öğrenci kimliklerini kaynak yedekle karşılaştırın; otomatik öğrenci atamayın.")

    for source in ("odev", "odev_satir"):
        join = (f"FROM {source} t LEFT JOIN odev_kume k ON k.id=t.kume_id "
                "WHERE t.kume_id IS NOT NULL AND k.id IS NULL")
        count, samples = _count_refs(con, "SELECT COUNT(*) " + join,
                                    sample_query="SELECT t.id " + join + " ORDER BY t.id", limit=limit)
        result.add("MISSING_GROUP_" + source.upper(), "critical", f"{source}: bulunamayan ödev kümesi", count, samples,
                   "Kayıt zincirini inceleyin; ödevleri veya kümeleri otomatik silmeyin.")
        join = (f"FROM {source} t JOIN odev_kume k ON k.id=t.kume_id "
                "WHERE t.ogrenci_id IS NOT NULL AND k.ogrenci_id IS NOT NULL AND t.ogrenci_id <> k.ogrenci_id")
        count, samples = _count_refs(con, "SELECT COUNT(*) " + join,
                                    sample_query="SELECT t.id " + join + " ORDER BY t.id", limit=limit)
        result.add("STUDENT_GROUP_MISMATCH_" + source.upper(), "critical",
                   f"{source}: ödev satırı ve bağlı küme farklı öğrencilere ait", count, samples,
                   "Kayıtları açmadan önce aidiyeti doğrulayın; otomatik taşıma yapmayın.")

    if "odev_id" in cols["odev_satir"]:
        join = ("FROM odev_satir s LEFT JOIN odev o ON o.id=s.odev_id "
                "WHERE s.odev_id IS NOT NULL AND o.id IS NULL")
        count, samples = _count_refs(con, "SELECT COUNT(*) " + join,
                                    sample_query="SELECT s.id " + join + " ORDER BY s.id", limit=limit)
        result.add("MISSING_LINKED_HOMEWORK", "high", "odev_satir.odev_id karşılığı olmayan bağlantı", count, samples,
                   "Bağlantıları yedekten tek tek karşılaştırın; odev_id'yi tahmin ederek doldurmayın.")
        join = ("FROM odev_satir s JOIN odev o ON o.id=s.odev_id "
                "WHERE s.ogrenci_id IS NOT NULL AND o.ogrenci_id IS NOT NULL AND s.ogrenci_id <> o.ogrenci_id")
        count, samples = _count_refs(con, "SELECT COUNT(*) " + join,
                                    sample_query="SELECT s.id " + join + " ORDER BY s.id", limit=limit)
        result.add("LINKED_HOMEWORK_STUDENT_MISMATCH", "critical", "Bağlı ödev farklı öğrenciye ait", count, samples,
                   "Ödev bağlantısı ve öğrenci sahipliği ayrı ayrı doğrulanmalıdır.")
    else:
        result.notes.append("odev_satir.odev_id kolonu bulunmuyor; tablo-arası bağlantı denetlenemedi.")

    # A row with no linked odev_id is normal for some legacy flows: do NOT flag.
    # Different row counts, task texts and statuses can be legitimate across legacy views.
    result.notes.append("odev ve odev_satir satır sayılarının farklı olması tek başına bozuk kayıt anlamına gelmez.")
    result.notes.append("Bu denetim mevcut veriye müdahale etmez; eski kayıtların düzeltmesi için manuel doğrulama gerekir.")
    return result


def _canon(s: Any) -> str:
    """Normalization for draft comparison; Turkish I kept consistent with app."""
    raw = unicodedata.normalize("NFKC", str(s or "")).strip().replace("İ", "i").replace("I", "ı")
    return " ".join(raw.casefold().split())


def _key(ders: Any, kitap: Any, konu: Any) -> tuple[str, str, str]:
    return _canon(ders), _canon(kitap), _canon(konu)


def audit_draft_matrix(cells: Iterable[dict], task_rows: Iterable[dict], *,
                       selected_student: Any, loaded_student: Any) -> AuditResult:
    """Compare only currently editable draft checks against visible right-hand rows.

    The locked/saved matrix rows are excluded; these are not expected to match
    transient right-hand rows and MUST NOT be automatically unchecked.
    """
    result = AuditResult()
    try:
        selected, loaded = int(selected_student), int(loaded_student)
    except (ValueError, TypeError):
        selected = loaded = 0
    if not selected or selected <= 0 or selected != loaded:
        result.add("STUDENT_CONTEXT_MISMATCH", "critical", "Seçili öğrenci ile yüklenmiş ders matrisi uyuşmuyor.",
                   guidance="Öğrenciyi tekrar seçip Bilgileri Getir işlemini uygulayın.")
        return result
    unique: dict[tuple, list[dict]] = defaultdict(list)
    locked_keys: set[tuple] = set()
    for cell in cells:
        key = _key(cell.get('ders'), cell.get('kitap'), cell.get('konu'))
        if not all(key):
            continue
        if cell.get('locked', False):
            locked_keys.add(key)
        else:
            unique[key].append(cell)
    tasks = Counter()
    for row in task_rows:
        key = _key(row.get('ders'), row.get('kitap'), row.get('konu'))
        if all(key):
            tasks[key] += 1
    ambiguous = {key for key, matched in unique.items() if len(matched) > 1}
    result.add("AMBIGUOUS_MATRIX_KEY", "high", "Birden fazla düzenlenebilir hücre aynı ders–kitap–konuya ait.", len(ambiguous),
               (" / ".join(k) for k in sorted(ambiguous)[:5]), "Hangi hücrenin doğru olduğunu manuel kontrol edin.")
    duplicates = {key for key, count in tasks.items() if count > 1}
    result.add("DUPLICATE_DRAFT_ROWS", "medium", "Sağdaki taslak listesinde aynı ders–kitap–konu yineleniyor.",
               sum(tasks[k] - 1 for k in duplicates), (" / ".join(k) for k in sorted(duplicates)[:5]),
               "Taslak satırlarını kontrol edin; otomatik toplu silme yapmayın.")
    missing_right = [k for k, matched in unique.items()
                     if k not in ambiguous and matched[0].get('checked', False) and not tasks[k]]
    result.add("CHECKED_WITHOUT_DRAFT", "medium", "Solda düzenlenebilir tik var, sağdaki taslakta ödev yok.",
               len(missing_right), (" / ".join(k) for k in sorted(missing_right)[:5]),
               "Kaydetmeden önce işaretli hücreyi ve sağdaki listeyi karşılaştırın.")
    missing_left = [k for k in tasks if k not in locked_keys and k not in ambiguous and
                    (k not in unique or not unique[k][0].get('checked', False))]
    result.add("DRAFT_WITHOUT_CHECK", "medium", "Sağda taslak ödev var, solda eşleşen düzenlenebilir tik yok.",
               len(missing_left), (" / ".join(k) for k in sorted(missing_left)[:5]),
               "Öğrencinin kitap/konu eşleşmesini kontrol edin; belirsiz hücreyi otomatik tiklemeyin.")
    result.notes.append("Kayıtlı ve kilitli hücreler taslak eşleşme hesabından hariç tutulur.")
    return result
