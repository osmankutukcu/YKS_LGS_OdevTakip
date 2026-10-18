# -*- coding: utf-8 -*-
"""V12.7: opt-in, allowlisted public educational web source checks.

No learner data, cookies, credentials, user-entered URLs or queries go to these sites.
A changed page is *not* a verified educational fact; human review is required.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from uuid import uuid4

SOURCES = {
    'ogm': {
        'name':'OGM Materyal',
        'url':'https://ogmmateryal.eba.gov.tr/',
        'category':'pedagogy',
        'description':'Ders kitapları, soru bankaları, öğretmen ve YKS materyalleri',
    },
    'mebi': {
        'name':'MEBİ',
        'url':'https://mebi.eba.gov.tr/',
        'category':'planning',
        'description':'MEB bireysel öğrenme ve sınava hazırlık kaynakları',
    },
    'osym': {
        'name':'ÖSYM Sınav Soru ve Cevapları',
        'url':'https://www.osym.gov.tr/sinav-soru-ve-cevaplari',
        'category':'assessment',
        'description':'Yayımlanan resmî sınav soru ve cevap duyuruları',
    },
}
MAX_DOWNLOAD = 350_000
MAX_CACHE_FILE = 110_000


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def catalog_entry(source_id):
    if not isinstance(source_id,str) or source_id not in SOURCES:
        raise ValueError('Resmî kaynak listesinde bulunmuyor')
    entry = SOURCES[source_id]
    parts = urlsplit(entry['url'])
    if (parts.scheme != 'https' or not parts.hostname or parts.username or parts.password
        or parts.port is not None or parts.query or parts.fragment
        or parts.hostname not in {'ogmmateryal.eba.gov.tr','mebi.eba.gov.tr','www.osym.gov.tr'}):
        raise ValueError('Güvenli kaynak bağlantısı değil')
    return entry


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_fixed_public_page(url):
    """Fetch fixed catalog URLs only; no redirects, no external query, max bytes."""
    if url not in (entry['url'] for entry in SOURCES.values()):
        raise ValueError('Katalog dışı URL indirilemez')
    req = Request(url, headers={
        'User-Agent':'EduTrack-OfficialSourceCheck/12.7 (manual public page metadata)',
        'Accept':'text/html',
        'Accept-Encoding':'identity',
    }, method='GET')
    try:
        with build_opener(NoRedirect()).open(req, timeout=6) as response:
            if response.geturl() != url:
                raise ValueError('Bağlantı beklenmedik adrese yönlendi')
            headers = dict(response.headers.items())
            clen = response.headers.get('Content-Length')
            if clen and int(clen)>MAX_DOWNLOAD:
                raise ValueError('Kaynak sayfa indirme sınırını aşıyor')
            payload = response.read(MAX_DOWNLOAD+1)
    except (HTTPError,URLError,TimeoutError,OSError) as exc:
        raise ConnectionError('Resmî siteye ulaşılamadı veya yönlendirme reddedildi') from exc
    if len(payload)>MAX_DOWNLOAD:
        raise ValueError('Resmî kaynak sayfası sınırı aşıyor')
    return payload,headers


class PublicTextParser(HTMLParser):
    SKIP={'script','style','noscript','iframe','svg','form','nav','footer'}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ignore=[]
        self.in_title=0
        self.title=[]
        self.parts=[]
        self.meta={}
        self.count=0
    def handle_starttag(self,tag,attrs):
        tag=tag.lower()
        if tag in self.SKIP:self.ignore.append(tag)
        if tag=='title':self.in_title+=1
        if tag=='meta':
            a=dict(attrs)
            key=(a.get('property') or a.get('name') or '').strip().lower()
            if key in ('article:published_time','datepublished','pubdate','dc.date','citation_date','date'):
                self.meta[key]=a.get('content','')[:80]
    def handle_endtag(self,tag):
        tag=tag.lower()
        if tag in self.SKIP and tag in self.ignore:
            self.ignore.remove(tag)
        if tag=='title' and self.in_title:self.in_title-=1
    def handle_data(self,text):
        if self.ignore:return
        txt=' '.join(text.split())
        if not txt:return
        if self.in_title:
            self.title.append(txt[:150])
        elif self.count<2500:
            self.parts.append(txt[:400]); self.count+=len(txt)


def check_source(source_id, fetcher=None, checked_at=None):
    """Returns a small informational snapshot, never an accepted coaching guideline."""
    source=catalog_entry(source_id)
    raw,headers=(fetcher or fetch_fixed_public_page)(source['url'])
    if not isinstance(raw,bytes) or len(raw)>MAX_DOWNLOAD:
        raise ValueError('Geçersiz veya çok büyük web yanıtı')
    content_type=next((str(v) for k,v in headers.items() if str(k).lower()=='content-type'),'').lower()
    if 'text/html' not in content_type:
        raise ValueError('Kaynak HTML sayfası olarak okunamadı')
    parser=PublicTextParser()
    parser.feed(raw.decode('utf-8','replace'))
    title=' '.join(parser.title).strip()[:180] or source['name']
    # Preview is a small, untrusted excerpt for manual teacher review only.
    excerpt=' '.join(parser.parts).strip()[:800]
    if not excerpt:
        raise ValueError('İncelenebilir sayfa metni yok')
    declared=''
    for key in ('article:published_time','datepublished','pubdate','citation_date','dc.date','date'):
        value=parser.meta.get(key,'')
        if re.match(r'^\d{4}-\d{2}-\d{2}',value):
            declared=value[:10]
            break
    return {
        'source_id':source_id,
        'url':source['url'],
        'title':title,
        'excerpt':excerpt,
        'checked_at':checked_at or utcnow(),
        'declared_publish_date':declared or None,
        'http_last_modified':next((str(v)[:90] for k,v in headers.items() if str(k).lower()=='last-modified'),None),
        'sha256':hashlib.sha256(raw).hexdigest(),
        'verified_science':False,
        'automatic_action_allowed':False,
    }


def default_cache_path():
    from services.coach_assistant_v1.knowledge_manager_v126 import default_store_path
    return default_store_path().with_name('coach_official_source_checks_v127.json')


class SourceCache:
    def __init__(self,path=None):
        self.path=Path(path) if path else default_cache_path()

    def read(self):
        if not self.path.exists():return {'schema_version':'1.0','checks':{}}
        if self.path.stat().st_size>MAX_CACHE_FILE:raise ValueError('Kaynak önbelleği boyut sınırını aştı')
        data=json.loads(self.path.read_text(encoding='utf-8'))
        if not isinstance(data,dict) or data.get('schema_version')!='1.0' or not isinstance(data.get('checks'),dict):
            raise ValueError('Kaynak önbelleği geçersiz')
        if set(data['checks'])-set(SOURCES):
            raise ValueError('Kaynak önbelleğinde bilinmeyen site var')
        return data

    def get(self,source_id):
        catalog_entry(source_id)
        return self.read()['checks'].get(source_id)

    def put(self,record):
        sid=record.get('source_id')
        canonical=catalog_entry(sid)
        if record.get('url')!=canonical['url'] or record.get('automatic_action_allowed') is not False:
            raise ValueError('Kaynak kimliği uyuşmuyor')
        data=self.read()
        old=data['checks'].get(sid)
        record=record.copy()
        record['change_status']=('first_check' if old is None else
                                 'changed' if old.get('sha256')!=record.get('sha256') else 'unchanged')
        data['checks'][sid]=record
        content=(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
        if len(content)>MAX_CACHE_FILE:raise ValueError('Önbellek doldu')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=None
        try:
            fd,tmp=tempfile.mkstemp(prefix='.source_check_',dir=self.path.parent)
            with os.fdopen(fd,'wb') as f:
                f.write(content);f.flush();os.fsync(f.fileno())
            os.replace(tmp,self.path)
        finally:
            if tmp:Path(tmp).unlink(missing_ok=True)
        return record
