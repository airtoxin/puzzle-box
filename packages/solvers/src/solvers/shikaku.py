from puzzle import (
    Puzzle,
    enumerate_shikaku_rectangles,
    exactly_one,
    square_grid,
)
from puzzle.shikaku import ShikakuRect

Grid = list[list[int | None]]


def solve(grid: Grid) -> list[ShikakuRect] | None:
    """Solve a Shikaku (四角に切れ) puzzle.

    Args:
        grid: 2D grid where each cell is a positive integer (clue) or None.

    Returns:
        List of ShikakuRect representing the rectangle partition,
        or None if no solution exists.
    """
    height = len(grid)
    width = len(grid[0])

    clues: dict[tuple[int, int], int] = {}
    for r in range(height):
        for c in range(width):
            if grid[r][c] is not None:
                clues[(r, c)] = grid[r][c]  # type: ignore[assignment]

    p = Puzzle("shikaku")
    p.add_feature("region_partition")
    board = square_grid(height, width)

    rects = enumerate_shikaku_rectangles(board, clues)

    if not rects:
        return None

    use = p.bool_var_map("use", rects)

    # Each cell is covered by exactly one rectangle
    rects_by_cell: dict = {}
    for rect in rects:
        for cell in rect.cells:
            rects_by_cell.setdefault(cell, []).append(rect)

    for cell in board.cells:
        covering = rects_by_cell.get(cell, [])
        if not covering:
            return None
        p.add(exactly_one(use[r] for r in covering))

    # Each clue is used by exactly one rectangle
    for cr, cc in clues:
        clue_cell = board.cell(cr, cc)
        clue_rects = [r for r in rects if r.clue_cell == clue_cell]
        p.add(exactly_one(use[r] for r in clue_rects))

    solution = p.solve()
    if solution is None:
        return None

    return [r for r in rects if solution.value(use[r])]
