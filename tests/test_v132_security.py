"""Headless security regression suite. Does not depend on PyQt or actual user DB."""
import hashlib
import sqlite3
import unittest
from pathlib import Path
from utils.auth_security_v13 import (
    bootstrap_password_error, create_initial_admin,
    hash_password, needs_upgrade, verify_and_upgrade_user, verify_password,
)


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(':memory:')
        self.con.execute('''CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
                         password_hash TEXT NOT NULL, role TEXT, active INTEGER DEFAULT 1)''')

    def tearDown(self):
        self.con.close()

    def test_new_hash_is_salted(self):
        a, b = hash_password('Güclu12!Güclu12'), hash_password('Güclu12!Güclu12')
        self.assertNotEqual(a, b)
        self.assertTrue(verify_password('Güclu12!Güclu12', a))
        self.assertFalse(verify_password('yanlis', a))

    def test_legacy_hash_is_verified(self):
        legacy = hashlib.sha256('mevcut-parola'.encode()).hexdigest()
        self.assertTrue(verify_password('mevcut-parola', legacy))
        self.assertFalse(verify_password('baska', legacy))
        self.assertTrue(needs_upgrade(legacy))

    def test_malformed_hash_is_rejected(self):
        for entry in ('bad', 'pbkdf2_sha256$123$abc$abc', None, '', 'f' * 80):
            self.assertFalse(verify_password('x', entry))

    def test_bootstrap_password_restriction(self):
        for x in ('admin', '123456789012', 'short', 'abcdefghijklmn'):
            self.assertIsNotNone(bootstrap_password_error(x))
        self.assertIsNone(bootstrap_password_error('LongAdminPassword74'))

    def test_first_setup_creates_admin_without_plaintext(self):
        create_initial_admin(self.con, 'LongAdminPassword74')
        row = self.con.execute('SELECT username, role, password_hash FROM users').fetchone()
        self.assertEqual(row[0:2], ('admin', 'admin'))
        self.assertTrue(row[2].startswith('pbkdf2_sha256$'))
        self.assertTrue(verify_password('LongAdminPassword74', row[2]))
        self.assertNotIn('LongAdminPassword74', row[2])

    def test_second_bootstrap_is_rejected_without_overwriting(self):
        create_initial_admin(self.con, 'LongAdminPassword74')
        with self.assertRaises(ValueError):
            create_initial_admin(self.con, 'NewDifferentPassword74')
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM users').fetchone()[0], 1)

    def test_bootstrap_failure_does_not_leave_transaction_open(self):
        with self.assertRaises(ValueError):
            create_initial_admin(self.con, 'bad')
        create_initial_admin(self.con, 'LongAdminPassword74')
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM users').fetchone()[0], 1)

    def test_legacy_migration_only_on_correct_password(self):
        old = hashlib.sha256('OldPassword123'.encode()).hexdigest()
        self.con.execute('INSERT INTO users(username,password_hash,role) VALUES (?,?,?)', ('teacher',old,'user'))
        self.con.commit()
        self.assertIsNone(verify_and_upgrade_user(self.con, 'teacher', 'wrong'))
        self.assertEqual(self.con.execute('SELECT password_hash FROM users').fetchone()[0], old)
        self.assertEqual(verify_and_upgrade_user(self.con, 'teacher', 'OldPassword123')[1], 'user')
        new_hash = self.con.execute('SELECT password_hash FROM users').fetchone()[0]
        self.assertTrue(new_hash.startswith('pbkdf2_sha256$'))
        self.assertTrue(verify_password('OldPassword123', new_hash))

    def test_disabled_account_cannot_login_or_upgrade(self):
        old = hashlib.sha256(b'ValidPassword123').hexdigest()
        self.con.execute('INSERT INTO users(username,password_hash,role,active) VALUES (?,?,?,0)',
                         ('disabled', old, 'user'))
        self.con.commit()
        self.assertIsNone(verify_and_upgrade_user(self.con, 'disabled', 'ValidPassword123'))
        self.assertEqual(self.con.execute('SELECT password_hash FROM users').fetchone()[0], old)

    def test_new_hash_does_not_rehash_on_each_login(self):
        create_initial_admin(self.con, 'LongAdminPassword74')
        before = self.con.execute('SELECT password_hash FROM users').fetchone()[0]
        self.assertIsNotNone(verify_and_upgrade_user(self.con, 'admin', 'LongAdminPassword74'))
        after = self.con.execute('SELECT password_hash FROM users').fetchone()[0]
        self.assertEqual(before, after)

    def test_other_account_is_not_modified(self):
        self.con.executemany('INSERT INTO users(username,password_hash,role) VALUES (?,?,?)', [
           ('a', hashlib.sha256(b'a-pass').hexdigest(), 'user'),
           ('b', hashlib.sha256(b'b-pass').hexdigest(), 'user')])
        self.con.commit()
        before = self.con.execute("SELECT password_hash FROM users WHERE username='b'").fetchone()[0]
        verify_and_upgrade_user(self.con, 'a', 'a-pass')
        self.assertEqual(before, self.con.execute("SELECT password_hash FROM users WHERE username='b'").fetchone()[0])

    def test_pbkdf2_iteration_floor(self):
        with self.assertRaises(ValueError):
            hash_password('test', iterations=1000)

    def test_source_entrypoints_have_no_known_admin_seed(self):
        root = Path(__file__).resolve().parents[1]
        for f in ('db.py', 'ui/user_manager.py'):
            src = (root/f).read_text(encoding='utf-8')
            self.assertNotIn('hashlib.sha256("admin".encode())', src)

    def test_startup_login_fail_closed(self):
        app = (Path(__file__).resolve().parents[1] / 'app.py').read_text(encoding='utf-8')
        self.assertIn('first_boot or (appset.ayar_get("enable_login", "1") == "1")', app)
        self.assertIn('Güvenli Giriş Hatası', app)
        self.assertNotIn('print("Login hatası:", e)\n        enable_login = False', app)

    def test_wizard_integrity_transfer_unchanged(self):
        root=Path(__file__).resolve().parents[1]
        form=(root/'ui/homework_form.py').read_text(encoding='utf-8')
        self.assertIn('def _wizard_transfer_tasks', form)
        self.assertIn('item.setCheckState(Qt.CheckState.Checked)', form)
        self.assertIn('if not (same_student(current_id, expected_student_id)', form)
        self.assertIn('self._sync_verilen_rows_from_table()', form)


if __name__=='__main__':
    unittest.main()
