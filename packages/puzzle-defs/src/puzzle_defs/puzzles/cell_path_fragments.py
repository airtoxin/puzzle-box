"""Local same-color degree and endpoint counts, separate from connectivity."""

from dataclasses import dataclass
from typing import ClassVar

from puzzle import Puzzle, SquareGrid, VarMap, sum_expr
from puzzle_defs.puzzles.component_shapes import _check_color
from puzzle_defs.puzzles.shading import _check_nonnegative
from puzzle_defs.ui import RuleUi, UiParameter


@dataclass(frozen=True)
class ColorDegreeRange:
    """Selected cells have minimum..maximum orthogonal same-color neighbors.

    Opposite-color cells are not constrained by their own neighbor counts.
    Absence, disconnected components, and cycles remain possible.
    """

    ui: ClassVar[RuleUi] = RuleUi(
        "color-degree-range", "同色マスの隣接数を制限",
        "対象色の各マスが上下左右で接する同色マス数を範囲内にします。連結や端点数は別条件です。対象色0個も許します。",
        (UiParameter("minimum", "同色の最少隣接数", "integer", 1, maximum=4),
         UiParameter("maximum", "同色の最多隣接数", "integer", 2, maximum=4),
         UiParameter("black", "隣接数を制限する色は黒（オフなら白）", "boolean", True)),
    )
    minimum: int = 1
    maximum: int = 2
    black: bool = True

    def __post_init__(self) -> None:
        if (any(type(n) is not int for n in (self.minimum, self.maximum))
                or not 0 <= self.minimum <= self.maximum <= 4):
            raise ValueError("Degree bounds must be integers with 0 <= minimum <= maximum <= 4")
        _check_color(self.black)

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        if self.minimum == 0 and self.maximum == 4:
            return
        selected = {c: black[c] if self.black else ~black[c] for c in board.cells}
        for cell in board.cells:
            degree = sum_expr(selected[n] for n in board.neighbors(cell))
            # Off-color cells retain only the natural 0..4 degree bounds.
            puzzle.add(degree >= sum_expr([selected[cell]] * self.minimum))
            puzzle.add(sum_expr([degree] + [selected[cell]] * (4-self.maximum)) <= 4)


@dataclass(frozen=True)
class ColorEndpointCount:
    """Count selected cells with exactly one orthogonal same-color neighbor.

    An isolated cell is not an endpoint. Branches, cycles, and disconnected
    components are not rejected by this fragment on their own.
    """

    ui: ClassVar[RuleUi] = RuleUi(
        "color-endpoint-count", "同色マスの端点数を固定",
        "同色の上下左右の隣接マスが1個だけの対象色マスを数えます。孤立マスは端点ではありません。枝分かれや連結は別条件です。",
        (UiParameter("count", "同色の端点数", "integer", 2),
         UiParameter("black", "端点を数える色は黒（オフなら白）", "boolean", True)),
    )
    count: int = 2
    black: bool = True

    def __post_init__(self) -> None:
        _check_nonnegative(self.count, "Endpoint count")
        _check_color(self.black)

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        if self.count > len(board.cells):
            raise ValueError("Endpoint count cannot exceed the board area")
        selected = {c: black[c] if self.black else ~black[c] for c in board.cells}
        degree = puzzle.int_var_map("color_degree", board.cells, 0, 4)
        endpoint = puzzle.bool_var_map("color_endpoint", board.cells)
        for cell in board.cells:
            puzzle.add(sum_expr([degree[cell]]) == sum_expr(selected[n] for n in board.neighbors(cell)))
            degree_one = degree[cell] == 1
            # endpoint iff (selected AND degree_one), in both directions.
            puzzle.add(endpoint[cell] <= selected[cell])
            puzzle.add(endpoint[cell] <= degree_one)
            puzzle.add(sum_expr([selected[cell], degree_one, ~endpoint[cell]]) <= 2)
        puzzle.add(sum_expr(endpoint[c] for c in board.cells) == self.count)
