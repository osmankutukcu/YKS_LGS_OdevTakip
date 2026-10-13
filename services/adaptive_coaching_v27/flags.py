"""Disabling V27 restores the original Homework Tracking layout."""
import os
from services.adaptive_coaching_v26.flags import enabled as v26_enabled


def enabled():
    return v26_enabled() and os.getenv('EDUTRACK_ADAPTIVE_V27', '1').strip().lower() not in ('0', 'false', 'off', 'hayir')
