from solvers.nurikabe import solve

N = None


def _validate(grid: list[list[int | None]], result: list[list[int]]) -> None:
    height = len(grid)
    width = len(grid[0])

    # Build clue mapping
    clues: dict[tuple[int, int], int] = {}
    clue_ids: dict[tuple[int, int], int] = {}
    island_counter = 0
    for r in range(height):
        for c in range(width):
            if grid[r][c] is not None:
                island_counter += 1
                clues[(r, c)] = grid[r][c]  # type: ignore[assignment]
                clue_ids[(r, c)] = island_counter

    # Check clue cells have correct island id
    for (r, c), iid in clue_ids.items():
        assert result[r][c] == iid, f"Clue cell ({r},{c}) should be island {iid}, got {result[r][c]}"

    # Check island sizes
    for (r, c), iid in clue_ids.items():
        size = sum(1 for rr in range(height) for cc in range(width) if result[rr][cc] == iid)
        assert size == clues[(r, c)], f"Island {iid} at ({r},{c}): expected size {clues[(r, c)]}, got {size}"

    # Check no 2x2 all-black
    for r in range(height - 1):
        for c in range(width - 1):
            block = [result[r + dr][c + dc] for dr in range(2) for dc in range(2)]
            assert not all(v == 0 for v in block), f"2x2 black pool at ({r},{c})"

    # Check connectivity via BFS
    def _bfs_component(start_r: int, start_c: int, value: int) -> set[tuple[int, int]]:
        visited: set[tuple[int, int]] = set()
        stack = [(start_r, start_c)]
        while stack:
            cr, cc = stack.pop()
            if (cr, cc) in visited:
                continue
            if not (0 <= cr < height and 0 <= cc < width):
                continue
            if result[cr][cc] != value:
                continue
            visited.add((cr, cc))
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                stack.append((cr + dr, cc + dc))
        return visited

    # Black connectivity
    black_cells = {(r, c) for r in range(height) for c in range(width) if result[r][c] == 0}
    if black_cells:
        start = next(iter(black_cells))
        component = _bfs_component(start[0], start[1], 0)
        assert component == black_cells, "Black cells are not connected"

    # Island connectivity
    for (r, c), iid in clue_ids.items():
        island_cells = {(rr, cc) for rr in range(height) for cc in range(width) if result[rr][cc] == iid}
        component = _bfs_component(r, c, iid)
        assert component == island_cells, f"Island {iid} at ({r},{c}) is not connected"


def test_solve_3x3():
    """Simple 3x3 puzzle.

    2 . .
    . . .
    . . 2
    """
    grid = [
        [2, N, N],
        [N, N, N],
        [N, N, 2],
    ]
    result = solve(grid)
    assert result is not None
    _validate(grid, result)


def test_solve_5x5():
    """5x5 puzzle.

    5 . . . .
    . . . . .
    . . 5 . .
    . . . . .
    . . . . 3
    """
    grid = [
        [5, N, N, N, N],
        [N, N, N, N, N],
        [N, N, 5, N, N],
        [N, N, N, N, N],
        [N, N, N, N, 3],
    ]
    result = solve(grid)
    assert result is not None
    _validate(grid, result)


def test_solve_single_island():
    """Entire grid is one island — no black cells.

    But connected constraint for black cells should handle empty set.
    """
    grid = [
        [4, N],
        [N, N],
    ]
    result = solve(grid)
    assert result is not None
    _validate(grid, result)
    # All cells belong to island 1
    assert all(result[r][c] == 1 for r in range(2) for c in range(2))


def test_unsolvable():
    """Contradictory clues."""
    grid = [
        [3, N],
        [N, 3],
    ]
    result = solve(grid)
    assert result is None


def test_solve_minimal():
    """1x1 grid — single island of size 1."""
    grid = [[1]]
    result = solve(grid)
    assert result is not None
    assert result == [[1]]
