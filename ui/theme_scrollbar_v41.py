# -*- coding: utf-8 -*-
"""V41 -- Qt-free scrollbar colours and QSS from the active surface palette.

Colour changes only. No event filters, scrolling behaviour, or data access.
A visible thumb contrasts with its actual opaque track >= 3:1.
"""
from ui.theme import _mix, _luminance, contrast_ratio


def ensure_visible(track, preferred, minimum=3.0):
    """Minimal, predictable channel blending to a contrasting neutral."""
    if contrast_ratio(track, preferred) >= minimum:
        return preferred
    goal = '#FFFFFF' if _luminance(track) < 0.19 else '#000000'
    for level in range(1, 101):
        candidate = _mix(preferred, goal, level / 100)
        if contrast_ratio(track, candidate) >= minimum:
            return candidate
    return goal


def scrollbar_palette(track, text, accent):
    # No transparency: an unknown underlying custom widget can otherwise
    # invalidate a contrast calculation (and turn the thumb invisible).
    normal = ensure_visible(track, _mix(text, track, .28))
    hovered = ensure_visible(track, _mix(accent, normal, .48))
    pressed = ensure_visible(track, accent)
    disabled = ensure_visible(track, _mix(normal, track, .10))
    return dict(track=track, normal=normal, hovered=hovered,
                pressed=pressed, disabled=disabled)


def scrollbar_qss(track, text, accent, size=12):
    try:
        size = max(6, min(24, int(size)))
    except (TypeError, ValueError):
        size = 12
    p = scrollbar_palette(track, text, accent)
    radius = size // 2
    return f"""
    /* V41: opaque, contrast-checked themed scrollbars; keep full hit area. */
    QScrollBar:vertical {{ border:none; background:{p['track']}; width:{size}px;
                          margin:0; border-radius:{radius}px; }}
    QScrollBar:horizontal {{ border:none; background:{p['track']}; height:{size}px;
                            margin:0; border-radius:{radius}px; }}
    QScrollBar::handle:vertical {{ background:{p['normal']}; min-height:32px;
                                  border:none; border-radius:{radius}px; }}
    QScrollBar::handle:horizontal {{ background:{p['normal']}; min-width:32px;
                                    border:none; border-radius:{radius}px; }}
    QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{background:{p['hovered']};}}
    QScrollBar::handle:vertical:pressed, QScrollBar::handle:horizontal:pressed {{background:{p['pressed']};}}
    QScrollBar::handle:vertical:disabled, QScrollBar::handle:horizontal:disabled {{background:{p['disabled']};}}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{height:0px; border:none; background:transparent;}}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{width:0px; border:none; background:transparent;}}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{background:{p['track']};}}
    QScrollBar::corner {{ background:{p['track']}; }}
    """
