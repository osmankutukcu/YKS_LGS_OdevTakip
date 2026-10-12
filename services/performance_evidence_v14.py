"""Read-only, explainable assignment-follow-up metrics for the Performance Panel.

Not an academic attainment estimator. A homework's completion state is not an
exam score or evidence of mastery. Never writes to SQLite or guesses missing data.
V13 legacy storage: a group may appear in both `odev` and `odev_satir`.
For such groups, the primary `odev` representation is counted once; a warning
is surfaced for the unverified shadow rows. This is a conservative policy,
not a reconciliation or a claim that both sources contain identical work.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from collections import defaultdict
import sqlite3

DONE = frozenset(('tamam', 'tamamlandi', 'tamamlandı', 'yapildi', 'yapıldı', 'bitti', 'ok', 'done'))
OPEN = frozenset(('devam', 'bekliyor', 'beklemede', 'acik', 'açık', 'eksik', 'todo', 'kısmi', 'kismi', 'yarim', 'yarım', 'kaldı'))
TRANSFERRED = frozenset(('aktarildi', 'aktarıldı', 'iptal', 'iptal edildi', 'silindi'))
MIN_RECOGNITION_SAMPLE = 5


def _table_exists(con: sqlite3.Connection, table: str) -> bool:
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def _cols(con: sqlite3.Connection, table: str) -> set[str]:
    return {str(x[1]) for x in con.execute(f'PRAGMA table_info({table})')}


def _records(con: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    cursor = con.execute(sql, params)
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _date(value) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    raw = str(value).strip()
    try:
        return date.fromisoformat(raw[:10])
    except (ValueError, TypeError):
        pass
    for fmt in ('%d.%m.%Y', '%Y/%m/%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(raw.split()[0], fmt).date()
        except ValueError:
            continue
    return None


def _norm_status(value) -> str:
    return str(value or 'devam').strip().lower()


@dataclass(frozen=True)
class Period:
    completed: int = 0
    total: int = 0
    open_count: int = 0
    overdue: int = 0

    @property
    def percent(self) -> float | None:
        return round(100.0 * self.completed / self.total, 1) if self.total else None


@dataclass(frozen=True)
class StudentEvidence:
    student_id: int
    name: str
    week: Period
    last30: Period
    previous30: Period
    groups_week: int
    overdue_all: int
    uncertain_count: int
    undated_count: int
    excluded_rows: int
    def summary(self) -> str:
        if self.week.total == 0 and self.last30.total == 0:
            return 'Bu dönemde teslim tarihli ödev verisi yok'
        if self.uncertain_count:
            return 'Kaynak kayıtları kontrol edilmeli'
        if self.overdue_all:
            return f'{self.overdue_all} gecikmiş açık ödev: kontrol/telafi için inceleyin'
        if self.week.total and self.week.total < MIN_RECOGNITION_SAMPLE:
            return 'Haftalık örneklem küçük; oranı temkinli yorumlayın'
        if self.week.total >= MIN_RECOGNITION_SAMPLE and (self.week.percent or 0) < 60:
            return 'Tamamlama oranı düşük: nedenini öğrenciyle kontrol edin'
        return 'Ödev takibi mevcut; akademik başarı ayrı ölçülür'


@dataclass(frozen=True)
class EvidenceResult:
    students: tuple[StudentEvidence, ...]
    week_start: date
    week_end: date
    last30_start: date
    last30_end: date
    notes: tuple[str, ...]
    skipped: int

    def top5(self) -> list[dict]:
        eligible = [r for r in self.students if r.week.total >= MIN_RECOGNITION_SAMPLE and not r.uncertain_count]
        eligible.sort(key=lambda r: (-(r.week.percent or 0), -r.week.completed, r.name))
        return [dict(ogrenci_id=r.student_id, ad=r.name, soyad='', gorev_bitti=r.week.completed,
                     gorev_toplam=r.week.total, kume_sayisi=r.groups_week,
                     ilerleme_yuzde=r.week.percent) for r in eligible[:5]]

    def club(self) -> list[dict]:
        eligible = [r for r in self.students if not r.uncertain_count and (
            (r.week.total >= MIN_RECOGNITION_SAMPLE and (r.week.percent or 0) >= 80)
            or (r.last30.total >= MIN_RECOGNITION_SAMPLE and (r.last30.percent or 0) >= 80))]
        def _score(r: StudentEvidence) -> float:
            week_score = (r.week.percent or 0) if r.week.total >= MIN_RECOGNITION_SAMPLE else 0
            month_score = (r.last30.percent or 0) if r.last30.total >= MIN_RECOGNITION_SAMPLE else 0
            return max(week_score, month_score)
        eligible.sort(key=lambda r: (-_score(r), r.name))
        return [dict(ogrenci_id=r.student_id, ad=r.name, soyad='',
                     hafta_pct=r.week.percent or 0, ay_pct=r.last30.percent or 0,
                     w_pct=r.week.percent or 0,
                     hafta_bitti=r.week.completed, hafta_toplam=r.week.total,
                     ay_bitti=r.last30.completed, ay_toplam=r.last30.total) for r in eligible[:50]]

    def trend(self) -> list[dict]:
        """Open items by non-overlapping *due-date cohorts*, not historic changes."""
        eligible = [r for r in self.students if r.last30.overdue > r.previous30.overdue]
        eligible.sort(key=lambda r: (-(r.last30.overdue-r.previous30.overdue), -r.last30.overdue, r.name))
        return [dict(ogrenci_id=r.student_id, ad=r.name, soyad='',
                     son30=r.last30.overdue, onceki30=r.previous30.overdue,
                     fark=r.last30.overdue-r.previous30.overdue) for r in eligible[:20]]


def compute_evidence(con: sqlite3.Connection, reference_day: date | None = None) -> EvidenceResult:
    """Read-only SELECTs, no schema creation, writes, jobs, or network activity."""
    today = reference_day or date.today()
    ws = today - timedelta(days=today.weekday())
    we = ws + timedelta(days=6)
    # Future deadlines in an unfinished week are not yet included in completion %.
    effective_we = min(we, date.today())
    last30_start = today - timedelta(days=29)
    prev_start = today - timedelta(days=59)
    prev_end = last30_start - timedelta(days=1)
    required = ('ogrenci', 'odev_kume', 'odev', 'odev_satir')
    missing = [t for t in required if not _table_exists(con, t)]
    if missing:
        raise ValueError('Performans hesabında gereken tablo yok: ' + ', '.join(missing))

    students = _records(con, 'SELECT id, ad, soyad, aktif FROM ogrenci')
    selected = {int(r['id']): r for r in students if (r.get('aktif') is None or int(r['aktif']) == 1)}
    groups = {int(r['id']):r for r in _records(con, 'SELECT id, ogrenci_id, bitis_tarihi FROM odev_kume')}
    entries: dict[int, list[tuple[date,str,int]]] = defaultdict(list)
    mixed: dict[int,int] = defaultdict(int)
    undated: dict[int,int] = defaultdict(int)
    excluded: dict[int,int] = defaultdict(int)
    skipped = 0
    by_group: dict[int,list[tuple[str, dict]]] = defaultdict(list)

    for table in ('odev', 'odev_satir'):
        cols = _cols(con, table)
        needed = {'id', 'kume_id', 'ogrenci_id', 'durum'}
        if not needed.issubset(cols):
            raise ValueError(table + ': eksik alan: ' + ', '.join(sorted(needed - cols)))
        optional = [c for c in ('silindi', 'aktarildi', 'odev_id') if c in cols]
        raw = _records(con, 'SELECT id, kume_id, ogrenci_id, durum' +
                       ''.join(', ' + col for col in optional) + ' FROM ' + table)
        for r in raw:
            try:
                sid, gid = int(r['ogrenci_id']), int(r['kume_id'])
            except (TypeError, ValueError):
                skipped += 1
                continue
            group = groups.get(gid)
            if sid not in selected or not group or group['ogrenci_id'] is None or int(group['ogrenci_id']) != sid:
                skipped += 1
                continue
            if r.get('silindi') or r.get('aktarildi') or _norm_status(r['durum']) in TRANSFERRED:
                excluded[sid] += 1
                continue
            by_group[gid].append((table, r))

    for gid, rows in by_group.items():
        group = groups[gid]
        sid = int(group['ogrenci_id'])
        core = [row for table,row in rows if table == 'odev']
        secondary = [row for table,row in rows if table == 'odev_satir']
        if core and secondary:
            # Never sum both representations. Flag the unverified shadow records.
            mixed[sid] += len(secondary)
        chosen = core if core else secondary
        due = _date(group['bitis_tarihi'])
        for row in chosen:
            status = _norm_status(row.get('durum'))
            if status not in DONE and status not in OPEN:
                mixed[sid] += 1
                continue
            if due is None:
                undated[sid] += 1
                continue
            entries[sid].append((due, 'done' if status in DONE else 'open', gid))

    def period(items: list[tuple[date,str,int]], start:date, end:date) -> Period:
        selected_rows = [(d,st) for d,st,_ in items if start <= d <= end]
        completed = sum(st == 'done' for _,st in selected_rows)
        opened = len(selected_rows) - completed
        overdue = sum(st == 'open' and d < today for d,st in selected_rows)
        return Period(completed, len(selected_rows), opened, overdue)

    data = []
    for sid,s in selected.items():
        rows = entries.get(sid, [])
        w = period(rows,ws,effective_we)
        month = period(rows,last30_start,today)
        prev = period(rows,prev_start,prev_end)
        weeks = len({gid for due,st,gid in rows if ws <= due <= effective_we})
        name = ' '.join(str(s.get(k) or '').strip() for k in ('ad', 'soyad')).strip() or f'Öğrenci #{sid}'
        all_overdue = sum(st == 'open' and due < today for due,st,_ in rows)
        data.append(StudentEvidence(sid,name,w,month,prev,weeks,all_overdue,
                                    mixed[sid],undated[sid],excluded[sid]))
    data.sort(key=lambda x: (x.name.casefold(),x.student_id))
    notes = (
        'Yüzdeler akademik başarı/net değil; teslim tarihi gelen ödevlerin güncel tamamlama durumudur.',
        'Geçmiş dönem değerleri geçmişteki durum fotoğrafı değildir; bugünkü kayıt durumuna göre hesaplanır.',
        'Her ödev kümesinde birincil kayıt kullanılır; iki kaynak aynı kümedeyse ikinci kaynak ayrıca sayılmaz.',
        'Liderlik ve kulüp için en az 5 tarihli ödev ve kaynak tutarlılığı gerekir.',
        'İptal, aktarım, silinmiş ve tarihsiz kayıtlar başarı paydasına alınmaz.',
    )
    return EvidenceResult(tuple(data),ws,effective_we,last30_start,today,notes,skipped)
