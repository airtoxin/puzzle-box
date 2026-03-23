from puzzle_defs import SudokuPuzzle

Grid = list[list[int]]


def solve(grid: Grid) -> Grid | None:
    puzzle = SudokuPuzzle(grid)
    solution = puzzle.solve()
    if solution is None:
        return None
    return puzzle.result(solution)
