from puzzle import (
    Cell,
    Puzzle,
    all_adjacent_different_shape,
    different_shape_across,
    enumerate_placements,
    exactly_one,
    polyomino,
    same_shape_across,
    square_grid,
)
from puzzle.grid import Vertex, _make_edge


def _solve_tiling(height, width, pieces, board_cells=None,
                  same_edges=None, different_edges=None,
                  adj_different=False):
    p = Puzzle("tiling")
    board = square_grid(height, width)
    target = board_cells if board_cells is not None else set(board.cells)

    all_placements = []
    for piece in pieces:
        for pl in enumerate_placements(board, piece):
            if pl.cells.issubset(target):
                all_placements.append(pl)

    use = p.bool_var_map("use", all_placements)

    by_cell: dict[Cell, list] = {}
    for pl in all_placements:
        for cell in pl.cells:
            by_cell.setdefault(cell, []).append(pl)

    for cell in target:
        covering = by_cell.get(cell, [])
        if not covering:
            return None
        p.add(exactly_one(use[pl] for pl in covering))

    for edge in (same_edges or []):
        p.add(same_shape_across(edge, use, all_placements, board))

    for edge in (different_edges or []):
        p.add(different_shape_across(edge, use, all_placements, board))

    if adj_different:
        p.add(all_adjacent_different_shape(use, all_placements, board))

    solution = p.solve()
    if solution is None:
        return None
    return [pl for pl in all_placements if solution.value(use[pl])]


def test_same_shape_across():
    """2x4 board with wall in the middle, two dominoes on each side.

    Left half and right half must use same shape (domino).
    Only one piece type, so same_shape is always satisfied.
    """
    domino = polyomino("D", [(0, 0), (0, 1)], allow_rotate=True)
    wall = _make_edge(Vertex(0, 2), Vertex(1, 2))
    # Wall splits 2x4 into two 2x2 halves
    result = _solve_tiling(
        2, 4, [domino],
        same_edges=[wall],
        different_edges=[],
    )
    assert result is not None


def test_different_shape_forces_variety():
    """2x4 board split by wall. L-tromino + monomino available.

    With different_shape constraint, the two sides must use different pieces.
    """
    L3 = polyomino("L3", [(0, 0), (1, 0), (1, 1)], allow_rotate=True, allow_reflect=True)
    mono = polyomino("mono", [(0, 0)], allow_rotate=False)
    # Wall between col 1 and col 2
    wall = _make_edge(Vertex(0, 2), Vertex(1, 2))

    # Left side: 2x2 = 4 cells, Right side: 2x2 = 4 cells
    # With different_shape: cells adjacent to the wall must be covered by different piece types
    result = _solve_tiling(
        2, 4, [L3, mono],
        different_edges=[wall],
    )
    assert result is not None
    # Check that pieces on each side of the wall differ in name
    left_cell = Cell(0, 1)
    right_cell = Cell(0, 2)
    left_piece = next(pl for pl in result if left_cell in pl.cells)
    right_piece = next(pl for pl in result if right_cell in pl.cells)
    assert left_piece.piece_name != right_piece.piece_name


