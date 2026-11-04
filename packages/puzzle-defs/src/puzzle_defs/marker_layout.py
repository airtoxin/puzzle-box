"""Immutable binary presence markers, distinct from numeric clues."""

from typing import Any

from puzzle_defs.number_layout import NumberGrid, number_grid

MarkerGrid = NumberGrid
DEFAULT_ENDPOINT_MARKERS: MarkerGrid = ((1, 0, 0), (0, 0, 1))


def marker_grid(value: Any, *, rows: int | None = None, cols: int | None = None) -> MarkerGrid:
    grid = number_grid(value, rows=rows, cols=cols)
    if any(n not in (0, 1) for row in grid for n in row):
        raise ValueError("Markers must be integers 0 (absent) or 1 (present)")
    return grid
