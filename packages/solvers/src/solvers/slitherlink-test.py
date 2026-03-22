from puzzle.grid import Edge, Vertex, SquareGrid, _make_edge

from solvers.slitherlink import solve


def _validate(grid: list[list[int | None]], edges: set[Edge]) -> None:
    rows = len(grid)
    cols = len(grid[0])
    board = SquareGrid(rows, cols)

    # Check clues
    for r in range(rows):
        for c in range(cols):
            clue = grid[r][c]
            if clue is not None:
                count = sum(1 for e in board.edges_around(board.cell(r, c)) if e in edges)
                assert count == clue, f"Cell ({r},{c}): expected {clue}, got {count}"

    # Check vertex degrees
    for v in board.vertices:
        deg = sum(1 for e in board.edges_incident(v) if e in edges)
        assert deg in (0, 2), f"Vertex ({v.row},{v.col}): degree {deg}"

    # Check connectivity (single cycle)
    if not edges:
        return
    adj: dict[Vertex, list[Vertex]] = {}
    for e in edges:
        adj.setdefault(e.v1, []).append(e.v2)
        adj.setdefault(e.v2, []).append(e.v1)
    start = next(iter(adj))
    visited: set[Vertex] = set()
    stack = [start]
    while stack:
        v = stack.pop()
        if v in visited:
            continue
        visited.add(v)
        for u in adj[v]:
            if u not in visited:
                stack.append(u)
    assert visited == set(adj.keys()), "Edges do not form a single connected cycle"


N = None


def test_solve_2x2():
    grid = [
        [2, 2],
        [2, 2],
    ]
    result = solve(grid)
    assert result is not None
    _validate(grid, result)


def test_solve_3x3():
    grid = [
        [2, 1, 2],
        [1, 0, 1],
        [2, 1, 2],
    ]
    result = solve(grid)
    assert result is not None
    _validate(grid, result)


def test_solve_with_none_clues():
    """Partial clues — some cells have no clue."""
    grid = [
        [N, 2, N],
        [2, N, 2],
        [N, 2, N],
    ]
    result = solve(grid)
    assert result is not None
    _validate(grid, result)


def test_solve_5x5():
    """A 5x5 puzzle.

    . 2 . 3 .
    2 . . . 2
    . . 2 . .
    2 . . . 2
    . 2 . 3 .
    """
    grid = [
        [N, 2, N, 3, N],
        [2, N, N, N, 2],
        [N, N, 2, N, N],
        [2, N, N, N, 2],
        [N, 2, N, 3, N],
    ]
    result = solve(grid)
    assert result is not None
    _validate(grid, result)


def test_unsolvable():
    """Contradictory clues — no valid loop exists."""
    grid = [
        [4, 4],
        [4, 4],
    ]
    result = solve(grid)
    assert result is None


def test_all_zeros():
    grid = [
        [0, 0],
        [0, 0],
    ]
    result = solve(grid)
    assert result is not None
    assert len(result) == 0
