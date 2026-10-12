"""V23.2: SQL-read-only bridge between legacy matrix IDs and scoped curriculum."""
from .bridge import MatrixTopic, MatrixReview, inspect_matrix_topics

__all__ = ('MatrixTopic', 'MatrixReview', 'inspect_matrix_topics')
