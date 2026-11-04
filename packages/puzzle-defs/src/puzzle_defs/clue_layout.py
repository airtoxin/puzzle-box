"""Nullable numeric givens: None is absent, while zero remains a real clue."""

from typing import Any

ClueGrid = tuple[tuple[int | None, ...], ...]


def clue_grid(value: Any, *, rows: int | None = None, cols: int | None = None,
              maximum: int = 99) -> ClueGrid:
    if type(maximum) is not int or maximum < 0:
        raise ValueError("Clue maximum must be a nonnegative integer")
    if (type(value) not in (tuple, list) or not value
            or any(type(row) not in (tuple, list) or not row for row in value)):
        raise ValueError("Clues must be a nonempty rectangular array")
    height, width = len(value), len(value[0])
    if (any(len(row) != width for row in value) or rows is not None and rows != height
            or cols is not None and cols != width):
        raise ValueError("Clue grid dimensions must match the board")
    if any(n is not None and (type(n) is not int or not 0 <= n <= maximum) for row in value for n in row):
        raise ValueError(f"Clues must be null or integers in 0..{maximum}")
    return tuple(tuple(row) for row in value)
