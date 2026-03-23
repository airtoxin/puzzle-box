from puzzle import Cell
from puzzle.grid import Edge
from puzzle_impls import Placement, Polyomino, TilingPuzzle


def solve(
    height: int,
    width: int,
    pieces: list[Polyomino],
    max_uses: dict[str, int] | None = None,
    forbidden_internal_edges: set[Edge] | None = None,
    board_cells: set[Cell] | None = None,
) -> list[Placement] | None:
    puzzle = TilingPuzzle(
        height, width, pieces,
        max_uses=max_uses,
        forbidden_internal_edges=forbidden_internal_edges,
        board_cells=board_cells,
    )
    solution = puzzle.solve()
    if solution is None:
        return None
    return puzzle.result(solution)
