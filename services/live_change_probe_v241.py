"""Read-only cross-connection SQLite commit detector for local GUI refreshes.

Persistent monitoring connection is REQUIRED: PRAGMA data_version compares
observations on that same connection; never assume a numeric global revision.
This module neither discovers student identity nor writes to any table.
"""
from __future__ import annotations
import os
import sqlite3
from pathlib import Path

class DatabaseChangeProbe:
    def __init__(self, path):
        self.path = Path(path).expanduser().resolve()
        self._connection = None
        self._observed = None
        self._fingerprint = None
        self._has_baseline = False
        self.last_error = None

    @property
    def connected(self):
        return self._connection is not None

    def close(self):
        con, self._connection = self._connection, None
        if con is not None:
            try:con.close()
            except sqlite3.Error:pass

    def poll(self):
        """True for a newly observed committed change, False otherwise.

        When the database is temporarily unavailable, return False and retry
        later. On reconnection report one invalidation if previously observed.
        Never report uncommitted/rolled-back changes.
        """
        try:
            st = self.path.stat()
            fingerprint = (st.st_dev, st.st_ino)
            if self._connection is not None and fingerprint != self._fingerprint:
                self.close()
            if self._connection is None:
                uri = self.path.as_uri() + '?mode=ro'
                try:
                    con = sqlite3.connect(uri, uri=True, timeout=0.2)
                    con.execute('PRAGMA query_only=ON')
                    revision = int(con.execute('PRAGMA data_version').fetchone()[0])
                except sqlite3.OperationalError:
                    con = sqlite3.connect(str(self.path), timeout=0.2)
                    con.execute('PRAGMA query_only=ON')
                    revision = int(con.execute('PRAGMA data_version').fetchone()[0])
                was_seen = self._has_baseline
                self._connection = con
                self._observed = revision
                self._fingerprint = fingerprint
                self._has_baseline = True
                self.last_error = None
                return was_seen
            revision = int(self._connection.execute('PRAGMA data_version').fetchone()[0])
            changed = revision != self._observed
            self._observed = revision
            self.last_error = None
            return changed
        except (OSError, sqlite3.Error, ValueError) as exc:
            self.last_error = str(exc)
            self.close()
            return False

    def __enter__(self):return self
    def __exit__(self, *_):self.close()
