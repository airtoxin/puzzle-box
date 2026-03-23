from puzzle import Puzzle, Solution, all_different, square_grid

Grid = list[list[int]]


class SudokuPuzzle(Puzzle):
    """Sudoku puzzle: fill a 9x9 grid so each row, column, and 3x3 box
    contains the digits 1-9 exactly once."""

    def __init__(self, grid: Grid) -> None:
        super().__init__("sudoku")
        self.grid = grid
        board = square_grid(9, 9)
        self.board = board

        self.cell_value = self.int_var_grid("cell_value", board.cells, 1, 9)

        # Fix given values
        for r in range(9):
            for c in range(9):
                if grid[r][c] != 0:
                    self.add(self.cell_value[board.cell(r, c)] == grid[r][c])

        for row in board.rows():
            self.add(all_different(self.cell_value[c] for c in row))

        for col in board.cols():
            self.add(all_different(self.cell_value[c] for c in col))

        for box in board.blocks(3, 3):
            self.add(all_different(self.cell_value[c] for c in box))

    def result(self, solution: Solution) -> Grid:
        """Format the solution as a 9x9 grid of integers."""
        return solution.grid_values(self.cell_value, 9, 9)
