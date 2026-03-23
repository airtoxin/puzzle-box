from puzzle import Puzzle, Solution, single_cycle, square_grid, sum_expr
from puzzle.grid import Cell, Vertex

# Direction vectors: (dr, dc)
DIRECTIONS = {
    "up": (-1, 0),
    "down": (1, 0),
    "left": (0, -1),
    "right": (0, 1),
}

Clue = tuple[str, int]  # (direction, count)
Grid = list[list[Clue | None]]


class YajilinPuzzle(Puzzle):
    """Yajilin puzzle: shade cells and draw a single loop through the
    remaining non-clue cells, respecting arrow clue counts."""

    def __init__(self, grid: Grid) -> None:
        super().__init__("yajilin")
        self.grid = grid
        self.height = len(grid)
        self.width = len(grid[0])

        board = square_grid(self.height, self.width)
        self.board = board

        # Identify clue cells
        self.clue_cells: set[Cell] = set()
        for r in range(self.height):
            for c in range(self.width):
                if grid[r][c] is not None:
                    self.clue_cells.add(board.cell(r, c))

        non_clue_cells = [c for c in board.cells if c not in self.clue_cells]

        # Variables
        self.is_black = self.bool_var_map("is_black", non_clue_cells)

        # Dual grid: vertices = cells, edges = cell adjacencies
        dual = square_grid(self.height - 1, self.width - 1)
        self.edge_on = self.bool_var_map("edge_on", dual.edges)

        # --- Constraints ---

        # 1. Arrow clues: count black cells in direction
        self._infeasible = False
        for r in range(self.height):
            for c in range(self.width):
                clue = grid[r][c]
                if clue is None:
                    continue
                direction, count = clue
                dr, dc = DIRECTIONS[direction]
                # Collect non-clue cells in the ray
                targets: list[Cell] = []
                nr, nc = r + dr, c + dc
                while 0 <= nr < self.height and 0 <= nc < self.width:
                    cell = board.cell(nr, nc)
                    if cell not in self.clue_cells:
                        targets.append(cell)
                    nr += dr
                    nc += dc
                if targets:
                    self.add(sum_expr(self.is_black[t] for t in targets) == count)
                else:
                    if count != 0:
                        self._infeasible = True

        # 2. Black cells not adjacent
        non_clue_set = set(non_clue_cells)
        for c in non_clue_cells:
            for n in board.neighbors(c):
                if n in non_clue_set and c < n:
                    self.add(sum_expr([self.is_black[c], self.is_black[n]]) <= 1)

        # 3. Clue cells: all incident edges off
        for c in self.clue_cells:
            v = Vertex(c.row, c.col)
            for e in dual.edges_incident(v):
                self.add(self.edge_on[e] == 0)

        # 4. Non-clue cells: black (deg=0) or loop (deg=2)
        for c in non_clue_cells:
            v = Vertex(c.row, c.col)
            incident = dual.edges_incident(v)
            terms = [self.edge_on[e] for e in incident] + [self.is_black[c], self.is_black[c]]
            self.add(sum_expr(terms) == 2)

        # 5. Single cycle
        self.add(single_cycle(self.edge_on, dual))

    def result(self, solution: Solution) -> list[list[str]] | None:
        """Return a grid of cell states: 'black', 'loop', or 'clue'.

        Returns None if the puzzle was detected as infeasible during construction.
        """
        if self._infeasible:
            return None

        result: list[list[str]] = []
        for r in range(self.height):
            row: list[str] = []
            for c in range(self.width):
                cell = self.board.cell(r, c)
                if cell in self.clue_cells:
                    row.append("clue")
                elif solution.value(self.is_black[cell]):
                    row.append("black")
                else:
                    row.append("loop")
            result.append(row)

        return result
