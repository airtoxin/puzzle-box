from puzzle import Puzzle, Solution, at_most_one, connected, square_grid
from puzzle_defs.number_layout import equal_number_pairs

Grid = list[list[int]]


class HitoriPuzzle(Puzzle):
    """Hitori puzzle: shade cells so that no row or column contains
    duplicate unshaded numbers, shaded cells are not adjacent, and
    unshaded cells form a connected group."""

    def __init__(self, grid: Grid) -> None:
        super().__init__("hitori")
        self.grid = grid
        self.height = len(grid)
        self.width = len(grid[0])

        board = square_grid(self.height, self.width)
        self.board = board

        self.black = self.bool_var_map("black", board.cells)

        # The dedicated puzzle and composable fragment share only pair finding;
        # the dedicated constructor's existing input and connectivity policy stay intact.
        for a,b in equal_number_pairs(board,grid):
            self.add(self.black[a] | self.black[b])

        # Black cells are not adjacent
        for a, b in board.adjacent_cell_pairs():
            self.add(at_most_one([self.black[a], self.black[b]]))

        # White cells are connected
        self.add(connected(cells=board.cells, predicate=lambda c: ~self.black[c]))

    def result(self, solution: Solution) -> list[list[bool]]:
        """Return a grid of booleans: True = black (shaded), False = white."""
        return [
            [bool(solution.value(self.black[self.board.cell(r, c)])) for c in range(self.width)]
            for r in range(self.height)
        ]
