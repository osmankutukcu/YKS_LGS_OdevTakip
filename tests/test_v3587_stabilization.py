# -*- coding: utf-8 -*-
"""V3.5.87: no-real-student-data safety, publication and compatibility tests."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch
import errno
import hashlib
import json
import os
import tempfile
import unittest

from services.bulk_reports_v3586 import export_batch_pdf
from tests.test_professional_pdf_v3583 import fixture

DAY = date(2026, 10, 20)
ROOT = Path(__file__).resolve().parents[1]


class StabilizationV3587Tests(unittest.TestCase):
    def setUp(self):
        self.con = fixture()
        self.addCleanup(self.con.close)

    def test_pdf_is_published_only_after_fully_written(self):
        import fitz
        self.con.execute('PRAGMA query_only=ON')
        changes = self.con.total_changes
        original_link = os.link
        observed = []
        def observe(source, destination, *args, **kwargs):
            source = Path(source)
            destination = Path(destination)
            self.assertFalse(destination.exists())
            self.assertEqual(source.suffix, '.part')
            with fitz.open(source) as pdf:
                self.assertGreaterEqual(pdf.page_count, 2)
            observed.append((source.stat().st_size, source.parent == destination.parent))
            return original_link(source, destination, *args, **kwargs)

        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'final.pdf'
            with patch('services.bulk_reports_v3586.os.link', side_effect=observe):
                saved, rows = export_batch_pdf(self.con, [1], target,
                                               reference_day=DAY, template='veli')
            self.assertEqual(saved, str(target))
            self.assertEqual(len(rows), 1)
            self.assertEqual(len(observed), 1)
            self.assertTrue(observed[0][1])
            self.assertEqual(observed[0][0], target.stat().st_size)
            self.assertEqual(sorted(p.name for p in Path(folder).iterdir()), ['final.pdf'])
            self.assertEqual(self.con.total_changes, changes)

    def test_publish_failure_leaves_no_partial_public_file(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'failed.pdf'
            def reject_link(*args, **kwargs):
                self.assertFalse(target.exists())
                raise OSError(errno.EOPNOTSUPP, 'hard link unavailable')
            with patch('services.bulk_reports_v3586.os.link', side_effect=reject_link):
                with self.assertRaisesRegex(OSError, 'atomik'):
                    export_batch_pdf(self.con, [1], target, reference_day=DAY)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_copy_failure_does_not_expose_incomplete_pdf(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'interrupted.pdf'
            def fail_midway(src, dst, length):
                dst.write(src.read(64))
                raise OSError('disk full')
            with patch('services.bulk_reports_v3586.shutil.copyfileobj', side_effect=fail_midway):
                with self.assertRaisesRegex(OSError, 'disk full'):
                    export_batch_pdf(self.con, [1], target, reference_day=DAY)
            self.assertFalse(target.exists())
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_no_overwrite_even_when_target_appears_during_export(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'already_exists.pdf'
            original_link = os.link
            def concurrent_create(source, destination):
                target.write_bytes(b'OTHER PROCESS FILE')
                return original_link(source, destination)
            with patch('services.bulk_reports_v3586.os.link', side_effect=concurrent_create):
                with self.assertRaises(FileExistsError):
                    export_batch_pdf(self.con, [1], target, reference_day=DAY)
            self.assertEqual(target.read_bytes(), b'OTHER PROCESS FILE')
            self.assertEqual([p.name for p in Path(folder).iterdir()], [target.name])

    def test_reference_core_files_still_identical(self):
        manifest = json.loads((ROOT / 'tests/v42_protected_hashes.json').read_text('utf-8'))
        for source, digest in manifest.items():
            with self.subTest(source=source):
                self.assertEqual(hashlib.sha256((ROOT / source).read_bytes()).hexdigest(), digest)


if __name__ == '__main__':
    unittest.main()
