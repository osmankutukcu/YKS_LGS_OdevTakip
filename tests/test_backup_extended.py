"""Additional synthetic regression checks for backup_manager. No real student data."""
import hashlib
import json
import os
import re
import sqlite3
import zipfile
from pathlib import Path

import pytest
from test_backup_manager import patched, make_db


def get_archive(root):
    archives = list((root / 'out').glob('YKS_Yedek_*.zip'))
    assert len(archives) == 1
    return archives[0]


def prepare(patched, monkeypatch, db_filename='veritabani.db'):
    manager, root = patched
    db_file = root / db_filename
    make_db(db_file)
    monkeypatch.setenv('YKS_DB_PATH', str(db_file))
    (root / 'out').mkdir()
    return manager, root, db_file


def test_error_nonexisting_destination(patched):
    manager, root = patched
    success, msg = manager.create_backup(root / 'missing')
    assert success is False
    assert 'klasör' in msg


def test_error_destination_is_file(patched):
    manager, root = patched
    dest = root / 'a_file'
    dest.write_text('x', encoding='utf8')
    assert manager.create_backup(dest)[0] is False


def test_error_when_no_configured_destination(patched):
    manager, _ = patched
    assert manager.create_backup()[0] is False


def test_invalid_database_signature_is_rejected(patched, monkeypatch):
    manager, root = patched
    garbage = root / 'veritabani.db'
    garbage.write_bytes(b'not a database ' * 80)
    monkeypatch.setenv('YKS_DB_PATH', str(garbage))
    (root / 'out').mkdir()
    assert manager.create_backup(root / 'out')[0] is False
    assert not list((root / 'out').glob('*.zip'))


def test_truncated_sqlite_is_not_accepted(patched, monkeypatch):
    manager, root = patched
    broken = root / 'veritabani.db'
    broken.write_bytes(b'SQLite format 3\0' + b'X' * 800)
    monkeypatch.setenv('YKS_DB_PATH', str(broken))
    (root / 'out').mkdir()
    success, _ = manager.create_backup(root / 'out')
    assert not success
    assert not list((root / 'out').glob('*.zip'))


def test_sha256_manifest_matches_restored_bytes(patched, monkeypatch):
    manager, root, _ = prepare(patched, monkeypatch)
    assert manager.create_backup(root / 'out')[0]
    with zipfile.ZipFile(get_archive(root)) as z:
        manifest = json.loads(z.read('backup_manifest.json'))
        assert manifest['format_version'] == 1
        assert manifest['created_at_utc'].endswith('+00:00')
        for entry in manifest['files']:
            payload = z.read(entry['name'])
            assert entry['bytes'] == len(payload)
            assert entry['sha256'] == hashlib.sha256(payload).hexdigest()
            assert payload.startswith(b'SQLite format 3\0')


def test_backup_does_not_mutate_source_db(patched, monkeypatch):
    manager, root, source = prepare(patched, monkeypatch)
    old_hash = hashlib.sha256(source.read_bytes()).digest()
    assert manager.create_backup(root / 'out')[0]
    assert hashlib.sha256(source.read_bytes()).digest() == old_hash


def test_backup_is_readable_when_writer_connection_is_open(patched, monkeypatch):
    manager, root, source = prepare(patched, monkeypatch)
    writer = sqlite3.connect(source)
    writer.execute('PRAGMA journal_mode=WAL')
    writer.execute("INSERT INTO ogrenci(ad) VALUES ('Committed WAL record')")
    writer.commit()
    assert manager.create_backup(root / 'out')[0]
    with zipfile.ZipFile(get_archive(root)) as z:
        recovered = root / 'restore.db'
        recovered.write_bytes(z.read('veritabani.db'))
    with sqlite3.connect(recovered) as reader:
        assert reader.execute('select count(*) from ogrenci').fetchone()[0] == 2
        assert reader.execute('pragma integrity_check').fetchone()[0] == 'ok'
    writer.close()


