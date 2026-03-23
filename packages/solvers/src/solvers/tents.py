from puzzle_impls import TentsPuzzle

Grid = list[list[str]]


def solve(
    grid: Grid,
    row_counts: list[int] | None = None,
    col_counts: list[int] | None = None,
) -> list[list[str]] | None:
    puzzle = TentsPuzzle(grid, row_counts=row_counts, col_counts=col_counts)
    solution = puzzle.solve()
    if solution is None:
        return None
    return puzzle.result(solution)
