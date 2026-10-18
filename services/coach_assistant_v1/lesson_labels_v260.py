# -*- coding: utf-8 -*-
"""Pure presentation aliases used by Coach Assistant; no Qt dependency."""
from __future__ import annotations

_LESSON_LABELS = {
    'tyt_turkce': 'TYT Türkçe',
    'tyt_matematik': 'TYT Matematik',
    'ayt_matematik': 'AYT Matematik',
    'tyt_geometri': 'TYT Geometri',
    'ayt_geometri': 'AYT Geometri',
    'geometri': 'Geometri',
    'tyt_fizik': 'TYT Fizik',
    'ayt_fizik': 'AYT Fizik',
    'fizik': 'Fizik',
    'tyt_kimya': 'TYT Kimya',
    'ayt_kimya': 'AYT Kimya',
    'kimya': 'Kimya',
    'tyt_biyoloji': 'TYT Biyoloji',
    'ayt_biyoloji': 'AYT Biyoloji',
    'biyoloji': 'Biyoloji',
    'tyt_tarih': 'TYT Tarih',
    'ayt_tarih': 'AYT Tarih',
    'tarih': 'Tarih',
    'tyt_cografya': 'TYT Coğrafya',
    'ayt_cografya': 'AYT Coğrafya',
    'cografya': 'Coğrafya',
    'tyt_felsefe': 'TYT Felsefe',
    'felsefe': 'Felsefe',
    'tyt_din': 'TYT Din Kültürü',
    'din_kulturu': 'Din Kültürü',
    'ayt_edebiyat': 'AYT Edebiyat',
    'edebiyat': 'Edebiyat',
    'lgs_turkce': 'LGS Türkçe',
    'lgs_matematik': 'LGS Matematik',
    'lgs_fen': 'LGS Fen Bilimleri',
    'lgs_inkilap': 'LGS İnkılap Tarihi',
    'lgs_ingilizce': 'LGS İngilizce',
    'lgs_din': 'LGS Din Kültürü',
    'turkce': 'Türkçe',
    'matematik': 'Matematik',
}


def format_lesson_name(raw: str) -> str:
    text = str(raw or '').strip()
    if not text:
        return ''
    key = text.casefold().replace(' ', '_').replace('-', '_')
    if key in _LESSON_LABELS:
        return _LESSON_LABELS[key]
    if '_' in text:
        parts = text.split('_')
        out = []
        for p in parts:
            low = p.casefold()
            if low in ('tyt', 'ayt', 'lgs', 'ydt'):
                out.append(low.upper())
            else:
                out.append(p.capitalize())
        return ' '.join(out)
    return text


def format_action_title(raw_title: str) -> tuple[str, str]:
    """Return (lesson_badge, topic_title) from 'ayt_matematik / Eşitsizlikler' or plain title."""
    text = str(raw_title or '').strip()
    if ' / ' in text:
        left, right = text.split(' / ', 1)
        return format_lesson_name(left), right.strip()
    return '', text

