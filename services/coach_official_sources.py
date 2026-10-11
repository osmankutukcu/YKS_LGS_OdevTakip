"""Opt-in, PII-free official resource metadata check (V6).

Loads only a bounded HTML prefix to show source provenance. Does NOT claim
curriculum-topic validation, download student data or contact an AI API.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler

OFFICIAL_SOURCES = (
    {'name': 'MEB – Türkiye Yüzyılı Maarif Modeli', 'url': 'https://tymm.meb.gov.tr/ogretim-programlari/'},
    {'name': 'MEB – 2026–2027 Ortaöğretim Planları', 'url': 'https://tymm.meb.gov.tr/taslak-cerceve-planlari/ortaogretim'},
    {'name': 'MEB OGM – Eğitim Materyalleri', 'url': 'https://ogmmateryal.eba.gov.tr/'},
    {'name': 'ÖSYM – Sınav Takvimi', 'url': 'https://www.osym.gov.tr/Sayfa/SinavTakvimi/tr-TR'},
)
APPROVED_HOSTS = {'tymm.meb.gov.tr', 'ogmmateryal.eba.gov.tr', 'www.osym.gov.tr'}
MAX_BYTES = 96 * 1024


def _is_allowed(url):
    try:
        parsed = urlparse(url)
        return (parsed.scheme == 'https' and parsed.hostname in APPROVED_HOSTS
                and parsed.username is None and parsed.password is None
                and parsed.port in (None, 443) and not parsed.fragment)
    except ValueError:
        return False


class _StrictRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _is_allowed(newurl):
            raise URLError('İzin verilmeyen yönlendirme')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _TitleParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.inside = False
        self.title = ''

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'title':
            self.inside = True

    def handle_endtag(self, tag):
        if tag.lower() == 'title':
            self.inside = False

    def handle_data(self, data):
        if self.inside and len(self.title) < 200:
            self.title += data[:200]


def inspect_source(url: str, *, timeout: float = 3.0, opener=None) -> dict:
    """Retrieve bounded public metadata, with no student input or custom URLs.

    The optional opener is used in offline unit tests. The URL allowlist is
    enforced both before and after fetching regardless of the opener.
    """
    if not _is_allowed(url):
        raise ValueError('Yalnızca onaylı resmî HTTPS adreslerine erişilir.')
    req = Request(url, headers={'User-Agent': 'EduTrackCoachOfficialCheck/2.0',
                                'Accept': 'text/html'}, method='GET')
    client = opener or build_opener(_StrictRedirect())
    with client.open(req, timeout=timeout) as response:
        final = response.geturl()
        if not _is_allowed(final):
            raise ValueError('Kaynak izin verilmeyen adrese yönlendirdi.')
        ok = 200 <= response.status < 300
        mime = response.headers.get('Content-Type', '').split(';', 1)[0].lower().strip()
        if not ok or mime not in ('text/html', 'application/xhtml+xml'):
            return {'reachable': bool(ok), 'title': None, 'sample_sha256': None,
                    'http_status': response.status, 'content_checked': False,
                    'status': 'Sayfa erişilebilir; HTML başlığı doğrulanamadı.' if ok else 'HTTP hata yanıtı.'}
        prefix = response.read(MAX_BYTES)
        parser = _TitleParser()
        parser.feed(prefix.decode('utf-8', errors='replace'))
        title = ' '.join(parser.title.split())[:160] or None
        return {'reachable': True, 'title': title, 'sample_sha256': sha256(prefix).hexdigest(),
                'http_status': response.status, 'content_checked': bool(title),
                'status': 'Başlık okundu; konu/kazanım eşleştirmesi yapılmadı.' if title else 'Bağlantı açık, başlık okunamadı.'}


def check_source(url: str, *, timeout: float = 3.0) -> bool:
    return bool(inspect_source(url, timeout=timeout)['reachable'])


def check_official_sources() -> list[dict]:
    results = []
    for source in OFFICIAL_SOURCES:
        now = datetime.now(timezone.utc).isoformat(timespec='seconds')
        try:
            result = inspect_source(source['url'])
        except (OSError, ValueError, HTTPError, URLError) as exc:
            result = {'reachable': False, 'title': None, 'content_checked': False,
                      'sample_sha256': None, 'http_status': None,
                      'status': f'Kaynağa erişilemedi ({type(exc).__name__})'}
        results.append({**source, **result, 'checked_at': now})
    return results
