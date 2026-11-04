"""Experimental fixed-size color components, using bounded region candidates."""

from dataclasses import dataclass
from typing import ClassVar

from puzzle import Puzzle, SquareGrid, VarMap, sum_expr
from puzzle_defs.regions import enumerate_connected_regions
from puzzle_defs.ui import RuleUi, UiParameter

MAX_COMPONENT_CELLS = 9


@dataclass(frozen=True)
class ColorComponentSize:
    """Every orthogonal component of one color has exactly size cells.

    Candidate enumeration is restricted to at most nine board cells. Empty
    selected-color sets are allowed. Candidate uses are witnesses, not answers.
    """

    ui: ClassVar[RuleUi] = RuleUi("color-component-size", "同色の連結成分のサイズを固定",
        "対象色の各連結成分を指定マス数にします。上下左右の接触だけを数え、対象色0個も許します。9セル以下の実験的な部品です。",
        (UiParameter("size", "各連結成分のマス数", "integer", 3, minimum=1),
         UiParameter("black", "黒を対象にする（オフなら白）", "boolean", True)))
    size: int
    black: bool = True

    def __post_init__(self) -> None:
        if type(self.size) is not int or self.size < 1:
            raise ValueError("Component size must be a positive integer")
        if type(self.black) is not bool:
            raise ValueError("black must be a boolean")

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        if len(board.cells) > MAX_COMPONENT_CELLS:
            raise ValueError(f"Fixed component sizes support at most {MAX_COMPONENT_CELLS} board cells")
        if self.size > len(board.cells):
            raise ValueError("Component size cannot exceed the board area")
        regions = sorted(enumerate_connected_regions(board,self.size), key=lambda r: tuple(sorted(r.cells)))
        uses = puzzle.bool_var_map("component_use",regions)
        selected = {c:black[c] if self.black else ~black[c] for c in board.cells}
        # Every selected cell is covered once. An active placement must be a
        # whole component: no same-color cell may touch its exterior boundary.
        for cell in board.cells:
            puzzle.add(sum_expr(uses[r] for r in regions if cell in r.cells) == selected[cell])
        for region in regions:
            boundary = {n for c in region.cells for n in board.neighbors(c)} - region.cells
            for cell in sorted(boundary):
                puzzle.add(sum_expr([uses[region],selected[cell]]) <= 1)
