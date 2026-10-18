"""V3.5.32 synthetic tests; no user data, Qt, network, UI or live writes."""
from __future__ import annotations
from contextlib import closing
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import gzip
import json
from pathlib import Path
import sqlite3
import zipfile

import pytest
from services.verified_recovery_v3532 import (
    create_verified_backup, preview_restore, due_for_backup, RecoveryError,
)

@pytest.fixture
def sample(tmp_path):
    source = tmp_path / 'source.db'
    with closing(sqlite3.connect(source)) as conn:
        conn.executescript('''CREATE TABLE ogrenci (id integer PRIMARY KEY, ad text);
            CREATE TABLE odev(id integer PRIMARY KEY, student int);
            CREATE TABLE odev_kume(id integer PRIMARY KEY);
            INSERT INTO ogrenci(id,ad) VALUES (1,'Hayali Ogrenci');''')
    backups = tmp_path / 'backups'
    backups.mkdir()
    return source, backups


def test_compressed_backup_wal_and_restore_rehearsal(sample):
    source, backups = sample
    con = sqlite3.connect(source)
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('INSERT INTO ogrenci VALUES(2,?)', ('WAL committed',))
    con.commit()
    result = create_verified_backup(source, backups)
    assert result['status'] == 'BACKUP_CREATED_AND_REHEARSED', result
    output = Path(result['archive_path'])
    assert output.name.endswith('.db.gz')
    assert len(list(backups.glob('*.db.gz'))) == 1
    with gzip.open(output, 'rb') as fh:
        sqlite_file = backups / 'check-in-test.db'
        sqlite_file.write_bytes(fh.read())
    with closing(sqlite3.connect(sqlite_file)) as conn:
        assert conn.execute('SELECT count(*) FROM ogrenci').fetchone()[0] == 2
    sqlite_file.unlink()
    rehearsal = preview_restore(output, require_manifest=True)
    assert rehearsal['status'] == 'REHEARSAL_PASSED', rehearsal
    assert rehearsal['provenance'] == 'SHA256_MANIFEST_MATCHED'
    assert rehearsal['restored_to_live_database'] is False
    con.close()


def test_uncommitted_row_excluded(sample):
    source, backups = sample
    w = sqlite3.connect(source)
    w.execute('PRAGMA journal_mode=WAL')
    w.execute('INSERT INTO ogrenci VALUES(2,?)', ('Not committed',))
    outcome = create_verified_backup(source, backups)
    assert outcome['status'] == 'BACKUP_CREATED_AND_REHEARSED'
    with gzip.open(outcome['archive_path'], 'rb') as zipped:
        restored = backups / 'temporary.db'
        restored.write_bytes(zipped.read())
    with closing(sqlite3.connect(restored)) as conn:
        assert conn.execute('select count(*) from ogrenci').fetchone()[0] == 1
    w.rollback();w.close()


def test_raw_backup_is_sqlite_binary_not_sql_dump(sample):
    source, backups = sample
    original = source.read_bytes()
    answer = create_verified_backup(source, backups, compress=False)
    assert answer['status'] == 'BACKUP_CREATED_AND_REHEARSED'
    out = Path(answer['archive_path'])
    assert out.read_bytes().startswith(b'SQLite format 3\0')
    assert preview_restore(out)['status'] == 'REHEARSAL_PASSED'
    assert source.read_bytes() == original


def test_corrupted_gzip_does_not_touch_source(sample):
    source, backups = sample
    initial = source.read_bytes()
    candidate = backups / 'faulty.db.gz'
    candidate.write_bytes(b'broken-data')
    assert preview_restore(candidate)['status'] == 'REHEARSAL_FAILED'
    assert source.read_bytes() == initial


def test_dump_disguised_as_db_is_rejected(sample):
    source, backups = sample
    for ext in ('.db', '.db.gz'):
        f = backups / ('legacy' + ext)
        dump = b'BEGIN TRANSACTION;\nCREATE TABLE ogrenci (x);\nCOMMIT;\n'
        if ext.endswith('gz'):
            with gzip.open(f, 'wb') as out:out.write(dump)
        else:f.write_bytes(dump)
        assert preview_restore(f)['status'] == 'REHEARSAL_FAILED'
    assert source.exists()


def test_corrupt_manifest_is_a_failure(sample):
    source, backups = sample
    data = create_verified_backup(source, backups)
    sidecar = Path(data['manifest_path'])
    meta = json.loads(sidecar.read_text())
    meta['database_sha256'] = '0'*64
    sidecar.write_text(json.dumps(meta))
    assert preview_restore(data['archive_path'])['reason'] == 'MANIFEST_MISMATCH'


def test_unmanifested_raw_allowed_only_when_opted_in(sample):
    source, backups = sample
    plain = backups / 'plain.db'
    plain.write_bytes(source.read_bytes())
    assert preview_restore(plain)['status'] == 'REHEARSAL_PASSED'
    assert preview_restore(plain)['provenance'] == 'UNSIGNED_UNMANIFESTED'
    assert preview_restore(plain, require_manifest=True)['reason'] == 'MANIFEST_REQUIRED'


