"""Shikaku (四角に切れ) rectangle enumeration."""

from __future__ import annotations

from dataclasses import dataclass

from puzzle.grid import Cell, SquareGrid


@dataclass(frozen=True)
class ShikakuRect:
    """A rectangle candidate for Shikaku: covers a clue cell with matching area."""

    clue_cell: Cell
    cells: frozenset[Cell]

    def __hash__(self) -> int:
        return hash((self.clue_cell, self.cells))


def enumerate_shikaku_rectangles(
    board: SquareGrid,
    clues: dict[tuple[int, int], int],
) -> list[ShikakuRect]:
    """Enumerate all valid rectangle placements for Shikaku.

    For each clue at (r, c) with value n, generates all axis-aligned
    rectangles of area n that contain (r, c) and fit within the board.
    """
    rows = board._rows
    cols = board._cols
    result: list[ShikakuRect] = []

    for (cr, cc), area in clues.items():
        clue_cell = Cell(cr, cc)

        # Try all (height, width) factorizations of area
        for h in range(1, area + 1):
            if area % h != 0:
                continue
            w = area // h
            if h > rows or w > cols:
                continue

            # Try all top-left positions such that the rectangle
            # contains the clue cell and fits in the board
            for top in range(max(0, cr - h + 1), min(rows - h, cr) + 1):
                for left in range(max(0, cc - w + 1), min(cols - w, cc) + 1):
                    cells = frozenset(
                        Cell(top + dr, left + dc)
                        for dr in range(h)
                        for dc in range(w)
                    )
                    result.append(ShikakuRect(clue_cell, cells))

    return result
