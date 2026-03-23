from puzzle import Cell, Puzzle, Solution, exactly_one, square_grid, sum_expr
from puzzle.grid import Edge
from puzzle_impls.polyomino import Placement, Polyomino, enumerate_placements


class TilingPuzzle(Puzzle):
    """Tiling puzzle: fill a board with polyomino pieces such that every
    target cell is covered by exactly one placement."""

    def __init__(
        self,
        height: int,
        width: int,
        pieces: list[Polyomino],
        max_uses: dict[str, int] | None = None,
        forbidden_internal_edges: set[Edge] | None = None,
        board_cells: set[Cell] | None = None,
    ) -> None:
        super().__init__("tiling")
        self.add_feature("region_partition")
        self.add_feature("shape_class")
        self.height = height
        self.width = width

        board = square_grid(height, width)
        self.board = board
        walls = forbidden_internal_edges or set()
        target_cells = board_cells if board_cells is not None else set(board.cells)

        # Enumerate all valid placements for all pieces
        self.all_placements: list[Placement] = []
        placements_by_piece: dict[str, list[Placement]] = {}
        for piece in pieces:
            pls = enumerate_placements(board, piece, walls)
            for pl in pls:
                if pl.cells.issubset(target_cells):
                    self.all_placements.append(pl)
                    placements_by_piece.setdefault(piece.name, []).append(pl)

        self._infeasible = False
        if not self.all_placements:
            self._infeasible = True
            # Create empty use map; solve() will return None
            self.use = self.bool_var_map("use", [])
            return

        self.use = self.bool_var_map("use", self.all_placements)

        # Each target cell is covered by exactly one placement
        placements_by_cell: dict[Cell, list[Placement]] = {}
        for pl in self.all_placements:
            for cell in pl.cells:
                placements_by_cell.setdefault(cell, []).append(pl)

        for cell in target_cells:
            covering = placements_by_cell.get(cell, [])
            if not covering:
                self._infeasible = True
                return
            self.add(exactly_one(self.use[pl] for pl in covering))

        # Per-piece usage limits
        if max_uses:
            for piece_name, limit in max_uses.items():
                pls = placements_by_piece.get(piece_name, [])
                if pls:
                    self.add(sum_expr(self.use[pl] for pl in pls) <= limit)

    def result(self, solution: Solution) -> list[Placement] | None:
        """Return the list of chosen placements, or None if infeasible."""
        if self._infeasible:
            return None
        return [pl for pl in self.all_placements if solution.value(self.use[pl])]