def test_backup_manager_zip_compatible(sample):
    source, backups = sample
    data = source.read_bytes()
    manifest = {'format_version': 2,
        'files':[{'name':'veritabani.db','bytes':len(data),'sha256':sha256(data).hexdigest()},
                 {'name':'planner/plan_profiles.json','type':'json','bytes':2,
                  'sha256':sha256(b'{}').hexdigest()}]}
    archive = backups / 'backup.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('backup_manifest.json',json.dumps(manifest))
        z.writestr('veritabani.db',data)
        z.writestr('planner/plan_profiles.json', b'{}')
    result = preview_restore(archive)
    assert result['status'] == 'REHEARSAL_PASSED', result
    assert result['planner_payloads_present'] is True


def test_zip_without_manifest_rejected(sample):
    source, backups = sample
    archive=backups/'unknown.zip'
    with zipfile.ZipFile(archive,'w') as z:z.writestr('my.db',source.read_bytes())
    assert preview_restore(archive)['reason'] == 'ZIP_MANIFEST_MISSING'


def test_zip_hash_tamper_rejected(sample):
    source, backups=sample
    archive=backups/'tampered.zip'
    data=source.read_bytes()
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr('backup_manifest.json',json.dumps({'format_version':1,'files':[
            {'name':'foo.db','bytes':len(data),'sha256':'0'*64}]}))
        z.writestr('foo.db',data)
    assert preview_restore(archive)['reason']=='ZIP_MANIFEST_HASH_MISMATCH'


def test_broken_database_rejected(sample):
    source,backups=sample
    with closing(sqlite3.connect(source)) as con:
        con.execute('DROP TABLE odev')
        con.commit()
    result=create_verified_backup(source,backups)
    assert result['status']=='BACKUP_FAILED'
    assert list(backups.glob('*.db.gz'))==[]


def test_missing_db_and_invalid_destination_are_safe(tmp_path):
    out = tmp_path/'out';out.mkdir()
    result=create_verified_backup(tmp_path/'missing.db',out)
    assert result['status']=='BACKUP_FAILED'
    assert list(out.iterdir())==[]


def test_progress_helper_does_not_perform_backups():
    now=datetime(2026,10,18,tzinfo=timezone.utc)
    assert due_for_backup(None,now_utc=now) is True
    assert due_for_backup(now-timedelta(hours=12),now_utc=now) is False
    assert due_for_backup(now-timedelta(hours=25),now_utc=now) is True
    with pytest.raises(RecoveryError):due_for_backup(datetime(2026,10,17),now_utc=now)


def test_verify_source_hash_stable(sample):
    source,backups=sample
    old=sha256(source.read_bytes()).hexdigest()
    assert create_verified_backup(source,backups)['status']=='BACKUP_CREATED_AND_REHEARSED'
    assert sha256(source.read_bytes()).hexdigest()==old


def test_filename_collision_no_overwrite(sample,monkeypatch):
    source,backups=sample
    import services.verified_recovery_v3532 as mod
    class FakeClock:
        @classmethod
        def now(cls,*args):return datetime(2026,10,18,0,0,tzinfo=timezone.utc)
    monkeypatch.setattr(mod,'datetime',FakeClock)
    assert create_verified_backup(source,backups)['status']=='BACKUP_CREATED_AND_REHEARSED'
    answer=create_verified_backup(source,backups)
    assert answer['status']=='BACKUP_FAILED'
    assert answer['reason']=='BACKUP_NAME_COLLISION'
    assert len(list(backups.glob('*.db.gz')))==1


def test_zip_traversal_rejected(sample):
    source,backups=sample
    archive=backups/'traversal.zip'
    data=source.read_bytes()
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr('backup_manifest.json',json.dumps({'format_version':1,'files':[
            {'name':'../evil.db','bytes':len(data),'sha256':sha256(data).hexdigest()}]}))
        z.writestr('../evil.db',data)
    assert preview_restore(archive)['reason']=='ZIP_PATH_UNSAFE'
    assert not (backups/'evil.db').exists()


def test_multiple_databases_in_zip_rejected(sample):
    source,backups=sample
    archive=backups/'many.zip'
    data=source.read_bytes()
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr('backup_manifest.json',json.dumps({'format_version':1,'files':[
            {'name':n,'bytes':len(data),'sha256':sha256(data).hexdigest()}
            for n in ('first.db','second.db')]}))
        z.writestr('first.db',data);z.writestr('second.db',data)
    assert preview_restore(archive)['reason']=='ZIP_EXPECTED_ONE_DB'


def test_gzip_decompression_limit_enforced(sample,monkeypatch):
    source,backups=sample
    import services.verified_recovery_v3532 as r
    monkeypatch.setattr(r, 'MAX_PREVIEW_SIZE', 500)
    f=backups/'oversized.db.gz'
    with gzip.open(f,'wb') as z:z.write(source.read_bytes())
    assert preview_restore(f)['reason']=='BACKUP_SIZE_LIMIT'


def test_symbolic_link_backup_disallowed(sample):
    source,backups=sample
    direct=backups/'direct.db'
    direct.write_bytes(source.read_bytes())
    link=backups/'link.db'
    try:link.symlink_to(direct)
    except OSError:pytest.skip('Symlinks unavailable')
    assert preview_restore(link)['reason']=='BACKUP_NOT_FOUND_OR_LINK'
    assert create_verified_backup(link,backups)['reason']=='SYMLINK_PATH_REJECTED'


def test_cli_hides_source_path_and_personal_details(sample,capsys):
    source,backups=sample
    from tools.v3532_recovery_doctor import main
    assert main(['create',str(source),str(backups)])==0
    display=capsys.readouterr().out
    assert str(source) not in display
    assert str(backups) not in display
    assert 'Hayali Ogrenci' not in display
