"""V7 conservative learning-outcome crosswalk and read-only remediation draft.

Only exact, same-grade reviewed aliases may match. Subject-level trial exam
scores cannot identify a learning outcome, so they are never used as proof.
No network, data writes, automatic assignment, or learning diagnoses.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from datetime import date
from html import escape
from pathlib import Path
from urllib.parse import urlparse

from services.coach_evidence_v5 import _assignment_rows, _columns, _norm, DONE

CATALOG_PATH = Path(__file__).resolve().parent.parent / 'assets' / 'coach_curriculum_v7.json'
APPROVED_DOMAINS = {'tymm.meb.gov.tr', 'mufredat.meb.gov.tr', 'ttkbyayin.meb.gov.tr'}
MAX_ITEMS = 12000


def _key(raw):
    # Turkish I/i behavior must not collapse semantically distinct words.
    value = unicodedata.normalize('NFKC', str(raw or '')).strip().translate(str.maketrans({'İ':'i', 'I':'ı'})).casefold()
    return ' '.join(value.split())


def _source_is_official(url):
    try:
        p = urlparse(url)
        return (p.scheme == 'https' and p.hostname in APPROVED_DOMAINS
                and p.username is None and p.password is None and p.port in (None, 443)
                and not p.fragment and bool(p.path))
    except (TypeError, ValueError):
        return False


def load_catalog(path=None):
    """Read curated examples; reject invalid/unreviewed catalogues wholesale."""
    source = Path(path) if path else CATALOG_PATH
    if source.stat().st_size > 3_000_000:
        raise ValueError('Kazanım kataloğu için dosya boyutu sınırı aşıldı.')
    with source.open('r', encoding='utf-8') as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict) or payload.get('schema_version') != 1:
        raise ValueError('Kazanım katalog biçimi geçersiz.')
    rows = payload.get('outcomes')
    if not isinstance(rows, list) or len(rows) > MAX_ITEMS:
        raise ValueError('Kazanım sayısı geçersiz.')
    seen = set()
    checked = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Kazanım kaydı geçersiz.')
        subject = str(row.get('subject') or '').strip()
        try:
            grade = int(row.get('grade'))
        except (ValueError, TypeError, OverflowError):
            raise ValueError('Geçersiz sınıf düzeyi.') from None
        code = str(row.get('code') or '').strip()
        title = str(row.get('outcome') or '').strip()
        url = str(row.get('source_url') or '').strip()
        topic_aliases = row.get('topic_aliases')
        if (not subject or not 1 <= grade <= 12 or not code or not title
                or len(code) > 70 or len(title) > 320 or len(subject) > 100
                or not _source_is_official(url)
                or row.get('review_status') not in ('official_excerpt', 'teacher_confirmed')
                or not isinstance(topic_aliases, list) or not topic_aliases
                or len(topic_aliases) > 15
                or any(not isinstance(a, str) or not a.strip() or len(a) > 160 for a in topic_aliases)):
            raise ValueError(f'Doğrulanamayan kazanım katalog kaydı: {code[:70]}')
        identifier = (_key(subject), grade, _key(code))
        if identifier in seen:
            raise ValueError('Tekrarlanan kazanım kodu: ' + code)
        seen.add(identifier)
        checked.append({'subject': subject, 'grade': grade, 'code': code, 'outcome': title,
                        'source_url': url, 'review_status': row['review_status'],
                        'topic_aliases': topic_aliases})
    return checked


def detect_grade(student):
    """Do not guess from exam track alone (YKS, LGS, Mezun, etc.)."""
    raw = str(student.get('alt_grup') or '').strip()
    if not raw or 'mezun' in _key(raw):
        return None
    m = re.match(r'^\s*(?P<grade>1[0-2]|[1-9])(?=\s|[.\-–/]|$)', raw)
    return int(m['grade']) if m else None


SUBJECT_CANONICAL = {
    'tyt matematik': 'matematik',
    'ayt matematik': 'matematik',
    'tyt_matematik': 'matematik',
    'ayt_matematik': 'matematik',
    'matematik': 'matematik',
    'geometri': 'matematik',
    'problemler': 'matematik',
    'tyt fizik': 'fizik',
    'ayt fizik': 'fizik',
    'fizik': 'fizik',
    'tyt kimya': 'kimya',
    'ayt kimya': 'kimya',
    'kimya': 'kimya',
    'tyt biyoloji': 'biyoloji',
    'ayt biyoloji': 'biyoloji',
    'biyoloji': 'biyoloji',
    'turkce': 'türkçe',
    'türkçe': 'türkçe',
    'tyt turkce': 'türkçe',
    'tyt türkçe': 'türkçe',
    'paragraf': 'türkçe',
    'edebiyat': 'türk dili ve edebiyatı',
    'türk dili ve edebiyatı': 'türk dili ve edebiyatı',
    'ayt edebiyat': 'türk dili ve edebiyatı',
    'tarih': 'tarih',
    'ayt tarih': 'tarih',
    'tyt tarih': 'tarih',
    'cografya': 'coğrafya',
    'coğrafya': 'coğrafya',
    'tyt cografya': 'coğrafya',
    'ayt cografya': 'coğrafya',
    'felsefe': 'felsefe',
    'tyt felsefe': 'felsefe',
    'ayt felsefe': 'felsefe',
}


def exact_outcome(subject, topic, grade, catalog):
    if grade is None or not _key(topic) or not _key(subject):
        return None
    k_subj = ' '.join(_key(subject).replace('_', ' ').split())
    canon_subj = SUBJECT_CANONICAL.get(k_subj, k_subj)
    allowed_subjects = {_key(subject), k_subj, canon_subj}
    options = [v for v in catalog
               if v['grade'] == grade and _key(v['subject']) in allowed_subjects
               and _key(topic) in {_key(k) for k in v['topic_aliases']}]
    # Multiple matches are ambiguous, not auto-decided.
    return options[0] if len(options) == 1 else None


def _safe_score(raw):
    try:
        score = float(raw)
        return score if 0 < score <= 100 and score == score else None
    except (TypeError, ValueError, OverflowError):
        return None


def build_outcome_review(con, student_id, *, as_of=None, catalog=None,
                         max_minutes=75, max_items=4, grade_override=None):
    today = as_of or date.today()
    if max_minutes < 0 or max_items < 0:
        raise ValueError('Süre ve işlem sınırı negatif olamaz.')
    if catalog is None:
        catalog = load_catalog()
    sc = _columns(con, 'ogrenci')
    if not {'id','ad','soyad'} <= sc:
        raise ValueError('Öğrenci tablosu eksik.')
    group_sql = 'alt_grup' if 'alt_grup' in sc else 'NULL AS alt_grup'
    student = con.execute(f'SELECT id,ad,soyad,{group_sql} FROM ogrenci WHERE id=?',
                          (student_id,)).fetchone()
    if student is None:
        raise ValueError('Öğrenci bulunamadı.')
    grade = detect_grade(dict(student))
    if grade_override is not None:
        if type(grade_override) is not int or not 1 <= grade_override <= 12:
            raise ValueError('Öğretmenin seçtiği sınıf geçersiz.')
        grade = grade_override
    rows, stats = _assignment_rows(con, student_id)
    notices = ['Deneme ders toplamlarından soru/kazanım hatası çıkarılamaz.']
    if grade_override is not None:
        notices.append('Sınıf öğretmen tarafından yalnızca bu önizleme için seçildi; öğrenci kaydı değiştirilmedi.')
    if grade is None:
        notices.append('Öğrencinin sınıfı kesin belirlenemedi; hiçbir kazanım otomatik eşleştirilmedi.')
    if not catalog:
        notices.append('Doğrulanmış kazanım kataloğu boş.')
    grouped = defaultdict(list)
    unresolved = set()
    for r in rows:
        if not r['ders'] or not r['konu']:
            continue
        target = exact_outcome(r['ders'], r['konu'], grade, catalog)
        if not target:
            unresolved.add((_key(r['ders']), _key(r['konu'])))
            continue
        grouped[target['code']].append((target, r))

    # Only explicitly stored 0<score<=100 is a usable teacher-rated signal.
    # Legacy 'durum=2' or a mere completed homework does not mean mastery.
    ratings = defaultdict(list)
    general_ratings = {}
    cols = _columns(con, 'koc_konu_takip')
    if {'ogrenci_id','ders_adi','konu_adi','hakimiyet_puani'} <= cols:
        fields = 'ders_adi,konu_adi,hakimiyet_puani'
        if 'updated_at' in cols:
            fields += ',updated_at'
        for r in con.execute(f'SELECT {fields} FROM koc_konu_takip WHERE ogrenci_id=?', (student_id,)):
            rd = dict(r)
            val = _safe_score(rd.get('hakimiyet_puani'))
            if val is None:
                continue
            updated = rd.get('updated_at')
            if updated is not None:
                try:
                    logged = date.fromisoformat(str(updated)[:10])
                except ValueError:
                    continue
                if (today - logged).days < 0 or (today - logged).days > 90:
                    continue
            target = exact_outcome(rd['ders_adi'],rd['konu_adi'],grade,catalog)
            if target:
                ratings[target['code']].append((val, target))
            elif val <= 50 and rd.get('ders_adi') and rd.get('konu_adi'):
                key = (_key(rd['ders_adi']), _key(rd['konu_adi']))
                old = general_ratings.get(key)
                if old is None or val < old['score']:
                    general_ratings[key] = {'subject':str(rd['ders_adi']),
                        'topic':str(rd['konu_adi']), 'score':val}

    # Include teacher-rated outcomes even when no homework has been assigned yet.
    # A dated direct teacher observation is stronger than absence of homework.
    for code, observations in ratings.items():
        if code not in grouped and observations:
            grouped[code] = [(observations[0][1], None)]

    suggestions = []
    remain = int(max_minutes)
    for code, entries in grouped.items():
        target = entries[0][0]
        open_rows = [r for _, r in entries if r is not None and r['durum'] not in DONE]
        late = [r for r in open_rows if r['due'] and r['due'] < today]
        completed = sum(1 for _, r in entries if r is not None and r['durum'] in DONE)
        vals = [x[0] for x in ratings.get(code, [])]
        weak_rating = min(vals) if vals else None
        if late:
            kind, reason, minutes = ('overdue_check',
                f'{len(late)} süresi geçmiş açık ödev kaydı; tamamlanma durumunu öğretmen kontrol etmeli.', 0)
        elif weak_rating is not None and weak_rating <= 50:
            kind, reason, minutes = ('teacher_review',
                f'Kayıtlı öğretmen konu puanı {weak_rating:g}/100; ölçümü güncellemek için kısa kontrol önerilir.', 20)
        elif open_rows:
            kind, reason, minutes = ('pending_check',
                f'{len(open_rows)} açık ödev bulunuyor; telafiye karar vermeden önce ödev kontrolü yapın.', 0)
        elif completed:
            kind, reason, minutes = ('retention_check',
                'Tamamlanmış ödev kanıtı var; kalıcılık ölçülmedi. Kısa hatırlama kontrolü yapılabilir.', 15)
        else:
            continue
        if minutes > remain or len(suggestions) >= max_items:
            continue
        suggestions.append({'type':kind, 'code':code,'subject':target['subject'],
            'grade':target['grade'],'outcome':target['outcome'],
            'evidence':reason,'minutes':minutes,'source_url':target['source_url'],
            'source_status':target['review_status'], 'approval_required':True,
            'action':('Öğretmen ödev durumunu kontrol etsin.' if minutes == 0 else
                      'Öğretmen kısa bir konu ölçmesi yapıp sonuca göre telafi kararı versin.')})
        remain -= minutes
    suggestions.sort(key=lambda x:({'overdue_check':0,'teacher_review':1,
                                   'pending_check':2,'retention_check':3}[x['type']], x['subject']))
    # Separate unlinked teacher observations; no claim of official outcome match.
    general_actions = []
    for item in sorted(general_ratings.values(), key=lambda r:(r['score'], _key(r['subject']))):
        if len(suggestions) + len(general_actions) >= max_items or remain < 20:
            break
        general_actions.append({'subject':item['subject'], 'topic':item['topic'],
              'score':item['score'], 'minutes':20, 'approval_required':True,
              'evidence':f'Kayıtlı öğretmen konu puanı {item["score"]:g}/100',
              'action':'Kısa yeniden ölçme; sonucuna göre telafi kararı.',
              'source_status':'no_official_match'})
        remain -= 20
    result = {'student_id':int(student_id),'grade':grade, 'as_of':today.isoformat(),
              'mapped_topics':len(grouped),'unmapped_topics':len(unresolved),
              'mirrored':stats['mirrored'], 'catalog_total':len(catalog),
              'actions':suggestions, 'general_actions':general_actions,
              'total_minutes':sum(x['minutes'] for x in suggestions + general_actions),
              'warnings':notices, 'write_performed':False,
              'limitations':'Katalog kısmi; ders bazlı netler kazanım kanıtı değildir; taslak öğretmen onayına tabidir.'}
    if unresolved:
        result['warnings'].append(f'{len(unresolved)} konu için sınıf/ders/kazanım düzeyinde tekil doğrulanmış eşleşme bulunamadı.')
    if not suggestions:
        result['warnings'].append('Bu öğrenci için resmî kazanımla eşleşen telafi taslağı oluşmadı.')
    if general_actions:
        result['warnings'].append('Bazı konu değerlendirmeleri resmî kazanımla eşleşmedi; yalnızca öğretmen kayıtlı kısa ölçme önerisidir.')
    return result


def outcome_as_html(report):
    e = lambda s: escape(str(s or ''),quote=True)
    header = (f'<h3>Doğrulanmış kazanım kontrolleri</h3><p>Sınıf: {e(report["grade"] or "belirsiz")} · '
              f'Eşleşen: {report["mapped_topics"]} · Eşleşmeyen: {report["unmapped_topics"]} · '
              f'Tahmini kısa kontrol: {report["total_minutes"]} dk</p>')
    items = []
    for action in report['actions']:
        items.append(f'<li><b>{e(action["subject"])} – {e(action["code"])}</b>: '
                     f'{e(action["outcome"])}<br/> '
                     f'{e(action["evidence"])}<br/>'
                     f'<em>{e(action["action"])} ({action["minutes"]} dk)</em> '
                     f'· <a href="{e(action["source_url"])}">Resmî kaynak</a></li>')
    generic = ''.join(f'<li><b>{e(x["subject"])} – {e(x["topic"])}</b>: '
              f'{e(x["evidence"])}; {e(x["action"])} ({x["minutes"]} dk)</li>'
              for x in report.get('general_actions', []))
    warnings = ''.join(f'<li>{e(x)}</li>' for x in report['warnings'])
    return (header + '<ol>' + ''.join(items) + '</ol>'
            + ('<b>Resmî eşleşmesi olmayan öğretmen kontrolleri</b><ul>'+generic+'</ul>' if generic else '')
            + '<b>Veri sınırları</b><ul>'
            + warnings + '</ul><small>Hiçbir ödev ve öğrenci kaydı değiştirilmedi.</small>')


def outcome_as_text(report):
    lines = [f'KAZANIM/TELAFİ KONTROL TASLAĞI – {report["as_of"]}',
             f'Sınıf: {report["grade"] or "belirsiz"}',
             f'Önerilen kısa kontrol toplamı: {report["total_minutes"]} dk']
    for item in report['actions']:
        lines.append(f'- {item["subject"]} / {item["code"]}: {item["action"]} '
                     f'({item["minutes"]} dk) | {item["evidence"]} | {item["source_url"]}')
    for item in report.get('general_actions', []):
        lines.append(f'- Kazanım eşleşmesi yok: {item["subject"]} / {item["topic"]}: '
                     f'{item["action"]} ({item["minutes"]} dk); {item["evidence"]}')
    lines.extend('UYARI: ' + x for x in report['warnings'])
    return '\n'.join(lines)
