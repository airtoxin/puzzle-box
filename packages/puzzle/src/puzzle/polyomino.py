"""Polyomino definition, transformation, and placement enumeration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Hashable, Sequence

from puzzle.grid import Cell, Edge, SquareGrid, Vertex, _make_edge

if TYPE_CHECKING:
    from puzzle.expr import VarMap


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


@dataclass(frozen=True)
class ShapeAcrossConstraint:
    """Constraint on piece shapes across a boundary edge."""

    forbidden_pairs: list[tuple[Placement, Placement]]
    use_vars: VarMap


def _placements_by_cell(
    placements: list[Placement],
) -> dict[Cell, list[Placement]]:
    result: dict[Cell, list[Placement]] = {}
    for pl in placements:
        for cell in pl.cells:
            result.setdefault(cell, []).append(pl)
    return result


def same_shape_across(
    edge: Edge,
    use_vars: VarMap,
    placements: list[Placement],
    board: SquareGrid,
) -> ShapeAcrossConstraint:
    """Pieces on both sides of the edge must have the same shape."""
    a, b = board.cells_sharing_edge(edge)
    by_cell = _placements_by_cell(placements)
    pa_list = by_cell.get(a, [])
    pb_list = by_cell.get(b, [])
    forbidden = [
        (pa, pb)
        for pa in pa_list
        for pb in pb_list
        if pa.piece_name != pb.piece_name
    ]
    return ShapeAcrossConstraint(forbidden, use_vars)


def different_shape_across(
    edge: Edge,
    use_vars: VarMap,
    placements: list[Placement],
    board: SquareGrid,
) -> ShapeAcrossConstraint:
    """Pieces on both sides of the edge must have different shapes."""
    a, b = board.cells_sharing_edge(edge)
    by_cell = _placements_by_cell(placements)
    pa_list = by_cell.get(a, [])
    pb_list = by_cell.get(b, [])
    forbidden = [
        (pa, pb)
        for pa in pa_list
        for pb in pb_list
        if pa.piece_name == pb.piece_name
    ]
    return ShapeAcrossConstraint(forbidden, use_vars)


def all_adjacent_different_shape(
    use_vars: VarMap,
    placements: list[Placement],
    board: SquareGrid,
) -> ShapeAcrossConstraint:
    """All adjacent pieces must have different shapes.

    For every pair of adjacent cells covered by different placements,
    those placements must have different piece names.
    """
    by_cell = _placements_by_cell(placements)
    seen: set[tuple[Placement, Placement]] = set()
    forbidden: list[tuple[Placement, Placement]] = []

    for cell in board.cells:
        for nbr in board.neighbors(cell):
            pa_list = by_cell.get(cell, [])
            pb_list = by_cell.get(nbr, [])
            for pa in pa_list:
                for pb in pb_list:
                    if pa is pb:
                        continue  # same placement = same piece
                    if pa.piece_name != pb.piece_name:
                        continue  # different shape = allowed
                    pair = (pa, pb) if id(pa) < id(pb) else (pb, pa)
                    if pair not in seen:
                        seen.add(pair)
                        forbidden.append(pair)

    return ShapeAcrossConstraint(forbidden, use_vars)


@dataclass(frozen=True)
class NoBoundaryCrossConstraint:
    """At each interior vertex, boundaries must not form a cross (+).

    Stores per-vertex lists of placements that bridge at least one
    adjacent cell pair around that vertex. At least one must be selected.
    """

    vertex_bridges: list[list[Placement]]
    use_vars: VarMap


def no_boundary_cross(
    use_vars: VarMap,
    placements: list[Placement],
    board: SquareGrid,
    board_cells: set[Cell] | None = None,
) -> NoBoundaryCrossConstraint:
    """No boundary cross (tatami constraint).

    At every interior vertex, the region boundaries must not form
    a + shape. Equivalently, at least one adjacent cell pair around
    each vertex must belong to the same region.
    """
    target = board_cells if board_cells is not None else set(board.cells)

    # Index placements by adjacent cell pairs
    pair_to_pls: dict[tuple[Cell, Cell], list[Placement]] = {}
    for pl in placements:
        cells_list = list(pl.cells)
        for i, c1 in enumerate(cells_list):
            for c2 in cells_list[i + 1 :]:
                if abs(c1.row - c2.row) + abs(c1.col - c2.col) == 1:
                    pair = (min(c1, c2), max(c1, c2))
                    pair_to_pls.setdefault(pair, []).append(pl)

    vertex_bridges: list[list[Placement]] = []

    for r in range(1, board._rows):
        for c in range(1, board._cols):
            a = Cell(r - 1, c - 1)
            b = Cell(r - 1, c)
            cc = Cell(r, c - 1)
            d = Cell(r, c)

            # Only constrain if all 4 cells are on the board
            if not {a, b, cc, d}.issubset(target):
                continue

            pairs = [
                (min(a, b), max(a, b)),
                (min(cc, d), max(cc, d)),
                (min(a, cc), max(a, cc)),
                (min(b, d), max(b, d)),
            ]

            bridges: set[Placement] = set()
            for pair in pairs:
                bridges.update(pair_to_pls.get(pair, []))

            vertex_bridges.append(list(bridges))

    return NoBoundaryCrossConstraint(vertex_bridges, use_vars)
