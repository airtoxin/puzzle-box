from puzzle_impls import HitoriPuzzle

Grid = list[list[int]]


def solve(grid: Grid) -> list[list[bool]] | None:
    puzzle = HitoriPuzzle(grid)
    solution = puzzle.solve()
    if solution is None:
        return None
    return puzzle.result(solution)
