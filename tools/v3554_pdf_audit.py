# -*- coding: utf-8 -*-
"""V3.5.54: read-only check of exported mobile PDF links and page integrity.

The auditor is an acceptance tool, NOT a guarantee that WhatsApp, phone or
calendar applications will open on a physical device. PyMuPDF is a QA-only
requirement; the desktop PDF exporter itself needs only ReportLab.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from urllib.parse import urlsplit, parse_qs


def check_uri(uri: str, approved_https_origins=()):
    """Return a non-sensitive rejection code or None for permitted actions."""
    if not isinstance(uri, str) or not uri or len(uri) > 24000:
        return 'MALFORMED_URI'
    try:
        parts = urlsplit(uri)
        if parts.username or parts.password or parts.fragment:
            return 'UNSAFE_URI_COMPONENT'
        if parts.scheme == 'tel':
            return None if re.fullmatch(r'\+?[1-9][0-9]{7,14}', parts.path) and not parts.query else 'INVALID_PHONE_LINK'
        if parts.scheme != 'https':
            return 'DISALLOWED_SCHEME'
        if parts.hostname == 'wa.me' and parts.port is None:
            query = parse_qs(parts.query, keep_blank_values=True)
            if re.fullmatch(r'/[1-9][0-9]{7,14}', parts.path) and set(query) == {'text'} and len(query['text']) == 1 and query['text'][0].strip():
                return None
            return 'INVALID_WHATSAPP_LINK'
        if parts.hostname == 'calendar.google.com' and parts.port is None:
            if parts.path == '/calendar/render' and parse_qs(parts.query).get('action') == ['TEMPLATE']:
                return None
            return 'INVALID_CALENDAR_LINK'
        origin = f'{parts.scheme}://{parts.netloc}'
        if origin in approved_https_origins and parts.path.startswith(('/academic/', '/mobile/', '/feedback/')):
            return None
        return 'UNAPPROVED_EXTERNAL_HOST'
    except (ValueError, TypeError):
        return 'INVALID_URI'


def audit_pdf(path, *, approved_https_origins=()):
    """Return structured, privacy-safe results without changing PDF bytes."""
    import fitz  # installed for CI testing, not required by desktop application
    result = {'status': 'PASS', 'pages': 0, 'links': 0, 'external_links': 0, 'issues': []}
    file_path = Path(path)
    if not file_path.is_file():
        return {**result, 'status': 'BLOCK', 'issues': ['PDF_MISSING']}
    try:
        with fitz.open(file_path) as doc:
            if doc.is_encrypted or doc.page_count < 1:
                result['issues'].append('PDF_ENCRYPTED_OR_EMPTY')
            result['pages'] = doc.page_count
            for xref in range(1, doc.xref_length()):
                object_text = doc.xref_object(xref)
                if '/JavaScript' in object_text or '/Launch' in object_text:
                    result['issues'].append('EMBEDDED_ACTIVE_ACTION')
                    break
            for page in doc:
                if not page.get_text().strip():
                    result['issues'].append('BLANK_PAGE')
                for link in page.get_links():
                    result['links'] += 1
                    bounds = link.get('from')
                    if bounds is None or bounds.is_empty or not page.rect.contains(bounds):
                        result['issues'].append('LINK_OUTSIDE_PAGE')
                    kind = link.get('kind')
                    if kind == fitz.LINK_GOTO:
                        if not isinstance(link.get('page'), int) or not 0 <= link['page'] < doc.page_count:
                            result['issues'].append('INVALID_PAGE_DESTINATION')
                    elif kind == fitz.LINK_URI:
                        result['external_links'] += 1
                        problem = check_uri(link.get('uri'), approved_https_origins)
                        if problem:
                            result['issues'].append(problem)
                    else:
                        result['issues'].append('UNSUPPORTED_LINK_ACTION')
            result['issues'] = sorted(set(result['issues']))
    except Exception:
        result['issues'].append('UNREADABLE_PDF')
    result['status'] = 'BLOCK' if result['issues'] else 'PASS'
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description='Salt okunur Akıllı Mobil PDF güvenlik kontrolü')
    parser.add_argument('pdf', type=Path)
    parser.add_argument('--allow-live-origin', action='append', default=[])
    ns = parser.parse_args(argv)
    outcome = audit_pdf(ns.pdf, approved_https_origins=tuple(ns.allow_live_origin))
    print(json.dumps(outcome, indent=2))
    return 0 if outcome['status'] == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
