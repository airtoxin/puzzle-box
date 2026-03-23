from puzzle import Puzzle, Solution, one_of, single_cycle, square_grid, sum_expr
from puzzle.grid import Edge

Grid = list[list[int | None]]


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

        # Clue constraints
        for cell in board.cells:
            clue = grid[cell.row][cell.col]
            if clue is not None:
                self.add(sum_expr(self.edge_on[e] for e in board.edges_around(cell)) == clue)

        # Vertex degree: 0 or 2
        for v in board.vertices:
            deg = sum_expr(self.edge_on[e] for e in board.edges_incident(v))
            self.add(one_of(deg == 0, deg == 2))

        # Single loop
        self.add(single_cycle(self.edge_on, board))

    def result(self, solution: Solution) -> set[Edge]:
        """Return the set of edges that form the solution loop."""
        return {e for e in self.board.edges if solution.value(self.edge_on[e])}
