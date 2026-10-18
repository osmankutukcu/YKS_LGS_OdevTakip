"""Optional Student 360 / adaptive coaching read-only V3 connector.

Builds a compact view from the EXISTING V27 presenter, not a second scoring
algorithm. SQLiteChangeMonitor watches local SQLite commits only. It is not a
network client or a guarantee of remote/cloud synchronization.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class CoachGlance:
    student_id: int
    status: str
    evidence_count: int
    priority: str
    next_step: str
    basis: str
    warning: str
    as_of: str


def read_coach_glance(con: sqlite3.Connection, student_id: int, *, provider=None) -> CoachGlance:
    """Reuse V27's existing advisor; no INSERT/UPDATE/DELETE or schema changes."""
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('Öğrenci kimliği geçersiz.')
    if provider is None:
        from services.adaptive_coaching_v27.presenter import sidebar_data
        provider = sidebar_data
    original_factory = con.row_factory
    try:
        con.row_factory = sqlite3.Row  # V27 expects name-based columns.
        model = provider(con, student_id)
    finally:
        con.row_factory = original_factory
    if type(model) is not dict or int(model.get('student_id') or 0) != student_id:
        raise ValueError('Koçluk verisi farklı öğrenciye ait veya geçersiz.')
    actions = model.get('actions') or []
    first = actions[0] if actions else None
    evidence_count = max(0, int(model.get('evidence_count') or 0))
    priority = str(first.get('title') or '') if isinstance(first, dict) else ''
    step = str(first.get('next_step') or '') if isinstance(first, dict) else ''
    basis = str(first.get('source') or '') if isinstance(first, dict) else ''
    if not priority:
        priority = 'Önce bağımsız kazanım ölçümü yapın' if not evidence_count else 'Mevcut ölçümleri öğretmenle değerlendirin'
    if not step:
        step = str(model.get('guidance') or 'Kısa bir tanılama yapın.')
    warnings = model.get('warnings') or []
    warning = str(warnings[0]) if warnings else ''
    return CoachGlance(
        student_id, str(model.get('status') or 'Henüz değerlendirilmedi')[:160],
        evidence_count, priority[:180], step[:260], basis[:120],
        warning[:180], str(model.get('as_of') or '')[:30]
    )


class SQLiteChangeMonitor:
    """Poll a *persistent* read-only connection: PRAGMA data_version is scoped
    to its connection. Also notice DB-file replacement and WAL checkpoints.

    This is explicitly a LOCAL commit detector; remote data only appears if an
    existing sync service has actually committed it to this SQLite database.
    """
    def __init__(self, db_path: str | Path):
        self.path = Path(db_path).expanduser().resolve()
        self._conn = None
        self._version = None
        self._fingerprint = None
        self._file_identity = None

    def _files(self):
        def state(path):
            try:
                stat = path.stat()
                return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
            except FileNotFoundError:
                return None
        return (state(self.path), state(Path(str(self.path) + '-wal')))

    def _connect(self):
        uri = self.path.as_uri() + '?mode=ro'  # portable on macOS/Windows
        self._conn = sqlite3.connect(uri, uri=True, timeout=1)
        self._conn.execute('PRAGMA query_only=ON')
        self._version = int(self._conn.execute('PRAGMA data_version').fetchone()[0])

    def poll(self) -> bool:
        """Return True if local DB changed since the preceding successful poll."""
        fingerprint = self._files()
        if fingerprint[0] is None:
            self.close()
            return False
        identity = fingerprint[0][:2]
        if self._conn is None or identity != self._file_identity:
            had_baseline = self._file_identity is not None
            self.close()
            self._connect()
            self._file_identity = identity
            self._fingerprint = fingerprint
            return had_baseline
        try:
            version = int(self._conn.execute('PRAGMA data_version').fetchone()[0])
        except sqlite3.Error:
            self.close()
            raise
        changed = version != self._version or fingerprint != self._fingerprint
        self._version, self._fingerprint = version, fingerprint
        return changed

    def close(self):
        if self._conn is not None:
            self._conn.close()
        self._conn = None
        self._version = None
        self._fingerprint = None
        # Keep file identity to flag a replaced DB when poll resumes.
