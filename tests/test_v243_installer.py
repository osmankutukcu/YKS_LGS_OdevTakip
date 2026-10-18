import json
import hashlib
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import pytest

ROOT = Path('/mnt/data/v243_safe_patch')
BASE = Path('/mnt/data/v242_full_source')
if not (ROOT / 'checksums.json').exists():
    pytest.skip("Standalone patch installer test; requires /mnt/data/v243_safe_patch", allow_module_level=True)
META=json.loads((ROOT/'checksums.json').read_text())
SCRIPT=ROOT/'install_v243.py'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def run(project,*args):
    return subprocess.run([sys.executable,str(SCRIPT),'--project',str(project),*args],capture_output=True,text=True)

def fixture(path):
    for rel,change in META['files'].items():
        if change['before'] is not None:
            f=path/rel; f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes((BASE/rel).read_bytes())
    for rel in ('ui/homework_form.py','ui/odev_kontrol.py','db.py'):
        f=path/rel;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes((BASE/rel).read_bytes())

def test_safe_install_then_idempotence_and_rollback():
    with TemporaryDirectory() as tmp:
        p=Path(tmp);fixture(p)
        cores={rel:sha(p/rel) for rel in ('ui/homework_form.py','ui/odev_kontrol.py','db.py')}
        assert 'clean' in run(p,'--check').stdout
        assert run(p,'--install').returncode==0
        assert 'installed' in run(p,'--check').stdout
        assert run(p,'--install').returncode==0
        assert (p/'services/course_topic_scope_v243.py').is_file()
        assert run(p,'--rollback').returncode==0
        assert 'clean' in run(p,'--check').stdout
        assert not (p/'services/course_topic_scope_v243.py').exists()
        for rel,digest in cores.items():assert sha(p/rel)==digest

def test_reject_unrecognized_source_with_no_partial_changes():
    with TemporaryDirectory() as tmp:
        p=Path(tmp);fixture(p)
        first=p/'ui/coaching_manager.py';first.write_text('unknown customization')
        assert run(p,'--install').returncode!=0
        assert first.read_text()=='unknown customization'
        assert not (p/'services/course_topic_scope_v243.py').exists()

def test_reject_missing_project_or_state_mismatch():
    with TemporaryDirectory() as tmp:
        p=Path(tmp)
        assert run(p,'--install').returncode!=0
        fixture(p)
        assert run(p,'--rollback').returncode!=0
