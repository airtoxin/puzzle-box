from __future__ import annotations

from puzzle import Puzzle, Solution, all_different, square_grid
from puzzle.grid import Cell

Grid = list[list[int]]
Clue = tuple[Cell, int]


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
        return solution.grid_values(self.cell_value, 9, 9)

    @classmethod
    def create_empty(cls) -> SudokuPuzzle:
        return cls([[0] * 9 for _ in range(9)])

    @classmethod
    def extract_clues(cls, solution: Solution, puzzle: SudokuPuzzle) -> list[Clue]:
        board = puzzle.board
        return [
            (board.cell(r, c), solution.value(puzzle.cell_value[board.cell(r, c)]))
            for r in range(9)
            for c in range(9)
        ]

    @classmethod
    def build_from_clues(cls, clues: list[Clue]) -> SudokuPuzzle:
        grid: Grid = [[0] * 9 for _ in range(9)]
        for cell, value in clues:
            grid[cell.row][cell.col] = value
        return cls(grid)
