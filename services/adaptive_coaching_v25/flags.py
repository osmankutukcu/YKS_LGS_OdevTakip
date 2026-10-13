# -*- coding: utf-8 -*-
"""V25 feature switch; disabled value completely hides the optional entry points."""
import os


def enabled():
    return os.getenv('EDUTRACK_ADAPTIVE_V25', '1').strip().lower() not in ('0','false','off','hayir')
