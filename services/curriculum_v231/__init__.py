"""V23.1 shared topic identity and readonly curriculum preview."""
from .identity import TopicIdentity, topic_key
from .reader import TopicRecord, TopicView, CurriculumSnapshot, effective_topics
from .legacy import LegacyResolution, resolve_legacy

__all__ = ('TopicIdentity', 'topic_key', 'TopicRecord', 'TopicView',
           'CurriculumSnapshot', 'effective_topics', 'LegacyResolution', 'resolve_legacy')
