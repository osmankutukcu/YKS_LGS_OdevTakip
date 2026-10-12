"""Pure sizing decisions for Windows/low-resolution Qt layouts.

Widths are Qt logical pixels, not physical display pixels: on Windows at
125% scaling a 1366px monitor offers roughly 1093 logical pixels.
No font/DPI override is used; accessibility zoom stays under the user's OS.
"""

MAIN_SIDEBAR_BREAKPOINT = 1280
HOMEWORK_THREE_COLUMN_BREAKPOINT = 1440


def compact_main_shell(width: int) -> bool:
    return width > 0 and width < MAIN_SIDEBAR_BREAKPOINT


def compact_homework_workspace(width: int) -> bool:
    return width > 0 and width < HOMEWORK_THREE_COLUMN_BREAKPOINT


def minimum_form_columns(width: int) -> tuple[int, int]:
    """Preferred minimal left/right widths: actual tables can scroll."""
    return (350, 230) if compact_homework_workspace(width) else (530, 300)


def screen_bound_minimum(default: tuple[int, int], available: tuple[int, int], reserve: int = 24) -> tuple[int, int]:
    """Ensure nominal dialog minimum never exceeds the work area (Qt logical px)."""
    return (min(default[0], max(1, available[0] - reserve)),
            min(default[1], max(1, available[1] - reserve)))
