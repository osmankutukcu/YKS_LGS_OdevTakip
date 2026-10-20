import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from services.student_load_profiler_v3577 import (
    BoundedLocalRecorder, install_student_load_profiler,
)
from tools.student_load_report_v1 import read_records, summarise


class FakeTable:
    def rowCount(self): return 12
    def columnCount(self): return 3


class ProfilerTests(unittest.TestCase):
    def make_form(self, calls):
        class Form:
            def _ogrenci_degisti_combo_ile(self):
                calls.append('selection')
                self._bilgileri_getir()
                self._update_student_snapshot()
                return 'selected'
            def _bilgileri_getir(self):
                calls.append('load')
                self._ders_tab_olustur(4, 'ignored')
                return 'loaded'
            def _ders_tab_olustur(self, student_id, lesson):
                calls.append(('lesson', student_id, lesson))
                return object(), FakeTable()
            def _update_student_snapshot(self):
                calls.append('snapshot')
                return 6
        return Form

    def test_original_called_once_and_output_unmodified(self):
        calls, stored = [], []
        form = self.make_form(calls)
        rec = type('Recorder', (), {'append': lambda self, r: stored.append(r)})()
        self.assertTrue(install_student_load_profiler(form, recorder=rec))
        self.assertFalse(install_student_load_profiler(form, recorder=rec))
        self.assertEqual(form()._ogrenci_degisti_combo_ile(), 'selected')
        self.assertEqual(calls, ['selection', 'load', ('lesson', 4, 'ignored'), 'snapshot'])
        self.assertEqual(len(stored), 1)
        record = stored[0]
        self.assertEqual(record['schema'], 'student_load_v1')
        self.assertEqual(record['status'], 'ok')
        self.assertEqual(record['lesson_tables'], 1)
        self.assertEqual(record['lesson_rows'], 12)
        self.assertEqual(record['lesson_columns'], 3)
        self.assertEqual(record['parts']['_bilgileri_getir']['calls'], 1)
        self.assertEqual(record['parts']['_update_student_snapshot']['calls'], 1)
        self.assertNotIn('student_id', json.dumps(record))
        self.assertNotIn('ignored', json.dumps(record))

    def test_direct_load_emits_one_record(self):
        calls, stored = [], []
        form = self.make_form(calls)
        rec = type('Recorder', (), {'append': lambda self, r: stored.append(r)})()
        install_student_load_profiler(form, recorder=rec)
        self.assertEqual(form()._bilgileri_getir(), 'loaded')
        self.assertEqual(len(stored), 1)
        self.assertNotIn('_ogrenci_degisti_combo_ile', stored[0]['parts'])

    def test_diagnostic_writer_failure_does_not_interfere(self):
        form = self.make_form([])
        class BrokenWriter:
            def append(self, result):
                raise OSError('locked')
        install_student_load_profiler(form, recorder=BrokenWriter())
        self.assertEqual(form()._ogrenci_degisti_combo_ile(), 'selected')

    def test_original_exceptions_are_preserved_and_reported(self):
        class Form:
            def _bilgileri_getir(self):
                raise RuntimeError('expected')
        stored = []
        rec = type('Recorder', (), {'append': lambda self, r: stored.append(r)})()
        install_student_load_profiler(Form, recorder=rec)
        with self.assertRaisesRegex(RuntimeError, 'expected'):
            Form()._bilgileri_getir()
        self.assertEqual(stored[0]['status'], 'error')

    def test_progress_update_unmodified(self):
        class Progress:
            def guncelle(self, percent, label): return (percent, label)
        class Form:
            def _bilgileri_getir(self):
                return Progress().guncelle(55, 'loading')
        stored = []
        rec = type('Recorder', (), {'append': lambda self, r: stored.append(r)})()
        install_student_load_profiler(Form, progress_class=Progress, recorder=rec)
        self.assertEqual(Form()._bilgileri_getir(), (55, 'loading'))
        self.assertEqual(stored[0]['parts']['progress_update']['calls'], 1)
        self.assertNotIn('loading', json.dumps(stored[0]))

    def test_bounded_recording_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'diagnostic.jsonl'
            rec = BoundedLocalRecorder(path, max_bytes=175)
            row = {'schema': 'student_load_v1', 'status': 'ok', 'duration_ms': 65.0,
                   'lesson_tables': 2, 'parts': {'_bilgileri_getir': {'total_ms': 44.0}}}
            rec.append(row)
            rec.append(row)
            items = read_records(path)
            self.assertEqual(len(items), 2)
            result = summarise(items)
            self.assertEqual(result['median_ms'], 65.0)
            self.assertEqual(result['successful'], 2)


if __name__ == '__main__': unittest.main()
