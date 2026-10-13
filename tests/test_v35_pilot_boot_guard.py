# -*- coding: utf-8 -*-
"""Pilot process isolation and fail-closed handshakes; no Qt required."""
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from services.pilot_boot_guard_v35 import (
    pilot_instance_key, ready_matches, verify_pilot_database, write_pilot_ready)
from tools.v35_pilot_assistant import make_dummy_db
from tools.v35_windows_smoke import smoke


class PilotBootGuardTests(unittest.TestCase):
    def test_normal_instance_key_is_unchanged(self):
        self.assertEqual(pilot_instance_key('legacy_key',{}),'legacy_key')
        self.assertEqual(pilot_instance_key('legacy_key',{'YKS_PILOT_ISOLATED':'0'}),'legacy_key')

    def test_pilot_instance_key_unique_for_each_disposable_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            env={'YKS_PILOT_ISOLATED':'1', 'YKS_DB_PATH':str(Path(tmp)/'pilot.db')}
            key=pilot_instance_key('legacy_key',env)
            self.assertNotEqual(key,'legacy_key')
            self.assertNotIn(tmp,key)
            self.assertEqual(key,pilot_instance_key('legacy_key',env))
            env['YKS_DB_PATH']=str(Path(tmp)/'another.db')
            self.assertNotEqual(key,pilot_instance_key('legacy_key',env))

    def test_missing_db_path_blocks_pilot(self):
        with self.assertRaises(ValueError):
            pilot_instance_key('legacy_key',{'YKS_PILOT_ISOLATED':'1'})

    def test_verify_rejects_unrelated_or_non_guarded_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'dummy.db';make_dummy_db(p)
            alternate=Path(tmp)/'other.db'
            sqlite3.connect(alternate).close()
            env={'YKS_PILOT_ISOLATED':'1','YKS_DB_PATH':str(p)}
            verify_pilot_database(p,env)
            with self.assertRaises(ValueError):verify_pilot_database(alternate,env)
            env['YKS_DB_PATH']=str(alternate)
            with self.assertRaises(sqlite3.DatabaseError):verify_pilot_database(alternate,env)

    def test_ready_marker_written_only_for_correct_guard_and_nonce(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'dummy.db';make_dummy_db(p)
            ready=Path(tmp)/'pilot_ready.json'
            env={'YKS_PILOT_ISOLATED':'1','YKS_DB_PATH':str(p),
                 'YKS_PILOT_NONCE':'ab'*16,'YKS_PILOT_READY_PATH':str(ready)}
            self.assertFalse(ready_matches(ready,'ab'*16))
            write_pilot_ready(p,env)
            self.assertTrue(ready_matches(ready,'ab'*16))
            self.assertFalse(ready_matches(ready,'cd'*16))
            self.assertEqual(set(json.loads(ready.read_text())),{'status','nonce','db_guard'})
            with self.assertRaises(FileExistsError):write_pilot_ready(p,env)

    def test_no_ready_marker_leaves_smoke_as_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe=Path(tmp)/'dummy.exe';exe.write_bytes(b'MZpilot')
            class NeverExits:
                def poll(self):return None
                def terminate(self):pass
                def wait(self,timeout=None):return 0
            result=smoke(exe,platform='win32',seconds=2,
                         popen=lambda *a,**kw:NeverExits(),sleep=lambda _:None)
            self.assertEqual(result['result'],'FAIL')
            self.assertEqual(result['isolated_db_initialized'],'FAIL')

    def test_actual_startup_integrates_guard_before_db_write(self):
        s=(ROOT/'app.py').read_text(encoding='utf-8')
        self.assertIn('pilot_instance_key("yks_lgs_odev_takip_v2_lock")',s)
        self.assertLess(s.index('verify_pilot_database(db.DB_PATH)'),s.index('db.init_db()'))
        self.assertLess(s.index('db.init_db()'),s.index('write_pilot_ready(db.DB_PATH)'))

if __name__=='__main__':unittest.main()
