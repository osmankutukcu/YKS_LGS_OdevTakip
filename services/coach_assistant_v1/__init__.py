# -*- coding: utf-8 -*-
"""Modular, zero-overhead Coach Assistant insight engine (V1).

100% read-only, isolated from core homework writes, and easily extensible.
"""
from .insights import AssistantInsight, build_student_curiosity_insight, build_topic_curiosity_insight

__all__ = [
    "AssistantInsight",
    "build_student_curiosity_insight",
    "build_topic_curiosity_insight",
]
