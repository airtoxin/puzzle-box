from puzzle import (
    Cell,
    Placement,
    Polyomino,
    Puzzle,
    enumerate_placements,
    exactly_one,
    square_grid,
    sum_expr,
)
from puzzle.grid import Edge


def solve(
    height: int,
    width: int,
    pieces: list[Polyomino],
    max_uses: dict[str, int] | None = None,
    forbidden_internal_edges: set[Edge] | None = None,
) -> list[Placement] | None:
    """Solve a tiling puzzle: fill the board with given pieces.

    Args:
        height: Board height.
        width: Board width.
        pieces: List of polyomino pieces to use.
        max_uses: Optional per-piece usage limit (by piece name).
                  If None, each piece can be used unlimited times.
                  Use {name: 1} to restrict a piece to one use.
        forbidden_internal_edges: Edges (walls) that pieces cannot cross.

    Returns:
        List of chosen placements, or None if no solution exists.
    """
    p = Puzzle("tiling")
    board = square_grid(height, width)
    walls = forbidden_internal_edges or set()

    # Enumerate all valid placements for all pieces
    all_placements: list[Placement] = []
    placements_by_piece: dict[str, list[Placement]] = {}
    for piece in pieces:
        pls = enumerate_placements(board, piece, walls)
        all_placements.extend(pls)
        placements_by_piece.setdefault(piece.name, []).extend(pls)

    if not all_placements:
        return None

    use = p.bool_var_map("use", all_placements)

    # Each cell is covered by exactly one placement
    placements_by_cell: dict[Cell, list[Placement]] = {}
    for pl in all_placements:
        for cell in pl.cells:
            placements_by_cell.setdefault(cell, []).append(pl)

    for cell in board.cells:
        covering = placements_by_cell.get(cell, [])
        if not covering:
            return None  # Cell cannot be covered
        p.add(exactly_one(use[pl] for pl in covering))

    # Per-piece usage limits
    if max_uses:
        for piece_name, limit in max_uses.items():
            pls = placements_by_piece.get(piece_name, [])
            if pls:
                p.add(sum_expr(use[pl] for pl in pls) <= limit)

    solution = p.solve()
    if solution is None:
        return None

    return [pl for pl in all_placements if solution.value(use[pl])]
