from puzzle.grid import Edge
from puzzle_defs import SlitherlinkPuzzle

Grid = list[list[int | None]]


def solve(grid: Grid) -> set[Edge] | None:
    puzzle = SlitherlinkPuzzle(grid)
    solution = puzzle.solve()
    if solution is None:
        return None
    return puzzle.result(solution)
