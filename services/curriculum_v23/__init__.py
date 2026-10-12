"""V23: Mevcut müfredat tablolarını koruyan güvenli düzenleme katmanı.

Bu modüller PyQt6 bağımlılığı taşımaz; ana ödev matrisini değiştirmez.
"""
from .impact import topic_impact, topic_table, CurriculumSafetyError
from .changes import save_topics, delete_unused_topics, rename_topic_safe

__all__ = ['topic_impact', 'topic_table', 'CurriculumSafetyError',
           'save_topics', 'delete_unused_topics', 'rename_topic_safe']
