"""Unnumbered Nurimisaki circles mark exactly the orthogonal white endpoints."""

from dataclasses import dataclass
from typing import ClassVar

from puzzle import Puzzle, SquareGrid, VarMap, sum_expr
from puzzle_defs.marker_layout import DEFAULT_ENDPOINT_MARKERS, MarkerGrid, marker_grid
from puzzle_defs.ui import RuleUi, UiChannel, UiParameter, UiRequirements


@dataclass(frozen=True)
class WhiteEndpointMarkers:
    """Marked cells are white endpoints, and unmarked cells cannot be endpoints.

    An endpoint is white with exactly one orthogonal white neighbor. Isolated
    white cells are not endpoints. Connectivity and cycles are not constrained.
    """

    ui: ClassVar[RuleUi] = RuleUi(
        "white-endpoint-markers", "丸を白の端点と一致させる",
        "丸は白で、上下左右の白い隣接マスが1個。丸なしの白マスは端点になれません。孤立白は端点ではなく、数字の直線長は未対応です。",
        (UiParameter("markers", "端点の丸（0は丸なし、1は丸あり）", "marker-grid", DEFAULT_ENDPOINT_MARKERS, maximum=1),),
        UiRequirements(channels=(UiChannel("answer", "binary-cells"), UiChannel("endpoint-markers", "cell-endpoint-markers"))),
    )
    markers: MarkerGrid

    def __post_init__(self) -> None:
        object.__setattr__(self, "markers", marker_grid(self.markers))

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        marker_grid(self.markers, rows=len(board.rows()), cols=len(board.cols()))
        degree = puzzle.int_var_map("white_endpoint_degree", board.cells, 0, 4)
        for cell in board.cells:
            puzzle.add(sum_expr([degree[cell]]) == sum_expr(~black[n] for n in board.neighbors(cell)))
            if self.markers[cell.row][cell.col]:
                puzzle.add(black[cell] == 0)
                puzzle.add(degree[cell] == 1)
            else:
                # If degree is one, this cell must be black. White cells with
                # degree zero, two, three or four remain allowed here.
                puzzle.add((degree[cell] == 1) <= black[cell])
