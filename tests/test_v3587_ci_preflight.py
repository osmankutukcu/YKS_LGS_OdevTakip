# -*- coding: utf-8 -*-
"""Synthetic isolated tests, never touch student databases."""
from __future__ import annotations
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools.v3587_ci_preflight import verify

ROOT = Path(__file__).resolve().parents[1]

class WindowsReleasePreflightTests(unittest.TestCase):
    def test_current_source_passes(self):
        self.assertGreaterEqual(len(verify(ROOT)), 10)

    def test_smoke_skip_is_rejected(self):
        original = (ROOT / '.github/workflows/build_installer.yml').read_text('utf-8')
        modified = original.replace('          if ($LASTEXITCODE -ne 0) { throw "Windows EXE acilis testi basarisiz; kurulum yayinlanamaz" }',
                                    '          exit 0', 1)
        self.assertNotEqual(original, modified)
        original_read_text = Path.read_text
        def replacement(path, *args, **kwargs):
            return modified if str(path).endswith('build_installer.yml') else original_read_text(path, *args, **kwargs)
        with patch.object(Path, 'read_text', new=replacement):
            with self.assertRaisesRegex(ValueError, 'zorunlu adım|yok sayılıyor'):
                verify(ROOT)

    def test_missing_installer_dependency_is_rejected(self):
        original = (ROOT / 'OdevTakip_v2.spec').read_text('utf-8')
        modified = original.replace("    'fitz',  # V3.5.87 PDF sayfa onizleme / toplu rapor\n", '', 1)
        self.assertNotEqual(original,modified)
        original_read_text = Path.read_text
        def replacement(path, *args, **kwargs):
            return modified if str(path).endswith('OdevTakip_v2.spec') else original_read_text(path, *args, **kwargs)
        with patch.object(Path, 'read_text', new=replacement):
            with self.assertRaisesRegex(ValueError, 'fitz'):
                verify(ROOT)

if __name__ == '__main__':
    unittest.main()
