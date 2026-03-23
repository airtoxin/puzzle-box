from puzzle import Cell
from puzzle_defs import polyomino
from puzzle.grid import Edge, Vertex, _make_edge
from solvers.tiling import solve


def _validate(height: int, width: int, result: list) -> None:
    """Check every cell is covered exactly once."""
    coverage: dict[Cell, int] = {}
    for pl in result:
        for cell in pl.cells:
            assert 0 <= cell.row < height and 0 <= cell.col < width, (
                f"Cell {cell} out of bounds"
            )
            coverage[cell] = coverage.get(cell, 0) + 1

    for r in range(height):
        for c in range(width):
            cell = Cell(r, c)
            assert coverage.get(cell, 0) == 1, (
                f"Cell {cell} covered {coverage.get(cell, 0)} times"
            )


def test_l_tromino_4x3():
    """4x3 = 12 cells, L-tromino covers 3 → 4 pieces needed."""
    L3 = polyomino("L3", [(0, 0), (1, 0), (1, 1)],
                   allow_rotate=True, allow_reflect=True)
    result = solve(4, 3, [L3])
    assert result is not None
    assert len(result) == 4
    _validate(4, 3, result)


def test_domino_2x4():
    """2x4 = 8 cells, domino covers 2 → 4 pieces needed."""
    domino = polyomino("domino", [(0, 0), (0, 1)], allow_rotate=True)
    result = solve(2, 4, [domino])
    assert result is not None
    assert len(result) == 4
    _validate(2, 4, result)


def test_monomino_3x3():
    """3x3 = 9 cells, monomino covers 1 → 9 pieces."""
    mono = polyomino("mono", [(0, 0)], allow_rotate=False)
    result = solve(3, 3, [mono])
    assert result is not None
    assert len(result) == 9
    _validate(3, 3, result)


def test_tetromino_4x4():
    """4x4 with T-tetromino."""
    T = polyomino("T", [(0, 0), (0, 1), (0, 2), (1, 1)],
                  allow_rotate=True, allow_reflect=True)
    result = solve(4, 4, [T])
    assert result is not None
    assert len(result) == 4
    _validate(4, 4, result)


def test_impossible_domino_3x3():
    """3x3 = 9 cells, domino covers 2 → can't tile odd area."""
    domino = polyomino("domino", [(0, 0), (0, 1)], allow_rotate=True)
    result = solve(3, 3, [domino])
    assert result is None


def test_max_uses():
    """Limit each piece to one use — can't fill 2x4 with 1 domino."""
    domino = polyomino("domino", [(0, 0), (0, 1)], allow_rotate=True)
    result = solve(2, 4, [domino], max_uses={"domino": 1})
    assert result is None


def test_mixed_pieces():
    """4x3 with dominoes and L-trominoes."""
    domino = polyomino("domino", [(0, 0), (0, 1)], allow_rotate=True)
    L3 = polyomino("L3", [(0, 0), (1, 0), (1, 1)],
                   allow_rotate=True, allow_reflect=True)
    result = solve(4, 3, [domino, L3])
    assert result is not None
    _validate(4, 3, result)


def test_walls():
    """2x2 board with a wall splitting it — dominoes can't cross."""
    domino = polyomino("domino", [(0, 0), (0, 1)], allow_rotate=True)
    # Wall between (0,0)-(0,1) and (1,0)-(1,1): vertical edge at col 1
    wall = _make_edge(Vertex(0, 1), Vertex(1, 1))
    # Only vertical dominoes fit on each side
    result = solve(2, 2, [domino], forbidden_internal_edges={wall})
    assert result is not None
    _validate(2, 2, result)
    # Both dominoes must be vertical (no crossing the wall)
    for pl in result:
        cells = sorted(pl.cells)
        assert cells[0].col == cells[1].col, "Domino should be vertical"


def test_max_uses_per_piece():
    """2x4 with exactly 2 L-trominoes and 1 domino."""
    L3 = polyomino("L3", [(0, 0), (1, 0), (1, 1)],
                   allow_rotate=True, allow_reflect=True)
    D = polyomino("D", [(0, 0), (0, 1)], allow_rotate=True)
    result = solve(2, 4, [L3, D], max_uses={"L3": 2, "D": 1})
    assert result is not None
    _validate(2, 4, result)
    names = sorted(pl.piece_name for pl in result)
    assert names == ["D", "L3", "L3"]
