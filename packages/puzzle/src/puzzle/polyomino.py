"""Polyomino definition, transformation, and placement enumeration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from puzzle.grid import Cell, Edge, SquareGrid, Vertex, _make_edge


def _normalize(cells: list[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    """Translate cells so minimum row and col are 0, return sorted tuple."""
    min_r = min(r for r, _ in cells)
    min_c = min(c for _, c in cells)
    return tuple(sorted((r - min_r, c - min_c) for r, c in cells))


def _rotate90(cells: tuple[tuple[int, int], ...]) -> tuple[tuple[int, int], ...]:
    """Rotate 90° clockwise: (r, c) -> (c, -r)."""
    return _normalize([(c, -r) for r, c in cells])


def _reflect(cells: tuple[tuple[int, int], ...]) -> tuple[tuple[int, int], ...]:
    """Reflect horizontally: (r, c) -> (r, -c)."""
    return _normalize([(r, -c) for r, c in cells])


@dataclass(frozen=True)
class Polyomino:
    name: str
    variants: frozenset[tuple[tuple[int, int], ...]]


def polyomino(
    name: str,
    cells: Sequence[tuple[int, int]],
    allow_rotate: bool = True,
    allow_reflect: bool = False,
) -> Polyomino:
    """Define a polyomino piece with optional rotation and reflection."""
    base = _normalize(list(cells))
    variants: set[tuple[tuple[int, int], ...]] = set()

    orientations = [base]
    if allow_rotate:
        r1 = _rotate90(base)
        r2 = _rotate90(r1)
        r3 = _rotate90(r2)
        orientations = [base, r1, r2, r3]

    for o in orientations:
        variants.add(o)
        if allow_reflect:
            variants.add(_reflect(o))

    return Polyomino(name, frozenset(variants))


@dataclass(frozen=True)
class Placement:
    piece_name: str
    cells: frozenset[Cell]

    def __hash__(self) -> int:
        return hash((self.piece_name, self.cells))


def _edge_between_cells(c1: Cell, c2: Cell) -> Edge:
    """Return the grid edge that separates two adjacent cells."""
    if c1.row == c2.row:
        # Horizontal neighbors: vertical edge between them
        right_col = max(c1.col, c2.col)
        return _make_edge(
            Vertex(c1.row, right_col),
            Vertex(c1.row + 1, right_col),
        )
    else:
        # Vertical neighbors: horizontal edge between them
        bottom_row = max(c1.row, c2.row)
        return _make_edge(
            Vertex(bottom_row, c1.col),
            Vertex(bottom_row, c1.col + 1),
        )


def enumerate_placements(
    board: SquareGrid,
    piece: Polyomino,
    forbidden_internal_edges: set[Edge] | None = None,
) -> list[Placement]:
    """Enumerate all valid placements of a polyomino on a board."""
    walls = forbidden_internal_edges or set()
    board_cells = set(board.cells)
    result: list[Placement] = []

    for variant in piece.variants:
        # Bounding box of this variant
        max_r = max(r for r, _ in variant)
        max_c = max(c for _, c in variant)

        for offset_r in range(board._rows - max_r):
            for offset_c in range(board._cols - max_c):
                placed = frozenset(
                    Cell(r + offset_r, c + offset_c) for r, c in variant
                )

                # All cells must be on the board
                if not placed.issubset(board_cells):
                    continue

                # Check no internal edge crosses a wall
                valid = True
                if walls:
                    placed_list = list(placed)
                    for i, c1 in enumerate(placed_list):
                        for c2 in placed_list[i + 1 :]:
                            if abs(c1.row - c2.row) + abs(c1.col - c2.col) == 1:
                                if _edge_between_cells(c1, c2) in walls:
                                    valid = False
                                    break
                        if not valid:
                            break

                if valid:
                    result.append(Placement(piece.name, placed))

    return result
