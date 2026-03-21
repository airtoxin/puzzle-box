from puzzle import Puzzle, all_different, square_grid

Grid = list[list[int]]


def solve(grid: Grid) -> Grid | None:
    """Solve a 9x9 sudoku puzzle using CP-SAT.

    Args:
        grid: 9x9 grid where 0 represents an empty cell.

    Returns:
        Solved 9x9 grid, or None if no solution exists.
    """
    p = Puzzle("sudoku")
    board = square_grid(9, 9)

    cell_value = p.int_var_grid("cell_value", board.cells, 1, 9)

    # Fix given values
    for r in range(9):
        for c in range(9):
            if grid[r][c] != 0:
                p.add(cell_value[board.cell(r, c)] == grid[r][c])

    for row in board.rows():
        p.add(all_different(cell_value[c] for c in row))

    for col in board.cols():
        p.add(all_different(cell_value[c] for c in col))

    for box in board.blocks(3, 3):
        p.add(all_different(cell_value[c] for c in box))

    solution = p.solve()
    if solution is None:
        return None

    return solution.grid_values(cell_value, 9, 9)
