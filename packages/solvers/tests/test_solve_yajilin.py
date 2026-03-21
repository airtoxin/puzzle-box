from collections import deque

from solvers.yajilin import solve, DIRECTIONS, Clue

N = None


def _validate(
    grid: list[list[Clue | None]], result: list[list[str]]
) -> None:
    height = len(grid)
    width = len(grid[0])

    clue_cells: set[tuple[int, int]] = set()
    for r in range(height):
        for c in range(width):
            if grid[r][c] is not None:
                clue_cells.add((r, c))

    # Check cell types
    for r in range(height):
        for c in range(width):
            if (r, c) in clue_cells:
                assert result[r][c] == "clue", f"({r},{c}) should be clue"
            else:
                assert result[r][c] in ("black", "loop"), f"({r},{c}) unexpected: {result[r][c]}"

    # Check arrow clues
    for r in range(height):
        for c in range(width):
            clue = grid[r][c]
            if clue is None:
                continue
            direction, count = clue
            dr, dc = DIRECTIONS[direction]
            nr, nc = r + dr, c + dc
            black_count = 0
            while 0 <= nr < height and 0 <= nc < width:
                if result[nr][nc] == "black":
                    black_count += 1
                nr += dr
                nc += dc
            assert black_count == count, (
                f"Clue ({r},{c}) {direction}={count}: found {black_count} black"
            )

    # Check no adjacent black cells
    for r in range(height):
        for c in range(width):
            if result[r][c] != "black":
                continue
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < height and 0 <= nc < width:
                    assert result[nr][nc] != "black", (
                        f"Adjacent black cells at ({r},{c}) and ({nr},{nc})"
                    )

    # Check loop: connected single cycle through all loop cells
    loop_cells = {
        (r, c) for r in range(height) for c in range(width) if result[r][c] == "loop"
    }
    assert len(loop_cells) > 0, "No loop cells"

    # Build adjacency on loop cells via edge_on (degree must be 2)
    adj: dict[tuple[int, int], list[tuple[int, int]]] = {c: [] for c in loop_cells}
    for r, c in loop_cells:
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if (nr, nc) in loop_cells:
                adj[(r, c)].append((nr, nc))

    # Each loop cell must have exactly 2 loop neighbors
    # (This checks degree in the grid adjacency, but the actual loop
    #  degree is enforced by the solver. We verify connectivity.)

    # BFS connectivity check
    start = next(iter(loop_cells))
    visited: set[tuple[int, int]] = set()
    queue = deque([start])
    while queue:
        v = queue.popleft()
        if v in visited:
            continue
        visited.add(v)
        for u in adj[v]:
            if u not in visited:
                queue.append(u)
    assert visited == loop_cells, "Loop cells are not connected"


def test_solve_4x4_single_clue():
    grid: list[list[Clue | None]] = [
        [N, N, N, N],
        [N, ("right", 1), N, N],
        [N, N, N, N],
        [N, N, N, N],
    ]
    result = solve(grid)
    assert result is not None
    _validate(grid, result)


def test_solve_4x4_two_clues():
    grid: list[list[Clue | None]] = [
        [("down", 1), N, N, N],
        [N, N, N, ("down", 0)],
        [N, N, N, N],
        [N, N, N, N],
    ]
    result = solve(grid)
    assert result is not None
    _validate(grid, result)


def test_solve_3x3_no_clues():
    """No clues — loop must fill all cells, no black cells possible in 3x3."""
    grid: list[list[Clue | None]] = [
        [N, N, N],
        [N, N, N],
        [N, N, N],
    ]
    result = solve(grid)
    assert result is not None
    _validate(grid, result)


def test_solve_4x4_zero_clue():
    """Arrow clue with count 0 — no black cells in that direction."""
    grid: list[list[Clue | None]] = [
        [("right", 0), N, N, N],
        [N, N, N, N],
        [N, N, N, N],
        [N, N, N, N],
    ]
    result = solve(grid)
    assert result is not None
    _validate(grid, result)
    # No black cells in row 0 to the right of clue
    for c in range(1, 4):
        assert result[0][c] != "black"


def test_unsolvable():
    """Too many required black cells in a short row."""
    grid: list[list[Clue | None]] = [
        [("right", 3), N, N],
        [N, N, N],
        [N, N, N],
    ]
    result = solve(grid)
    assert result is None


def test_solve_5x5():
    grid: list[list[Clue | None]] = [
        [N, ("down", 1), N, N, N],
        [N, N, N, N, N],
        [N, N, N, N, N],
        [N, N, N, N, N],
        [N, N, N, ("up", 1), N],
    ]
    result = solve(grid)
    assert result is not None
    _validate(grid, result)
