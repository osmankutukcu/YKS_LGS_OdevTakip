import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from utils.update_core import (
    release_candidate, strictly_newer, allowed_release_url, allowed_redirect_url,
    parse_checksum_file, UpdateSecurityError, checksum_of_file, validate_installer,
    backup_sqlite_for_update, INSTALLER_NAME,
)
from tools.validate_release import read_versions, emit_checksum

REPO = 'osmankutukcu/YKS_LGS_OdevTakip'
BASE = f'https://github.com/{REPO}/releases/download/v3.5.2/'


def fake_release(**asset_overrides):
    installer = {'name': INSTALLER_NAME, 'browser_download_url': BASE + INSTALLER_NAME,
                 'size': 600, 'digest': 'sha256:' + 'a' * 64}
    installer.update(asset_overrides)
    return {'tag_name': 'v3.5.2', 'name': 'new version', 'body': 'release notes',
            'published_at': '2026-10-10T00:00:00Z', 'assets': [installer]}


class TestUpdateCore(unittest.TestCase):
    def test_version(self):
        self.assertTrue(strictly_newer('v3.5.2', '3.5.0'))
        self.assertFalse(strictly_newer('v3.5.2', '3.5.2'))
        self.assertFalse(strictly_newer('v3.6rc1', '3.5.2'))

    def test_strict_installer(self):
        r = release_candidate(fake_release(), REPO, '3.5.0')
        self.assertTrue(r['has_update'] and r['installable'])
        self.assertEqual(r['sha256'], 'a' * 64)

    def test_no_new_release(self):
        r = release_candidate(fake_release(), REPO, '3.5.2')
        self.assertFalse(r['has_update'])

    def test_source_zip_never_used(self):
        rel = fake_release()
        rel['assets'] = []
        rel['zipball_url'] = f'https://api.github.com/repos/{REPO}/zipball/v3.5.2'
        r = release_candidate(rel, REPO, '3.5.0')
        self.assertTrue(r['has_update'])
        self.assertFalse(r['installable'])
        self.assertEqual('', r['download_url'])

    def test_wrong_asset_url(self):
        r = release_candidate(fake_release(browser_download_url='https://evil.example/install.exe'), REPO, '3.5.0')
        self.assertFalse(r['installable'])

    def test_no_digest_no_sidecar(self):
        r = release_candidate(fake_release(digest=None), REPO, '3.5.0')
        self.assertFalse(r['installable'])

    def test_sidecar_without_digest(self):
        rel = fake_release(digest=None)
        rel['assets'].append({'name': INSTALLER_NAME + '.sha256',
                              'browser_download_url': BASE + INSTALLER_NAME + '.sha256'})
        r = release_candidate(rel, REPO, '3.5.0')
        self.assertTrue(r['installable'])

    def test_bad_tag(self):
        rel = fake_release();rel['tag_name'] = 'v3.5.2-rc1'
        with self.assertRaises(UpdateSecurityError): release_candidate(rel, REPO, '3.5.0')

    def test_reject_http_and_unsafe_redirect(self):
        self.assertFalse(allowed_release_url('http://github.com/' + REPO + '/releases/download/v3.5.2/x', REPO))
        self.assertFalse(allowed_redirect_url('https://attacker.example/setup'))
        self.assertTrue(allowed_redirect_url('https://release-assets.githubusercontent.com/asset'))

    def test_checksum_parser(self):
        h='b'*64
        self.assertEqual(h, parse_checksum_file(h+'  '+INSTALLER_NAME))
        with self.assertRaises(UpdateSecurityError): parse_checksum_file(h+'  a.exe')
        with self.assertRaises(UpdateSecurityError): parse_checksum_file(h+'  '+INSTALLER_NAME+'\n'+h+'  '+INSTALLER_NAME)

    def test_installer_digest_size_and_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / INSTALLER_NAME
            p.write_bytes(b'MZtest_fake_setup')
            h=checksum_of_file(p)
            self.assertTrue(validate_installer(p,h,p.stat().st_size))
            with self.assertRaises(UpdateSecurityError): validate_installer(p,'0'*64,p.stat().st_size)
            with self.assertRaises(UpdateSecurityError): validate_installer(p,h,p.stat().st_size+1)
            p.write_bytes(b'NOT_A_WINDOWS_EXE')
            with self.assertRaises(UpdateSecurityError): validate_installer(p,checksum_of_file(p),p.stat().st_size)

    def test_live_wal_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            dbp=Path(tmp)/'student.db'
            con=sqlite3.connect(str(dbp))
            try:
                con.execute('PRAGMA journal_mode=WAL')
                con.execute('CREATE TABLE tasks(id integer, label text)')
                con.commit()
                con.execute('INSERT INTO tasks VALUES(123, "sample")')
                con.commit()
                copy=backup_sqlite_for_update(dbp, Path(tmp)/'safe_backups')
                db = sqlite3.connect(str(copy))
                try:
                    self.assertEqual((123,'sample'),db.execute('SELECT id,label FROM tasks').fetchone())
                    self.assertEqual('ok',db.execute('PRAGMA quick_check').fetchone()[0])
                finally:
                    db.close()
            finally: con.close()

    def test_missing_backup_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(UpdateSecurityError):
                backup_sqlite_for_update(Path(tmp)/'missing.db',Path(tmp)/'bk')

    def test_corrupted_backup_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'broken.db';p.write_bytes(b'fake_db_data')
            with self.assertRaises(sqlite3.DatabaseError): backup_sqlite_for_update(p,Path(tmp)/'backup')

    def test_release_guard_consistency(self):
        self.assertEqual('3.5.6',read_versions())

    def test_checksum_sidecar_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/INSTALLER_NAME;p.write_bytes(b'MZ-EXE')
            out=emit_checksum(p)
            self.assertEqual(hashlib.sha256(b'MZ-EXE').hexdigest(),parse_checksum_file(out.read_bytes()))


if __name__ == '__main__': unittest.main()
