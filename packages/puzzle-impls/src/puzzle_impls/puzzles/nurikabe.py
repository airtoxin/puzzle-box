from puzzle import Puzzle, Solution, connected, count_eq, square_grid, sum_expr

Grid = list[list[int | None]]


class NurikabePuzzle(Puzzle):
    """Nurikabe puzzle: shade cells to form a connected sea while each
    numbered cell anchors an island of that size."""

    def __init__(self, grid: Grid) -> None:
        super().__init__("nurikabe")
        self.grid = grid
        self.height = len(grid)
        self.width = len(grid[0])

        clues: dict[tuple[int, int], int] = {}
        for r in range(self.height):
            for c in range(self.width):
                if grid[r][c] is not None:
                    clues[(r, c)] = grid[r][c]  # type: ignore[assignment]

        board = square_grid(self.height, self.width)
        self.board = board

        clue_cells = [board.cell(r, c) for (r, c) in clues]
        clue_ids = {cell: i + 1 for i, cell in enumerate(clue_cells)}
        k = len(clue_cells)

        self.owner = self.int_var_map("owner", board.cells, 0, k)

        # Clue cells belong to their island
        for cell, island_id in clue_ids.items():
            self.add(self.owner[cell] == island_id)

        # Each island has exactly the right size
        for cell, island_id in clue_ids.items():
            self.add(count_eq(
                (self.owner[c] == island_id for c in board.cells),
                clues[(cell.row, cell.col)],
            ))

        # No 2x2 all-black pool
        for window in board.windows(2, 2):
            self.add(sum_expr(self.owner[c] == 0 for c in window) <= 3)

        # Black cells are connected
        self.add(connected(cells=board.cells, predicate=lambda c: self.owner[c] == 0))

        # Each island is connected
        for island_id in clue_ids.values():
            self.add(connected(
                cells=board.cells,
                predicate=lambda c, iid=island_id: self.owner[c] == iid,
            ))

    def result(self, solution: Solution) -> list[list[int]]:
        """Return a grid of owner values: 0 = sea, 1..k = island id."""
        return [
            [solution.value(self.owner[self.board.cell(r, c)]) for c in range(self.width)]
            for r in range(self.height)
        ]
