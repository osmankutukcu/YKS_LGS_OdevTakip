"""V3.5.33: synthetic backup schedule and safe opt-in integration tests."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import sqlite3

import pytest
from services import backup_automation_v3533 as b
from services.verified_recovery_v3532 import preview_restore


def sample(tmp_path):
    src=tmp_path/'data.db'
    with closing(sqlite3.connect(src)) as db:
        db.executescript('''CREATE TABLE ogrenci (id INTEGER, name TEXT);
                           CREATE TABLE odev (id INTEGER);
                           CREATE TABLE odev_kume (id INTEGER);
                           INSERT INTO ogrenci VALUES(1, 'Deneme');''')
    dest=tmp_path/'backups';dest.mkdir()
    return src,dest


def test_disabled_is_pure_no_writes(tmp_path):
    source,dest=sample(tmp_path)
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    r=b.run_due_backup(source,dest)
    assert r['status']=='DISABLED'
    assert list(dest.iterdir())==[]
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before


def test_enabled_creates_and_rehearses_exactly_once(tmp_path):
    src,dest=sample(tmp_path)
    digest=hashlib.sha256(src.read_bytes()).hexdigest()
    a=b.run_due_backup(src,dest,enabled=True)
    assert a['status']=='BACKUP_CREATED_AND_VERIFIED',a
    assert a['data_modified'] is False
    outputs=list(dest.glob('YKS_Kurtarilabilir_*.db.gz'))
    assert len(outputs)==1
    assert preview_restore(outputs[0],require_manifest=True)['status']=='REHEARSAL_PASSED'
    z=b.run_due_backup(src,dest,enabled=True)
    assert z['status']=='ALREADY_CURRENT',z
    assert len(list(dest.glob('*.db.gz')))==1
    assert hashlib.sha256(src.read_bytes()).hexdigest()==digest
    assert not (dest/b.LOCK_NAME).exists()


def test_missing_directory_fails_closed(tmp_path):
    src,dest=sample(tmp_path)
    assert b.run_due_backup(src,tmp_path/'unknown',enabled=True)['status']=='LOCATION_NOT_READY'
    assert list(dest.iterdir())==[]


def test_existing_lock_prevents_duplicate_run(tmp_path):
    src,dest=sample(tmp_path)
    lock=dest/b.LOCK_NAME;lock.mkdir()
    assert b.run_due_backup(src,dest,enabled=True)['status']=='BUSY_OR_STALE_LOCK'
    assert lock.exists()
    assert list(dest.glob('*.db.gz'))==[]


def test_unverified_candidate_not_considered_fresh(tmp_path):
    src,dest=sample(tmp_path)
    fake=dest/'YKS_Kurtarilabilir_20261018T010000_000001Z.db.gz'
    fake.write_bytes(b'not really an archive')
    result=b.inspect_last_verified(dest)
    assert result['status']=='NO_VERIFIED_BACKUP'
    assert result['invalid_recent_candidates']==1
    assert b.run_due_backup(src,dest,enabled=True)['status']=='BACKUP_CREATED_AND_VERIFIED'
    assert fake.read_bytes()==b'not really an archive'


def test_no_pruning_prior_good_backup(tmp_path):
    src,dest=sample(tmp_path)
    assert b.run_due_backup(src,dest,enabled=True)['status']=='BACKUP_CREATED_AND_VERIFIED'
    old=list(dest.glob('*.db.gz'))
    future=datetime.now(timezone.utc)+timedelta(days=2)
    assert b.run_due_backup(src,dest,enabled=True,now_utc=future)['status']=='BACKUP_CREATED_AND_VERIFIED'
    assert len(list(dest.glob('*.db.gz')))==2
    assert old[0].exists()


def test_separate_sources_same_target_do_not_skip_each_other(tmp_path):
    one, dest = sample(tmp_path)
    other = tmp_path/'data_two.db'
    with closing(sqlite3.connect(other)) as db:
        db.executescript('''CREATE TABLE ogrenci(id INTEGER);
                           CREATE TABLE odev(id INTEGER);
                           CREATE TABLE odev_kume(id INTEGER);''')
    a=b.run_due_backup(one,dest,enabled=True)
    b_result=b.run_due_backup(other,dest,enabled=True)
    assert a['status']=='BACKUP_CREATED_AND_VERIFIED'
    assert b_result['status']=='BACKUP_CREATED_AND_VERIFIED'
    assert len(list(dest.glob('*.db.gz')))==2
    assert b.run_due_backup(one,dest,enabled=True)['status']=='ALREADY_CURRENT'
    assert b.run_due_backup(other,dest,enabled=True)['status']=='ALREADY_CURRENT'


def test_partial_success_does_not_succeed(monkeypatch,tmp_path):
    src,dest=sample(tmp_path)
    monkeypatch.setattr(b,'create_verified_backup',lambda *a,**kw:{'status':'BACKUP_FAILED','reason':'QUOTA_EXCEEDED'})
    r=b.run_due_backup(src,dest,enabled=True)
    assert r['status']=='BACKUP_FAILED'
    assert r['reason']=='QUOTA_EXCEEDED'
    assert not (dest/b.LOCK_NAME).exists()


def test_no_bypass_legacy_close_on_exit_or_protected_forms():
    base=Path(__file__).resolve().parents[1]
    dialog=(base/'ui/backup_dialog.py').read_text(encoding='utf8')
    strip=(base/'ui/teacher_copilot_strip_v5.py').read_text(encoding='utf8')
    main=(base/'main_window.py').read_text(encoding='utf8')
    assert 'yedek_gunluk_dogrulamali_v3533' in dialog and 'yedek_gunluk_dogrulamali_v3533' in strip
    assert "self.chk_auto.toggled.connect(self.manager.set_auto_backup)" in dialog
    assert 'bm.create_backup()' in main
    assert 'threading.Thread(target=action' in strip
    assert 'services.backup_automation_v3533' in strip


def test_symlink_destination_rejected(tmp_path):
    src,dest=sample(tmp_path)
    shortcut=tmp_path/'link'
    try:shortcut.symlink_to(dest, target_is_directory=True)
    except OSError:pytest.skip('no symlink privilege')
    assert b.run_due_backup(src,shortcut,enabled=True)['status']=='LOCATION_NOT_READY'


def test_no_student_content_in_result(tmp_path):
    src,dest=sample(tmp_path)
    r=b.run_due_backup(src,dest,enabled=True)
    assert 'Deneme' not in str(r)
