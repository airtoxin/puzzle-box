from __future__ import annotations

from puzzle import Puzzle, Solution, one_of, single_cycle, square_grid, sum_expr
from puzzle.grid import Cell, Edge

Grid = list[list[int | None]]
Clue = tuple[Cell, int]


class SlitherlinkPuzzle(Puzzle):
    """Slitherlink puzzle: draw a single closed loop on the grid edges
    such that each numbered cell has exactly that many edges used."""

    def __init__(self, grid: Grid) -> None:
        super().__init__("slitherlink")
        self.grid = grid
        rows = len(grid)
        cols = len(grid[0])
        self.rows = rows
        self.cols = cols

        board = square_grid(rows, cols)
        self.board = board

        self.edge_on = self.bool_var_map("edge_on", board.edges)

        for cell in board.cells:
            clue = grid[cell.row][cell.col]
            if clue is not None:
                self.add(sum_expr(self.edge_on[e] for e in board.edges_around(cell)) == clue)

        for v in board.vertices:
            deg = sum_expr(self.edge_on[e] for e in board.edges_incident(v))
            self.add(one_of(deg == 0, deg == 2))

        self.add(single_cycle(self.edge_on, board))

    def result(self, solution: Solution) -> set[Edge]:
        return {e for e in self.board.edges if solution.value(self.edge_on[e])}

    @classmethod
    def create_empty(cls, rows: int = 5, cols: int = 5) -> SlitherlinkPuzzle:
        return cls([[None] * cols for _ in range(rows)])

    @classmethod
    def extract_clues(cls, solution: Solution, puzzle: SlitherlinkPuzzle) -> list[Clue]:
        edges = puzzle.result(solution)
        clues: list[Clue] = []
        for cell in puzzle.board.cells:
            count = sum(1 for e in puzzle.board.edges_around(cell) if e in edges)
            clues.append((cell, count))
        return clues

    @classmethod
    def build_from_clues(
        cls, clues: list[Clue], rows: int = 5, cols: int = 5
    ) -> SlitherlinkPuzzle:
        grid: Grid = [[None] * cols for _ in range(rows)]
        for cell, count in clues:
            grid[cell.row][cell.col] = count
        return cls(grid)
