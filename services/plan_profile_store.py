"""Atomic and user-writable profile storage for installed Windows builds."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Dict, Any


def profile_path() -> Path:
    try:
        from db import _platform_appdata_dir
        return _platform_appdata_dir() / 'plan_profiles.json'
    except Exception:
        pass
    if sys.platform == 'win32':
        base = os.getenv('LOCALAPPDATA') or os.getenv('APPDATA')
        root = Path(base) if base else Path.home() / 'AppData' / 'Local'
    else:
        root = Path(os.getenv('XDG_CONFIG_HOME') or (Path.home() / '.config'))
    return root / 'YKS_LGS_HomeworkManager' / 'plan_profiles.json'


def legacy_paths() -> list[Path]:
    return [
        Path.home() / 'AppData' / 'Roaming' / 'YKS_LGS_OdevTakip' / 'plan_profiles.json',
        Path.home() / '.config' / 'YKS_LGS_OdevTakip' / 'plan_profiles.json',
        Path.home() / '.yks_lgs_manager' / 'plan_profiles.json',
        Path.cwd() / 'plan_profiles.json',
        Path(sys.executable).resolve().parent / 'plan_profiles.json',
        Path(__file__).resolve().parent.parent / 'plan_profiles.json'
    ]


def load_profiles(path: Path | None = None) -> Dict[str, Any]:
    path = path or profile_path()
    if path.exists():
        with path.open('r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {}
        for legacy in legacy_paths():
            if legacy.is_file():
                with legacy.open('r', encoding='utf-8') as f:
                    data = json.load(f)
                break
    if not isinstance(data, dict) or not all(isinstance(x, dict) for x in data.values()):
        raise ValueError('Profil dosyasının biçimi geçersiz.')
    return data


def save_profiles(profiles: Dict[str, Any], path: Path | None = None) -> Path:
    path = path or profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=str(path.parent), prefix='.profiles-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(profiles, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return path


def assignment_path() -> Path:
    return profile_path().with_name('plan_student_assignments.json')


def load_assignments(path: Path | None = None) -> Dict[str, str]:
    path = path or assignment_path()
    if not path.is_file():
        return {}
    with path.open('r', encoding='utf-8') as stream:
        data = json.load(stream)
    if not isinstance(data, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in data.items()):
        raise ValueError('Öğrenci profil eşleşmeleri geçersiz.')
    return data


def save_assignments(assignments: Dict[str, str], path: Path | None = None) -> Path:
    return save_profiles(assignments, path or assignment_path())
