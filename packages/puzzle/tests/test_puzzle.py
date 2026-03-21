from puzzle import Puzzle, all_different, square_grid


EASY_PUZZLE = [
    [5, 3, 0, 0, 7, 0, 0, 0, 0],
    [6, 0, 0, 1, 9, 5, 0, 0, 0],
    [0, 9, 8, 0, 0, 0, 0, 6, 0],
    [8, 0, 0, 0, 6, 0, 0, 0, 3],
    [4, 0, 0, 8, 0, 3, 0, 0, 1],
    [7, 0, 0, 0, 2, 0, 0, 0, 6],
    [0, 6, 0, 0, 0, 0, 2, 8, 0],
    [0, 0, 0, 4, 1, 9, 0, 0, 5],
    [0, 0, 0, 0, 8, 0, 0, 7, 9],
]


def _define_sudoku(givens: list[list[int]]) -> Puzzle:
    p = Puzzle("sudoku")

    board = square_grid(9, 9)
    cell_value = p.int_var_grid("cell_value", board.cells, 1, 9)

    for row in board.rows():
        p.add(all_different(cell_value[c] for c in row))

    for col in board.cols():
        p.add(all_different(cell_value[c] for c in col))

    for box in board.blocks(3, 3):
        p.add(all_different(cell_value[c] for c in box))

    for r in range(9):
        for c in range(9):
            if givens[r][c] != 0:
                p.add(cell_value[board.cell(r, c)] == givens[r][c])

    return p, board, cell_value


def _is_valid_solution(grid: list[list[int]]) -> bool:
    for r in range(9):
        if sorted(grid[r]) != list(range(1, 10)):
            return False
    for c in range(9):
        if sorted(grid[r][c] for r in range(9)) != list(range(1, 10)):
            return False
    for box_r in range(3):
        for box_c in range(3):
            vals = [
                grid[box_r * 3 + r][box_c * 3 + c]
                for r in range(3)
                for c in range(3)
            ]
            if sorted(vals) != list(range(1, 10)):
                return False
    return True


def test_solve_sudoku():
    p, board, cell_value = _define_sudoku(EASY_PUZZLE)
    solution = p.solve()
    assert solution is not None
    result = solution.grid_values(cell_value, 9, 9)
    assert _is_valid_solution(result)


def test_preserves_givens():
    p, board, cell_value = _define_sudoku(EASY_PUZZLE)
    solution = p.solve()
    assert solution is not None
    for r in range(9):
        for c in range(9):
            if EASY_PUZZLE[r][c] != 0:
                assert solution.value(cell_value[board.cell(r, c)]) == EASY_PUZZLE[r][c]


def test_unsolvable():
    p = Puzzle("bad")
    board = square_grid(9, 9)
    cell_value = p.int_var_grid("cell_value", board.cells, 1, 9)

    for row in board.rows():
        p.add(all_different(cell_value[c] for c in row))

    # Conflicting constraints: same row, same value
    p.add(cell_value[board.cell(0, 0)] == 5)
    p.add(cell_value[board.cell(0, 1)] == 5)

    assert p.solve() is None


def test_fixed_values():
    """Test the exact DSL pattern from the spec."""
    p = Puzzle("sudoku")
    board = square_grid(9, 9)
    cell_value = p.int_var_grid("cell_value", board.cells, 1, 9)

    for row in board.rows():
        p.add(all_different(cell_value[c] for c in row))
    for col in board.cols():
        p.add(all_different(cell_value[c] for c in col))
    for box in board.blocks(3, 3):
        p.add(all_different(cell_value[c] for c in box))

    p.add(cell_value[board.cell(0, 0)] == 5)
    p.add(cell_value[board.cell(0, 1)] == 3)

    solution = p.solve()
    assert solution is not None
    assert solution.value(cell_value[board.cell(0, 0)]) == 5
    assert solution.value(cell_value[board.cell(0, 1)]) == 3
