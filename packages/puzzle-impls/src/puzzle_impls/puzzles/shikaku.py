from puzzle import Puzzle, Solution, exactly_one, square_grid
from puzzle_impls.shikaku import ShikakuRect, enumerate_shikaku_rectangles

Grid = list[list[int | None]]


class ShikakuPuzzle(Puzzle):
    """Shikaku puzzle: partition the grid into rectangles such that each
    rectangle contains exactly one number equal to its area."""

    def __init__(self, grid: Grid) -> None:
        super().__init__("shikaku")
        self.add_feature("region_partition")
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

        self.rects = enumerate_shikaku_rectangles(board, clues)

        self._infeasible = False
        if not self.rects:
            self._infeasible = True
            self.use = self.bool_var_map("use", [])
            return

        self.use = self.bool_var_map("use", self.rects)

        # Each cell is covered by exactly one rectangle
        rects_by_cell: dict = {}
        for rect in self.rects:
            for cell in rect.cells:
                rects_by_cell.setdefault(cell, []).append(rect)

        for cell in board.cells:
            covering = rects_by_cell.get(cell, [])
            if not covering:
                self._infeasible = True
                return
            self.add(exactly_one(self.use[r] for r in covering))

        # Each clue is used by exactly one rectangle
        for cr, cc in clues:
            clue_cell = board.cell(cr, cc)
            clue_rects = [r for r in self.rects if r.clue_cell == clue_cell]
            self.add(exactly_one(self.use[r] for r in clue_rects))

    def result(self, solution: Solution) -> list[ShikakuRect] | None:
        """Return the list of rectangles forming the partition, or None if infeasible."""
        if self._infeasible:
            return None
        return [r for r in self.rects if solution.value(self.use[r])]
