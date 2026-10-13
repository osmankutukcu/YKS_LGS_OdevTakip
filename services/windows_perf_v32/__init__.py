"""V32 non-invasive Windows homework GUI performance measurements.

This module never imports PyQt6, alters homework records, or installs GUI hooks
when used as an ordinary application dependency.
"""
from .trace import MethodStats, install_method_timing
from .database import inspect_query_plans, compare_header_stat_queries
__all__ = ['MethodStats', 'install_method_timing', 'inspect_query_plans', 'compare_header_stat_queries']
