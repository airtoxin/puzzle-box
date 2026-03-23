from puzzle import (
    Cell,
    Puzzle,
    exactly_one,
    square_grid,
)
from puzzle.grid import Vertex, _make_edge
from puzzle_defs import (
    all_adjacent_different_shape,
    different_shape_across,
    enumerate_placements,
    no_boundary_cross,
    polyomino,
    same_shape_across,
)


def _solve_tiling(height, width, pieces, board_cells=None,
                  same_edges=None, different_edges=None,
                  adj_different=False, tatami=False):
    p = Puzzle("tiling")
    p.add_feature("region_partition")
    p.add_feature("shape_class")
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

    if tatami:
        p.add(no_boundary_cross(use, all_placements, board, board_cells))

    solution = p.solve()
    if solution is None:
        return None
    return [pl for pl in all_placements if solution.value(use[pl])]


def test_same_shape_across():
    domino = polyomino("D", [(0, 0), (0, 1)], allow_rotate=True)
    wall = _make_edge(Vertex(0, 2), Vertex(1, 2))
    result = _solve_tiling(2, 4, [domino], same_edges=[wall])
    assert result is not None


def test_different_shape_forces_variety():
    L3 = polyomino("L3", [(0, 0), (1, 0), (1, 1)], allow_rotate=True, allow_reflect=True)
    mono = polyomino("mono", [(0, 0)], allow_rotate=False)
    wall = _make_edge(Vertex(0, 2), Vertex(1, 2))
    result = _solve_tiling(2, 4, [L3, mono], different_edges=[wall])
    assert result is not None
    left_piece = next(pl for pl in result if Cell(0, 1) in pl.cells)
    right_piece = next(pl for pl in result if Cell(0, 2) in pl.cells)
    assert left_piece.piece_name != right_piece.piece_name


def test_same_shape_constrains():
    H = polyomino("H", [(0, 0), (0, 1)], allow_rotate=False)
    V = polyomino("V", [(0, 0), (1, 0)], allow_rotate=False)
    wall2 = _make_edge(Vertex(0, 2), Vertex(1, 2))
    result = _solve_tiling(2, 4, [H, V], same_edges=[wall2])
    assert result is not None
    left_piece = next(pl for pl in result if Cell(0, 1) in pl.cells)
    right_piece = next(pl for pl in result if Cell(0, 2) in pl.cells)
    assert left_piece.piece_name == right_piece.piece_name


def test_different_shape_makes_infeasible():
    domino = polyomino("D", [(0, 0), (0, 1)], allow_rotate=True)
    wall = _make_edge(Vertex(0, 2), Vertex(1, 2))
    result = _solve_tiling(2, 4, [domino], different_edges=[wall])
    assert result is None


def test_all_adjacent_different_shape():
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


def test_all_adjacent_different_infeasible_single_piece():
    domino = polyomino("D", [(0, 0), (0, 1)], allow_rotate=True)
    result = _solve_tiling(2, 4, [domino], adj_different=True)
    assert result is None


def test_all_adjacent_different_infeasible_2x3():
    I3 = polyomino("I", [(0, 0), (0, 1), (0, 2)], allow_rotate=True)
    result = _solve_tiling(2, 3, [I3], adj_different=True)
    assert result is None


def test_no_boundary_cross_2x2():
    domino = polyomino("D", [(0, 0), (0, 1)], allow_rotate=True)
    result = _solve_tiling(2, 2, [domino], tatami=True)
    assert result is not None


def test_no_boundary_cross_rejects_cross():
    mono = polyomino("M", [(0, 0)])
    result = _solve_tiling(2, 2, [mono], tatami=True)
    assert result is None


def test_no_boundary_cross_3x3():
    I3 = polyomino("I", [(0, 0), (0, 1), (0, 2)], allow_rotate=True)
    L3 = polyomino("L", [(0, 0), (1, 0), (1, 1)], allow_rotate=True, allow_reflect=True)
    result = _solve_tiling(3, 3, [I3, L3], tatami=True)
    assert result is not None


def test_polyomino_rotation_variants():
    O = polyomino("O", [(0, 0), (0, 1), (1, 0), (1, 1)], allow_rotate=True)
    assert len(O.variants) == 1
    D = polyomino("D", [(0, 0), (0, 1)], allow_rotate=True)
    assert len(D.variants) == 2
    L = polyomino("L", [(0, 0), (1, 0), (1, 1)], allow_rotate=True, allow_reflect=True)
    assert len(L.variants) == 4
    T = polyomino("T", [(0, 0), (0, 1), (0, 2), (1, 1)], allow_rotate=True)
    assert len(T.variants) == 4
