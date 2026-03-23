"""Region enumeration and filtering utilities for partition puzzles."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from puzzle.grid import Cell, SquareGrid


@dataclass(frozen=True)
class Region:
    """A connected set of cells, optionally associated with a clue cell."""

    cells: frozenset[Cell]
    clue_cell: Cell | None = None

    def __hash__(self) -> int:
        return hash((self.cells, self.clue_cell))


def _grow(
    current: frozenset[Cell],
    target: set[Cell],
    size: int,
    results: set[frozenset[Cell]],
    board: SquareGrid,
) -> None:
    if len(current) == size:
        results.add(current)
        return
    candidates: set[Cell] = set()
    for c in current:
        for n in board.neighbors(c):
            if n in target and n not in current:
                candidates.add(n)
    for c in sorted(candidates):
        _grow(current | {c}, target, size, results, board)


def enumerate_connected_regions(
    board: SquareGrid,
    size: int,
    board_cells: set[Cell] | None = None,
) -> list[Region]:
    """Enumerate all connected regions of exactly `size` cells."""
    target = board_cells if board_cells is not None else set(board.cells)
    cell_sets: set[frozenset[Cell]] = set()
    for start in sorted(target):
        _grow(frozenset({start}), target, size, cell_sets, board)
    return [Region(cs) for cs in cell_sets]


def enumerate_rectangles(
    board: SquareGrid,
    size: int | None = None,
    board_cells: set[Cell] | None = None,
) -> list[Region]:
    """Enumerate all axis-aligned rectangles on the board.

    If size is given, only rectangles with that area are returned.
    """
    target = board_cells if board_cells is not None else set(board.cells)
    result: list[Region] = []

    for h in range(1, board._rows + 1):
        for w in range(1, board._cols + 1):
            area = h * w
            if size is not None and area != size:
                continue
            for top in range(board._rows - h + 1):
                for left in range(board._cols - w + 1):
                    cells = frozenset(
                        Cell(top + dr, left + dc)
                        for dr in range(h)
                        for dc in range(w)
                    )
                    if cells.issubset(target):
                        result.append(Region(cells))

    return result


def filter_one_number_per_region(
    regions: list[Region],
    numbers: dict[Cell, int],
) -> list[Region]:
    """Keep only regions containing exactly one numbered cell.

    Sets clue_cell on each matching region.
    """
    result: list[Region] = []
    for r in regions:
        numbered = [c for c in r.cells if c in numbers]
        if len(numbered) == 1:
            result.append(Region(r.cells, clue_cell=numbered[0]))
    return result


def filter_number_equals_area(
    regions: list[Region],
    numbers: dict[Cell, int],
) -> list[Region]:
    """Keep only regions containing exactly one number equal to the region's area.

    Sets clue_cell on each matching region.
    """
    result: list[Region] = []
    for r in regions:
        numbered = [c for c in r.cells if c in numbers]
        if len(numbered) == 1 and numbers[numbered[0]] == len(r.cells):
            result.append(Region(r.cells, clue_cell=numbered[0]))
    return result


def filter_same_number_combination(
    regions: list[Region],
    numbers: dict[Cell, int],
    num_regions: int,
) -> list[Region]:
    """Keep only regions whose number multiset matches the expected per-region share.

    Given the total numbers and number of regions, computes the required
    multiset per region. Returns only regions matching that multiset.
    """
    # Compute total counts
    total_counts = Counter(numbers.values())

    # Check divisibility
    expected: Counter[int] = Counter()
    for value, count in total_counts.items():
        if count % num_regions != 0:
            return []  # Not evenly divisible — no valid regions
        expected[value] = count // num_regions

    result: list[Region] = []
    for r in regions:
        region_counts = Counter(numbers[c] for c in r.cells if c in numbers)
        if region_counts == expected:
            result.append(r)

    return result
