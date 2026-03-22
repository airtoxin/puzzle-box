from puzzle import (
    Puzzle,
    at_most_one,
    connected,
    square_grid,
)

Grid = list[list[int]]


def solve(grid: Grid) -> list[list[bool]] | None:
    """Solve a Hitori puzzle.

    Args:
        grid: 2D grid of positive integers (all cells have numbers).

    Returns:
        2D grid of booleans: True = black (shaded), False = white.
        Returns None if no solution exists.
    """
    height = len(grid)
    width = len(grid[0])

    p = Puzzle("hitori")
    board = square_grid(height, width)

    black = p.bool_var_map("black", board.cells)

    # Same number in same row: at least one must be black
    for row in board.rows():
        for i in range(len(row)):
            for j in range(i + 1, len(row)):
                a, b = row[i], row[j]
                if grid[a.row][a.col] == grid[b.row][b.col]:
                    p.add(black[a] | black[b])

    # Same number in same column: at least one must be black
    for col in board.cols():
        for i in range(len(col)):
            for j in range(i + 1, len(col)):
                a, b = col[i], col[j]
                if grid[a.row][a.col] == grid[b.row][b.col]:
                    p.add(black[a] | black[b])

    # Black cells are not adjacent
    for a, b in board.adjacent_cell_pairs():
        p.add(at_most_one([black[a], black[b]]))

    # White cells are connected
    p.add(connected(cells=board.cells, predicate=lambda c: ~black[c]))

    solution = p.solve()
    if solution is None:
        return None

    return [
        [bool(solution.value(black[board.cell(r, c)])) for c in range(width)]
        for r in range(height)
    ]
