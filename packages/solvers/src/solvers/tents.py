from puzzle import (
    Cell,
    Puzzle,
    non_touching,
    square_grid,
    sum_expr,
)

Grid = list[list[str]]  # "T" for tree, "." for empty


def solve(
    grid: Grid,
    row_counts: list[int] | None = None,
    col_counts: list[int] | None = None,
) -> list[list[str]] | None:
    """Solve a Tents puzzle.

    Args:
        grid: 2D grid where "T" is a tree and "." is empty.
        row_counts: Optional number of tents per row.
        col_counts: Optional number of tents per column.

    Returns:
        2D grid: "T" = tree, "A" = tent, "." = grass.
        Returns None if no solution exists.
    """
    height = len(grid)
    width = len(grid[0])

    p = Puzzle("tents")
    board = square_grid(height, width)

    tree_cells = {board.cell(r, c) for r in range(height) for c in range(width) if grid[r][c] == "T"}
    tent_cells = [c for c in board.cells if c not in tree_cells]

    tent = p.bool_var_map("tent", tent_cells)

    # Bipartite matching: each tree paired to exactly one adjacent tent
    match = p.match_var_map(
        "tree_tent",
        left=list(tree_cells),
        right=tent_cells,
        allowed_pairs=[
            (tree, cell)
            for tree in tree_cells
            for cell in board.neighbors(tree)
            if cell not in tree_cells
        ],
    )

    # Each tree matched to exactly 1 tent
    p.add(match.left_degree_eq(1))

    # Each tent cell matched to at most 1 tree
    p.add(match.right_degree_le(1))

    # tent[c] == 1 iff c is matched to some tree
    p.add(match.right_selected_iff(tent))

    # Tents don't touch each other (king adjacency = 8 directions)
    p.add(non_touching(tent, board.king_neighbor_pairs()))

    # Row counts
    if row_counts is not None:
        for r, row_cells in enumerate(board.rows()):
            cells_in_row = [c for c in row_cells if c in tent]
            if cells_in_row:
                p.add(sum_expr(tent[c] for c in cells_in_row) == row_counts[r])

    # Column counts
    if col_counts is not None:
        for c, col_cells in enumerate(board.cols()):
            cells_in_col = [cell for cell in col_cells if cell in tent]
            if cells_in_col:
                p.add(sum_expr(tent[cell] for cell in cells_in_col) == col_counts[c])

    solution = p.solve()
    if solution is None:
        return None

    result: list[list[str]] = []
    for r in range(height):
        row: list[str] = []
        for c in range(width):
            cell = board.cell(r, c)
            if cell in tree_cells:
                row.append("T")
            elif solution.value(tent[cell]):
                row.append("A")
            else:
                row.append(".")
        result.append(row)

    return result
