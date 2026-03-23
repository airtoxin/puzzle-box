from puzzle_impls import NurikabePuzzle

Grid = list[list[int | None]]


def solve(grid: Grid) -> list[list[int]] | None:
    puzzle = NurikabePuzzle(grid)
    solution = puzzle.solve()
    if solution is None:
        return None
    return puzzle.result(solution)
