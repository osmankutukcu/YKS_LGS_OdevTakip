"""Switch off V34 without affecting legacy homework tracking or V25-V33."""
import os
from services.adaptive_coaching_v27.flags import enabled as v27_enabled


def enabled():
    return v27_enabled() and os.environ.get('EDUTRACK_ADAPTIVE_V34', '1').strip().lower() not in (
        '0', 'off', 'false', 'hayir', 'no'
    )
