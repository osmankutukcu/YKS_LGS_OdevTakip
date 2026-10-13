"""Independent fail-safe for the optional V30 action."""
import os
from services.adaptive_coaching_v29.flags import enabled as v29_enabled

def enabled():
    return v29_enabled() and os.environ.get('EDUTRACK_ADAPTIVE_V30', '1').strip().lower() not in (
        '0', 'off', 'false', 'hayir', 'no'
    )
