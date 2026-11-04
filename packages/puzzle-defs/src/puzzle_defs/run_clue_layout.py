"""Immutable unordered lengths of cyclic black runs; None is no clue."""

from typing import Any

RunClue = tuple[int, ...]
RunClueGrid = tuple[tuple[RunClue | None, ...], ...]
DEFAULT_BLACK_RUN_CLUES: RunClueGrid = (((3,), None, None), (None, None, None))


def run_clue_grid(value: Any, *, rows: int | None = None, cols: int | None = None) -> RunClueGrid:
    if (type(value) not in (tuple, list) or not value
            or any(type(row) not in (tuple, list) or not row for row in value)):
        raise ValueError("Run clues must be a nonempty rectangular grid")
    height, width = len(value), len(value[0])
    if (any(len(row) != width for row in value) or rows is not None and rows != height
            or cols is not None and cols != width):
        raise ValueError("Run clue grid dimensions must match the board")
    result = []
    for row in value:
        parsed = []
        for clue in row:
            if clue is None:
                parsed.append(None)
                continue
            if (type(clue) not in (tuple, list) or not 1 <= len(clue) <= 4
                    or any(type(n) is not int or not 0 <= n <= 8 for n in clue)
                    or 0 in clue and tuple(clue) != (0,)
                    or len(clue) > 1 and sum(clue)+len(clue) > 8):
                raise ValueError("Run clues must be [0] or 1..4 positive lengths fitting eight cells with separating gaps")
            parsed.append(tuple(sorted(clue)))
        result.append(tuple(parsed))
    return tuple(result)
