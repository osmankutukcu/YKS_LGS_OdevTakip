# -*- coding: utf-8 -*-
"""Qt-free, contrast-safe 2-stop gradients for dashboard and badge labels."""
from ui.theme import _safe_color, _hex_to_rgb, _contrast_safe_background, contrast_ratio


def _distance(a, b):
    x, y = _hex_to_rgb(a), _hex_to_rgb(b)
    return sum((j - k) ** 2 for j, k in zip(x, y))


def accessible_gradient(left, right, preferred='#FFFFFF'):
    """Return (left, right, foreground) with both text stops >= WCAG 4.5:1.

    Change only the gradient stops when neither foreground candidate can pass;
    select the smallest total movement in RGB space. Semantic red/green/blue
    hues remain distinct, the Qt gradient direction and widget geometry remain.
    """
    left = _safe_color(left, '#2563EB')
    right = _safe_color(right, '#1D4ED8')
    candidates = ('#FFFFFF', '#111315') if preferred == '#FFFFFF' else ('#111315', '#FFFFFF')
    choices = []
    for fg in candidates:
        a = _contrast_safe_background(left, fg)
        b = _contrast_safe_background(right, fg)
        assert min(contrast_ratio(a, fg), contrast_ratio(b, fg)) >= 4.5
        choices.append((_distance(a, left) + _distance(b, right), a, b, fg))
    _, a, b, fg = min(choices, key=lambda p: p[0])
    return a, b, fg
