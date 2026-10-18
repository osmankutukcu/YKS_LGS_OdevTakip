# -*- coding: utf-8 -*-
import importlib.util
from pathlib import Path
import tempfile,unittest,json
FILE=Path(__file__).resolve().parents[1]/'tools'/'windows_readiness_v254.py'
spec=importlib.util.spec_from_file_location('windows_readiness_v254',FILE)
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)

class ReadinessTests(unittest.TestCase):
    def test_nonwindows_never_runs_checker(self):
        def must_not_run():raise AssertionError('must not be invoked')
        report=v.build_report(checker=must_not_run,os_name='posix')
        self.assertEqual(report['result'],'NOT_RUN_WINDOWS_REQUIRED')
        self.assertFalse(report['automatic_sending_enabled'])
    def test_success_validated_but_sending_disabled(self):
        r=v.build_report(checker=lambda:{'result':'PASS_WINDOWS_SYNTHETIC_TEST',
                              'passed_checks':list(v.EXPECTED)},os_name='nt')
        self.assertEqual(r['result'],'PASS_WINDOWS_SYNTHETIC_TEST')
        self.assertEqual(r['two_distinct_windows_users'],'NOT_VERIFIED')
        self.assertFalse(r['baileys_enabled'])
    def test_missing_check_fails_closed(self):
        r=v.build_report(checker=lambda:{'result':'PASS_WINDOWS_SYNTHETIC_TEST',
                            'passed_checks':['dpapi_roundtrip']},os_name='nt')
        self.assertEqual(r['result'],'FAIL_CLOSED')
    def test_repeated_check_fails_closed(self):
        r=v.build_report(checker=lambda:{'result':'PASS_WINDOWS_SYNTHETIC_TEST',
                           'passed_checks':list(v.EXPECTED)+['dpapi_roundtrip']},os_name='nt')
        self.assertEqual(r['result'],'FAIL_CLOSED')
    def test_unknown_result_fails_closed(self):
        r=v.build_report(checker=lambda:{'result':'NEVER_HEARD_OF_IT'},os_name='nt')
        self.assertEqual(r['result'],'FAIL_CLOSED')
    def test_runtime_exception_fails_closed(self):
        def crash():raise RuntimeError('secret message token')
        r=v.build_report(checker=crash,os_name='nt')
        self.assertEqual(r['result'],'FAIL_CLOSED')
        self.assertNotIn('secret',json.dumps(r))
    def test_report_is_private_and_retained(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);r=v.build_report(os_name='posix')
            j,s=v.save_report(r,p)
            self.assertTrue(j.is_file() and s.is_file())
            self.assertFalse(any(s in j.read_text() for s in ['0532','token','user_id']))
            self.assertEqual(json.loads(j.read_text())['personal_data_read'],'NONE')
            j2,s2=v.save_report(r,p)
            self.assertNotEqual(j,j2)
            self.assertTrue(s2.is_file())
    def test_text_never_reports_success_as_send(self):
        r=v.build_report(checker=lambda:{'result':'PASS_WINDOWS_SYNTHETIC_TEST','passed_checks':list(v.EXPECTED)},os_name='nt')
        s=v.render_text(r)
        self.assertIn('Mesaj gonderimi: KAPALI',s)
        self.assertIn('HENUZ DOGRULANMADI',s)
    def test_broken_output_directory_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            base=Path(t);link=base/'shortcut';link.symlink_to(base, target_is_directory=True)
            with self.assertRaises(RuntimeError):v._safe_output_dir(str(link))
    def test_report_no_network_or_whatsapp_import(self):
        src=FILE.read_text(encoding='utf-8')
        self.assertNotIn('baileys',src.lower().split('from services.whatsapp_queue.readiness_v252')[0])
        self.assertNotIn('requests.',src)
    def test_output_has_fixed_flags(self):
        for name in ('nt','posix'):
            r=v.build_report(checker=lambda:{'result':'PASS_WINDOWS_SYNTHETIC_TEST','passed_checks':list(v.EXPECTED)},os_name=name)
            self.assertEqual(r['actual_whatsapp_send'],'NOT_ATTEMPTED')
            self.assertEqual(r['secure_queue_is_default'],'NO')

if __name__=='__main__':unittest.main()
