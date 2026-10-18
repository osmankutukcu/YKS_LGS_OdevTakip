# -*- coding: utf-8 -*-
"""V40: Explicit light 'report paper' for legacy HTML reports.

Many reports contain *both* white paper panels and deliberately colored
risk/success/notice panels with explicit inline foreground/background colors.
Painting their whole QTextEdit dark while retaining original HTML foregrounds
causes unreadable text. Keep the pre-existing light HTML as a visibly bounded
reading surface even inside a dark parent theme; do not alter report HTML,
its data, links, markup, layout, selection, or scrolling.

A future opt-in dark HTML template can replace this after visual acceptance.
"""
from ui.theme_tokens_v37 import semantic_palette
from ui.theme import readable_text


def report_paper_qss():
    theme = semantic_palette()
    bg = '#FFFFFF'
    fg = readable_text(bg, '#172033')
    return ("QTextEdit, QTextBrowser {background:#FFFFFF;color:" + fg + ";"
            "border:1px solid " + theme['border'] + ";border-radius:8px;"
            "selection-background-color:#dbeafe;selection-color:#172033;}")
