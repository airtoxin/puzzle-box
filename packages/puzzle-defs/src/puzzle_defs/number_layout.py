"""Fixed numeric labels; values are preserved rather than canonically renamed."""

from collections.abc import Sequence
from itertools import combinations
from typing import Any

from puzzle import Cell, SquareGrid

NumberGrid = tuple[tuple[int, ...], ...]
DEFAULT_NUMBERS: NumberGrid = ((1,1,2),(2,3,2))


def number_grid(value: Any, *, rows: int | None = None, cols: int | None = None) -> NumberGrid:
    if (type(value) not in (tuple,list) or not value
            or any(type(row) not in (tuple,list) or not row for row in value)):
        raise ValueError("Numbers must be a nonempty rectangular array")
    height,width = len(value),len(value[0])
    if (any(len(row) != width for row in value) or rows is not None and rows != height
            or cols is not None and cols != width):
        raise ValueError("Number grid dimensions must match the board")
    if any(type(n) is not int or not 0 <= n <= 99 for row in value for n in row):
        raise ValueError("Fixed numbers must be integers in 0..99")
    return tuple(tuple(row) for row in value)


def equal_number_pairs(board: SquareGrid, numbers: Sequence[Sequence[int]]) -> list[tuple[Cell, Cell]]:
    """Same-number pairs within each row or column; no new grid validation."""
    return [(a,b) for line in board.rows() + board.cols() for a,b in combinations(line,2)
            if numbers[a.row][a.col] == numbers[b.row][b.col]]
