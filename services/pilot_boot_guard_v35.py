# -*- coding: utf-8 -*-
"""Fail-closed verification for disposable Windows pilots only.

Production startup is unchanged when YKS_PILOT_ISOLATED is not set to '1'.
The READY marker proves that *this* app process opened *this* guarded dummy
SQLite database and completed initialisation; mere process survival is not proof.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3


def pilot_instance_key(base: str, env=None) -> str:
    env = os.environ if env is None else env
    if env.get('YKS_PILOT_ISOLATED') != '1':
        return base
    raw = env.get('YKS_DB_PATH', '').strip()
    if not raw or not Path(raw).is_absolute():
        raise ValueError('Pilot kilidi için mutlak YKS_DB_PATH zorunlu.')
    # Do not expose student names, machine paths or student data in the lock.
    normalized = os.path.normcase(os.path.abspath(raw))
    fingerprint = hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:20]
    return f'{base}_PILOT_{fingerprint}'


def verify_pilot_database(db_path: Path, env=None) -> None:
    env = os.environ if env is None else env
    if env.get('YKS_PILOT_ISOLATED') != '1':
        return
    raw = env.get('YKS_DB_PATH', '').strip()
    if not raw or not Path(raw).is_absolute():
        raise ValueError('Pilot için mutlak sahte veritabanı yolu zorunlu.')
    expected = Path(raw).resolve(strict=True)
    actual = Path(db_path).resolve(strict=True)
    if expected != actual or not expected.is_file():
        raise ValueError('Pilot yanlış veritabanına yöneliyor; başlatma engellendi.')
    with sqlite3.connect(expected.as_uri() + '?mode=ro', uri=True) as con:
        row = con.execute('SELECT test_only FROM v35_disposable_pilot_guard').fetchone()
    if row != (1,):
        raise ValueError('Sahte veritabanı koruma işareti yok; başlatma engellendi.')


def write_pilot_ready(db_path: Path, env=None) -> None:
    env = os.environ if env is None else env
    if env.get('YKS_PILOT_ISOLATED') != '1':
        return
    verify_pilot_database(db_path, env)
    raw = env.get('YKS_PILOT_READY_PATH', '').strip()
    nonce = env.get('YKS_PILOT_NONCE', '')
    if not raw or len(nonce) < 24:
        raise ValueError('Pilot el sıkışma belirteci eksik; başlatma engellendi.')
    dest = Path(raw)
    if not dest.is_absolute() or dest.resolve().parent != Path(db_path).resolve().parent:
        raise ValueError('Pilot doğrulama dosyası sahte DB klasöründe olmalı.')
    # Exclusive creation: never overwrite any previous evidence.
    with dest.open('x', encoding='utf-8') as out:
        json.dump({'status': 'READY', 'nonce': nonce, 'db_guard': 'PASS'}, out)


def ready_matches(path: Path, nonce: str) -> bool:
    try:
        evidence = json.loads(Path(path).read_text(encoding='utf-8'))
        return bool(nonce) and evidence == {
            'status': 'READY', 'nonce': nonce, 'db_guard': 'PASS'}
    except (OSError, ValueError, TypeError):
        return False
