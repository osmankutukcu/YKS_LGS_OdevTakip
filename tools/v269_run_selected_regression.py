# -*- coding: utf-8 -*-
"""Portable, safe regression launcher for the documented V26.9 selected suite.

For Windows/macOS/Linux. Read-only against application student data; tests use
fixtures and temporary files. This is NOT a replacement for GUI acceptance.
"""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TEST_LIST = ROOT / 'V26_9_SECILI_TEST_DOSYALARI.txt'


def main() -> int:
    selected = [line.strip() for line in TEST_LIST.read_text('utf-8').splitlines()
                if line.strip() and not line.startswith('#')]
    if not selected or any(not x.startswith('tests/') or '..' in Path(x).parts
                           or not (ROOT / x).is_file() for x in selected):
        print('Selected test file list missing or invalid.', file=sys.stderr)
        return 2
    print('Running', len(selected), 'selected test modules (not full project or GUI acceptance).', flush=True)
    return subprocess.call([sys.executable, '-m', 'pytest', '-q', *selected], cwd=ROOT)


if __name__ == '__main__':
    raise SystemExit(main())
