from puzzle import Puzzle, Solution, at_most_one, connected, square_grid

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

        # Same number in same row: at least one must be black
        for row in board.rows():
            for i in range(len(row)):
                for j in range(i + 1, len(row)):
                    a, b = row[i], row[j]
                    if grid[a.row][a.col] == grid[b.row][b.col]:
                        self.add(self.black[a] | self.black[b])

        # Same number in same column: at least one must be black
        for col in board.cols():
            for i in range(len(col)):
                for j in range(i + 1, len(col)):
                    a, b = col[i], col[j]
                    if grid[a.row][a.col] == grid[b.row][b.col]:
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
