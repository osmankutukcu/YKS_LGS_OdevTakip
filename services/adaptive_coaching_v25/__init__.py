"""V25 bilimsel öğrenme döngüsü; mevcut ödev şemasına dokunmaz."""
from .engine import (
    ensure_schema, save_observation, observations, student_topics, make_plan,
    save_plan, load_preferences, save_preferences, student_overview,
    save_blocker, get_blockers
)
