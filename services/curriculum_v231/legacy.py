"""Legacy (often name-only) topic references: conservative resolution only."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from .reader import CurriculumSnapshot, TopicRecord
from .identity import topic_key


@dataclass(frozen=True)
class LegacyResolution:
    status: str  # unique / ambiguous / missing / name_changed_review / mismatch
    topic: Optional[TopicRecord]
    candidate_keys: tuple[str, ...]
    reason: str


def resolve_legacy(snapshot: CurriculumSnapshot, *, topic_name: str,
                   general_topic_id: Optional[int] = None) -> LegacyResolution:
    """Never mutate historic assignments or assume a masked topic is unique.

    A general numeric ID is usable only when the historical name ALSO matches
    and no matching scoped aliases exist. Rename drift requires manual review.
    """
    key = topic_key(topic_name)
    candidates = [item for item in snapshot.all_sources if topic_key(item.name) == key]
    possible_ids = [r for r in snapshot.all_sources if r.identity.scope == 'Genel'
                    and general_topic_id is not None and r.identity.row_id == int(general_topic_id)]
    options = tuple(sorted({x.identity.key for x in [*candidates, *possible_ids]}))
    if possible_ids and topic_key(possible_ids[0].name) != key:
        return LegacyResolution('name_changed_review', None, options,
                                'Konu ID ve tarihsel ad uyuşmuyor; eski adı otomatik güncelleme.')
    if general_topic_id is not None and not possible_ids:
        return LegacyResolution('mismatch', None, options, 'Genel konu ID bu derste bulunamadı.')
    if not candidates:
        return LegacyResolution('missing', None, options, 'Kayıtlı ada karşılık gelen konu bulunamadı.')
    if len(candidates) != 1 or key in snapshot.ambiguous_keys:
        return LegacyResolution('ambiguous', None, options, 'Aynı ad birden fazla kapsamda mevcut; otomatik eşleştirilmedi.')
    if general_topic_id is not None and candidates[0].identity != possible_ids[0].identity:
        return LegacyResolution('mismatch', None, options, 'Tarihsel ID seçilen konu kaydıyla uyuşmuyor.')
    return LegacyResolution('unique', candidates[0], options, 'Aynı isimli tek konu kaydı doğrulandı.')