def test_uncommitted_write_not_in_snapshot(patched, monkeypatch):
    manager, root, source = prepare(patched, monkeypatch)
    writer = sqlite3.connect(source)
    writer.execute('PRAGMA journal_mode=WAL')
    writer.execute("INSERT INTO ogrenci(ad) VALUES ('Uncommitted record')")
    assert manager.create_backup(root / 'out')[0]
    with zipfile.ZipFile(get_archive(root)) as z:
        recovered = root / 'restore.db'
        recovered.write_bytes(z.read('veritabani.db'))
    with sqlite3.connect(recovered) as reader:
        assert reader.execute('select count(*) from ogrenci').fetchone()[0] == 1
    writer.rollback()
    writer.close()


def test_duplicate_path_references_do_not_duplicate_archive_entries(patched, monkeypatch):
    manager, root, source = prepare(patched, monkeypatch)
    assert manager.create_backup(root / 'out')[0]
    with zipfile.ZipFile(get_archive(root)) as z:
        assert z.namelist().count(source.name) == 1


def test_extra_databases_not_silently_captured(patched, monkeypatch):
    manager, root, source = prepare(patched, monkeypatch)
    other = root / 'settings.db'
    make_db(other)
    assert manager.create_backup(root / 'out')[0]
    with zipfile.ZipFile(get_archive(root)) as z:
        assert set(z.namelist()) == {'veritabani.db', 'backup_manifest.json'}


def test_backup_filename_contains_safe_unique_timestamp(patched, monkeypatch):
    manager, root, _ = prepare(patched, monkeypatch)
    assert manager.create_backup(root / 'out')[0]
    assert re.fullmatch(r'YKS_Yedek_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_\d{6}\.zip',get_archive(root).name)


def test_old_backup_rotation_preserves_last_ten(patched, monkeypatch):
    manager, root, _ = prepare(patched, monkeypatch)
    for i in range(13):
        assert manager.create_backup(root / 'out')[0]
    assert len(list((root / 'out').glob('YKS_Yedek_*.zip'))) == 10


def test_other_zips_are_not_deleted_during_retention(patched, monkeypatch):
    manager, root, _ = prepare(patched, monkeypatch)
    unrelated = root / 'out' / 'my_school_archive.zip'
    unrelated.write_bytes(b'untouched')
    for _ in range(11):
        assert manager.create_backup(root / 'out')[0]
    assert unrelated.read_bytes() == b'untouched'


def test_cwd_fallback_detects_real_db(patched):
    manager, root = patched
    make_db(root / 'YKS_LGS_HomeworkManager.db')
    (root / 'out').mkdir()
    assert manager.create_backup(root / 'out')[0]


def test_backup_contents_are_not_encrypted(patched, monkeypatch):
    """Current state documented: this is a SECURITY GAP, not a passing security control."""
    manager, root, _ = prepare(patched, monkeypatch)
    assert manager.create_backup(root / 'out')[0]
    with zipfile.ZipFile(get_archive(root)) as z:
        assert all((entry.flag_bits & 1) == 0 for entry in z.infolist())


def test_security_only_explicitly_selected_database_should_be_in_archive(patched, monkeypatch):
    manager, root, source = prepare(patched, monkeypatch)
    # This can accidentally include a separate SQLite file in the working folder.
    other = root / 'data.db'
    make_db(other)
    assert manager.create_backup(root / 'out')[0]
    with zipfile.ZipFile(get_archive(root)) as z:
        assert set(z.namelist()) == {source.name, 'backup_manifest.json'}


def test_security_bad_explicit_path_must_fail_closed(patched, monkeypatch):
    manager, root = patched
    explicit = root / 'missing.db'
    monkeypatch.setenv('YKS_DB_PATH', str(explicit))
    make_db(root / 'data.db')
    (root / 'out').mkdir()
    assert manager.create_backup(root / 'out')[0] is False
