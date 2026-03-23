from puzzle import Puzzle, Solution, non_touching, square_grid, sum_expr
from puzzle.grid import Cell

Grid = list[list[str]]  # "T" for tree, "." for empty


class TentsPuzzle(Puzzle):
    """Tents puzzle: place tents adjacent to trees such that each tree
    pairs with exactly one tent, tents don't touch diagonally, and
    row/column tent counts are satisfied."""

    def __init__(
        self,
        grid: Grid,
        row_counts: list[int] | None = None,
        col_counts: list[int] | None = None,
    ) -> None:
        super().__init__("tents")
        self.grid = grid
        self.height = len(grid)
        self.width = len(grid[0])

        board = square_grid(self.height, self.width)
        self.board = board

        self.tree_cells = {
            board.cell(r, c)
            for r in range(self.height)
            for c in range(self.width)
            if grid[r][c] == "T"
        }
        tent_cells = [c for c in board.cells if c not in self.tree_cells]

        self.tent = self.bool_var_map("tent", tent_cells)

        # Bipartite matching: each tree paired to exactly one adjacent tent
        self.match = self.match_var_map(
            "tree_tent",
            left=list(self.tree_cells),
            right=tent_cells,
            allowed_pairs=[
                (tree, cell)
                for tree in self.tree_cells
                for cell in board.neighbors(tree)
                if cell not in self.tree_cells
            ],
        )

        # Each tree matched to exactly 1 tent
        self.add(self.match.left_degree_eq(1))

        # Each tent cell matched to at most 1 tree
        self.add(self.match.right_degree_le(1))

        # tent[c] == 1 iff c is matched to some tree
        self.add(self.match.right_selected_iff(self.tent))

        # Tents don't touch each other (king adjacency = 8 directions)
        self.add(non_touching(self.tent, board.king_neighbor_pairs()))

        # Row counts
        if row_counts is not None:
            for r, row_cells in enumerate(board.rows()):
                cells_in_row = [c for c in row_cells if c in self.tent]
                if cells_in_row:
                    self.add(sum_expr(self.tent[c] for c in cells_in_row) == row_counts[r])

        # Column counts
        if col_counts is not None:
            for c_idx, col_cells in enumerate(board.cols()):
                cells_in_col = [cell for cell in col_cells if cell in self.tent]
                if cells_in_col:
                    self.add(sum_expr(self.tent[cell] for cell in cells_in_col) == col_counts[c_idx])

    def result(self, solution: Solution) -> list[list[str]]:
        """Return a grid: 'T' = tree, 'A' = tent, '.' = grass."""
        result: list[list[str]] = []
        for r in range(self.height):
            row: list[str] = []
            for c in range(self.width):
                cell = self.board.cell(r, c)
                if cell in self.tree_cells:
                    row.append("T")
                elif solution.value(self.tent[cell]):
                    row.append("A")
                else:
                    row.append(".")
            result.append(row)
        return result
