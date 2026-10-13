"""Feature flag. Disabling V28 leaves V27 and all legacy workflows unchanged."""
import os
from services.adaptive_coaching_v25.flags import enabled as v25_enabled


def enabled():
    return v25_enabled() and os.environ.get('EDUTRACK_ADAPTIVE_V28', '1').strip().lower() not in (
        '0', 'off', 'false', 'hayir', 'no')