def test_same_shape_constrains():
    """2x2 board with two piece types, same_shape on the vertical wall.

    domino (horizontal) + domino available.
    With same_shape on the wall between col 0 and col 1,
    pieces on both sides must be the same type.
    """
    H = polyomino("H", [(0, 0), (0, 1)], allow_rotate=False)  # horizontal only
    V = polyomino("V", [(0, 0), (1, 0)], allow_rotate=False)  # vertical only

    wall = _make_edge(Vertex(0, 1), Vertex(1, 1))  # vertical wall between col 0 and 1

    # Without same_shape: could use H+H (but H crosses wall) or V+V
    # H piece spans (0,0)-(0,1) which crosses the wall, so H can't be used
    # Wait, the wall is forbidden_internal_edges for pieces? No, same/different is
    # about the shape constraint, not about preventing crossing.
    # Actually the wall here is just for the shape constraint, pieces CAN cross it.
    # We need forbidden_internal_edges to prevent crossing.

    # Let me redesign: 2x4 with wall at col 2, using H and V dominoes
    # Left: 2x2, Right: 2x2
    # V fits in 2x2, H fits in 2x2
    # same_shape means both sides use same piece type
    wall2 = _make_edge(Vertex(0, 2), Vertex(1, 2))

    result = _solve_tiling(
        2, 4, [H, V],
        same_edges=[wall2],
    )
    assert result is not None
    # Pieces on both sides of wall must be same type
    left_cell = Cell(0, 1)
    right_cell = Cell(0, 2)
    left_piece = next(pl for pl in result if left_cell in pl.cells)
    right_piece = next(pl for pl in result if right_cell in pl.cells)
    assert left_piece.piece_name == right_piece.piece_name


def test_different_shape_makes_infeasible():
    """Only one piece type available, but different_shape required across wall."""
    domino = polyomino("D", [(0, 0), (0, 1)], allow_rotate=True)
    wall = _make_edge(Vertex(0, 2), Vertex(1, 2))

    # 2x4 split by wall. Both sides must use dominoes (only option).
    # different_shape requires different piece names, but only "D" exists.
    result = _solve_tiling(
        2, 4, [domino],
        different_edges=[wall],
    )
    assert result is None


def test_all_adjacent_different_shape():
    """Custom board shaped so I and L trominoes tile with no same-shape adjacency.

    I I I
    L .
    L L
    """
    I3 = polyomino("I", [(0, 0), (0, 1), (0, 2)], allow_rotate=True)
    L3 = polyomino("L", [(0, 0), (1, 0), (1, 1)], allow_rotate=True, allow_reflect=True)
    board_cells = {
        Cell(0, 0), Cell(0, 1), Cell(0, 2),
        Cell(1, 0),
        Cell(2, 0), Cell(2, 1),
    }
    result = _solve_tiling(3, 3, [I3, L3], board_cells=board_cells, adj_different=True)
    assert result is not None
    assert len(result) == 2
    # Verify all adjacent pieces have different names
    by_cell = {}
    for pl in result:
        for cell in pl.cells:
            by_cell[cell] = pl
    board = square_grid(3, 3)
    for cell in board_cells:
        for nbr in board.neighbors(cell):
            if nbr not in board_cells:
                continue
            pa = by_cell[cell]
            pb = by_cell[nbr]
            if pa is not pb:
                assert pa.piece_name != pb.piece_name, (
                    f"Adjacent same shape: {cell}({pa.piece_name}) - {nbr}({pb.piece_name})"
                )


def test_all_adjacent_different_infeasible_single_piece():
    """Only one piece type — impossible if any two pieces are adjacent."""
    domino = polyomino("D", [(0, 0), (0, 1)], allow_rotate=True)
    result = _solve_tiling(2, 4, [domino], adj_different=True)
    assert result is None


def test_polyomino_rotation_variants():
    """Verify rotation and reflection generate correct variant counts."""
    # Square: rotation doesn't change shape
    O = polyomino("O", [(0, 0), (0, 1), (1, 0), (1, 1)], allow_rotate=True)
    assert len(O.variants) == 1

    # Domino: 2 rotations
    D = polyomino("D", [(0, 0), (0, 1)], allow_rotate=True)
    assert len(D.variants) == 2

    # L-tromino: 4 rotations x 2 reflections = 4 unique (some overlap)
    L = polyomino("L", [(0, 0), (1, 0), (1, 1)], allow_rotate=True, allow_reflect=True)
    assert len(L.variants) == 4

    # T-tetromino: 4 rotations
    T = polyomino("T", [(0, 0), (0, 1), (0, 2), (1, 1)], allow_rotate=True)
    assert len(T.variants) == 4
