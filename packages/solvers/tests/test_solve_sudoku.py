from solvers.sudoku import solve


def _is_valid_solution(grid: list[list[int]]) -> bool:
    """Check that the grid satisfies all sudoku constraints."""
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

# https://en.wikipedia.org/wiki/Sudoku_solving_algorithms (hard puzzle)
HARD_PUZZLE = [
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 3, 0, 8, 5],
    [0, 0, 1, 0, 2, 0, 0, 0, 0],
    [0, 0, 0, 5, 0, 7, 0, 0, 0],
    [0, 0, 4, 0, 0, 0, 1, 0, 0],
    [0, 9, 0, 0, 0, 0, 0, 0, 0],
    [5, 0, 0, 0, 0, 0, 0, 7, 3],
    [0, 0, 2, 0, 1, 0, 0, 0, 0],
    [0, 0, 0, 0, 4, 0, 0, 0, 9],
]


def test_solve_easy_puzzle():
    result = solve(EASY_PUZZLE)
    assert result is not None
    assert _is_valid_solution(result)


def test_solve_hard_puzzle():
    result = solve(HARD_PUZZLE)
    assert result is not None
    assert _is_valid_solution(result)


def test_preserves_given_values():
    result = solve(EASY_PUZZLE)
    assert result is not None
    for r in range(9):
        for c in range(9):
            if EASY_PUZZLE[r][c] != 0:
                assert result[r][c] == EASY_PUZZLE[r][c]


def test_empty_grid():
    empty = [[0] * 9 for _ in range(9)]
    result = solve(empty)
    assert result is not None
    assert _is_valid_solution(result)


def test_already_solved():
    solved = [
        [5, 3, 4, 6, 7, 8, 9, 1, 2],
        [6, 7, 2, 1, 9, 5, 3, 4, 8],
        [1, 9, 8, 3, 4, 2, 5, 6, 7],
        [8, 5, 9, 7, 6, 1, 4, 2, 3],
        [4, 2, 6, 8, 5, 3, 7, 9, 1],
        [7, 1, 3, 9, 2, 4, 8, 5, 6],
        [9, 6, 1, 5, 3, 7, 2, 8, 4],
        [2, 8, 7, 4, 1, 9, 6, 3, 5],
        [3, 4, 5, 2, 8, 6, 1, 7, 9],
    ]
    result = solve(solved)
    assert result is not None
    assert result == solved


def test_unsolvable_returns_none():
    # Row has duplicate 5s — impossible
    invalid = [[0] * 9 for _ in range(9)]
    invalid[0][0] = 5
    invalid[0][1] = 5
    result = solve(invalid)
    assert result is None
