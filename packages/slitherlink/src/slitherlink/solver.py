from puzzle import Puzzle, one_of, single_cycle, square_grid, sum_expr
from puzzle.grid import Edge

Grid = list[list[int | None]]


def solve(grid: Grid) -> set[Edge] | None:
    """Solve a Slitherlink puzzle.

    Args:
        grid: 2D grid of clues. Each cell is 0-4 or None (no clue).
              grid[row][col] indicates how many edges surround that cell.

    Returns:
        Set of edges that form the solution loop, or None if no solution exists.
    """
    rows = len(grid)
    cols = len(grid[0])

    p = Puzzle("slitherlink")
    board = square_grid(rows, cols)

    edge_on = p.bool_var_map("edge_on", board.edges)

    # Clue constraints
    for cell in board.cells:
        clue = grid[cell.row][cell.col]
        if clue is not None:
            p.add(sum_expr(edge_on[e] for e in board.edges_around(cell)) == clue)

    # Vertex degree: 0 or 2
    for v in board.vertices:
        deg = sum_expr(edge_on[e] for e in board.edges_incident(v))
        p.add(one_of(deg == 0, deg == 2))

    # Single loop
    p.add(single_cycle(edge_on, board))

    solution = p.solve()
    if solution is None:
        return None

    return {e for e in board.edges if solution.value(edge_on[e])}
