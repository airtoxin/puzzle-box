from puzzle import Puzzle, connected, count_eq, square_grid, sum_expr

Grid = list[list[int | None]]


def solve(grid: Grid) -> list[list[int]] | None:
    """Solve a Nurikabe puzzle.

    Args:
        grid: 2D grid of clues. Each cell is a positive integer (island size)
              or None (no clue).

    Returns:
        2D grid of owner values: 0 = black (sea), 1..k = island id.
        Returns None if no solution exists.
    """
    height = len(grid)
    width = len(grid[0])

    clues: dict[tuple[int, int], int] = {}
    for r in range(height):
        for c in range(width):
            if grid[r][c] is not None:
                clues[(r, c)] = grid[r][c]  # type: ignore[assignment]

    p = Puzzle("nurikabe")
    board = square_grid(height, width)

    clue_cells = [board.cell(r, c) for (r, c) in clues]
    clue_ids = {cell: i + 1 for i, cell in enumerate(clue_cells)}
    k = len(clue_cells)

    owner = p.int_var_map("owner", board.cells, 0, k)

    # Clue cells belong to their island
    for cell, island_id in clue_ids.items():
        p.add(owner[cell] == island_id)

    # Each island has exactly the right size
    for cell, island_id in clue_ids.items():
        p.add(count_eq(
            (owner[c] == island_id for c in board.cells),
            clues[(cell.row, cell.col)],
        ))

    # No 2x2 all-black pool
    for window in board.windows(2, 2):
        p.add(sum_expr(owner[c] == 0 for c in window) <= 3)

    # Black cells are connected
    p.add(connected(cells=board.cells, predicate=lambda c: owner[c] == 0))

    # Each island is connected
    for island_id in clue_ids.values():
        p.add(connected(
            cells=board.cells,
            predicate=lambda c, iid=island_id: owner[c] == iid,
        ))

    solution = p.solve()
    if solution is None:
        return None

    return [
        [solution.value(owner[board.cell(r, c)]) for c in range(width)]
        for r in range(height)
    ]
