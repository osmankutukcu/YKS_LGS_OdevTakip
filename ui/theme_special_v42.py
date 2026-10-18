# -*- coding: utf-8 -*-
"""V42: Qt-free color tokens for locally painted timelines and table delegates.

Only visual values. Never changes data, events, reports or persistence.
"""
from ui.theme import _mix, _luminance, contrast_ratio, _contrast_safe_background, readable_text
from ui.theme_tokens_v37 import semantic_palette


def legible_accent(background, preferred, target=4.5):
    """Shift an accent toward black/white without discarding its original hue."""
    if contrast_ratio(background, preferred) >= target:
        return preferred
    end = '#FFFFFF' if _luminance(background) < 0.18 else '#000000'
    for n in range(1, 101):
        color = _mix(preferred, end, n / 100)
        if contrast_ratio(background, color) >= target:
            return color
    return end


def timeline_colors():
    c = semantic_palette()
    surface = c['surface']
    dark = c['dark']
    school = ('#7F1D1D', '#991B1B') if dark else ('#FECACA', '#FEE2E2')
    course = ('#7C2D12', '#9A3412') if dark else ('#FED7AA', '#FFEDD5')
    return {
        'surface': surface, 'text': c['surface_fg'],
        'muted': legible_accent(surface, '#94A3B8' if dark else '#64748B'),
        'capacity': legible_accent(surface, '#34D399' if dark else '#059669'),
        'track': c['alt'], 'border': c['border'],
        'free': '#065F46' if dark else '#DCFCE7',
        'free_border': '#34D399' if dark else '#4ADE80',
        'school_start': school[0], 'school_end': school[1],
        'school_text': readable_text(school[0], '#FFFFFF' if dark else '#991B1B', school[1:]),
        'school_border': '#F87171' if dark else '#F87171',
        'course_start': course[0], 'course_end': course[1],
        'course_text': readable_text(course[0], '#FFFFFF' if dark else '#9A3412', course[1:]),
        'course_border': '#FB923C',
    }


def table_bar_colors(percent):
    c = semantic_palette()
    pct = max(0., min(1., float(percent) / 100.))
    raw = _mix('#EF4444', '#22C55E', pct)
    # The label crosses the completed/remaining portions. One foreground must
    # contrast with BOTH surfaces; do not place dark text on dark progress fill.
    base = c['alt']
    text = c['alt_fg']
    fill = _contrast_safe_background(raw, text)
    return {'base': base, 'text': text, 'fill': fill,
            'border': c['border']}


def trend_colors():
    c = semantic_palette()
    return {'surface': c['alt'], 'text': c['alt_fg'],
            'border': c['border'], 'dark': c['dark']}
