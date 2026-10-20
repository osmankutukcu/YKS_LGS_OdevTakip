import os
import unittest
from unittest.mock import patch
from services.student_load_fastpath_v3578 import install_student_load_fastpath
from services.student_load_profiler_v3577 import install_student_load_profiler


class StudentLoadFastpathTests(unittest.TestCase):
    def make_form(self, *, success=True, bad_id=False, raises=False):
        calls = []
        class Suggestions:
            def _yenile_click(self): calls.append('suggestions')
        class Form:
            oneri = Suggestions()
            def __init__(self):
                self._loaded_student_id = None
            def _secili_ogrenci_id(self):
                return None if bad_id else 12
            def _bilgileri_getir(self):
                calls.append('load')
                if raises: raise RuntimeError('transient')
                self.oneri._yenile_click()
                self._update_student_snapshot()
                if success: self._loaded_student_id = 12
            def _update_student_snapshot(self):
                calls.append('snapshot')
            def _ogrenci_degisti_combo_ile(self):
                calls.append('legacy_start')
                try: self.oneri._yenile_click()
                except Exception: pass
                try: self._bilgileri_getir()
                except Exception: pass
                try: self._update_student_snapshot()
                except Exception: pass
        return Form, calls

    def test_success_skips_only_duplicate_outer_refreshes(self):
        cls, calls = self.make_form()
        self.assertTrue(install_student_load_fastpath(cls))
        self.assertFalse(install_student_load_fastpath(cls))
        cls()._ogrenci_degisti_combo_ile()
        self.assertEqual(calls, ['load', 'suggestions', 'snapshot'])

    def test_missing_selection_preserves_original(self):
        cls, calls = self.make_form(bad_id=True)
        install_student_load_fastpath(cls)
        cls()._ogrenci_degisti_combo_ile()
        self.assertEqual(calls, ['legacy_start', 'suggestions', 'load', 'suggestions', 'snapshot', 'snapshot'])

    def test_partial_load_keeps_outer_refreshes(self):
        cls, calls = self.make_form(success=False)
        install_student_load_fastpath(cls)
        cls()._ogrenci_degisti_combo_ile()
        self.assertEqual(calls, ['load', 'suggestions', 'snapshot', 'suggestions', 'snapshot'])

    def test_load_exception_does_not_repeat_load(self):
        cls, calls = self.make_form(raises=True)
        install_student_load_fastpath(cls)
        cls()._ogrenci_degisti_combo_ile()
        self.assertEqual(calls, ['load', 'suggestions', 'snapshot'])

    def test_disable_restores_legacy_path(self):
        cls, calls = self.make_form()
        with patch.dict(os.environ, {'KOCPILOT_STUDENT_LOAD_FASTPATH': '0'}):
            self.assertFalse(install_student_load_fastpath(cls))
        cls()._ogrenci_degisti_combo_ile()
        self.assertEqual(calls.count('suggestions'), 2)
        self.assertEqual(calls.count('snapshot'), 2)

    def test_v1_profiler_remains_compatible(self):
        cls, calls = self.make_form()
        records=[]
        install_student_load_fastpath(cls)
        class Recorder:
            def append(self, row): records.append(row)
        install_student_load_profiler(cls, recorder=Recorder())
        cls()._ogrenci_degisti_combo_ile()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['parts']['_bilgileri_getir']['calls'], 1)
        self.assertEqual(records[0]['parts']['_update_student_snapshot']['calls'], 1)
        self.assertEqual(calls.count('snapshot'), 1)

if __name__ == '__main__': unittest.main()
