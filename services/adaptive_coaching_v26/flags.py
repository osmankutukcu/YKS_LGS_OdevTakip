"""V26 is additive and inherits the V25 opt-out switch."""
import os
from services.adaptive_coaching_v25.flags import enabled as v25_enabled


def enabled():
    return v25_enabled() and os.getenv('EDUTRACK_ADAPTIVE_V26', '1').strip().lower() not in ('0', 'false', 'off', 'hayir')
