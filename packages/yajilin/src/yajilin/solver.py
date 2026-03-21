from puzzle import Puzzle, single_cycle, square_grid, sum_expr
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


def solve(grid: Grid) -> list[list[str]] | None:
    """Solve a Yajilin puzzle.

    Args:
        grid: 2D grid where each cell is either None (empty) or
              a (direction, count) tuple for arrow clues.
              direction is one of "up", "down", "left", "right".

    Returns:
        2D grid of cell states:
        - "black" for shaded cells
        - "loop" for loop cells
        - "clue" for clue cells
        Returns None if no solution exists.
    """
    height = len(grid)
    width = len(grid[0])

    p = Puzzle("yajilin")
    board = square_grid(height, width)

    # Identify clue cells
    clue_cells: set[Cell] = set()
    for r in range(height):
        for c in range(width):
            if grid[r][c] is not None:
                clue_cells.add(board.cell(r, c))

    non_clue_cells = [c for c in board.cells if c not in clue_cells]

    # Variables
    is_black = p.bool_var_map("is_black", non_clue_cells)

    # Dual grid: vertices = cells, edges = cell adjacencies
    dual = square_grid(height - 1, width - 1)
    edge_on = p.bool_var_map("edge_on", dual.edges)

    # --- Constraints ---

    # 1. Arrow clues: count black cells in direction
    for r in range(height):
        for c in range(width):
            clue = grid[r][c]
            if clue is None:
                continue
            direction, count = clue
            dr, dc = DIRECTIONS[direction]
            # Collect non-clue cells in the ray
            targets: list[Cell] = []
            nr, nc = r + dr, c + dc
            while 0 <= nr < height and 0 <= nc < width:
                cell = board.cell(nr, nc)
                if cell not in clue_cells:
                    targets.append(cell)
                nr += dr
                nc += dc
            if targets:
                p.add(sum_expr(is_black[t] for t in targets) == count)
            else:
                # No targets in direction — count must be 0
                if count != 0:
                    return None

    # 2. Black cells not adjacent
    non_clue_set = set(non_clue_cells)
    for c in non_clue_cells:
        for n in board.neighbors(c):
            if n in non_clue_set and c < n:
                p.add(sum_expr([is_black[c], is_black[n]]) <= 1)

    # 3. Clue cells: all incident edges off
    for c in clue_cells:
        v = Vertex(c.row, c.col)
        for e in dual.edges_incident(v):
            p.add(edge_on[e] == 0)

    # 4. Non-clue cells: black (deg=0) or loop (deg=2)
    #    deg + 2 * is_black == 2
    for c in non_clue_cells:
        v = Vertex(c.row, c.col)
        incident = dual.edges_incident(v)
        terms = [edge_on[e] for e in incident] + [is_black[c], is_black[c]]
        p.add(sum_expr(terms) == 2)

    # 5. Single cycle
    p.add(single_cycle(edge_on, dual))

    solution = p.solve()
    if solution is None:
        return None

    result: list[list[str]] = []
    for r in range(height):
        row: list[str] = []
        for c in range(width):
            cell = board.cell(r, c)
            if cell in clue_cells:
                row.append("clue")
            elif solution.value(is_black[cell]):
                row.append("black")
            else:
                row.append("loop")
        result.append(row)

    return result
