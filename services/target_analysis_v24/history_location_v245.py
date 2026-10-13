# -*- coding: utf-8 -*-
"""V24.5 – geçmiş veri konumunu değiştirmeden doğru dosyayı bul.

V24.4 ve eski sürümlerde ``db.get_db_path()`` kullanılmıştı; bazı sürümlerde
bu fonksiyon bulunmadığı için Windows LOCALAPPDATA yedeği kullanılıyordu.
Var olan dosyayı habersiz taşımayız; iki veritabanı varsa çakışmayı bildiririz.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class HistoryLocation:
    selected: Path
    legacy: Path
    canonical: Path
    conflict: bool


def resolve_history_location(main_db_path: str | Path, *, local_app_data: str | Path | None = None) -> HistoryLocation:
    main = Path(main_db_path)
    if not str(main) or not main.name:
        raise ValueError('Öğrenci veritabanı yolu belirlenemedi.')
    canonical = main.parent / 'deneme_history.db'
    if local_app_data is None:
        local_app_data = os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')
    legacy = Path(local_app_data) / 'YKS_LGS_HomeworkManager' / 'deneme_history.db'
    try:
        same = canonical.resolve() == legacy.resolve()
    except OSError:
        same = canonical == legacy
    both = not same and legacy.is_file() and canonical.is_file()
    # V24.4'e kadar geçmiş Windows kurulumları önce legacy konumu kullandı.
    # Var olan o kayıtlar asla örtük olarak kaybolmasın.
    selected = legacy if legacy.is_file() else canonical
    return HistoryLocation(selected, legacy, canonical, both)
