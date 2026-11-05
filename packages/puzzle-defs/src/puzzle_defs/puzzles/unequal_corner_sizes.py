"""Different component areas at corner contacts, independently of shape."""

from dataclasses import dataclass
from itertools import combinations
from typing import ClassVar

from puzzle import Puzzle, SquareGrid, VarMap, sum_expr
from puzzle_defs.puzzles.component_shapes import _check_color
from puzzle_defs.puzzles.room_components import MAX_ROOM_COMPONENT_CELLS, _component_uses
from puzzle_defs.ui import RuleUi, UiParameter

MAX_CORNER_SIZE_CELLS = MAX_ROOM_COMPONENT_CELLS


@dataclass(frozen=True)
class UnequalCornerComponentSizes:
    """Distinct orthogonal components touching diagonally must differ in area.

    Internal corner contacts and non-touching equal components are allowed.
    Shape, connectivity of the whole color, and nonemptiness are independent.
    Component candidates are bounded to at most nine board cells.
    """

    ui: ClassVar[RuleUi] = RuleUi(
        "unequal-corner-component-sizes", "同じ大きさの成分の角接触を禁止",
        "対象色の別々の上下左右成分が角で接するとき、面積を異ならせます。同一成分内の角接触や離れた同面積は許します。9セル以下の実験的な部品です。",
        (UiParameter("black", "面積を比べる色は黒（オフなら白）", "boolean", True),),
    )
    black: bool = True

    def __post_init__(self) -> None:
        _check_color(self.black)

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        if len(board.cells) > MAX_CORNER_SIZE_CELLS:
            raise ValueError(f"Unequal corner component sizes support at most {MAX_CORNER_SIZE_CELLS} board cells")
        rows,cols = len(board.rows()),len(board.cols())
        if min(rows,cols) == 1:
            return  # There are no diagonal contacts on a one-dimensional board.
        # A single internal room reuses exact-cover/maximality witnesses for
        # GLOBAL components. It is not a user room partition or a UI channel.
        for _,regions,uses in _component_uses(puzzle,board,black,((0,)*cols,)*rows,self.black):
            for first,second in combinations(regions,2):
                if (len(first.cells) == len(second.cells) and first.cells.isdisjoint(second.cells)
                        and any(abs(a.row-b.row) == abs(a.col-b.col) == 1 for a in first.cells for b in second.cells)):
                    puzzle.add(sum_expr([uses[first],uses[second]]) <= 1)
