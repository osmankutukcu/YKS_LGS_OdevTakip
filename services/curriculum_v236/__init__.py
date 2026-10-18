"""V23.6 teacher-friendly, read-only view of existing scoped curriculum records."""
from .overview import (CoverageOverview, ScopedTotals, read_coverage_overview, count_scoped_tasks)
__all__ = ('CoverageOverview', 'ScopedTotals', 'read_coverage_overview', 'count_scoped_tasks')
