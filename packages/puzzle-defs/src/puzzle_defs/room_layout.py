"""Immutable, connected partitions of a rectangular cell board."""

from typing import Any

RoomMap = tuple[tuple[int, ...], ...]
DEFAULT_ROOMS: RoomMap = ((0, 0, 1), (0, 1, 1))


def room_map(value: Any, *, rows: int | None = None, cols: int | None = None) -> RoomMap:
    """Validate and canonically relabel rooms in first-cell order.

    Labels are nonnegative integers smaller than the area. Each cell belongs to
    exactly one orthogonally connected room. Labels have no meaning beyond equality.
    """
    if (type(value) not in (tuple, list) or not value
            or any(type(row) not in (tuple, list) or not row for row in value)):
        raise ValueError("Rooms must be a nonempty rectangular array of integer labels")
    height, width = len(value), len(value[0])
    if (any(len(row) != width for row in value) or rows is not None and rows != height
            or cols is not None and cols != width):
        raise ValueError("Room map dimensions must match the board")
    if any(type(n) is not int or not 0 <= n < height*width for row in value for n in row):
        raise ValueError("Room labels must be integers in 0..area-1")
    labels: dict[int, int] = {}
    normalized = tuple(tuple(labels.setdefault(n, len(labels)) for n in row) for row in value)
    groups: dict[int, set[tuple[int, int]]] = {}
    for r, row in enumerate(normalized):
        for c, label in enumerate(row):
            groups.setdefault(label, set()).add((r, c))
    for cells in groups.values():
        remaining, todo = set(cells), [min(cells)]
        while todo:
            r, c = todo.pop()
            if (r, c) not in remaining:
                continue
            remaining.remove((r, c))
            todo.extend(p for p in ((r-1,c), (r+1,c), (r,c-1), (r,c+1)) if p in remaining)
        if remaining:
            raise ValueError("Each room must be orthogonally connected")
    return normalized
