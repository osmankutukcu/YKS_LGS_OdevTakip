"""V23.1: A curriculum row's scoped identity; no database migrations.

An ID is stable inside the same SQLite database while its source row exists. This
is NOT a globally unique identifier across independent databases or restores.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
import unicodedata

from services.curriculum_v23.impact import CurriculumSafetyError


def topic_key(name: str) -> str:
    """Comparison key, not an educational synonym mapping."""
    return unicodedata.normalize('NFC', str(name or '').strip()).replace('İ', 'i').replace('I', 'ı').casefold()


@dataclass(frozen=True)
class TopicIdentity:
    scope: str
    ders: str
    row_id: int
    ana_grup: str = ''
    alt_grup: str = ''
    ogrenci_id: int = 0

    def __post_init__(self):
        if self.scope not in ('Genel', 'Grup', 'Öğrenci') or not str(self.ders).strip() or int(self.row_id) <= 0:
            raise CurriculumSafetyError('Geçersiz ders/kapsam/konu kimliği.')
        if self.scope == 'Grup' and (not self.ana_grup or not self.alt_grup):
            raise CurriculumSafetyError('Grup kimliği için ana ve alt grup gerekir.')
        if self.scope == 'Öğrenci' and int(self.ogrenci_id) <= 0:
            raise CurriculumSafetyError('Öğrenci konusuna öğrenci ID gerekli.')
        if self.scope == 'Genel' and (self.ana_grup or self.alt_grup or self.ogrenci_id):
            raise CurriculumSafetyError('Genel konuya özel kapsam eklenemez.')
        if self.scope == 'Grup' and self.ogrenci_id:
            raise CurriculumSafetyError('Grup konusu öğrenci kimliği taşımaz.')
        if self.scope == 'Öğrenci' and (self.ana_grup or self.alt_grup):
            raise CurriculumSafetyError('Öğrenci konusu grup kimliği taşımaz.')

    @property
    def key(self) -> str:
        # JSON escaping prevents accidental separator collisions.
        return 'v231:' + json.dumps([self.scope, self.ders, int(self.row_id), self.ana_grup,
                                    self.alt_grup, int(self.ogrenci_id)], ensure_ascii=False, separators=(',', ':'))
