"""V13.2 password hashing and first-run bootstrap. No PyQt dependency."""
from __future__ import annotations
import hashlib
import hmac
import re
import secrets

PREFIX = "pbkdf2_sha256"
ITERATIONS = 260_000


def hash_password(password: str, *, salt: bytes | None = None, iterations: int = ITERATIONS) -> str:
    if not isinstance(password, str) or not password:
        raise ValueError("Parola boş olamaz")
    if iterations < 200_000:
        raise ValueError("PBKDF2 iterasyon sayısı yetersiz")
    salt = secrets.token_bytes(16) if salt is None else salt
    if len(salt) < 16:
        raise ValueError("Salt çok kısa")
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
    return f'{PREFIX}${iterations}${salt.hex()}${digest.hex()}'


def verify_password(password: str, stored: str | None) -> bool:
    if not password or not stored or not isinstance(stored, str):
        return False
    if stored.startswith(PREFIX + '$'):
        try:
            kind, count, salt_hex, digest_hex = stored.split('$')
            count = int(count)
            salt = bytes.fromhex(salt_hex)
            digest = bytes.fromhex(digest_hex)
            if kind != PREFIX or not 100_000 <= count <= 2_000_000 or len(salt) < 16 or len(digest) != 32:
                return False
            actual = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, count)
            return hmac.compare_digest(actual, digest)
        except (TypeError, ValueError, OverflowError):
            return False
    if re.fullmatch(r'[0-9a-fA-F]{64}', stored):
        legacy = hashlib.sha256(password.encode('utf-8')).hexdigest()
        return hmac.compare_digest(legacy, stored.lower())
    return False


def needs_upgrade(stored: str | None) -> bool:
    return bool(stored and re.fullmatch(r'[0-9a-fA-F]{64}', stored))


def bootstrap_password_error(password: str) -> str | None:
    if len(password) < 12:
        return 'Yönetici parolası en az 12 karakter olmalı.'
    if password.casefold() in {'admin', '123456789012', 'password1234', 'administrator', 'qwerty123456'}:
        return 'Tahmin edilmesi kolay bir parola seçilemez.'
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        return 'Parola harf ve rakam içermeli.'
    return None


def create_initial_admin(con, password: str) -> None:
    """Atomically create admin ONLY when users table has zero accounts."""
    problem = bootstrap_password_error(password)
    if problem:
        raise ValueError(problem)
    con.execute('BEGIN IMMEDIATE')
    try:
        n = con.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        if n:
            raise ValueError('Başlangıç yöneticisi yalnızca boş kullanıcı tablosunda oluşturulur.')
        columns = {x[1] for x in con.execute('PRAGMA table_info(users)')}
        if 'active' in columns:
            con.execute('INSERT INTO users(username,password_hash,role,active) VALUES(?,?,?,1)',
                        ('admin', hash_password(password), 'admin'))
        else:
            con.execute('INSERT INTO users(username,password_hash,role) VALUES(?,?,?)',
                        ('admin', hash_password(password), 'admin'))
        con.commit()
    except Exception:
        con.rollback()
        raise


def verify_and_upgrade_user(con, username: str, password: str):
    """Return user row (id, role) or None, upgrading legacy hash on successful login."""
    columns = {r[1] for r in con.execute('PRAGMA table_info(users)')}
    if 'active' in columns:
        row = con.execute('SELECT id, role, password_hash, active FROM users WHERE username=?', (username,)).fetchone()
        if row and not row[3]:
            return None
    else:
        row = con.execute('SELECT id, role, password_hash FROM users WHERE username=?', (username,)).fetchone()
    if not row or not verify_password(password, row[2]):
        return None
    if needs_upgrade(row[2]):
        con.execute('UPDATE users SET password_hash=? WHERE id=? AND password_hash=?',
                    (hash_password(password), row[0], row[2]))
        con.commit()
    return row[0], row[1]
