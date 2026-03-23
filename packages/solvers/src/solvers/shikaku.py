from puzzle_defs import ShikakuPuzzle, ShikakuRect

Grid = list[list[int | None]]


def solve(grid: Grid) -> list[ShikakuRect] | None:
    puzzle = ShikakuPuzzle(grid)
    solution = puzzle.solve()
    if solution is None:
        return None
    return puzzle.result(solution)
