# -*- coding: utf-8 -*-
"""Read-only, locally curated coaching knowledge for Koça Sor (V12.5).

No database writes, network calls, web requests, hidden student scoring, or automatic
assignment. This library is guidance; live student data still comes from existing
Student360/Adaptive Coach readers. Unreviewed draft records are never searchable.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
import unicodedata
from pathlib import Path
from typing import Optional

ALLOWED_CATEGORIES = frozenset({
    'coaching', 'error_analysis', 'assessment', 'homework', 'planning',
    'learning_science', 'curriculum', 'pedagogy', 'student_support', 'methodology',
})
MAX_LIBRARY_BYTES = 1_000_000
MAX_ENTRIES = 600
DEFAULT_LIBRARY_PATH = Path(__file__).resolve().parents[2] / 'assets' / 'coach_knowledge_v125.json'


def _fold(text: str) -> str:
    text = str(text or '').replace('ı', 'i').replace('İ', 'I')
    text = unicodedata.normalize('NFKD', text.casefold())
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return ' '.join(re.findall(r'[a-z0-9]+', text))


@dataclass(frozen=True)
class KnowledgeMatch:
    entry_id: str
    title: str
    category: str
    guidance: str
    teacher_question: str
    source: str
    caution: str
    score: int


class KnowledgeBank:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path is not None else DEFAULT_LIBRARY_PATH
        self._cache_key = None
        self._entries = ()
        self._source_names = {}

    def _refresh(self):
        info = self.path.stat()
        if info.st_size > MAX_LIBRARY_BYTES:
            raise ValueError('Koçluk bilgi dosyası boyut sınırını aşıyor')
        key = (info.st_mtime_ns, info.st_size)
        if self._cache_key == key:
            return
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if data.get('schema_version') != '1.0' or not isinstance(data.get('entries'), list):
            raise ValueError('Bilinmeyen koçluk kütüphanesi şeması')
        if len(data['entries']) > MAX_ENTRIES:
            raise ValueError('Koçluk kütüphanesi kayıt sınırını aşıyor')
        source_names = {s['id']: s['title'] for s in data.get('sources', [])
                        if isinstance(s, dict) and isinstance(s.get('id'), str)
                        and isinstance(s.get('title'), str)}
        prepared = []
        seen_ids = set()
        for item in data['entries']:
            if not isinstance(item, dict):
                raise ValueError('Geçersiz kütüphane kaydı')
            key_id = item.get('id')
            if not isinstance(key_id, str) or not re.fullmatch(r'[a-z0-9_\-]{3,70}', key_id) or key_id in seen_ids:
                raise ValueError('Geçersiz/tekrarlı bilgi kimliği')
            seen_ids.add(key_id)
            if item.get('status') != 'approved_pilot':
                continue  # Drafts and unverified remote sources never become live advice.
            if item.get('category') not in ALLOWED_CATEGORIES or item.get('automatic_action_allowed') is not False:
                raise ValueError('Onaysız kategori veya otomatik eylem yetkisi')
            for field in ('title','guidance','teacher_question','source_section'):
                if not isinstance(item.get(field), str) or not item[field].strip() or len(item[field]) > 1200:
                    raise ValueError('Hatalı bilgi alanı: '+field)
            if not isinstance(item.get('keywords'), list) or not all(isinstance(k, str) for k in item['keywords']):
                raise ValueError('Geçersiz anahtar sözcük listesi')
            if not item.get('source_ids') or not all(s in source_names for s in item['source_ids']):
                raise ValueError('Kaynağı belirsiz koçluk bilgisi')
            prepared.append(item)
        self._entries = tuple(prepared)
        self._source_names = source_names
        self._cache_key = key

    def search(self, query: str, *, limit: int = 2, allow_sensitive: bool = False) -> tuple[KnowledgeMatch, ...]:
        self._refresh()
        q = _fold(str(query or '')[:600])
        if len(q) < 4:
            return ()
        # Sensitive self-reports must not be interpreted as ordinary student
        # performance evidence in the compact, generally visible assistant.
        if not allow_sensitive and any(
            token.startswith(word) for token in q.split()
            for word in ('kaygi', 'panik', 'uyku', 'depresyon', 'stres', 'travma')
        ):
            return ()
        results = []
        q_words = set(q.split())
        for e in self._entries:
            if e.get('sensitive') and not allow_sensitive:
                continue
            score = 0
            for keyword in e['keywords']:
                k = _fold(keyword)
                if not k: continue
                if re.search(r'(?<![a-z0-9])'+re.escape(k)+r'(?![a-z0-9])',q):
                    score += 7 + min(len(k.split()),3)
                elif len(k.split()) >= 2 and len(q_words & set(k.split())) >= 2:
                    score += 3
            title_tokens = set(_fold(e['title']).split())
            score += min(len(q_words & title_tokens), 3) * 2
            if score >= 8:
                source = ' / '.join(self._source_names[s] for s in e['source_ids']) + ' — ' + e['source_section']
                results.append(KnowledgeMatch(
                    entry_id=e['id'], title=e['title'], category=e['category'],
                    guidance=e['guidance'], teacher_question=e['teacher_question'],
                    source=source, caution=str(e.get('caution') or ''), score=score,
                ))
        results.sort(key=lambda x: (-x.score, x.entry_id))
        return tuple(results[:max(0,min(int(limit),3))])


def enrich_answer(answer, question: str, *, bank: Optional[KnowledgeBank] = None):
    """Optionally add one transparently sourced *general* tip to a live student answer.

    Works with existing immutable CoachAnswer; no personal data is passed to bank.
    In case there is no relevant source, returns the exact original answer object.
    """
    from services.coach_assistant_v1.dialogue import CoachAnswer
    if not isinstance(answer, CoachAnswer):
        raise TypeError('Koç Asistanı yanıt biçimi bekleniyor')
    bank = bank or KnowledgeBank()
    matches = bank.search(question, limit=1)
    if not matches:
        return answer
    m = matches[0]
    # Keep the pedagogical text distinctly separate from live student observations.
    addition = '\n\n📚 Koçluk bilgi kütüphanesi (genel yöntem; öğrenci teşhisi değildir): '+m.guidance
    addition += '\nGörüşmede sorulabilir: '+m.teacher_question
    if m.caution:
        addition += '\nNot: '+m.caution
    evidence = (*answer.evidence, 'Pedagojik kaynak (öğrenci ölçümü değildir): '+m.source)
    return CoachAnswer(answer.title, answer.message+addition, tuple(evidence), answer.action_target)


def existing_curriculum_tip(topic_name: str, *, app_root: Optional[Path] = None) -> Optional[dict]:
    """Reuse existing curriculum.json, never generate or overwrite a second curriculum.

    Only exact normalized topic matches are accepted. Returns general pre-existing
    tip and optional checklist, not mastery, a student-specific score or an action.
    """
    root = Path(app_root) if app_root is not None else Path(__file__).resolve().parents[2]
    path = root/'assets'/'curriculum.json'
    if not path.exists() or path.stat().st_size > 8_000_000:
        return None
    data = json.loads(path.read_text(encoding='utf-8'))
    topics = data.get('topics', {})
    if not isinstance(topics, dict):
        return None
    requested = _fold(topic_name)
    if len(requested) < 5:
        return None
    hits = [(name, payload) for name,payload in topics.items() if _fold(name)==requested and isinstance(payload, dict)]
    if len(hits) != 1:
        return None
    name,item=hits[0]
    return {'topic':name, 'tip':str(item.get('tip') or '')[:600],
            'coach_tips':[str(x)[:350] for x in item.get('coach_tips', [])[:3]],
            'source':'assets/curriculum.json (mevcut program kaynağı)',
            'verified_current_curriculum':False}
