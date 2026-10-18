# V10 sources: protect baseline and prohibit pretending Windows acceptance.
from pathlib import Path
import hashlib
import json
import zipfile
ROOT=Path(__file__).resolve().parents[1]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def test_offline_v10_additive_and_protected():
    manifest=json.loads((ROOT/'V9_OFFLINE_MANIFEST.json').read_text(encoding='utf-8'))
    for path in manifest['protected_unchanged']:
        assert (ROOT/path).is_file()
    # NOTE: V9 protected source digest is measured in v10 baseline, never re-pinned.
    assert 'manual_windows_acceptance' in (ROOT/'tools/v35_release_gate.py').read_text(encoding='utf-8')
    assert 'validate_acceptance' in (ROOT/'tools/v35_release_gate.py').read_text(encoding='utf-8')
    workflow=ROOT/'.github/workflows/build_installer.yml'
    assert workflow.is_file()
    txt=workflow.read_text(encoding='utf-8')
    assert 'tools/v35_release_gate.py --require-acceptance' in txt
    assert 'tools/v35_windows_smoke.py --exe' in txt
    assert 'dist/v35_windows_smoke.json' in txt

def test_release_approval_remains_manual():
    data=json.loads((ROOT/'release/windows_acceptance_TEMPLATE.json').read_text(encoding='utf-8'))
    assert all(v=='PENDING' for v in data['checks'].values())
    assert not (ROOT/'release/windows_acceptance_v35.json').exists()
