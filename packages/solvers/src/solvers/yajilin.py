from puzzle_defs import YajilinPuzzle
from puzzle_defs.puzzles.yajilin import DIRECTIONS
Clue = tuple[str, int]
Grid = list[list[Clue | None]]


def solve(grid: Grid) -> list[list[str]] | None:
    puzzle = YajilinPuzzle(grid)
    solution = puzzle.solve()
    if solution is None:
        return None
    return puzzle.result(solution)
