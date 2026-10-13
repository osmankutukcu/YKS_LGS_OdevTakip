"""V29 can be disabled without disabling any previous operation."""
import os
from services.adaptive_coaching_v28.flags import enabled as v28_enabled


def enabled():
    return v28_enabled() and os.environ.get('EDUTRACK_ADAPTIVE_V29', '1').strip().lower() not in (
        '0', 'off', 'false', 'hayir', 'no')
