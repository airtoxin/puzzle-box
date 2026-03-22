from puzzle import Cell

from solvers.shikaku import solve

N = None


def _validate(grid: list[list[int | None]], result: list) -> None:
    height = len(grid)
    width = len(grid[0])

    # All cells covered exactly once
    coverage: dict[Cell, int] = {}
    for rect in result:
        for cell in rect.cells:
            coverage[cell] = coverage.get(cell, 0) + 1
    for r in range(height):
        for c in range(width):
            assert coverage.get(Cell(r, c), 0) == 1, f"Cell ({r},{c}) not covered exactly once"

    # Each rectangle is axis-aligned and has correct area
    for rect in result:
        cells = sorted(rect.cells)
        rows = sorted(set(c.row for c in cells))
        cols = sorted(set(c.col for c in cells))
        assert rows == list(range(rows[0], rows[-1] + 1)), f"Non-contiguous rows"
        assert cols == list(range(cols[0], cols[-1] + 1)), f"Non-contiguous cols"
        assert len(cells) == len(rows) * len(cols), f"Not a rectangle"

    # Each clue cell is in a rectangle with matching area
    for r in range(height):
        for c in range(width):
            clue = grid[r][c]
            if clue is None:
                continue
            clue_cell = Cell(r, c)
            rect = next(rect for rect in result if clue_cell in rect.cells)
            assert rect.clue_cell == clue_cell
            assert len(rect.cells) == clue, f"Clue ({r},{c})={clue} but rect area={len(rect.cells)}"


def test_solve_2x3():
    grid = [
        [2, N, N],
        [N, N, 4],
    ]
    result = solve(grid)
    assert result is not None
    assert len(result) == 2
    _validate(grid, result)


def test_solve_4x4():
    grid = [
        [4, N, N, N],
        [N, N, 4, N],
        [N, N, N, N],
        [4, N, N, 4],
    ]
    result = solve(grid)
    assert result is not None
    assert len(result) == 4
    _validate(grid, result)


def test_solve_5x5():
    grid = [
        [N, N, N, N, N],
        [N, 4, N, 6, N],
        [N, N, N, N, N],
        [N, 9, N, 6, N],
        [N, N, N, N, N],
    ]
    result = solve(grid)
    assert result is not None
    assert len(result) == 4
    _validate(grid, result)


def test_solve_1x1():
    grid = [[1]]
    result = solve(grid)
    assert result is not None
    assert len(result) == 1
    _validate(grid, result)


def test_unsolvable():
    """Clues don't sum to total area."""
    grid = [
        [3, N],
        [N, 3],
    ]
    # 3 + 3 = 6, but board is 2x2 = 4. No valid partition.
    result = solve(grid)
    assert result is None


def test_solve_6x6():
    grid = [
        [4, N, N, 8, N, N],
        [N, N, N, N, N, N],
        [6, N, N, N, N, 6],
        [N, N, N, N, N, N],
        [N, N, N, N, N, N],
        [N, 12, N, N, N, N],
    ]
    result = solve(grid)
    assert result is not None
    _validate(grid, result)
