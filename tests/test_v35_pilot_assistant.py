# -*- coding: utf-8 -*-
"""Windows pilot isolation and truthful reporting tests, without PyQt6."""
from __future__ import annotations
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.v35_pilot_assistant import (CHECK_LABELS, make_dummy_db, safe_env,
                                       prepare, run_gui, record_manual, main,
                                       test_target_identity as identify_target)
from tools.v35_release_gate import MANUAL_CHECKS, check_source
from tools.v35_windows_smoke import smoke

class PilotSafety(unittest.TestCase):
    def test_guarded_synthetic_sqlite_is_valid(self):
        with tempfile.TemporaryDirectory() as t:
            db=Path(t)/'disposable.db'
            make_dummy_db(db)
            with sqlite3.connect(db) as c:
                self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0],'ok')
                self.assertEqual(c.execute('SELECT test_only FROM v35_disposable_pilot_guard').fetchone(),(1,))

    def test_existing_db_never_overwritten(self):
        with tempfile.TemporaryDirectory() as t:
            db=Path(t)/'actual.db';db.write_bytes(b'SENSITIVE_ORIGINAL')
            with self.assertRaises(FileExistsError): make_dummy_db(db)
            self.assertEqual(db.read_bytes(),b'SENSITIVE_ORIGINAL')

    def test_inherited_real_db_overridden_and_auto_adopt_off(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'only_pilot.db'
            with patch.dict(os.environ,{'YKS_DB_PATH':'C:/real_student.db','YKS_AUTO_ADOPT':'1',
                                        'YKS_DATA_DIR':'C:/real_student',
                                        'LOCALAPPDATA':'C:/real_profiles',
                                        'USERPROFILE':'C:/real_user',
                                        'TEMP':'C:/real_temp'}):
                env=safe_env(path)
            self.assertEqual(env['YKS_DB_PATH'],str(path.resolve()))
            self.assertEqual(env['YKS_AUTO_ADOPT'],'0')
            self.assertEqual(env['YKS_PILOT_ISOLATED'],'1')
            for key in ('YKS_DATA_DIR','LOCALAPPDATA','USERPROFILE','APPDATA',
                        'HOME','TEMP','TMP','XDG_CONFIG_HOME','XDG_DATA_HOME'):
                self.assertNotIn('C:/real_',env[key])
                self.assertTrue(Path(env[key]).exists())
                self.assertTrue(str(Path(env[key]).resolve()).startswith(str(Path(t).resolve())))

    def test_legacy_learning_plan_never_imported_in_pilot(self):
        from services.plan_profile_store import legacy_paths
        with patch.dict(os.environ,{'YKS_PILOT_ISOLATED':'1'}):
            self.assertEqual(legacy_paths(),[])
        with patch.dict(os.environ,{'YKS_PILOT_ISOLATED':'0'}):
            self.assertTrue(len(legacy_paths())>=1)

    def test_installer_cannot_be_selected_as_application(self):
        with tempfile.TemporaryDirectory() as t:
            fake=Path(t)/'OdevTakip_v2_Kurulum.exe'; fake.write_bytes(b'MZ')
            with self.assertRaisesRegex(ValueError,'Kurulum'):
                identify_target(fake)

    def test_artifact_fingerprint_has_hash_but_no_private_path(self):
        with tempfile.TemporaryDirectory() as t:
            fake=Path(t)/'OdevTakip_v2.exe'; fake.write_bytes(b'MZpilot')
            result=identify_target(fake)
            self.assertEqual(result['kind'],'WINDOWS_EXE')
            self.assertEqual(len(result['sha256']),64)
            self.assertNotIn(t,str(result))
            self.assertEqual(result['matches_release_commit'],'NOT_VERIFIED')

    def test_exe_cannot_be_ignored_without_interactive(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(SystemExit):
                main(['--exe',str(Path(t)/'unknown.exe'),'--prepare-only'])

    def test_prepare_does_not_mark_pass_or_emit_student_data(self):
        with tempfile.TemporaryDirectory() as t:
            run,man=prepare(Path(t))
            self.assertEqual(man['source_integrity'],'PASS')
            self.assertEqual(man['windows_manual_status'],'NOT_VERIFIED')
            self.assertTrue(all(v=='PENDING' for v in man['checks'].values()))
            self.assertEqual(set(man['checks']),set(MANUAL_CHECKS))
            self.assertTrue((run/'SADECE_DENEME.db').exists())
            report=(run/'pilot_durumu.json').read_text(encoding='utf-8')
            self.assertNotIn('C:/real_student.db',report)
            self.assertTrue((run/'KONTROL_LISTESI.md').exists())
            self.assertFalse((run/'windows_acceptance_TASLAK.json').exists())

    def test_prepare_is_new_each_time(self):
        with tempfile.TemporaryDirectory() as t:
            first,_=prepare(Path(t));second,_=prepare(Path(t))
            self.assertNotEqual(first,second)

    def test_all_checks_have_turkish_labels(self):
        self.assertEqual(set(CHECK_LABELS),set(MANUAL_CHECKS))

    def test_interactive_forbidden_outside_windows(self):
        with patch('sys.platform','linux'):
            with tempfile.TemporaryDirectory() as t:
                with self.assertRaises(SystemExit) as ctx:
                    main(['--interactive','--output-root',t])
                self.assertNotEqual(ctx.exception.code,0)

    def test_manual_record_refused_outside_windows(self):
        with patch('sys.platform','linux'):
            with self.assertRaisesRegex(ValueError,'Windows'):
                record_manual(Path('unused'),{'checks':{}})

    def test_manual_explicit_pending_and_launch_fail_override(self):
        with tempfile.TemporaryDirectory() as t:
            run,man=prepare(Path(t))
            fake_answers=iter(['P']*len(MANUAL_CHECKS))
            with patch('sys.platform','win32'):
                result=record_manual(run,man,launch_ok=False,response=lambda prompt: next(fake_answers))
            self.assertEqual(result['windows_manual_status'],'NOT_VERIFIED')
            self.assertEqual(result['checks']['windows_10_or_11_launch'],'FAIL')
            draft=json.loads((run/'windows_acceptance_TASLAK.json').read_text(encoding='utf-8'))
            self.assertEqual(draft['checks']['windows_10_or_11_launch'],'FAIL')
            self.assertIn('<',draft['tester'])  # never auto-sign a manual review

    def test_manual_empty_is_not_pass(self):
        with tempfile.TemporaryDirectory() as t:
            run,man=prepare(Path(t))
            with patch('sys.platform','win32'):
                record_manual(run,man,response=lambda prompt: '')
            self.assertTrue(all(v=='PENDING' for v in man['checks'].values()))

    def test_smoke_precreates_protected_db_and_disables_adoption(self):
        with tempfile.TemporaryDirectory() as td:
            exe=Path(td)/'dummy.exe'; exe.write_bytes(b'MZdemo')
            evidence=[]
            class FakeProc:
                def poll(self): return None
                def terminate(self): pass
                def wait(self,timeout=None): return 0
            def fake_popen(cmd,**kw):
                env=kw['env'];db=Path(env['YKS_DB_PATH'])
                self.assertTrue(db.exists())
                self.assertEqual(env['YKS_AUTO_ADOPT'],'0')
                self.assertEqual(env['YKS_PILOT_ISOLATED'],'1')
                self.assertTrue(str(Path(env['LOCALAPPDATA']).resolve()).startswith(str(db.parent.resolve())))
                with sqlite3.connect(db) as con:
                    self.assertEqual(con.execute('SELECT test_only FROM v35_disposable_pilot_guard').fetchone(),(1,))
                from services.pilot_boot_guard_v35 import write_pilot_ready
                write_pilot_ready(db,env)
                evidence.append(True)
                return FakeProc()
            with patch.dict(os.environ,{'YKS_AUTO_ADOPT':'1','YKS_DB_PATH':'C:/real_student.db'}):
                report=smoke(exe,platform='win32',seconds=2,popen=fake_popen,sleep=lambda _:None)
            self.assertEqual(report['result'],'PASS')
            self.assertEqual(report['isolated_db_initialized'],'PASS')
            self.assertEqual(evidence,[True])

    def test_release_acceptance_is_external_secret_not_self_referential_commit(self):
        yml=(ROOT/'.github/workflows/build_installer.yml').read_text(encoding='utf-8')
        self.assertIn('secrets.V35_WINDOWS_ACCEPTANCE_JSON',yml)
        self.assertIn('tools/v35_release_gate.py --require-acceptance',yml)
        self.assertIn('Remove-Item release/windows_acceptance_v35.json',yml)
        gitignore=(ROOT/'.gitignore').read_text(encoding='utf-8')
        self.assertIn('release/windows_acceptance_v35.json',gitignore)
        self.assertIn('pilot_runs/',gitignore)

    def test_core_hash_gate_still_passes(self):
        self.assertEqual(check_source(ROOT)['source_status'],'PASS')

if __name__=='__main__': unittest.main()
