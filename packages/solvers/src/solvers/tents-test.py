from solvers.tents import solve


def _validate(grid, result, row_counts=None, col_counts=None):
    height = len(grid)
    width = len(grid[0])

    trees = set()
    tents = set()
    for r in range(height):
        for c in range(width):
            if grid[r][c] == "T":
                assert result[r][c] == "T"
                trees.add((r, c))
            elif result[r][c] == "A":
                tents.add((r, c))
            else:
                assert result[r][c] == "."

    # Each tent has at least one adjacent tree
    for r, c in tents:
        has_tree = False
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            if (r + dr, c + dc) in trees:
                has_tree = True
        assert has_tree, f"Tent at ({r},{c}) has no adjacent tree"

    # No two tents touch (king adjacency)
    for r, c in tents:
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                assert (r + dr, c + dc) not in tents, f"Tents touch: ({r},{c}) and ({r+dr},{c+dc})"

    # Tree count == tent count (1:1 matching)
    assert len(trees) == len(tents), f"Trees={len(trees)} but tents={len(tents)}"

    # Row/col counts
    if row_counts:
        for r in range(height):
            count = sum(1 for c in range(width) if result[r][c] == "A")
            assert count == row_counts[r], f"Row {r}: expected {row_counts[r]}, got {count}"
    if col_counts:
        for c in range(width):
            count = sum(1 for r in range(height) if result[r][c] == "A")
            assert count == col_counts[c], f"Col {c}: expected {col_counts[c]}, got {count}"


def test_solve_4x4():
    grid = [
        [".", "T", ".", "."],
        [".", ".", ".", "T"],
        ["T", ".", ".", "."],
        [".", ".", "T", "."],
    ]
    result = solve(grid, row_counts=[1, 1, 1, 1], col_counts=[1, 1, 1, 1])
    assert result is not None
    _validate(grid, result, [1, 1, 1, 1], [1, 1, 1, 1])


def test_solve_without_counts():
    grid = [
        [".", "T", "."],
        [".", ".", "."],
        [".", "T", "."],
    ]
    result = solve(grid)
    assert result is not None
    _validate(grid, result)


def test_solve_5x5():
    grid = [
        ["T", ".", ".", ".", "T"],
        [".", ".", ".", ".", "."],
        [".", ".", "T", ".", "."],
        [".", ".", ".", ".", "."],
        ["T", ".", ".", ".", "T"],
    ]
    rc, cc = [0, 2, 0, 3, 0], [2, 0, 1, 0, 2]
    result = solve(grid, row_counts=rc, col_counts=cc)
    assert result is not None
    _validate(grid, result, rc, cc)


def test_unsolvable():
    """Two trees adjacent with no room for two non-touching tents."""
    grid = [
        ["T", "T"],
        [".", "."],
    ]
    # Need 2 tents that don't touch — impossible in 2x2 with 2 trees on top
    result = solve(grid, row_counts=[0, 2], col_counts=[1, 1])
    assert result is None
